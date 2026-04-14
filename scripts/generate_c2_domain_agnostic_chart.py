"""
Fig 2 — C2 主図: Domain-Agnostic Transfer (ROS vs NT)
出力: docs/figures/fig3_c2_domain_agnostic.png

仕様: docs/paper/figure_table_list.md (Fig 2 セクション)
データ:
  ROS (P8) T3:      inv=0.9857  STRONG_SUCCESS
  NT  (P9) T3:      inv=0.8571  GEOMETRY_ONLY  ← artifact
  NT  (P10-A) T3+pf: inv=1.000  STRONG_SUCCESS
  B2 baseline: inv=0.9714
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ── データ ────────────────────────────────────────────────────────────────────
b2_inv = 0.9714

# グループ: ROS (P8) / NT (P9 / P10-A)
groups      = ["ROS (P8)", "NT (P9 / P10-A)"]
# 各グループの棒: [T3, T3+pf]
inv_data = {
    "ROS": {"T3": 0.9857, "T3+pf": None},   # ROS には T3+pf なし
    "NT":  {"T3": 0.8571, "T3+pf": 1.000},
}
outcomes = {
    "ROS_T3":     "STRONG_SUCCESS",
    "NT_T3":      "GEOMETRY_ONLY\n(artifact)",
    "NT_T3+pf":   "STRONG_SUCCESS",
}

# ── 色設定 ────────────────────────────────────────────────────────────────────
COLOR_T3    = "#4C72B0"   # 青: T3 (e_score_min)  — 薄色は alpha で
COLOR_T3PF  = "#2C6B2F"   # 緑: T3+pf (endpoint-aware)
COLOR_BASE  = "#C44E52"   # 赤: B2 baseline
COLOR_ART   = "#AAAAAA"   # グレー: artifact 棒

# ── レイアウト ────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4.5))

x     = np.array([0.0, 1.0])   # グループ位置
width = 0.28

# ROS: T3 のみ (1 棒)
ax.bar(x[0], inv_data["ROS"]["T3"], width, color=COLOR_T3, alpha=0.85,
       label="T3 (e_score_min ordering)")

# NT: T3 (artifact) — 薄色/ハッチ
ax.bar(x[1] - width / 2, inv_data["NT"]["T3"], width,
       color=COLOR_ART, alpha=0.75, hatch="//",
       label="T3 (GEOMETRY_ONLY artifact)")

# NT: T3+pf (success) — 濃色
ax.bar(x[1] + width / 2, inv_data["NT"]["T3+pf"], width,
       color=COLOR_T3PF, alpha=0.90,
       label="T3+pf (endpoint-aware pre-filter)")

# B2 baseline 点線
ax.axhline(b2_inv, color=COLOR_BASE, linestyle="--", linewidth=1.5,
           label=f"B2 baseline = {b2_inv}")

# ── アノテーション ────────────────────────────────────────────────────────────
# ROS T3: STRONG_SUCCESS
ax.text(x[0], inv_data["ROS"]["T3"] + 0.012,
        f"{inv_data['ROS']['T3']:.4f}\nSTRONG_SUCCESS",
        ha="center", va="bottom", fontsize=8, color="#1a5c1a")

# NT T3: GEOMETRY_ONLY
ax.text(x[1] - width / 2, inv_data["NT"]["T3"] - 0.012,
        f"{inv_data['NT']['T3']:.4f}\nGEOMETRY_ONLY\n(artifact)",
        ha="center", va="top", fontsize=7.5, color="#555555",
        style="italic")

# NT T3+pf: STRONG_SUCCESS
ax.text(x[1] + width / 2, inv_data["NT"]["T3+pf"] + 0.010,
        f"{inv_data['NT']['T3+pf']:.3f}\nSTRONG_SUCCESS",
        ha="center", va="bottom", fontsize=8, color="#1a5c1a")

# NT T3 → NT T3+pf 矢印 + 差分ラベル
diff_pp = (inv_data["NT"]["T3+pf"] - inv_data["NT"]["T3"]) * 100
ax.annotate(
    f"+{diff_pp:.1f}pp\n(selection artifact fixed)",
    xy=(x[1] + width / 2, inv_data["NT"]["T3+pf"] - 0.005),
    xytext=(x[1] + width / 2 + 0.22, 0.935),
    fontsize=7.5, color="#2C6B2F",
    arrowprops=dict(arrowstyle="->", color="#2C6B2F", lw=1.0),
    ha="left",
)

# ── 軸設定 ────────────────────────────────────────────────────────────────────
ax.set_ylabel("Investigability", fontsize=11)
ax.set_ylim(0.80, 1.055)
ax.set_xticks(x)
ax.set_xticklabels(groups, fontsize=11)
ax.set_xlim(-0.5, 1.65)

# ── タイトル・凡例 ────────────────────────────────────────────────────────────
ax.set_title(
    "Fig 2 — Domain-Agnostic Transfer: ROS vs NT Family\n"
    "(C2: selection strategy, not domain, determines investigability)",
    fontsize=11, pad=10,
)

handles = [
    mpatches.Patch(color=COLOR_T3, alpha=0.85,
                   label="T3 – e_score_min (ROS)"),
    mpatches.Patch(color=COLOR_ART, alpha=0.75, hatch="//",
                   label="T3 – e_score_min (NT, artifact)"),
    mpatches.Patch(color=COLOR_T3PF, alpha=0.90,
                   label="T3+pf – endpoint-aware (NT)"),
    plt.Line2D([0], [0], color=COLOR_BASE, linestyle="--", lw=1.5,
               label=f"B2 baseline ({b2_inv})"),
]
ax.legend(handles=handles, loc="lower left", fontsize=8)

plt.tight_layout()

# ── 保存 ─────────────────────────────────────────────────────────────────────
out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "figures")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "fig3_c2_domain_agnostic.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Saved: {out_path}")
