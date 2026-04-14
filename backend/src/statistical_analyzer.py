"""
Deterministic statistical engine for assessment data.

Given a long-format DataFrame from assessment_loader, computes:
  - Descriptive stats per (test × sub_category × timepoint): mean, std, median, IQR, n
  - Inferential tests for paired pre-post comparisons:
      * Continuous quantitative      → Shapiro-Wilk normality → paired t-test or Wilcoxon
      * Ordinal qualitative          → Wilcoxon signed-rank
      * Discrete quantitative        → Wilcoxon signed-rank
  - Effect sizes (Cohen's d for t-test, r for Wilcoxon)

NO AI involvement here — every number can be reproduced from raw data with scipy.
"""

import math
import pandas as pd
import numpy as np
from scipy import stats
from logger import logger


def _to_numeric(series: pd.Series) -> pd.Series:
    """Coerce values to float, dropping non-numeric and NaN."""
    return pd.to_numeric(series, errors="coerce").dropna()


def _normality_ok(values: np.ndarray, alpha: float = 0.05) -> bool | None:
    """Returns True if Shapiro-Wilk fails to reject normality (p > alpha). None if n too small."""
    if len(values) < 3:
        return None
    try:
        _, p = stats.shapiro(values)
        return bool(p > alpha)
    except Exception:
        return None


def _cohens_d_paired(pre: np.ndarray, post: np.ndarray) -> float | None:
    """Cohen's d for paired samples = mean(diff) / std(diff)."""
    diff = post - pre
    if len(diff) < 2 or diff.std(ddof=1) == 0:
        return None
    return float(diff.mean() / diff.std(ddof=1))


def _r_effect(z_stat: float, n: int) -> float | None:
    """Effect size r = |Z| / sqrt(N) — for non-parametric tests."""
    if n <= 0 or z_stat is None:
        return None
    return float(abs(z_stat) / math.sqrt(n))


def _wilcoxon_z(w_stat: float, n: int) -> float:
    """
    Computes the Wilcoxon z-statistic from W under H0 (when scipy doesn't expose it).
    H0: mean(W) = n(n+1)/4, std(W) = sqrt(n(n+1)(2n+1)/24).
    """
    if n <= 0:
        return 0.0
    mean_w = n * (n + 1) / 4
    std_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    if std_w == 0:
        return 0.0
    return (w_stat - mean_w) / std_w


def descriptive_stats(values: list) -> dict:
    """Returns mean, std, median, IQR, min, max, n for a list of numeric values."""
    nums = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if nums.empty:
        return {"n": 0, "mean": None, "std": None, "median": None,
                "q1": None, "q3": None, "min": None, "max": None}
    return {
        "n":      int(len(nums)),
        "mean":   round(float(nums.mean()), 3),
        "std":    round(float(nums.std(ddof=1)), 3) if len(nums) > 1 else 0.0,
        "median": round(float(nums.median()), 3),
        "q1":     round(float(nums.quantile(0.25)), 3),
        "q3":     round(float(nums.quantile(0.75)), 3),
        "min":    round(float(nums.min()), 3),
        "max":    round(float(nums.max()), 3),
    }


def paired_test(pre_values: list, post_values: list, test_type: str) -> dict:
    """
    Runs a paired pre-post test choosing the appropriate method.
    Returns: {test, n_pairs, statistic, p_value, effect_size, effect_label, interpretation}
    """
    # Pair up values, dropping any pair where either side is missing
    paired = [(p, q) for p, q in zip(pre_values, post_values)
              if p is not None and q is not None
              and not (isinstance(p, float) and math.isnan(p))
              and not (isinstance(q, float) and math.isnan(q))]

    if len(paired) < 2:
        return {
            "test": "insufficient_data", "n_pairs": len(paired),
            "statistic": None, "p_value": None,
            "effect_size": None, "effect_label": None,
            "interpretation": "Not enough paired observations.",
        }

    pre  = np.array([p for p, _ in paired], dtype=float)
    post = np.array([q for _, q in paired], dtype=float)

    # Edge case: all paired values identical → no change at all
    if np.all(pre == post):
        return {
            "test": "no_difference", "n_pairs": len(paired),
            "statistic": 0.0, "p_value": 1.0,
            "effect_size": 0.0, "effect_label": None,
            "interpretation": "All paired values are identical (no change).",
        }

    is_continuous = test_type == "quantitative_continuous"
    use_parametric = is_continuous and _normality_ok(post - pre) is True

    try:
        if use_parametric:
            stat, p = stats.ttest_rel(pre, post)
            effect = _cohens_d_paired(pre, post)
            test_used = "paired_t_test"
            effect_label = "cohens_d"
        else:
            try:
                result = stats.wilcoxon(pre, post, zero_method="wilcox", alternative="two-sided")
                stat, p = result.statistic, result.pvalue
                z = result.zstatistic if hasattr(result, "zstatistic") else _wilcoxon_z(stat, len(paired))
            except ValueError as e:
                # All differences are zero → no change at all
                return {
                    "test": "wilcoxon_signed_rank", "n_pairs": len(paired),
                    "statistic": None, "p_value": 1.0,
                    "effect_size": 0.0, "effect_label": "r",
                    "interpretation": f"All paired differences are zero ({e}).",
                }
            effect = _r_effect(z, len(paired) * 2)
            test_used = "wilcoxon_signed_rank"
            effect_label = "r"
    except Exception as e:
        logger.warning(f"[Stats] paired test failed: {e}")
        return {
            "test": "failed", "n_pairs": len(paired),
            "statistic": None, "p_value": None,
            "effect_size": None, "effect_label": None,
            "interpretation": f"Test failed: {e}",
        }

    interpretation = _interpret(p, effect, effect_label)

    return {
        "test": test_used,
        "n_pairs": len(paired),
        "statistic": round(float(stat), 4) if stat is not None else None,
        "p_value": round(float(p), 4) if p is not None else None,
        "effect_size": round(float(effect), 3) if effect is not None else None,
        "effect_label": effect_label,
        "interpretation": interpretation,
    }


def _interpret(p_value: float | None, effect: float | None, effect_label: str | None) -> str:
    """Plain-language summary of significance + effect size."""
    if p_value is None:
        return "No interpretation available."
    sig = "statistically significant" if p_value < 0.05 else "not statistically significant"
    msg = f"Difference is {sig} (p={p_value:.4f})."
    if effect is not None and effect_label == "cohens_d":
        magnitude = "negligible" if abs(effect) < 0.2 else "small" if abs(effect) < 0.5 else "moderate" if abs(effect) < 0.8 else "large"
        msg += f" Cohen's d = {effect:.2f} ({magnitude} effect)."
    elif effect is not None and effect_label == "r":
        magnitude = "negligible" if abs(effect) < 0.1 else "small" if abs(effect) < 0.3 else "moderate" if abs(effect) < 0.5 else "large"
        msg += f" Effect size r = {effect:.2f} ({magnitude})."
    return msg


def analyze_assessments(df: pd.DataFrame) -> dict:
    """
    Main entry point. Returns a structured stats dict:

    {
        "n_tests": int,
        "n_patients": int,
        "tests": [
            {
                "test_name": str,
                "test_type": str,
                "scale": str | None,
                "sub_categories": [
                    {
                        "sub_category": str | None,
                        "descriptive": {timepoint: {n, mean, std, median, q1, q3, min, max}},
                        "paired_pre_post": {test, n_pairs, statistic, p_value, effect_size, ...} | None,
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    if df.empty:
        return {"n_tests": 0, "n_patients": 0, "tests": []}

    n_patients = int(df["patient_id"].nunique())
    tests_results = []

    for test_name, test_df in df.groupby("test_name", sort=False):
        test_type = test_df["test_type"].mode().iat[0] if not test_df["test_type"].mode().empty else "unknown"
        scale = test_df["scale"].dropna().iat[0] if test_df["scale"].notna().any() else None

        sub_cat_results = []
        # NaN sub_categories are grouped together (single category)
        groupby_cols = ["sub_category"] if test_df["sub_category"].notna().any() else []

        if groupby_cols:
            sub_groups = test_df.groupby("sub_category", dropna=False, sort=False)
        else:
            sub_groups = [(None, test_df)]

        for sub_cat, sub_df in sub_groups:
            descriptive = {}
            for tp, tp_df in sub_df.groupby("timepoint", dropna=True, sort=False):
                if pd.isna(tp):
                    continue
                descriptive[str(tp)] = descriptive_stats(tp_df["value"].tolist())

            # Paired pre-post test if both timepoints exist and have ≥2 pairs
            paired = None
            if "pre" in descriptive and "post" in descriptive:
                pre_df = sub_df[sub_df["timepoint"] == "pre"].set_index("patient_id")["value"]
                post_df = sub_df[sub_df["timepoint"] == "post"].set_index("patient_id")["value"]
                common_patients = pre_df.index.intersection(post_df.index)
                if len(common_patients) >= 2:
                    pre_values = pre_df.loc[common_patients].tolist()
                    post_values = post_df.loc[common_patients].tolist()
                    paired = paired_test(pre_values, post_values, test_type)

            sub_cat_results.append({
                "sub_category": sub_cat,
                "descriptive": descriptive,
                "paired_pre_post": paired,
            })

        tests_results.append({
            "test_name": test_name,
            "test_type": test_type,
            "scale": scale,
            "sub_categories": sub_cat_results,
        })

    return {
        "n_tests": len(tests_results),
        "n_patients": n_patients,
        "tests": tests_results,
    }


def format_summary(results: dict) -> str:
    """Renders a stats summary as a human-readable text block."""
    if not results.get("tests"):
        return "No statistical results available."

    lines = [
        f"━━━ Statistical analysis ━━━",
        f"  {results['n_patients']} patient(s), {results['n_tests']} test(s)",
    ]

    for test in results["tests"]:
        lines.append(f"\n  ▸ {test['test_name']} ({test['test_type']}, scale={test.get('scale') or 'n/a'})")
        for sc in test["sub_categories"]:
            label = sc["sub_category"] or "—"
            lines.append(f"    • {label}")
            for tp, desc in sc["descriptive"].items():
                if desc["n"] > 0:
                    lines.append(f"        {tp.upper():<10} n={desc['n']}, mean={desc['mean']}±{desc['std']}, median={desc['median']}")
            if sc["paired_pre_post"]:
                p = sc["paired_pre_post"]
                lines.append(f"        Paired test ({p['test']}, n={p['n_pairs']}): {p['interpretation']}")

    return "\n".join(lines)
