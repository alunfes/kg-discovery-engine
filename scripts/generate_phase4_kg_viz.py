"""Generate Phase 4 KG visualization for paper/marketing assets.

Produces:
  - paper_assets/figures/phase4_full_kg.png        (1920x1080, dpi=200)
  - paper_assets/figures/phase4_full_kg_preview.png (960x540)
  - paper_assets/figures/phase4_kg_bio_only.png
  - paper_assets/figures/phase4_kg_chem_only.png
  - paper_assets/figures/phase4_kg_bridge_focused.png
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

from src.data.wikidata_phase4_loader import load_phase4_data  # noqa: E402
from src.kg.models import KnowledgeGraph  # noqa: E402
from src.kg.phase4_data import build_condition_d  # noqa: E402

SEED = 42
OUT_DIR = PROJECT_ROOT / "paper_assets" / "figures"

# Colours
COL_BIO = "#2196F3"      # steel blue
COL_CHEM = "#FF7043"     # deep orange
COL_BRIDGE = "#FFD700"   # gold
COL_BG = "#0F1117"       # dark background
COL_PANEL = "#1E2030"    # legend / stats panel


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def build_phase4_kg() -> KnowledgeGraph:
    """Load Phase 4 data and build Condition D (maximum merged KG)."""
    data = load_phase4_data()
    return build_condition_d(data)


def kg_to_networkx(kg: KnowledgeGraph) -> nx.DiGraph:
    """Convert KnowledgeGraph to networkx DiGraph with domain attributes."""
    G: nx.DiGraph = nx.DiGraph()
    for node in kg.nodes():
        G.add_node(node.id, label=node.label, domain=node.domain)
    for edge in kg.edges():
        G.add_edge(edge.source_id, edge.target_id, relation=edge.relation)
    return G


# ---------------------------------------------------------------------------
# Graph analysis
# ---------------------------------------------------------------------------

def find_bridge_nodes(G: nx.DiGraph) -> set[str]:
    """Return node IDs incident to at least one cross-domain edge."""
    bridge_ids: set[str] = set()
    for src, tgt in G.edges():
        if G.nodes[src]["domain"] != G.nodes[tgt]["domain"]:
            bridge_ids.add(src)
            bridge_ids.add(tgt)
    return bridge_ids


def select_label_nodes(G: nx.DiGraph, bridge_ids: set[str]) -> dict[str, str]:
    """Select top-degree nodes to label (bridge×8, bio×6, chem×6 max)."""
    def top_k(nodes: list[str], k: int) -> list[str]:
        return sorted(nodes, key=lambda n: G.degree(n), reverse=True)[:k]

    bridges = list(bridge_ids)
    bio_only = [n for n in G if G.nodes[n]["domain"] == "biology" and n not in bridge_ids]
    chem_only = [n for n in G if G.nodes[n]["domain"] == "chemistry" and n not in bridge_ids]

    labeled = set(top_k(bridges, 8)) | set(top_k(bio_only, 6)) | set(top_k(chem_only, 6))
    return {n: G.nodes[n]["label"] for n in labeled}


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _spring_sub(
    G: nx.DiGraph,
    node_ids: set[str],
    seed: int,
) -> dict[str, tuple[float, float]]:
    """Compute spring_layout for a subgraph of G."""
    sub = G.subgraph(list(node_ids))
    if not sub:
        return {}
    k = 2.0 / max(len(sub) ** 0.5, 1.0)
    return nx.spring_layout(sub, seed=seed, k=k)  # type: ignore[return-value]


def _rescale(
    sub_pos: dict[str, tuple[float, float]],
    x_range: tuple[float, float],
    y_range: tuple[float, float] = (-1.0, 1.0),
) -> dict[str, tuple[float, float]]:
    """Linearly rescale (x, y) positions into given ranges."""
    if not sub_pos:
        return {}
    xs = [p[0] for p in sub_pos.values()]
    ys = [p[1] for p in sub_pos.values()]
    x_span = (max(xs) - min(xs)) or 1.0
    y_span = (max(ys) - min(ys)) or 1.0
    return {
        nid: (
            x_range[0] + (x - min(xs)) / x_span * (x_range[1] - x_range[0]),
            y_range[0] + (y - min(ys)) / y_span * (y_range[1] - y_range[0]),
        )
        for nid, (x, y) in sub_pos.items()
    }


def compute_domain_layout(
    G: nx.DiGraph,
    bio_ids: set[str],
    chem_ids: set[str],
    bridge_ids: set[str],
    seed: int = SEED,
) -> dict[str, tuple[float, float]]:
    """Domain-separated layout: bio left, bridges centre, chem right."""
    bio_only = bio_ids - bridge_ids
    chem_only = chem_ids - bridge_ids
    pos: dict[str, tuple[float, float]] = {}
    pos.update(_rescale(_spring_sub(G, bio_only, seed), (-2.8, -0.8)))
    pos.update(_rescale(_spring_sub(G, chem_only, seed + 1), (0.8, 2.8)))
    pos.update(_rescale(_spring_sub(G, bridge_ids, seed + 2), (-0.5, 0.5), (-0.7, 0.7)))
    return pos


# ---------------------------------------------------------------------------
# Visual properties
# ---------------------------------------------------------------------------

def node_sizes(G: nx.DiGraph, bridge_ids: set[str]) -> list[float]:
    """Log-scaled degree-based sizes; bridge nodes are 2.5× larger."""
    return [
        20.0 * (1.0 + math.log1p(G.degree(n))) * (2.5 if n in bridge_ids else 1.0)
        for n in G.nodes()
    ]


def node_colors(G: nx.DiGraph, bridge_ids: set[str]) -> list[str]:
    """bio=blue, chem=orange, bridge=gold."""
    def _col(n: str) -> str:
        if n in bridge_ids:
            return COL_BRIDGE
        return COL_BIO if G.nodes[n]["domain"] == "biology" else COL_CHEM
    return [_col(n) for n in G.nodes()]


def split_edges(
    G: nx.DiGraph, bridge_ids: set[str]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split edges into (normal_edges, bridge_edges)."""
    normal, bridges = [], []
    for src, tgt in G.edges():
        (bridges if (src in bridge_ids or tgt in bridge_ids) else normal).append((src, tgt))
    return normal, bridges


# ---------------------------------------------------------------------------
# Stats / legend
# ---------------------------------------------------------------------------

def _stats_box(
    ax: plt.Axes,
    G: nx.DiGraph,
    bridge_ids: set[str],
    bridge_edges: list[tuple[str, str]],
) -> None:
    """Add bottom-right stats annotation to axes."""
    bio_n = sum(1 for n in G if G.nodes[n]["domain"] == "biology")
    chem_n = G.number_of_nodes() - bio_n
    txt = (
        f"Nodes : {G.number_of_nodes()}  (Bio {bio_n} | Chem {chem_n})\n"
        f"Edges : {G.number_of_edges()}  (Cross-domain {len(bridge_edges)})\n"
        f"Bridge nodes : {len(bridge_ids)}"
    )
    ax.text(
        0.985, 0.015, txt, transform=ax.transAxes,
        ha="right", va="bottom", fontsize=7.5, color="white",
        bbox=dict(boxstyle="round,pad=0.45", facecolor=COL_PANEL, alpha=0.85),
    )


def _legend(ax: plt.Axes, G: nx.DiGraph, bridge_ids: set[str]) -> None:
    """Add domain/bridge legend to axes."""
    bio_n = sum(1 for n in G if G.nodes[n]["domain"] == "biology")
    chem_n = G.number_of_nodes() - bio_n
    handles = [
        mpatches.Patch(color=COL_BIO, label=f"Biology  ({bio_n} nodes)"),
        mpatches.Patch(color=COL_CHEM, label=f"Chemistry  ({chem_n} nodes)"),
        mpatches.Patch(color=COL_BRIDGE, label=f"Bridge / Alignment  ({len(bridge_ids)} nodes)"),
    ]
    ax.legend(
        handles=handles, loc="upper left", fontsize=8.5,
        facecolor=COL_PANEL, labelcolor="white", framealpha=0.85, edgecolor="gray",
    )


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_kg(
    G: nx.DiGraph,
    pos: dict[str, tuple[float, float]],
    bridge_ids: set[str],
    out_path: Path,
    title: str,
    figsize: tuple[float, float] = (19.2, 10.8),
    dpi: int = 200,
) -> None:
    """Draw KG and save to out_path.

    Args:
        G: networkx DiGraph with domain/label attributes.
        pos: Node position dict.
        bridge_ids: Set of bridge node IDs.
        out_path: Destination PNG path.
        title: Figure title string.
        figsize: Matplotlib figure size in inches.
        dpi: Output resolution.
    """
    fig, ax = plt.subplots(figsize=figsize, facecolor=COL_BG)
    ax.set_facecolor(COL_BG)

    normal_edges, bridge_edges = split_edges(G, bridge_ids)

    # Edges — normal (faint grey) then bridge-adjacent (gold)
    nx.draw_networkx_edges(
        G, pos, edgelist=normal_edges, ax=ax,
        edge_color="#888888", alpha=0.12, arrows=False, width=0.35,
    )
    nx.draw_networkx_edges(
        G, pos, edgelist=bridge_edges, ax=ax,
        edge_color=COL_BRIDGE, alpha=0.50, arrows=True,
        width=1.1, arrowsize=5, arrowstyle="-|>",
    )

    # Nodes
    nx.draw_networkx_nodes(
        G, pos, nodelist=list(G.nodes()), ax=ax,
        node_color=node_colors(G, bridge_ids),
        node_size=node_sizes(G, bridge_ids),
        alpha=0.88,
    )

    # Labels (top-degree only)
    nx.draw_networkx_labels(
        G, pos, labels=select_label_nodes(G, bridge_ids), ax=ax,
        font_size=4.8, font_color="white", font_weight="bold",
    )

    _legend(ax, G, bridge_ids)
    _stats_box(ax, G, bridge_ids, bridge_edges)

    ax.axis("off")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=8)
    plt.tight_layout(pad=0.5)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path} ({out_path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def save_preview(src: Path, dst: Path, width: int = 960, height: int = 540) -> None:
    """Save a downscaled preview using sips (macOS) or PIL fallback.

    Args:
        src: Source high-res PNG.
        dst: Destination preview PNG.
        width: Target width in pixels.
        height: Target height in pixels.
    """
    try:
        from PIL import Image
        img = Image.open(src)
        img.thumbnail((width, height), Image.LANCZOS)
        img.save(dst)
    except ImportError:
        subprocess.run(["sips", "-Z", str(max(width, height)), str(src), "--out", str(dst)], check=True)
    print(f"  Preview: {dst}")


# ---------------------------------------------------------------------------
# Variant helpers
# ---------------------------------------------------------------------------

def subgraph_bio_only(
    G: nx.DiGraph,
    bio_ids: set[str],
) -> tuple[nx.DiGraph, dict[str, tuple[float, float]]]:
    """Return (subgraph, layout) for bio-only nodes."""
    sub = G.subgraph(list(bio_ids)).copy()
    pos = _rescale(_spring_sub(G, bio_ids, SEED), (-2.5, 2.5))
    return sub, pos


def subgraph_chem_only(
    G: nx.DiGraph,
    chem_ids: set[str],
) -> tuple[nx.DiGraph, dict[str, tuple[float, float]]]:
    """Return (subgraph, layout) for chem-only nodes."""
    sub = G.subgraph(list(chem_ids)).copy()
    pos = _rescale(_spring_sub(G, chem_ids, SEED + 3), (-2.5, 2.5))
    return sub, pos


def subgraph_bridge_focused(
    G: nx.DiGraph,
    bridge_ids: set[str],
) -> tuple[nx.DiGraph, dict[str, tuple[float, float]]]:
    """Return (subgraph, layout) for bridge nodes + 1-hop neighbours."""
    neighbours: set[str] = set(bridge_ids)
    for n in bridge_ids:
        neighbours.update(G.predecessors(n))
        neighbours.update(G.successors(n))
    sub = G.subgraph(list(neighbours)).copy()
    pos = compute_domain_layout(
        sub,
        {n for n in sub if sub.nodes[n]["domain"] == "biology"},
        {n for n in sub if sub.nodes[n]["domain"] == "chemistry"},
        bridge_ids & set(sub.nodes()),
        seed=SEED + 4,
    )
    return sub, pos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate all Phase 4 KG visualizations."""
    np.random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Phase 4 KG (Condition D — maximum merged)...")
    kg = build_phase4_kg()
    G = kg_to_networkx(kg)

    bio_ids: set[str] = {n for n, d in G.nodes(data=True) if d["domain"] == "biology"}
    chem_ids: set[str] = {n for n, d in G.nodes(data=True) if d["domain"] == "chemistry"}
    bridge_ids = find_bridge_nodes(G)

    print(f"  Nodes  : {G.number_of_nodes()} (bio={len(bio_ids)}, chem={len(chem_ids)})")
    print(f"  Edges  : {G.number_of_edges()}")
    print(f"  Bridges: {len(bridge_ids)} nodes")

    # ── Figure 1: full KG ────────────────────────────────────────────────
    print("\n[1/4] Full KG (domain-separated layout)...")
    pos_full = compute_domain_layout(G, bio_ids, chem_ids, bridge_ids, seed=SEED)
    main_out = OUT_DIR / "phase4_full_kg.png"
    draw_kg(
        G, pos_full, bridge_ids, main_out,
        title=(
            f"Phase 4 Knowledge Graph — Cross-Domain KG Discovery "
            f"({G.number_of_nodes()} nodes · {G.number_of_edges()} edges · {len(bridge_ids)} bridge nodes)"
        ),
    )
    save_preview(main_out, OUT_DIR / "phase4_full_kg_preview.png")

    # ── Figure 2: bio-only ───────────────────────────────────────────────
    print("\n[2/4] Bio-only subgraph...")
    G_bio, pos_bio = subgraph_bio_only(G, bio_ids)
    draw_kg(
        G_bio, pos_bio, bridge_ids & set(G_bio.nodes()),
        OUT_DIR / "phase4_kg_bio_only.png",
        title="Phase 4 KG — Biology Domain Only (293 nodes)",
        dpi=150,
    )

    # ── Figure 3: chem-only ──────────────────────────────────────────────
    print("\n[3/4] Chem-only subgraph...")
    G_chem, pos_chem = subgraph_chem_only(G, chem_ids)
    draw_kg(
        G_chem, pos_chem, bridge_ids & set(G_chem.nodes()),
        OUT_DIR / "phase4_kg_chem_only.png",
        title="Phase 4 KG — Chemistry Domain Only (243 nodes)",
        dpi=150,
    )

    # ── Figure 4: bridge-focused ─────────────────────────────────────────
    print("\n[4/4] Bridge-focused subgraph (bridge + 1-hop)...")
    G_bridge, pos_bridge = subgraph_bridge_focused(G, bridge_ids)
    draw_kg(
        G_bridge, pos_bridge, bridge_ids & set(G_bridge.nodes()),
        OUT_DIR / "phase4_kg_bridge_focused.png",
        title="Phase 4 KG — Bridge Zone (alignment candidates + 1-hop neighbours)",
        dpi=150,
    )

    print("\nAll figures generated successfully.")
    print(f"Output directory: {OUT_DIR}")


if __name__ == "__main__":
    main()
