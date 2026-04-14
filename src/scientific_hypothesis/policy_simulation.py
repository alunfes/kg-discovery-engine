"""
WS4 Policy Simulation — P2B Framework
Simulates 6 selection policies on the 140-record population (C1+C2)
and compares their investigability, novelty, and stability metrics.

Usage:
    python3 src/scientific_hypothesis/policy_simulation.py

Reads:  runs/run_021_density_ceiling/density_scores.json
Writes: runs/run_024_p2b_framework/simulation_results.json
        runs/run_024_p2b_framework/plots/policy_comparison.html
"""

import json
import math
import os
import random
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED: int = 42
N_SELECT: int = 70
N_ITERATIONS: int = 1000
C1_REFERENCE: float = 0.971
TAU: float = 7500.0
LOG_TAU: float = math.log10(TAU)
K: float = 3.0
LAMBDA: float = 0.7
TAU_FLOOR: float = 3500.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_population(path: str) -> list[dict[str, Any]]:
    """Load density_scores.json and return only C1_compose + C2_multi_op records."""
    with open(path, "r") as f:
        data = json.load(f)
    kept = [r for r in data if r["method"] in ("C1_compose", "C2_multi_op")]
    return kept


def compute_boundaries(population: list[dict[str, Any]]) -> tuple[float, float]:
    """Return (Q1_boundary, Q2_boundary) = (25th pct, 50th pct) of min_density."""
    densities = sorted(r["min_density"] for r in population)
    n = len(densities)
    q1_idx = int(n * 0.25)
    q2_idx = int(n * 0.50)
    return float(densities[q1_idx]), float(densities[q2_idx])


# ---------------------------------------------------------------------------
# Helper: weighted sampling without replacement
# ---------------------------------------------------------------------------
def weighted_sample_without_replacement(
    pool: list[dict[str, Any]],
    weights: list[float],
    k: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Sample k items from pool without replacement using provided weights."""
    remaining = list(zip(pool, weights))
    selected: list[dict[str, Any]] = []
    for _ in range(min(k, len(remaining))):
        total_w = sum(w for _, w in remaining)
        if total_w <= 0:
            break
        r = rng.random() * total_w
        cumulative = 0.0
        chosen_idx = 0
        for idx, (item, w) in enumerate(remaining):
            cumulative += w
            if cumulative >= r:
                chosen_idx = idx
                break
        selected.append(remaining[chosen_idx][0])
        remaining.pop(chosen_idx)
    return selected


# ---------------------------------------------------------------------------
# 6 Policy implementations
# ---------------------------------------------------------------------------
def policy_uniform(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Random sample n without replacement from full population."""
    return rng.sample(pop, n)


def policy_hard_threshold(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Sample from min_density >= TAU; fill remainder from full pool randomly."""
    high = [r for r in pop if r["min_density"] >= TAU]
    if len(high) >= n:
        return rng.sample(high, n)
    selected = list(high)
    high_ids = {r["id"] for r in high}
    remaining_pool = [r for r in pop if r["id"] not in high_ids]
    fill = rng.sample(remaining_pool, n - len(selected))
    return selected + fill


def policy_soft_weighting(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Weighted sampling using sigmoid(k*(log_density - log(tau)))."""
    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    weights = [sigmoid(K * (r["log_min_density"] - LOG_TAU)) for r in pop]
    return weighted_sample_without_replacement(pop, weights, n, rng)


def policy_two_mode(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """49 from high-density (>=tau), 21 from low-density (<tau); fill if insufficient."""
    n_high = int(n * LAMBDA)   # 49
    n_low = n - n_high          # 21
    high = [r for r in pop if r["min_density"] >= TAU]
    low = [r for r in pop if r["min_density"] < TAU]

    if len(high) >= n_high:
        sel_high = rng.sample(high, n_high)
    else:
        sel_high = list(high)
    deficit_high = n_high - len(sel_high)

    if len(low) >= n_low + deficit_high:
        sel_low = rng.sample(low, n_low + deficit_high)
    elif len(low) >= n_low:
        sel_low = rng.sample(low, n_low)
        # fill from high if any left
        extra_high = [r for r in high if r not in sel_high]
        sel_low += rng.sample(extra_high, min(deficit_high, len(extra_high)))
    else:
        sel_low = list(low)
        extra = [r for r in pop if r not in sel_high and r not in sel_low]
        fill = rng.sample(extra, min(n - len(sel_high) - len(sel_low), len(extra)))
        sel_low += fill

    return sel_high + sel_low


def policy_quantile_constrained(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Sample evenly from 4 quartiles (17/18 each to reach 70)."""
    densities = sorted(r["min_density"] for r in pop)
    total = len(densities)
    q1_b = densities[int(total * 0.25)]
    q2_b = densities[int(total * 0.50)]
    q3_b = densities[int(total * 0.75)]

    quartiles = [
        [r for r in pop if r["min_density"] < q1_b],
        [r for r in pop if q1_b <= r["min_density"] < q2_b],
        [r for r in pop if q2_b <= r["min_density"] < q3_b],
        [r for r in pop if r["min_density"] >= q3_b],
    ]
    # allocate: 17, 18, 17, 18 = 70
    targets = [17, 18, 17, 18]
    selected: list[dict[str, Any]] = []
    for q, t in zip(quartiles, targets):
        k = min(t, len(q))
        selected += rng.sample(q, k)
    return selected


def policy_diversity_guarded(
    pop: list[dict[str, Any]], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Hard floor min_density>=TAU_FLOOR, then greedy max-spread by log_density."""
    eligible = [r for r in pop if r["min_density"] >= TAU_FLOOR]
    if len(eligible) <= n:
        return eligible

    # Greedy max-spread: iteratively pick item farthest from current selections
    # Seed with random item to avoid determinism collapse
    seed_item = rng.choice(eligible)
    selected = [seed_item]
    remaining = [r for r in eligible if r is not seed_item]

    while len(selected) < n and remaining:
        # Find item with max min-distance to any already selected
        sel_logs = [r["log_min_density"] for r in selected]
        best_item = max(
            remaining,
            key=lambda r: min(abs(r["log_min_density"] - s) for s in sel_logs),
        )
        selected.append(best_item)
        remaining = [r for r in remaining if r is not best_item]

    return selected


# ---------------------------------------------------------------------------
# Metric computation per iteration
# ---------------------------------------------------------------------------
def compute_iteration_metrics(
    selected: list[dict[str, Any]],
    q1_boundary: float,
    density_median: float,
) -> dict[str, float]:
    """Compute per-iteration metrics for a selection."""
    investigated = [r["investigated"] for r in selected]
    mean_inv = sum(investigated) / len(investigated) if investigated else 0.0
    delta = mean_inv - C1_REFERENCE
    q1_frac = sum(1 for r in selected if r["min_density"] < q1_boundary) / len(selected)
    novelty = sum(1 for r in selected if r["min_density"] < density_median) / len(selected)
    return {
        "mean_investigability": mean_inv,
        "delta_vs_c1": delta,
        "low_density_exposure": q1_frac,
        "novelty_retention": novelty,
    }


# ---------------------------------------------------------------------------
# Bootstrap runner
# ---------------------------------------------------------------------------
def run_bootstrap(
    policy_fn,
    pop: list[dict[str, Any]],
    q1_boundary: float,
    density_median: float,
    n: int,
    n_iter: int,
    rng: random.Random,
) -> dict[str, list[float]]:
    """Run n_iter bootstrap iterations for a single policy."""
    results: dict[str, list[float]] = {
        "mean_investigability": [],
        "delta_vs_c1": [],
        "low_density_exposure": [],
        "novelty_retention": [],
    }
    for _ in range(n_iter):
        selected = policy_fn(pop, n, rng)
        metrics = compute_iteration_metrics(selected, q1_boundary, density_median)
        for k, v in metrics.items():
            results[k].append(v)
    return results


# ---------------------------------------------------------------------------
# Statistics aggregation
# ---------------------------------------------------------------------------
def aggregate_stats(
    raw: dict[str, list[float]],
) -> dict[str, float]:
    """Compute mean/std/percentiles and probability metrics."""
    inv = sorted(raw["mean_investigability"])
    n = len(inv)
    mean_inv = sum(inv) / n
    var = sum((x - mean_inv) ** 2 for x in inv) / n
    std_inv = math.sqrt(var)
    p5 = inv[int(n * 0.05)]
    p95 = inv[int(n * 0.95)]
    p_095 = sum(1 for x in inv if x >= 0.95) / n
    p_c1 = sum(1 for x in inv if x >= C1_REFERENCE) / n

    delta = raw["delta_vs_c1"]
    mean_delta = sum(delta) / len(delta)

    low_exp = raw["low_density_exposure"]
    mean_low = sum(low_exp) / len(low_exp)

    nov = raw["novelty_retention"]
    mean_nov = sum(nov) / len(nov)

    return {
        "mean_investigability": round(mean_inv, 6),
        "std_investigability": round(std_inv, 6),
        "p5_investigability": round(p5, 6),
        "p95_investigability": round(p95, 6),
        "mean_delta_vs_c1": round(mean_delta, 6),
        "mean_low_density_exposure": round(mean_low, 6),
        "mean_novelty_retention": round(mean_nov, 6),
        "p_meet_095": round(p_095, 6),
        "p_meet_c1": round(p_c1, 6),
    }


# ---------------------------------------------------------------------------
# Scenario rankings
# ---------------------------------------------------------------------------
def compute_rankings(
    policy_stats: dict[str, dict[str, float]],
) -> dict[str, list[str]]:
    """Compute 4 scenario rankings."""
    names = list(policy_stats.keys())

    stability = sorted(names, key=lambda p: policy_stats[p]["std_investigability"])
    parity = sorted(names, key=lambda p: abs(policy_stats[p]["mean_delta_vs_c1"]))
    balanced = sorted(
        names,
        key=lambda p: (
            0.5 * policy_stats[p]["mean_investigability"]
            + 0.5 * policy_stats[p]["mean_novelty_retention"]
        ),
        reverse=True,
    )
    discovery = sorted(
        names, key=lambda p: policy_stats[p]["mean_novelty_retention"], reverse=True
    )
    return {
        "stability_priority": stability,
        "parity_priority": parity,
        "balanced": balanced,
        "discovery_priority": discovery,
    }


# ---------------------------------------------------------------------------
# Recommended defaults
# ---------------------------------------------------------------------------
def recommend_defaults(
    policy_stats: dict[str, dict[str, float]],
    rankings: dict[str, list[str]],
) -> dict[str, str]:
    """Pick production and research recommended policies."""
    production = rankings["stability_priority"][0]
    research = rankings["discovery_priority"][0]
    rationale = (
        f"Production default '{production}' chosen for lowest variance "
        f"(std={policy_stats[production]['std_investigability']:.4f}), "
        f"ensuring reliable investigability >= {policy_stats[production]['p5_investigability']:.3f} "
        f"at 5th percentile. "
        f"Research default '{research}' chosen for highest novelty retention "
        f"(mean_novelty={policy_stats[research]['mean_novelty_retention']:.3f}), "
        f"maximizing exposure to structurally unusual hypotheses."
    )
    return {"production": production, "research": research, "rationale": rationale}


# ---------------------------------------------------------------------------
# HTML chart generator
# ---------------------------------------------------------------------------
def build_html(
    policy_stats: dict[str, dict[str, float]],
    rankings: dict[str, list[str]],
    q1_boundary: float,
) -> str:
    """Generate self-contained HTML with vanilla JS charts."""
    policies = list(policy_stats.keys())

    # Sort by mean_investigability descending for bar chart 1
    sorted_by_inv = sorted(
        policies, key=lambda p: policy_stats[p]["mean_investigability"], reverse=True
    )
    # Sort by novelty descending for bar chart 2
    sorted_by_nov = sorted(
        policies, key=lambda p: policy_stats[p]["mean_novelty_retention"], reverse=True
    )

    def inv_color(val: float) -> str:
        if val >= 0.95:
            return "#2ecc71"
        if val >= 0.90:
            return "#f1c40f"
        return "#e74c3c"

    def nov_color(idx: int, n: int) -> str:
        blues = ["#003f5c", "#2f6090", "#4584c8", "#7eb6d9", "#b3d4ec", "#ddeef9"]
        return blues[min(idx, len(blues) - 1)]

    # Build JS data objects
    inv_labels = json.dumps(sorted_by_inv)
    inv_means = json.dumps([policy_stats[p]["mean_investigability"] for p in sorted_by_inv])
    inv_stds = json.dumps([policy_stats[p]["std_investigability"] for p in sorted_by_inv])
    inv_colors = json.dumps([inv_color(policy_stats[p]["mean_investigability"]) for p in sorted_by_inv])

    nov_labels = json.dumps(sorted_by_nov)
    nov_vals = json.dumps([policy_stats[p]["mean_novelty_retention"] for p in sorted_by_nov])
    nov_colors = json.dumps([nov_color(i, len(sorted_by_nov)) for i in range(len(sorted_by_nov))])

    scatter_x = json.dumps([policy_stats[p]["mean_novelty_retention"] for p in policies])
    scatter_y = json.dumps([policy_stats[p]["mean_investigability"] for p in policies])
    scatter_labels = json.dumps(policies)

    # Rankings table data
    scenario_names = ["stability_priority", "parity_priority", "balanced", "discovery_priority"]
    scenario_labels = ["Stability Priority", "Parity Priority", "Balanced", "Discovery Priority"]
    rankings_rows = []
    max_rank = max(len(rankings[s]) for s in scenario_names)
    for rank_idx in range(max_rank):
        row = []
        for s in scenario_names:
            lst = rankings[s]
            row.append(lst[rank_idx] if rank_idx < len(lst) else "")
        rankings_rows.append(row)

    table_header = "".join(f"<th>{lbl}</th>" for lbl in scenario_labels)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rankings_rows
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>WS4 Policy Comparison</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }}
  h1 {{ color: #2c3e50; }}
  h2 {{ color: #34495e; border-bottom: 2px solid #bdc3c7; padding-bottom: 4px; }}
  .section {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 30px;
              box-shadow: 0 2px 6px rgba(0,0,0,0.1); max-width: 900px; }}
  canvas {{ display: block; margin: 0 auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
  th {{ background: #2c3e50; color: #fff; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .legend {{ font-size: 13px; margin-top: 8px; }}
  .leg-item {{ display: inline-block; margin-right: 18px; }}
  .leg-box {{ display: inline-block; width: 14px; height: 14px; vertical-align: middle; margin-right: 4px; }}
</style>
</head>
<body>
<h1>WS4 — Policy Simulation Results (P2B Framework)</h1>
<p>Population: 140 records (C1+C2). Bootstrap iterations: 1000. Seed: 42. C1 reference: 0.971. Q1 boundary: {q1_boundary:.0f}</p>

<div class="section">
  <h2>1. Mean Investigability by Policy</h2>
  <canvas id="invChart" width="860" height="340"></canvas>
  <div class="legend">
    <span class="leg-item"><span class="leg-box" style="background:#2ecc71"></span>&ge; 0.95 (good)</span>
    <span class="leg-item"><span class="leg-box" style="background:#f1c40f"></span>0.90–0.95 (acceptable)</span>
    <span class="leg-item"><span class="leg-box" style="background:#e74c3c"></span>&lt; 0.90 (poor)</span>
  </div>
</div>

<div class="section">
  <h2>2. Novelty Retention by Policy</h2>
  <canvas id="novChart" width="860" height="300"></canvas>
</div>

<div class="section">
  <h2>3. Investigability vs Novelty Retention (Scatter)</h2>
  <canvas id="scatterChart" width="860" height="460"></canvas>
</div>

<div class="section">
  <h2>4. Scenario Rankings</h2>
  <table>
    <thead><tr>{table_header}</tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<script>
// -----------------------------------------------------------------------
// Chart 1: Mean Investigability (horizontal bar with error bars)
// -----------------------------------------------------------------------
(function() {{
  const canvas = document.getElementById('invChart');
  const ctx = canvas.getContext('2d');
  const labels = {inv_labels};
  const means  = {inv_means};
  const stds   = {inv_stds};
  const colors = {inv_colors};
  const C1_REF = {C1_REFERENCE};

  const marginL = 180, marginR = 40, marginT = 20, marginB = 30;
  const W = canvas.width - marginL - marginR;
  const H = canvas.height - marginT - marginB;
  const n = labels.length;
  const barH = Math.floor(H / n) - 6;
  const xMin = 0.7, xMax = 1.0;

  function xScale(v) {{ return marginL + (v - xMin) / (xMax - xMin) * W; }}

  // grid
  ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1;
  for (let t = 0; t <= 6; t++) {{
    const v = xMin + t * (xMax - xMin) / 6;
    const x = xScale(v);
    ctx.beginPath(); ctx.moveTo(x, marginT); ctx.lineTo(x, marginT + H); ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText(v.toFixed(2), x, marginT + H + 15);
  }}

  // bars + error bars
  for (let i = 0; i < n; i++) {{
    const y = marginT + i * (H / n) + 3;
    const xStart = xScale(xMin);
    const xEnd   = xScale(Math.max(xMin, Math.min(xMax, means[i])));

    ctx.fillStyle = colors[i];
    ctx.fillRect(xStart, y, xEnd - xStart, barH);

    // error bar
    const xMean = xScale(means[i]);
    const xErr1 = xScale(Math.min(xMax, means[i] + stds[i]));
    const xErr0 = xScale(Math.max(xMin, means[i] - stds[i]));
    ctx.strokeStyle = '#333'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(xErr0, y + barH/2); ctx.lineTo(xErr1, y + barH/2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(xErr0, y + barH/4); ctx.lineTo(xErr0, y + 3*barH/4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(xErr1, y + barH/4); ctx.lineTo(xErr1, y + 3*barH/4); ctx.stroke();

    // value label
    ctx.fillStyle = '#333'; ctx.font = '11px Arial'; ctx.textAlign = 'left';
    ctx.fillText(means[i].toFixed(4), xEnd + 4, y + barH/2 + 4);

    // policy label
    ctx.textAlign = 'right';
    ctx.fillText(labels[i], marginL - 6, y + barH/2 + 4);
  }}

  // C1 reference line
  const xC1 = xScale(C1_REF);
  ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 2; ctx.setLineDash([6, 3]);
  ctx.beginPath(); ctx.moveTo(xC1, marginT); ctx.lineTo(xC1, marginT + H); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#c0392b'; ctx.font = 'bold 11px Arial'; ctx.textAlign = 'left';
  ctx.fillText('C1=' + C1_REF, xC1 + 3, marginT + 14);
}})();

// -----------------------------------------------------------------------
// Chart 2: Novelty Retention (horizontal bar)
// -----------------------------------------------------------------------
(function() {{
  const canvas = document.getElementById('novChart');
  const ctx = canvas.getContext('2d');
  const labels = {nov_labels};
  const vals   = {nov_vals};
  const colors = {nov_colors};

  const marginL = 180, marginR = 40, marginT = 20, marginB = 30;
  const W = canvas.width - marginL - marginR;
  const H = canvas.height - marginT - marginB;
  const n = labels.length;
  const barH = Math.floor(H / n) - 6;
  const xMin = 0.0, xMax = 1.0;

  function xScale(v) {{ return marginL + (v - xMin) / (xMax - xMin) * W; }}

  ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1;
  for (let t = 0; t <= 5; t++) {{
    const v = xMin + t * (xMax - xMin) / 5;
    const x = xScale(v);
    ctx.beginPath(); ctx.moveTo(x, marginT); ctx.lineTo(x, marginT + H); ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText(v.toFixed(1), x, marginT + H + 15);
  }}

  for (let i = 0; i < n; i++) {{
    const y = marginT + i * (H / n) + 3;
    const xStart = xScale(xMin);
    const xEnd   = xScale(vals[i]);

    ctx.fillStyle = colors[i];
    ctx.fillRect(xStart, y, xEnd - xStart, barH);

    ctx.fillStyle = '#333'; ctx.font = '11px Arial'; ctx.textAlign = 'left';
    ctx.fillText(vals[i].toFixed(4), xEnd + 4, y + barH/2 + 4);

    ctx.textAlign = 'right';
    ctx.fillText(labels[i], marginL - 6, y + barH/2 + 4);
  }}
}})();

// -----------------------------------------------------------------------
// Chart 3: Scatter — Investigability vs Novelty
// -----------------------------------------------------------------------
(function() {{
  const canvas = document.getElementById('scatterChart');
  const ctx = canvas.getContext('2d');
  const xs = {scatter_x};
  const ys = {scatter_y};
  const labels = {scatter_labels};

  const marginL = 60, marginR = 80, marginT = 60, marginB = 50;
  const W = canvas.width - marginL - marginR;
  const H = canvas.height - marginT - marginB;
  const xMin = 0.0, xMax = 1.0, yMin = 0.7, yMax = 1.0;

  function xS(v) {{ return marginL + (v - xMin) / (xMax - xMin) * W; }}
  function yS(v) {{ return marginT + H - (v - yMin) / (yMax - yMin) * H; }}

  // quadrant shading
  const xMid = xS(0.5), yMid = yS(0.85);
  ctx.globalAlpha = 0.07;
  ctx.fillStyle = '#27ae60'; ctx.fillRect(xMid, marginT, W - (xMid - marginL), yMid - marginT);
  ctx.fillStyle = '#3498db'; ctx.fillRect(marginL, marginT, xMid - marginL, yMid - marginT);
  ctx.fillStyle = '#e67e22'; ctx.fillRect(xMid, yMid, W - (xMid - marginL), H - (yMid - marginT));
  ctx.fillStyle = '#95a5a6'; ctx.fillRect(marginL, yMid, xMid - marginL, H - (yMid - marginT));
  ctx.globalAlpha = 1.0;

  // quadrant labels
  ctx.fillStyle = '#27ae60'; ctx.font = 'bold 12px Arial'; ctx.textAlign = 'center';
  ctx.fillText('IDEAL', xS(0.75), marginT + 22);
  ctx.fillStyle = '#3498db';
  ctx.fillText('Safe/Low novelty', xS(0.25), marginT + 22);
  ctx.fillStyle = '#e67e22';
  ctx.fillText('Risky high novelty', xS(0.75), yMid + 22);

  // grid lines
  ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1;
  for (let t = 0; t <= 5; t++) {{
    const x = xS(xMin + t * (xMax - xMin) / 5);
    ctx.beginPath(); ctx.moveTo(x, marginT); ctx.lineTo(x, marginT + H); ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'center';
    ctx.fillText((xMin + t * (xMax - xMin) / 5).toFixed(1), x, marginT + H + 16);
  }}
  for (let t = 0; t <= 6; t++) {{
    const y = yS(yMin + t * (yMax - yMin) / 6);
    ctx.beginPath(); ctx.moveTo(marginL, y); ctx.lineTo(marginL + W, y); ctx.stroke();
    ctx.fillStyle = '#888'; ctx.font = '11px Arial'; ctx.textAlign = 'right';
    ctx.fillText((yMin + t * (yMax - yMin) / 6).toFixed(2), marginL - 6, y + 4);
  }}

  // axis labels
  ctx.fillStyle = '#333'; ctx.font = 'bold 13px Arial';
  ctx.textAlign = 'center';
  ctx.fillText('Novelty Retention (x)', marginL + W / 2, marginT + H + 38);
  ctx.save(); ctx.translate(16, marginT + H / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillText('Mean Investigability (y)', 0, 0); ctx.restore();

  // points
  const ptColors = ['#2c3e50','#e74c3c','#3498db','#2ecc71','#9b59b6','#e67e22'];
  for (let i = 0; i < xs.length; i++) {{
    const cx = xS(xs[i]), cy = yS(ys[i]);
    ctx.beginPath();
    ctx.arc(cx, cy, 8, 0, 2 * Math.PI);
    ctx.fillStyle = ptColors[i % ptColors.length];
    ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();

    // label
    ctx.fillStyle = '#2c3e50'; ctx.font = '11px Arial'; ctx.textAlign = 'left';
    ctx.fillText(labels[i], cx + 10, cy + 4);
  }}

  // C1 reference horizontal line
  const yC1 = yS({C1_REFERENCE});
  ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 1.5; ctx.setLineDash([5,3]);
  ctx.beginPath(); ctx.moveTo(marginL, yC1); ctx.lineTo(marginL + W, yC1); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#c0392b'; ctx.font = '11px Arial'; ctx.textAlign = 'right';
  ctx.fillText('C1={C1_REFERENCE}', marginL + W, yC1 - 4);
}})();
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Run simulation, write outputs, print summary."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    input_path = os.path.join(base, "runs", "run_021_density_ceiling", "density_scores.json")
    out_dir = os.path.join(base, "runs", "run_024_p2b_framework")
    plots_dir = os.path.join(out_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    population = load_population(input_path)
    print(f"Population loaded: {len(population)} records")

    q1_boundary, q2_boundary = compute_boundaries(population)
    density_median = q2_boundary
    print(f"Q1 boundary: {q1_boundary:.1f}, Q2 (median) boundary: {q2_boundary:.1f}")

    rng = random.Random(SEED)

    policies = {
        "uniform": policy_uniform,
        "hard_threshold": policy_hard_threshold,
        "soft_weighting": policy_soft_weighting,
        "two_mode": policy_two_mode,
        "quantile_constrained": policy_quantile_constrained,
        "diversity_guarded": policy_diversity_guarded,
    }

    policy_raw: dict[str, dict[str, list[float]]] = {}
    for name, fn in policies.items():
        print(f"  Running {name} ({N_ITERATIONS} iterations)...")
        policy_raw[name] = run_bootstrap(
            fn, population, q1_boundary, density_median, N_SELECT, N_ITERATIONS, rng
        )

    policy_stats = {name: aggregate_stats(raw) for name, raw in policy_raw.items()}
    rankings = compute_rankings(policy_stats)
    recommended = recommend_defaults(policy_stats, rankings)

    result = {
        "simulation_config": {
            "n_population": len(population),
            "n_select": N_SELECT,
            "n_iterations": N_ITERATIONS,
            "seed": SEED,
            "c1_reference": C1_REFERENCE,
            "q1_boundary": q1_boundary,
            "q2_boundary": q2_boundary,
        },
        "policy_results": policy_stats,
        "scenario_rankings": rankings,
        "recommended_defaults": recommended,
    }

    results_path = os.path.join(out_dir, "simulation_results.json")
    with open(results_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults written to: {results_path}")

    html = build_html(policy_stats, rankings, q1_boundary)
    html_path = os.path.join(plots_dir, "policy_comparison.html")
    with open(html_path, "w") as f:
        f.write(html)
    print(f"HTML chart written to: {html_path}")

    # Summary table
    print("\n" + "=" * 90)
    print(f"{'Policy':<22} {'MeanInv':>9} {'StdInv':>8} {'P5':>7} {'P95':>7} "
          f"{'Delta':>8} {'LowExp':>8} {'Novelty':>9} {'P>=0.95':>8} {'P>=C1':>7}")
    print("-" * 90)
    for name, s in policy_stats.items():
        print(
            f"{name:<22} {s['mean_investigability']:>9.4f} {s['std_investigability']:>8.4f} "
            f"{s['p5_investigability']:>7.4f} {s['p95_investigability']:>7.4f} "
            f"{s['mean_delta_vs_c1']:>8.4f} {s['mean_low_density_exposure']:>8.4f} "
            f"{s['mean_novelty_retention']:>9.4f} {s['p_meet_095']:>8.4f} "
            f"{s['p_meet_c1']:>7.4f}"
        )
    print("=" * 90)
    print(f"\nStability ranking: {rankings['stability_priority']}")
    print(f"Parity ranking:    {rankings['parity_priority']}")
    print(f"Balanced ranking:  {rankings['balanced']}")
    print(f"Discovery ranking: {rankings['discovery_priority']}")
    print(f"\nRecommended production: {recommended['production']}")
    print(f"Recommended research:   {recommended['research']}")


if __name__ == "__main__":
    main()
