import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from synthesis_agent import _parse_synthesis_response, _derive_dominant_objective, synthesize_session

FAKE_EXERCISES = [
    {"objective": "STR", "muscles": ["Gluteus maximus"]},
    {"objective": "STR", "muscles": ["Quadriceps femoris"]},
    {"objective": "FUNC", "muscles": ["Gluteus maximus"]},
]

VALID_SYNTH = json.dumps({
    "dominant_objective": "STR",
    "dominant_objective_label": "Renforcement musculaire",
    "muscle_groups_worked": ["Gluteus maximus", "Quadriceps femoris"],
    "session_intensity": "moderate",
    "clinical_summary": "Session focused on strengthening.",
    "recommendations": ["Increase reps"],
})


# --- _parse_synthesis_response ---

def test_parse_synthesis_valid():
    result = _parse_synthesis_response(VALID_SYNTH)
    assert result["dominant_objective"] == "STR"
    assert result["session_intensity"] == "moderate"

def test_parse_synthesis_strips_markdown():
    raw = f"```json\n{VALID_SYNTH}\n```"
    result = _parse_synthesis_response(raw)
    assert result["dominant_objective"] == "STR"

def test_parse_synthesis_handles_prefix():
    raw = f"Here is the synthesis:\n{VALID_SYNTH}"
    result = _parse_synthesis_response(raw)
    assert result["dominant_objective"] == "STR"


# --- _derive_dominant_objective ---

def test_derive_dominant_most_common():
    objectives_ref = [
        {"code": "STR", "label": "Strength"},
        {"code": "FUNC", "label": "Functional"},
    ]
    code, label = _derive_dominant_objective(FAKE_EXERCISES, objectives_ref)
    assert code == "STR"
    assert label == "Strength"

def test_derive_dominant_ignores_unknown():
    exercises = [{"objective": "unknown"}, {"objective": "unknown"}, {"objective": "STR"}]
    objectives_ref = [{"code": "STR", "label": "Strength"}]
    code, _ = _derive_dominant_objective(exercises, objectives_ref)
    assert code == "STR"

def test_derive_dominant_all_unknown():
    exercises = [{"objective": "unknown"}, {"objective": "unknown"}]
    code, label = _derive_dominant_objective(exercises, [])
    assert code == "unknown"


# --- synthesize_session ---

@patch("synthesis_agent._call_mistral_synthesis")
def test_synthesize_adds_patient_and_session(mock_call):
    mock_call.return_value = json.loads(VALID_SYNTH)
    result = synthesize_session("P001", "Seance 1", FAKE_EXERCISES, provider="Mistral")
    assert result["patient_id"] == "P001"
    assert result["session"] == "Seance 1"

@patch("synthesis_agent._call_anthropic_synthesis")
def test_synthesize_routes_anthropic(mock_call):
    mock_call.return_value = json.loads(VALID_SYNTH)
    synthesize_session("P001", "S1", FAKE_EXERCISES, provider="Anthropic")
    mock_call.assert_called_once()

@patch("synthesis_agent._call_mistral_synthesis")
def test_synthesize_fallback_on_empty(mock_call):
    mock_call.return_value = {}
    result = synthesize_session("P001", "S1", FAKE_EXERCISES, provider="Mistral")
    # Fallback should still include required fields
    assert "dominant_objective" in result
    assert "muscle_groups_worked" in result
    assert result["patient_id"] == "P001"

@patch("synthesis_agent._call_mistral_synthesis")
def test_synthesize_passes_protocol_in_prompt(mock_call):
    mock_call.return_value = json.loads(VALID_SYNTH)
    protocol = {"description": "Post-stroke rehab", "obj_principal": "FUNC", "obj_secondaires": ["STR"]}
    synthesize_session("P001", "S1", FAKE_EXERCISES, provider="Mistral", protocol=protocol)
    prompt = mock_call.call_args[0][1]
    assert "Post-stroke rehab" in prompt
    assert "FUNC" in prompt
