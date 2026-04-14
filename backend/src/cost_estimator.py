import pandas as pd
from logger import logger

# Pricing in USD per 1M tokens (input, output)
# Sources: Mistral AI pricing & Anthropic pricing (last verified 2026-01).
# Update these constants if pricing changes upstream.
PRICING = {
    "Mistral": {
        "open-mistral-7b":      (0.25, 0.25),
        "open-mixtral-8x7b":    (0.70, 0.70),
        "mistral-small-latest": (0.20, 0.60),
    },
    "Anthropic": {
        "claude-haiku-4-5-20251001": (0.80, 4.00),
        "claude-sonnet-4-6":         (3.00, 15.00),
        "claude-opus-4-6":           (15.00, 75.00),
    },
}

# Average prompt/response token sizes per agent (estimated from typical prompts)
AVG_TOKENS = {
    "extractor":   {"prompt": 2200, "response": 500},
    "reviewer":    {"prompt": 1800, "response": 450},
    "synthesis":   {"prompt": 1200, "response": 350},
    "publication": {"prompt": 3500, "response": 1500},
    "clinical":    {"prompt": 3000, "response": 1500},
}

# Reviewer averages 1.1x because some inputs trigger 1 retry
REVIEW_RETRY_FACTOR = 1.1

CONFIRM_THRESHOLD_USD = 1.0


def get_pricing(provider: str, model: str) -> tuple[float, float] | None:
    """Returns (input $/M, output $/M) for the given provider/model, or None if unknown."""
    return PRICING.get(provider, {}).get(model)


def estimate_cost(
    df: pd.DataFrame,
    provider: str,
    model: str,
    report_mode: str | None = None,
) -> dict:
    """
    Estimates total API cost before processing.

    Parameters:
        df:         the validated input DataFrame (rows = exercise descriptions)
        provider:   "Mistral" | "Anthropic"
        model:      model id
        report_mode: "publication" | "clinical" | None  (adds final-report cost if set)

    Returns:
        {
            "provider": str, "model": str,
            "n_rows": int, "n_sessions": int, "n_patients": int,
            "calls_per_agent": {agent: int, ...},
            "estimated_total_calls": int,
            "estimated_input_tokens": int,
            "estimated_output_tokens": int,
            "estimated_cost_usd": float,
            "pricing_known": bool,
        }
    """
    pricing = get_pricing(provider, model)
    if pricing is None:
        logger.warning(f"[CostEstimator] no pricing data for {provider}/{model}")
        return {
            "provider": provider, "model": model,
            "n_rows": len(df),
            "estimated_cost_usd": 0.0,
            "pricing_known": False,
            "warning": f"Pricing unknown for {provider}/{model}. Update PRICING in cost_estimator.py.",
        }

    in_per_token = pricing[0] / 1_000_000
    out_per_token = pricing[1] / 1_000_000

    n_rows = len(df)
    n_sessions = int(df["session"].nunique()) if "session" in df.columns else n_rows
    n_patients = int(df["patient_id"].nunique()) if "patient_id" in df.columns else 1

    # Call counts per agent
    calls = {
        "extractor": n_rows,
        "reviewer":  int(round(n_rows * REVIEW_RETRY_FACTOR)),
        "synthesis": n_sessions,
    }
    if report_mode == "publication":
        calls["publication"] = 1
    elif report_mode == "clinical":
        calls["clinical"] = n_patients

    # Token totals
    in_tokens = 0
    out_tokens = 0
    for agent, n_calls in calls.items():
        avg = AVG_TOKENS.get(agent, {"prompt": 1500, "response": 400})
        in_tokens += n_calls * avg["prompt"]
        out_tokens += n_calls * avg["response"]

    cost = in_tokens * in_per_token + out_tokens * out_per_token

    return {
        "provider": provider, "model": model,
        "n_rows": n_rows, "n_sessions": n_sessions, "n_patients": n_patients,
        "calls_per_agent": calls,
        "estimated_total_calls": sum(calls.values()),
        "estimated_input_tokens": in_tokens,
        "estimated_output_tokens": out_tokens,
        "estimated_cost_usd": round(cost, 4),
        "pricing_known": True,
    }


def format_estimate(estimate: dict) -> str:
    """Renders a cost estimate as a human-readable block."""
    if not estimate.get("pricing_known", True):
        return (
            f"━━━ Cost estimate ━━━\n"
            f"  {estimate.get('warning', 'No pricing data available.')}\n"
            f"  Rows to process: {estimate['n_rows']}"
        )

    lines = [
        f"━━━ Cost estimate ({estimate['provider']} / {estimate['model']}) ━━━",
        f"  Patients: {estimate['n_patients']} | Sessions: {estimate['n_sessions']} | Rows: {estimate['n_rows']}",
        f"  Calls per agent: " + ", ".join(f"{k}={v}" for k, v in estimate['calls_per_agent'].items()),
        f"  Total API calls: {estimate['estimated_total_calls']}",
        f"  Estimated tokens: {estimate['estimated_input_tokens']:,} input + {estimate['estimated_output_tokens']:,} output",
        f"  Estimated cost:   ~${estimate['estimated_cost_usd']:.4f} USD",
        f"  (Estimate ±30%. Actual cost depends on real prompt/response sizes.)",
    ]
    return "\n".join(lines)
