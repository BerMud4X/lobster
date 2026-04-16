import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from logger import logger
from report_figures import generate_all_figures
from report_exporter import export_report
from cohort_analyzer import compute_cohort_stats, format_cohort_summary
import audit_logger
import prompt_cache

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def _build_publication_prompt(
    protocol: dict,
    exercises_df: pd.DataFrame,
    syntheses: list[dict],
    cohort_stats: dict = None,
) -> str:
    protocol_desc = protocol.get("description", "Not specified") if protocol else "Not specified"
    obj_principal = protocol.get("obj_principal", "N/A") if protocol else "N/A"
    obj_secondaires = ", ".join(protocol.get("obj_secondaires", [])) if protocol else "N/A"

    sessions_summary = []
    for s in syntheses:
        sessions_summary.append({
            "session": s.get("session"),
            "patient_id": s.get("patient_id"),
            "intensity": s.get("session_intensity"),
            "dominant_objective": s.get("dominant_objective"),
            "clinical_summary": s.get("clinical_summary"),
        })

    cohort_block = ""
    extra_keys = ""
    if cohort_stats and cohort_stats.get("n_patients", 0) >= 2:
        cohort_block = f"""
COHORT STATISTICS (computed from raw data):
{format_cohort_summary(cohort_stats)}

Per-patient breakdown:
{json.dumps(cohort_stats.get("per_patient_breakdown", []), ensure_ascii=False, indent=2)}
"""
        extra_keys = """,
  "cohort_analysis": "Inter-patient analysis — describe cohort composition, variability, and any patient-level patterns visible in the breakdown and statistics above. Mention means ± std where relevant."""
    else:
        n_sessions = exercises_df["session"].nunique()
        n_exercises = len(exercises_df)
        cohort_block = f"""
DATA SUMMARY (single-patient study):
- Total sessions: {n_sessions}
- Total exercises recorded: {n_exercises}
"""

    return f"""You are a scientific writer helping to draft a clinical research publication.

STUDY PROTOCOL:
- Description: {protocol_desc}
- Primary objective: {obj_principal}
- Secondary objectives: {obj_secondaires}
{cohort_block}
SESSION SUMMARIES:
{json.dumps(sessions_summary, ensure_ascii=False, indent=2)}

YOUR TASK:
Write the following sections of a scientific publication in the same language as the clinical summaries above.

Return a JSON object with exactly these keys:
{{
  "abstract": "150-200 word structured abstract (background, methods, results, conclusion). If the cohort has 2+ patients, mention sample size, means ± std",
  "study_context": "2-3 paragraphs on the study context and rationale derived from the protocol",
  "interventions": "Detailed description of the interventions performed across all sessions, suitable for a Methods section",
  "results": "Objective description of what was observed in the data (frequency, distribution, volume, patterns). Use cohort statistics if available.",
  "discussion": "2-3 key discussion points that emerge from the data — notable findings, patterns worth highlighting for reviewers"{extra_keys}
}}

IMPORTANT: Return ONLY a valid JSON object. No markdown. No code blocks. Write in a formal scientific style."""


def _parse_publication_response(raw: str) -> dict:
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
                def _fetch():
                    r = client.messages.create(
                        model=model, max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return r.content[0].text.strip()
                raw, cached = prompt_cache.get_or_fetch("Anthropic", model, prompt, _fetch)
                parsed = _parse_publication_response(raw)
                audit_logger.log_call("publication", "Anthropic", model, prompt, raw, parsed=parsed,
                                      metadata={"cache_hit": cached})
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[PublicationAgent/Anthropic] attempt {attempt} invalid JSON: {e}")
    else:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found.")
        from mistralai.client import Mistral
        client = Mistral(api_key=api_key)
        for attempt in range(1, 3):
            try:
                def _fetch():
                    r = client.chat.complete(model=model, messages=[{"role": "user", "content": prompt}])
                    return r.choices[0].message.content.strip()
                raw, cached = prompt_cache.get_or_fetch("Mistral", model, prompt, _fetch)
                parsed = _parse_publication_response(raw)
                audit_logger.log_call("publication", "Mistral", model, prompt, raw, parsed=parsed,
                                      metadata={"cache_hit": cached})
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[PublicationAgent/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[PublicationAgent] AI call failed — returning empty sections.")
    return {}


def write_publication_report(
    exercises_df: pd.DataFrame,
    syntheses: list[dict],
    protocol: dict,
    output_path: str,
    fmt: str = "pdf",
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    assessments_df: pd.DataFrame | None = None,
) -> Path:
    """
    Agent 4 — Generates a publication-ready clinical report.
    """
    logger.info(f"[Agent 4 / Publication] generating report for {exercises_df['patient_id'].nunique()} patient(s)")
    print(f"\n=== AGENT 4 — PUBLICATION REPORT ===")

    output_dir = Path(output_path).parent / "figures"

    # Generate figures
    print("  Generating figures...")
    figures = generate_all_figures(exercises_df, output_dir)
    print(f"  {len(figures)} figure(s) saved to {output_dir}")

    # Compute cohort statistics (used only if 2+ patients)
    cohort_stats = compute_cohort_stats(exercises_df)
    is_cohort = cohort_stats.get("n_patients", 0) >= 2

    # Generate narrative via AI
    print("  Generating narrative (AI)...")
    prompt = _build_publication_prompt(protocol, exercises_df, syntheses, cohort_stats=cohort_stats)
    content = _call_ai(prompt, model=model, provider=provider)

    if not content:
        content = {
            "abstract": "Abstract could not be generated.",
            "study_context": "Study context could not be generated.",
            "interventions": "Interventions could not be generated.",
            "results": "Results could not be generated.",
            "discussion": "Discussion could not be generated.",
        }

    # Build sections
    sections = [
        {"heading": "Abstract", "body": content.get("abstract", "")},
        {"heading": "Study Context", "body": content.get("study_context", "")},
        {"heading": "Interventions", "body": content.get("interventions", "")},
        {"heading": "Results", "body": content.get("results", "")},
    ]

    # Cohort analysis section (only when 2+ patients)
    if is_cohort:
        sections.append({
            "heading": "Cohort Analysis",
            "body": content.get("cohort_analysis", "") + "\n\n" + format_cohort_summary(cohort_stats),
        })

    # Statistical Analysis section (only if assessments data is provided)
    if assessments_df is not None and not assessments_df.empty:
        from statistical_analyzer import analyze_assessments, format_summary
        from stats_writer_agent import write_stats_narrative
        from stats_figures import generate_stats_figures

        stats_results = analyze_assessments(assessments_df)
        stats_narrative = write_stats_narrative(stats_results, protocol=protocol, model=model, provider=provider)
        stats_figs = generate_stats_figures(assessments_df, stats_results, output_dir)
        figures.update(stats_figs)

        sections.append({"heading": "Statistical Methods", "body": stats_narrative.get("methods", "")})
        sections.append({"heading": "Statistical Results", "body": stats_narrative.get("results", "")})
        if stats_narrative.get("key_findings"):
            sections.append({
                "heading": "Key Findings",
                "body": "\n".join(f"• {f}" for f in stats_narrative["key_findings"]),
            })
        sections.append({"heading": "Limitations", "body": stats_narrative.get("limitations", "")})
        # Append the deterministic summary at the end so reviewers can verify numbers
        sections.append({"heading": "Statistical Summary (raw)", "body": format_summary(stats_results)})

    sections.append({"heading": "Discussion", "body": content.get("discussion", "")})

    protocol_desc = protocol.get("description", "Clinical Study") if protocol else "Clinical Study"
    title = f"Publication Report — {protocol_desc}"

    out = export_report(sections, figures, output_path, fmt=fmt, title=title)
    print(f"  Report saved: {out}")
    return out
