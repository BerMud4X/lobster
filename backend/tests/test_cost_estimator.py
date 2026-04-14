import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cost_estimator import (
    estimate_cost,
    format_estimate,
    get_pricing,
    PRICING,
    AVG_TOKENS,
)


SAMPLE_DF = pd.DataFrame([
    {"patient_id": "P001", "session": "S1", "exercise": "x"},
    {"patient_id": "P001", "session": "S1", "exercise": "y"},
    {"patient_id": "P001", "session": "S2", "exercise": "z"},
    {"patient_id": "P002", "session": "S1", "exercise": "w"},
])


# --- get_pricing ---

def test_get_pricing_known_model():
    p = get_pricing("Mistral", "open-mistral-7b")
    assert p == (0.25, 0.25)

def test_get_pricing_unknown_model():
    assert get_pricing("Mistral", "nonexistent") is None

def test_get_pricing_unknown_provider():
    assert get_pricing("OpenAI", "anything") is None


# --- estimate_cost ---

def test_estimate_returns_pricing_warning_when_unknown():
    est = estimate_cost(SAMPLE_DF, provider="OpenAI", model="gpt-x")
    assert est["pricing_known"] is False
    assert "warning" in est

def test_estimate_counts_rows_sessions_patients():
    est = estimate_cost(SAMPLE_DF, provider="Mistral", model="open-mistral-7b")
    assert est["n_rows"] == 4
    assert est["n_sessions"] == 2  # S1, S2 (unique values)
    assert est["n_patients"] == 2

def test_estimate_includes_basic_calls():
    est = estimate_cost(SAMPLE_DF, provider="Mistral", model="open-mistral-7b")
    calls = est["calls_per_agent"]
    assert calls["extractor"] == 4   # one per row
    assert calls["synthesis"] == 2   # one per session
    assert calls["reviewer"] >= 4    # at least one per row, some retries

def test_estimate_includes_publication_call():
    est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b", report_mode="publication")
    assert est["calls_per_agent"]["publication"] == 1

def test_estimate_includes_clinical_calls_per_patient():
    est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b", report_mode="clinical")
    assert est["calls_per_agent"]["clinical"] == 2  # 2 patients

def test_estimate_cost_is_positive():
    est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b")
    assert est["estimated_cost_usd"] > 0
    assert est["pricing_known"] is True

def test_estimate_anthropic_more_expensive_than_mistral():
    mistral_est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b")
    anthropic_est = estimate_cost(SAMPLE_DF, "Anthropic", "claude-sonnet-4-6")
    assert anthropic_est["estimated_cost_usd"] > mistral_est["estimated_cost_usd"]

def test_estimate_token_totals_consistent_with_calls():
    est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b", report_mode="publication")
    # Verify the math at least matches calls_per_agent
    expected_in = sum(
        n * AVG_TOKENS[a]["prompt"]
        for a, n in est["calls_per_agent"].items()
    )
    assert est["estimated_input_tokens"] == expected_in


# --- format_estimate ---

def test_format_estimate_known_pricing():
    est = estimate_cost(SAMPLE_DF, "Mistral", "open-mistral-7b")
    text = format_estimate(est)
    assert "Mistral" in text
    assert "$" in text
    assert "Total API calls" in text

def test_format_estimate_unknown_pricing():
    est = estimate_cost(SAMPLE_DF, "OpenAI", "gpt-x")
    text = format_estimate(est)
    assert "Pricing unknown" in text or "No pricing" in text


# --- PRICING table sanity ---

def test_pricing_table_has_known_models():
    assert "open-mistral-7b" in PRICING["Mistral"]
    assert "claude-sonnet-4-6" in PRICING["Anthropic"]

def test_pricing_values_are_positive():
    for provider, models in PRICING.items():
        for model, (input_p, output_p) in models.items():
            assert input_p > 0, f"{provider}/{model} input price must be positive"
            assert output_p > 0, f"{provider}/{model} output price must be positive"
