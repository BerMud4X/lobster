import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from report_figures import (
    figure_objective_distribution,
    figure_muscles_worked,
    figure_codebase_distribution,
    figure_volume_progression,
    figure_cohort_exercises_per_patient,
    figure_cohort_volume_boxplot,
    figure_cohort_objectives_heatmap,
    generate_all_figures,
)

SAMPLE_DF = pd.DataFrame([
    {"session": "S1", "objective": "STR", "code_base": "Push",       "muscles": "Gluteus maximus, Quadriceps femoris", "series": 3,    "repetitions": 10},
    {"session": "S1", "objective": "STR", "code_base": "Pull",       "muscles": "Biceps brachii",                      "series": 3,    "repetitions": 12},
    {"session": "S2", "objective": "FUNC","code_base": "Functional", "muscles": "Gluteus maximus",                      "series": None, "repetitions": None},
    {"session": "S2", "objective": "STR", "code_base": "Push",       "muscles": "Quadriceps femoris",                   "series": 4,    "repetitions": 8},
])

COHORT_DF = pd.DataFrame([
    {"patient_id": "P001", "session": "S1", "objective": "STR",  "code_base": "Push",       "muscles": "Gluteus maximus", "series": 3, "repetitions": 10},
    {"patient_id": "P001", "session": "S2", "objective": "FUNC", "code_base": "Functional", "muscles": "Gluteus maximus", "series": 2, "repetitions": 8},
    {"patient_id": "P002", "session": "S1", "objective": "STR",  "code_base": "Push",       "muscles": "Quadriceps femoris", "series": 4, "repetitions": 10},
    {"patient_id": "P002", "session": "S2", "objective": "FUNC", "code_base": "Functional", "muscles": "Erector spinae",     "series": 3, "repetitions": 10},
])


def test_objective_distribution_creates_svg_and_png(tmp_path):
    svg, png = figure_objective_distribution(SAMPLE_DF, tmp_path)
    assert svg.exists()
    assert png.exists()
    assert svg.suffix == ".svg"
    assert png.suffix == ".png"

def test_muscles_figure_handles_comma_separated(tmp_path):
    svg, png = figure_muscles_worked(SAMPLE_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_muscles_figure_returns_none_on_empty(tmp_path):
    empty = pd.DataFrame({"muscles": []})
    svg, png = figure_muscles_worked(empty, tmp_path)
    assert svg is None
    assert png is None

def test_codebase_distribution(tmp_path):
    svg, png = figure_codebase_distribution(SAMPLE_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_volume_progression_with_series_reps(tmp_path):
    svg, png = figure_volume_progression(SAMPLE_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_volume_progression_fallback_no_series(tmp_path):
    no_vol = pd.DataFrame([
        {"session": "S1", "objective": "STR", "code_base": "Push", "muscles": "x", "series": None, "repetitions": None},
        {"session": "S2", "objective": "STR", "code_base": "Pull", "muscles": "y", "series": None, "repetitions": None},
    ])
    svg, png = figure_volume_progression(no_vol, tmp_path)
    assert svg.exists()

def test_generate_all_figures_creates_output_dir(tmp_path):
    out = tmp_path / "figs"
    figures = generate_all_figures(SAMPLE_DF, out)
    assert out.exists()
    assert len(figures) >= 3  # objectives, codebase, volume always, muscles conditional
    for name, (svg, png) in figures.items():
        assert svg.exists()
        assert png.exists()

def test_generate_all_figures_keys(tmp_path):
    figures = generate_all_figures(SAMPLE_DF, tmp_path)
    expected = {"objectives", "codebase", "volume"}
    assert expected.issubset(set(figures.keys()))


# --- Cohort figures ---

def test_cohort_exercises_per_patient(tmp_path):
    svg, png = figure_cohort_exercises_per_patient(COHORT_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_cohort_exercises_skipped_single_patient(tmp_path):
    single = COHORT_DF[COHORT_DF["patient_id"] == "P001"]
    svg, png = figure_cohort_exercises_per_patient(single, tmp_path)
    assert svg is None and png is None

def test_cohort_volume_boxplot(tmp_path):
    svg, png = figure_cohort_volume_boxplot(COHORT_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_cohort_objectives_heatmap(tmp_path):
    svg, png = figure_cohort_objectives_heatmap(COHORT_DF, tmp_path)
    assert svg.exists() and png.exists()

def test_generate_all_figures_includes_cohort_figures(tmp_path):
    figures = generate_all_figures(COHORT_DF, tmp_path)
    assert "cohort_exercises_per_patient" in figures
    assert "cohort_volume_boxplot" in figures
    assert "cohort_objectives_heatmap" in figures

def test_generate_all_figures_skips_cohort_for_single_patient(tmp_path):
    single = COHORT_DF[COHORT_DF["patient_id"] == "P001"]
    figures = generate_all_figures(single, tmp_path)
    assert "cohort_exercises_per_patient" not in figures
    assert "cohort_volume_boxplot" not in figures
