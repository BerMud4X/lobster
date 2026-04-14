import pandas as pd
from pathlib import Path
from logger import logger
from exercise_extractor import select_provider_and_model
from agent_orchestrator import orchestrate
from reference_loader import load_protocol
from data_validator import validate_and_clean, format_report, is_blocking
from cost_estimator import estimate_cost, format_estimate, CONFIRM_THRESHOLD_USD
import audit_logger


def _detect_sessions(df: pd.DataFrame) -> str:
    """Tries to detect which column identifies sessions."""
    candidates = ["session", "séance", "seance", "date", "jour", "day"]
    for col in df.columns:
        if col.strip().lower() in candidates:
            logger.info(f"Session column detected: '{col}'")
            return col

    # Ask user if not found
    print(f"\nAvailable columns: {df.columns.tolist()}")
    choice = input("Which column identifies the session? (or press Enter to use row index): ").strip()
    return choice if choice in df.columns else None


def _detect_patient(df: pd.DataFrame, sheet_name: str = None) -> str:
    """Tries to detect the patient ID."""
    candidates = ["patient_id", "id", "patient", "pseudonyme", "code_patient"]
    for col in df.columns:
        if col.strip().lower() in candidates:
            val = df[col].dropna().iloc[0] if not df[col].dropna().empty else "unknown"
            logger.info(f"Patient ID detected from column '{col}': {val}")
            return str(val)

    # Try sheet name
    if sheet_name:
        logger.info(f"Using sheet name as patient ID: {sheet_name}")
        return sheet_name

    patient_id = input("Patient ID not detected. Enter patient ID manually: ").strip()
    return patient_id or "unknown"


def _detect_exercise_column(df: pd.DataFrame) -> str:
    """Tries to detect which column contains exercise descriptions."""
    candidates = ["exercise", "exercice", "activite", "activité", "description", "texte", "notes"]
    for col in df.columns:
        if col.strip().lower() in candidates:
            logger.info(f"Exercise column detected: '{col}'")
            return col

    print(f"\nAvailable columns: {df.columns.tolist()}")
    choice = input("Which column contains exercise descriptions? ").strip()
    return choice


def analyze_dataframe(df: pd.DataFrame, patient_id: str, model: str = "open-mistral-7b", provider: str = "Mistral", protocol: dict = None) -> tuple[pd.DataFrame, list[dict]]:
    """Runs the 3-agent pipeline over a DataFrame. Returns (exercises_df, syntheses)."""
    # Pre-flight deterministic validation (no AI)
    df, report = validate_and_clean(df, source_name=patient_id)
    print(format_report(report))

    if is_blocking(report):
        logger.error(f"[Validator] blocking errors for '{patient_id}', skipping sheet.")
        print(f"  → Skipping sheet '{patient_id}' due to critical errors.")
        return pd.DataFrame(), []

    session_col = _detect_sessions(df)
    exercise_col = _detect_exercise_column(df)

    if not exercise_col or exercise_col not in df.columns:
        logger.error("Could not identify exercise column.")
        raise ValueError("Exercise column not found.")

    return orchestrate(df, patient_id, session_col, exercise_col, model=model, provider=provider, protocol=protocol)


def analyze_file(file_path: str, model: str = None, provider: str = None) -> tuple[pd.DataFrame, list[dict], str, str]:
    """
    Main entry point — runs the 3-agent pipeline on a clinical exercise file.
    Returns (exercises_df, syntheses, provider, model).
    """
    path = Path(file_path)
    all_exercises = []
    all_syntheses = []

    print(f"\n=== LOBSTER ANALYZER ===")
    print(f"File: {file_path}")

    if model is None or provider is None:
        provider, model = select_provider_and_model()

    # Initialize audit log for this run (writes one JSONL entry per AI call)
    audit_logger.init_audit(output_dir="output")

    if path.suffix.lower() in (".xlsx", ".xls"):
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names

        # Load protocol once for the whole file (optional sheet)
        protocol = load_protocol(file_path)
        if protocol:
            print(f"\n[Protocol detected] {protocol.get('description', '')}")
            print(f"  obj_principal={protocol.get('obj_principal')} | obj_secondaires={', '.join(protocol.get('obj_secondaires', []))}")

        # Exclude the protocole sheet from patient data sheets
        data_sheets = [s for s in sheets if s.lower() != "protocole"]
        logger.info(f"Excel file with {len(data_sheets)} data sheet(s): {data_sheets}")

        # Cost estimate across all selected sheets — confirm if expensive
        try:
            combined = pd.concat([xl.parse(s) for s in data_sheets], ignore_index=True)
            estimate = estimate_cost(combined, provider=provider, model=model)
            print("\n" + format_estimate(estimate))
            if estimate.get("estimated_cost_usd", 0) > CONFIRM_THRESHOLD_USD:
                confirm = input(f"\nEstimated cost exceeds ${CONFIRM_THRESHOLD_USD}. Continue? (y/n): ").strip().lower()
                if confirm != "y":
                    print("Aborted by user.")
                    return pd.DataFrame(), [], provider, model
        except Exception as e:
            logger.warning(f"[CostEstimator] could not compute estimate: {e}")

        if len(data_sheets) == 1:
            df = xl.parse(data_sheets[0])
            patient_id = _detect_patient(df, sheet_name=data_sheets[0])
            exercises_df, syntheses = analyze_dataframe(df, patient_id, model=model, provider=provider, protocol=protocol)
            all_exercises.append(exercises_df)
            all_syntheses.extend(syntheses)
        else:
            print(f"Sheets detected: {data_sheets}")
            choice = input("Analyze all sheets or specific ones? (all / sheet names separated by commas): ")
            selected = data_sheets if choice.strip().lower() == "all" else [s.strip() for s in choice.split(",")]

            for sheet in selected:
                print(f"\n--- Sheet: {sheet} ---")
                df = xl.parse(sheet)
                patient_id = _detect_patient(df, sheet_name=sheet)
                exercises_df, syntheses = analyze_dataframe(df, patient_id, model=model, provider=provider, protocol=protocol)
                all_exercises.append(exercises_df)
                all_syntheses.extend(syntheses)

    elif path.suffix.lower() == ".csv":
        from reader import read_csv
        df = read_csv(file_path)
        patient_id = _detect_patient(df)
        exercises_df, syntheses = analyze_dataframe(df, patient_id, model=model, provider=provider)
        all_exercises.append(exercises_df)
        all_syntheses.extend(syntheses)

    else:
        logger.error(f"Unsupported format for analyzer: {path.suffix}")
        raise ValueError(f"Format not supported by analyzer: {path.suffix}")

    final = pd.concat(all_exercises, ignore_index=True) if all_exercises else pd.DataFrame()
    logger.info(f"Analysis complete: {len(final)} exercise records, {len(all_syntheses)} session syntheses.")
    print(f"\nAnalysis complete: {len(final)} exercise records, {len(all_syntheses)} session synthesis/syntheses.")

    if all_syntheses:
        print("\n=== SESSION SYNTHESES ===")
        for s in all_syntheses:
            print(f"\n[{s['session']}] {s.get('session_intensity', '?').upper()} intensity — {s.get('dominant_objective_label', '?')}")
            print(f"  {s.get('clinical_summary', '')}")
            for rec in s.get('recommendations', []):
                print(f"  → {rec}")

    return final, all_syntheses, provider, model


if __name__ == "__main__":
    from exporter import export
    exercises_df, syntheses = analyze_file("../tests/test_files/test_patient.xlsx")
    print(exercises_df)
    export(exercises_df)
