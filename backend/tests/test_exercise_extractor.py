import pytest
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from exercise_extractor import (
    _build_prompt,
    _parse_response,
    _fallback,
    extract_exercises,
    PROVIDERS,
)

MUSCLES_REF = ["Quadriceps femoris", "Gluteus maximus", "Biceps brachii", "Triceps brachii"]

VALID_JSON = json.dumps([{
    "exercise_name": "Knee locking",
    "code": "KnL",
    "code_base": "Functional",
    "muscles": ["Gluteus maximus"],
    "assistance": "parallel bars",
    "repetitions": None,
    "time": None,
}])


# --- _build_prompt ---

def test_build_prompt_contains_text():
    prompt = _build_prompt("patient did squats", [], MUSCLES_REF)
    assert "patient did squats" in prompt

def test_build_prompt_contains_muscles():
    prompt = _build_prompt("squats", [], MUSCLES_REF)
    assert "Gluteus maximus" in prompt

def test_build_prompt_no_exercises_ref():
    prompt = _build_prompt("squats", [], MUSCLES_REF)
    assert "No reference available yet" in prompt

def test_build_prompt_with_exercises_ref():
    ref = [{"name": "Knee locking", "code": "KnL", "code_base": "Functional"}]
    prompt = _build_prompt("squats", ref, MUSCLES_REF)
    assert "KnL" in prompt

def test_build_prompt_contains_valid_code_base_values():
    prompt = _build_prompt("squats", [], MUSCLES_REF)
    assert "Push" in prompt
    assert "Transfer" in prompt
    assert "unknown" in prompt


# --- _parse_response ---

def test_parse_response_valid_json():
    result = _parse_response(VALID_JSON, MUSCLES_REF)
    assert len(result) == 1
    assert result[0]["exercise_name"] == "Knee locking"

def test_parse_response_strips_markdown_code_block():
    raw = f"```json\n{VALID_JSON}\n```"
    result = _parse_response(raw, MUSCLES_REF)
    assert len(result) == 1

def test_parse_response_strips_markdown_no_lang():
    raw = f"```\n{VALID_JSON}\n```"
    result = _parse_response(raw, MUSCLES_REF)
    assert len(result) == 1

def test_parse_response_finds_array_in_text():
    raw = f"Here is the result: {VALID_JSON}"
    result = _parse_response(raw, MUSCLES_REF)
    assert len(result) == 1

def test_parse_response_filters_invalid_muscles():
    raw = json.dumps([{
        "exercise_name": "Test",
        "code": "TST",
        "code_base": "Push",
        "muscles": ["Gluteus maximus", "Not a real muscle"],
        "assistance": None,
        "repetitions": None,
        "time": None,
    }])
    result = _parse_response(raw, MUSCLES_REF)
    assert result[0]["muscles"] == ["Gluteus maximus"]

def test_parse_response_normalizes_none_fields():
    raw = json.dumps([{
        "exercise_name": "Test",
        "code": "TST",
        "code_base": "Push",
        "muscles": [],
        "assistance": "",
        "repetitions": 0,
        "time": 0,
    }])
    result = _parse_response(raw, MUSCLES_REF)
    assert result[0]["assistance"] is None
    assert result[0]["repetitions"] is None
    assert result[0]["time"] is None

def test_parse_response_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_response("not valid json", MUSCLES_REF)


# --- _fallback ---

def test_fallback_returns_list():
    result = _fallback()
    assert isinstance(result, list)
    assert len(result) == 1

def test_fallback_fields():
    result = _fallback()[0]
    assert result["exercise_name"] == "unknown"
    assert result["code"] == "UNK"
    assert result["code_base"] == "unknown"
    assert result["muscles"] == []
    assert result["assistance"] is None
    assert result["repetitions"] is None
    assert result["time"] is None


# --- PROVIDERS config ---

def test_providers_has_mistral_and_anthropic():
    names = [p["name"] for p in PROVIDERS.values()]
    assert "Mistral" in names
    assert "Anthropic" in names

def test_providers_have_required_keys():
    for p in PROVIDERS.values():
        assert "name" in p
        assert "models" in p
        assert "env_key" in p


# --- extract_exercises (mocked API calls) ---

@patch("exercise_extractor._call_mistral")
def test_extract_exercises_routes_mistral(mock_mistral):
    mock_mistral.return_value = [{"exercise_name": "Test", "code": "TST", "code_base": "Push",
                                  "muscles": [], "assistance": None, "repetitions": None, "time": None}]
    result = extract_exercises("patient did squats", model="open-mistral-7b", provider="Mistral")
    mock_mistral.assert_called_once()
    assert len(result) == 1

@patch("exercise_extractor._call_anthropic")
def test_extract_exercises_routes_anthropic(mock_anthropic):
    mock_anthropic.return_value = [{"exercise_name": "Test", "code": "TST", "code_base": "Push",
                                    "muscles": [], "assistance": None, "repetitions": None, "time": None}]
    result = extract_exercises("patient did squats", model="claude-haiku-4-5-20251001", provider="Anthropic")
    mock_anthropic.assert_called_once()
    assert len(result) == 1

@patch("exercise_extractor._call_mistral")
def test_extract_exercises_default_provider_is_mistral(mock_mistral):
    mock_mistral.return_value = _fallback()
    extract_exercises("some text")
    mock_mistral.assert_called_once()
