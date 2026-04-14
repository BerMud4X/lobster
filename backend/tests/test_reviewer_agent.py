import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reviewer_agent import _parse_review_response, _fallback_review, review_exercises

MUSCLES_REF = ["Gluteus maximus", "Quadriceps femoris", "Biceps brachii"]

FAKE_EXERCISES = [{
    "exercise_name": "Knee locking",
    "code": "KnL",
    "code_base": "Push",
    "objective": "STR",
    "muscles": ["Gluteus maximus"],
    "assistance": "parallel bars",
    "series": 3,
    "repetitions": 10,
    "time": None,
}]

VALID_REVIEW = json.dumps({
    "decision": "approved",
    "confidence": 0.95,
    "issues": [],
    "exercises": FAKE_EXERCISES,
})

CORRECTED_REVIEW = json.dumps({
    "decision": "corrected",
    "confidence": 0.85,
    "issues": ["Objective was wrong, corrected to STR"],
    "exercises": [{**FAKE_EXERCISES[0], "objective": "STR"}],
})


# --- _parse_review_response ---

def test_parse_review_approved():
    result = _parse_review_response(VALID_REVIEW)
    assert result["decision"] == "approved"
    assert result["confidence"] == 0.95
    assert result["issues"] == []

def test_parse_review_corrected():
    result = _parse_review_response(CORRECTED_REVIEW)
    assert result["decision"] == "corrected"
    assert len(result["issues"]) == 1

def test_parse_review_strips_markdown():
    raw = f"```json\n{VALID_REVIEW}\n```"
    result = _parse_review_response(raw)
    assert result["decision"] == "approved"

def test_parse_review_handles_prefix():
    raw = f"Here is the review:\n{VALID_REVIEW}"
    result = _parse_review_response(raw)
    assert result["decision"] == "approved"

def test_parse_review_filters_invalid_muscles():
    review = json.dumps({
        "decision": "approved",
        "confidence": 1.0,
        "issues": [],
        "exercises": [{**FAKE_EXERCISES[0], "muscles": ["Gluteus maximus", "FakeMuscle"]}],
    })
    result = _parse_review_response(review)
    assert "FakeMuscle" not in result["exercises"][0]["muscles"]
    assert "Gluteus maximus" in result["exercises"][0]["muscles"]

def test_parse_review_normalizes_code_base():
    review = json.dumps({
        "decision": "approved",
        "confidence": 1.0,
        "issues": [],
        "exercises": [{**FAKE_EXERCISES[0], "code_base": "push"}],
    })
    result = _parse_review_response(review)
    assert result["exercises"][0]["code_base"] == "Push"


# --- _fallback_review ---

def test_fallback_review_structure():
    result = _fallback_review()
    assert result["decision"] == "approved"
    assert "exercises" in result
    assert isinstance(result["issues"], list)


# --- review_exercises ---

@patch("reviewer_agent._call_mistral_review")
def test_review_exercises_calls_mistral(mock_call):
    mock_call.return_value = {"decision": "approved", "confidence": 1.0, "issues": [], "exercises": FAKE_EXERCISES}
    result = review_exercises("do squats", FAKE_EXERCISES, provider="Mistral")
    mock_call.assert_called_once()
    assert result["decision"] == "approved"

@patch("reviewer_agent._call_anthropic_review")
def test_review_exercises_calls_anthropic(mock_call):
    mock_call.return_value = {"decision": "approved", "confidence": 1.0, "issues": [], "exercises": FAKE_EXERCISES}
    result = review_exercises("do squats", FAKE_EXERCISES, provider="Anthropic")
    mock_call.assert_called_once()

def test_review_exercises_preserves_exercises_on_empty_response():
    with patch("reviewer_agent._call_mistral_review", return_value={"decision": "approved", "confidence": 1.0, "issues": [], "exercises": []}):
        result = review_exercises("do squats", FAKE_EXERCISES, provider="Mistral")
        assert result["exercises"] == FAKE_EXERCISES

def test_review_exercises_passes_protocol():
    protocol = {"description": "Test protocol", "obj_principal": "STR", "obj_secondaires": ["FUNC"]}
    with patch("reviewer_agent._call_mistral_review") as mock_call:
        mock_call.return_value = {"decision": "approved", "confidence": 1.0, "issues": [], "exercises": FAKE_EXERCISES}
        review_exercises("do squats", FAKE_EXERCISES, provider="Mistral", protocol=protocol)
        # Second positional arg is the prompt — it should contain protocol context
        prompt = mock_call.call_args[0][1]
        assert "STR" in prompt
        assert "Test protocol" in prompt
