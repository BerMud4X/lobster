import pandas as pd
from pathlib import Path
from logger import logger

REFERENCE_PATH = Path(__file__).parent.parent / "references" / "exercises_reference.xlsx"

# Fixed list of valid code_base values
VALID_CODE_BASES = {
    "push", "pull", "transfer", "balance", "stretch", "cardio", "functional"
}


def load_exercises() -> list[dict]:
    """Loads the exercise reference list."""
    try:
        df = pd.read_excel(REFERENCE_PATH, sheet_name="exercises")
        exercises = df.dropna(subset=["name", "code", "code_base"]).to_dict(orient="records")
        logger.info(f"Loaded {len(exercises)} exercises from reference.")
        return exercises
    except Exception as e:
        logger.warning(f"Could not load exercises reference: {e}")
        return []


def load_muscles() -> list[dict]:
    """Loads the muscle reference list."""
    try:
        df = pd.read_excel(REFERENCE_PATH, sheet_name="muscles")
        muscles = df.dropna(subset=["name_latin"]).to_dict(orient="records")
        logger.info(f"Loaded {len(muscles)} muscles from reference.")
        return muscles
    except Exception as e:
        logger.warning(f"Could not load muscles reference: {e}")
        return []


def get_muscles_latin_list() -> list[str]:
    """Returns a flat list of all known muscle latin names."""
    return [m["name_latin"] for m in load_muscles()]


def validate_code_base(code_base: str) -> str:
    """Returns code_base if valid, otherwise 'unknown'."""
    if code_base and code_base.strip().lower() in VALID_CODE_BASES:
        return code_base.strip().capitalize()
    return "unknown"
