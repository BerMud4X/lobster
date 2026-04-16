import json
import re
from collections import Counter
from logger import logger
from reference_loader import get_objectives_list
import audit_logger
import prompt_cache


def _build_synthesis_prompt(patient_id: str, session: str, exercises: list[dict], objectives_ref: list[dict], protocol: dict = None) -> str:
    objectives_map = {o["code"]: o["label"] for o in objectives_ref}
    exercises_str = json.dumps(exercises, ensure_ascii=False, indent=2)

    protocol_block = ""
    if protocol:
        sec = ", ".join(protocol.get("obj_secondaires", [])) or "none"
        protocol_block = f"""
RESEARCH PROTOCOL:
- Description: {protocol.get("description", "N/A")}
- Primary objective: {protocol.get("obj_principal", "unknown")}
- Secondary objectives: {sec}

In your clinical_summary and recommendations, comment on whether the session is aligned with the protocol objectives.
"""

    return f"""You are a senior clinical physiotherapy expert writing a session summary for a patient file.
{protocol_block}

PATIENT: {patient_id}
SESSION: {session}

VALIDATED EXERCISES FOR THIS SESSION:
{exercises_str}

THERAPEUTIC OBJECTIVES LEGEND:
{json.dumps(objectives_map, ensure_ascii=False)}

YOUR TASK:
Produce a structured clinical summary of this session. Return a JSON object with this exact structure:
{{
  "dominant_objective": "the most frequent objective code in this session",
  "dominant_objective_label": "its full label",
  "muscle_groups_worked": ["list of unique muscles across all exercises"],
  "session_intensity": "low" | "moderate" | "high",
  "clinical_summary": "2-3 sentence clinical narrative of what was worked on and why (professional tone, in the language of the original notes)",
  "recommendations": ["1-3 short clinical recommendations for the next session based on what was done"]
}}

Base session_intensity on: number of exercises, repetitions, time, and code_base types (Cardio/Functional = higher).

IMPORTANT: Return ONLY a valid JSON object. No explanation. No markdown. No code blocks."""


def _parse_synthesis_response(raw: str) -> dict:
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()

    if not raw.startswith("{"):
        start = raw.find("{")
        if start != -1:
            raw = raw[start:]

    return json.loads(raw)


def _derive_dominant_objective(exercises: list[dict], objectives_ref: list[dict]) -> tuple[str, str]:
    objectives_map = {o["code"]: o["label"] for o in objectives_ref}
    codes = [ex.get("objective", "unknown") for ex in exercises if ex.get("objective") != "unknown"]
    if not codes:
        return "unknown", "Unknown"
    most_common = Counter(codes).most_common(1)[0][0]
    return most_common, objectives_map.get(most_common, "Unknown")


def _call_mistral_synthesis(model: str, prompt: str) -> dict:
    import os
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    api_key = os.getenv("MISTRAL_API_KEY")

    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found.")

    from mistralai.client import Mistral
    client = Mistral(api_key=api_key)

    for attempt in range(1, 3):
        try:
            logger.info(f"[Synthesis/Mistral/{model}] attempt {attempt}")

            def _fetch():
                r = client.chat.complete(model=model, messages=[{"role": "user", "content": prompt}])
                return r.choices[0].message.content.strip()
            raw, cached = prompt_cache.get_or_fetch("Mistral", model, prompt, _fetch)
            logger.info(f"[Synthesis/Mistral] raw ({'cache' if cached else 'api'}): {raw[:200]}")
            parsed = _parse_synthesis_response(raw)
            audit_logger.log_call("synthesis", "Mistral", model, prompt, raw, parsed=parsed,
                                  metadata={"cache_hit": cached})
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"[Synthesis/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[Synthesis/Mistral] all attempts failed")
    return {}


def _call_anthropic_synthesis(model: str, prompt: str) -> dict:
    import os
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(1, 3):
        try:
            logger.info(f"[Synthesis/Anthropic/{model}] attempt {attempt}")

            def _fetch():
                r = client.messages.create(
                    model=model, max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                return r.content[0].text.strip()
            raw, cached = prompt_cache.get_or_fetch("Anthropic", model, prompt, _fetch)
            logger.info(f"[Synthesis/Anthropic] raw ({'cache' if cached else 'api'}): {raw[:200]}")
            parsed = _parse_synthesis_response(raw)
            audit_logger.log_call("synthesis", "Anthropic", model, prompt, raw, parsed=parsed,
                                  metadata={"cache_hit": cached})
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"[Synthesis/Anthropic] attempt {attempt} invalid JSON: {e}")

    logger.error("[Synthesis/Anthropic] all attempts failed")
    return {}


def synthesize_session(
    patient_id: str,
    session: str,
    exercises: list[dict],
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    protocol: dict = None,
) -> dict:
    """
    Agent 3 — Produces a clinical synthesis of a session.

    Returns:
        {
            "patient_id": str,
            "session": str,
            "dominant_objective": str,
            "dominant_objective_label": str,
            "muscle_groups_worked": list[str],
            "session_intensity": str,
            "clinical_summary": str,
            "recommendations": list[str]
        }
    """
    objectives_ref = get_objectives_list()
    prompt = _build_synthesis_prompt(patient_id, session, exercises, objectives_ref, protocol=protocol)

    logger.info(f"[Agent 3 / Synthesis] synthesizing session '{session}' for patient '{patient_id}' with {provider}/{model}")

    if provider == "Anthropic":
        result = _call_anthropic_synthesis(model, prompt)
    else:
        result = _call_mistral_synthesis(model, prompt)

    # Fallback: derive dominant objective locally if AI failed
    if not result:
        dominant_code, dominant_label = _derive_dominant_objective(exercises, objectives_ref)
        result = {
            "dominant_objective": dominant_code,
            "dominant_objective_label": dominant_label,
            "muscle_groups_worked": list({m for ex in exercises for m in ex.get("muscles", []) if m}),
            "session_intensity": "unknown",
            "clinical_summary": "Synthesis could not be generated.",
            "recommendations": [],
        }

    result["patient_id"] = patient_id
    result["session"] = session

    logger.info(f"[Agent 3 / Synthesis] done — intensity={result.get('session_intensity')}, objective={result.get('dominant_objective')}")
    return result
