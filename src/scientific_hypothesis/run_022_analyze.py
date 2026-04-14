"""Statistical analysis for run_022 density-aware selection experiment.

Inputs:
  runs/run_022_density_aware_selection/hypotheses_*.json
  runs/run_022_density_aware_selection/labeling_results.json

Outputs:
  runs/run_022_density_aware_selection/statistical_tests.json
  runs/run_022_density_aware_selection/matched_comparison.json
  runs/run_022_density_aware_selection/review_memo.md
  docs/scientific_hypothesis/density_aware_results.md

Tests:
  SC_ds_primary:   C2_density_aware parity with C1 (Fisher two-sided, p>0.05, delta<=0.02)
  SC_ds_improvement: C2_density_aware > C2_baseline rate (0.914)
  SC_ds_random:    C2_density_aware > C_rand_v2 (Fisher one-sided, p<0.05)

Matched comparison: density-only bins (den_low/den_mid/den_high tertiles).
H_matched_parity: all reportable cells gap <= 0.03.

Python stdlib only, seed=42.
"""
from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime
from typing import Any

random.seed(42)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_022_DIR = os.path.join(BASE_DIR, "runs", "run_022_density_aware_selection")
RUN_021_DIR = os.path.join(BASE_DIR, "runs", "run_021_density_ceiling")
DOCS_DIR = os.path.join(BASE_DIR, "docs", "scientific_hypothesis")

C2_BASELINE_RATE = 0.914   # run_018 C2 investigability rate
KNOWN_THRESHOLD = 20
PARITY_DELTA = 0.02        # SC_ds_primary: |rate_c2da - rate_c1| <= this
MATCHED_GAP_THRESHOLD = 0.03  # H_matched_parity: all cells gap <= this


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def mean(xs: list[float]) -> float:
    """Compute mean of a float list."""
    return sum(xs) / len(xs) if xs else 0.0


def _comb(n: int, k: int) -> int:
    """Binomial coefficient C(n, k)."""
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def _hyper_prob(a: int, b: int, c: int, d: int) -> float:
    """Hypergeometric probability for 2x2 contingency table."""
    n = a + b + c + d
    denom = _comb(n, a + c)
    if denom == 0:
        return 0.0
    return _comb(a + b, a) * _comb(c + d, c) / denom


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher's exact test p-value for 2x2 table [[a,b],[c,d]]."""
    r1, r2, col1 = a + b, c + d, a + c
    if r1 == 0 or r2 == 0:
        return 1.0
    observed_p = _hyper_prob(a, b, c, d)
    total_p = 0.0
    for ai in range(max(0, col1 - r2), min(r1, col1) + 1):
        bi = r1 - ai
        ci = col1 - ai
        di = r2 - ci
        if bi < 0 or ci < 0 or di < 0:
            continue
        p = _hyper_prob(ai, bi, ci, di)
        if p <= observed_p + 1e-10:
            total_p += p
    return min(total_p, 1.0)


def fisher_exact_one_sided(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher: H_a: a/(a+b) > c/(c+d). Returns p-value."""
    r1, r2, col1 = a + b, c + d, a + c
    if r1 == 0 or r2 == 0:
        return 1.0
    p = 0.0
    for ai in range(max(0, col1 - r2), min(r1, col1) + 1):
        if ai >= a:
            p += _hyper_prob(ai, r1 - ai, col1 - ai, r2 - (col1 - ai))
    return min(p, 1.0)


def percentile(values: list[float], q: float) -> float:
    """Return q-th percentile (0<q<1) of sorted values."""
    if not values:
        return 0.0
    sv = sorted(values)
    n = len(sv)
    idx = q * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    return sv[lo] + (idx - lo) * (sv[hi] - sv[lo])


# ---------------------------------------------------------------------------
# Novelty scoring (same formula as run_019/add_novelty_scores.py)
# ---------------------------------------------------------------------------

NOVELTY_WEIGHTS = {"path_length": 0.3, "cross_domain": 0.3, "popularity": 0.4}


def path_length_score(chain_length: int) -> float:
    """Map chain_length to novelty sub-score."""
    if chain_length <= 2:
        return 0.2
    elif chain_length == 3:
        return 0.5
    elif chain_length == 4:
        return 0.8
    return 1.0


def cross_domain_score(subject_id: str, object_id: str) -> float:
    """1.0 if cross-domain, else 0.0."""
    sd = subject_id.split(":")[0]
    od = object_id.split(":")[0]
    return 1.0 if sd != od else 0.0


def compute_novelty(hyp: dict[str, Any], past_hits: int, max_hits: int) -> float:
    """Compute combined novelty score."""
    pl = path_length_score(hyp.get("chain_length", 3))
    cd = cross_domain_score(hyp.get("subject_id", ""), hyp.get("object_id", ""))
    pop_norm = math.log(1 + past_hits) / math.log(1 + max_hits) if max_hits > 0 else 0.0
    pop = 1.0 - pop_norm
    return round(NOVELTY_WEIGHTS["path_length"] * pl
                 + NOVELTY_WEIGHTS["cross_domain"] * cd
                 + NOVELTY_WEIGHTS["popularity"] * pop, 4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: str) -> Any:
    """Load JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved -> {path}")


def save_text(path: str, text: str) -> None:
    """Write text file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  saved -> {path}")


def load_hypotheses() -> dict[str, list[dict[str, Any]]]:
    """Load all hypothesis files, keyed by method."""
    files = {
        "C2_density_aware": "hypotheses_c2_density_aware.json",
        "C1_compose": "hypotheses_c1.json",
        "C_rand_v2": "hypotheses_crand_v2.json",
    }
    result = {}
    for method, fname in files.items():
        data = load_json(os.path.join(RUN_022_DIR, fname))
        result[method] = data["hypotheses"]
    return result


def load_labels() -> dict[str, dict[str, Any]]:
    """Load labeling_results.json, indexed by hypothesis ID."""
    records = load_json(os.path.join(RUN_022_DIR, "labeling_results.json"))
    return {r["id"]: r for r in records}


# ---------------------------------------------------------------------------
# Investigability stats
# ---------------------------------------------------------------------------

def compute_investigability(labels: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute investigability metrics for a method's labels."""
    total = len(labels)
    if total == 0:
        return {"total": 0, "investigated": 0, "investigability": 0.0}
    investigated = sum(1 for r in labels if r["label_layer1"] != "not_investigated")
    l2_counts: dict[str, int] = {}
    for r in labels:
        l2 = r.get("label_layer2", "plausible_novel")
        l2_counts[l2] = l2_counts.get(l2, 0) + 1
    novel_sup = l2_counts.get("novel_supported", 0)
    known_fact = l2_counts.get("known_fact", 0)
    return {
        "total": total,
        "investigated": investigated,
        "investigability": round(investigated / total, 4),
        "not_investigated": total - investigated,
        "novel_supported": novel_sup,
        "novel_supported_rate": round(novel_sup / investigated, 4) if investigated else 0.0,
        "known_fact": known_fact,
        "layer2_counts": l2_counts,
    }


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def sc_ds_primary(c2da: dict[str, Any], c1: dict[str, Any]) -> dict[str, Any]:
    """SC_ds_primary: parity between C2_density_aware and C1."""
    a = c2da["investigated"]
    b = c2da["total"] - a
    c = c1["investigated"]
    d = c1["total"] - c
    p = fisher_exact_two_sided(a, b, c, d)
    delta = abs(c2da["investigability"] - c1["investigability"])
    parity_p = p > 0.05
    parity_delta = delta <= PARITY_DELTA
    passed = parity_p and parity_delta
    return {
        "name": "SC_ds_primary",
        "description": "C2_density_aware investigability parity with C1 (Fisher two-sided)",
        "test": "Fisher exact two-sided",
        "alpha": 0.05,
        "primary": True,
        "c2da_rate": c2da["investigability"],
        "c1_rate": c1["investigability"],
        "delta": round(delta, 4),
        "parity_delta_threshold": PARITY_DELTA,
        "contingency": {"a": a, "b": b, "c": c, "d": d},
        "p_value": round(p, 4),
        "parity_p_condition": parity_p,
        "parity_delta_condition": parity_delta,
        "passed": passed,
        "note": (
            f"C2_da investigated={a}/{c2da['total']} vs C1 investigated={c}/{c1['total']}; "
            f"p={p:.4f}, delta={delta:.4f}"
        ),
    }


def sc_ds_improvement(c2da: dict[str, Any]) -> dict[str, Any]:
    """SC_ds_improvement: C2_density_aware > run_018 C2 baseline."""
    rate = c2da["investigability"]
    passed = rate > C2_BASELINE_RATE
    return {
        "name": "SC_ds_improvement",
        "description": f"C2_density_aware investigability > run_018 C2 baseline ({C2_BASELINE_RATE})",
        "test": "Descriptive threshold check",
        "primary": False,
        "c2da_rate": rate,
        "baseline_rate": C2_BASELINE_RATE,
        "baseline_run": "run_018",
        "passed": passed,
        "note": f"C2_density_aware={rate:.4f}; baseline={C2_BASELINE_RATE}",
    }


def sc_ds_random(c2da: dict[str, Any], crand: dict[str, Any]) -> dict[str, Any]:
    """SC_ds_random: C2_density_aware > C_rand_v2 (one-sided Fisher)."""
    a = c2da["investigated"]
    b = c2da["total"] - a
    c = crand["investigated"]
    d = crand["total"] - c
    p = fisher_exact_one_sided(a, b, c, d)
    passed = p < 0.05
    return {
        "name": "SC_ds_random",
        "description": "C2_density_aware investigability > C_rand_v2 (Fisher one-sided)",
        "test": "Fisher exact one-sided",
        "alpha": 0.05,
        "primary": False,
        "c2da_rate": c2da["investigability"],
        "crand_rate": crand["investigability"],
        "contingency": {"a": a, "b": b, "c": c, "d": d},
        "p_value": round(p, 4),
        "passed": passed,
        "note": (
            f"C2_da investigated={a}/{c2da['total']} vs C_rand investigated={c}/{crand['total']}; "
            f"p={p:.4f}"
        ),
    }


# ---------------------------------------------------------------------------
# Matched comparison (density-only bins)
# ---------------------------------------------------------------------------

def compute_matched_comparison(
    hyps: dict[str, list[dict[str, Any]]],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Density-only 3-bin matched comparison between C2_density_aware and C1."""

    # Build density + investigability records for C2_da and C1
    records_c2da: list[dict[str, Any]] = []
    records_c1: list[dict[str, Any]] = []

    density_threshold = load_json(
        os.path.join(RUN_022_DIR, "density_threshold.json")
    )

    for hyp in hyps["C2_density_aware"]:
        hid = hyp["id"]
        label = labels.get(hid, {})
        min_d = hyp.get("min_density", -1)
        inv = 1 if label.get("label_layer1", "not_investigated") != "not_investigated" else 0
        if min_d >= 0:
            records_c2da.append({"id": hid, "min_density": min_d, "investigated": inv})

    for hyp in hyps["C1_compose"]:
        hid = hyp["id"]
        label = labels.get(hid, {})
        inv = 1 if label.get("label_layer1", "not_investigated") != "not_investigated" else 0
        # C1 hypotheses don't have density in hypothesis file — use density_scores from run_021
        # For density, we use entity density from run_021 if available, else skip
        records_c1.append({"id": hid, "min_density": None, "investigated": inv})

    # For C1, load min_density from run_021 density_scores.json
    run021_density: dict[str, float] = {}
    try:
        ds = load_json(os.path.join(RUN_021_DIR, "density_scores.json"))
        for r in ds:
            if r.get("method") == "C1_compose":
                run021_density[r["id"]] = r.get("min_density", -1)
    except Exception:
        pass

    for rec in records_c1:
        if rec["id"] in run021_density:
            rec["min_density"] = run021_density[rec["id"]]

    # Only use records with valid density
    c2da_valid = [r for r in records_c2da if r["min_density"] is not None and r["min_density"] >= 0]
    c1_valid = [r for r in records_c1 if r["min_density"] is not None and r["min_density"] >= 0]

    # Compute density tertile thresholds from combined pool (C2_da + C1)
    all_densities = [r["min_density"] for r in c2da_valid + c1_valid]
    if len(all_densities) >= 3:
        p33 = percentile(all_densities, 0.333)
        p67 = percentile(all_densities, 0.667)
    else:
        p33 = p67 = 0.0

    def density_bin(d: float) -> str:
        if d < p33:
            return "den_low"
        elif d < p67:
            return "den_mid"
        return "den_high"

    # Compute per-cell stats
    bins = ["den_low", "den_mid", "den_high"]
    cells: list[dict[str, Any]] = []
    all_gaps: list[float] = []

    for b in bins:
        c2da_cell = [r for r in c2da_valid if density_bin(r["min_density"]) == b]
        c1_cell = [r for r in c1_valid if density_bin(r["min_density"]) == b]
        n_c2da = len(c2da_cell)
        n_c1 = len(c1_cell)
        sufficient = n_c2da >= 5 and n_c1 >= 5

        c2da_inv = sum(r["investigated"] for r in c2da_cell) / n_c2da if n_c2da else None
        c1_inv = sum(r["investigated"] for r in c1_cell) / n_c1 if n_c1 else None

        if c2da_inv is not None and c1_inv is not None:
            gap = round(c1_inv - c2da_inv, 4)
            all_gaps.append(abs(gap))
        else:
            gap = None

        cells.append({
            "cell": f"density={b}",
            "n_c2da": n_c2da,
            "n_c1": n_c1,
            "c2da_investigability": round(c2da_inv, 4) if c2da_inv is not None else None,
            "c1_investigability": round(c1_inv, 4) if c1_inv is not None else None,
            "gap_c1_minus_c2da": gap,
            "sufficient_n": sufficient,
        })

    # H_matched_parity verdict
    reportable_cells = [c for c in cells if c["sufficient_n"]]
    if reportable_cells:
        max_gap = max(abs(c["gap_c1_minus_c2da"]) for c in reportable_cells
                      if c["gap_c1_minus_c2da"] is not None)
        h_match_pass = max_gap <= MATCHED_GAP_THRESHOLD
        h_match_verdict = "supported" if h_match_pass else "rejected"
        h_match_note = (
            f"max reportable gap={max_gap:.4f} <= {MATCHED_GAP_THRESHOLD}: H_matched_parity supported"
            if h_match_pass else
            f"max reportable gap={max_gap:.4f} > {MATCHED_GAP_THRESHOLD}: H_matched_parity rejected"
        )
    else:
        max_gap = None
        h_match_verdict = "insufficient_data"
        h_match_note = "No cells with sufficient n (>=5) in both C2_da and C1"

    # Unmatched baseline
    c2da_overall = (
        sum(r["investigated"] for r in c2da_valid) / len(c2da_valid) if c2da_valid else 0.0
    )
    c1_overall = (
        sum(r["investigated"] for r in c1_valid) / len(c1_valid) if c1_valid else 0.0
    )

    return {
        "n_c2da_with_density": len(c2da_valid),
        "n_c1_with_density": len(c1_valid),
        "density_tertile_thresholds": {
            "p33": round(p33, 1),
            "p67": round(p67, 1),
        },
        "density_threshold_from_run_021": density_threshold.get("threshold"),
        "unmatched": {
            "c2da_investigability": round(c2da_overall, 4),
            "c1_investigability": round(c1_overall, 4),
            "gap_c1_minus_c2da": round(c1_overall - c2da_overall, 4),
        },
        "cells_density_only": cells,
        "n_reportable_cells": len(reportable_cells),
        "max_reportable_gap": round(max_gap, 4) if max_gap is not None else None,
        "h_match_verdict": h_match_verdict,
        "h_match_note": h_match_note,
        "h_match_criteria": {
            "parity_threshold": MATCHED_GAP_THRESHOLD,
            "pass_condition": f"all reportable cells gap <= {MATCHED_GAP_THRESHOLD}",
        },
    }


# ---------------------------------------------------------------------------
# Review memo
# ---------------------------------------------------------------------------

def build_review_memo(
    stats: dict[str, dict[str, Any]],
    tests: dict[str, Any],
    matched: dict[str, Any],
    n_c2da: int,
) -> str:
    """Build review_memo.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c2da = stats["C2_density_aware"]
    c1 = stats["C1_compose"]
    crand = stats["C_rand_v2"]

    sc_primary = tests["SC_ds_primary"]
    sc_improvement = tests["SC_ds_improvement"]
    sc_random = tests["SC_ds_random"]

    overall_go = sc_primary["passed"] and sc_random["passed"]

    memo = f"""# run_022 density-aware pair selection — review_memo.md
Generated: {now}

## 実験概要

**目的**: density-aware C2 pair selection により C1 との investigability parity を達成できるか検証。
**仮説**: H_density_select (parity), H_matched_parity (density-matched parity)
**参照**: run_021 にて H_ceiling 支持 (log_min_density: |r|=0.461)、低密度群のみ C1-C2 gap 集中。

## 実験条件

| 条件 | N | 説明 |
|------|---|------|
| C2_density_aware | {n_c2da} | density filter (min_density >= 8105.5)後の multi-op pipeline |
| C1_baseline | {c1['total']} | run_018 C1 再利用 |
| C_rand_v2 | {crand['total']} | run_018 C_rand_v2 再利用 |

**density threshold**: run_021 Q2_median = 8105.5

## 主要結果

| Method | N | Investigated | Investigability | Novel_Supported |
|--------|---|--------------|-----------------|-----------------|
| C2_density_aware | {c2da['total']} | {c2da['investigated']} | {c2da['investigability']:.3f} | {c2da['novel_supported']} |
| C1_baseline | {c1['total']} | {c1['investigated']} | {c1['investigability']:.3f} | {c1['novel_supported']} |
| C_rand_v2 | {crand['total']} | {crand['investigated']} | {crand['investigability']:.3f} | {crand['novel_supported']} |

## 統計検定

### SC_ds_primary (主検定): C2_density_aware parity with C1
- C2_da investigability: {sc_primary['c2da_rate']:.3f}
- C1 investigability: {sc_primary['c1_rate']:.3f}
- Delta: {sc_primary['delta']:.4f} (threshold: {PARITY_DELTA})
- Fisher two-sided p: {sc_primary['p_value']:.4f}
- Parity条件 (p>0.05): {'✓ PASS' if sc_primary['parity_p_condition'] else '✗ FAIL'}
- Delta条件 (<=0.02): {'✓ PASS' if sc_primary['parity_delta_condition'] else '✗ FAIL'}
- **判定: {'✓ PASS' if sc_primary['passed'] else '✗ FAIL'}**

### SC_ds_improvement: C2_da > run_018 C2 baseline (0.914)
- C2_da rate: {sc_improvement['c2da_rate']:.3f}
- **判定: {'✓ PASS' if sc_improvement['passed'] else '✗ FAIL'}**

### SC_ds_random: C2_da > C_rand_v2
- Fisher one-sided p: {sc_random['p_value']:.4f}
- **判定: {'✓ PASS' if sc_random['passed'] else '✗ FAIL'}**

## Matched Comparison (density-only bins)

- C1-C2_da gap (unmatched): {matched['unmatched']['gap_c1_minus_c2da']:.4f}
- Reportable cells: {matched['n_reportable_cells']}
- Max gap: {matched.get('max_reportable_gap', 'N/A')}
- **H_matched_parity: {matched['h_match_verdict'].upper()}**
- Note: {matched['h_match_note']}

## 総合判定

**GO/NO-GO: {'GO' if overall_go else 'NO-GO'}**

- SC_ds_primary (parity): {'PASS' if sc_primary['passed'] else 'FAIL'}
- SC_ds_improvement: {'PASS' if sc_improvement['passed'] else 'FAIL'}
- SC_ds_random: {'PASS' if sc_random['passed'] else 'FAIL'}

## 考察

"""
    # Add interpretation based on results
    if sc_primary["passed"]:
        memo += (
            "### H_density_select: 支持\n\n"
            f"density filter (min_density >= 8105.5) 適用後、C2_density_aware investigability は "
            f"{c2da['investigability']:.3f} となり、C1 investigability {c1['investigability']:.3f} と統計的に同等 "
            f"(Fisher two-sided p={sc_primary['p_value']:.4f} > 0.05, delta={sc_primary['delta']:.4f} <= 0.02)。\n\n"
            "run_021 で特定された density ceiling の影響を、density filter によって制御できることが確認された。\n"
        )
    else:
        memo += (
            "### H_density_select: 棄却\n\n"
            f"density filter 適用後も C2_density_aware ({c2da['investigability']:.3f}) と "
            f"C1 ({c1['investigability']:.3f}) の差が残存 "
            f"(p={sc_primary['p_value']:.4f}, delta={sc_primary['delta']:.4f})。\n\n"
        )
        if sc_primary["delta"] > PARITY_DELTA and sc_primary["parity_p_condition"]:
            memo += "p値は有意差なし (p>0.05) だが delta が閾値超過。効果量は小さいが実質的差異が残っている。\n"
        elif not sc_primary["parity_p_condition"] and sc_primary["parity_delta_condition"]:
            memo += "delta は閾値内だが Fisher p < 0.05。統計的有意差が残存。\n"
        else:
            memo += "density filter のみでは investigability gap を完全には解消できない。他の要因（novelty asymmetry 等）の影響が示唆される。\n"

    if sc_improvement["passed"]:
        memo += (
            f"\n### 改善確認\n\n"
            f"C2_density_aware ({c2da['investigability']:.3f}) は run_018 C2 baseline (0.914) を超えた。"
            f"density filter が C2 investigability 向上に有効であることが確認された。\n"
        )
    else:
        memo += (
            f"\n### 改善未達\n\n"
            f"C2_density_aware ({c2da['investigability']:.3f}) は run_018 C2 baseline (0.914) を超えなかった。"
        )

    memo += f"""
## 次のステップ

"""
    if overall_go:
        memo += (
            "- density-aware selection の有効性が確認された\n"
            "- threshold の最適化 (Q1/Q3 での感度分析) を検討\n"
            "- 他ドメインペアへの適用可能性を評価\n"
            "- 論文用図表の作成\n"
        )
    else:
        memo += (
            "- density filter のみでは不十分な場合、追加フィルタ条件を検討\n"
            "- novelty asymmetry の影響を制御する matched selection を検討\n"
            "- threshold の調整 (Q3 = 22743.0) で追加実験\n"
        )

    return memo


# ---------------------------------------------------------------------------
# density_aware_results.md
# ---------------------------------------------------------------------------

def build_results_doc(
    stats: dict[str, dict[str, Any]],
    tests: dict[str, Any],
    matched: dict[str, Any],
    threshold_data: dict[str, Any],
) -> str:
    """Build docs/scientific_hypothesis/density_aware_results.md."""
    now = datetime.now().strftime("%Y-%m-%d")
    c2da = stats["C2_density_aware"]
    c1 = stats["C1_compose"]
    crand = stats["C_rand_v2"]
    sc_p = tests["SC_ds_primary"]
    sc_i = tests["SC_ds_improvement"]
    sc_r = tests["SC_ds_random"]
    overall_go = sc_p["passed"] and sc_r["passed"]

    doc = f"""# Density-Aware Pair Selection Results (run_022)

Date: {now}
Registration: configs/density_aware_registry.json (frozen)

## Background

run_021 findings:
- H_ceiling supported: log_min_density is the strongest predictor of investigability (|r|=0.461)
- C1-C2 investigability gap concentrated in low-density group: gap=0.197
- Mid/high density groups: gap≈0 (C1≈C2)

Hypothesis: density-aware pair selection will restore C2-C1 parity by filtering out low-density cross-domain pairs.

## Density Threshold

- Source: run_021/quartile_analysis.json
- Metric: min_density = min(subject_density, object_density) from PubMed past corpus (<=2023)
- Threshold: **{threshold_data.get('threshold', 8105.5)} (Q2_median)**
- Q1={threshold_data.get('q1')}, Q2_median={threshold_data.get('q2_median')}, Q3={threshold_data.get('q3')}

Filter: keep candidate pairs where min_density >= {threshold_data.get('threshold', 8105.5)}

## Results Summary

| Method | N | Investigated | Investigability | Novel_Supported |
|--------|---|--------------|-----------------|-----------------|
| C2_density_aware | {c2da['total']} | {c2da['investigated']} | **{c2da['investigability']:.3f}** | {c2da['novel_supported']} |
| C1_baseline | {c1['total']} | {c1['investigated']} | **{c1['investigability']:.3f}** | {c1['novel_supported']} |
| C_rand_v2 | {crand['total']} | {crand['investigated']} | **{crand['investigability']:.3f}** | {crand['novel_supported']} |
| C2_baseline (run_018) | 70 | 64 | 0.914 | 11 | (reference) |

## Statistical Tests

| Test | Criterion | Result | Pass? |
|------|-----------|--------|-------|
| SC_ds_primary | Fisher two-sided p>0.05 AND delta<=0.02 | p={sc_p['p_value']:.4f}, delta={sc_p['delta']:.4f} | {'✓ PASS' if sc_p['passed'] else '✗ FAIL'} |
| SC_ds_improvement | C2_da > 0.914 | {sc_i['c2da_rate']:.4f} | {'✓ PASS' if sc_i['passed'] else '✗ FAIL'} |
| SC_ds_random | Fisher one-sided p<0.05 | p={sc_r['p_value']:.4f} | {'✓ PASS' if sc_r['passed'] else '✗ FAIL'} |

## Matched Comparison

Density-only bins (tertiles from combined C2_da + C1 pool):

| Cell | n(C2_da) | n(C1) | C2_da Inv. | C1 Inv. | Gap | Reportable |
|------|----------|-------|------------|---------|-----|------------|
"""
    for cell in matched.get("cells_density_only", []):
        rep = "Yes" if cell["sufficient_n"] else "No"
        gap = f"{cell['gap_c1_minus_c2da']:.4f}" if cell["gap_c1_minus_c2da"] is not None else "N/A"
        c2da_inv = f"{cell['c2da_investigability']:.3f}" if cell["c2da_investigability"] is not None else "N/A"
        c1_inv = f"{cell['c1_investigability']:.3f}" if cell["c1_investigability"] is not None else "N/A"
        doc += f"| {cell['cell']} | {cell['n_c2da']} | {cell['n_c1']} | {c2da_inv} | {c1_inv} | {gap} | {rep} |\n"

    max_gap = matched.get("max_reportable_gap")
    doc += f"""
H_matched_parity verdict: **{matched['h_match_verdict'].upper()}**
Max reportable gap: {max_gap if max_gap is not None else 'N/A'} (threshold: {MATCHED_GAP_THRESHOLD})
Note: {matched['h_match_note']}

## Overall Verdict

**{'GO' if overall_go else 'NO-GO'}**

H_density_select: {'Supported' if sc_p['passed'] else 'Rejected'}
H_matched_parity: {matched['h_match_verdict'].capitalize()}

## Interpretation

"""
    if overall_go:
        doc += (
            "Density-aware pair selection successfully restores C2-C1 investigability parity. "
            "The density ceiling identified in run_021 can be overcome by filtering out low-density "
            "cross-domain pairs (min_density < Q2_median). "
            f"C2_density_aware achieves {c2da['investigability']:.3f} investigability, "
            f"statistically equivalent to C1's {c1['investigability']:.3f}.\n\n"
            "This establishes a practical KG usage guideline: cross-domain composition is reliable "
            "when both entities have sufficient literature coverage (min_density >= 8105.5).\n"
        )
    else:
        doc += (
            "Density-aware pair selection did not achieve full C2-C1 parity. "
        )
        if not sc_p["parity_p_condition"] or not sc_p["parity_delta_condition"]:
            doc += (
                "The remaining gap suggests additional factors beyond literature density "
                "contribute to C2's investigability deficit. Possible explanations include: "
                "(1) novelty asymmetry — C2 inherently targets less-studied cross-domain pairs; "
                "(2) threshold sensitivity — Q2_median may not fully eliminate the problematic low-density regime; "
                "(3) dataset-specific effects of the bio_chem_kg_full.json structure.\n\n"
                "Recommended next step: sensitivity analysis with Q3 threshold (22743.0) or "
                "additional matched selection on novelty × density.\n"
            )

    return doc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run full statistical analysis for run_022."""
    print(f"\n{'='*60}")
    print(f"  run_022_analyze.py — statistical tests + matched comparison")
    print(f"{'='*60}\n")

    # Load data
    print("[Step 1] Loading hypotheses and labels...")
    hyps = load_hypotheses()
    labels = load_labels()
    threshold_data = load_json(os.path.join(RUN_022_DIR, "density_threshold.json"))
    print(f"  C2_density_aware: {len(hyps['C2_density_aware'])} hyps")
    print(f"  C1_compose: {len(hyps['C1_compose'])} hyps")
    print(f"  C_rand_v2: {len(hyps['C_rand_v2'])} hyps")
    print(f"  Labels: {len(labels)} total")

    # Compute stats per method
    print("\n[Step 2] Computing investigability statistics...")
    stats: dict[str, dict[str, Any]] = {}
    for method in ["C2_density_aware", "C1_compose", "C_rand_v2"]:
        method_labels = [labels[h["id"]] for h in hyps[method] if h["id"] in labels]
        stats[method] = compute_investigability(method_labels)
        s = stats[method]
        print(f"  {method}: {s['investigated']}/{s['total']} = {s['investigability']:.4f}")

    # Statistical tests
    print("\n[Step 3] Running statistical tests...")
    sc_p = sc_ds_primary(stats["C2_density_aware"], stats["C1_compose"])
    sc_i = sc_ds_improvement(stats["C2_density_aware"])
    sc_r = sc_ds_random(stats["C2_density_aware"], stats["C_rand_v2"])

    overall_go = sc_p["passed"] and sc_r["passed"]
    tests = {
        "SC_ds_primary": sc_p,
        "SC_ds_improvement": sc_i,
        "SC_ds_random": sc_r,
        "overall": {
            "go_nogo": "GO" if overall_go else "NO-GO",
            "sc_ds_primary": sc_p["passed"],
            "sc_ds_improvement": sc_i["passed"],
            "sc_ds_random": sc_r["passed"],
            "summary": (
                f"{'GO' if overall_go else 'NO-GO'} | "
                f"SC_ds_primary={'PASS' if sc_p['passed'] else 'FAIL'} | "
                f"SC_ds_improvement={'PASS' if sc_i['passed'] else 'FAIL'} | "
                f"SC_ds_random={'PASS' if sc_r['passed'] else 'FAIL'}"
            ),
        },
    }
    print(f"  SC_ds_primary (parity): {'PASS' if sc_p['passed'] else 'FAIL'}")
    print(f"  SC_ds_improvement: {'PASS' if sc_i['passed'] else 'FAIL'}")
    print(f"  SC_ds_random: {'PASS' if sc_r['passed'] else 'FAIL'}")
    print(f"  Overall: {tests['overall']['go_nogo']}")

    save_json(os.path.join(RUN_022_DIR, "statistical_tests.json"), tests)

    # Matched comparison
    print("\n[Step 4] Matched comparison (density-only bins)...")
    matched = compute_matched_comparison(hyps, labels)
    print(f"  H_matched_parity verdict: {matched['h_match_verdict']}")
    save_json(os.path.join(RUN_022_DIR, "matched_comparison.json"), matched)

    # Review memo
    print("\n[Step 5] Writing review_memo.md...")
    memo = build_review_memo(stats, tests, matched, len(hyps["C2_density_aware"]))
    save_text(os.path.join(RUN_022_DIR, "review_memo.md"), memo)

    # docs/scientific_hypothesis/density_aware_results.md
    print("\n[Step 6] Writing density_aware_results.md...")
    results_doc = build_results_doc(stats, tests, matched, threshold_data)
    save_text(os.path.join(DOCS_DIR, "density_aware_results.md"), results_doc)

    # Run config
    run_config = {
        "run_id": "run_022_density_aware_selection",
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Density-aware pair selection: C2_density_aware (min_density >= 8105.5) vs "
            "C1_baseline and C_rand_v2 (reused from run_018)"
        ),
        "seed": 42,
        "density_threshold": threshold_data.get("threshold"),
        "threshold_source": "run_021 Q2_median",
        "n_per_method": 70,
        "total": sum(len(hyps[m]) for m in hyps),
        "pre_registration": "configs/density_aware_registry.json",
        "source_runs": ["run_018_investigability_replication", "run_021_density_ceiling"],
        "methods": {
            "C2_density_aware": {
                "description": "Multi-op density-filtered pipeline",
                "n": len(hyps["C2_density_aware"]),
                "new_generation": True,
            },
            "C1_compose": {
                "description": "Single-op bio-only (reused from run_018)",
                "n": len(hyps["C1_compose"]),
                "new_generation": False,
            },
            "C_rand_v2": {
                "description": "Random baseline (reused from run_018)",
                "n": len(hyps["C_rand_v2"]),
                "new_generation": False,
            },
        },
        "results_summary": {
            "C2_density_aware_investigability": stats["C2_density_aware"]["investigability"],
            "C1_investigability": stats["C1_compose"]["investigability"],
            "C_rand_v2_investigability": stats["C_rand_v2"]["investigability"],
            "SC_ds_primary": "PASS" if sc_p["passed"] else "FAIL",
            "SC_ds_improvement": "PASS" if sc_i["passed"] else "FAIL",
            "SC_ds_random": "PASS" if sc_r["passed"] else "FAIL",
            "overall": tests["overall"]["go_nogo"],
        },
    }
    save_json(os.path.join(RUN_022_DIR, "run_config.json"), run_config)

    print(f"\n{'='*60}")
    print(f"  run_022 analysis complete")
    print(f"  Overall: {tests['overall']['go_nogo']}")
    print(f"  {tests['overall']['summary']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
