import pandas as pd
from pathlib import Path
from logger import logger
from exercise_extractor import extract_exercises, select_provider_and_model


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


def analyze_dataframe(df: pd.DataFrame, patient_id: str, model: str = "open-mistral-7b", provider: str = "Mistral") -> pd.DataFrame:
    """Analyzes a DataFrame and extracts structured exercise data."""
    session_col = _detect_sessions(df)
    exercise_col = _detect_exercise_column(df)

    if not exercise_col or exercise_col not in df.columns:
        logger.error("Could not identify exercise column.")
        raise ValueError("Exercise column not found.")

    results = []
    session_exercise_counter = {}  # tracks exercise_num per session

    for idx, row in df.iterrows():
        session = str(row[session_col]) if session_col and session_col in df.columns else f"session_{idx + 1}"
        text = str(row[exercise_col])

        if not text or text.lower() in ("nan", "none", ""):
            continue

        print(f"  Analyzing: [{session}] {text[:60]}...")
        exercises = extract_exercises(text, model=model, provider=provider)

        for ex in exercises:
            session_exercise_counter[session] = session_exercise_counter.get(session, 0) + 1
            results.append({
                "patient_id": patient_id,
                "session": session,
                "exercise_num": session_exercise_counter[session],
                "exercise_name": ex.get("exercise_name"),
                "code": ex.get("code"),
                "code_base": ex.get("code_base"),
                "muscles": ", ".join(ex.get("muscles", [])),
                "assistance": ex.get("assistance"),
                "repetitions": ex.get("repetitions"),
                "time": ex.get("time"),
            })

    return pd.DataFrame(results)


def analyze_file(file_path: str, model: str = None, provider: str = None) -> pd.DataFrame:
    """
    Main entry point — analyzes a clinical exercise file.
    Handles single sheet, multi-sheet Excel, and single DataFrame inputs.
    """
    path = Path(file_path)
    all_results = []

    print(f"\n=== LOBSTER ANALYZER ===")
    print(f"File: {file_path}")

    if model is None or provider is None:
        provider, model = select_provider_and_model()

    if path.suffix.lower() in (".xlsx", ".xls"):
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        logger.info(f"Excel file with {len(sheets)} sheet(s): {sheets}")

        if len(sheets) == 1:
            df = xl.parse(sheets[0])
            patient_id = _detect_patient(df, sheet_name=sheets[0])
            result = analyze_dataframe(df, patient_id, model=model, provider=provider)
            all_results.append(result)
        else:
            print(f"Sheets detected: {sheets}")
            choice = input("Analyze all sheets or specific ones? (all / sheet names separated by commas): ")
            selected = sheets if choice.strip().lower() == "all" else [s.strip() for s in choice.split(",")]

            for sheet in selected:
                print(f"\n--- Sheet: {sheet} ---")
                df = xl.parse(sheet)
                patient_id = _detect_patient(df, sheet_name=sheet)
                result = analyze_dataframe(df, patient_id, model=model, provider=provider, sheet_name=sheet)
                all_results.append(result)

    elif path.suffix.lower() == ".csv":
        from reader import read_csv
        df = read_csv(file_path)
        patient_id = _detect_patient(df)
        result = analyze_dataframe(df, patient_id, model=model, provider=provider)
        all_results.append(result)

    else:
        logger.error(f"Unsupported format for analyzer: {path.suffix}")
        raise ValueError(f"Format not supported by analyzer: {path.suffix}")

    final = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
    logger.info(f"Analysis complete: {len(final)} exercise records extracted.")
    print(f"\nAnalysis complete: {len(final)} exercise records extracted.")
    return final


if __name__ == "__main__":
    from exporter import export
    df = analyze_file("../tests/test_files/test_patient.xlsx")
    print(df)
    export(df)
