"""
P3: Novelty-Investigability Tradeoff Analysis for run_018 data.

Computes novelty scores for 210 hypotheses (C2/C1/C_rand_v2) and runs
bin analysis, sweet spot detection, and statistical tests.

Usage:
    python src/scientific_hypothesis/add_novelty_scores.py

Outputs (runs/run_019_novelty_tradeoff_analysis/):
    novelty_scores.json, bin_analysis.json, sweet_spot_analysis.json,
    statistical_tests.json, review_memo.md, novelty_scatter.html
"""

import json
import math
import os
import random
import datetime
from typing import Dict, List, Tuple, Any

random.seed(42)

RUN_018_DIR = "runs/run_018_investigability_replication"
RUN_019_DIR = "runs/run_019_novelty_tradeoff_analysis"

HYP_FILES = {
    "C2_multi_op": f"{RUN_018_DIR}/hypotheses_c2.json",
    "C1_compose": f"{RUN_018_DIR}/hypotheses_c1.json",
    "C_rand_v2": f"{RUN_018_DIR}/hypotheses_crand_v2.json",
}
LAYER2_FILE = f"{RUN_018_DIR}/labeling_results_layer2.json"

NOVELTY_WEIGHTS = {"path_length": 0.3, "cross_domain": 0.3, "popularity": 0.4}

SWEET_SPOT_INVESTIGABILITY_MIN = 0.90
SWEET_SPOT_NOVELTY_MIN = 0.40

BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
BIN_LABELS = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]


def load_hypotheses() -> Dict[str, List[Dict]]:
    """Load all hypothesis files and return dict keyed by method."""
    result: Dict[str, List[Dict]] = {}
    for method, path in HYP_FILES.items():
        with open(path) as f:
            data = json.load(f)
        result[method] = data["hypotheses"]
    return result


def load_layer2() -> Dict[str, Dict]:
    """Load Layer 2 labels, indexed by hypothesis id."""
    with open(LAYER2_FILE) as f:
        records = json.load(f)
    return {r["id"]: r for r in records}


def path_length_score(chain_length: int) -> float:
    """Map chain_length to novelty score (longer path = higher novelty).

    Rationale: longer KG paths tend to connect more distal, less-explored
    entity pairs.
    """
    if chain_length <= 2:
        return 0.2
    elif chain_length == 3:
        return 0.5
    elif chain_length == 4:
        return 0.8
    else:  # 5+
        return 1.0


def cross_domain_score(subject_id: str, object_id: str) -> float:
    """1.0 if subject and object are from different domains (chem vs bio), else 0.0."""
    subj_domain = subject_id.split(":")[0]
    obj_domain = object_id.split(":")[0]
    return 1.0 if subj_domain != obj_domain else 0.0


def compute_popularity_scores(
    records: List[Dict],
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Normalize past_pubmed_hits_le2023 via log scale across all records.

    Uses existing Layer 2 `past_pubmed_hits_le2023` as a proxy for entity
    popularity (how well-known the hypothesis is in the ≤2023 corpus).
    This avoids redundant PubMed API calls since the data is already present.

    Returns:
        norm_scores: {id: normalized_popularity (0–1, high = popular)}
        raw_hits: {id: raw hit count}
    """
    raw_hits = {r["id"]: r["past_pubmed_hits_le2023"] for r in records}
    max_hits = max(raw_hits.values()) if raw_hits else 1
    norm_scores = {
        hid: math.log(1 + hits) / math.log(1 + max_hits)
        for hid, hits in raw_hits.items()
    }
    return norm_scores, raw_hits


def compute_novelty_record(
    hyp: Dict,
    layer2: Dict,
    pop_norm: Dict[str, float],
    pop_raw: Dict[str, int],
) -> Dict[str, Any]:
    """Compute all novelty sub-scores and combined score for one hypothesis."""
    hid = hyp["id"]
    l2 = layer2[hid]

    pl_score = path_length_score(hyp["chain_length"])
    cd_score = cross_domain_score(hyp["subject_id"], hyp["object_id"])
    pop_normalized = pop_norm[hid]
    pop_score = 1.0 - pop_normalized  # low popularity = high novelty

    combined = (
        NOVELTY_WEIGHTS["path_length"] * pl_score
        + NOVELTY_WEIGHTS["cross_domain"] * cd_score
        + NOVELTY_WEIGHTS["popularity"] * pop_score
    )

    investigated = 1 if l2["label_layer1"] != "not_investigated" else 0

    return {
        "id": hid,
        "method": hyp["method"],
        "description": hyp["description"],
        "subject_id": hyp["subject_id"],
        "object_id": hyp["object_id"],
        "chain_length": hyp["chain_length"],
        "label_layer1": l2["label_layer1"],
        "label_layer2": l2["label_layer2"],
        "past_pubmed_hits_le2023": pop_raw[hid],
        "path_length_score": round(pl_score, 4),
        "cross_domain_score": round(cd_score, 4),
        "entity_popularity_raw": pop_raw[hid],
        "entity_popularity_normalized": round(pop_normalized, 4),
        "entity_popularity_score": round(pop_score, 4),
        "combined_novelty": round(combined, 4),
        "investigated": investigated,
    }


def build_novelty_records(
    hypotheses: Dict[str, List[Dict]], layer2: Dict[str, Dict]
) -> List[Dict]:
    """Build full novelty record list for all 210 hypotheses."""
    all_hyps = [h for hyps in hypotheses.values() for h in hyps]
    all_l2 = list(layer2.values())

    pop_norm, pop_raw = compute_popularity_scores(all_l2)

    records = []
    for hyps in hypotheses.values():
        for hyp in hyps:
            rec = compute_novelty_record(hyp, layer2, pop_norm, pop_raw)
            records.append(rec)
    return records


def bin_index(novelty: float) -> int:
    """Return bin index (0–4) for a given novelty score."""
    for i, (lo, hi) in enumerate(BINS):
        if lo <= novelty < hi:
            return i
    return len(BINS) - 1  # 1.0 falls in last bin


def run_bin_analysis(records: List[Dict]) -> Dict:
    """Compute investigability rate per novelty bin, overall and per method."""
    methods = sorted(set(r["method"] for r in records))

    def bin_stats(recs: List[Dict]) -> List[Dict]:
        bins: List[List[Dict]] = [[] for _ in BINS]
        for r in recs:
            bins[bin_index(r["combined_novelty"])].append(r)
        result = []
        for i, (lo, hi) in enumerate(BINS):
            n = len(bins[i])
            investigated = sum(r["investigated"] for r in bins[i])
            rate = investigated / n if n > 0 else None
            result.append(
                {
                    "bin": BIN_LABELS[i],
                    "n": n,
                    "investigated": investigated,
                    "investigability_rate": round(rate, 4) if rate is not None else None,
                }
            )
        return result

    output: Dict[str, Any] = {"overall": bin_stats(records)}
    for method in methods:
        subset = [r for r in records if r["method"] == method]
        output[method] = bin_stats(subset)

    return output


def run_sweet_spot_analysis(records: List[Dict]) -> Dict:
    """Identify sweet spot (investigability≥0.90, novelty≥0.40) and method breakdown."""
    methods = sorted(set(r["method"] for r in records))

    def sweet_spot_stats(recs: List[Dict]) -> Dict:
        n_total = len(recs)
        high_novelty = [r for r in recs if r["combined_novelty"] >= SWEET_SPOT_NOVELTY_MIN]
        sweet = [
            r for r in high_novelty
            if r["investigated"] == 1
        ]
        n_high = len(high_novelty)
        inv_rate_high = sum(r["investigated"] for r in high_novelty) / n_high if n_high else None
        return {
            "n_total": n_total,
            "n_high_novelty": n_high,
            "high_novelty_rate": round(n_high / n_total, 4) if n_total else None,
            "n_sweet_spot": len(sweet),
            "sweet_spot_rate_of_total": round(len(sweet) / n_total, 4) if n_total else None,
            "investigability_in_high_novelty": round(inv_rate_high, 4) if inv_rate_high is not None else None,
            "sweet_spot_threshold_novelty": SWEET_SPOT_NOVELTY_MIN,
            "sweet_spot_threshold_investigability": SWEET_SPOT_INVESTIGABILITY_MIN,
        }

    output: Dict[str, Any] = {"overall": sweet_spot_stats(records)}
    for method in methods:
        subset = [r for r in records if r["method"] == method]
        output[method] = sweet_spot_stats(subset)
    return output


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> Tuple[float, str]:
    """Compute Fisher's exact test p-value (one-sided, a/a+b > c/c+d).

    Uses exact hypergeometric probability. Returns (p_value, direction).
    Handles small tables analytically.
    """
    from math import comb

    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d

    # P(X=k) for hypergeometric
    def hyp_prob(k: int) -> float:
        return comb(r1, k) * comb(r2, c1 - k) / comb(n, c1)

    # One-sided p-value: P(X >= a) under H0
    p = sum(
        hyp_prob(k)
        for k in range(a, min(r1, c1) + 1)
        if 0 <= c1 - k <= r2
    )
    direction = "high_group_more_investigable" if a / (a + b) > c / (c + d) else "low_group_more_investigable"
    return round(p, 6), direction


def run_statistical_tests(records: List[Dict]) -> Dict:
    """Fisher's exact tests: novelty high vs low, and C2 vs C_rand sweet spot."""
    # Test 1: novelty high (≥0.6) vs low (<0.4) investigability
    high_nov = [r for r in records if r["combined_novelty"] >= 0.6]
    low_nov = [r for r in records if r["combined_novelty"] < 0.4]

    a = sum(r["investigated"] for r in high_nov)  # high nov, investigated
    b = len(high_nov) - a                          # high nov, not investigated
    c = sum(r["investigated"] for r in low_nov)    # low nov, investigated
    d = len(low_nov) - c                           # low nov, not investigated

    p1, dir1 = fisher_exact_2x2(a, b, c, d) if (a + b > 0 and c + d > 0) else (None, "n/a")

    # Test 2: C2 vs C_rand sweet spot rate
    c2 = [r for r in records if r["method"] == "C2_multi_op"]
    cr = [r for r in records if r["method"] == "C_rand_v2"]

    def sweet(recs: List[Dict]) -> Tuple[int, int]:
        n_sweet = sum(
            1 for r in recs
            if r["combined_novelty"] >= SWEET_SPOT_NOVELTY_MIN and r["investigated"] == 1
        )
        return n_sweet, len(recs) - n_sweet

    a2, b2 = sweet(c2)
    c2_n, d2 = sweet(cr)

    p2, dir2 = fisher_exact_2x2(a2, b2, c2_n, d2) if (a2 + b2 > 0 and c2_n + d2 > 0) else (None, "n/a")

    return {
        "test1_novelty_high_vs_low": {
            "description": "Investigability: novelty≥0.6 vs novelty<0.4 (Fisher one-sided)",
            "high_novelty_n": len(high_nov),
            "high_novelty_investigated": a,
            "high_novelty_rate": round(a / len(high_nov), 4) if high_nov else None,
            "low_novelty_n": len(low_nov),
            "low_novelty_investigated": c,
            "low_novelty_rate": round(c / len(low_nov), 4) if low_nov else None,
            "p_value_one_sided": p1,
            "direction": dir1,
            "significant_p05": p1 < 0.05 if p1 is not None else None,
        },
        "test2_c2_vs_crand_sweet_spot": {
            "description": "Sweet spot occupancy: C2 vs C_rand (Fisher one-sided)",
            "c2_sweet_spot": a2,
            "c2_not_sweet_spot": b2,
            "c2_sweet_spot_rate": round(a2 / (a2 + b2), 4) if (a2 + b2) > 0 else None,
            "crand_sweet_spot": c2_n,
            "crand_not_sweet_spot": d2,
            "crand_sweet_spot_rate": round(c2_n / (c2_n + d2), 4) if (c2_n + d2) > 0 else None,
            "p_value_one_sided": p2,
            "direction": dir2,
            "significant_p05": p2 < 0.05 if p2 is not None else None,
        },
    }


def ascii_bin_table(bin_analysis: Dict) -> str:
    """Render ASCII table of novelty bin × investigability rate by method."""
    methods = ["C2_multi_op", "C1_compose", "C_rand_v2"]
    header = f"{'Bin':<12} {'Overall':>10} {'C2':>10} {'C1':>10} {'C_rand':>10} {'C2_n':>6} {'C1_n':>6} {'Cr_n':>6}"
    sep = "-" * 72
    lines = [header, sep]
    for i, label in enumerate(BIN_LABELS):
        overall = bin_analysis["overall"][i]
        row = f"{label:<12} {_fmt_rate(overall['investigability_rate']):>10}"
        for m in methods:
            b = bin_analysis[m][i]
            row += f" {_fmt_rate(b['investigability_rate']):>10}"
        row += f" {bin_analysis['C2_multi_op'][i]['n']:>6}"
        row += f" {bin_analysis['C1_compose'][i]['n']:>6}"
        row += f" {bin_analysis['C_rand_v2'][i]['n']:>6}"
        lines.append(row)
    return "\n".join(lines)


def _fmt_rate(rate: Any) -> str:
    """Format rate or return N/A."""
    return f"{rate:.3f}" if rate is not None else "  N/A"


def generate_html_chart(records: List[Dict], output_path: str) -> None:
    """Generate interactive HTML scatter plot (novelty vs investigability)."""
    data_by_method = {}
    for r in records:
        m = r["method"]
        if m not in data_by_method:
            data_by_method[m] = []
        data_by_method[m].append({
            "x": r["combined_novelty"],
            "y": r["investigated"],
            "id": r["id"],
            "desc": r["description"][:60] + "...",
            "l1": r["label_layer1"],
            "l2": r["label_layer2"],
            "hits": r["past_pubmed_hits_le2023"],
        })

    colors = {"C2_multi_op": "#2196F3", "C1_compose": "#4CAF50", "C_rand_v2": "#FF5722"}

    js_datasets = []
    for method, pts in data_by_method.items():
        color = colors.get(method, "#999")
        pts_json = json.dumps(pts)
        js_datasets.append(
            f"{{label: '{method}', data: {pts_json}, backgroundColor: '{color}88', "
            f"borderColor: '{color}', pointRadius: 5}}"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>P3: Novelty-Investigability Tradeoff</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body {{ font-family: monospace; background: #1a1a2e; color: #eee; margin: 20px; }}
  h1 {{ color: #90caf9; }}
  .chart-wrap {{ max-width: 900px; background: #16213e; padding: 20px; border-radius: 8px; }}
  #tooltip-box {{ position: fixed; background: #0f3460; padding: 10px; border-radius: 4px;
    border: 1px solid #90caf9; display: none; max-width: 350px; font-size: 12px; z-index: 999; }}
</style>
</head>
<body>
<h1>P3: Novelty-Investigability Tradeoff (run_018, N=210)</h1>
<div class="chart-wrap">
  <canvas id="chart" width="860" height="500"></canvas>
</div>
<div id="tooltip-box"></div>
<script>
const ctx = document.getElementById('chart').getContext('2d');
const datasets = [{', '.join(js_datasets)}];

// Jitter y-axis for visibility
datasets.forEach(ds => {{
  ds.data = ds.data.map(p => ({{...p, y: p.y + (Math.random() - 0.5) * 0.04}}));
}});

const chart = new Chart(ctx, {{
  type: 'scatter',
  data: {{ datasets }},
  options: {{
    responsive: false,
    plugins: {{
      title: {{ display: true, text: 'Combined Novelty vs Investigated (jittered)', color: '#eee' }},
      legend: {{ labels: {{ color: '#eee' }} }},
      tooltip: {{
        callbacks: {{
          label: function(ctx) {{
            const p = ctx.raw;
            return [p.id, p.desc, 'L1: ' + p.l1, 'L2: ' + p.l2, 'hits≤2023: ' + p.hits];
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ title: {{ display: true, text: 'Combined Novelty Score', color: '#ccc' }},
           ticks: {{ color: '#ccc' }}, grid: {{ color: '#333' }}, min: 0, max: 1 }},
      y: {{ title: {{ display: true, text: 'Investigated (jittered)', color: '#ccc' }},
           ticks: {{ color: '#ccc' }}, grid: {{ color: '#333' }}, min: -0.1, max: 1.1 }}
    }}
  }}
}});
</script>
</body></html>
"""
    with open(output_path, "w") as f:
        f.write(html)


def save_run_config(output_dir: str) -> None:
    """Save run_019 config."""
    config = {
        "run_id": "run_019_novelty_tradeoff_analysis",
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": "P3: Novelty-investigability tradeoff analysis on run_018 N=210",
        "seed": 42,
        "source_run": "run_018_investigability_replication",
        "n_total": 210,
        "novelty_weights": NOVELTY_WEIGHTS,
        "sweet_spot_thresholds": {
            "investigability": SWEET_SPOT_INVESTIGABILITY_MIN,
            "novelty": SWEET_SPOT_NOVELTY_MIN,
        },
        "note_entity_popularity": (
            "entity_popularity_score uses existing past_pubmed_hits_le2023 "
            "from Layer 2 data (combined subject+object hits in ≤2023 corpus). "
            "This avoids redundant API calls and directly captures hypothesis-level "
            "prior literature density."
        ),
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(config, f, indent=2)


def main() -> None:
    """Run full P3 novelty-investigability tradeoff analysis."""
    os.makedirs(RUN_019_DIR, exist_ok=True)

    print("Loading data...")
    hypotheses = load_hypotheses()
    layer2 = load_layer2()

    print("Computing novelty scores...")
    records = build_novelty_records(hypotheses, layer2)

    print("Running bin analysis...")
    bin_analysis = run_bin_analysis(records)

    print("Running sweet spot analysis...")
    sweet_spot = run_sweet_spot_analysis(records)

    print("Running statistical tests...")
    stat_tests = run_statistical_tests(records)

    # Save JSON outputs
    save_run_config(RUN_019_DIR)

    with open(os.path.join(RUN_019_DIR, "novelty_scores.json"), "w") as f:
        json.dump(records, f, indent=2)

    with open(os.path.join(RUN_019_DIR, "bin_analysis.json"), "w") as f:
        json.dump(bin_analysis, f, indent=2)

    with open(os.path.join(RUN_019_DIR, "sweet_spot_analysis.json"), "w") as f:
        json.dump(sweet_spot, f, indent=2)

    with open(os.path.join(RUN_019_DIR, "statistical_tests.json"), "w") as f:
        json.dump(stat_tests, f, indent=2)

    # ASCII table
    table = ascii_bin_table(bin_analysis)
    print("\n=== Novelty Bin × Investigability Rate ===")
    print(table)

    # HTML chart
    html_path = os.path.join(RUN_019_DIR, "novelty_scatter.html")
    generate_html_chart(records, html_path)
    print(f"\nHTML chart saved: {html_path}")

    # Summary
    print("\n=== Sweet Spot Summary ===")
    for method in ["C2_multi_op", "C1_compose", "C_rand_v2"]:
        ss = sweet_spot[method]
        print(
            f"{method}: sweet_spot={ss['n_sweet_spot']}/{ss['n_total']} "
            f"({ss['sweet_spot_rate_of_total']:.3f}), "
            f"inv_in_high_novelty={ss['investigability_in_high_novelty']}"
        )

    print("\n=== Statistical Tests ===")
    t1 = stat_tests["test1_novelty_high_vs_low"]
    t2 = stat_tests["test2_c2_vs_crand_sweet_spot"]
    print(
        f"Test1 (high vs low novelty inv): "
        f"high={t1['high_novelty_rate']} ({t1['high_novelty_n']}), "
        f"low={t1['low_novelty_rate']} ({t1['low_novelty_n']}), "
        f"p={t1['p_value_one_sided']}, sig={t1['significant_p05']}"
    )
    print(
        f"Test2 (C2 vs C_rand sweet spot): "
        f"C2={t2['c2_sweet_spot_rate']}, C_rand={t2['crand_sweet_spot_rate']}, "
        f"p={t2['p_value_one_sided']}, sig={t2['significant_p05']}"
    )

    print(f"\nAll outputs saved to {RUN_019_DIR}/")


if __name__ == "__main__":
    main()
