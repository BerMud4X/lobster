"""
Figures specific to the statistical analysis section.
- Pre/post boxplot per test sub_category
- Spaghetti plot (individual patient trajectories pre→post)
- Forest plot of effect sizes
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PALETTE = ["#2D6A9F", "#4EABD1", "#6DC5A1", "#F4A261", "#E76F51"]


def _save(fig, output_dir: Path, name: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    svg = output_dir / f"{name}.svg"
    png = output_dir / f"{name}.png"
    fig.savefig(svg, format="svg", bbox_inches="tight")
    fig.savefig(png, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return svg, png


def figure_pre_post_boxplot(df: pd.DataFrame, test_name: str, output_dir: Path) -> tuple[Path, Path] | tuple[None, None]:
    """Boxplot pre vs post for one test (collapses sub_categories or shows them grouped)."""
    test_df = df[df["test_name"] == test_name].copy()
    test_df["value"] = pd.to_numeric(test_df["value"], errors="coerce")
    test_df = test_df.dropna(subset=["value", "timepoint"])
    test_df = test_df[test_df["timepoint"].isin(["pre", "post"])]

    if test_df.empty:
        return None, None

    sub_cats = [s for s in test_df["sub_category"].dropna().unique()] or [None]

    fig, ax = plt.subplots(figsize=(max(6, len(sub_cats) * 1.5), 5))

    positions = []
    labels = []
    data = []
    colors = []
    pos = 1

    for sc in sub_cats:
        if sc is None:
            sc_df = test_df
        else:
            sc_df = test_df[test_df["sub_category"] == sc]

        for tp, color in [("pre", PALETTE[0]), ("post", PALETTE[2])]:
            vals = sc_df[sc_df["timepoint"] == tp]["value"].tolist()
            if vals:
                data.append(vals)
                positions.append(pos)
                labels.append(f"{sc or 'all'}\n{tp.upper()}")
                colors.append(color)
            pos += 1
        pos += 0.5  # gap between sub_categories

    if not data:
        plt.close(fig)
        return None, None

    bp = ax.boxplot(data, positions=positions, patch_artist=True, widths=0.7)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Value")
    ax.set_title(f"{test_name} — Pre vs Post")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()

    safe = test_name.replace(" ", "_").replace("/", "_")
    return _save(fig, output_dir, f"stats_boxplot_{safe}")


def figure_individual_change(df: pd.DataFrame, test_name: str, output_dir: Path) -> tuple[Path, Path] | tuple[None, None]:
    """Spaghetti plot — individual patient trajectories pre→post."""
    test_df = df[(df["test_name"] == test_name)].copy()
    test_df["value"] = pd.to_numeric(test_df["value"], errors="coerce")
    test_df = test_df.dropna(subset=["value", "timepoint", "patient_id"])
    test_df = test_df[test_df["timepoint"].isin(["pre", "post"])]

    if test_df.empty:
        return None, None

    # Aggregate sub_categories: take mean per patient if multiple sub_categories
    agg = test_df.groupby(["patient_id", "timepoint"])["value"].mean().reset_index()
    pivot = agg.pivot(index="patient_id", columns="timepoint", values="value")

    # Need both pre and post for each line
    if "pre" not in pivot.columns or "post" not in pivot.columns:
        return None, None
    pivot = pivot.dropna(subset=["pre", "post"])
    if pivot.empty:
        return None, None

    fig, ax = plt.subplots(figsize=(6, 5))
    for pid, row in pivot.iterrows():
        ax.plot([0, 1], [row["pre"], row["post"]], marker="o", color=PALETTE[0], alpha=0.6, linewidth=1.5)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["PRE", "POST"])
    ax.set_ylabel("Value")
    ax.set_title(f"{test_name} — Individual change (n={len(pivot)})")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    fig.tight_layout()

    safe = test_name.replace(" ", "_").replace("/", "_")
    return _save(fig, output_dir, f"stats_change_{safe}")


def figure_effect_sizes(stats_results: dict, output_dir: Path) -> tuple[Path, Path] | tuple[None, None]:
    """Forest plot — effect sizes across all tests with paired comparisons."""
    rows = []
    for test in stats_results.get("tests", []):
        for sc in test["sub_categories"]:
            paired = sc.get("paired_pre_post")
            if paired and paired.get("effect_size") is not None:
                label = test["test_name"]
                if sc.get("sub_category"):
                    label += f" / {sc['sub_category']}"
                rows.append({
                    "label": label,
                    "effect": paired["effect_size"],
                    "test_used": paired["test"],
                    "p_value": paired.get("p_value"),
                })

    if not rows:
        return None, None

    rows.sort(key=lambda r: r["effect"])
    labels = [r["label"][:50] for r in rows]
    effects = [r["effect"] for r in rows]
    sig = [r["p_value"] is not None and r["p_value"] < 0.05 for r in rows]

    fig, ax = plt.subplots(figsize=(8, max(4, len(rows) * 0.4)))
    colors = [PALETTE[2] if s else PALETTE[3] for s in sig]
    bars = ax.barh(labels, effects, color=colors, alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Effect size (Cohen's d or r)")
    ax.set_title("Effect sizes across tests (green = p<0.05)")
    ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    fig.tight_layout()

    return _save(fig, output_dir, "stats_effect_sizes")


def generate_stats_figures(df: pd.DataFrame, stats_results: dict, output_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Generates all stats figures. Returns {key: (svg, png)} dict."""
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {}

    test_names = df["test_name"].dropna().unique() if not df.empty else []
    for test_name in test_names:
        bp = figure_pre_post_boxplot(df, test_name, output_dir)
        if bp[0] is not None:
            figures[f"boxplot_{test_name}"] = bp
        ic = figure_individual_change(df, test_name, output_dir)
        if ic[0] is not None:
            figures[f"change_{test_name}"] = ic

    es = figure_effect_sizes(stats_results, output_dir)
    if es[0] is not None:
        figures["effect_sizes"] = es

    return figures
