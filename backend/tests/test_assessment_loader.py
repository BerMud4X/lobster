import sys
import pandas as pd
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from assessment_loader import load_assessments, CANONICAL_COLUMNS


FAKE_EXTRACTION_GRIP = {
    "test_name": "Grip Strength",
    "test_type": "quantitative_continuous",
    "scale": "kg",
    "data": [
        {"patient_id": "P1", "sub_category": None, "timepoint": "pre",  "value": 20, "missing_reason": None},
        {"patient_id": "P1", "sub_category": None, "timepoint": "post", "value": 25, "missing_reason": None},
    ],
}

FAKE_EXTRACTION_DEMOG = {
    "test_name": "Cases description",
    "test_type": "demographic",
    "scale": None,
    "data": [{"patient_id": "P1", "sub_category": "Age", "timepoint": None, "value": 59, "missing_reason": None}],
}


def _make_xlsx(tmp_path: Path, sheets: dict) -> str:
    p = tmp_path / "assessments.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False, header=False)
    return str(p)


@patch("assessment_loader.detect_and_extract")
def test_load_assessments_returns_canonical_columns(mock_detect, tmp_path):
    mock_detect.return_value = FAKE_EXTRACTION_GRIP
    path = _make_xlsx(tmp_path, {"Grip": pd.DataFrame([[1, 2], [3, 4]])})
    df, meta = load_assessments(path)
    assert list(df.columns) == CANONICAL_COLUMNS
    assert len(df) == 2

@patch("assessment_loader.detect_and_extract")
def test_load_assessments_metadata(mock_detect, tmp_path):
    mock_detect.return_value = FAKE_EXTRACTION_GRIP
    path = _make_xlsx(tmp_path, {"Grip": pd.DataFrame([[1]])})
    _, meta = load_assessments(path)
    assert meta["n_records"] == 2
    assert meta["n_patients"] == 1
    assert "Grip Strength" in meta["tests_found"]

@patch("assessment_loader.detect_and_extract")
def test_load_assessments_skips_demographics_sheet(mock_detect, tmp_path):
    # Two sheets: one demographics, one real test
    def side_effect(name, df, **kwargs):
        return FAKE_EXTRACTION_DEMOG if name == "Cases description" else FAKE_EXTRACTION_GRIP

    mock_detect.side_effect = side_effect
    path = _make_xlsx(tmp_path, {
        "Cases description": pd.DataFrame([[1]]),
        "Grip":              pd.DataFrame([[2]]),
    })
    df, meta = load_assessments(path)
    # Demographics should not be in the test data
    assert "Cases description" not in df["test_name"].tolist()
    assert meta["demographics"] is not None

@patch("assessment_loader.detect_and_extract")
def test_load_assessments_skips_failed_sheets(mock_detect, tmp_path):
    mock_detect.side_effect = [Exception("AI failed"), FAKE_EXTRACTION_GRIP]
    path = _make_xlsx(tmp_path, {
        "BadSheet": pd.DataFrame([[1]]),
        "Grip":     pd.DataFrame([[2]]),
    })
    df, meta = load_assessments(path)
    # Bad sheet skipped, good sheet kept
    assert len(df) == 2

def test_load_assessments_rejects_non_excel(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("a,b\n1,2")
    try:
        load_assessments(str(csv))
        assert False, "should have raised"
    except ValueError as e:
        assert "Excel" in str(e)
