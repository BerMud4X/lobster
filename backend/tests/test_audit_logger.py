import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import audit_logger


def test_log_call_silent_when_uninitialized(tmp_path):
    audit_logger.reset_audit()
    # Should not raise even though no audit was initialized
    audit_logger.log_call("extractor", "Mistral", "open-mistral-7b", "p", "r", parsed=[])
    assert audit_logger.get_audit_path() is None


def test_init_audit_creates_file(tmp_path):
    audit_logger.reset_audit()
    path = audit_logger.init_audit(output_dir=str(tmp_path))
    assert path.parent.exists()
    assert path.parent.name == "audit"
    assert path.suffix == ".jsonl"
    assert path.name.startswith("audit_")


def test_log_call_appends_jsonl_entry(tmp_path):
    audit_logger.reset_audit()
    path = audit_logger.init_audit(output_dir=str(tmp_path))

    audit_logger.log_call(
        agent="extractor",
        provider="Mistral",
        model="open-mistral-7b",
        prompt="Extract from: do squats",
        raw_response='[{"exercise_name": "Squat"}]',
        parsed=[{"exercise_name": "Squat"}],
        metadata={"row": 1},
    )

    assert path.exists()
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent"] == "extractor"
    assert entry["provider"] == "Mistral"
    assert entry["model"] == "open-mistral-7b"
    assert entry["parsed"] == [{"exercise_name": "Squat"}]
    assert entry["metadata"]["row"] == 1
    assert "timestamp" in entry
    assert entry["session_id"]


def test_multiple_log_calls_append(tmp_path):
    audit_logger.reset_audit()
    path = audit_logger.init_audit(output_dir=str(tmp_path))

    for i in range(5):
        audit_logger.log_call("synthesis", "Mistral", "x", f"p{i}", f"r{i}", parsed={"i": i})

    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 5
    for i, line in enumerate(lines):
        assert json.loads(line)["parsed"]["i"] == i


def test_session_id_is_set_after_init(tmp_path):
    audit_logger.reset_audit()
    audit_logger.init_audit(output_dir=str(tmp_path))
    assert audit_logger.get_session_id() is not None
    assert len(audit_logger.get_session_id()) > 0


def test_unicode_in_audit_log(tmp_path):
    audit_logger.reset_audit()
    path = audit_logger.init_audit(output_dir=str(tmp_path))
    audit_logger.log_call("clinical", "Mistral", "x", "Rééducation", "Séance — résumé", parsed={"text": "café"})

    with open(path, encoding="utf-8") as f:
        entry = json.loads(f.readline())
    assert entry["prompt"] == "Rééducation"
    assert entry["parsed"]["text"] == "café"
