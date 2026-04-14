import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cohort_analyzer import compute_cohort_stats, format_cohort_summary


SAMPLE_COHORT = pd.DataFrame([
    {"patient_id": "P001", "session": "S1", "objective": "STR",  "code_base": "Push",       "muscles": "Gluteus maximus, Quadriceps femoris", "series": 3, "repetitions": 10},
    {"patient_id": "P001", "session": "S1", "objective": "STR",  "code_base": "Pull",       "muscles": "Biceps brachii",                      "series": 3, "repetitions": 12},
    {"patient_id": "P001", "session": "S2", "objective": "FUNC", "code_base": "Functional", "muscles": "Gluteus maximus",                      "series": 2, "repetitions": 8},
    {"patient_id": "P002", "session": "S1", "objective": "STR",  "code_base": "Push",       "muscles": "Quadriceps femoris",                   "series": 4, "repetitions": 10},
    {"patient_id": "P002", "session": "S2", "objective": "FUNC", "code_base": "Functional", "muscles": "Gluteus maximus, Erector spinae",      "series": 3, "repetitions": 10},
])


def test_compute_cohort_stats_counts():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    assert stats["n_patients"] == 2
    assert stats["n_sessions_total"] == 4  # P001: S1+S2, P002: S1+S2
    assert stats["n_exercises_total"] == 5

def test_compute_cohort_stats_sessions_per_patient():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    assert stats["sessions_per_patient"]["min"] == 2
    assert stats["sessions_per_patient"]["max"] == 2
    assert stats["sessions_per_patient"]["mean"] == 2.0

def test_compute_cohort_stats_exercises_per_patient():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    # P001 has 3 exercises, P002 has 2
    assert stats["exercises_per_patient"]["min"] == 2
    assert stats["exercises_per_patient"]["max"] == 3

def test_compute_cohort_stats_objective_distribution():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    assert stats["objective_distribution"]["STR"] == 3
    assert stats["objective_distribution"]["FUNC"] == 2

def test_compute_cohort_stats_top_muscles():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    assert "Gluteus maximus" in stats["top_muscles"]
    assert stats["top_muscles"]["Gluteus maximus"] == 3  # appears in 3 rows

def test_compute_cohort_stats_per_patient_breakdown():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    breakdown = stats["per_patient_breakdown"]
    assert len(breakdown) == 2
    ids = {b["patient_id"] for b in breakdown}
    assert ids == {"P001", "P002"}

def test_compute_cohort_stats_volume_uses_series_reps():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    # P001 S1: 3*10 + 3*12 = 66
    # P001 S2: 2*8 = 16
    # P002 S1: 4*10 = 40
    # P002 S2: 3*10 = 30
    # mean = (66+16+40+30)/4 = 38.0
    assert stats["volume_per_session"]["mean"] == 38.0

def test_compute_cohort_stats_empty_df():
    stats = compute_cohort_stats(pd.DataFrame())
    assert stats == {}

def test_format_cohort_summary_contains_key_numbers():
    stats = compute_cohort_stats(SAMPLE_COHORT)
    text = format_cohort_summary(stats)
    assert "2 patient" in text
    assert "5 exercises" in text
    assert "Gluteus maximus" in text

def test_format_cohort_summary_empty():
    assert "No cohort data" in format_cohort_summary({})

def test_single_patient_still_works():
    single = SAMPLE_COHORT[SAMPLE_COHORT["patient_id"] == "P001"]
    stats = compute_cohort_stats(single)
    assert stats["n_patients"] == 1
    assert stats["sessions_per_patient"]["mean"] == 2.0
