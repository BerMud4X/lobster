import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from logger import logger
from report_figures import generate_all_figures
from report_exporter import export_report
import audit_logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def _build_clinical_prompt(
    patient_id: str,
    protocol: dict,
    exercises_df: pd.DataFrame,
    syntheses: list[dict],
    language: str = "English",
) -> str:
    protocol_desc = protocol.get("description", "Not specified") if protocol else "Not specified"
    obj_principal = protocol.get("obj_principal", "N/A") if protocol else "N/A"
    obj_secondaires = ", ".join(protocol.get("obj_secondaires", [])) if protocol else "N/A"

    sessions_detail = []
    for session in exercises_df["session"].unique():
        s_df = exercises_df[exercises_df["session"] == session]
        synth = next((s for s in syntheses if s["session"] == session), {})
        sessions_detail.append({
            "session": session,
            "exercises": s_df[["exercise_name", "code_base", "objective", "series", "repetitions", "time", "assistance"]].to_dict(orient="records"),
            "intensity": synth.get("session_intensity", "unknown"),
            "clinical_summary": synth.get("clinical_summary", ""),
            "recommendations": synth.get("recommendations", []),
        })

    return f"""You are a clinical physiotherapist writing a follow-up document and observation record for a patient file.

PROTOCOL:
- Description: {protocol_desc}
- Primary objective: {obj_principal}
- Secondary objectives: {obj_secondaires}

PATIENT: {patient_id}

SESSION DATA:
{json.dumps(sessions_detail, ensure_ascii=False, indent=2)}

OUTPUT LANGUAGE: {language}

YOUR TASK:
Write a clinical follow-up document ENTIRELY in {language}. All narrative fields (follow_up_summary, progression_notes, observations, patient_response, next_session_goals, recommendations) MUST be in {language}. Do NOT mix languages.

Return a JSON object with exactly these keys:
{{
  "follow_up_summary": "Global follow-up summary for the patient across all sessions (3-4 paragraphs, clinical tone)",
  "progression_notes": "Assessment of the patient's progression across sessions — what improved, what remained stable, any concerns",
  "observation_records": [
    {{
      "session": "session name",
      "observations": "clinical observations for this session (2-3 sentences, first-person clinical tone as if written by the therapist)",
      "patient_response": "how the patient responded to the exercises",
      "next_session_goals": "specific goals for the next session"
    }}
  ],
  "recommendations": "Clinical recommendations for continuing care based on the observed progression"
}}

IMPORTANT: Return ONLY a valid JSON object. No markdown. No code blocks. Use a professional clinical tone."""


def _parse_clinical_response(raw: str) -> dict:
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()
    if not raw.startswith("{"):
        start = raw.find("{")
        if start != -1:
            raw = raw[start:]
    return json.loads(raw)


def _call_ai(prompt: str, model: str, provider: str) -> dict:
    if provider == "Anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found.")
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        for attempt in range(1, 3):
            try:
                response = client.messages.create(
                    model=model, max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw = response.content[0].text.strip()
                parsed = _parse_clinical_response(raw)
                audit_logger.log_call("clinical", "Anthropic", model, prompt, raw, parsed=parsed)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[ClinicalWriter/Anthropic] attempt {attempt} invalid JSON: {e}")
    else:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found.")
        from mistralai.client import Mistral
        client = Mistral(api_key=api_key)
        for attempt in range(1, 3):
            try:
                response = client.chat.complete(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw = response.choices[0].message.content.strip()
                parsed = _parse_clinical_response(raw)
                audit_logger.log_call("clinical", "Mistral", model, prompt, raw, parsed=parsed)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[ClinicalWriter/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[ClinicalWriter] AI call failed — returning empty sections.")
    return {}


def write_clinical_report(
    exercises_df: pd.DataFrame,
    syntheses: list[dict],
    protocol: dict,
    output_path: str,
    fmt: str = "pdf",
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    language: str = "English",
) -> list[Path]:
    """
    Agent 5 — Generates a clinical follow-up report and observation record per patient.
    Output narrative is written in `language` (default: English).
    Returns a list of generated file paths (one per patient).
    """
    logger.info(f"[Agent 5 / ClinicalWriter] generating report(s) in {language}")
    print(f"\n=== AGENT 5 — CLINICAL REPORT ({language}) ===")

    output_dir = Path(output_path).parent / "figures"
    figures = generate_all_figures(exercises_df, output_dir)
    print(f"  {len(figures)} figure(s) saved to {output_dir}")

    patients = exercises_df["patient_id"].unique().tolist()
    output_paths = []

    for patient_id in patients:
        print(f"\n  Patient: {patient_id}")
        p_df = exercises_df[exercises_df["patient_id"] == patient_id]
        p_syntheses = [s for s in syntheses if s.get("patient_id") == patient_id]

        prompt = _build_clinical_prompt(patient_id, protocol, p_df, p_syntheses, language=language)
        content = _call_ai(prompt, model=model, provider=provider)

        if not content:
            content = {
                "follow_up_summary": "Follow-up summary could not be generated.",
                "progression_notes": "",
                "observation_records": [],
                "recommendations": "",
            }

        sections = [
            {"heading": "Follow-up Summary", "body": content.get("follow_up_summary", "")},
            {"heading": "Progression Notes", "body": content.get("progression_notes", "")},
            {"heading": "Recommendations", "body": content.get("recommendations", "")},
        ]

        # Observation records — one sub-section per session
        obs_records = content.get("observation_records", [])
        if obs_records:
            sections.append({"heading": "Observation Records", "body": ""})
            for obs in obs_records:
                session_text = (
                    f"Observations: {obs.get('observations', '')}\n\n"
                    f"Patient response: {obs.get('patient_response', '')}\n\n"
                    f"Next session goals: {obs.get('next_session_goals', '')}"
                )
                sections.append({"heading": f"  {obs.get('session', '')}", "body": session_text})

        # Per-patient figures
        p_figures = generate_all_figures(p_df, output_dir / patient_id)

        protocol_desc = protocol.get("description", "Clinical Follow-up") if protocol else "Clinical Follow-up"
        title = f"Clinical Follow-up — {patient_id} — {protocol_desc}"

        # Build per-patient output path
        p_output = str(Path(output_path).parent / f"{Path(output_path).stem}_{patient_id}.{fmt}")
        out = export_report(sections, p_figures, p_output, fmt=fmt, title=title)
        output_paths.append(out)
        print(f"  Report saved: {out}")

    return output_paths
