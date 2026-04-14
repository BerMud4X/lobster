from collections import Counter
import pandas as pd
from logger import logger


def compute_cohort_stats(df: pd.DataFrame) -> dict:
    """
    Computes cohort-level statistics across all patients in the DataFrame.
    Returns a structured dict ready for injection into AI prompts or reports.
    """
    if df.empty:
        return {}

    n_patients = df["patient_id"].nunique()
    n_sessions_total = df.groupby("patient_id")["session"].nunique().sum()
    n_exercises_total = len(df)

    # Per-patient breakdown
    per_patient = df.groupby("patient_id").agg(
        n_sessions=("session", "nunique"),
        n_exercises=("session", "count"),
    ).reset_index()

    sessions_per_patient = per_patient["n_sessions"]
    exercises_per_patient = per_patient["n_exercises"]

    # Volume per session (series × reps if available, else exercise count)
    volumes = []
    for (pid, session), group in df.groupby(["patient_id", "session"]):
        s = group["series"].fillna(1) if "series" in group.columns else pd.Series([1] * len(group))
        r = group["repetitions"].fillna(1) if "repetitions" in group.columns else pd.Series([1] * len(group))
        if group.get("series", pd.Series()).notna().any() and group.get("repetitions", pd.Series()).notna().any():
            vol = (s * r).sum()
        else:
            vol = len(group)
        volumes.append({"patient_id": pid, "session": session, "volume": vol})

    volume_df = pd.DataFrame(volumes) if volumes else pd.DataFrame(columns=["patient_id", "session", "volume"])

    # Cohort-wide distributions
    objective_dist = df["objective"].value_counts().to_dict() if "objective" in df.columns else {}
    codebase_dist = df["code_base"].value_counts().to_dict() if "code_base" in df.columns else {}

    # Top muscles (cohort-wide)
    all_muscles = []
    for m in df["muscles"].dropna():
        all_muscles.extend([x.strip() for x in str(m).split(",") if x.strip()])
    top_muscles = dict(Counter(all_muscles).most_common(10))

    stats = {
        "n_patients": int(n_patients),
        "n_sessions_total": int(n_sessions_total),
        "n_exercises_total": int(n_exercises_total),
        "sessions_per_patient": {
            "mean": round(float(sessions_per_patient.mean()), 2),
            "std": round(float(sessions_per_patient.std(ddof=0)), 2),
            "min": int(sessions_per_patient.min()),
            "max": int(sessions_per_patient.max()),
        },
        "exercises_per_patient": {
            "mean": round(float(exercises_per_patient.mean()), 2),
            "std": round(float(exercises_per_patient.std(ddof=0)), 2),
            "min": int(exercises_per_patient.min()),
            "max": int(exercises_per_patient.max()),
        },
        "volume_per_session": {
            "mean": round(float(volume_df["volume"].mean()), 2) if not volume_df.empty else 0,
            "std": round(float(volume_df["volume"].std(ddof=0)), 2) if not volume_df.empty else 0,
            "min": float(volume_df["volume"].min()) if not volume_df.empty else 0,
            "max": float(volume_df["volume"].max()) if not volume_df.empty else 0,
        },
        "objective_distribution": objective_dist,
        "codebase_distribution": codebase_dist,
        "top_muscles": top_muscles,
        "per_patient_breakdown": per_patient.to_dict(orient="records"),
    }

    logger.info(f"[Cohort] stats computed for {n_patients} patient(s), {n_sessions_total} session(s)")
    return stats


def format_cohort_summary(stats: dict) -> str:
    """Formats cohort stats as a human-readable text block for AI prompts or reports."""
    if not stats:
        return "No cohort data available."

    lines = [
        f"COHORT SIZE: {stats['n_patients']} patient(s), {stats['n_sessions_total']} total session(s), {stats['n_exercises_total']} exercises recorded.",
        f"Sessions per patient: {stats['sessions_per_patient']['mean']} ± {stats['sessions_per_patient']['std']} (range: {stats['sessions_per_patient']['min']}-{stats['sessions_per_patient']['max']}).",
        f"Exercises per patient: {stats['exercises_per_patient']['mean']} ± {stats['exercises_per_patient']['std']} (range: {stats['exercises_per_patient']['min']}-{stats['exercises_per_patient']['max']}).",
        f"Volume per session: {stats['volume_per_session']['mean']} ± {stats['volume_per_session']['std']} (range: {stats['volume_per_session']['min']}-{stats['volume_per_session']['max']}).",
        f"Objective distribution: {stats['objective_distribution']}",
        f"Top 10 muscles: {stats['top_muscles']}",
    ]
    return "\n".join(lines)
