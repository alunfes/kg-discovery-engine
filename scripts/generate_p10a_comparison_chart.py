"""
P10-A Comparison Chart: B2 vs T3 vs T3+pf
Generates Figure 1 for the Final Synthesis document.
Shows investigability, novelty_retention, and long_path_share side-by-side.
"""

import json
import os
import sys


def load_comparison_data():
    """Load comparison table from run_043 artifact."""
    data_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "runs",
        "run_043_p10a_prefilter",
        "comparison_table.json",
    )
    with open(data_path) as f:
        return json.load(f)


def generate_chart(data: dict, output_path: str) -> None:
    """Generate bar chart comparing B2, T3, T3+pf across three metrics."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("ERROR: matplotlib not available. Install with: pip install matplotlib")
        sys.exit(1)

    selections = data["selections"]
    labels = [s["selection"] for s in selections]
    inv = [s["investigability"] for s in selections]
    nov = [s["novelty_retention"] for s in selections]
    lps = [s["long_path_share"] for s in selections]

    x = [0, 1, 2]
    width = 0.22
    offsets = [-width, 0, width]

    # Colors: B2=blue, T3=orange, T3+pf=green
    group_colors = ["#4C72B0", "#DD8452", "#55A868"]

    # Three metrics as separate bar groups
    metric_data = [inv, nov, lps]
    metric_labels = ["Investigability", "Novelty Retention", "Long-path Share"]
    metric_refs = [0.986, None, 0.30]  # success thresholds

    fig, axes = plt.subplots(1, 3, figsize=(13, 5.5), sharey=False)
    fig.suptitle(
        "P10-A: B2 vs T3 vs T3+pf — Selection Strategy Comparison\n"
        r"$\Delta$B2–T3 gap: −0.114 $\rightarrow$ +0.029 (inverted)",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )

    for ax_i, (ax, metric, metric_label, ref_line) in enumerate(
        zip(axes, metric_data, metric_labels, metric_refs)
    ):
        bars = ax.bar(
            x,
            metric,
            color=group_colors,
            width=0.55,
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )

        # Value labels on top of bars
        for bar, val in zip(bars, metric):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.015,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # Reference threshold line
        if ref_line is not None:
            ax.axhline(
                ref_line,
                color="#C44E52",
                linestyle="--",
                linewidth=1.5,
                alpha=0.8,
                label=f"threshold={ref_line}",
            )
            ax.legend(fontsize=8, loc="lower right")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_title(metric_label, fontsize=12, fontweight="bold", pad=8)
        ax.set_ylim(0, max(metric) * 1.20)
        ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Highlight T3+pf bar
        bars[2].set_edgecolor("#2d6a4f")
        bars[2].set_linewidth(2.5)

        # Investigability: annotate B2-T3 gap and B2-(T3+pf) gap
        if ax_i == 0:
            # Arrow: T3 → T3+pf with gap annotation
            ax.annotate(
                "",
                xy=(2, inv[2]),
                xytext=(1, inv[1]),
                arrowprops=dict(
                    arrowstyle="->",
                    color="#2d6a4f",
                    lw=2,
                ),
                zorder=5,
            )
            mid_y = (inv[1] + inv[2]) / 2
            ax.text(
                1.5,
                mid_y + 0.015,
                "+0.143",
                ha="center",
                color="#2d6a4f",
                fontsize=9,
                fontweight="bold",
            )
            ax.text(
                1.5,
                mid_y - 0.030,
                "gap inverted",
                ha="center",
                color="#2d6a4f",
                fontsize=8,
                style="italic",
            )

    # Legend
    legend_patches = [
        mpatches.Patch(color=c, label=l)
        for c, l in zip(group_colors, labels)
    ]
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=3,
        fontsize=10,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )

    # Footer annotation
    fig.text(
        0.5,
        -0.10,
        "Data: run_043 (P10-A) | N=70 per condition | KG: C_NT_ONLY (5 NT bridge nodes, cdr_L3=0.605)\n"
        "T3+pf = T3 buckets with endpoint-aware 2024-2025 investigability pre-filter",
        ha="center",
        fontsize=8,
        color="#555555",
    )

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Chart saved: {output_path}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output_path = os.path.join(repo_root, "docs", "figures", "fig1_p10a_comparison.png")

    data = load_comparison_data()
    generate_chart(data, output_path)


if __name__ == "__main__":
    main()
