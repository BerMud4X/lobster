"""
Agent 6 — Assessment Schema Detection.

Reads the raw content of a single Excel sheet (the test data filled by a clinician)
and returns standardized assessment records in canonical long format:

    {
        "test_name":  str,
        "test_type":  "quantitative_continuous" | "quantitative_discrete"
                      | "qualitative_ordinal" | "qualitative_nominal" | "demographic",
        "scale":      str | None,           # e.g. "0-56", "seconds"
        "data": [
            {"patient_id": str, "sub_category": str | None,
             "timepoint":  str | None, "value": float | int | str | None,
             "missing_reason": str | None},   # NT / NA / NC / etc.
            ...
        ]
    }

The agent's job is to absorb whatever layout the clinician used (patients in
columns or rows, multi-level headers, sub-categories like muscles, special
missing codes) and produce a clean canonical structure.
"""

import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from logger import logger
import audit_logger
import prompt_cache

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Codes commonly used by clinicians for missing / not-applicable values
MISSING_CODES = {"NT", "NA", "NC", "ND", "N/A", "n/a", "-", ""}


def _serialize_sheet(df: pd.DataFrame, max_rows: int = 60) -> str:
    """Renders the raw sheet content as a compact text grid for the AI prompt."""
    rows = []
    for r_idx, row in df.head(max_rows).iterrows():
        cells = [
            "" if pd.isna(v) else str(v).strip()
            for v in row.values
        ]
        # Trim trailing empty cells to reduce noise
        while cells and cells[-1] == "":
            cells.pop()
        if cells:
            rows.append(f"R{r_idx} | " + " | ".join(cells))
    if len(df) > max_rows:
        rows.append(f"... ({len(df) - max_rows} more rows truncated)")
    return "\n".join(rows)


def _build_prompt(sheet_name: str, df: pd.DataFrame) -> str:
    grid = _serialize_sheet(df)
    return f"""You are a clinical data extractor. You receive the raw content of one Excel sheet
that contains an assessment test (e.g., Ashworth, Tardieu, NHPT, Maximal grip strength).

The data layout varies wildly between clinicians:
- Patients can appear as COLUMNS or as ROWS
- Timepoints (PRE / POST / pre_test / etc.) may be in headers, sub-headers, or cell values
- The test may have SUB-CATEGORIES (e.g., per muscle for Ashworth: Pronators, Supinators, ...)
- Empty rows/columns at the top and around the data are common
- Missing values are often coded as: NT (not testable), NA (not assessed), NC (not completed)

SHEET NAME: "{sheet_name}"

RAW SHEET CONTENT (rows prefixed by R{{index}}):
{grid}

YOUR TASK:
Identify the structure and extract every (patient × timepoint × sub_category) value into canonical long format.

Return ONLY a valid JSON object:
{{
  "test_name":   "the most likely test name (use sheet name if unclear)",
  "test_type":   "one of: quantitative_continuous, quantitative_discrete, qualitative_ordinal, qualitative_nominal, demographic",
  "scale":       "the scale or unit if visible, e.g. '0-5', 'seconds', 'kg', or null",
  "data": [
    {{"patient_id": "Patient 1", "sub_category": "Pronators", "timepoint": "PRE",  "value": 2,    "missing_reason": null}},
    {{"patient_id": "Patient 1", "sub_category": "Pronators", "timepoint": "POST", "value": 2,    "missing_reason": null}},
    {{"patient_id": "Patient 2", "sub_category": "Pronators", "timepoint": "PRE",  "value": null, "missing_reason": "NT"}}
  ]
}}

RULES:
- For numeric values, return a number. For codes like NT/NA/NC, set "value": null and put the code in "missing_reason".
- "sub_category" is null when the test has no sub-divisions (e.g., grip strength has none, but Ashworth has muscle subcategories).
- "timepoint" must be normalized to one of: "pre", "post", "during", "retention", or null if unknown.
- If the sheet looks like demographics (age, gender), set test_type="demographic" and use the field name as sub_category.
- Skip rows that are clearly comments, legends, or empty.
- IMPORTANT: Return ONLY the JSON object. No markdown, no explanation, no code blocks."""


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


def _validate_extraction(parsed) -> dict:
    """
    Defensive validation of Agent 6's output. Guarantees downstream code
    always receives a well-formed dict, even if the AI returns garbage.
    """
    if not isinstance(parsed, dict):
        logger.warning(f"[SchemaAgent] response is not a dict ({type(parsed).__name__}) — replacing with empty.")
        return {"test_name": "unknown", "test_type": "unknown", "scale": None, "data": []}

    test_name = parsed.get("test_name")
    if not isinstance(test_name, str) or not test_name.strip():
        test_name = "unknown"

    test_type = parsed.get("test_type")
    if not isinstance(test_type, str) or not test_type.strip():
        test_type = "unknown"

    scale = parsed.get("scale")
    if scale is not None and not isinstance(scale, (str, int, float)):
        scale = None

    data = parsed.get("data")
    if not isinstance(data, list):
        logger.warning(f"[SchemaAgent] 'data' is not a list ({type(data).__name__}) — discarding.")
        data = []
    else:
        data = [d for d in data if isinstance(d, dict)]

    return {
        "test_name": str(test_name).strip(),
        "test_type": str(test_type).strip(),
        "scale": scale,
        "data": data,
    }


def _normalize_record(rec: dict) -> dict:
    """Normalizes one extracted record (timepoint case, missing detection)."""
    val = rec.get("value")
    missing = rec.get("missing_reason")

    # Detect missing codes that AI may have placed in 'value' as strings
    if isinstance(val, str):
        val_str = val.strip().upper()
        if val_str in MISSING_CODES:
            missing = missing or val_str
            val = None

    timepoint = rec.get("timepoint")
    if isinstance(timepoint, str):
        timepoint = timepoint.strip().lower()
        # Map common variants
        timepoint_map = {
            "pre_test": "pre", "pretest": "pre", "baseline": "pre",
            "post_test": "post", "posttest": "post", "final": "post",
            "follow_up": "retention", "followup": "retention", "ret": "retention",
        }
        timepoint = timepoint_map.get(timepoint, timepoint)

    return {
        "patient_id":     rec.get("patient_id"),
        "sub_category":   rec.get("sub_category"),
        "timepoint":      timepoint,
        "value":          val,
        "missing_reason": missing,
    }


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
                def _fetch():
                    r = client.messages.create(
                        model=model, max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return r.content[0].text.strip()
                raw, cached = prompt_cache.get_or_fetch("Anthropic", model, prompt, _fetch)
                parsed = _validate_extraction(_parse_response(raw))
                audit_logger.log_call("schema_detector", "Anthropic", model, prompt, raw, parsed=parsed,
                                      metadata={"cache_hit": cached})
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[SchemaAgent/Anthropic] attempt {attempt} invalid JSON: {e}")
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
                parsed = _validate_extraction(_parse_response(raw))
                audit_logger.log_call("schema_detector", "Mistral", model, prompt, raw, parsed=parsed,
                                      metadata={"cache_hit": cached})
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"[SchemaAgent/Mistral] attempt {attempt} invalid JSON: {e}")

    logger.error("[SchemaAgent] all attempts failed — returning empty extraction.")
    return {"test_name": "unknown", "test_type": "unknown", "scale": None, "data": []}


def detect_and_extract(
    sheet_name: str,
    df: pd.DataFrame,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
) -> dict:
    """
    Agent 6 entry point — extracts canonical assessment data from one raw sheet.
    """
    logger.info(f"[Agent 6 / Schema] sheet='{sheet_name}' shape={df.shape}")
    print(f"  [Schema] {sheet_name}...", end=" ", flush=True)

    prompt = _build_prompt(sheet_name, df)
    result = _call_ai(prompt, model=model, provider=provider)

    # Normalize all records
    raw_data = result.get("data", []) or []
    result["data"] = [_normalize_record(r) for r in raw_data if isinstance(r, dict)]

    n_records = len(result["data"])
    n_missing = sum(1 for r in result["data"] if r["value"] is None)
    print(f"{n_records} records ({n_missing} missing) — type={result.get('test_type', '?')}")

    return result
