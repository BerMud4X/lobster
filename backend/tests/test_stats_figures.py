import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stats_figures import (
    figure_pre_post_boxplot,
    figure_individual_change,
    figure_effect_sizes,
    generate_stats_figures,
)

LONG_DF = pd.DataFrame([
    {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous", "scale": "kg",
     "sub_category": None, "timepoint": "pre",  "value": 20, "missing_reason": None},
    {"patient_id": "P1", "test_name": "Grip", "test_type": "quantitative_continuous", "scale": "kg",
     "sub_category": None, "timepoint": "post", "value": 25, "missing_reason": None},
    {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous", "scale": "kg",
     "sub_category": None, "timepoint": "pre",  "value": 22, "missing_reason": None},
    {"patient_id": "P2", "test_name": "Grip", "test_type": "quantitative_continuous", "scale": "kg",
     "sub_category": None, "timepoint": "post", "value": 28, "missing_reason": None},
])

STATS_RESULTS = {
    "n_tests": 1, "n_patients": 2,
    "tests": [{
        "test_name": "Grip", "test_type": "quantitative_continuous", "scale": "kg",
        "sub_categories": [{
            "sub_category": None,
            "descriptive": {
                "pre":  {"n": 2, "mean": 21, "std": 1, "median": 21, "q1": 20.5, "q3": 21.5, "min": 20, "max": 22},
                "post": {"n": 2, "mean": 26.5, "std": 2.12, "median": 26.5, "q1": 25.75, "q3": 27.25, "min": 25, "max": 28},
            },
            "paired_pre_post": {
                "test": "paired_t_test", "n_pairs": 2, "statistic": -8.5,
                "p_value": 0.0746, "effect_size": -3.46, "effect_label": "cohens_d",
                "interpretation": "...",
            },
        }],
    }],
}


def test_pre_post_boxplot_creates_files(tmp_path):
    svg, png = figure_pre_post_boxplot(LONG_DF, "Grip", tmp_path)
    assert svg.exists() and png.exists()

def test_pre_post_boxplot_skips_when_no_data(tmp_path):
    empty = LONG_DF.iloc[0:0]
    svg, png = figure_pre_post_boxplot(empty, "Nonexistent", tmp_path)
    assert svg is None and png is None

def test_individual_change_creates_files(tmp_path):
    svg, png = figure_individual_change(LONG_DF, "Grip", tmp_path)
    assert svg.exists() and png.exists()

def test_individual_change_skips_unpaired(tmp_path):
    only_pre = LONG_DF[LONG_DF["timepoint"] == "pre"]
    svg, png = figure_individual_change(only_pre, "Grip", tmp_path)
    assert svg is None and png is None

def test_effect_sizes_creates_files(tmp_path):
    svg, png = figure_effect_sizes(STATS_RESULTS, tmp_path)
    assert svg.exists() and png.exists()

def test_effect_sizes_skipped_when_no_paired(tmp_path):
    empty_results = {"tests": [{"test_name": "X", "sub_categories": [{"paired_pre_post": None}]}]}
    svg, png = figure_effect_sizes(empty_results, tmp_path)
    assert svg is None and png is None

def test_generate_stats_figures_returns_dict(tmp_path):
    figs = generate_stats_figures(LONG_DF, STATS_RESULTS, tmp_path)
    assert "boxplot_Grip" in figs
    assert "change_Grip" in figs
    assert "effect_sizes" in figs
    for name, (svg, png) in figs.items():
        assert svg.exists()
        assert png.exists()
