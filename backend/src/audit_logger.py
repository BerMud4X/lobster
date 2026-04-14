import json
from datetime import datetime
from pathlib import Path
from logger import logger

_audit_path: Path | None = None
_session_id: str | None = None


def init_audit(output_dir: str = "output") -> Path:
    """
    Initializes the audit log for the current run.
    Creates a timestamped JSONL file in `output_dir/audit/`.
    """
    global _audit_path, _session_id
    _session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = Path(output_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _audit_path = audit_dir / f"audit_{_session_id}.jsonl"
    logger.info(f"[Audit] session={_session_id} → {_audit_path}")
    print(f"[Audit] log: {_audit_path}")
    return _audit_path


def log_call(
    agent: str,
    provider: str,
    model: str,
    prompt: str,
    raw_response: str,
    parsed: dict | list | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Appends one entry to the audit log. Silently skipped if init_audit() was not called.
    """
    if _audit_path is None:
        return

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": _session_id,
        "agent": agent,
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "raw_response": raw_response,
        "parsed": parsed,
        "metadata": metadata or {},
    }
    try:
        with open(_audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[Audit] could not write entry: {e}")


def get_audit_path() -> Path | None:
    return _audit_path


def get_session_id() -> str | None:
    return _session_id


def reset_audit() -> None:
    """Resets the global state (mainly for tests)."""
    global _audit_path, _session_id
    _audit_path = None
    _session_id = None
