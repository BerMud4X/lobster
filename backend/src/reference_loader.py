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


def load_objectives() -> list[dict]:
    """Loads the therapeutic objectives reference list."""
    try:
        df = pd.read_excel(REFERENCE_PATH, sheet_name="Objecif")
        objectives = df.dropna(subset=["Code objectif", "Signification"]).to_dict(orient="records")
        logger.info(f"Loaded {len(objectives)} objectives from reference.")
        return objectives
    except Exception as e:
        logger.warning(f"Could not load objectives reference: {e}")
        return []


def get_objectives_list() -> list[dict]:
    """Returns a list of {code, label} dicts for all therapeutic objectives."""
    return [
        {"code": o["Code objectif"], "label": o["Signification"]}
        for o in load_objectives()
    ]


def validate_objective_code(code: str) -> str:
    """Returns the objective code if valid, otherwise 'unknown'."""
    valid_codes = {o["Code objectif"].strip().upper() for o in load_objectives()}
    if code and code.strip().upper() in valid_codes:
        return code.strip().upper()
    return "unknown"


def load_protocol(file_path: str) -> dict:
    """
    Loads protocol metadata from a 'protocole' sheet in a patient Excel file.
    Returns a dict with keys: description, obj_principal, obj_secondaires (list).
    Returns empty dict if the sheet does not exist.
    """
    try:
        df = pd.read_excel(file_path, sheet_name="protocole")
        data = dict(zip(df["champ"].str.strip(), df["valeur"].astype(str).str.strip()))

        obj_secondaires_raw = data.get("obj_secondaires", "")
        obj_secondaires = [
            code.strip().upper()
            for code in obj_secondaires_raw.split(",")
            if code.strip()
        ]

        protocol = {
            "description": data.get("protocole", ""),
            "obj_principal": data.get("obj_principal", "").strip().upper(),
            "obj_secondaires": obj_secondaires,
        }
        logger.info(f"Protocol loaded: {protocol}")
        return protocol
    except Exception:
        logger.info("No 'protocole' sheet found — running without protocol context.")
        return {}


def validate_code_base(code_base: str) -> str:
    """Returns code_base if valid, otherwise 'unknown'."""
    if code_base and code_base.strip().lower() in VALID_CODE_BASES:
        return code_base.strip().capitalize()
    return "unknown"
