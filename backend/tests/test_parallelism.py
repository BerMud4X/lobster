"""
Tests that the orchestrator parallelism is wired correctly and preserves
output semantics (ordering, session grouping, thread safety).
"""
import sys
import time
import pandas as pd
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_orchestrator import orchestrate


def _mock_synthesis(patient_id, session, exercises, **kwargs):
    return {"patient_id": patient_id, "session": session, "ok": True}


def _mock_extract(text, **kwargs):
    # Simulate API latency so parallelism actually matters
    time.sleep(0.05)
    return [{"exercise_name": f"ex-from-{text[-5:]}", "code": "X", "code_base": "Push",
             "objective": "STR", "muscles": ["M1"],
             "assistance": None, "series": None, "repetitions": None, "time": None}]


def _mock_review_approved(text, exercises, **kwargs):
    return {"decision": "approved", "confidence": 1.0, "issues": [], "exercises": exercises}


def _make_df(n_rows: int, n_sessions: int) -> pd.DataFrame:
    return pd.DataFrame({
        "patient_id": ["P001"] * n_rows,
        "session":    [f"S{(i % n_sessions) + 1}" for i in range(n_rows)],
        "exercise":   [f"row-{i:04d}" for i in range(n_rows)],
    })


@patch("agent_orchestrator.synthesize_session", side_effect=_mock_synthesis)
@patch("agent_orchestrator.review_exercises", side_effect=_mock_review_approved)
@patch("agent_orchestrator.extract_exercises", side_effect=_mock_extract)
def test_parallelism_is_faster_than_sequential(mock_extract, mock_review, mock_synth):
    """10 rows × 50ms latency should take ~100-200ms with 5 workers (vs 500ms sequential)."""
    df = _make_df(n_rows=10, n_sessions=2)
    t0 = time.time()
    exercises_df, _ = orchestrate(df, "P001", "session", "exercise", max_workers=5)
    elapsed = time.time() - t0

    # Must have produced all rows
    assert len(exercises_df) == 10
    # With 5 workers, should be significantly faster than 10*0.05=0.5s sequential
    assert elapsed < 0.35, f"Expected <0.35s with 5 workers, got {elapsed:.2f}s"


@patch("agent_orchestrator.synthesize_session", side_effect=_mock_synthesis)
@patch("agent_orchestrator.review_exercises", side_effect=_mock_review_approved)
@patch("agent_orchestrator.extract_exercises", side_effect=_mock_extract)
def test_parallelism_preserves_exercise_count(mock_extract, mock_review, mock_synth):
    df = _make_df(n_rows=15, n_sessions=3)
    exercises_df, syntheses = orchestrate(df, "P001", "session", "exercise", max_workers=5)
    assert len(exercises_df) == 15
    assert mock_extract.call_count == 15

@patch("agent_orchestrator.synthesize_session", side_effect=_mock_synthesis)
@patch("agent_orchestrator.review_exercises", side_effect=_mock_review_approved)
@patch("agent_orchestrator.extract_exercises", side_effect=_mock_extract)
def test_parallelism_one_synthesis_per_session(mock_extract, mock_review, mock_synth):
    """Each unique session should produce exactly one synthesis call."""
    df = _make_df(n_rows=12, n_sessions=3)
    _, syntheses = orchestrate(df, "P001", "session", "exercise", max_workers=5)
    assert len(syntheses) == 3
    # Agent 3 called once per unique session, not per row
    assert mock_synth.call_count == 3


@patch("agent_orchestrator.synthesize_session", side_effect=_mock_synthesis)
@patch("agent_orchestrator.review_exercises", side_effect=_mock_review_approved)
@patch("agent_orchestrator.extract_exercises", side_effect=_mock_extract)
def test_parallelism_deterministic_exercise_numbering(mock_extract, mock_review, mock_synth):
    """exercise_num must reflect input order within each session, regardless of completion order."""
    df = _make_df(n_rows=6, n_sessions=2)  # rows 0,2,4 → S1 ; rows 1,3,5 → S2
    exercises_df, _ = orchestrate(df, "P001", "session", "exercise", max_workers=5)

    s1 = exercises_df[exercises_df["session"] == "S1"]["exercise_num"].tolist()
    s2 = exercises_df[exercises_df["session"] == "S2"]["exercise_num"].tolist()
    assert s1 == [1, 2, 3]
    assert s2 == [1, 2, 3]


@patch("agent_orchestrator.synthesize_session", side_effect=_mock_synthesis)
@patch("agent_orchestrator.review_exercises", side_effect=_mock_review_approved)
@patch("agent_orchestrator.extract_exercises", side_effect=_mock_extract)
def test_parallelism_handles_empty_dataframe(mock_extract, mock_review, mock_synth):
    empty = pd.DataFrame({"patient_id": [], "session": [], "exercise": []})
    df, syntheses = orchestrate(empty, "P001", "session", "exercise")
    assert df.empty
    assert syntheses == []
    mock_extract.assert_not_called()
