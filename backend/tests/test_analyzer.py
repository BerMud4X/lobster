import pytest
import sys
import pandas as pd
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyzer import (
    _detect_sessions,
    _detect_patient,
    _detect_exercise_column,
    analyze_dataframe,
)

FAKE_EXERCISE = [{
    "exercise_name": "Knee locking",
    "code": "KnL",
    "code_base": "Functional",
    "muscles": ["Gluteus maximus"],
    "assistance": "parallel bars",
    "repetitions": None,
    "time": None,
}]


# --- _detect_sessions ---

def test_detect_sessions_finds_session_column():
    df = pd.DataFrame({"session": ["S1", "S2"], "exercise": ["squat", "push"]})
    assert _detect_sessions(df) == "session"

def test_detect_sessions_finds_seance_column():
    df = pd.DataFrame({"seance": ["S1"], "exercise": ["squat"]})
    assert _detect_sessions(df) == "seance"

def test_detect_sessions_finds_date_column():
    df = pd.DataFrame({"date": ["2024-01-01"], "exercise": ["squat"]})
    assert _detect_sessions(df) == "date"

def test_detect_sessions_case_insensitive():
    df = pd.DataFrame({"SESSION": ["S1"], "exercise": ["squat"]})
    assert _detect_sessions(df) == "SESSION"

def test_detect_sessions_returns_none_when_not_found(monkeypatch):
    df = pd.DataFrame({"col_a": ["x"], "col_b": ["y"]})
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = _detect_sessions(df)
    assert result is None


# --- _detect_patient ---

def test_detect_patient_finds_patient_id_column():
    df = pd.DataFrame({"patient_id": ["P001"], "exercise": ["squat"]})
    assert _detect_patient(df) == "P001"

def test_detect_patient_finds_id_column():
    df = pd.DataFrame({"id": ["P002"], "exercise": ["squat"]})
    assert _detect_patient(df) == "P002"

def test_detect_patient_uses_sheet_name_as_fallback():
    df = pd.DataFrame({"col_a": ["x"]})
    assert _detect_patient(df, sheet_name="P003") == "P003"

def test_detect_patient_prompts_user_if_not_found(monkeypatch):
    df = pd.DataFrame({"col_a": ["x"]})
    monkeypatch.setattr("builtins.input", lambda _: "P999")
    assert _detect_patient(df) == "P999"

def test_detect_patient_returns_unknown_if_empty_input(monkeypatch):
    df = pd.DataFrame({"col_a": ["x"]})
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert _detect_patient(df) == "unknown"


# --- _detect_exercise_column ---

def test_detect_exercise_column_finds_exercise():
    df = pd.DataFrame({"exercise": ["squat"], "session": ["S1"]})
    assert _detect_exercise_column(df) == "exercise"

def test_detect_exercise_column_finds_description():
    df = pd.DataFrame({"description": ["squat"], "session": ["S1"]})
    assert _detect_exercise_column(df) == "description"

def test_detect_exercise_column_case_insensitive():
    df = pd.DataFrame({"EXERCISE": ["squat"], "session": ["S1"]})
    assert _detect_exercise_column(df) == "EXERCISE"

def test_detect_exercise_column_prompts_user(monkeypatch):
    df = pd.DataFrame({"col_a": ["squat"], "session": ["S1"]})
    monkeypatch.setattr("builtins.input", lambda _: "col_a")
    assert _detect_exercise_column(df) == "col_a"


# --- analyze_dataframe ---

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_returns_dataframe(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({
        "session": ["Seance 1"],
        "exercise": ["Knee locking in parallel bars"],
    })
    result = analyze_dataframe(df, patient_id="P001")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_columns(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({
        "session": ["Seance 1"],
        "exercise": ["Knee locking in parallel bars"],
    })
    result = analyze_dataframe(df, patient_id="P001")
    expected_cols = {"patient_id", "session", "exercise_num", "exercise_name",
                     "code", "code_base", "muscles", "assistance", "repetitions", "time"}
    assert expected_cols.issubset(set(result.columns))

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_patient_id_propagated(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({"session": ["S1"], "exercise": ["squats"]})
    result = analyze_dataframe(df, patient_id="P042")
    assert result["patient_id"].iloc[0] == "P042"

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_exercise_num_increments_per_session(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({
        "session": ["S1", "S1", "S2"],
        "exercise": ["squat", "push-up", "squat"],
    })
    result = analyze_dataframe(df, patient_id="P001")
    s1 = result[result["session"] == "S1"]["exercise_num"].tolist()
    s2 = result[result["session"] == "S2"]["exercise_num"].tolist()
    assert s1 == [1, 2]
    assert s2 == [1]

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_skips_empty_rows(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({
        "session": ["S1", "S1"],
        "exercise": ["squat", ""],
    })
    result = analyze_dataframe(df, patient_id="P001")
    assert len(result) == 1

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_muscles_joined_as_string(mock_extract):
    mock_extract.return_value = [{
        **FAKE_EXERCISE[0],
        "muscles": ["Gluteus maximus", "Biceps brachii"],
    }]
    df = pd.DataFrame({"session": ["S1"], "exercise": ["squats"]})
    result = analyze_dataframe(df, patient_id="P001")
    assert result["muscles"].iloc[0] == "Gluteus maximus, Biceps brachii"

@patch("analyzer.extract_exercises")
def test_analyze_dataframe_uses_provider_param(mock_extract):
    mock_extract.return_value = FAKE_EXERCISE
    df = pd.DataFrame({"session": ["S1"], "exercise": ["squats"]})
    analyze_dataframe(df, patient_id="P001", provider="Anthropic", model="claude-haiku-4-5-20251001")
    _, kwargs = mock_extract.call_args
    assert kwargs.get("provider") == "Anthropic"
