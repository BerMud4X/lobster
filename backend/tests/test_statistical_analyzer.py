import sys
import math
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from statistical_analyzer import (
    descriptive_stats,
    paired_test,
    analyze_assessments,
    format_summary,
)


# --- descriptive_stats ---

def test_descriptive_basic():
    d = descriptive_stats([1, 2, 3, 4, 5])
    assert d["n"] == 5
    assert d["mean"] == 3.0
    assert d["median"] == 3.0
    assert d["min"] == 1.0
    assert d["max"] == 5.0

def test_descriptive_with_missing():
    d = descriptive_stats([1, 2, None, 4, "NT"])
    assert d["n"] == 3  # only numeric values counted

def test_descriptive_empty():
    d = descriptive_stats([])
    assert d["n"] == 0
    assert d["mean"] is None

def test_descriptive_single_value():
    d = descriptive_stats([42])
    assert d["n"] == 1
    assert d["mean"] == 42.0
    assert d["std"] == 0.0


# --- paired_test ---

def test_paired_test_significant_improvement():
    pre  = [10, 12, 11, 9,  10, 13, 11]
    post = [15, 16, 14, 13, 14, 17, 15]
    result = paired_test(pre, post, "quantitative_continuous")
    assert result["n_pairs"] == 7
    assert result["p_value"] < 0.05
    assert result["effect_size"] is not None

def test_paired_test_no_difference():
    pre  = [10, 11, 12, 13]
    post = [10, 11, 12, 13]
    result = paired_test(pre, post, "quantitative_continuous")
    assert result["p_value"] > 0.05 or result["p_value"] == 1.0

def test_paired_test_drops_unpaired_missing():
    pre  = [10, None, 12]
    post = [15, 16,   14]
    result = paired_test(pre, post, "quantitative_continuous")
    assert result["n_pairs"] == 2  # one pair dropped

def test_paired_test_insufficient_data():
    result = paired_test([10], [12], "quantitative_continuous")
    assert result["test"] == "insufficient_data"

def test_paired_test_ordinal_uses_wilcoxon():
    pre  = [1, 2, 1, 2, 1]
    post = [3, 4, 3, 3, 4]
    result = paired_test(pre, post, "qualitative_ordinal")
    assert result["test"] == "wilcoxon_signed_rank"
    assert result["effect_label"] == "r"

def test_paired_test_continuous_normal_uses_t_test():
    np.random.seed(0)
    pre = list(np.random.normal(10, 2, 30))
    # Add normal noise so differences are normally distributed (not constant)
    post = [v + 3 + np.random.normal(0, 0.8) for v in pre]
    result = paired_test(pre, post, "quantitative_continuous")
    assert result["test"] == "paired_t_test"
    assert result["p_value"] < 0.001
    assert result["effect_label"] == "cohens_d"

def test_paired_test_interpretation_text():
    pre  = [1, 2, 1, 2, 1]
    post = [3, 4, 3, 3, 4]
    result = paired_test(pre, post, "qualitative_ordinal")
    assert "significant" in result["interpretation"]


# --- analyze_assessments ---

def _build_long_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a canonical long-format DataFrame."""
    cols = ["patient_id", "test_name", "test_type", "scale",
            "sub_category", "timepoint", "value", "missing_reason"]
    return pd.DataFrame(rows, columns=cols)


def test_analyze_empty_returns_zero():
    result = analyze_assessments(pd.DataFrame())
    assert result["n_tests"] == 0
    assert result["tests"] == []

def test_analyze_one_test_no_subcategory():
    df = _build_long_df([
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": 20, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 25, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": 22, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 28, "missing_reason": None},
    ])
    result = analyze_assessments(df)
    assert result["n_tests"] == 1
    assert result["n_patients"] == 2
    test = result["tests"][0]
    assert test["test_name"] == "Grip"
    assert "pre" in test["sub_categories"][0]["descriptive"]
    assert "post" in test["sub_categories"][0]["descriptive"]
    assert test["sub_categories"][0]["paired_pre_post"] is not None

def test_analyze_test_with_subcategories():
    df = _build_long_df([
        {"patient_id": "P1", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Pronators", "timepoint": "pre", "value": 2, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Pronators", "timepoint": "post", "value": 1, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Pronators", "timepoint": "pre", "value": 3, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Pronators", "timepoint": "post", "value": 2, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Supinators", "timepoint": "pre", "value": 1, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Ashworth", "test_type": "qualitative_ordinal",
         "scale": "0-5", "sub_category": "Supinators", "timepoint": "post", "value": 0, "missing_reason": None},
    ])
    result = analyze_assessments(df)
    sub_cats = {sc["sub_category"] for sc in result["tests"][0]["sub_categories"]}
    assert sub_cats == {"Pronators", "Supinators"}

def test_analyze_skips_paired_when_only_one_timepoint():
    df = _build_long_df([
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre", "value": 20, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre", "value": 22, "missing_reason": None},
    ])
    result = analyze_assessments(df)
    # Only descriptive; no paired test
    assert result["tests"][0]["sub_categories"][0]["paired_pre_post"] is None

def test_analyze_handles_missing_values_in_data():
    df = _build_long_df([
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": 20, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 25, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": None, "missing_reason": "NT"},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 28, "missing_reason": None},
    ])
    result = analyze_assessments(df)
    paired = result["tests"][0]["sub_categories"][0]["paired_pre_post"]
    # Only P1 has both pre + post → only 1 pair → insufficient
    assert paired["n_pairs"] == 1
    assert paired["test"] == "insufficient_data"


# --- format_summary ---

def test_format_summary_includes_test_names():
    df = _build_long_df([
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": 20, "missing_reason": None},
        {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 25, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "pre",  "value": 22, "missing_reason": None},
        {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous",
         "scale": "kg", "sub_category": None, "timepoint": "post", "value": 28, "missing_reason": None},
    ])
    result = analyze_assessments(df)
    text = format_summary(result)
    assert "Grip" in text
    assert "PRE" in text
    assert "POST" in text

def test_format_summary_empty():
    assert "No statistical results" in format_summary({"tests": []})
