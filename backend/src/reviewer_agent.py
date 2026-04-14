import json
import re
from logger import logger
from reference_loader import get_objectives_list, validate_code_base, validate_objective_code, get_muscles_latin_list
import audit_logger


def _build_review_prompt(original_text: str, exercises: list[dict], objectives_ref: list[dict], muscles_ref: list[str], protocol: dict = None) -> str:
    objectives_str = "\n".join(f"- {o['code']}: {o['label']}" for o in objectives_ref)
    muscles_str = "\n".join(f"- {m}" for m in muscles_ref)
    exercises_str = json.dumps(exercises, ensure_ascii=False, indent=2)

    protocol_block = ""
    if protocol:
        sec = ", ".join(protocol.get("obj_secondaires", [])) or "none"
        protocol_block = f"""
RESEARCH PROTOCOL CONTEXT:
- Description: {protocol.get("description", "N/A")}
- Primary objective: {protocol.get("obj_principal", "unknown")}
- Secondary objectives: {sec}

IMPORTANT: Each exercise's objective field MUST be either the primary objective or one of the secondary objectives listed above. Flag any objective outside this list as an error.
"""

    return f"""You are a senior clinical physiotherapy expert reviewing the work of a junior analyst.
{protocol_block}

ORIGINAL THERAPIST NOTE:
"{original_text}"

EXTRACTED EXERCISES (to review):
{exercises_str}

VALID CODE_BASE VALUES: Push, Pull, Transfer, Balance, Stretch, Cardio, Functional, unknown

THERAPEUTIC OBJECTIVES:
{objectives_str}

VALID MUSCLES (only these are accepted):
{muscles_str}

YOUR TASK:
Review each extracted exercise for clinical coherence and accuracy. Check:
1. Is the exercise_name clinically appropriate for the description?
2. Is code_base coherent with the exercise type?
3. Is the objective coherent with the exercise and code_base?
4. Are the muscles anatomically correct for this exercise?
5. Are series, repetitions per set, time, and assistance correctly extracted from the text? Note: series = number of sets, repetitions = reps per set — these are distinct fields.

Return a JSON object with this exact structure:
{{
  "decision": "approved" | "corrected" | "rejected",
  "confidence": 0.0 to 1.0,
  "issues": ["list of problems found, empty if none"],
  "exercises": [corrected exercises array — same structure as input, with your corrections applied]
}}

- "approved": everything is correct, return exercises unchanged
- "corrected": you fixed one or more fields, return corrected exercises
- "rejected": the extraction is too wrong to fix (e.g. completely wrong exercises identified), explain in issues

IMPORTANT: Return ONLY a valid JSON object. No explanation. No markdown. No code blocks."""


def _parse_review_response(raw: str) -> dict:
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()

    if not raw.startswith("{"):
        start = raw.find("{")
        if start != -1:
            raw = raw[start:]

    result = json.loads(raw)

    # Validate and normalize exercises in the review
    muscles_ref = get_muscles_latin_list()
    for ex in result.get("exercises", []):
        ex["code_base"] = validate_code_base(ex.get("code_base", ""))
        ex["objective"] = validate_objective_code(ex.get("objective", ""))
        ex["muscles"] = [m for m in (ex.get("muscles") or []) if m in muscles_ref]

    return result


def _call_mistral_review(model: str, prompt: str) -> dict:
    from reference_loader import load_exercises
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
            logger.info(f"[Reviewer/Mistral/{model}] attempt {attempt}")
            response = client.chat.complete(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.choices[0].message.content.strip()
            logger.info(f"[Reviewer/Mistral] raw: {raw[:200]}")
            parsed = _parse_review_response(raw)
            audit_logger.log_call("reviewer", "Mistral", model, prompt, raw, parsed=parsed)
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"[Reviewer/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[Reviewer/Mistral] all attempts failed, returning approved as fallback")
    return _fallback_review()


def _call_anthropic_review(model: str, prompt: str) -> dict:
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
            logger.info(f"[Reviewer/Anthropic/{model}] attempt {attempt}")
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            logger.info(f"[Reviewer/Anthropic] raw: {raw[:200]}")
            parsed = _parse_review_response(raw)
            audit_logger.log_call("reviewer", "Anthropic", model, prompt, raw, parsed=parsed)
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"[Reviewer/Anthropic] attempt {attempt} invalid JSON: {e}")

    logger.error("[Reviewer/Anthropic] all attempts failed, returning approved as fallback")
    return _fallback_review()


def _fallback_review() -> dict:
    return {
        "decision": "approved",
        "confidence": 0.0,
        "issues": ["Reviewer failed to parse — exercises passed through unreviewed"],
        "exercises": [],
    }


def review_exercises(
    original_text: str,
    exercises: list[dict],
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    protocol: dict = None,
) -> dict:
    """
    Agent 2 — Reviews extracted exercises for clinical coherence.

    Returns:
        {
            "decision": "approved" | "corrected" | "rejected",
            "confidence": float,
            "issues": list[str],
            "exercises": list[dict]   # corrected exercises
        }
    """
    objectives_ref = get_objectives_list()
    muscles_ref = get_muscles_latin_list()
    prompt = _build_review_prompt(original_text, exercises, objectives_ref, muscles_ref, protocol=protocol)

    logger.info(f"[Agent 2 / Reviewer] reviewing {len(exercises)} exercise(s) with {provider}/{model}")

    if provider == "Anthropic":
        result = _call_anthropic_review(model, prompt)
    else:
        result = _call_mistral_review(model, prompt)

    # If fallback returned empty exercises, preserve originals
    if not result.get("exercises"):
        result["exercises"] = exercises

    logger.info(f"[Agent 2 / Reviewer] decision={result['decision']}, confidence={result['confidence']}, issues={result['issues']}")
    return result
