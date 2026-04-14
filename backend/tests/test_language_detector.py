import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from language_detector import detect_language, detect_language_from_excel, DEFAULT_LANGUAGE


# --- detect_language ---

def test_detect_french():
    samples = [
        "Verrouillage du genou aux barres parallèles avec aide",
        "Transfert du fauteuil roulant avec aide partielle",
        "Renforcement des muscles quadriceps en position assise",
    ]
    assert detect_language(samples) == "French"

def test_detect_english():
    samples = [
        "Knee locking at parallel bars with assistance",
        "Wheelchair to chair transfer with partial weight bearing",
        "Seated quadriceps strengthening",
    ]
    assert detect_language(samples) == "English"

def test_detect_empty_list_defaults():
    assert detect_language([]) == DEFAULT_LANGUAGE

def test_detect_none_and_short_strings_defaults():
    assert detect_language([None, "", "ok"]) == DEFAULT_LANGUAGE

def test_detect_mixed_prefers_dominant():
    # Mostly French with one English line
    samples = [
        "Renforcement musculaire des membres inférieurs",
        "Verrouillage genou aux barres paralleles avec aide",
        "Marche avec deambulateur pendant dix minutes",
        "Squats with wall support",
    ]
    assert detect_language(samples) == "French"


# --- detect_language_from_excel ---

def test_detect_from_excel_french(tmp_path):
    path = tmp_path / "patient_fr.xlsx"
    df = pd.DataFrame({
        "patient_id": ["P001", "P001"],
        "session": ["S1", "S1"],
        "exercise": [
            "Renforcement des muscles ischio-jambiers en position assise",
            "Verrouillage du genou aux barres parallèles avec aide",
        ],
    })
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="P001", index=False)
    assert detect_language_from_excel(str(path)) == "French"

def test_detect_from_excel_english(tmp_path):
    path = tmp_path / "patient_en.xlsx"
    df = pd.DataFrame({
        "patient_id": ["P001"],
        "session": ["S1"],
        "exercise": ["Seated hamstring strengthening with elastic band for rehabilitation"],
    })
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="P001", index=False)
    assert detect_language_from_excel(str(path)) == "English"

def test_detect_from_excel_ignores_protocole_sheet(tmp_path):
    path = tmp_path / "patient.xlsx"
    data = pd.DataFrame({
        "patient_id": ["P001", "P001"],
        "session": ["S1", "S1"],
        "exercise": [
            "Renforcement des muscles quadriceps en position assise avec élastique",
            "Marche avec déambulateur pendant dix minutes dans le couloir",
        ],
    })
    protocol = pd.DataFrame({"champ": ["protocole"], "valeur": ["Post-stroke rehabilitation program with functional goals"]})
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        data.to_excel(w, sheet_name="P001", index=False)
        protocol.to_excel(w, sheet_name="protocole", index=False)

    # Should detect French from P001, not English from protocole
    assert detect_language_from_excel(str(path)) == "French"

def test_detect_from_excel_missing_file_returns_default():
    assert detect_language_from_excel("/nonexistent/file.xlsx") == DEFAULT_LANGUAGE

def test_detect_from_excel_no_exercise_column_returns_default(tmp_path):
    path = tmp_path / "no_exercise.xlsx"
    df = pd.DataFrame({"col_a": ["x"], "col_b": ["y"]})
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="P001", index=False)
    assert detect_language_from_excel(str(path)) == DEFAULT_LANGUAGE
