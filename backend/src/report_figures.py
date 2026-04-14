import io
from pathlib import Path
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

PALETTE = ["#2D6A9F", "#4EABD1", "#6DC5A1", "#F4A261", "#E76F51", "#A8DADC", "#457B9D"]


def _save(fig, output_dir: Path, name: str) -> tuple[Path, Path]:
    """Saves a figure as both SVG and PNG. Returns (svg_path, png_path)."""
    svg_path = output_dir / f"{name}.svg"
    png_path = output_dir / f"{name}.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return svg_path, png_path


def figure_objective_distribution(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Bar chart — exercise count by therapeutic objective."""
    counts = df["objective"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(counts.index.tolist(), counts.values, color=PALETTE[:len(counts)])
    ax.set_xlabel("Number of exercises")
    ax.set_title("Distribution of Therapeutic Objectives")
    ax.bar_label(bars, padding=3)
    ax.invert_yaxis()
    fig.tight_layout()
    return _save(fig, output_dir, "fig_objectives")


def figure_muscles_worked(df: pd.DataFrame, output_dir: Path, top_n: int = 10) -> tuple[Path, Path]:
    """Horizontal bar chart — most frequently worked muscles."""
    all_muscles = []
    for muscles_str in df["muscles"].dropna():
        all_muscles.extend([m.strip() for m in muscles_str.split(",") if m.strip()])

    counts = Counter(all_muscles).most_common(top_n)
    if not counts:
        return None, None

    muscles, freqs = zip(*counts)
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(list(muscles), list(freqs), color=PALETTE[1])
    ax.set_xlabel("Frequency")
    ax.set_title(f"Top {top_n} Most Worked Muscles")
    ax.bar_label(bars, padding=3)
    ax.invert_yaxis()
    fig.tight_layout()
    return _save(fig, output_dir, "fig_muscles")


def figure_codebase_distribution(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Pie chart — exercise distribution by code_base."""
    counts = df["code_base"].value_counts()
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(
        counts.values,
        labels=counts.index.tolist(),
        autopct="%1.1f%%",
        colors=PALETTE[:len(counts)],
        startangle=140,
    )
    ax.set_title("Exercise Distribution by Type (code_base)")
    fig.tight_layout()
    return _save(fig, output_dir, "fig_codebase")


def figure_volume_progression(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Line chart — exercise volume (series × reps or exercise count) per session."""
    sessions = df["session"].unique().tolist()

    volumes = []
    for session in sessions:
        s_df = df[df["session"] == session]
        # Volume = sum(series * repetitions) if available, else exercise count
        if s_df["series"].notna().any() and s_df["repetitions"].notna().any():
            vol = (s_df["series"].fillna(1) * s_df["repetitions"].fillna(1)).sum()
        else:
            vol = len(s_df)
        volumes.append(vol)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(sessions, volumes, marker="o", color=PALETTE[0], linewidth=2, markersize=7)
    ax.fill_between(range(len(sessions)), volumes, alpha=0.15, color=PALETTE[0])
    ax.set_xticks(range(len(sessions)))
    ax.set_xticklabels(sessions, rotation=30, ha="right")
    ax.set_ylabel("Volume (series × reps or exercise count)")
    ax.set_title("Exercise Volume Progression Across Sessions")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()
    return _save(fig, output_dir, "fig_volume")


def figure_cohort_exercises_per_patient(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Bar chart — total exercises per patient across the cohort."""
    counts = df.groupby("patient_id").size().sort_values(ascending=True)
    if len(counts) < 2:
        return None, None

    fig, ax = plt.subplots(figsize=(8, max(4, len(counts) * 0.4)))
    bars = ax.barh(counts.index.tolist(), counts.values, color=PALETTE[0])
    ax.set_xlabel("Number of exercises")
    ax.set_title("Exercises per Patient (Cohort View)")
    ax.bar_label(bars, padding=3)
    fig.tight_layout()
    return _save(fig, output_dir, "fig_cohort_exercises_per_patient")


def figure_cohort_volume_boxplot(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Box plot — distribution of session volume across patients."""
    if df["patient_id"].nunique() < 2:
        return None, None

    # Compute volume per session per patient
    volumes_per_patient = {}
    for pid in df["patient_id"].unique():
        p_df = df[df["patient_id"] == pid]
        vols = []
        for _, group in p_df.groupby("session"):
            if group["series"].notna().any() and group["repetitions"].notna().any():
                v = (group["series"].fillna(1) * group["repetitions"].fillna(1)).sum()
            else:
                v = len(group)
            vols.append(v)
        volumes_per_patient[pid] = vols

    labels = list(volumes_per_patient.keys())
    data = list(volumes_per_patient.values())

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.8), 5))
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], PALETTE * (len(labels) // len(PALETTE) + 1)):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel("Volume per session")
    ax.set_title("Session Volume Distribution per Patient")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()
    return _save(fig, output_dir, "fig_cohort_volume_boxplot")


def figure_cohort_objectives_heatmap(df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Heatmap — objective distribution across patients (rows = patients, cols = objectives)."""
    if df["patient_id"].nunique() < 2:
        return None, None

    pivot = df.pivot_table(
        index="patient_id", columns="objective", aggfunc="size", fill_value=0
    )
    if pivot.empty:
        return None, None

    fig, ax = plt.subplots(figsize=(max(6, pivot.shape[1] * 1.2), max(4, pivot.shape[0] * 0.5)))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index)

    # Annotate cells
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, int(pivot.values[i, j]), ha="center", va="center",
                    color="white" if pivot.values[i, j] > pivot.values.max() / 2 else "black",
                    fontsize=9)

    ax.set_title("Objective Distribution per Patient")
    fig.colorbar(im, ax=ax, label="Exercise count")
    fig.tight_layout()
    return _save(fig, output_dir, "fig_cohort_objectives_heatmap")


def generate_all_figures(df: pd.DataFrame, output_dir: Path) -> dict[str, tuple[Path, Path]]:
    """
    Generates all report figures. Returns a dict:
        {figure_name: (svg_path, png_path)}

    Cohort figures are only added when df contains 2+ patients.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {}

    figures["objectives"] = figure_objective_distribution(df, output_dir)
    figures["muscles"] = figure_muscles_worked(df, output_dir)
    figures["codebase"] = figure_codebase_distribution(df, output_dir)
    figures["volume"] = figure_volume_progression(df, output_dir)

    # Cohort-level figures (only if 2+ patients)
    if "patient_id" in df.columns and df["patient_id"].nunique() >= 2:
        figures["cohort_exercises_per_patient"] = figure_cohort_exercises_per_patient(df, output_dir)
        figures["cohort_volume_boxplot"] = figure_cohort_volume_boxplot(df, output_dir)
        figures["cohort_objectives_heatmap"] = figure_cohort_objectives_heatmap(df, output_dir)

    return {k: v for k, v in figures.items() if v[0] is not None}
