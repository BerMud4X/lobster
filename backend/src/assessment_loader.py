"""
Loads an assessments Excel file and returns a long-format DataFrame
with one row per (patient × test × sub_category × timepoint).

Heavy lifting (interpreting the layout of each sheet) is delegated to
Agent 6 (assessment_schema_agent).
"""

from pathlib import Path
import pandas as pd
from logger import logger
from assessment_schema_agent import detect_and_extract


CANONICAL_COLUMNS = [
    "patient_id", "test_name", "test_type", "scale",
    "sub_category", "timepoint", "value", "missing_reason",
]

# Sheets that should not be treated as test data
SKIP_SHEET_PATTERNS = {"cases description", "case description", "demographics", "info"}


def load_assessments(
    file_path: str,
    model: str = "open-mistral-7b",
    provider: str = "Mistral",
    skip_demographics: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """
    Loads an assessments file (one Excel, one sheet per test).
    Returns:
        - long-format DataFrame with CANONICAL_COLUMNS
        - metadata dict: {"sheets_processed": int, "tests_found": list[str], "demographics": dict | None}
    """
    path = Path(file_path)
    if path.suffix.lower() not in (".xlsx", ".xls"):
        raise ValueError(f"Assessments file must be Excel — got: {path.suffix}")

    logger.info(f"[AssessmentLoader] loading {file_path}")
    print(f"\n=== ASSESSMENT LOADER ===")
    print(f"File: {file_path}")

    xl = pd.ExcelFile(file_path)
    sheets = xl.sheet_names
    print(f"Sheets detected: {sheets}\n")

    rows = []
    tests_found = []
    demographics = None

    for sheet in sheets:
        df_raw = xl.parse(sheet, header=None)

        is_demographics = sheet.strip().lower() in SKIP_SHEET_PATTERNS

        try:
            extracted = detect_and_extract(sheet, df_raw, model=model, provider=provider)
        except Exception as e:
            logger.error(f"[AssessmentLoader] sheet '{sheet}' failed: {e}")
            print(f"  [Skipped] {sheet} — extraction error: {e}")
            continue

        if not extracted.get("data"):
            logger.warning(f"[AssessmentLoader] sheet '{sheet}' produced no records.")
            continue

        # Demographics sheet → keep separately, don't pollute test data
        if is_demographics or extracted.get("test_type") == "demographic":
            if skip_demographics:
                demographics = extracted
                continue

        test_name = extracted.get("test_name", sheet)
        test_type = extracted.get("test_type", "unknown")
        scale = extracted.get("scale")
        tests_found.append(test_name)

        for rec in extracted["data"]:
            rows.append({
                "patient_id":     rec.get("patient_id"),
                "test_name":      test_name,
                "test_type":      test_type,
                "scale":          scale,
                "sub_category":   rec.get("sub_category"),
                "timepoint":      rec.get("timepoint"),
                "value":          rec.get("value"),
                "missing_reason": rec.get("missing_reason"),
            })

    df = pd.DataFrame(rows, columns=CANONICAL_COLUMNS) if rows else pd.DataFrame(columns=CANONICAL_COLUMNS)

    metadata = {
        "sheets_processed": len(sheets),
        "tests_found": list(dict.fromkeys(tests_found)),  # de-dup, preserve order
        "demographics": demographics,
        "n_records": len(df),
        "n_patients": int(df["patient_id"].nunique()) if not df.empty else 0,
    }

    print(f"\n[AssessmentLoader] extracted {metadata['n_records']} records from {len(metadata['tests_found'])} test(s)")
    logger.info(f"[AssessmentLoader] {metadata}")
    return df, metadata
