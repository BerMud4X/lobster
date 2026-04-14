import pandas as pd
from logger import logger

MIN_EXERCISE_LENGTH = 5  # shorter than this = likely not a real exercise description


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Returns the first column matching a case-insensitive candidate, or None."""
    for candidate in candidates:
        for col in df.columns:
            if col.strip().lower() == candidate.lower():
                return col
    return None


def validate_and_clean(df: pd.DataFrame, source_name: str = "input") -> tuple[pd.DataFrame, dict]:
    """
    Deterministic pre-flight validation before sending data to AI agents.

    Checks:
      - at least one exercise-like column exists
      - drops rows with empty/NaN exercise text
      - drops exact duplicate rows
      - flags (without dropping) rows with very short exercise text
      - flags rows with missing patient_id

    Returns:
        (cleaned_df, report) where report is:
            {
                "source": str,
                "total_rows": int,
                "valid_rows": int,
                "removed": {"empty_exercise": int, "duplicate": int},
                "warnings": list[str],
                "critical": list[str],
            }
    """
    report = {
        "source": source_name,
        "total_rows": len(df),
        "valid_rows": 0,
        "removed": {"empty_exercise": 0, "duplicate": 0},
        "warnings": [],
        "critical": [],
    }

    if df.empty:
        report["critical"].append("DataFrame is empty.")
        return df, report

    # 1. Find the exercise column
    exercise_col = _find_column(df, [
        "exercise", "exercice", "activite", "activité",
        "description", "texte", "notes",
    ])
    if not exercise_col:
        report["critical"].append(
            f"No exercise column found. Expected one of: exercise, exercice, description, notes."
        )
        return df, report

    cleaned = df.copy()

    # 2. Drop rows with empty/NaN exercise cells
    before = len(cleaned)
    cleaned = cleaned[cleaned[exercise_col].notna()]
    cleaned = cleaned[cleaned[exercise_col].astype(str).str.strip() != ""]
    cleaned = cleaned[~cleaned[exercise_col].astype(str).str.strip().str.lower().isin(("nan", "none"))]
    removed_empty = before - len(cleaned)
    report["removed"]["empty_exercise"] = removed_empty

    # 3. Drop exact duplicate rows
    before = len(cleaned)
    cleaned = cleaned.drop_duplicates()
    removed_dup = before - len(cleaned)
    report["removed"]["duplicate"] = removed_dup

    # 4. Flag very short exercise descriptions (warning, keep in df)
    short_mask = cleaned[exercise_col].astype(str).str.strip().str.len() < MIN_EXERCISE_LENGTH
    n_short = int(short_mask.sum())
    if n_short > 0:
        report["warnings"].append(
            f"{n_short} exercise description(s) shorter than {MIN_EXERCISE_LENGTH} characters — verify quality."
        )

    # 5. Flag missing patient_id if column exists
    patient_col = _find_column(cleaned, ["patient_id", "id", "patient", "pseudonyme", "code_patient"])
    if patient_col:
        n_missing_pid = int(cleaned[patient_col].isna().sum())
        if n_missing_pid > 0:
            report["warnings"].append(
                f"{n_missing_pid} row(s) missing '{patient_col}' — will be labeled 'unknown'."
            )

    # 6. Session coverage
    session_col = _find_column(cleaned, ["session", "séance", "seance", "date", "jour", "day"])
    if not session_col:
        report["warnings"].append(
            "No session column detected — each row will be treated as its own session."
        )

    report["valid_rows"] = len(cleaned)

    # Log summary
    logger.info(
        f"[Validator:{source_name}] {report['total_rows']} → {report['valid_rows']} rows "
        f"(removed: {removed_empty} empty, {removed_dup} duplicate; "
        f"warnings: {len(report['warnings'])}, critical: {len(report['critical'])})"
    )

    return cleaned, report


def format_report(report: dict) -> str:
    """Renders a validation report as a human-readable string."""
    lines = [
        f"━━━ Data validation — {report['source']} ━━━",
        f"  Rows: {report['total_rows']} → {report['valid_rows']} valid",
    ]
    removed = report.get("removed", {})
    if removed.get("empty_exercise"):
        lines.append(f"  Removed (empty exercise): {removed['empty_exercise']}")
    if removed.get("duplicate"):
        lines.append(f"  Removed (duplicate):      {removed['duplicate']}")

    for w in report.get("warnings", []):
        lines.append(f"  [WARN]     {w}")
    for c in report.get("critical", []):
        lines.append(f"  [CRITICAL] {c}")

    return "\n".join(lines)


def is_blocking(report: dict) -> bool:
    """Returns True if the report contains critical errors that should stop processing."""
    return bool(report.get("critical")) or report.get("valid_rows", 0) == 0
