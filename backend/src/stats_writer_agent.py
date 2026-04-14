"""
Agent 7 — Statistical Writer.

Takes the deterministic stats results (from statistical_analyzer.analyze_assessments)
and produces a narrative interpretation suitable for a Methods+Results section.

The agent NEVER computes numbers — it only reads the pre-computed values and
writes prose around them. This separation guarantees no AI hallucination of stats.
"""

import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from logger import logger
import audit_logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def _build_prompt(stats_results: dict, protocol: dict | None) -> str:
    protocol_block = ""
    if protocol:
        protocol_block = (
            f"PROTOCOL: {protocol.get('description', 'N/A')}\n"
            f"Primary objective: {protocol.get('obj_principal', 'N/A')}\n"
            f"Secondary objectives: {', '.join(protocol.get('obj_secondaires', []))}\n\n"
        )

    return f"""You are a scientific writer interpreting pre-computed statistical results for a clinical research publication.

{protocol_block}STATISTICAL RESULTS (computed deterministically, do NOT recompute or invent numbers):
{json.dumps(stats_results, ensure_ascii=False, indent=2)}

YOUR TASK:
Write the Methods and Results sections for the statistical analysis.

Return ONLY a valid JSON object with these keys:
{{
  "methods":     "1 paragraph: which tests were applied, why (e.g., paired t-test for normally distributed continuous, Wilcoxon for ordinal/non-normal), normality assumptions checked.",
  "results":     "Detailed paragraph(s) reporting findings test by test. ALWAYS cite numbers verbatim from the data above (n, mean ± std, p-value, effect size). Mention significant results first.",
  "key_findings": ["bullet 1 (one sentence)", "bullet 2", "..."],
  "limitations": "1-2 sentences on limitations visible in the data (small sample, missing values, etc.)"
}}

CRITICAL RULES:
- Use ONLY the numbers provided. Do NOT invent any value.
- Format p-values as p<0.001 if below 0.001, otherwise p=X.XXX.
- Round means/SDs to 2 decimals in prose.
- Be honest: if a test is "not statistically significant", say so. Do not over-interpret.
- Return ONLY the JSON object. No markdown, no code blocks."""


def _parse_response(raw: str) -> dict:
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
                parsed = _parse_response(raw)
                audit_logger.log_call("stats_writer", "Anthropic", model, prompt, raw, parsed=parsed)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[StatsWriter/Anthropic] attempt {attempt} invalid JSON: {e}")
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
                parsed = _parse_response(raw)
                audit_logger.log_call("stats_writer", "Mistral", model, prompt, raw, parsed=parsed)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[StatsWriter/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[StatsWriter] all attempts failed — returning empty narrative.")
    return {}


def write_stats_narrative(
    stats_results: dict,
    protocol: dict | None = None,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
) -> dict:
    """
    Agent 7 — Generates Methods + Results narrative for the statistical analysis.

    Returns:
        {
            "methods":     str,
            "results":     str,
            "key_findings": list[str],
            "limitations": str,
        }
    """
    if not stats_results.get("tests"):
        logger.info("[Agent 7 / StatsWriter] no tests to interpret.")
        return {
            "methods": "", "results": "No statistical results were available.",
            "key_findings": [], "limitations": "",
        }

    logger.info(f"[Agent 7 / StatsWriter] interpreting {stats_results['n_tests']} test(s)")
    print(f"\n=== AGENT 7 — STATS WRITER ===")
    print(f"  Interpreting {stats_results['n_tests']} test(s) for {stats_results['n_patients']} patient(s)...")

    prompt = _build_prompt(stats_results, protocol)
    narrative = _call_ai(prompt, model=model, provider=provider)

    if not narrative:
        narrative = {
            "methods": "Statistical methods description could not be generated.",
            "results": "Statistical results narrative could not be generated.",
            "key_findings": [],
            "limitations": "",
        }

    return narrative
