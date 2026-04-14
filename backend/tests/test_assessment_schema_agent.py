import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from assessment_schema_agent import _validate_extraction, MISSING_CODES, _normalize_record


# --- _validate_extraction: defensive validation ---

def test_validate_valid_input_passes_through():
    parsed = {
        "test_name": "Berg Balance",
        "test_type": "quantitative_continuous",
        "scale": "0-56",
        "data": [{"patient_id": "P1", "value": 42}],
    }
    result = _validate_extraction(parsed)
    assert result["test_name"] == "Berg Balance"
    assert result["test_type"] == "quantitative_continuous"
    assert result["scale"] == "0-56"
    assert len(result["data"]) == 1

def test_validate_non_dict_returns_empty():
    for bad in [None, [], "string", 42, True]:
        result = _validate_extraction(bad)
        assert result["data"] == []
        assert result["test_name"] == "unknown"

def test_validate_missing_test_name_defaults_unknown():
    result = _validate_extraction({"test_type": "foo", "data": []})
    assert result["test_name"] == "unknown"

def test_validate_empty_test_name_defaults_unknown():
    result = _validate_extraction({"test_name": "  ", "test_type": "foo", "data": []})
    assert result["test_name"] == "unknown"

def test_validate_missing_test_type_defaults_unknown():
    result = _validate_extraction({"test_name": "Test", "data": []})
    assert result["test_type"] == "unknown"

def test_validate_invalid_scale_becomes_none():
    result = _validate_extraction({"test_name": "T", "test_type": "x", "scale": {"bad": 1}, "data": []})
    assert result["scale"] is None

def test_validate_scale_can_be_string_or_number():
    for ok in ["0-56", 42, 3.14]:
        result = _validate_extraction({"test_name": "T", "test_type": "x", "scale": ok, "data": []})
        assert result["scale"] == ok

def test_validate_data_not_list_becomes_empty():
    result = _validate_extraction({"test_name": "T", "test_type": "x", "data": "not a list"})
    assert result["data"] == []

def test_validate_data_filters_non_dict_items():
    result = _validate_extraction({
        "test_name": "T", "test_type": "x",
        "data": [{"patient_id": "P1"}, "garbage", 42, None, {"patient_id": "P2"}],
    })
    assert len(result["data"]) == 2

def test_validate_strips_whitespace():
    result = _validate_extraction({"test_name": "  Berg  ", "test_type": "  ordinal  ", "data": []})
    assert result["test_name"] == "Berg"
    assert result["test_type"] == "ordinal"


# --- _normalize_record: missing-code & timepoint normalization ---

def test_normalize_detects_missing_code_in_value():
    rec = {"patient_id": "P1", "value": "NT", "timepoint": "pre"}
    norm = _normalize_record(rec)
    assert norm["value"] is None
    assert norm["missing_reason"] == "NT"

def test_normalize_preserves_explicit_missing_reason():
    rec = {"patient_id": "P1", "value": None, "missing_reason": "NA"}
    norm = _normalize_record(rec)
    assert norm["value"] is None
    assert norm["missing_reason"] == "NA"

def test_normalize_timepoint_variants():
    assert _normalize_record({"timepoint": "PRE"})["timepoint"] == "pre"
    assert _normalize_record({"timepoint": "baseline"})["timepoint"] == "pre"
    assert _normalize_record({"timepoint": "posttest"})["timepoint"] == "post"
    assert _normalize_record({"timepoint": "follow_up"})["timepoint"] == "retention"

def test_normalize_numeric_value_unchanged():
    assert _normalize_record({"value": 42})["value"] == 42
    assert _normalize_record({"value": 3.14})["value"] == 3.14

def test_missing_codes_set_contains_expected():
    for code in ["NT", "NA", "NC", "N/A", "", "-"]:
        assert code in MISSING_CODES
