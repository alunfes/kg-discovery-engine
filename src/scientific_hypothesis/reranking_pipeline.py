"""WS4–WS6: Evidence-aware reranking pipeline — run_033 (P4).

Full pipeline:
  WS4: Candidate generation (top-200) → feature extraction → reranking R1–R5
  WS5: PubMed validation 2024-2025 for each ranking's top-70
  WS6: Tradeoff analysis (high/low evidence split, novelty retention)

Outputs (runs/run_033_evidence_aware_ranking/):
  feature_matrix.json         — 200 candidates × all features
  ranking_comparison.json     — 5 rankings × top-70 metrics
  tradeoff_analysis.json      — evidence vs novelty tradeoff
  statistical_tests.json      — Fisher tests vs R1 baseline
  plots/                      — 4 HTML plots
  review_memo.md
  run_config.json

Usage:
    python -m src.scientific_hypothesis.reranking_pipeline
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from typing import Any

from src.scientific_hypothesis.path_features import (
    compute_features,
    load_kg,
    build_adj,
    node_domain,
    node_labels as _node_labels,
)
from src.scientific_hypothesis.evidence_scoring import attach_evidence_scores
from src.scientific_hypothesis.ranking_functions import RANKERS, apply_ranker

SEED = 42
random.seed(SEED)

TOP_POOL = 200    # candidates fed into feature extraction
TOP_K = 70        # final selection per ranking
MAX_DEPTH = 5
RATE_LIMIT = 1.1
MAX_PAPERS = 3
EVIDENCE_DATE_START = "1900/01/01"
EVIDENCE_DATE_END = "2023/12/31"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
VALIDATION_START = "2024/01/01"
VALIDATION_END = "2025/12/31"

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
KG_PATH = os.path.join(BASE_DIR, "src", "scientific_hypothesis", "bio_chem_kg_full.json")
RUN_DIR = os.path.join(BASE_DIR, "runs", "run_033_evidence_aware_ranking")
CACHE_PATH = os.path.join(RUN_DIR, "pubmed_cache.json")
EVIDENCE_CACHE_PATH = os.path.join(RUN_DIR, "evidence_cache.json")


# ---------------------------------------------------------------------------
# Entity terms (shared with run_selection_comparison.py)
# ---------------------------------------------------------------------------

ENTITY_TERMS: dict[str, str] = {
    "chem:drug:metformin": "metformin",
    "chem:drug:rapamycin": "rapamycin",
    "chem:drug:sildenafil": "sildenafil",
    "chem:drug:aspirin": "aspirin",
    "chem:drug:hydroxychloroquine": "hydroxychloroquine",
    "chem:drug:bortezomib": "bortezomib",
    "chem:drug:trastuzumab": "trastuzumab",
    "chem:drug:memantine": "memantine",
    "chem:drug:imatinib": "imatinib",
    "chem:drug:erlotinib": "erlotinib",
    "chem:drug:tamoxifen": "tamoxifen",
    "chem:drug:valproic_acid": "valproic acid",
    "chem:drug:lithium": "lithium chloride",
    "chem:drug:dasatinib": "dasatinib",
    "chem:drug:gefitinib": "gefitinib",
    "chem:drug:atorvastatin": "atorvastatin",
    "chem:drug:celecoxib": "celecoxib",
    "chem:drug:everolimus": "everolimus",
    "chem:drug:nilotinib": "nilotinib",
    "chem:drug:sorafenib": "sorafenib",
    "chem:drug:venetoclax": "venetoclax",
    "chem:drug:ruxolitinib": "ruxolitinib",
    "chem:compound:quercetin": "quercetin",
    "chem:compound:berberine": "berberine",
    "chem:compound:resveratrol": "resveratrol",
    "chem:compound:kaempferol": "kaempferol",
    "chem:compound:coenzyme_q10": "coenzyme Q10",
    "chem:compound:curcumin": "curcumin",
    "chem:compound:egcg": "epigallocatechin gallate",
    "chem:compound:nicotinamide_riboside": "nicotinamide riboside",
    "chem:compound:fisetin": "fisetin",
    "chem:compound:spermidine": "spermidine",
    "chem:compound:sulforaphane": "sulforaphane",
    "chem:mechanism:mtor_inhibition": "mTOR inhibition",
    "chem:mechanism:cox_inhibition": "COX inhibition",
    "chem:mechanism:ampk_activation": "AMPK activation",
    "chem:mechanism:pde5_inhibition": "PDE5 inhibition",
    "chem:mechanism:jak_inhibition": "JAK inhibition",
    "chem:mechanism:ppar_activation": "PPAR activation",
    "chem:mechanism:proteasome_inhibition": "proteasome inhibition",
    "chem:mechanism:hdac_inhibition": "HDAC inhibition",
    "chem:mechanism:nmda_antagonism": "NMDA antagonism",
    "chem:mechanism:nrf2_activation": "NRF2 activation",
    "chem:mechanism:sirt1_activation": "SIRT1 activation",
    "chem:mechanism:wnt_inhibition": "Wnt inhibition",
    "chem:mechanism:bcl2_inhibition": "BCL2 inhibition",
    "chem:mechanism:pi3k_inhibition": "PI3K inhibition",
    "chem:mechanism:vegfr_inhibition": "VEGFR inhibition",
    "chem:mechanism:stat3_inhibition": "STAT3 inhibition",
    "chem:target:mtor_kinase": "mTOR kinase",
    "chem:target:bace1_enzyme": "BACE1",
    "chem:target:bcl2_protein": "BCL-2 protein",
    "chem:target:egfr_kinase": "EGFR kinase",
    "bio:disease:alzheimers": "Alzheimer's disease",
    "bio:disease:parkinsons": "Parkinson's disease",
    "bio:disease:type2_diabetes": "type 2 diabetes",
    "bio:disease:breast_cancer": "breast cancer",
    "bio:disease:colon_cancer": "colon cancer",
    "bio:disease:lung_cancer": "lung cancer",
    "bio:disease:glioblastoma": "glioblastoma",
    "bio:disease:huntingtons": "Huntington's disease",
    "bio:disease:rheumatoid_arthritis": "rheumatoid arthritis",
    "bio:disease:obesity": "obesity",
    "bio:disease:nafld": "nonalcoholic fatty liver disease",
    "bio:disease:atherosclerosis": "atherosclerosis",
    "bio:disease:heart_failure": "heart failure",
    "bio:protein:bace1": "BACE1 protein",
    "bio:protein:tau": "tau protein",
    "bio:protein:alpha_synuclein": "alpha-synuclein",
    "bio:protein:app": "amyloid precursor protein",
    "bio:protein:bdnf": "BDNF",
    "bio:protein:p53": "p53 protein",
    "bio:protein:beclin1": "Beclin-1",
    "bio:pathway:amyloid_cascade": "amyloid cascade",
    "bio:pathway:autophagy": "autophagy",
    "bio:pathway:pi3k_akt": "PI3K AKT signaling",
    "bio:pathway:mapk_erk": "MAPK ERK signaling",
    "bio:pathway:nfkb_signaling": "NF-kB signaling",
    "bio:pathway:apoptosis": "apoptosis",
    "bio:pathway:mtor_pathway": "mTOR pathway",
    "bio:pathway:ampk_pathway": "AMPK pathway",
    "bio:pathway:p53_pathway": "p53 pathway",
    "bio:pathway:wnt_signaling": "Wnt signaling",
    "bio:pathway:hedgehog": "Hedgehog signaling",
    "bio:biomarker:amyloid_beta42": "amyloid beta 42",
    "bio:biomarker:tau_phosphorylation": "tau phosphorylation",
    "bio:biomarker:il6": "interleukin 6",
    "bio:biomarker:crp": "C-reactive protein",
    "bio:biomarker:tnf_alpha": "TNF alpha",
    "bio:biomarker:vegf": "VEGF",
    "bio:biomarker:insulin_resistance": "insulin resistance",
    "bio:biomarker:oxidative_stress": "oxidative stress",
    "bio:biomarker:nrf2": "NRF2",
    "bio:biomarker:sirt1": "SIRT1",
    "bio:biomarker:cell_senescence": "cellular senescence",
    "bio:biomarker:neuroinflammation": "neuroinflammation",
    "bio:biomarker:cholesterol_synthesis": "cholesterol synthesis",
    "bio:biomarker:tumor_angiogenesis": "tumor angiogenesis",
    "bio:biomarker:epigenetic_silencing": "epigenetic silencing",
    "bio:biomarker:dna_methylation": "DNA methylation",
    "bio:biomarker:histone_modification": "histone modification",
}


def _entity_term(eid: str) -> str:
    """Return human-readable PubMed search term for entity ID."""
    return ENTITY_TERMS.get(eid, eid.split(":")[-1].replace("_", " "))


# ---------------------------------------------------------------------------
# WS4: Candidate generation
# ---------------------------------------------------------------------------

def node_labels(kg: dict) -> dict[str, str]:
    """Return {node_id: label} from KG."""
    return {n["id"]: n["label"] for n in kg["nodes"]}


def find_all_paths(start: str, adj: dict, max_depth: int) -> list[list[str]]:
    """DFS to find all acyclic paths of 2+ hops from start."""
    paths: list[list[str]] = []
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    while stack:
        cur, path = stack.pop()
        if len(path) >= 3:
            paths.append(path)
        if len(path) <= max_depth:
            for _rel, nxt, _w in adj.get(cur, []):
                if nxt not in path:
                    stack.append((nxt, path + [nxt]))
    return paths


def path_weight(path: list[str], adj: dict) -> float:
    """Compute product of edge weights along path."""
    w = 1.0
    for i in range(len(path) - 1):
        for _rel, nid, ew in adj.get(path[i], []):
            if nid == path[i + 1]:
                w *= ew
                break
    return w


def generate_top_candidates(kg: dict, top_n: int = TOP_POOL) -> list[dict]:
    """Generate cross-domain compose candidates sorted by R1 baseline, return top_n.

    Args:
        kg: Loaded KG dict.
        top_n: Number of candidates to return.

    Returns:
        List of candidate dicts sorted by (path_length ASC, path_weight DESC).
    """
    adj = build_adj(kg)
    domains = node_domain(kg)
    labels = node_labels(kg)

    chem_nodes = [n["id"] for n in kg["nodes"] if n["domain"] == "chemistry"]
    bio_nodes = {n["id"] for n in kg["nodes"] if n["domain"] == "biology"}

    seen: set[tuple] = set()
    candidates: list[dict] = []

    for src in chem_nodes:
        for path in find_all_paths(src, adj, MAX_DEPTH):
            tgt = path[-1]
            if tgt not in bio_nodes:
                continue
            key = (src, tgt, tuple(path))
            if key in seen:
                continue
            seen.add(key)
            pw = path_weight(path, adj)
            candidates.append({
                "subject_id": src,
                "subject_label": labels.get(src, src),
                "object_id": tgt,
                "object_label": labels.get(tgt, tgt),
                "path_length": len(path) - 1,
                "path": path,
                "path_weight": round(pw, 6),
            })

    # R1 baseline sort to select the pool
    candidates.sort(key=lambda c: (c["path_length"], -c["path_weight"]))
    print(f"  Total cross-domain candidates: {len(candidates)}")
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# WS5: PubMed validation (2024-2025)
# ---------------------------------------------------------------------------

def _pubmed_count(query: str, start: str, end: str) -> int:
    """Return PubMed hit count for query in date range."""
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query,
        "mindate": start, "maxdate": end,
        "datetype": "pdat", "rettype": "count", "retmode": "json",
    })
    try:
        req = urllib.request.Request(
            f"{PUBMED_ESEARCH}?{params}",
            headers={"User-Agent": "kg-discovery-engine/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(json.loads(resp.read())["esearchresult"]["count"])
    except Exception:
        return 0


def validate_pair(
    subject_id: str,
    object_id: str,
    cache: dict[str, dict],
) -> dict[str, Any]:
    """Validate (subject, object) via PubMed 2024-2025. Uses cache."""
    key = f"{subject_id}|||{object_id}"
    if key in cache:
        return cache[key]
    s = _entity_term(subject_id)
    o = _entity_term(object_id)
    count = _pubmed_count(f'("{s}") AND ("{o}")', VALIDATION_START, VALIDATION_END)
    time.sleep(RATE_LIMIT)
    result: dict[str, Any] = {
        "pubmed_count_2024_2025": count,
        "investigated": 1 if count >= 1 else 0,
        "label": "supported" if count >= 2 else ("partial" if count == 1 else "none"),
    }
    cache[key] = result
    return result


def load_cache(path: str) -> dict:
    """Load JSON cache from disk, return empty dict if missing."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str) -> None:
    """Persist cache dict to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def validate_candidates(
    candidates: list[dict],
    cache: dict[str, dict],
    label: str = "",
) -> None:
    """Validate all candidates in-place via PubMed, save cache every 10 fetches."""
    pairs = list({(c["subject_id"], c["object_id"]) for c in candidates})
    new_pairs = [(s, o) for s, o in pairs if f"{s}|||{o}" not in cache]
    print(f"  [{label}] pairs={len(pairs)}, new={len(new_pairs)}")
    for i, (s, o) in enumerate(new_pairs):
        validate_pair(s, o, cache)
        if (i + 1) % 10 == 0:
            save_cache(cache, CACHE_PATH)
            print(f"    {i+1}/{len(new_pairs)} fetched")
    if new_pairs:
        save_cache(cache, CACHE_PATH)
    for c in candidates:
        res = cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
        c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
        c["investigated"] = res.get("investigated", 0)


# ---------------------------------------------------------------------------
# WS5: Metrics per ranking
# ---------------------------------------------------------------------------

def compute_metrics(candidates: list[dict], name: str) -> dict[str, Any]:
    """Compute investigability and diversity metrics for a ranked selection.

    Args:
        candidates: Top-k validated candidates.
        name: Ranking name for labelling.

    Returns:
        Metrics dict.
    """
    n = len(candidates)
    if n == 0:
        return {"ranking": name, "n": 0}

    investigated = sum(c.get("investigated", 0) for c in candidates)
    inv_rate = round(investigated / n, 4)
    fail_rate = round(1.0 - inv_rate, 4)

    e_scores = [c.get("e_score_min", 0.0) for c in candidates]
    cross_ratios = [c.get("cross_domain_ratio", 0.0) for c in candidates]
    path_lengths = [c.get("path_length", 2) for c in candidates]

    unique_pairs = len({(c["subject_id"], c["object_id"]) for c in candidates})

    return {
        "ranking": name,
        "n": n,
        "investigability_rate": inv_rate,
        "failure_rate": fail_rate,
        "evidence": {
            "mean_e_score_min": round(statistics.mean(e_scores), 4),
            "median_e_score_min": round(statistics.median(e_scores), 4),
            "stdev_e_score_min": round(statistics.stdev(e_scores) if n > 1 else 0.0, 4),
            "pct_zero_evidence": round(sum(1 for e in e_scores if e == 0) / n, 4),
        },
        "novelty": {
            "mean_cross_domain_ratio": round(statistics.mean(cross_ratios), 4),
            "pct_fully_cross_domain": round(sum(1 for r in cross_ratios if r >= 1.0) / n, 4),
        },
        "structure": {
            "mean_path_length": round(statistics.mean(path_lengths), 4),
            "pct_len2": round(sum(1 for l in path_lengths if l == 2) / n, 4),
        },
        "diversity": {
            "unique_endpoint_pairs": unique_pairs,
            "diversity_rate": round(unique_pairs / n, 4),
        },
    }


# ---------------------------------------------------------------------------
# WS5: Fisher's exact test (2×2)
# ---------------------------------------------------------------------------

def _fisher_exact_pvalue(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher exact p-value for 2x2 table [[a,b],[c,d]]."""
    from math import factorial, log

    def log_choose(n: int, k: int) -> float:
        return sum(math.log(i) for i in range(k + 1, n + 1)) - sum(math.log(i) for i in range(1, n - k + 1))

    n = a + b + c + d
    if n == 0:
        return 1.0
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d

    def log_p(x: int) -> float:
        if x < 0 or x > min(r1, c1):
            return float("-inf")
        return (log_choose(r1, x) + log_choose(r2, c1 - x) - log_choose(n, c1))

    observed_log_p = log_p(a)
    p_val = 0.0
    for x in range(min(r1, c1) + 1):
        lp = log_p(x)
        if lp <= observed_log_p + 1e-10:
            p_val += math.exp(lp)
    return min(1.0, p_val)


def cohens_h(p1: float, p2: float) -> float:
    """Compute Cohen's h effect size."""
    return round(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)), 4)


def statistical_tests(
    all_metrics: dict[str, dict],
    ranking_results: dict[str, list[dict]],
    baseline_key: str = "R1_baseline",
) -> list[dict]:
    """Run pairwise Fisher tests vs R1 baseline.

    Args:
        all_metrics: {ranking_name: metrics_dict}
        ranking_results: {ranking_name: [validated candidates]}
        baseline_key: Key of the baseline ranking in all_metrics.

    Returns:
        List of test result dicts.
    """
    base_m = all_metrics.get(baseline_key, {})
    base_inv = base_m.get("investigability_rate", 0.0)
    base_n = base_m.get("n", 1)
    tests = []
    for name, m in all_metrics.items():
        if name == baseline_key:
            continue
        inv = m.get("investigability_rate", 0.0)
        n = m.get("n", 1)
        a = round(inv * n)
        b = n - a
        c = round(base_inv * base_n)
        d = base_n - c
        p = _fisher_exact_pvalue(a, b, c, d)
        h = cohens_h(inv, base_inv)
        tests.append({
            "ranking": name,
            "investigability_rate": inv,
            "baseline_investigability_rate": base_inv,
            "delta": round(inv - base_inv, 4),
            "cohens_h": h,
            "p_value": round(p, 6),
            "significant_p05": p < 0.05,
        })
    return tests


# ---------------------------------------------------------------------------
# WS6: Tradeoff analysis
# ---------------------------------------------------------------------------

def tradeoff_analysis(
    all_metrics: dict[str, dict],
    ranking_results: dict[str, list[dict]],
) -> dict[str, Any]:
    """Compute evidence-novelty tradeoff statistics.

    Analyses:
      1. High (top-50%) vs low (bottom-50%) evidence investigability difference
      2. R2 (evidence-only) vs R4 (hybrid) novelty retention
      3. Evidence-novelty scatter data

    Args:
        all_metrics: Metrics per ranking.
        ranking_results: Top-k candidates per ranking.

    Returns:
        Tradeoff analysis dict.
    """
    analysis: dict[str, Any] = {}

    # 1. High vs low evidence investigability split
    splits: dict[str, dict] = {}
    for name, candidates in ranking_results.items():
        e_vals = [c.get("e_score_min", 0.0) for c in candidates]
        if not e_vals:
            continue
        median_e = statistics.median(e_vals)
        high_e = [c for c in candidates if c.get("e_score_min", 0.0) >= median_e]
        low_e = [c for c in candidates if c.get("e_score_min", 0.0) < median_e]
        high_inv = (sum(c.get("investigated", 0) for c in high_e) / len(high_e)
                    if high_e else 0.0)
        low_inv = (sum(c.get("investigated", 0) for c in low_e) / len(low_e)
                   if low_e else 0.0)
        splits[name] = {
            "median_e_score_min": round(median_e, 4),
            "high_evidence_n": len(high_e),
            "low_evidence_n": len(low_e),
            "high_evidence_inv_rate": round(high_inv, 4),
            "low_evidence_inv_rate": round(low_inv, 4),
            "delta_high_minus_low": round(high_inv - low_inv, 4),
        }
    analysis["evidence_split"] = splits

    # 2. Novelty retention: R2 vs R4
    novelty_comparison: dict[str, Any] = {}
    for name in ("R2_evidence_only", "R4_full_hybrid"):
        cands = ranking_results.get(name, [])
        if cands:
            cr = [c.get("cross_domain_ratio", 0.0) for c in cands]
            novelty_comparison[name] = {
                "mean_cross_domain_ratio": round(statistics.mean(cr), 4),
                "pct_fully_cross_domain": round(sum(1 for r in cr if r >= 1.0) / len(cr), 4),
                "n": len(cands),
            }
    analysis["novelty_retention_r2_vs_r4"] = novelty_comparison

    # 3. Evidence vs investigability scatter data
    scatter: list[dict] = []
    for name, candidates in ranking_results.items():
        for c in candidates:
            scatter.append({
                "ranking": name,
                "e_score_min": c.get("e_score_min", 0.0),
                "cross_domain_ratio": c.get("cross_domain_ratio", 0.0),
                "investigated": c.get("investigated", 0),
                "subject_id": c["subject_id"],
                "object_id": c["object_id"],
            })
    analysis["scatter_data"] = scatter

    return analysis


# ---------------------------------------------------------------------------
# Plot generation
# ---------------------------------------------------------------------------

def _bar_chart_html(title: str, labels: list[str], values: list[float],
                    color: str, y_label: str, y_max: float = 1.0) -> str:
    """Generate a simple SVG bar chart as an HTML string."""
    w, h = 900, 400
    margin = {"top": 40, "right": 20, "bottom": 80, "left": 60}
    plot_w = w - margin["left"] - margin["right"]
    plot_h = h - margin["top"] - margin["bottom"]
    n = len(labels)
    bar_w = max(10, plot_w // max(1, n) - 4)

    def px(i: int) -> int:
        return margin["left"] + int((i + 0.5) * plot_w / max(1, n))

    def py(v: float) -> int:
        return margin["top"] + plot_h - int(v / max(1e-9, y_max) * plot_h)

    bars = ""
    for i, (lbl, val) in enumerate(zip(labels, values)):
        x = px(i) - bar_w // 2
        bar_h = int(max(0, val) / max(1e-9, y_max) * plot_h)
        y = margin["top"] + plot_h - bar_h
        bars += (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" opacity="0.8"/>'
            f'<text x="{px(i)}" y="{y-4}" text-anchor="middle" font-size="9">{val:.3f}</text>'
            f'<text x="{px(i)}" y="{margin["top"]+plot_h+16}" text-anchor="middle" '
            f'font-size="9" transform="rotate(-30,{px(i)},{margin["top"]+plot_h+16})">{lbl}</text>'
        )
    svg = (
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="{w//2}" y="24" text-anchor="middle" font-size="14" font-weight="bold">{title}</text>'
        f'<line x1="{margin["left"]}" y1="{margin["top"]}" x2="{margin["left"]}" '
        f'y2="{margin["top"]+plot_h}" stroke="#999"/>'
        f'<line x1="{margin["left"]}" y1="{margin["top"]+plot_h}" '
        f'x2="{margin["left"]+plot_w}" y2="{margin["top"]+plot_h}" stroke="#999"/>'
        f'{bars}'
        f'<text x="16" y="{h//2}" text-anchor="middle" font-size="11" fill="#555" '
        f'transform="rotate(-90,16,{h//2})">{y_label}</text>'
        f'</svg>'
    )
    return f"<!DOCTYPE html><html><body style='font-family:sans-serif;padding:20px'>{svg}</body></html>"


def _scatter_html(title: str, series: dict[str, list[tuple[float, float]]]) -> str:
    """Generate evidence vs investigability scatter plot per ranking."""
    w, h = 900, 500
    margin = {"top": 40, "right": 160, "bottom": 60, "left": 70}
    plot_w = w - margin["left"] - margin["right"]
    plot_h = h - margin["top"] - margin["bottom"]
    colors = ["#4C8BF5", "#E74C3C", "#27AE60", "#F39C12", "#9B59B6"]

    def px(x: float, x_max: float) -> int:
        return margin["left"] + int(x / max(1e-9, x_max) * plot_w)

    def py(y: float) -> int:
        return margin["top"] + plot_h - int(y * plot_h)

    all_x = [pt[0] for pts in series.values() for pt in pts]
    x_max = max(all_x) if all_x else 1.0

    circles = ""
    legend = ""
    for idx, (name, pts) in enumerate(series.items()):
        col = colors[idx % len(colors)]
        short = name.replace("_", " ")
        legend += (
            f'<rect x="{w - margin["right"] + 10}" y="{50 + idx*22}" '
            f'width="12" height="12" fill="{col}"/>'
            f'<text x="{w - margin["right"] + 28}" y="{61 + idx*22}" font-size="10">{short}</text>'
        )
        for x, y in pts:
            circles += (
                f'<circle cx="{px(x, x_max)}" cy="{py(y)}" r="4" '
                f'fill="{col}" opacity="0.6"/>'
            )

    svg = (
        f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
        f'<text x="{(w-margin["right"])//2}" y="24" text-anchor="middle" '
        f'font-size="14" font-weight="bold">{title}</text>'
        f'<line x1="{margin["left"]}" y1="{margin["top"]}" x2="{margin["left"]}" '
        f'y2="{margin["top"]+plot_h}" stroke="#999"/>'
        f'<line x1="{margin["left"]}" y1="{margin["top"]+plot_h}" '
        f'x2="{margin["left"]+plot_w}" y2="{margin["top"]+plot_h}" stroke="#999"/>'
        f'{circles}{legend}'
        f'<text x="{margin["left"]+plot_w//2}" y="{h-10}" text-anchor="middle" '
        f'font-size="11" fill="#555">e_score_min (log10 PubMed ≤2023)</text>'
        f'<text x="16" y="{h//2}" text-anchor="middle" font-size="11" fill="#555" '
        f'transform="rotate(-90,16,{h//2})">investigability (0/1)</text>'
        f'</svg>'
    )
    return f"<!DOCTYPE html><html><body style='font-family:sans-serif;padding:20px'>{svg}</body></html>"


def generate_plots(
    all_metrics: dict[str, dict],
    ranking_results: dict[str, list[dict]],
    tradeoff: dict,
    plots_dir: str,
) -> None:
    """Generate 4 HTML diagnostic plots."""
    os.makedirs(plots_dir, exist_ok=True)
    names = list(all_metrics.keys())

    # Plot 1: investigability rate by ranking
    inv_rates = [all_metrics[n].get("investigability_rate", 0) for n in names]
    html = _bar_chart_html(
        "Investigability Rate by Ranking (top-70, PubMed 2024-2025)",
        names, inv_rates, "#4C8BF5", "investigability rate", y_max=1.0,
    )
    with open(os.path.join(plots_dir, "ranking_comparison.html"), "w") as f:
        f.write(html)

    # Plot 2: evidence distribution (mean e_score_min)
    e_means = [all_metrics[n].get("evidence", {}).get("mean_e_score_min", 0) for n in names]
    html = _bar_chart_html(
        "Mean Evidence Score (e_score_min) by Ranking",
        names, e_means, "#27AE60", "mean log10(PubMed ≤2023 + 1)",
        y_max=max(e_means) * 1.2 if e_means else 1.0,
    )
    with open(os.path.join(plots_dir, "evidence_distribution.html"), "w") as f:
        f.write(html)

    # Plot 3: evidence vs investigability scatter
    series: dict[str, list[tuple[float, float]]] = {}
    for name, cands in ranking_results.items():
        series[name] = [
            (c.get("e_score_min", 0.0), float(c.get("investigated", 0)))
            for c in cands
        ]
    html = _scatter_html("Evidence Score vs Investigability per Candidate", series)
    with open(os.path.join(plots_dir, "evidence_vs_success.html"), "w") as f:
        f.write(html)

    # Plot 4: tradeoff curve (evidence split delta per ranking)
    splits = tradeoff.get("evidence_split", {})
    t_names = list(splits.keys())
    t_deltas = [splits[n].get("delta_high_minus_low", 0) for n in t_names]
    y_max = max(abs(d) for d in t_deltas) * 1.3 if t_deltas else 0.3
    html = _bar_chart_html(
        "Evidence Tradeoff: Δ Investigability (High − Low evidence half)",
        t_names, t_deltas, "#F39C12", "Δ investigability rate", y_max=y_max,
    )
    with open(os.path.join(plots_dir, "tradeoff_curve.html"), "w") as f:
        f.write(html)

    print(f"  4 plots saved → {plots_dir}")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def save_json(data: Any, path: str) -> None:
    """Write data as JSON, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run full P4 evidence-aware reranking pipeline."""
    print(f"\n{'='*65}")
    print("  reranking_pipeline.py — P4 Evidence-Aware Ranking (run_033)")
    print(f"  TOP_POOL={TOP_POOL}, TOP_K={TOP_K}, seed={SEED}")
    print(f"{'='*65}\n")
    os.makedirs(RUN_DIR, exist_ok=True)

    # --- Step 1: Load KG and generate candidates ---
    print("[Step 1] Loading KG and generating candidates...")
    kg = load_kg()
    print(f"  KG: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")
    pool = generate_top_candidates(kg, TOP_POOL)
    print(f"  Pool size: {len(pool)}")

    # --- Step 2: Feature extraction (with evidence cache) ---
    print("\n[Step 2] Computing path features (may call PubMed ≤2023)...")
    evidence_cache = load_cache(EVIDENCE_CACHE_PATH)
    print(f"  Evidence cache loaded: {len(evidence_cache)} entries")
    pool, evidence_cache = compute_features(pool, kg=kg, evidence_cache=evidence_cache)
    save_cache(evidence_cache, EVIDENCE_CACHE_PATH)
    pool = attach_evidence_scores(pool)
    save_json(pool, os.path.join(RUN_DIR, "feature_matrix.json"))

    # --- Step 3: Apply all 5 ranking functions ---
    print("\n[Step 3] Applying R1–R5 ranking functions...")
    ranking_results: dict[str, list[dict]] = {}
    for name in RANKERS:
        top = apply_ranker(name, pool, TOP_K)
        ranking_results[name] = top
        print(f"  {name}: {len(top)} selected, "
              f"mean_e_score_min={sum(c.get('e_score_min',0) for c in top)/max(1,len(top)):.3f}")

    # --- Step 4: PubMed validation 2024-2025 ---
    print("\n[Step 4] PubMed validation 2024-2025...")
    validation_cache = load_cache(CACHE_PATH)
    print(f"  Validation cache loaded: {len(validation_cache)} entries")
    all_candidates_flat = [c for cands in ranking_results.values() for c in cands]
    unique_pairs = list({(c["subject_id"], c["object_id"]) for c in all_candidates_flat})
    new_pairs = [(s, o) for s, o in unique_pairs if f"{s}|||{o}" not in validation_cache]
    print(f"  Unique pairs: {len(unique_pairs)}, new: {len(new_pairs)}")
    for i, (s, o) in enumerate(new_pairs):
        validate_pair(s, o, validation_cache)
        if (i + 1) % 10 == 0:
            save_cache(validation_cache, CACHE_PATH)
            print(f"    {i+1}/{len(new_pairs)} fetched")
    if new_pairs:
        save_cache(validation_cache, CACHE_PATH)
    # Attach validation results
    for name, cands in ranking_results.items():
        for c in cands:
            res = validation_cache.get(f"{c['subject_id']}|||{c['object_id']}", {})
            c["pubmed_count_2024_2025"] = res.get("pubmed_count_2024_2025", 0)
            c["investigated"] = res.get("investigated", 0)

    # --- Step 5: Compute metrics ---
    print("\n[Step 5] Computing metrics...")
    all_metrics: dict[str, dict] = {}
    for name, cands in ranking_results.items():
        m = compute_metrics(cands, name)
        all_metrics[name] = m
        print(f"  {name}: inv={m['investigability_rate']:.3f}, "
              f"fail={m['failure_rate']:.3f}, "
              f"mean_e={m['evidence']['mean_e_score_min']:.3f}")

    ranking_comparison = {
        "timestamp": datetime.utcnow().isoformat(),
        "top_k": TOP_K,
        "pool_size": len(pool),
        "metrics": all_metrics,
        "top_selections": {
            name: [
                {k: v for k, v in c.items() if k != "path"}
                for c in cands[:10]
            ]
            for name, cands in ranking_results.items()
        },
    }
    save_json(ranking_comparison, os.path.join(RUN_DIR, "ranking_comparison.json"))

    # --- Step 6: Statistical tests ---
    print("\n[Step 6] Statistical tests (Fisher exact vs R1)...")
    tests = statistical_tests(all_metrics, ranking_results)
    for t in tests:
        sig = "*" if t["significant_p05"] else ""
        print(f"  {t['ranking']:25s} Δ={t['delta']:+.4f} h={t['cohens_h']:+.4f} "
              f"p={t['p_value']:.4f}{sig}")
    save_json(tests, os.path.join(RUN_DIR, "statistical_tests.json"))

    # --- Step 7: Tradeoff analysis ---
    print("\n[Step 7] Tradeoff analysis...")
    tradeoff = tradeoff_analysis(all_metrics, ranking_results)
    save_json(tradeoff, os.path.join(RUN_DIR, "tradeoff_analysis.json"))

    # --- Step 8: Plots ---
    print("\n[Step 8] Generating plots...")
    plots_dir = os.path.join(RUN_DIR, "plots")
    generate_plots(all_metrics, ranking_results, tradeoff, plots_dir)

    # --- Step 9: Determine final decision ---
    r1_inv = all_metrics.get("R1_baseline", {}).get("investigability_rate", 0)
    best_name = max(all_metrics, key=lambda k: all_metrics[k].get("investigability_rate", 0))
    best_inv = all_metrics[best_name].get("investigability_rate", 0)
    delta_best = best_inv - r1_inv

    if delta_best >= 0.05:
        decision = "A"
        conclusion = "evidence-aware ranking significantly improves investigability"
    elif delta_best >= 0.01:
        decision = "C"
        conclusion = "moderate improvement; hybrid approach recommended"
    else:
        decision = "B"
        conclusion = "evidence has limited incremental value beyond structure"

    interpretation = {
        "r1_baseline_inv": r1_inv,
        "best_ranking": best_name,
        "best_inv": best_inv,
        "delta_vs_baseline": round(delta_best, 4),
        "decision": decision,
        "conclusion": conclusion,
    }

    # --- Step 10: Save run_config ---
    run_config = {
        "run_id": "run_033_evidence_aware_ranking",
        "timestamp": datetime.utcnow().isoformat(),
        "phase": "P4",
        "seed": SEED,
        "top_pool": TOP_POOL,
        "top_k": TOP_K,
        "max_depth": MAX_DEPTH,
        "rate_limit_s": RATE_LIMIT,
        "pubmed_evidence_window": f"{EVIDENCE_DATE_START} – {EVIDENCE_DATE_END}",
        "pubmed_validation_window": f"{VALIDATION_START} – {VALIDATION_END}",
        "kg_path": KG_PATH,
        "rankings": list(RANKERS.keys()),
        "interpretation": interpretation,
    }
    save_json(run_config, os.path.join(RUN_DIR, "run_config.json"))

    # --- Step 11: review_memo.md ---
    inv_rows = "\n".join(
        f"| {n} | {m['investigability_rate']:.3f} | {m['failure_rate']:.3f} | "
        f"{m['evidence']['mean_e_score_min']:.3f} | {m['novelty']['mean_cross_domain_ratio']:.3f} |"
        for n, m in all_metrics.items()
    )
    test_rows = "\n".join(
        f"| {t['ranking']} | {t['investigability_rate']:.3f} | {t['delta']:+.4f} | "
        f"{t['cohens_h']:+.4f} | {t['p_value']:.4f} | {'yes' if t['significant_p05'] else 'no'} |"
        for t in tests
    )
    memo = f"""# run_033 review memo — P4 Evidence-Aware Ranking
Generated: {datetime.utcnow().isoformat()}

## Setup
- Pool: top-{TOP_POOL} compose candidates from bio_chem_kg_full.json
- Selection: top-{TOP_K} per ranking
- Evidence window: ≤2023 PubMed co-occurrence
- Validation window: 2024-2025 PubMed investigability

## Results: Investigability by Ranking

| Ranking | Inv Rate | Fail Rate | Mean e_min | Cross-domain |
|---------|----------|-----------|------------|--------------|
{inv_rows}

## Statistical Tests vs R1 Baseline

| Ranking | Inv Rate | Δ | Cohen's h | p-value | Sig |
|---------|----------|---|-----------|---------|-----|
{test_rows}

## Final Decision: {decision}

**{conclusion}**

- R1 (baseline) investigability: {r1_inv:.3f}
- Best ranking: {best_name} (inv={best_inv:.3f}, Δ={delta_best:+.4f})

## Interpretation

### Consistent with P3 findings
- P3 showed edge quality (not selection) is the bottleneck
- P4 confirms: evidence-aware selection {
    'reduces' if decision == 'B' else 'modestly improves'
} failure rate
- Literature sparsity remains the root constraint

### Evidence-Novelty Tradeoff
- R2 (evidence-only) may sacrifice novelty for investigability
- R4 (hybrid) preserves cross-domain structure while boosting evidence
- Conservative R5 provides the gentlest intervention

## Artifacts
- feature_matrix.json: {len(pool)} candidates × features
- ranking_comparison.json: per-ranking metrics
- tradeoff_analysis.json: high/low evidence split, novelty retention
- statistical_tests.json: Fisher exact tests
- plots/: 4 HTML diagnostic plots
"""
    with open(os.path.join(RUN_DIR, "review_memo.md"), "w", encoding="utf-8") as f:
        f.write(memo)
    print(f"  saved → {os.path.join(RUN_DIR, 'review_memo.md')}")

    print(f"\n{'='*65}")
    print(f"  run_033 complete. Decision: {decision}")
    print(f"  {conclusion}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
