"""
Content-addressed prompt/response cache.

Goal: avoid re-paying the API when the exact same prompt is sent again
(same provider + same model + same prompt text). Identical reruns on the
same input file become free.

Storage format: one JSON file per cache entry, keyed by sha256 of the
(provider, model, prompt) tuple. Entries expire after TTL_DAYS.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from logger import logger

CACHE_DIR = Path("output") / "cache"
TTL_DAYS = 30
_enabled = True
_lock = Lock()
_hits = 0
_misses = 0


def set_enabled(enabled: bool) -> None:
    """Enable/disable the cache for the current process (default: enabled)."""
    global _enabled
    _enabled = bool(enabled)
    logger.info(f"[Cache] enabled={_enabled}")


def is_enabled() -> bool:
    env_flag = os.environ.get("LOBSTER_CACHE", "").lower()
    if env_flag in ("0", "false", "off", "no"):
        return False
    return _enabled


def _key(provider: str, model: str, prompt: str) -> str:
    raw = f"{provider}||{model}||{prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def get(provider: str, model: str, prompt: str) -> str | None:
    """Returns cached raw response or None. None on miss, expired, or if disabled."""
    global _misses
    if not is_enabled():
        return None

    path = _path(_key(provider, model, prompt))
    if not path.exists():
        _misses += 1
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(entry["timestamp"])
        if datetime.now() - ts > timedelta(days=TTL_DAYS):
            logger.info(f"[Cache] expired entry removed: {path.name}")
            path.unlink(missing_ok=True)
            _misses += 1
            return None
        return entry["response"]
    except Exception as e:
        logger.warning(f"[Cache] could not read {path}: {e}")
        _misses += 1
        return None


def put(provider: str, model: str, prompt: str, response: str) -> None:
    """Stores a raw response keyed by (provider, model, prompt)."""
    if not is_enabled():
        return

    key = _key(provider, model, prompt)
    path = _path(key)
    entry = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "response": response,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with _lock:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Cache] could not write {path}: {e}")


def get_or_fetch(provider: str, model: str, prompt: str, fetch_fn) -> tuple[str, bool]:
    """
    Returns (raw_response, was_cache_hit).
    If the cache has an entry, returns it. Otherwise calls fetch_fn() (a no-arg
    callable that performs the API call and returns the raw response string)
    and caches the result.
    """
    global _hits
    cached = get(provider, model, prompt)
    if cached is not None:
        _hits += 1
        return cached, True

    raw = fetch_fn()
    put(provider, model, prompt, raw)
    return raw, False


def stats() -> dict:
    """Returns current session cache stats."""
    total = _hits + _misses
    return {
        "hits": _hits,
        "misses": _misses,
        "total": total,
        "hit_rate": round(_hits / total, 3) if total > 0 else 0.0,
    }


def reset_stats() -> None:
    global _hits, _misses
    _hits = 0
    _misses = 0


def clear_expired() -> int:
    """Deletes all expired entries. Returns count deleted. Safe to call anytime."""
    if not CACHE_DIR.exists():
        return 0
    deleted = 0
    cutoff = datetime.now() - timedelta(days=TTL_DAYS)
    for path in CACHE_DIR.glob("*.json"):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if datetime.fromisoformat(entry["timestamp"]) < cutoff:
                path.unlink()
                deleted += 1
        except Exception:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted


def clear_all() -> int:
    """Deletes ALL cache entries. Returns count deleted."""
    if not CACHE_DIR.exists():
        return 0
    deleted = 0
    for path in CACHE_DIR.glob("*.json"):
        path.unlink()
        deleted += 1
    return deleted
