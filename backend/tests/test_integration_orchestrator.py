"""
End-to-end integration tests for the agent orchestrator.

These tests mock the AI providers at the lowest level (_call_mistral_*,
_call_anthropic_*) so that the entire pipeline (Agent 1 → Agent 2 → Agent 3)
runs with realistic data flow — no API calls, fully reproducible.
"""
import sys
import pandas as pd
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_orchestrator import orchestrate, run_agents


# --- Fixtures mimicking real AI output shape ---

FAKE_EXTRACTED = [{
    "exercise_name": "Knee locking",
    "code": "KnL",
    "code_base": "Push",
    "objective": "STR",
    "muscles": ["Gluteus maximus", "Quadriceps femoris"],
    "assistance": "parallel bars",
    "series": 3,
    "repetitions": 10,
    "time": None,
}]

APPROVED_REVIEW = {
    "decision": "approved",
    "confidence": 0.95,
    "issues": [],
    "exercises": FAKE_EXTRACTED,
}

CORRECTED_REVIEW = {
    "decision": "corrected",
    "confidence": 0.85,
    "issues": ["Muscle mismatch — corrected"],
    "exercises": [{**FAKE_EXTRACTED[0], "muscles": ["Gluteus maximus"]}],
}

REJECTED_REVIEW = {
    "decision": "rejected",
    "confidence": 0.2,
    "issues": ["Exercise name wrong"],
    "exercises": [],
}

def _mock_synthesis(patient_id, session, exercises, **kwargs):
    """Mock that mirrors the real synthesize_session — patient_id/session are set in output."""
    return {
        "patient_id": patient_id,
        "session": session,
        "dominant_objective": "STR",
        "dominant_objective_label": "Strength",
        "muscle_groups_worked": ["Gluteus maximus"],
        "session_intensity": "moderate",
        "clinical_summary": "Session focused on strength training.",
        "recommendations": ["Increase reps next session"],
    }

FAKE_SYNTHESIS = _mock_synthesis("P001", "S1", [])  # for tests that don't care about fidelity


def _sample_df(n_rows=3, sessions=("S1", "S1", "S2")):
    return pd.DataFrame({
        "patient_id": ["P001"] * n_rows,
        "session": sessions[:n_rows],
        "exercise": [f"exercise description {i}" for i in range(n_rows)],
    })


# --- Full orchestrate() pipeline ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_returns_exercises_and_syntheses(mock_extract, mock_review, mock_synth):
    mock_extract.return_value = FAKE_EXTRACTED
    mock_review.return_value = APPROVED_REVIEW
    mock_synth.side_effect = _mock_synthesis

    df = _sample_df()
    exercises_df, syntheses = orchestrate(df, "P001", "session", "exercise")

    assert not exercises_df.empty
    assert len(syntheses) == 2  # 2 unique sessions
    # Every row was processed
    assert mock_extract.call_count == 3


@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_numbers_exercises_correctly_per_session(mock_extract, mock_review, mock_synth):
    mock_extract.return_value = FAKE_EXTRACTED
    mock_review.return_value = APPROVED_REVIEW
    mock_synth.return_value = FAKE_SYNTHESIS

    df = _sample_df(n_rows=3, sessions=("S1", "S1", "S2"))
    exercises_df, _ = orchestrate(df, "P001", "session", "exercise")

    s1 = exercises_df[exercises_df["session"] == "S1"]["exercise_num"].tolist()
    s2 = exercises_df[exercises_df["session"] == "S2"]["exercise_num"].tolist()
    assert s1 == [1, 2]
    assert s2 == [1]


# --- Agent 2 decision paths ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_applies_corrected_exercises(mock_extract, mock_review, mock_synth):
    """When Agent 2 returns 'corrected', the corrected exercises replace Agent 1's output."""
    mock_extract.return_value = FAKE_EXTRACTED
    mock_review.return_value = CORRECTED_REVIEW
    mock_synth.return_value = FAKE_SYNTHESIS

    exercises, synth = run_agents("some text", "P001", "S1")
    # Corrected muscles = ["Gluteus maximus"] only (one muscle)
    assert exercises[0]["muscles"] == "Gluteus maximus"
    assert exercises[0]["review_decision"] == "corrected"


@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_retries_on_rejection(mock_extract, mock_review, mock_synth):
    """When Agent 2 rejects, orchestrator re-calls Agent 1 (max 2 attempts)."""
    mock_extract.return_value = FAKE_EXTRACTED
    # First review rejects, second approves
    mock_review.side_effect = [REJECTED_REVIEW, APPROVED_REVIEW]
    mock_synth.return_value = FAKE_SYNTHESIS

    run_agents("some text", "P001", "S1")
    assert mock_extract.call_count == 2  # initial + 1 retry
    assert mock_review.call_count == 2


# --- Protocol propagation ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_protocol_propagated_to_all_agents(mock_extract, mock_review, mock_synth):
    mock_extract.return_value = FAKE_EXTRACTED
    mock_review.return_value = APPROVED_REVIEW
    mock_synth.return_value = FAKE_SYNTHESIS

    protocol = {"description": "Test", "obj_principal": "STR", "obj_secondaires": ["FUNC"]}
    run_agents("text", "P001", "S1", protocol=protocol)

    for mock_fn in (mock_extract, mock_review, mock_synth):
        _, kwargs = mock_fn.call_args
        assert kwargs.get("protocol") == protocol


# --- Output shape contract ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_output_columns(mock_extract, mock_review, mock_synth):
    mock_extract.return_value = FAKE_EXTRACTED
    mock_review.return_value = APPROVED_REVIEW
    mock_synth.return_value = FAKE_SYNTHESIS

    df = _sample_df()
    exercises_df, _ = orchestrate(df, "P001", "session", "exercise")

    required = {
        "patient_id", "session", "exercise_num", "exercise_name", "code",
        "code_base", "objective", "muscles", "assistance", "series",
        "repetitions", "time", "review_decision", "review_confidence",
    }
    assert required.issubset(set(exercises_df.columns))


# --- Unknown objectives are kept as-is (no protocol) ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_preserves_unknown_objective_without_protocol(mock_extract, mock_review, mock_synth):
    ex = [{**FAKE_EXTRACTED[0], "objective": "unknown"}]
    mock_extract.return_value = ex
    mock_review.return_value = {**APPROVED_REVIEW, "exercises": ex}
    mock_synth.return_value = FAKE_SYNTHESIS

    exercises, _ = run_agents("text", "P001", "S1", protocol=None)
    # No protocol → unknown stays unknown
    assert exercises[0]["objective"] == "unknown"


@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_replaces_unknown_objective_with_protocol_principal(mock_extract, mock_review, mock_synth):
    ex = [{**FAKE_EXTRACTED[0], "objective": "unknown"}]
    mock_extract.return_value = ex
    mock_review.return_value = {**APPROVED_REVIEW, "exercises": ex}
    mock_synth.return_value = FAKE_SYNTHESIS

    protocol = {"description": "T", "obj_principal": "FUNC", "obj_secondaires": ["STR"]}
    exercises, _ = run_agents("text", "P001", "S1", protocol=protocol)
    # Unknown is replaced by obj_principal
    assert exercises[0]["objective"] == "FUNC"


# --- Muscle trimming (max 3) ---

@patch("agent_orchestrator.synthesize_session")
@patch("agent_orchestrator.review_exercises")
@patch("agent_orchestrator.extract_exercises")
def test_orchestrate_limits_muscles_to_top_3(mock_extract, mock_review, mock_synth):
    ex = [{**FAKE_EXTRACTED[0], "muscles": ["M1", "M2", "M3", "M4", "M5"]}]
    mock_extract.return_value = ex
    mock_review.return_value = {**APPROVED_REVIEW, "exercises": ex}
    mock_synth.return_value = FAKE_SYNTHESIS

    exercises, _ = run_agents("text", "P001", "S1")
    muscles_str = exercises[0]["muscles"]
    assert muscles_str == "M1, M2, M3"
