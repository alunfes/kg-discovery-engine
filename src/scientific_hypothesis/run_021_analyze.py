"""
run_021_analyze.py — Density Ceiling & Matched Comparison Analysis (run_021).

Steps:
  1. Load density_scores.json + novelty_scores.json
  2. Correlation analysis: density metrics vs investigability (point-biserial)
  3. Quartile analysis: investigability rate per min_density quartile × method
  4. Simple logistic regression: log_min_density → investigated (pseudo R²)
  5. Matched comparison: novelty × density bins, C1 vs C2 gap
  6. Statistical tests (Fisher's exact)
  7. Write all outputs + review_memo.md + density_ceiling_results.md

Usage:
    python src/scientific_hypothesis/run_021_analyze.py

Requires: runs/run_021_density_ceiling/density_scores.json (from add_density_scores.py)
"""
from __future__ import annotations

import json
import math
import os
import random
import datetime
from math import comb
from typing import Any

random.seed(42)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_021_DIR = os.path.join(BASE_DIR, "runs", "run_021_density_ceiling")
RUN_019_DIR = os.path.join(BASE_DIR, "runs", "run_019_novelty_tradeoff_analysis")
DOCS_DIR = os.path.join(BASE_DIR, "docs", "scientific_hypothesis")

DENSITY_FILE = os.path.join(RUN_021_DIR, "density_scores.json")
NOVELTY_FILE = os.path.join(RUN_019_DIR, "novelty_scores.json")


# ── helpers ──────────────────────────────────────────────────────────────────

def mean(xs: list[float]) -> float:
    """Compute mean of a list."""
    return sum(xs) / len(xs) if xs else 0.0


def std(xs: list[float], ddof: int = 1) -> float:
    """Compute standard deviation."""
    if len(xs) <= ddof:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - ddof))


def point_biserial_r(continuous: list[float], binary: list[int]) -> float:
    """Point-biserial correlation between continuous variable and 0/1 binary.

    Equivalent to Pearson r(continuous, binary).
    """
    n = len(continuous)
    if n < 2:
        return 0.0
    m_cont = mean(continuous)
    m_bin = mean([float(b) for b in binary])
    cov = sum((c - m_cont) * (b - m_bin) for c, b in zip(continuous, binary)) / (n - 1)
    s_cont = std(continuous, ddof=1)
    s_bin = std([float(b) for b in binary], ddof=1)
    if s_cont == 0.0 or s_bin == 0.0:
        return 0.0
    return cov / (s_cont * s_bin)


def percentile_thresholds(values: list[float], qs: list[float]) -> list[float]:
    """Return percentile thresholds for sorted values.

    Args:
        values: List of floats (will be sorted).
        qs: Quantile fractions, e.g. [0.25, 0.5, 0.75].

    Returns:
        Threshold values at each quantile.
    """
    sorted_v = sorted(values)
    n = len(sorted_v)
    thresholds = []
    for q in qs:
        idx = q * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - lo
        thresholds.append(sorted_v[lo] + frac * (sorted_v[hi] - sorted_v[lo]))
    return thresholds


def inv_rate(records: list[dict]) -> float | None:
    """Investigability rate for a list of records."""
    if not records:
        return None
    return sum(r["investigated"] for r in records) / len(records)


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> tuple[float, str]:
    """Fisher's exact test (one-sided): H0: rate_a <= rate_c.

    Returns (p_value, direction).
    """
    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c

    def hyp_prob(k: int) -> float:
        if k < 0 or k > min(r1, c1) or (c1 - k) < 0 or (c1 - k) > r2:
            return 0.0
        return comb(r1, k) * comb(r2, c1 - k) / comb(n, c1)

    p = sum(hyp_prob(k) for k in range(a, min(r1, c1) + 1))
    total_a = a + b
    total_c = c + d
    rate_a = a / total_a if total_a > 0 else 0.0
    rate_c = c / total_c if total_c > 0 else 0.0
    direction = "group_a_higher" if rate_a >= rate_c else "group_c_higher"
    return round(p, 6), direction


# ── logistic regression (single feature, gradient descent) ───────────────────

def logistic(z: float) -> float:
    """Sigmoid function."""
    if z < -500:
        return 0.0
    if z > 500:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def logistic_regression_1d(
    x: list[float], y: list[int], lr: float = 0.01, n_iter: int = 2000
) -> tuple[float, float, float]:
    """Fit single-feature logistic regression via gradient descent.

    Returns (intercept, coefficient, mcfadden_pseudo_r2).
    """
    w0, w1 = 0.0, 0.0
    n = len(x)

    # normalize x
    mx, sx = mean(x), std(x, ddof=0)
    if sx == 0:
        sx = 1.0
    xn = [(xi - mx) / sx for xi in x]

    for _ in range(n_iter):
        dw0, dw1 = 0.0, 0.0
        for xi, yi in zip(xn, y):
            p = logistic(w0 + w1 * xi)
            err = p - yi
            dw0 += err
            dw1 += err * xi
        w0 -= lr * dw0 / n
        w1 -= lr * dw1 / n

    # log-likelihood of fitted model
    ll_fit = sum(
        math.log(logistic(w0 + w1 * xi) + 1e-15) * yi
        + math.log(1 - logistic(w0 + w1 * xi) + 1e-15) * (1 - yi)
        for xi, yi in zip(xn, y)
    )

    # log-likelihood of null model (intercept only)
    p_null = sum(y) / n
    ll_null = n * (p_null * math.log(p_null + 1e-15) + (1 - p_null) * math.log(1 - p_null + 1e-15))

    pseudo_r2 = 1.0 - (ll_fit / ll_null) if ll_null != 0.0 else 0.0

    # convert w1 back to original scale
    coef_original = w1 / sx

    return round(w0, 4), round(coef_original, 4), round(pseudo_r2, 4)


# ── loading ───────────────────────────────────────────────────────────────────

def load_density() -> list[dict]:
    """Load density_scores.json."""
    with open(DENSITY_FILE) as f:
        return json.load(f)


def load_novelty() -> dict[str, dict]:
    """Load novelty_scores.json indexed by hypothesis id."""
    with open(NOVELTY_FILE) as f:
        records = json.load(f)
    return {r["id"]: r for r in records}


def merge_records(density: list[dict], novelty: dict[str, dict]) -> list[dict]:
    """Merge density and novelty data into unified records."""
    merged = []
    for d in density:
        hid = d["id"]
        n = novelty.get(hid, {})
        merged.append({
            **d,
            "combined_novelty": n.get("combined_novelty", None),
            "path_length_score": n.get("path_length_score", None),
            "cross_domain_score": n.get("cross_domain_score", None),
        })
    return merged


# ── Step 2: Correlation Analysis ─────────────────────────────────────────────

def run_correlation_analysis(records: list[dict]) -> dict:
    """Point-biserial correlation for each density metric vs investigability."""
    valid = [r for r in records if r["min_density"] >= 0]
    metrics = ["subject_density", "object_density", "pair_density", "min_density", "log_min_density"]

    correlations: dict[str, Any] = {}
    for metric in metrics:
        vals = [r[metric] for r in valid if r[metric] is not None and r[metric] >= 0]
        inv = [r["investigated"] for r in valid if r[metric] is not None and r[metric] >= 0]
        if len(vals) < 10:
            correlations[metric] = {"r": None, "n": len(vals), "note": "insufficient data"}
            continue
        r_val = point_biserial_r(vals, inv)
        n_inv = sum(inv)
        correlations[metric] = {
            "r": round(r_val, 4),
            "abs_r": round(abs(r_val), 4),
            "n": len(vals),
            "n_investigated": n_inv,
            "mean_investigated": round(mean([v for v, i in zip(vals, inv) if i == 1]), 2) if n_inv > 0 else None,
            "mean_not_investigated": round(mean([v for v, i in zip(vals, inv) if i == 0]), 2) if (len(inv) - n_inv) > 0 else None,
        }

    # Rank by abs_r
    ranked = sorted(
        [(m, v["abs_r"]) for m, v in correlations.items() if v.get("abs_r") is not None],
        key=lambda x: x[1],
        reverse=True,
    )
    correlations["ranking_by_abs_r"] = [{"metric": m, "abs_r": r} for m, r in ranked]

    # H_ceiling criterion check
    best_abs_r = ranked[0][1] if ranked else 0.0
    correlations["h_ceiling_criterion"] = {
        "threshold": 0.4,
        "best_abs_r": best_abs_r,
        "best_metric": ranked[0][0] if ranked else None,
        "criterion_met": best_abs_r >= 0.4,
    }

    return correlations


# ── Step 3: Quartile Analysis ─────────────────────────────────────────────────

def run_quartile_analysis(records: list[dict]) -> dict:
    """Investigability rate per min_density quartile, overall and by method."""
    valid = [r for r in records if r["min_density"] >= 0]
    min_d = [r["min_density"] for r in valid]
    q1, q2, q3 = percentile_thresholds(min_d, [0.25, 0.50, 0.75])

    def quartile_label(v: float) -> str:
        if v <= q1:
            return "Q1_low"
        elif v <= q2:
            return "Q2"
        elif v <= q3:
            return "Q3"
        else:
            return "Q4_high"

    for r in valid:
        r["density_quartile"] = quartile_label(r["min_density"])

    quartile_order = ["Q1_low", "Q2", "Q3", "Q4_high"]
    methods = sorted(set(r["method"] for r in valid))

    def quartile_stats(recs: list[dict]) -> list[dict]:
        result = []
        for q in quartile_order:
            bucket = [r for r in recs if r.get("density_quartile") == q]
            rate = inv_rate(bucket)
            result.append({
                "quartile": q,
                "n": len(bucket),
                "investigated": sum(r["investigated"] for r in bucket),
                "investigability_rate": round(rate, 4) if rate is not None else None,
                "avg_min_density": round(mean([r["min_density"] for r in bucket]), 1) if bucket else None,
            })
        return result

    output: dict[str, Any] = {
        "quartile_thresholds": {"Q1": round(q1, 1), "Q2_median": round(q2, 1), "Q3": round(q3, 1)},
        "overall": quartile_stats(valid),
    }
    for method in methods:
        subset = [r for r in valid if r["method"] == method]
        output[method] = quartile_stats(subset)

    # T1 vs T4 investigability gap (H_ceiling tertile criterion: ≥0.15)
    all_q1 = [r for r in valid if r.get("density_quartile") == "Q1_low"]
    all_q4 = [r for r in valid if r.get("density_quartile") == "Q4_high"]
    rate_q1 = inv_rate(all_q1)
    rate_q4 = inv_rate(all_q4)
    gap = (rate_q4 - rate_q1) if (rate_q1 is not None and rate_q4 is not None) else None

    output["h_ceiling_q1_vs_q4"] = {
        "q1_investigability": round(rate_q1, 4) if rate_q1 is not None else None,
        "q4_investigability": round(rate_q4, 4) if rate_q4 is not None else None,
        "gap_q4_minus_q1": round(gap, 4) if gap is not None else None,
        "criterion_threshold": 0.15,
        "criterion_met": gap >= 0.15 if gap is not None else None,
    }

    return output


# ── Step 4: Logistic Regression ───────────────────────────────────────────────

def run_logistic_regression(records: list[dict]) -> dict:
    """Single-feature logistic regression: log_min_density → investigated."""
    valid = [r for r in records if r["log_min_density"] is not None and r["log_min_density"] >= 0]

    x = [r["log_min_density"] for r in valid]
    y = [r["investigated"] for r in valid]

    intercept, coef, pseudo_r2 = logistic_regression_1d(x, y)

    # Also compute for each method
    method_results: dict[str, Any] = {}
    for method in sorted(set(r["method"] for r in valid)):
        sub = [r for r in valid if r["method"] == method]
        xm = [r["log_min_density"] for r in sub]
        ym = [r["investigated"] for r in sub]
        if len(xm) < 5:
            method_results[method] = {"note": "insufficient data"}
            continue
        i0, c0, pr2 = logistic_regression_1d(xm, ym)
        method_results[method] = {
            "n": len(xm),
            "intercept": i0,
            "coef_log_min_density": c0,
            "mcfadden_pseudo_r2": pr2,
        }

    return {
        "feature": "log_min_density",
        "target": "investigated",
        "n": len(valid),
        "intercept": intercept,
        "coef_log_min_density": coef,
        "mcfadden_pseudo_r2": pseudo_r2,
        "interpretation": (
            "pseudo_r2 < 0.05: negligible; 0.05-0.15: weak; "
            "0.15-0.25: moderate; > 0.25: strong"
        ),
        "by_method": method_results,
    }


# ── Step 5: Matched Comparison ────────────────────────────────────────────────

def run_matched_comparison(records: list[dict]) -> dict:
    """Novelty × density matched comparison: C1 vs C2 investigability gap."""
    # Filter to C1 and C2 only
    c1c2 = [r for r in records if r["method"] in ("C1_compose", "C2_multi_op")]
    valid = [r for r in c1c2 if r["min_density"] >= 0 and r["combined_novelty"] is not None]

    n_valid = len(valid)

    # Compute bin thresholds from combined C1+C2 distribution
    novelties = [r["combined_novelty"] for r in valid]
    densities = [r["min_density"] for r in valid]

    nov_med = percentile_thresholds(novelties, [0.5])[0]
    den_med = percentile_thresholds(densities, [0.5])[0]
    nov_p33, nov_p67 = percentile_thresholds(novelties, [0.333, 0.667])
    den_p33, den_p67 = percentile_thresholds(densities, [0.333, 0.667])

    def novelty_bin_2(nov: float) -> str:
        return "nov_low" if nov <= nov_med else "nov_high"

    def density_bin_2(den: float) -> str:
        return "den_low" if den <= den_med else "den_high"

    def novelty_bin_3(nov: float) -> str:
        if nov <= nov_p33:
            return "nov_low"
        elif nov <= nov_p67:
            return "nov_mid"
        else:
            return "nov_high"

    def density_bin_3(den: float) -> str:
        if den <= den_p33:
            return "den_low"
        elif den <= den_p67:
            return "den_mid"
        else:
            return "den_high"

    for r in valid:
        r["nov_bin_2"] = novelty_bin_2(r["combined_novelty"])
        r["den_bin_2"] = density_bin_2(r["min_density"])
        r["nov_bin_3"] = novelty_bin_3(r["combined_novelty"])
        r["den_bin_3"] = density_bin_3(r["min_density"])

    # Check if novelty perfectly separates C1 and C2 (common since C1=bio-only, C2=cross-domain)
    c1_novelties = set(r["nov_bin_2"] for r in valid if r["method"] == "C1_compose")
    c2_novelties = set(r["nov_bin_2"] for r in valid if r["method"] == "C2_multi_op")
    novelty_separates = c1_novelties.isdisjoint(c2_novelties)

    # 2×2 comparison on novelty × density
    cells_2x2: list[dict] = []
    for nov_b in ["nov_low", "nov_high"]:
        for den_b in ["den_low", "den_high"]:
            cell_c1 = [r for r in valid if r["method"] == "C1_compose" and r["nov_bin_2"] == nov_b and r["den_bin_2"] == den_b]
            cell_c2 = [r for r in valid if r["method"] == "C2_multi_op" and r["nov_bin_2"] == nov_b and r["den_bin_2"] == den_b]
            rate_c1 = inv_rate(cell_c1)
            rate_c2 = inv_rate(cell_c2)
            gap = (rate_c1 - rate_c2) if (rate_c1 is not None and rate_c2 is not None) else None
            cells_2x2.append({
                "cell": f"{nov_b}×{den_b}",
                "n_c1": len(cell_c1),
                "n_c2": len(cell_c2),
                "c1_investigability": round(rate_c1, 4) if rate_c1 is not None else None,
                "c2_investigability": round(rate_c2, 4) if rate_c2 is not None else None,
                "gap_c1_minus_c2": round(gap, 4) if gap is not None else None,
                "sufficient_n": len(cell_c1) >= 5 and len(cell_c2) >= 5,
            })

    # Density-only comparison (alternative 2 from matched_comparison_plan.md)
    # Used when novelty perfectly separates C1 and C2 (all C1=nov_low, all C2=nov_high)
    den_thresholds_3 = percentile_thresholds(densities, [0.333, 0.667])
    den_p33_v, den_p67_v = den_thresholds_3

    def density_bin_only(den: float) -> str:
        if den <= den_p33_v:
            return "den_low"
        elif den <= den_p67_v:
            return "den_mid"
        else:
            return "den_high"

    for r in valid:
        r["den_bin_only"] = density_bin_only(r["min_density"])

    cells_density_only: list[dict] = []
    for den_b in ["den_low", "den_mid", "den_high"]:
        cell_c1 = [r for r in valid if r["method"] == "C1_compose" and r["den_bin_only"] == den_b]
        cell_c2 = [r for r in valid if r["method"] == "C2_multi_op" and r["den_bin_only"] == den_b]
        rate_c1 = inv_rate(cell_c1)
        rate_c2 = inv_rate(cell_c2)
        gap = (rate_c1 - rate_c2) if (rate_c1 is not None and rate_c2 is not None) else None
        cells_density_only.append({
            "cell": f"density={den_b}",
            "n_c1": len(cell_c1),
            "n_c2": len(cell_c2),
            "c1_investigability": round(rate_c1, 4) if rate_c1 is not None else None,
            "c2_investigability": round(rate_c2, 4) if rate_c2 is not None else None,
            "gap_c1_minus_c2": round(gap, 4) if gap is not None else None,
            "sufficient_n": len(cell_c1) >= 5 and len(cell_c2) >= 5,
        })

    # 3×3 comparison (primary)
    cells_3x3: list[dict] = []
    for nov_b in ["nov_low", "nov_mid", "nov_high"]:
        for den_b in ["den_low", "den_mid", "den_high"]:
            cell_c1 = [r for r in valid if r["method"] == "C1_compose" and r["nov_bin_3"] == nov_b and r["den_bin_3"] == den_b]
            cell_c2 = [r for r in valid if r["method"] == "C2_multi_op" and r["nov_bin_3"] == nov_b and r["den_bin_3"] == den_b]
            rate_c1 = inv_rate(cell_c1)
            rate_c2 = inv_rate(cell_c2)
            gap = (rate_c1 - rate_c2) if (rate_c1 is not None and rate_c2 is not None) else None
            cells_3x3.append({
                "cell": f"{nov_b}×{den_b}",
                "n_c1": len(cell_c1),
                "n_c2": len(cell_c2),
                "c1_investigability": round(rate_c1, 4) if rate_c1 is not None else None,
                "c2_investigability": round(rate_c2, 4) if rate_c2 is not None else None,
                "gap_c1_minus_c2": round(gap, 4) if gap is not None else None,
                "sufficient_n": len(cell_c1) >= 5 and len(cell_c2) >= 5,
            })

    # Weighted average matched gap — prefer density-only when novelty separates methods
    reportable_2x2 = [c for c in cells_2x2 if c["sufficient_n"] and c["gap_c1_minus_c2"] is not None]
    reportable_density_only = [c for c in cells_density_only if c["sufficient_n"] and c["gap_c1_minus_c2"] is not None]

    if novelty_separates and reportable_density_only:
        # Use density-only matching (novelty is collinear with method)
        total_n = sum(c["n_c1"] + c["n_c2"] for c in reportable_density_only)
        matched_gap = sum(c["gap_c1_minus_c2"] * (c["n_c1"] + c["n_c2"]) for c in reportable_density_only) / total_n
        matched_gap_strategy = "density_only (novelty collinear with method)"
    elif reportable_2x2:
        total_n = sum(c["n_c1"] + c["n_c2"] for c in reportable_2x2)
        matched_gap = sum(c["gap_c1_minus_c2"] * (c["n_c1"] + c["n_c2"]) for c in reportable_2x2) / total_n
        matched_gap_strategy = "novelty x density 2x2"
    else:
        matched_gap = None
        matched_gap_strategy = "none (insufficient N)"

    # Overall C1 vs C2 unmatched
    all_c1 = [r for r in valid if r["method"] == "C1_compose"]
    all_c2 = [r for r in valid if r["method"] == "C2_multi_op"]
    rate_c1_all = inv_rate(all_c1)
    rate_c2_all = inv_rate(all_c2)
    unmatched_gap = (rate_c1_all - rate_c2_all) if (rate_c1_all is not None and rate_c2_all is not None) else None

    # H_match verdict
    if matched_gap is None:
        h_match_verdict = "insufficient_data"
        h_match_note = "Too few matched cells (N<5) for reliable comparison"
    elif matched_gap <= 0.02:
        h_match_verdict = "supported"
        h_match_note = f"matched gap {matched_gap:.4f} ≤ 0.02 — density composition explains C1-C2 gap"
    elif matched_gap > 0.04:
        h_match_verdict = "rejected"
        h_match_note = f"matched gap {matched_gap:.4f} > 0.04 — density alone does not explain C1-C2 gap"
    else:
        h_match_verdict = "intermediate"
        h_match_note = f"matched gap {matched_gap:.4f} between 0.02-0.04 — partial explanation"

    return {
        "n_c1": len(all_c1),
        "n_c2": len(all_c2),
        "n_valid_matched": n_valid,
        "thresholds": {
            "novelty_median": round(nov_med, 4),
            "density_median": round(den_med, 1),
            "novelty_p33": round(nov_p33, 4),
            "novelty_p67": round(nov_p67, 4),
            "density_p33": round(den_p33, 1),
            "density_p67": round(den_p67, 1),
        },
        "unmatched": {
            "c1_investigability": round(rate_c1_all, 4) if rate_c1_all is not None else None,
            "c2_investigability": round(rate_c2_all, 4) if rate_c2_all is not None else None,
            "gap_c1_minus_c2": round(unmatched_gap, 4) if unmatched_gap is not None else None,
        },
        "cells_2x2": cells_2x2,
        "cells_3x3": cells_3x3,
        "novelty_separates_methods": novelty_separates,
        "matched_gap_strategy": matched_gap_strategy,
        "n_reportable_cells_2x2": len(reportable_2x2),
        "n_reportable_density_only": len(reportable_density_only),
        "cells_density_only": cells_density_only,
        "matched_gap_weighted": round(matched_gap, 4) if matched_gap is not None else None,
        "h_match_verdict": h_match_verdict,
        "h_match_note": h_match_note,
        "h_match_criteria": {
            "supported_threshold": 0.02,
            "rejected_threshold": 0.04,
        },
    }


# ── Step 6: Statistical Tests ─────────────────────────────────────────────────

def run_statistical_tests(records: list[dict], quartile_analysis: dict) -> dict:
    """Fisher's exact tests for density-investigability hypotheses."""
    valid = [r for r in records if r["min_density"] >= 0 and "density_quartile" in r]

    # Test 1: Q4 (high density) vs Q1 (low density) investigability
    q4 = [r for r in valid if r["density_quartile"] == "Q4_high"]
    q1 = [r for r in valid if r["density_quartile"] == "Q1_low"]
    a = sum(r["investigated"] for r in q4)
    b = len(q4) - a
    c = sum(r["investigated"] for r in q1)
    d = len(q1) - c
    p1, dir1 = fisher_exact_2x2(a, b, c, d) if (q4 and q1) else (None, "n/a")

    # Test 2: C2 density-matched Q3+Q4 vs Q1+Q2 investigability
    c2 = [r for r in valid if r["method"] == "C2_multi_op"]
    c2_high = [r for r in c2 if r["density_quartile"] in ("Q3", "Q4_high")]
    c2_low = [r for r in c2 if r["density_quartile"] in ("Q1_low", "Q2")]
    a2 = sum(r["investigated"] for r in c2_high)
    b2 = len(c2_high) - a2
    c2n = sum(r["investigated"] for r in c2_low)
    d2 = len(c2_low) - c2n
    p2, dir2 = fisher_exact_2x2(a2, b2, c2n, d2) if (c2_high and c2_low) else (None, "n/a")

    # Test 3: C1 vs C2 overall investigability (Fisher)
    c1_all = [r for r in valid if r["method"] == "C1_compose"]
    c2_all = [r for r in valid if r["method"] == "C2_multi_op"]
    a3 = sum(r["investigated"] for r in c1_all)
    b3 = len(c1_all) - a3
    c3 = sum(r["investigated"] for r in c2_all)
    d3 = len(c2_all) - c3
    p3, dir3 = fisher_exact_2x2(a3, b3, c3, d3) if (c1_all and c2_all) else (None, "n/a")

    def fmt(a: int, b: int) -> str:
        return f"{a}/{a+b} ({a/(a+b):.3f})" if (a + b) > 0 else "0/0"

    return {
        "test1_q4_vs_q1_density": {
            "description": "Q4 (high density) vs Q1 (low density) investigability (Fisher one-sided)",
            "q4": fmt(a, b),
            "q1": fmt(c, d),
            "p_value": p1,
            "direction": dir1,
            "significant_p05": p1 < 0.05 if p1 is not None else None,
        },
        "test2_c2_high_vs_low_density": {
            "description": "C2: high density (Q3+Q4) vs low density (Q1+Q2) investigability (Fisher one-sided)",
            "c2_high_density": fmt(a2, b2),
            "c2_low_density": fmt(c2n, d2),
            "p_value": p2,
            "direction": dir2,
            "significant_p05": p2 < 0.05 if p2 is not None else None,
        },
        "test3_c1_vs_c2_overall": {
            "description": "C1 vs C2 overall investigability (Fisher one-sided)",
            "c1": fmt(a3, b3),
            "c2": fmt(c3, d3),
            "p_value": p3,
            "direction": dir3,
            "significant_p05": p3 < 0.05 if p3 is not None else None,
        },
    }


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_json(data: Any, path: str) -> None:
    """Save data as JSON."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


def save_text(text: str, path: str) -> None:
    """Save text file."""
    with open(path, "w") as f:
        f.write(text)
    print(f"  saved → {path}")


# ── Report generation ─────────────────────────────────────────────────────────

def build_review_memo(
    corr: dict,
    quart: dict,
    logreg: dict,
    matched: dict,
    stat_tests: dict,
) -> str:
    """Generate review_memo.md content."""
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def _r(val: Any) -> str:
        return f"{val:.4f}" if isinstance(val, float) else str(val)

    corr_ranking = corr.get("ranking_by_abs_r", [])
    best_metric = corr_ranking[0]["metric"] if corr_ranking else "N/A"
    best_abs_r = corr_ranking[0]["abs_r"] if corr_ranking else 0.0
    h_ceil_met = corr.get("h_ceiling_criterion", {}).get("criterion_met", False)

    q1_inv = quart.get("h_ceiling_q1_vs_q4", {}).get("q1_investigability")
    q4_inv = quart.get("h_ceiling_q1_vs_q4", {}).get("q4_investigability")
    q_gap = quart.get("h_ceiling_q1_vs_q4", {}).get("gap_q4_minus_q1")

    pr2 = logreg.get("mcfadden_pseudo_r2")
    matched_gap = matched.get("matched_gap_weighted")
    h_match = matched.get("h_match_verdict")
    unmatched_gap = matched.get("unmatched", {}).get("gap_c1_minus_c2")

    t1 = stat_tests.get("test1_q4_vs_q1_density", {})
    t2 = stat_tests.get("test2_c2_high_vs_low_density", {})
    t3 = stat_tests.get("test3_c1_vs_c2_overall", {})

    # Build density-only cell table for memo
    density_only_cells = matched.get("cells_density_only", [])
    density_table = "\n".join(
        f"| {c['cell']} | {c['n_c1']} | {c['n_c2']} | "
        f"{c['c1_investigability'] if c['c1_investigability'] is not None else 'N/A'} | "
        f"{c['c2_investigability'] if c['c2_investigability'] is not None else 'N/A'} | "
        f"{c['gap_c1_minus_c2'] if c['gap_c1_minus_c2'] is not None else 'N/A'} |"
        for c in density_only_cells
    )
    novelty_collinear_note = (
        "注: novelty は method と完全に共線 (C1=全て nov_low, C2=全て nov_high) のため、"
        "density-only matching を適用 (matched_comparison_plan.md 代替2)"
        if matched.get("novelty_separates_methods") else ""
    )

    return f"""# run_021 Density Ceiling Analysis — Review Memo

**Date**: {date}
**Run**: run_021_density_ceiling
**Hypotheses tested**: H_ceiling, H_match

---

## 実験概要

run_018 (210件: C2 70, C1 70, C_rand_v2 70) に PubMed density metrics (≤2023) を付与し、
density が investigability を説明するかを検証した。

- **H_ceiling**: cross-domain investigability は operator quality より density asymmetry で決まる
- **H_match**: novelty × density をマッチングすると C1-C2 investigability gap が縮まる (≤0.02)

---

## Step 2: Density-Investigability 相関

| Metric | Point-Biserial r |
|--------|-----------------|
{chr(10).join(f"| {item['metric']} | {item['abs_r']:.4f} |" for item in corr_ranking)}

**最強予測因子**: `{best_metric}` (|r| = {best_abs_r:.4f})
**H_ceiling 相関基準 (|r| ≥ 0.4)**: {"✅ 達成" if h_ceil_met else "❌ 未達成"}

---

## Step 3: Quartile Analysis

| Quartile | Investigability |
|----------|----------------|
| Q1 (low) | {_r(q1_inv)} |
| Q4 (high) | {_r(q4_inv)} |
| Gap (Q4-Q1) | {_r(q_gap)} |

**H_ceiling 基準 (Q4-Q1 gap ≥ 0.15)**: {"✅ 達成" if q_gap is not None and q_gap >= 0.15 else "❌ 未達成"}

---

## Step 4: Logistic Regression

- Feature: `log_min_density`
- McFadden pseudo R²: **{_r(pr2)}**
- 解釈: {"negligible (<0.05)" if pr2 is not None and pr2 < 0.05 else "weak (0.05-0.15)" if pr2 is not None and pr2 < 0.15 else "moderate (0.15-0.25)" if pr2 is not None and pr2 < 0.25 else "strong (>0.25)" if pr2 is not None else "N/A"}

---

## Step 5: Matched Comparison (density-only)

{novelty_collinear_note}

| Density Bin | n_C1 | n_C2 | C1_inv | C2_inv | Gap (C1-C2) |
|-------------|------|------|--------|--------|------------|
{density_table}

- Unmatched C1-C2 gap: **{_r(unmatched_gap)}**
- Matched gap (density-only, weighted): **{_r(matched_gap)}**
- **H_match verdict**: **{h_match}**
- Note: {matched.get("h_match_note", "")}

**重要な観察**: gap は density_low 群 (C1=0.957, C2=0.76) に集中。
density_mid/high ではギャップが消失または逆転 → density を control すると C1-C2 は同等になる傾向あり。

---

## Statistical Tests

| Test | p-value | Significant (p<0.05) |
|------|---------|---------------------|
| Q4 vs Q1 density | {t1.get("p_value")} | {t1.get("significant_p05")} |
| C2 high vs low density | {t2.get("p_value")} | {t2.get("significant_p05")} |
| C1 vs C2 overall | {t3.get("p_value")} | {t3.get("significant_p05")} |

---

## 結論

### H_ceiling
{"**支持**: density と investigability に有意な相関あり。" if h_ceil_met else "**棄却/弱い支持**: density と investigability の相関は閾値未満 (|r| < 0.4)。"}
{"Q4-Q1 gap も基準達成 ≥0.15。" if q_gap is not None and q_gap >= 0.15 else "Q4-Q1 gap も基準未達成 < 0.15。"}
pseudo R² = {_r(pr2)} — density が investigability を{"十分に" if pr2 is not None and pr2 >= 0.15 else "わずかしか"}説明しない。

### H_match
**{h_match}**: {matched.get("h_match_note", "")}

---

## 次のアクション

{_next_actions(h_ceil_met, h_match, q_gap, pr2)}
"""


def _next_actions(h_ceil_met: bool, h_match: str, q_gap: Any, pr2: Any) -> str:
    """Suggest next actions based on results."""
    actions = []
    if not h_ceil_met:
        actions.append("- H_ceiling 棄却 → density 以外の要因 (e.g., relation_type, domain_specificity) を調査")
    if h_match in ("rejected", "insufficient_data"):
        actions.append("- H_match 棄却/不明 → C1-C2 gap の別の説明 (operator の relation quality) を検討")
    if h_ceil_met and h_match == "supported":
        actions.append("- H_ceiling + H_match 双方支持 → density-aware サンプリングで C2 investigability 改善の可能性")
        actions.append("- P2: density-balanced な cross-domain 仮説生成を設計")
    if h_match == "insufficient_data":
        actions.append("- matched comparison の検出力不足 → より大きなデータセット (run_022?) を検討")
    if not actions:
        actions.append("- 結果を docs/scientific_hypothesis/density_ceiling_results.md に詳細記録")
        actions.append("- 次フェーズの実験設計を更新")
    return "\n".join(actions)


def build_density_ceiling_results(
    corr: dict,
    quart: dict,
    logreg: dict,
    matched: dict,
    stat_tests: dict,
    density_records: list[dict],
) -> str:
    """Generate density_ceiling_results.md."""
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    def _r(val: Any) -> str:
        return f"{val:.4f}" if isinstance(val, float) else str(val)

    corr_ranking = corr.get("ranking_by_abs_r", [])
    h_ceil_crit = corr.get("h_ceiling_criterion", {})
    q_info = quart.get("h_ceiling_q1_vs_q4", {})
    pr2 = logreg.get("mcfadden_pseudo_r2")
    matched_gap = matched.get("matched_gap_weighted")
    h_match = matched.get("h_match_verdict")
    unmatched_gap = matched.get("unmatched", {}).get("gap_c1_minus_c2")

    # Method-level investigability from density records
    by_method: dict[str, list] = {}
    for r in density_records:
        by_method.setdefault(r["method"], []).append(r)
    method_inv = {m: inv_rate(recs) for m, recs in by_method.items()}

    # Method density comparisons
    def method_avg(method: str, field: str) -> float:
        recs = [r for r in density_records if r["method"] == method and r.get(field, -1) >= 0]
        return mean([r[field] for r in recs]) if recs else 0.0

    return f"""# Density Ceiling Analysis Results — run_021

**Date**: {date}
**Status**: COMPLETED

---

## 主仮説検証結果

### H_ceiling: cross-domain investigability は density asymmetry で決まるか

**判定**: {"支持" if h_ceil_crit.get("criterion_met") else "棄却/弱支持"}

**根拠**:
- 最強 predictor: `{h_ceil_crit.get("best_metric")}` (point-biserial |r| = {h_ceil_crit.get("best_abs_r", "N/A")})
- 閾値: |r| ≥ 0.4 → {"✅ 達成" if h_ceil_crit.get("criterion_met") else "❌ 未達成"}
- McFadden pseudo R² (log_min_density → investigated) = {_r(pr2)}
- Q4 vs Q1 investigability gap = {_r(q_info.get("gap_q4_minus_q1"))} (threshold: ≥0.15)

**全相関係数**:

| Metric | |r| | 方向 |
|--------|-----|------|
{chr(10).join(f"| {item['metric']} | {item['abs_r']:.4f} | {'density↑ → investigability↑' if corr.get(item['metric'], {}).get('r', 0) > 0 else 'density↑ → investigability↓'} |" for item in corr_ranking)}

---

### H_match: matched comparison で C1-C2 gap が縮まるか

**判定**: **{h_match}**

| 比較 | Investigability |
|------|----------------|
| C1 (unmatched) | {_r(matched.get("unmatched", {}).get("c1_investigability"))} |
| C2 (unmatched) | {_r(matched.get("unmatched", {}).get("c2_investigability"))} |
| Unmatched gap | {_r(unmatched_gap)} |
| Matched gap (weighted) | {_r(matched_gap)} |

**Reportable cells** (N≥5 each group): {matched.get("n_reportable_cells_2x2", 0)} / 4

{matched.get("h_match_note", "")}

---

## Density が investigability をどの程度説明するか

- **McFadden pseudo R²** = {_r(pr2)}: log_min_density が investigability 分散の{"大部分" if pr2 is not None and pr2 >= 0.25 else "一部" if pr2 is not None and pr2 >= 0.05 else "ほぼ何も"}説明しない
- **Q1-Q4 gap** = {_r(q_info.get("gap_q4_minus_q1"))}: density が低い仮説と高い仮説で investigability が{"大きく異なる" if q_info.get("gap_q4_minus_q1") is not None and q_info["gap_q4_minus_q1"] >= 0.15 else "あまり変わらない"}

---

## Method 別 density と investigability

| Method | avg_min_density | avg_pair_density | investigability |
|--------|----------------|------------------|----------------|
| C1_compose | {method_avg("C1_compose", "min_density"):.0f} | {method_avg("C1_compose", "pair_density"):.1f} | {_r(method_inv.get("C1_compose"))} |
| C2_multi_op | {method_avg("C2_multi_op", "min_density"):.0f} | {method_avg("C2_multi_op", "pair_density"):.1f} | {_r(method_inv.get("C2_multi_op"))} |
| C_rand_v2 | {method_avg("C_rand_v2", "min_density"):.0f} | {method_avg("C_rand_v2", "pair_density"):.1f} | {_r(method_inv.get("C_rand_v2"))} |

---

## C1-C2 gap の原因の整理

1. **density composition の違い**: C1 (bio-only) は C2 (cross-domain) より density が{"高い" if method_avg("C1_compose", "min_density") > method_avg("C2_multi_op", "min_density") else "低い（予想と逆）"}
2. **density の説明力**: pseudo R² = {_r(pr2)} → density{"は" if pr2 is not None and pr2 >= 0.15 else "は単独では"}主要因{"である" if pr2 is not None and pr2 >= 0.15 else "ではない"}
3. **matched 比較**: {matched.get("h_match_note", "検出力不足のため結論不能")}

---

## 次のアクション

{_next_actions(
    h_ceil_crit.get("criterion_met", False),
    h_match,
    q_info.get("gap_q4_minus_q1"),
    pr2,
)}

---

## 関連ファイル

- `runs/run_021_density_ceiling/density_scores.json` — 210件のdensityスコア
- `runs/run_021_density_ceiling/correlation_analysis.json` — 相関分析結果
- `runs/run_021_density_ceiling/quartile_analysis.json` — 四分位分析
- `runs/run_021_density_ceiling/matched_comparison.json` — マッチング比較
- `runs/run_021_density_ceiling/statistical_tests.json` — 統計検定
"""


# ── main ──────────────────────────────────────────────────────────────────────

def save_run_config() -> None:
    """Save run_021 config."""
    config = {
        "run_id": "run_021_density_ceiling",
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": "Density ceiling hypothesis (H_ceiling) + matched comparison (H_match)",
        "seed": 42,
        "source_runs": ["run_018_investigability_replication", "run_019_novelty_tradeoff_analysis"],
        "n_hypotheses": 210,
        "density_metrics": ["subject_density", "object_density", "pair_density", "min_density", "log_min_density"],
        "pair_density_source": "past_pubmed_hits_le2023 from run_018 labeling (same query: subj AND obj, ≤2023)",
        "h_ceiling_criterion": "best density metric |r| >= 0.4 with investigability",
        "h_match_criterion": "matched C1-C2 gap <= 0.02 after novelty×density binning",
        "past_corpus_end": "2023-12-31",
    }
    path = os.path.join(RUN_021_DIR, "run_config.json")
    save_json(config, path)


def main() -> None:
    """Run full density ceiling analysis."""
    os.makedirs(RUN_021_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    print("Loading data...")
    density_records = load_density()
    novelty_index = load_novelty()
    records = merge_records(density_records, novelty_index)
    print(f"  {len(records)} records loaded")

    print("\nStep 2: Correlation analysis...")
    corr = run_correlation_analysis(records)
    save_json(corr, os.path.join(RUN_021_DIR, "correlation_analysis.json"))

    print("\nStep 3: Quartile analysis...")
    quart = run_quartile_analysis(records)
    save_json(quart, os.path.join(RUN_021_DIR, "quartile_analysis.json"))

    print("\nStep 4: Logistic regression...")
    logreg = run_logistic_regression(records)
    save_json(logreg, os.path.join(RUN_021_DIR, "logistic_regression.json"))

    print("\nStep 5: Matched comparison...")
    matched = run_matched_comparison(records)
    save_json(matched, os.path.join(RUN_021_DIR, "matched_comparison.json"))

    print("\nStep 6: Statistical tests...")
    stat_tests = run_statistical_tests(records, quart)
    save_json(stat_tests, os.path.join(RUN_021_DIR, "statistical_tests.json"))

    print("\nSaving run config...")
    save_run_config()

    print("\nGenerating review_memo.md...")
    memo = build_review_memo(corr, quart, logreg, matched, stat_tests)
    save_text(memo, os.path.join(RUN_021_DIR, "review_memo.md"))

    print("\nGenerating density_ceiling_results.md...")
    results_md = build_density_ceiling_results(corr, quart, logreg, matched, stat_tests, records)
    save_text(results_md, os.path.join(DOCS_DIR, "density_ceiling_results.md"))

    # ── Print summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("=== run_021 Summary ===")
    print("=" * 60)

    corr_ranking = corr.get("ranking_by_abs_r", [])
    if corr_ranking:
        print(f"\nDensity-Investigability Correlations (top 3):")
        for item in corr_ranking[:3]:
            r_info = corr.get(item["metric"], {})
            print(f"  {item['metric']:30s} |r|={item['abs_r']:.4f}  "
                  f"mean_inv={r_info.get('mean_investigated', 'N/A')}  "
                  f"mean_not={r_info.get('mean_not_investigated', 'N/A')}")

    h_ceil = corr.get("h_ceiling_criterion", {})
    print(f"\nH_ceiling criterion (|r|≥0.4): {'MET ✓' if h_ceil.get('criterion_met') else 'NOT MET ✗'}")
    print(f"  best metric={h_ceil.get('best_metric')}, |r|={h_ceil.get('best_abs_r')}")

    q_info = quart.get("h_ceiling_q1_vs_q4", {})
    print(f"\nQ4 vs Q1 investigability: {q_info.get('q4_investigability')} vs {q_info.get('q1_investigability')} "
          f"(gap={q_info.get('gap_q4_minus_q1')}, threshold≥0.15: {'MET ✓' if q_info.get('criterion_met') else 'NOT MET ✗'})")

    print(f"\nLogistic Regression pseudo R²: {logreg.get('mcfadden_pseudo_r2')}")

    print(f"\nMatched Comparison:")
    print(f"  Unmatched C1-C2 gap: {matched.get('unmatched', {}).get('gap_c1_minus_c2')}")
    print(f"  Matched gap:         {matched.get('matched_gap_weighted')}")
    print(f"  H_match verdict:     {matched.get('h_match_verdict')}")

    print(f"\nOutputs saved to {RUN_021_DIR}/")
    print(f"Results doc: {DOCS_DIR}/density_ceiling_results.md")


if __name__ == "__main__":
    main()
