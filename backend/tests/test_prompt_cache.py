import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import prompt_cache


def _setup_cache(tmp_path):
    """Redirect the cache dir to a temp folder and reset stats."""
    prompt_cache.CACHE_DIR = tmp_path / "cache"
    prompt_cache.reset_stats()
    prompt_cache.set_enabled(True)


# --- get / put basic ---

def test_get_miss_returns_none(tmp_path):
    _setup_cache(tmp_path)
    assert prompt_cache.get("Mistral", "x", "prompt") is None

def test_put_then_get_returns_cached(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "mistral-small", "hello", "response-body")
    assert prompt_cache.get("Mistral", "mistral-small", "hello") == "response-body"

def test_different_prompts_different_keys(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "prompt1", "r1")
    prompt_cache.put("Mistral", "x", "prompt2", "r2")
    assert prompt_cache.get("Mistral", "x", "prompt1") == "r1"
    assert prompt_cache.get("Mistral", "x", "prompt2") == "r2"

def test_different_models_different_keys(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "m1", "prompt", "r1")
    prompt_cache.put("Mistral", "m2", "prompt", "r2")
    assert prompt_cache.get("Mistral", "m1", "prompt") == "r1"
    assert prompt_cache.get("Mistral", "m2", "prompt") == "r2"


# --- disabled cache ---

def test_cache_disabled_always_misses(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "p", "r")
    prompt_cache.set_enabled(False)
    assert prompt_cache.get("Mistral", "x", "p") is None

def test_cache_disabled_does_not_write(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.set_enabled(False)
    prompt_cache.put("Mistral", "x", "p", "r")
    # Dir should not be created
    assert not (tmp_path / "cache").exists() or not list((tmp_path / "cache").glob("*.json"))

def test_env_var_disables_cache(tmp_path, monkeypatch):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "p", "r")
    monkeypatch.setenv("LOBSTER_CACHE", "false")
    assert prompt_cache.get("Mistral", "x", "p") is None


# --- TTL expiry ---

def test_expired_entry_is_removed(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "old", "response")
    # Mock datetime.fromisoformat to return old timestamp
    cache_file = list((tmp_path / "cache").glob("*.json"))[0]
    data = json.loads(cache_file.read_text())
    data["timestamp"] = (datetime.now() - timedelta(days=prompt_cache.TTL_DAYS + 1)).isoformat()
    cache_file.write_text(json.dumps(data))

    assert prompt_cache.get("Mistral", "x", "old") is None
    assert not cache_file.exists()  # expired entry removed


# --- get_or_fetch ---

def test_get_or_fetch_calls_fn_on_miss(tmp_path):
    _setup_cache(tmp_path)
    calls = []
    def fetch():
        calls.append(1)
        return "fresh"
    raw, cached = prompt_cache.get_or_fetch("Mistral", "x", "new-prompt", fetch)
    assert raw == "fresh"
    assert cached is False
    assert len(calls) == 1

def test_get_or_fetch_skips_fn_on_hit(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "existing-prompt", "stored")

    calls = []
    def fetch():
        calls.append(1)
        return "should-not-be-called"

    raw, cached = prompt_cache.get_or_fetch("Mistral", "x", "existing-prompt", fetch)
    assert raw == "stored"
    assert cached is True
    assert calls == []


# --- stats ---

def test_stats_track_hits_and_misses(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "p1", "r1")
    prompt_cache.get_or_fetch("Mistral", "x", "p1", lambda: "fresh")  # hit
    prompt_cache.get_or_fetch("Mistral", "x", "p2", lambda: "fresh")  # miss
    s = prompt_cache.stats()
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["hit_rate"] == 0.5


# --- clear ---

def test_clear_all(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "p1", "r1")
    prompt_cache.put("Mistral", "x", "p2", "r2")
    deleted = prompt_cache.clear_all()
    assert deleted == 2
    assert prompt_cache.get("Mistral", "x", "p1") is None

def test_clear_expired_removes_only_old(tmp_path):
    _setup_cache(tmp_path)
    prompt_cache.put("Mistral", "x", "fresh", "r_fresh")
    prompt_cache.put("Mistral", "x", "old", "r_old")

    # Age out one entry
    for path in (tmp_path / "cache").glob("*.json"):
        data = json.loads(path.read_text())
        if data["response"] == "r_old":
            data["timestamp"] = (datetime.now() - timedelta(days=prompt_cache.TTL_DAYS + 1)).isoformat()
            path.write_text(json.dumps(data))

    deleted = prompt_cache.clear_expired()
    assert deleted == 1
    assert prompt_cache.get("Mistral", "x", "fresh") == "r_fresh"
