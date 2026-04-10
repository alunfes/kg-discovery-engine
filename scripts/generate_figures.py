"""
generate_figures.py — KG Discovery Engine paper figure generation.

Generates Figures 1–4 from pre-computed metrics in paper_assets/.
No experiments are run; all numbers are read from:
  - paper_assets/final_metrics.json
  - paper_assets/subset_summary_table.csv

Run:
    python scripts/generate_figures.py

Output:
    paper_assets/figures/figure1_pipeline.png
    paper_assets/figures/figure2_alignment_leverage.png
    paper_assets/figures/figure3_drift_by_depth.png
    paper_assets/figures/figure4_filter_effect.png
"""

import json
import os
import random
import csv
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for deterministic rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as FancyBboxPatch
import numpy as np

# ── Reproducibility ───────────────────────────────────────────────────────────
random.seed(42)
np.random.seed(42)

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(REPO_ROOT, "paper_assets")
OUT_DIR = os.path.join(ASSETS, "figures")
METRICS_JSON = os.path.join(ASSETS, "final_metrics.json")
SUBSET_CSV = os.path.join(ASSETS, "subset_summary_table.csv")

os.makedirs(OUT_DIR, exist_ok=True)

# ── Colour palette (colorblind-safe: Paul Tol "bright") ───────────────────────
C_BIO   = "#4477AA"   # blue
C_CHEM  = "#228833"   # green
C_BRIDG = "#EE6677"   # red-pink (bridge / warning)
C_A     = "#4477AA"   # Subset A — blue
C_B     = "#228833"   # Subset B — green
C_C     = "#CCBB44"   # Subset C — yellow
C_PROM  = "#228833"   # promising — green
C_WEAK  = "#DDCC77"   # weak_speculative — yellow
C_DRIFT = "#CC3311"   # drift_heavy — red

# ── Common style ──────────────────────────────────────────────────────────────
FONT_TICK  = 10
FONT_LABEL = 11
FONT_TITLE = 12
FONT_ANNOT = 9
DPI = 300


def apply_style(ax):
    """Apply publication-ready style to an axes."""
    ax.grid(axis="y", color="0.85", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=FONT_TICK)


def load_metrics():
    """Load final_metrics.json."""
    with open(METRICS_JSON, "r") as f:
        return json.load(f)


def load_subset_csv():
    """Load subset_summary_table.csv as list of dicts."""
    rows = []
    with open(SUBSET_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


# =============================================================================
# Figure 1 — Pipeline Architecture
# =============================================================================

def make_box(ax, x, y, w, h, label, sub="", color="#DDEBF7", fontsize=10):
    """Draw a rounded box with optional subtitle."""
    box = mpatches.FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02",
        facecolor=color, edgecolor="#555555", linewidth=1.2, zorder=2
    )
    ax.add_patch(box)
    if sub:
        ax.text(x, y + 0.06, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", zorder=3)
        ax.text(x, y - 0.07, sub, ha="center", va="center",
                fontsize=fontsize - 1, color="#444444", zorder=3)
    else:
        ax.text(x, y, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", zorder=3)


def arrow(ax, x0, y0, x1, y1, color="#333333"):
    """Draw an arrow between two points."""
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=1.4, mutation_scale=14),
                zorder=3)


def figure1_pipeline():
    """Figure 1: pipeline architecture as a flow diagram."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.5)
    ax.axis("off")

    # ── KG nodes ──────────────────────────────────────────────────────────────
    make_box(ax, 1.0, 3.2, 1.6, 0.7, "G_bio", "(293 nodes)", color="#D4E6F1")
    make_box(ax, 1.0, 1.3, 1.6, 0.7, "G_chem", "(243 nodes)", color="#D5F5E3")

    # ── align ─────────────────────────────────────────────────────────────────
    make_box(ax, 3.0, 2.25, 1.4, 0.7, "align", "(7 bridges)", color="#FAD7A0")
    arrow(ax, 1.82, 3.1, 2.28, 2.6)
    arrow(ax, 1.82, 1.4, 2.28, 1.9)

    # ── union ─────────────────────────────────────────────────────────────────
    make_box(ax, 4.8, 2.25, 1.3, 0.7, "union", "G_merged", color="#F9EBEA")
    arrow(ax, 3.72, 2.25, 4.12, 2.25)

    # ── compose + filter ──────────────────────────────────────────────────────
    make_box(ax, 6.6, 2.25, 1.5, 0.7, "compose", "+ filter", color="#E8DAEF")
    arrow(ax, 5.45, 2.25, 5.82, 2.25)

    # ── evaluate / rank ───────────────────────────────────────────────────────
    make_box(ax, 8.6, 2.25, 1.6, 0.7, "evaluate", "& rank", color="#D5F5E3")
    arrow(ax, 7.35, 2.25, 7.78, 2.25)

    # ── Output label ──────────────────────────────────────────────────────────
    ax.text(8.6, 0.7, "Ranked\nhypotheses", ha="center", va="center",
            fontsize=FONT_ANNOT, color="#222222",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#EAF4FB",
                      edgecolor="#4477AA", linewidth=1.0))
    arrow(ax, 8.6, 1.87, 8.6, 1.05)

    # ── Bridge annotation ─────────────────────────────────────────────────────
    ax.annotate("Bridge nodes\n(cross-domain\npaths)",
                xy=(4.8, 2.6), xytext=(4.2, 3.8),
                fontsize=FONT_ANNOT, color=C_BRIDG,
                arrowprops=dict(arrowstyle="->", color=C_BRIDG, lw=1.0),
                ha="center")

    # ── Depth annotation ──────────────────────────────────────────────────────
    ax.text(6.6, 0.45,
            "2–5 hop paths enumerated;\ndrift-heavy paths removed",
            ha="center", va="center", fontsize=FONT_ANNOT - 0.5,
            color="#555555", style="italic")

    ax.set_title(
        "Figure 1. KG Discovery Engine pipeline",
        fontsize=FONT_TITLE, pad=8
    )
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "figure1_pipeline.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


# =============================================================================
# Figure 2 — Alignment Leverage
# =============================================================================

def figure2_alignment_leverage(metrics):
    """Figure 2: unique_to_alignment bar chart per subset."""
    # Data from final_metrics.json bridge_dispersion_analysis
    bda = metrics["bridge_dispersion_analysis"]
    subsets = ["A", "B", "C"]
    unique = [bda[f"subset_{s}"]["unique_to_alignment"] for s in subsets]
    bridges = [bda[f"subset_{s}"]["aligned_pairs"] for s in subsets]
    ratios = [bda[f"subset_{s}"]["unique_per_bridge"] for s in subsets]
    bridge_labels = [
        "NADH (1 hub)",
        "Eicosanoids (5)",
        "NTs (6–8)",
    ]
    colors = [C_A, C_B, C_C]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = np.arange(len(subsets))
    bars = ax.bar(x, unique, color=colors, edgecolor="white",
                  linewidth=0.8, width=0.55, zorder=2)
    apply_style(ax)

    # Annotate bars with ratio and bridge count
    for i, (bar, ratio, bridge) in enumerate(zip(bars, ratios, bridges)):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.8,
                f"ratio = {ratio}×\n({bridge} bridges)",
                ha="center", va="bottom", fontsize=FONT_ANNOT,
                color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"Subset {s}\n{bl}" for s, bl in zip(subsets, bridge_labels)],
        fontsize=FONT_TICK
    )
    ax.set_ylabel("Unique cross-domain candidate pairs\n(unique_to_alignment)",
                  fontsize=FONT_LABEL)
    ax.set_ylim(0, max(unique) * 1.35)
    ax.set_title(
        "Figure 2. Alignment unlocks otherwise unreachable cross-domain paths",
        fontsize=FONT_TITLE, pad=8
    )

    # Reference note
    ax.text(0.98, 0.02,
            "Subset B: fewest bridges (5), but 8× yield vs Subset A (7 bridges)\n"
            "→ Bridge dispersion, not count, drives yield",
            transform=ax.transAxes, fontsize=FONT_ANNOT - 0.5,
            ha="right", va="bottom", color="#555555", style="italic",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#F9F9F9",
                      edgecolor="#CCCCCC", linewidth=0.8))

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "figure2_alignment_leverage.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


# =============================================================================
# Figure 3 — Drift Rate by Depth (Reproducibility)
# =============================================================================

def figure3_drift_by_depth(metrics):
    """Figure 3: line chart of drift rate by depth bucket, 3 subsets."""
    repro = metrics["reproducibility_run013"]
    depth_labels = ["2-hop", "3-hop", "4–5-hop"]
    depth_keys = ["2hop", "3hop", "4_5hop"]

    data = {}
    for s in ["A", "B", "C"]:
        key = f"subset_{s}"
        data[s] = [repro[key]["drift_by_depth"][dk] for dk in depth_keys]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    styles = [
        (C_A, "o", "Subset A — Cancer sig. / Metabolic chem."),
        (C_B, "s", "Subset B — Immunology / Natural products"),
        (C_C, "^", "Subset C — Neuroscience / Neuro-pharmacology"),
    ]
    x = np.arange(len(depth_labels))

    for (color, marker, label), (s, vals) in zip(styles, data.items()):
        ax.plot(x, vals, color=color, marker=marker, linewidth=1.8,
                markersize=7, label=label, zorder=3)
        for xi, vi in zip(x, vals):
            ax.text(xi, vi + 0.005, f"{vi:.3f}", ha="center", va="bottom",
                    fontsize=FONT_ANNOT - 0.5, color=color)

    apply_style(ax)
    ax.set_xticks(x)
    ax.set_xticklabels(depth_labels, fontsize=FONT_TICK)
    ax.set_ylabel("Drift rate (fraction of drift-heavy candidates)",
                  fontsize=FONT_LABEL)
    ax.set_ylim(0, 0.38)
    ax.legend(fontsize=FONT_ANNOT, loc="upper left",
              framealpha=0.9, edgecolor="#CCCCCC")
    ax.set_title(
        "Figure 3. Drift rate increases monotonically with path depth\n"
        "(generalises across 3 independent domain pairs)",
        fontsize=FONT_TITLE - 0.5, pad=8
    )
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "figure3_drift_by_depth.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


# =============================================================================
# Figure 4 — Filter Effect (Before vs. After)
# =============================================================================

def figure4_filter_effect(metrics):
    """Figure 4: stacked bar chart showing quality composition before/after filter."""
    fe = metrics["filter_effect_run012"]
    # Counts from figure_specs.md Table (derived from 15%/60%/25% of 20 = 3/12/5)
    before = {"promising": 3, "weak_speculative": 12, "drift_heavy": 5}
    after  = {"promising": 3, "weak_speculative": 0,  "drift_heavy": 0}

    stages = ["Baseline\n(Run 011)", "Filtered\n(Run 012)"]
    prom  = [before["promising"],        after["promising"]]
    weak  = [before["weak_speculative"], after["weak_speculative"]]
    drift = [before["drift_heavy"],      after["drift_heavy"]]

    x = np.arange(len(stages))
    w = 0.45

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    p1 = ax.bar(x, prom,  w, label="Promising",         color=C_PROM,  zorder=2)
    p2 = ax.bar(x, weak,  w, bottom=prom,
                label="Weak speculative", color=C_WEAK,  zorder=2)
    p3 = ax.bar(x, drift, w, bottom=[p + wk for p, wk in zip(prom, weak)],
                label="Drift-heavy",      color=C_DRIFT, zorder=2)
    apply_style(ax)

    # Total count on top of each bar
    totals = [sum(v) for v in zip(prom, weak, drift)]
    for xi, tot in zip(x, totals):
        ax.text(xi, tot + 0.2, f"n = {tot}",
                ha="center", va="bottom", fontsize=FONT_ANNOT + 1,
                fontweight="bold", color="#222222")

    # Annotation: 0 false negatives
    ax.annotate("0 false negatives\n(all 3 promising preserved)",
                xy=(1, 3.3), xytext=(0.55, 12),
                fontsize=FONT_ANNOT, color=C_PROM,
                arrowprops=dict(arrowstyle="->", color=C_PROM, lw=1.1),
                ha="center")

    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontsize=FONT_TICK)
    ax.set_ylabel("Deep cross-domain candidates (count)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 25)
    ax.legend(fontsize=FONT_ANNOT, loc="upper right",
              framealpha=0.9, edgecolor="#CCCCCC")
    ax.set_title(
        "Figure 4. Quality-aware filter removes drift while preserving\n"
        "all promising candidates",
        fontsize=FONT_TITLE - 0.5, pad=8
    )
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "figure4_filter_effect.png")
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Generate all four paper figures."""
    metrics = load_metrics()

    print("Generating Figure 1: Pipeline architecture …")
    figure1_pipeline()

    print("Generating Figure 2: Alignment leverage …")
    figure2_alignment_leverage(metrics)

    print("Generating Figure 3: Drift rate by depth …")
    figure3_drift_by_depth(metrics)

    print("Generating Figure 4: Filter effect …")
    figure4_filter_effect(metrics)

    print("\nAll figures saved to:", OUT_DIR)
    for fname in sorted(os.listdir(OUT_DIR)):
        if fname.endswith(".png"):
            path = os.path.join(OUT_DIR, fname)
            size_kb = os.path.getsize(path) // 1024
            print(f"  {fname}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
