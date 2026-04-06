import pytest
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reporter import _build_snapshot, generate_report


# --- Fixtures ---

@pytest.fixture
def df_before():
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Bob"],
        "age": [30, 25, None, 25],
        "city": ["Paris", "Lyon", "Marseille", "Lyon"]
    })

@pytest.fixture
def df_after():
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [30, 25, 0],
        "city": ["Paris", "Lyon", "Marseille"]
    })


# --- _build_snapshot ---

def test_snapshot_shape(df_before):
    snapshot = _build_snapshot(df_before)
    assert snapshot["rows"] == 4
    assert snapshot["columns"] == 3

def test_snapshot_missing_values(df_before):
    snapshot = _build_snapshot(df_before)
    assert snapshot["missing_values"]["age"] == 1

def test_snapshot_duplicates(df_before):
    snapshot = _build_snapshot(df_before)
    assert snapshot["duplicates"] == 1

def test_snapshot_column_types(df_before):
    snapshot = _build_snapshot(df_before)
    assert "name" in snapshot["column_types"]
    assert "age" in snapshot["column_types"]


# --- generate_report ---

def test_report_structure(df_before, df_after):
    report = generate_report(df_before, df_after, [])
    assert "generated_at" in report
    assert "before" in report
    assert "after" in report
    assert "summary" in report
    assert "pipeline_steps" in report

def test_report_rows_removed(df_before, df_after):
    report = generate_report(df_before, df_after, [])
    assert report["summary"]["rows_removed"] == 1

def test_report_missing_values(df_before, df_after):
    report = generate_report(df_before, df_after, [])
    assert report["summary"]["missing_values_before"] == 1
    assert report["summary"]["missing_values_after"] == 0

def test_report_duplicates_removed(df_before, df_after):
    report = generate_report(df_before, df_after, [])
    assert report["summary"]["duplicates_removed"] == 1

def test_report_pipeline_steps(df_before, df_after):
    steps = [{"step": "replace_zeros", "params": {"columns": ["age"]}}]
    report = generate_report(df_before, df_after, steps)
    assert len(report["pipeline_steps"]) == 1
    assert report["pipeline_steps"][0]["step"] == "replace_zeros"
