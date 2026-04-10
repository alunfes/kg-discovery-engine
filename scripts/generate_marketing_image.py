"""
generate_marketing_image.py — Cross-Domain KG Discovery marketing visual.

Visualises two domain-specific KGs (Biology / Chemistry) merging to produce
novel cross-domain hypotheses.  Based on real candidate data from runs 012/013.

Run:
    python scripts/generate_marketing_image.py

Output:
    paper_assets/marketing/cross_domain_discovery.png   (1920×1080 @ 150 dpi)
    paper_assets/marketing/cross_domain_discovery_preview.png (960×540 @ 75 dpi)
"""

import os
import math
import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Arc
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patheffects as pe

# ── Reproducibility ────────────────────────────────────────────────────────────
random.seed(42)
np.random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
OUT_DIR    = os.path.join(REPO_ROOT, "paper_assets", "marketing")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Design tokens ──────────────────────────────────────────────────────────────
BG_COLOR    = "#0B0F1A"     # near-black background

# Biology KG (blue family)
BIO_NODE    = "#2B6CB0"
BIO_NODE_LT = "#63B3ED"
BIO_EDGE    = "#90CDF4"
BIO_GLOW    = "#4299E1"

# Chemistry KG (amber/orange family)
CHEM_NODE    = "#C05621"
CHEM_NODE_LT = "#F6AD55"
CHEM_EDGE    = "#FBD38D"
CHEM_GLOW    = "#ED8936"

# Bridge / Fusion
BRIDGE_COLOR = "#F6E05E"    # gold
FUSION_GLOW  = "#FEFCBF"
PATH_COLOR   = "#68D391"    # emerald for highlighted path
PATH_GLOW    = "#9AE6B4"

# Text
TITLE_COLOR  = "#FEFCE8"
LABEL_COLOR  = "#E2E8F0"
SUB_COLOR    = "#A0AEC0"
TAG_COLOR    = "#F6E05E"

# ── Canvas ─────────────────────────────────────────────────────────────────────
FIG_W, FIG_H = 12.8, 7.2   # inches → 1920×1080 @ 150 dpi
DPI_HIGH     = 150
DPI_PREVIEW  = 75

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_facecolor(BG_COLOR)
fig.patch.set_facecolor(BG_COLOR)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

# ══════════════════════════════════════════════════════════════════════════════
# Helper utilities
# ══════════════════════════════════════════════════════════════════════════════

def draw_glow_circle(ax, cx, cy, r, color, alpha_max=0.18, layers=6):
    """Draw a soft glowing halo around a node centre."""
    for i in range(layers, 0, -1):
        a = alpha_max * (i / layers) ** 1.5
        circ = plt.Circle((cx, cy), r * (1 + 0.6 * i / layers),
                           color=color, alpha=a, zorder=2)
        ax.add_patch(circ)


def draw_node(ax, cx, cy, label, color_fill, color_text="#FFFFFF",
              radius=0.030, fontsize=7.5, glow_color=None, zorder=10):
    """Draw a rounded node with glow and label."""
    gc = glow_color or color_fill
    draw_glow_circle(ax, cx, cy, radius, gc, alpha_max=0.22, layers=5)
    circ = plt.Circle((cx, cy), radius, color=color_fill,
                       ec="white", linewidth=0.6, zorder=zorder, alpha=0.95)
    ax.add_patch(circ)
    ax.text(cx, cy, label, ha="center", va="center",
            fontsize=fontsize, color=color_text, fontweight="bold",
            zorder=zorder + 1,
            path_effects=[pe.withStroke(linewidth=1.2, foreground=BG_COLOR)])


def draw_edge(ax, x0, y0, x1, y1, label="", color="#AAAAAA",
              lw=1.0, alpha=0.7, label_size=5.5, zorder=5,
              curved=False, rad=0.15):
    """Draw a directed edge with optional label."""
    style = f"arc3,rad={rad}" if curved else "arc3,rad=0"
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>",
                                color=color, lw=lw, alpha=alpha,
                                connectionstyle=style),
                zorder=zorder)
    if label:
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        if curved:
            # offset perpendicular to edge
            dx, dy = x1 - x0, y1 - y0
            nx, ny = -dy, dx
            norm = math.hypot(nx, ny) or 1
            mx += nx / norm * rad * 0.5
            my += ny / norm * rad * 0.5
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=label_size, color=color, alpha=0.9,
                style="italic",
                path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)],
                zorder=zorder + 1)


def draw_highlighted_edge(ax, x0, y0, x1, y1, label="",
                           color=PATH_COLOR, glow=PATH_GLOW,
                           lw=2.5, zorder=15, curved=False, rad=0.1):
    """Draw a thick glowing edge for the highlighted path."""
    style = f"arc3,rad={rad}" if curved else "arc3,rad=0"
    # Glow layer
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>",
                                color=glow, lw=lw + 3, alpha=0.25,
                                connectionstyle=style),
                zorder=zorder - 1)
    # Main arrow
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>",
                                color=color, lw=lw, alpha=0.95,
                                connectionstyle=style),
                zorder=zorder)
    if label:
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2
        ax.text(mx, my + 0.012, label, ha="center", va="center",
                fontsize=6.0, color=PATH_COLOR, fontweight="bold",
                path_effects=[pe.withStroke(linewidth=1.8, foreground=BG_COLOR)],
                zorder=zorder + 1)


# ══════════════════════════════════════════════════════════════════════════════
# Background gradient panels
# ══════════════════════════════════════════════════════════════════════════════

def draw_panel_gradient(ax, x0, x1, y0, y1, color, alpha=0.06):
    """Subtle tinted rectangular panel."""
    rect = mpatches.FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0.01",
        facecolor=color, edgecolor=color, alpha=alpha, zorder=0,
        linewidth=0.5)
    ax.add_patch(rect)


draw_panel_gradient(ax, 0.02, 0.36, 0.06, 0.96, BIO_NODE, alpha=0.08)
draw_panel_gradient(ax, 0.64, 0.98, 0.06, 0.96, CHEM_NODE, alpha=0.08)

# ══════════════════════════════════════════════════════════════════════════════
# Fusion glow in the centre
# ══════════════════════════════════════════════════════════════════════════════

cx_fuse, cy_fuse = 0.50, 0.55
for r, alpha in [(0.20, 0.04), (0.15, 0.07), (0.10, 0.10), (0.06, 0.14)]:
    circ = plt.Circle((cx_fuse, cy_fuse), r,
                       color=BRIDGE_COLOR, alpha=alpha, zorder=1)
    ax.add_patch(circ)

# ══════════════════════════════════════════════════════════════════════════════
# Biology KG (left panel)
# Based on Candidate A-1: g_VHL→VHL→HIF1A→LDHA→NADH→r_Oxidation
# ══════════════════════════════════════════════════════════════════════════════

# Node positions (x, y)
bio_nodes = {
    "g_VHL":  (0.10, 0.74),
    "VHL":    (0.19, 0.62),
    "HIF1A":  (0.10, 0.50),
    "mTOR":   (0.26, 0.50),
    "LDHA":   (0.19, 0.38),
    "NADH":   (0.11, 0.26),
    "ATP":    (0.27, 0.28),
}

bio_edges = [
    ("g_VHL", "VHL",   "encodes"),
    ("VHL",   "HIF1A", "inhibits"),
    ("VHL",   "mTOR",  "inhibits"),
    ("HIF1A", "LDHA",  "activates"),
    ("mTOR",  "LDHA",  "activates"),
    ("LDHA",  "NADH",  "requires_cofactor"),
    ("LDHA",  "ATP",   "produces"),
]

for n, (x, y) in bio_nodes.items():
    is_bridge = n in ("NADH",)
    fc = BRIDGE_COLOR if is_bridge else BIO_NODE
    gc = BRIDGE_COLOR if is_bridge else BIO_GLOW
    r  = 0.033 if is_bridge else 0.028
    draw_node(ax, x, y, n, fc, glow_color=gc, radius=r, fontsize=7.2)

for src, dst, lbl in bio_edges:
    x0, y0 = bio_nodes[src]
    x1, y1 = bio_nodes[dst]
    draw_edge(ax, x0, y0, x1, y1, label=lbl,
              color=BIO_EDGE, lw=1.0, alpha=0.65, curved=True, rad=0.12)

# Panel label
ax.text(0.19, 0.90, "Biology KG", ha="center", va="center",
        fontsize=11, color=BIO_NODE_LT, fontweight="bold",
        path_effects=[pe.withStroke(linewidth=2, foreground=BG_COLOR)])
ax.text(0.19, 0.85, "cancer signalling · metabolism",
        ha="center", va="center",
        fontsize=7.5, color=SUB_COLOR,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Chemistry KG (right panel)
# Based on Subset B: COX→AA→PGE2 / Catechol / natural products
# ══════════════════════════════════════════════════════════════════════════════

chem_nodes = {
    "PTGS2":       (0.90, 0.74),
    "m_AA":        (0.81, 0.62),
    "Catechol":    (0.73, 0.50),
    "m_PGE2":      (0.90, 0.50),
    "Phenolic":    (0.81, 0.38),
    "r_Oxidation": (0.73, 0.26),
    "Methylation": (0.89, 0.28),
}

chem_edges = [
    ("PTGS2",       "m_AA",        "catalyzes"),
    ("m_AA",        "Catechol",    "undergoes"),
    ("m_AA",        "m_PGE2",      "is_precursor_of"),
    ("m_PGE2",      "Phenolic",    "relates_to"),
    ("Catechol",    "r_Oxidation", "undergoes"),
    ("Phenolic",    "Methylation", "undergoes"),
    ("Catechol",    "Phenolic",    "subclass_of"),
]

for n, (x, y) in chem_nodes.items():
    is_bridge = n in ("m_AA", "r_Oxidation")
    fc = BRIDGE_COLOR if is_bridge else CHEM_NODE
    gc = BRIDGE_COLOR if is_bridge else CHEM_GLOW
    r  = 0.033 if is_bridge else 0.028
    draw_node(ax, x, y, n, fc, glow_color=gc, radius=r, fontsize=7.2)

for src, dst, lbl in chem_edges:
    x0, y0 = chem_nodes[src]
    x1, y1 = chem_nodes[dst]
    draw_edge(ax, x0, y0, x1, y1, label=lbl,
              color=CHEM_EDGE, lw=1.0, alpha=0.65, curved=True, rad=0.12)

# Panel label
ax.text(0.81, 0.90, "Chemistry KG", ha="center", va="center",
        fontsize=11, color=CHEM_NODE_LT, fontweight="bold",
        path_effects=[pe.withStroke(linewidth=2, foreground=BG_COLOR)])
ax.text(0.81, 0.85, "eicosanoids · natural products",
        ha="center", va="center",
        fontsize=7.5, color=SUB_COLOR,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Centre fusion arrows
# ══════════════════════════════════════════════════════════════════════════════

# Left KG → centre
draw_edge(ax, 0.33, 0.58, 0.42, 0.56,
          color=BIO_NODE_LT, lw=1.8, alpha=0.8, curved=False)
draw_edge(ax, 0.33, 0.50, 0.42, 0.52,
          color=BIO_NODE_LT, lw=1.8, alpha=0.8, curved=False)

# Right KG → centre
draw_edge(ax, 0.67, 0.58, 0.58, 0.56,
          color=CHEM_NODE_LT, lw=1.8, alpha=0.8, curved=False)
draw_edge(ax, 0.67, 0.50, 0.58, 0.52,
          color=CHEM_NODE_LT, lw=1.8, alpha=0.8, curved=False)

# Central "+" symbol
ax.text(0.50, 0.56, "+", ha="center", va="center",
        fontsize=28, color=BRIDGE_COLOR, fontweight="bold", alpha=0.9,
        path_effects=[pe.withStroke(linewidth=3, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Highlighted cross-domain discovery path (bottom strip)
# Candidate A-1: VHL → inhibits → HIF1A → activates → LDHA → NADH → Oxidation
# ══════════════════════════════════════════════════════════════════════════════

# Separator line
ax.plot([0.05, 0.95], [0.18, 0.18], color="#4A5568", lw=0.6, alpha=0.5, zorder=3)

path_y   = 0.11
path_nodes = ["VHL", "HIF1A", "LDHA", "NADH", "r_Oxidation"]
path_rels  = ["inhibits", "activates", "requires_cofactor", "undergoes"]
n_nodes    = len(path_nodes)
x_start    = 0.12
x_end      = 0.88
xs = [x_start + i * (x_end - x_start) / (n_nodes - 1) for i in range(n_nodes)]

# Node backgrounds
path_node_colors = [BIO_NODE, BIO_NODE, BIO_NODE, BRIDGE_COLOR, CHEM_NODE]

for i, (label, xp) in enumerate(zip(path_nodes, xs)):
    draw_node(ax, xp, path_y, label,
              color_fill=path_node_colors[i],
              glow_color=BRIDGE_COLOR if label in ("NADH", "r_Oxidation") else path_node_colors[i],
              radius=0.030, fontsize=7.5, zorder=14)

for i, rel in enumerate(path_rels):
    draw_highlighted_edge(ax, xs[i] + 0.031, path_y,
                          xs[i + 1] - 0.031, path_y,
                          label=rel, zorder=15)

# Domain labels under path
ax.text(0.28, 0.045, "← Biology domain", ha="center", va="center",
        fontsize=7.5, color=BIO_NODE_LT, alpha=0.85,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])
ax.text(0.82, 0.045, "Chemistry domain →", ha="center", va="center",
        fontsize=7.5, color=CHEM_NODE_LT, alpha=0.85,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])
ax.text(0.55, 0.045, "cross-domain bridge ⚡", ha="center", va="center",
        fontsize=7.5, color=TAG_COLOR, alpha=0.9,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])

# Strip label
ax.text(0.50, 0.165, "Discovered mechanistic hypothesis  (Candidate A-1, 5-hop)",
        ha="center", va="center", fontsize=7.5, color=PATH_COLOR, fontstyle="italic",
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Centre result label: unified KG emerges from fusion
# ══════════════════════════════════════════════════════════════════════════════

ax.text(0.50, 0.42, "Unified KG with\nNovel Cross-Domain Paths",
        ha="center", va="center", fontsize=9.5, color=FUSION_GLOW,
        fontweight="bold", linespacing=1.4,
        path_effects=[pe.withStroke(linewidth=2.5, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Title
# ══════════════════════════════════════════════════════════════════════════════

ax.text(0.50, 0.960,
        "Cross-Domain Knowledge Graph Discovery",
        ha="center", va="center",
        fontsize=17, color=TITLE_COLOR, fontweight="bold",
        path_effects=[pe.withStroke(linewidth=3, foreground=BG_COLOR)])

ax.text(0.50, 0.925,
        "Automated hypothesis generation by composing multi-domain KGs with alignment operators",
        ha="center", va="center",
        fontsize=8.5, color=SUB_COLOR,
        path_effects=[pe.withStroke(linewidth=1.5, foreground=BG_COLOR)])

# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════

plt.tight_layout(pad=0)

out_high    = os.path.join(OUT_DIR, "cross_domain_discovery.png")
out_preview = os.path.join(OUT_DIR, "cross_domain_discovery_preview.png")

fig.savefig(out_high,    dpi=DPI_HIGH,    bbox_inches="tight",
            facecolor=BG_COLOR, edgecolor="none")
fig.savefig(out_preview, dpi=DPI_PREVIEW, bbox_inches="tight",
            facecolor=BG_COLOR, edgecolor="none")

plt.close(fig)

print(f"Saved: {out_high}")
print(f"Saved: {out_preview}")
