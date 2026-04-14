from pathlib import Path
import pandas as pd
from logger import logger

# Map ISO 639-1 code → human-readable name used in AI prompts
LANGUAGE_NAMES = {
    "fr": "French",
    "en": "English",
    "es": "Spanish",
    "it": "Italian",
    "de": "German",
    "pt": "Portuguese",
    "nl": "Dutch",
}

DEFAULT_LANGUAGE = "English"


def detect_language(texts: list[str]) -> str:
    """
    Detects the dominant language from a list of text samples.
    Returns a human-readable language name (e.g. 'French', 'English').
    Falls back to DEFAULT_LANGUAGE if detection is ambiguous or fails.
    """
    try:
        from langdetect import detect_langs, DetectorFactory
    except ImportError:
        logger.warning("langdetect not installed — defaulting to French.")
        return DEFAULT_LANGUAGE

    # Deterministic results across runs
    DetectorFactory.seed = 42

    cleaned = [t.strip() for t in texts if t and isinstance(t, str) and len(t.strip()) >= 3]
    if not cleaned:
        logger.info(f"[Language] no usable text samples — defaulting to {DEFAULT_LANGUAGE}")
        return DEFAULT_LANGUAGE

    combined = " ".join(cleaned)

    try:
        langs = detect_langs(combined)
        if not langs:
            return DEFAULT_LANGUAGE
        top = langs[0]
        name = LANGUAGE_NAMES.get(top.lang, top.lang.capitalize())
        logger.info(f"[Language] detected: {name} (confidence={top.prob:.2f})")
        return name
    except Exception as e:
        logger.warning(f"[Language] detection failed ({e}) — defaulting to {DEFAULT_LANGUAGE}")
        return DEFAULT_LANGUAGE


def detect_language_from_excel(file_path: str, exercise_col_candidates: list[str] = None) -> str:
    """
    Extracts exercise text samples from an Excel file and detects their language.
    Scans every data sheet (excluding 'protocole') and all known exercise column names.
    """
    if exercise_col_candidates is None:
        exercise_col_candidates = [
            "exercise", "exercice", "activite", "activité",
            "description", "texte", "notes",
        ]

    path = Path(file_path)
    if path.suffix.lower() not in (".xlsx", ".xls"):
        # For CSV, just read the whole thing
        try:
            df = pd.read_csv(file_path)
            return _detect_from_dataframe(df, exercise_col_candidates)
        except Exception:
            return DEFAULT_LANGUAGE

    try:
        xl = pd.ExcelFile(file_path)
        data_sheets = [s for s in xl.sheet_names if s.lower() != "protocole"]

        samples = []
        for sheet in data_sheets:
            df = xl.parse(sheet)
            for candidate in exercise_col_candidates:
                for col in df.columns:
                    if col.strip().lower() == candidate:
                        samples.extend(df[col].dropna().astype(str).tolist())
                        break

        return detect_language(samples) if samples else DEFAULT_LANGUAGE
    except Exception as e:
        logger.warning(f"[Language] could not read Excel for detection: {e}")
        return DEFAULT_LANGUAGE


def _detect_from_dataframe(df: pd.DataFrame, candidates: list[str]) -> str:
    """Extract samples from matching columns and detect."""
    samples = []
    for candidate in candidates:
        for col in df.columns:
            if col.strip().lower() == candidate:
                samples.extend(df[col].dropna().astype(str).tolist())
                break
    return detect_language(samples) if samples else DEFAULT_LANGUAGE
