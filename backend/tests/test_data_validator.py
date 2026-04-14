import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_validator import validate_and_clean, format_report, is_blocking


# --- Happy path ---

def test_validates_clean_dataframe():
    df = pd.DataFrame({
        "patient_id": ["P001", "P001"],
        "session": ["S1", "S2"],
        "exercise": ["Squat with parallel bars", "Knee locking with assistance"],
    })
    cleaned, report = validate_and_clean(df, source_name="test")
    assert len(cleaned) == 2
    assert report["valid_rows"] == 2
    assert report["critical"] == []


# --- Critical errors ---

def test_empty_dataframe_is_critical():
    cleaned, report = validate_and_clean(pd.DataFrame())
    assert report["critical"]
    assert is_blocking(report)

def test_no_exercise_column_is_critical():
    df = pd.DataFrame({"patient_id": ["P001"], "random_col": ["foo"]})
    _, report = validate_and_clean(df)
    assert any("No exercise column" in c for c in report["critical"])
    assert is_blocking(report)


# --- Cleaning ---

def test_drops_empty_exercise_cells():
    df = pd.DataFrame({
        "session": ["S1", "S1", "S1"],
        "exercise": ["Squat", "", None],
    })
    cleaned, report = validate_and_clean(df)
    assert len(cleaned) == 1
    assert report["removed"]["empty_exercise"] == 2

def test_drops_nan_string_cells():
    df = pd.DataFrame({"session": ["S1", "S1"], "exercise": ["Squat", "nan"]})
    cleaned, report = validate_and_clean(df)
    assert len(cleaned) == 1
    assert report["removed"]["empty_exercise"] == 1

def test_drops_exact_duplicates():
    df = pd.DataFrame({
        "session": ["S1", "S1", "S2"],
        "exercise": ["Squat", "Squat", "Push-up"],
    })
    cleaned, report = validate_and_clean(df)
    assert len(cleaned) == 2
    assert report["removed"]["duplicate"] == 1


# --- Warnings (do NOT block) ---

def test_short_exercise_triggers_warning():
    df = pd.DataFrame({
        "session": ["S1", "S1"],
        "exercise": ["ok", "Wheelchair transfer with partial assistance"],
    })
    cleaned, report = validate_and_clean(df)
    assert len(cleaned) == 2  # not removed, just flagged
    assert any("shorter than" in w for w in report["warnings"])

def test_missing_patient_id_warning():
    df = pd.DataFrame({
        "patient_id": [None, "P001"],
        "session": ["S1", "S2"],
        "exercise": ["Knee locking with parallel bars", "Squat with assistance"],
    })
    _, report = validate_and_clean(df)
    assert any("missing 'patient_id'" in w for w in report["warnings"])

def test_no_session_column_warning():
    df = pd.DataFrame({
        "patient_id": ["P001"],
        "exercise": ["Knee locking with parallel bars"],
    })
    _, report = validate_and_clean(df)
    assert any("No session column" in w for w in report["warnings"])


# --- format_report ---

def test_format_report_includes_counts():
    df = pd.DataFrame({"session": ["S1", "S1"], "exercise": ["Squat", ""]})
    _, report = validate_and_clean(df, source_name="P001")
    text = format_report(report)
    assert "P001" in text
    assert "2 → 1" in text
    assert "Removed (empty exercise): 1" in text


# --- is_blocking ---

def test_is_blocking_when_critical():
    assert is_blocking({"critical": ["bad"], "valid_rows": 0})

def test_is_blocking_when_zero_valid_rows():
    assert is_blocking({"critical": [], "valid_rows": 0})

def test_not_blocking_when_warnings_only():
    assert not is_blocking({"critical": [], "valid_rows": 5, "warnings": ["minor"]})
