import pytest
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline import Pipeline


# --- record & get ---

def test_record_and_get():
    p = Pipeline()
    p.record("replace_zeros", {"columns": ["age"]})
    assert p.get("replace_zeros") == {"columns": ["age"]}

def test_get_nonexistent_step():
    p = Pipeline()
    assert p.get("nonexistent") is None

def test_has_step():
    p = Pipeline()
    p.record("trim_whitespace", {})
    assert p.has("trim_whitespace") is True
    assert p.has("handle_missing") is False

def test_multiple_steps():
    p = Pipeline()
    p.record("replace_zeros", {"columns": ["age"]})
    p.record("handle_missing", {"method": "drop_rows"})
    assert len(p.steps) == 2


# --- save & load ---

def test_save_and_load(tmp_path):
    p = Pipeline()
    p.record("replace_zeros", {"columns": ["age"]})
    p.record("standardize_case", {"case": "lowercase"})

    path = str(tmp_path / "pipeline.json")
    p.save(path)

    # verify file exists and is valid JSON
    assert Path(path).exists()
    with open(path) as f:
        data = json.load(f)
    assert "steps" in data
    assert "created_at" in data

def test_load_restores_steps(tmp_path):
    p = Pipeline()
    p.record("replace_zeros", {"columns": ["age"]})
    p.record("handle_missing", {"method": "fill", "fill_value": "mean"})

    path = str(tmp_path / "pipeline.json")
    p.save(path)

    p2 = Pipeline.load(path)
    assert len(p2.steps) == 2
    assert p2.get("replace_zeros") == {"columns": ["age"]}
    assert p2.get("handle_missing") == {"method": "fill", "fill_value": "mean"}

def test_load_preserves_created_at(tmp_path):
    p = Pipeline()
    path = str(tmp_path / "pipeline.json")
    p.save(path)

    p2 = Pipeline.load(path)
    assert p2.created_at == p.created_at
