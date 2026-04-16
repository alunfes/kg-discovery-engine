"""Marketing visualizations for Phase 4 KG (5 styles).

Outputs:
  paper_assets/figures/kg_circular_bundling.png
  paper_assets/figures/kg_chord_diagram.html
  paper_assets/figures/kg_3d_force.html
  paper_assets/figures/kg_adjacency_matrix.png
  paper_assets/figures/kg_hierarchical_bundling.html
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import networkx as nx

from src.data.wikidata_phase4_loader import load_phase4_data
from src.kg.phase4_data import build_condition_d

SEED = 42
OUT_DIR = PROJECT_ROOT / "paper_assets" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COL_BIO   = "#4FC3F7"   # light blue
COL_CHEM  = "#FF7043"   # deep orange
COL_CROSS = "#FFD700"   # gold for cross-domain
COL_BG    = "#0A0E1A"   # near-black
DOMAIN_COLORS = {"biology": COL_BIO, "chemistry": COL_CHEM}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_graph() -> nx.DiGraph:
    """Load Phase 4 Condition D as a networkx DiGraph."""
    data = load_phase4_data()
    kg = build_condition_d(data)
    G: nx.DiGraph = nx.DiGraph()
    for node in kg.nodes():
        G.add_node(node.id, label=node.label, domain=node.domain)
    for edge in kg.edges():
        G.add_edge(edge.source_id, edge.target_id, relation=edge.relation)
    return G


# ===========================================================================
# 1. Circular Layout + Bézier Edge Bundling
# ===========================================================================

def draw_circular_bundling(G: nx.DiGraph, out: Path) -> None:
    """Circular layout with Bézier curve edges, cross-domain edges in gold."""
    np.random.seed(SEED)

    bio_nodes   = [n for n, d in G.nodes(data=True) if d["domain"] == "biology"]
    chem_nodes  = [n for n, d in G.nodes(data=True) if d["domain"] == "chemistry"]

    # Arrange: bio occupies top-half arc, chem bottom-half
    def arc_positions(nodes: list, start_angle: float, end_angle: float) -> dict:
        pos = {}
        n = len(nodes)
        for i, node in enumerate(nodes):
            t = i / max(n - 1, 1)
            angle = start_angle + t * (end_angle - start_angle)
            pos[node] = (math.cos(angle), math.sin(angle))
        return pos

    pos: dict = {}
    pos.update(arc_positions(bio_nodes,  math.pi * 0.05,  math.pi * 0.95))
    pos.update(arc_positions(chem_nodes, math.pi * 1.05,  math.pi * 1.95))

    fig, ax = plt.subplots(figsize=(12, 12), dpi=200, facecolor=COL_BG)
    ax.set_facecolor(COL_BG)
    ax.set_aspect("equal")
    ax.axis("off")

    # Draw Bézier edges
    cross_edges   = [(u, v) for u, v in G.edges() if G.nodes[u]["domain"] != G.nodes[v]["domain"]]
    intra_edges   = [(u, v) for u, v in G.edges() if G.nodes[u]["domain"] == G.nodes[v]["domain"]]

    def draw_bezier_edge(ax, p0, p3, color, alpha, lw, ctrl_scale=0.45):
        """Cubic Bézier from p0 to p3 with control points toward center."""
        cx, cy = 0.0, 0.0
        # control points pulled toward center
        p1 = (p0[0] * ctrl_scale + cx * (1 - ctrl_scale),
               p0[1] * ctrl_scale + cy * (1 - ctrl_scale))
        p2 = (p3[0] * ctrl_scale + cx * (1 - ctrl_scale),
               p3[1] * ctrl_scale + cy * (1 - ctrl_scale))
        t = np.linspace(0, 1, 60)
        x = ((1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0]
             + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0])
        y = ((1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1]
             + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1])
        ax.plot(x, y, color=color, alpha=alpha, lw=lw, solid_capstyle="round")

    # Intra-domain edges (faint)
    for u, v in intra_edges:
        if u in pos and v in pos:
            col = DOMAIN_COLORS.get(G.nodes[u]["domain"], "#888")
            draw_bezier_edge(ax, pos[u], pos[v], col, alpha=0.06, lw=0.4)

    # Cross-domain edges (bright gold)
    for u, v in cross_edges:
        if u in pos and v in pos:
            draw_bezier_edge(ax, pos[u], pos[v], COL_CROSS, alpha=0.75, lw=1.2, ctrl_scale=0.3)

    # Nodes
    deg = dict(G.degree())
    max_deg = max(deg.values()) or 1
    for node in G.nodes():
        if node not in pos:
            continue
        x, y = pos[node]
        domain = G.nodes[node]["domain"]
        col = DOMAIN_COLORS[domain]
        size = 25 + 90 * (deg[node] / max_deg) ** 0.5
        ax.scatter(x, y, s=size, c=col, zorder=5, alpha=0.92,
                   edgecolors="white", linewidths=0.3)

    # Domain arc labels
    ax.text(0, 1.12, "BIOLOGY", ha="center", va="center",
            color=COL_BIO, fontsize=15, fontweight="bold",
            path_effects=[pe.withStroke(linewidth=3, foreground=COL_BG)])
    ax.text(0, -1.12, "CHEMISTRY", ha="center", va="center",
            color=COL_CHEM, fontsize=15, fontweight="bold",
            path_effects=[pe.withStroke(linewidth=3, foreground=COL_BG)])

    # Stats
    n_bio  = len(bio_nodes)
    n_chem = len(chem_nodes)
    n_cross = len(cross_edges)
    ax.text(0.01, 0.01,
            f"Nodes: {G.number_of_nodes()}  (Bio {n_bio} · Chem {n_chem})\n"
            f"Edges: {G.number_of_edges()}  (Cross-domain: {n_cross})",
            transform=ax.transAxes, color="white", fontsize=8, va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1E2030", alpha=0.85))

    handles = [
        mpatches.Patch(color=COL_BIO,   label=f"Biology ({n_bio})"),
        mpatches.Patch(color=COL_CHEM,  label=f"Chemistry ({n_chem})"),
        mpatches.Patch(color=COL_CROSS, label=f"Cross-domain edges ({n_cross})"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8,
              facecolor="#1E2030", labelcolor="white", framealpha=0.9,
              edgecolor="#444")

    ax.set_title("KG Discovery Engine — Circular Edge Bundling\n"
                 "Bio–Chem Knowledge Graph (Phase 4)",
                 color="white", fontsize=14, fontweight="bold", pad=12)

    plt.tight_layout(pad=0.8)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out}")


# ===========================================================================
# 2. Chord Diagram (d3.js HTML)
# ===========================================================================

def build_chord_html(G: nx.DiGraph, out: Path) -> None:
    """D3.js chord diagram showing domain-level connection volumes."""
    domains = sorted({d["domain"] for _, d in G.nodes(data=True)})
    dom_idx = {d: i for i, d in enumerate(domains)}

    # Build flow matrix (directed: from_domain -> to_domain edge count)
    n = len(domains)
    matrix = [[0] * n for _ in range(n)]
    for u, v in G.edges():
        du = G.nodes[u]["domain"]
        dv = G.nodes[v]["domain"]
        matrix[dom_idx[du]][dom_idx[dv]] += 1

    # Also collect relation type breakdown per domain pair
    relation_counts: dict = defaultdict(lambda: defaultdict(int))
    for u, v, d in G.edges(data=True):
        du = G.nodes[u]["domain"]
        dv = G.nodes[v]["domain"]
        rel = d.get("relation", "related")
        relation_counts[f"{du}→{dv}"][rel] += 1

    matrix_json = json.dumps(matrix)
    domains_json = json.dumps(domains)
    colors_json = json.dumps({
        "biology":   COL_BIO,
        "chemistry": COL_CHEM,
    })
    rel_json = json.dumps({k: dict(v) for k, v in relation_counts.items()})

    node_counts = {d: sum(1 for _, nd in G.nodes(data=True) if nd["domain"] == d) for d in domains}
    node_counts_json = json.dumps(node_counts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>KG Chord Diagram — Phase 4</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{COL_BG}; color:#fff; font-family:'Segoe UI',sans-serif; display:flex; flex-direction:column; align-items:center; min-height:100vh; padding:20px; }}
  h1 {{ font-size:1.4rem; margin-bottom:4px; color:#e0e0ff; letter-spacing:1px; }}
  p.sub {{ font-size:0.85rem; color:#888; margin-bottom:20px; }}
  #chart {{ position:relative; }}
  svg {{ overflow:visible; }}
  .tooltip {{ position:absolute; background:rgba(20,24,40,0.95); border:1px solid #444; border-radius:8px; padding:10px 14px; font-size:0.82rem; pointer-events:none; display:none; min-width:180px; }}
  .tooltip h3 {{ font-size:0.9rem; margin-bottom:6px; color:#FFD700; }}
  .tooltip .row {{ display:flex; justify-content:space-between; gap:20px; color:#ccc; }}
  .legend {{ display:flex; gap:24px; margin-top:18px; }}
  .legend-item {{ display:flex; align-items:center; gap:8px; font-size:0.85rem; color:#ccc; }}
  .legend-dot {{ width:14px; height:14px; border-radius:50%; }}
  .stats {{ margin-top:12px; font-size:0.78rem; color:#666; text-align:center; }}
</style>
</head>
<body>
<h1>KG Discovery Engine — Cross-Domain Knowledge Graph</h1>
<p class="sub">Phase 4 · Bio+Chem Integration · Chord Diagram (hover to explore)</p>
<div id="chart"><div class="tooltip" id="tip"></div></div>
<div class="legend" id="legend"></div>
<div class="stats" id="stats"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const matrix     = {matrix_json};
const domains    = {domains_json};
const colorMap   = {colors_json};
const relData    = {rel_json};
const nodeCounts = {node_counts_json};

const W = Math.min(window.innerWidth - 40, 700);
const H = W;
const outerR = W / 2 - 60;
const innerR = outerR - 30;

const svg = d3.select("#chart").append("svg")
  .attr("width", W).attr("height", H)
  .append("g")
  .attr("transform", `translate(${{W/2}},${{H/2}})`);

const chord = d3.chord().padAngle(0.05).sortSubgroups(d3.descending);
const chords = chord(matrix);

const arc = d3.arc().innerRadius(innerR).outerRadius(outerR);
const ribbon = d3.ribbon().radius(innerR - 2);

const color = d => colorMap[domains[d.index]] || "#888";

// Groups (arcs)
const group = svg.append("g").selectAll("g").data(chords.groups).join("g");

group.append("path")
  .attr("fill", d => color(d))
  .attr("stroke", d => d3.rgb(color(d)).darker())
  .attr("d", arc)
  .attr("opacity", 0.85)
  .on("mouseover", function(event, d) {{
    const dom = domains[d.index];
    const key1 = `${{dom}}→${{dom}}`;
    const crossKeys = domains.filter((_,i) => i !== d.index).map(od => `${{dom}}→${{od}}`);
    let html = `<h3>${{dom.toUpperCase()}}</h3>`;
    html += `<div class="row"><span>Nodes</span><span>${{nodeCounts[dom]}}</span></div>`;
    html += `<div class="row"><span>Internal edges</span><span>${{matrix[d.index][d.index]}}</span></div>`;
    crossKeys.forEach(k => {{
      if (relData[k]) {{
        html += `<hr style="border-color:#333;margin:6px 0"/>`;
        html += `<div class="row" style="color:#FFD700"><span>${{k}}</span><span></span></div>`;
        Object.entries(relData[k]).slice(0,5).forEach(([rel, cnt]) => {{
          html += `<div class="row"><span>&nbsp;${{rel}}</span><span>${{cnt}}</span></div>`;
        }});
      }}
    }});
    d3.select("#tip").html(html).style("display","block");
    d3.selectAll(".chord-path").attr("opacity", cd =>
      cd.source.index === d.index || cd.target.index === d.index ? 0.85 : 0.05);
  }})
  .on("mousemove", function(event) {{
    const [mx, my] = d3.pointer(event, document.body);
    d3.select("#tip").style("left", (mx+16)+"px").style("top", (my-10)+"px");
  }})
  .on("mouseout", function() {{
    d3.select("#tip").style("display","none");
    d3.selectAll(".chord-path").attr("opacity", 0.65);
  }});

// Arc labels
group.append("text")
  .each(d => {{ d.angle = (d.startAngle + d.endAngle) / 2; }})
  .attr("dy", "0.35em")
  .attr("transform", d => `
    rotate(${{(d.angle * 180 / Math.PI - 90)}})
    translate(${{outerR + 12}})
    ${{d.angle > Math.PI ? "rotate(180)" : ""}}
  `)
  .attr("text-anchor", d => d.angle > Math.PI ? "end" : null)
  .text(d => `${{domains[d.index].toUpperCase()}} (${{nodeCounts[domains[d.index]]}} nodes)`)
  .attr("fill", d => colorMap[domains[d.index]])
  .attr("font-size", "13px")
  .attr("font-weight", "bold");

// Chords (ribbons)
svg.append("g").attr("fill-opacity", 0.65)
  .selectAll("path").data(chords).join("path")
  .classed("chord-path", true)
  .attr("d", ribbon)
  .attr("fill", d => color(d.target))
  .attr("stroke", d => d3.rgb(color(d.target)).darker())
  .attr("opacity", 0.65)
  .on("mouseover", function(event, d) {{
    const src = domains[d.source.index];
    const tgt = domains[d.target.index];
    const key = `${{src}}→${{tgt}}`;
    let html = `<h3>${{src}} → ${{tgt}}</h3>`;
    html += `<div class="row"><span>Connections</span><span>${{matrix[d.source.index][d.target.index]}}</span></div>`;
    if (relData[key]) {{
      html += `<hr style="border-color:#333;margin:6px 0"/>`;
      Object.entries(relData[key]).slice(0,8).forEach(([rel, cnt]) => {{
        html += `<div class="row"><span>${{rel}}</span><span>${{cnt}}</span></div>`;
      }});
    }}
    d3.select("#tip").html(html).style("display","block");
    d3.select(this).attr("opacity", 0.9);
  }})
  .on("mousemove", function(event) {{
    const [mx, my] = d3.pointer(event, document.body);
    d3.select("#tip").style("left", (mx+16)+"px").style("top", (my-10)+"px");
  }})
  .on("mouseout", function() {{
    d3.select("#tip").style("display","none");
    d3.select(this).attr("opacity", 0.65);
  }});

// Legend
const legend = d3.select("#legend");
domains.forEach(d => {{
  const item = legend.append("div").attr("class","legend-item");
  item.append("div").attr("class","legend-dot").style("background", colorMap[d]);
  item.append("span").text(`${{d.charAt(0).toUpperCase()+d.slice(1)}} — ${{nodeCounts[d]}} nodes`);
}});

// Stats
const totalEdges = matrix.flat().reduce((a,b)=>a+b,0);
const crossEdges = matrix[0][1] + matrix[1][0];
d3.select("#stats").text(
  `Total: ${{domains.reduce((a,d)=>a+nodeCounts[d],0)}} nodes · ${{totalEdges}} edges · ${{crossEdges}} cross-domain connections`
);
</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"  Saved: {out}")


# ===========================================================================
# 3. 3D Force-Directed Graph (Plotly HTML)
# ===========================================================================

def build_3d_force_html(G: nx.DiGraph, out: Path) -> None:
    """3D force-directed graph using Plotly."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "plotly"])
        import plotly.graph_objects as go

    np.random.seed(SEED)

    # 3D spring layout via networkx (2D) + random z, then iterate
    # Use spectral layout for 2D base, add z dimension
    try:
        pos2d = nx.spring_layout(G, seed=SEED, k=0.3, iterations=50)
    except Exception:
        pos2d = nx.random_layout(G, seed=SEED)

    bridge_ids = {u for u, v in G.edges() if G.nodes[u]["domain"] != G.nodes[v]["domain"]} | \
                 {v for u, v in G.edges() if G.nodes[u]["domain"] != G.nodes[v]["domain"]}

    rng = np.random.default_rng(SEED)
    node_list = list(G.nodes())
    node_idx  = {n: i for i, n in enumerate(node_list)}

    xs = [pos2d[n][0] for n in node_list]
    ys = [pos2d[n][1] for n in node_list]
    zs = [rng.uniform(-0.5, 0.5) for _ in node_list]

    # Refine z by domain: bio positive, chem negative
    for i, n in enumerate(node_list):
        domain = G.nodes[n]["domain"]
        if domain == "biology":
            zs[i] = abs(zs[i]) * 0.8 + 0.1
        else:
            zs[i] = -abs(zs[i]) * 0.8 - 0.1

    degrees = dict(G.degree())
    max_deg = max(degrees.values()) or 1

    def node_color(n):
        if n in bridge_ids:
            return COL_CROSS
        return DOMAIN_COLORS[G.nodes[n]["domain"]]

    node_colors_list = [node_color(n) for n in node_list]
    node_sizes       = [4 + 14 * (degrees[n] / max_deg) ** 0.5 for n in node_list]
    node_labels      = [G.nodes[n]["label"] for n in node_list]
    node_domains     = [G.nodes[n]["domain"] for n in node_list]

    # Edge traces (batched by type for performance)
    edge_x_intra, edge_y_intra, edge_z_intra = [], [], []
    edge_x_cross, edge_y_cross, edge_z_cross = [], [], []

    for u, v in G.edges():
        xi, yi, zi = xs[node_idx[u]], ys[node_idx[u]], zs[node_idx[u]]
        xj, yj, zj = xs[node_idx[v]], ys[node_idx[v]], zs[node_idx[v]]
        is_cross = G.nodes[u]["domain"] != G.nodes[v]["domain"]
        if is_cross:
            edge_x_cross += [xi, xj, None]
            edge_y_cross += [yi, yj, None]
            edge_z_cross += [zi, zj, None]
        else:
            edge_x_intra += [xi, xj, None]
            edge_y_intra += [yi, yj, None]
            edge_z_intra += [zi, zj, None]

    traces = [
        go.Scatter3d(
            x=edge_x_intra, y=edge_y_intra, z=edge_z_intra,
            mode="lines",
            line=dict(color="rgba(150,150,150,0.12)", width=0.8),
            hoverinfo="none", name="Intra-domain edges",
        ),
        go.Scatter3d(
            x=edge_x_cross, y=edge_y_cross, z=edge_z_cross,
            mode="lines",
            line=dict(color="rgba(255,215,0,0.7)", width=2.0),
            hoverinfo="none", name="Cross-domain edges",
        ),
        go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="markers",
            marker=dict(
                size=node_sizes,
                color=node_colors_list,
                opacity=0.88,
                line=dict(color="rgba(255,255,255,0.2)", width=0.5),
            ),
            text=[
                f"<b>{node_labels[i]}</b><br>"
                f"Domain: {node_domains[i]}<br>"
                f"Degree: {degrees[n]}"
                f"{'<br><b>★ Bridge node</b>' if n in bridge_ids else ''}"
                for i, n in enumerate(node_list)
            ],
            hovertemplate="%{text}<extra></extra>",
            name="Nodes",
        ),
    ]

    layout = go.Layout(
        title=dict(
            text="KG Discovery Engine — 3D Force-Directed Graph<br>"
                 "<sup>Phase 4 Bio+Chem Knowledge Graph · Rotate & zoom to explore</sup>",
            font=dict(color="white", size=16),
            x=0.5,
        ),
        paper_bgcolor=COL_BG,
        plot_bgcolor=COL_BG,
        scene=dict(
            bgcolor=COL_BG,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            zaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                       title="", tickvals=[-1, 0, 1],
                       ticktext=["CHEMISTRY", "", "BIOLOGY"]),
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.8)),
        ),
        legend=dict(
            bgcolor="rgba(20,24,40,0.85)", bordercolor="#444", borderwidth=1,
            font=dict(color="white", size=11),
            x=0.01, y=0.99,
        ),
        margin=dict(l=0, r=0, t=80, b=0),
        width=1000, height=800,
    )

    fig = go.Figure(data=traces, layout=layout)
    fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
    print(f"  Saved: {out}")


# ===========================================================================
# 4. Adjacency Matrix Heatmap
# ===========================================================================

def draw_adjacency_matrix(G: nx.DiGraph, out: Path) -> None:
    """Adjacency matrix heatmap sorted by domain."""
    # Sort nodes: biology first, then chemistry, each sorted by degree desc
    bio_nodes  = sorted(
        [n for n, d in G.nodes(data=True) if d["domain"] == "biology"],
        key=lambda n: -G.degree(n)
    )
    chem_nodes = sorted(
        [n for n, d in G.nodes(data=True) if d["domain"] == "chemistry"],
        key=lambda n: -G.degree(n)
    )
    node_order = bio_nodes + chem_nodes
    idx = {n: i for i, n in enumerate(node_order)}
    N = len(node_order)

    # Build adjacency matrix (add transpose for undirected visual)
    mat = np.zeros((N, N), dtype=np.float32)
    for u, v in G.edges():
        if u in idx and v in idx:
            mat[idx[u], idx[v]] = 1.0
            mat[idx[v], idx[u]] = 0.6  # lighter for reverse

    # Log-scale for visibility
    mat_vis = np.log1p(mat * 5)

    fig, ax = plt.subplots(figsize=(14, 14), dpi=200, facecolor=COL_BG)
    ax.set_facecolor(COL_BG)

    im = ax.imshow(mat_vis, cmap="inferno", aspect="auto", interpolation="nearest",
                   vmin=0, vmax=mat_vis.max())

    # Domain boundary line
    nb = len(bio_nodes)
    ax.axhline(nb - 0.5, color=COL_CROSS, lw=1.5, alpha=0.8)
    ax.axvline(nb - 0.5, color=COL_CROSS, lw=1.5, alpha=0.8)

    # Domain block labels
    for axis in [ax.xaxis, ax.yaxis]:
        axis.set_tick_params(which="both", length=0)

    ax.set_xticks([nb / 2, nb + len(chem_nodes) / 2])
    ax.set_xticklabels(["BIOLOGY", "CHEMISTRY"], color="white", fontsize=12, fontweight="bold")
    ax.set_yticks([nb / 2, nb + len(chem_nodes) / 2])
    ax.set_yticklabels(["BIOLOGY", "CHEMISTRY"], color="white", fontsize=12, fontweight="bold",
                       rotation=90, va="center")

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.ax.yaxis.set_tick_params(color="white")
    cbar.outline.set_edgecolor("white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=8)
    cbar.set_label("Connection strength (log)", color="white", fontsize=9)

    ax.set_title(
        f"KG Discovery Engine — Adjacency Matrix Heatmap\n"
        f"Phase 4 Bio+Chem KG · {N} nodes × {N} nodes · {G.number_of_edges()} edges",
        color="white", fontsize=13, fontweight="bold", pad=12,
    )

    # Block highlight rectangles
    rect_bio  = mpatches.FancyBboxPatch((-0.5, -0.5), nb, nb,
                                         linewidth=1.5, edgecolor=COL_BIO,
                                         facecolor="none", boxstyle="square,pad=0")
    rect_chem = mpatches.FancyBboxPatch((nb - 0.5, nb - 0.5), len(chem_nodes), len(chem_nodes),
                                         linewidth=1.5, edgecolor=COL_CHEM,
                                         facecolor="none", boxstyle="square,pad=0")
    ax.add_patch(rect_bio)
    ax.add_patch(rect_chem)

    # Stats annotation
    n_cross = sum(1 for u, v in G.edges() if G.nodes[u]["domain"] != G.nodes[v]["domain"])
    ax.text(0.985, 0.015,
            f"Bio: {len(bio_nodes)} nodes  |  Chem: {len(chem_nodes)} nodes\n"
            f"Total edges: {G.number_of_edges()}  |  Cross-domain: {n_cross}",
            transform=ax.transAxes, ha="right", va="bottom", color="white", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1E2030", alpha=0.88))

    plt.tight_layout(pad=0.6)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out}")


# ===========================================================================
# 5. Hierarchical Edge Bundling (d3.js HTML)
# ===========================================================================

def build_hierarchical_bundling_html(G: nx.DiGraph, out: Path) -> None:
    """D3.js hierarchical edge bundling: domain → node."""
    # Build hierarchy: root → domain → node
    bio_nodes   = [n for n, d in G.nodes(data=True) if d["domain"] == "biology"]
    chem_nodes  = [n for n, d in G.nodes(data=True) if d["domain"] == "chemistry"]

    # Select top-N nodes per domain to keep it readable
    deg = dict(G.degree())
    TOP = 80
    bio_top   = sorted(bio_nodes,  key=lambda n: -deg[n])[:TOP]
    chem_top  = sorted(chem_nodes, key=lambda n: -deg[n])[:TOP]
    selected  = set(bio_top + chem_top)
    sel_idx   = {n: i for i, n in enumerate(bio_top + chem_top)}

    # Build d3 hierarchy data
    def make_leaf(node_id):
        d = G.nodes[node_id]
        return {"name": node_id, "label": d["label"], "domain": d["domain"]}

    hierarchy = {
        "name": "root",
        "children": [
            {"name": "biology",   "children": [make_leaf(n) for n in bio_top]},
            {"name": "chemistry", "children": [make_leaf(n) for n in chem_top]},
        ]
    }

    # Links: edges where both ends are in selected set
    links = []
    for u, v in G.edges():
        if u in selected and v in selected:
            links.append({"source": u, "target": v,
                          "cross": G.nodes[u]["domain"] != G.nodes[v]["domain"]})

    hierarchy_json = json.dumps(hierarchy)
    links_json     = json.dumps(links)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>KG Hierarchical Edge Bundling — Phase 4</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{COL_BG}; display:flex; flex-direction:column; align-items:center; padding:20px; font-family:'Segoe UI',sans-serif; }}
  h1 {{ color:#e0e0ff; font-size:1.4rem; margin-bottom:4px; letter-spacing:1px; }}
  p.sub {{ color:#888; font-size:0.82rem; margin-bottom:16px; }}
  svg text {{ font-size:9px; }}
  .node circle {{ fill-opacity:0.92; }}
  .link {{ fill:none; stroke-opacity:0.55; }}
  .link-cross {{ stroke:{COL_CROSS}; stroke-opacity:0.8; stroke-width:1.5px; }}
  .link-bio   {{ stroke:{COL_BIO};   stroke-width:0.7px; }}
  .link-chem  {{ stroke:{COL_CHEM};  stroke-width:0.7px; }}
  .label-bio  {{ fill:{COL_BIO};  }}
  .label-chem {{ fill:{COL_CHEM}; }}
  .legend {{ display:flex; gap:20px; margin-top:14px; }}
  .legend-item {{ display:flex; align-items:center; gap:8px; font-size:0.82rem; color:#ccc; }}
  .legend-dot {{ width:12px; height:12px; border-radius:50%; }}
  .stats {{ margin-top:8px; font-size:0.75rem; color:#555; }}
</style>
</head>
<body>
<h1>KG Discovery Engine — Hierarchical Edge Bundling</h1>
<p class="sub">Phase 4 · Top {TOP} nodes per domain · hover to highlight connections</p>
<div id="chart"></div>
<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:{COL_BIO}"></div><span>Biology ({len(bio_top)} nodes shown)</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:{COL_CHEM}"></div><span>Chemistry ({len(chem_top)} nodes shown)</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:{COL_CROSS}"></div><span>Cross-domain connections</span></div>
</div>
<div class="stats" id="stats"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const hierarchy_data = {hierarchy_json};
const links_data     = {links_json};

const W = Math.min(window.innerWidth - 40, 820);
const R = W / 2 - 120;  // radius

const svg = d3.select("#chart").append("svg")
  .attr("width", W).attr("height", W)
  .append("g")
  .attr("transform", `translate(${{W/2}},${{W/2}})`);

const cluster = d3.cluster().size([360, R]);
const root    = d3.hierarchy(hierarchy_data);
cluster(root);

// Flatten leaves
const leaves = root.leaves();
const leafMap = {{}};
leaves.forEach(d => {{ leafMap[d.data.name] = d; }});

// Line generator for bundled paths
const line = d3.lineRadial()
  .curve(d3.curveBundle.beta(0.85))
  .radius(d => d.y)
  .angle(d => d.x * Math.PI / 180);

// Draw bundled links
const linkGroup = svg.append("g");
links_data.forEach(link => {{
  const src = leafMap[link.source];
  const tgt = leafMap[link.target];
  if (!src || !tgt) return;
  const path = src.path(tgt);  // ancestor path
  const cls  = link.cross ? "link link-cross" : `link link-${{src.data.domain}}`;
  linkGroup.append("path")
    .datum(path)
    .attr("class", cls)
    .attr("d", line)
    .on("mouseover", function() {{ d3.select(this).attr("stroke-opacity", 1).attr("stroke-width", 2); }})
    .on("mouseout",  function() {{ d3.select(this).attr("stroke-opacity", link.cross ? 0.8 : 0.55).attr("stroke-width", link.cross ? 1.5 : 0.7); }});
}});

// Draw nodes
const nodeGroup = svg.append("g");
leaves.forEach(d => {{
  const g = nodeGroup.append("g")
    .attr("transform", `rotate(${{d.x - 90}}) translate(${{d.y}},0)`);

  g.append("circle")
    .attr("class", `node`)
    .attr("r", 3)
    .attr("fill", d.data.domain === "biology" ? "{COL_BIO}" : "{COL_CHEM}")
    .attr("stroke", "rgba(255,255,255,0.3)")
    .attr("stroke-width", 0.5);

  g.append("text")
    .attr("class", `label-${{d.data.domain}}`)
    .attr("dy", "0.31em")
    .attr("x", d.x < 180 ? 7 : -7)
    .attr("text-anchor", d.x < 180 ? "start" : "end")
    .attr("transform", d.x >= 180 ? "rotate(180)" : null)
    .text(d.data.label.length > 14 ? d.data.label.slice(0,12)+"…" : d.data.label)
    .on("mouseover", function(event, _) {{
      // Highlight all links for this node
      d3.selectAll(".link").attr("stroke-opacity", 0.05);
      d3.selectAll(".link-cross").attr("stroke-opacity", 0.05);
      linkGroup.selectAll("path").filter(function() {{
        const pathData = d3.select(this).datum();
        return pathData && pathData.some(p => p.data && p.data.name === d.data.name);
      }}).attr("stroke-opacity", 1).attr("stroke-width", 2);
    }})
    .on("mouseout", function() {{
      d3.selectAll(".link").attr("stroke-opacity", 0.55);
      d3.selectAll(".link-cross").attr("stroke-opacity", 0.8);
      d3.selectAll(".link").attr("stroke-width", 0.7);
      d3.selectAll(".link-cross").attr("stroke-width", 1.5);
    }});
}});

// Domain arc labels
["biology", "chemistry"].forEach(domain => {{
  const domLeaves = leaves.filter(d => d.data.domain === domain);
  if (domLeaves.length === 0) return;
  const angles = domLeaves.map(d => d.x);
  const midAngle = (Math.min(...angles) + Math.max(...angles)) / 2;
  const col = domain === "biology" ? "{COL_BIO}" : "{COL_CHEM}";
  svg.append("text")
    .attr("transform", `rotate(${{midAngle - 90}}) translate(${{R + 60}},0) ${{midAngle > 180 ? "rotate(180)" : ""}}`)
    .attr("text-anchor", midAngle > 180 ? "end" : "start")
    .attr("dy", "0.35em")
    .attr("fill", col)
    .attr("font-size", "13px")
    .attr("font-weight", "bold")
    .attr("letter-spacing", "2px")
    .text(domain.toUpperCase());
}});

const crossCount = links_data.filter(l => l.cross).length;
const intraCount = links_data.filter(l => !l.cross).length;
d3.select("#stats").text(
  `Showing ${{leaves.length}} of {G.number_of_nodes()} nodes · ${{links_data.length}} edges displayed (${{crossCount}} cross-domain, ${{intraCount}} intra-domain)`
);
</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"  Saved: {out}")


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    """Generate all 5 marketing visualizations."""
    np.random.seed(SEED)

    print("Loading Phase 4 KG (Condition D)...")
    G = load_graph()
    bio_n   = sum(1 for _, d in G.nodes(data=True) if d["domain"] == "biology")
    chem_n  = G.number_of_nodes() - bio_n
    cross_n = sum(1 for u, v in G.edges() if G.nodes[u]["domain"] != G.nodes[v]["domain"])
    print(f"  Nodes: {G.number_of_nodes()} (bio={bio_n}, chem={chem_n})")
    print(f"  Edges: {G.number_of_edges()} (cross-domain={cross_n})")

    print("\n[1/5] Circular + Bézier edge bundling (PNG)...")
    draw_circular_bundling(G, OUT_DIR / "kg_circular_bundling.png")

    print("\n[2/5] Chord diagram (HTML)...")
    build_chord_html(G, OUT_DIR / "kg_chord_diagram.html")

    print("\n[3/5] 3D force-directed graph (HTML)...")
    build_3d_force_html(G, OUT_DIR / "kg_3d_force.html")

    print("\n[4/5] Adjacency matrix heatmap (PNG)...")
    draw_adjacency_matrix(G, OUT_DIR / "kg_adjacency_matrix.png")

    print("\n[5/5] Hierarchical edge bundling (HTML)...")
    build_hierarchical_bundling_html(G, OUT_DIR / "kg_hierarchical_bundling.html")

    print(f"\nAll 5 visualizations saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
