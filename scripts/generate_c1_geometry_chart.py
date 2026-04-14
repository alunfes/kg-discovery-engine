"""
Fig 1 — C1 主図: Bridge Geometry Breaks the Novelty Ceiling
出力: docs/figures/fig2_c1_geometry_breakthrough.png

仕様: docs/paper/figure_table_list.md (Fig 1 セクション)
データ:
  P6-A (T2): cdr_L3=0.333, inv=0.9429
  P7   (T3): cdr_L3=0.619, inv=0.9857
  P8   (T3): cdr_L3=0.740, inv=0.9857
  B2 baseline: inv=0.9714
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ── データ ────────────────────────────────────────────────────────────────────
conditions = ["P6-A\n(T2, no geom)", "P7\n(T3, ROS expand)", "P8\n(T3, ROS+ALL)"]
cdr_l3     = [0.333,  0.619,  0.740]
inv        = [0.9429, 0.9857, 0.9857]
b2_inv     = 0.9714

# ── 色設定 ────────────────────────────────────────────────────────────────────
COLOR_CDR  = "#4C72B0"   # 青: cdr_L3 棒
COLOR_INV  = "#DD8452"   # オレンジ: investigability 棒
COLOR_BASE = "#C44E52"   # 赤: B2 baseline ライン
COLOR_CEIL = "#888888"   # グレー: ceiling ゾーン

# ── レイアウト ────────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(7, 4.5))
ax2 = ax1.twinx()

x      = np.arange(len(conditions))
width  = 0.35
offset = width / 2

# 左軸: investigability 棒
bars_inv = ax1.bar(x - offset, inv, width, color=COLOR_INV, alpha=0.85,
                   label="Investigability (left)")

# 右軸: cdr_L3 棒
bars_cdr = ax2.bar(x + offset, cdr_l3, width, color=COLOR_CDR, alpha=0.75,
                   label="cdr_L3 (right)")

# B2 baseline 点線
ax1.axhline(b2_inv, color=COLOR_BASE, linestyle="--", linewidth=1.5,
            label=f"B2 baseline = {b2_inv}")

# ceiling ゾーン (inv < B2)
ax1.axhspan(0.85, b2_inv, color=COLOR_CEIL, alpha=0.08, zorder=0)

# ── アノテーション ────────────────────────────────────────────────────────────
# P6-A: ceiling
ax1.annotate(
    "ceiling\n(−0.028 vs B2)",
    xy=(x[0] - offset, inv[0]),
    xytext=(x[0] - offset, inv[0] - 0.018),
    ha="center", va="top", fontsize=8, color="#555555",
    arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.8),
)

# P7: STRONG_SUCCESS
ax1.annotate(
    "STRONG_SUCCESS\n(+0.014 vs B2)",
    xy=(x[1] - offset, inv[1]),
    xytext=(x[1] - offset, inv[1] + 0.013),
    ha="center", va="bottom", fontsize=8, color="#2a7a2a",
    arrowprops=dict(arrowstyle="->", color="#2a7a2a", lw=0.8),
)

# P8: STRONG_SUCCESS confirmed
ax1.annotate(
    "STRONG_SUCCESS\n(confirmed)",
    xy=(x[2] - offset, inv[2]),
    xytext=(x[2] - offset, inv[2] + 0.013),
    ha="center", va="bottom", fontsize=8, color="#2a7a2a",
    arrowprops=dict(arrowstyle="->", color="#2a7a2a", lw=0.8),
)

# cdr_L3 値ラベル
for xi, cdr in zip(x, cdr_l3):
    ax2.text(xi + offset, cdr + 0.015, f"{cdr:.3f}",
             ha="center", va="bottom", fontsize=8, color=COLOR_CDR)

# ── 軸設定 ────────────────────────────────────────────────────────────────────
ax1.set_ylabel("Investigability", fontsize=11)
ax2.set_ylabel("cdr_L3 (cross-domain ratio at L3)", fontsize=11)
ax1.set_ylim(0.85, 1.04)
ax2.set_ylim(0.0, 1.05)
ax1.set_xticks(x)
ax1.set_xticklabels(conditions, fontsize=10)
ax1.tick_params(axis="y", labelcolor=COLOR_INV)
ax2.tick_params(axis="y", labelcolor=COLOR_CDR)

# ── タイトル・凡例 ────────────────────────────────────────────────────────────
ax1.set_title(
    "Fig 1 — Bridge Geometry Breaks the Investigability Ceiling\n"
    "(C1: Enriched bridge geometry removes novelty ceiling)",
    fontsize=11, pad=10,
)

handles = [
    mpatches.Patch(color=COLOR_INV, alpha=0.85, label="Investigability (left axis)"),
    mpatches.Patch(color=COLOR_CDR, alpha=0.75, label="cdr_L3 (right axis)"),
    plt.Line2D([0], [0], color=COLOR_BASE, linestyle="--", lw=1.5,
               label=f"B2 baseline (inv={b2_inv})"),
]
ax1.legend(handles=handles, loc="lower right", fontsize=8)

plt.tight_layout()

# ── 保存 ─────────────────────────────────────────────────────────────────────
out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "figures")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "fig2_c1_geometry_breakthrough.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Saved: {out_path}")
