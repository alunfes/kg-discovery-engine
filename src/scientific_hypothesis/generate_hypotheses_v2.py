"""P1 Phase A: bridge_quality / alignment_precision conditions.

Run ID: run_020_cross_domain_phase_a
5 conditions × up to 30 hypotheses (pool = 70 C2 from run_018).

Conditions:
  C2_baseline:            Current multi-op pool, first 30 (no bridge filter)
  C2_bridge_quality:      Bridge confidence ≥ 0.7 (broad semantic synonyms)
  C2_alignment_precision: Bridge confidence ≥ 0.8 (strict token-overlap only)
  C2_novelty_ceiling:     combined_novelty ≤ T_high=0.75 (from run_019)
  C2_combined:            Bridge broad ≥ 0.7 AND novelty ≤ 0.75

Confidence scoring:
  exact_match (same core token):       1.0
  synonym_dict_match (broad dict):     0.8  — used for bridge_quality ≥ 0.7
  strict_synonym_match (token overlap):0.8  — used for alignment_precision ≥ 0.8
  camelcase_partial (substring share): 0.5  — below thresholds, not used
  fallback:                            0.3

Note: alignment_precision ≥ 0.8 is STRICTLY token-overlap only (no broad dict).
Note: novelty_ceiling target N may be < 30 (only 8/70 C2 hypotheses have
      combined_novelty ≤ 0.75 in run_019 corpus — structural pool constraint).

Usage:
    cd /path/to/kg-discovery-engine
    python -m src.scientific_hypothesis.generate_hypotheses_v2
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime
from typing import Any, Callable

SEED = 42
random.seed(SEED)

RUN_ID = "run_020_cross_domain_phase_a"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR = os.path.join(BASE_DIR, "runs", RUN_ID)

_C2_POOL_PATH = os.path.join(
    BASE_DIR, "runs", "run_018_investigability_replication", "hypotheses_c2.json"
)
_NOVELTY_PATH = os.path.join(
    BASE_DIR, "runs", "run_019_novelty_tradeoff_analysis", "novelty_scores.json"
)

T_HIGH = 0.75           # novelty ceiling from P3 recommendation
TARGET_PER_COND = 30    # max hypotheses per condition


# ---------------------------------------------------------------------------
# Bridge confidence scoring
# ---------------------------------------------------------------------------

def _core(entity_id: str) -> str:
    """Return the final component of a colon-separated entity ID."""
    return entity_id.split(":")[-1]


_TOKEN_STOPWORDS: frozenset[str] = frozenset({
    "protein", "pathway", "enzyme", "mechanism", "kinase", "process",
    "disease", "drug", "compound", "receptor", "target", "biomarker",
    "signaling", "activation", "inhibition", "tion", "ase",
})


def _key_tokens(core: str) -> frozenset[str]:
    """Extract meaningful tokens from a core entity name."""
    return frozenset(
        t for t in core.split("_")
        if t not in _TOKEN_STOPWORDS and len(t) > 2
    )


def _has_exact_match(src_core: str, dst_core: str) -> bool:
    """Return True if both cores share identical key tokens."""
    return bool(_key_tokens(src_core) & _key_tokens(dst_core))


# Broad semantic synonym pairs: known biomedical mechanism→target relationships.
# Both directions are stored (frozenset comparison is order-independent).
_BROAD_SYNONYM_PAIRS: frozenset[frozenset[str]] = frozenset({
    # HDAC inhibition → epigenetic targets
    frozenset({"hdac_inhibition", "epigenetic_silencing"}),
    frozenset({"hdac_inhibition", "p53_pathway"}),
    frozenset({"hdac_inhibition", "bdnf"}),
    # BCL-2 family → apoptosis/senescence
    frozenset({"bcl2_protein", "apoptosis"}),
    frozenset({"bcl2_protein", "cell_senescence"}),
    frozenset({"bcl2_inhibition", "apoptosis"}),
    # VEGFR inhibition → angiogenesis
    frozenset({"vegfr_inhibition", "tumor_angiogenesis"}),
    # BACE1 → amyloid/neuroinflammation
    frozenset({"bace1_enzyme", "amyloid_cascade"}),
    frozenset({"bace1_enzyme", "app"}),
    frozenset({"bace1_enzyme", "neuroinflammation"}),
    # AMPK activation → downstream metabolic targets
    frozenset({"ampk_activation", "insulin_resistance"}),
    frozenset({"ampk_activation", "cholesterol_synthesis"}),
    frozenset({"ampk_activation", "neuroinflammation"}),
    frozenset({"ampk_activation", "nrf2"}),
    frozenset({"ampk_activation", "oxidative_stress"}),
    frozenset({"ampk_activation", "autophagy"}),
    frozenset({"ampk_activation", "cell_senescence"}),
    # Direct drug effects
    frozenset({"metformin", "ampk_pathway"}),
    # COX inhibition → inflammatory targets
    frozenset({"cox_inhibition", "tnf_alpha"}),
    frozenset({"cox_inhibition", "amyloid_cascade"}),
    frozenset({"cox_inhibition", "neuroinflammation"}),
    # EGFR → downstream kinase cascades
    frozenset({"egfr_kinase", "pi3k_akt"}),
    frozenset({"egfr_kinase", "mapk_erk"}),
    # STAT3 → multiple downstream nodes
    frozenset({"stat3_inhibition", "nfkb_signaling"}),
    frozenset({"stat3_inhibition", "mapk_erk"}),
    frozenset({"stat3_inhibition", "neuroinflammation"}),
    frozenset({"stat3_inhibition", "oxidative_stress"}),
    frozenset({"stat3_inhibition", "pi3k_akt"}),
    # NRF2 → NF-kB axis
    frozenset({"nrf2_activation", "nfkb_signaling"}),
})


def score_bridge_strict(src_id: str, dst_id: str) -> float:
    """Score bridge for alignment_precision: exact token overlap only (0.8 or 0.3)."""
    src_c, dst_c = _core(src_id), _core(dst_id)
    if src_c == dst_c:
        return 1.0
    if _has_exact_match(src_c, dst_c):
        return 0.8
    return 0.3


def score_bridge_broad(src_id: str, dst_id: str) -> float:
    """Score bridge for bridge_quality: token overlap + broad semantic synonyms."""
    strict = score_bridge_strict(src_id, dst_id)
    if strict >= 0.8:
        return strict
    pair = frozenset({_core(src_id), _core(dst_id)})
    if pair in _BROAD_SYNONYM_PAIRS:
        return 0.8
    return 0.3


def max_bridge_confidence(
    hyp: dict[str, Any], scorer: Callable[[str, str], float]
) -> float:
    """Return max bridge confidence over all cross-domain edges in provenance."""
    prov: list[str] = hyp.get("provenance", [])
    best = 0.0
    for i in range(0, len(prov) - 2, 2):
        src, dst = prov[i], prov[i + 2]
        s_chem = src.startswith("chem:")
        d_chem = dst.startswith("chem:")
        if s_chem != d_chem:          # cross-domain bridge
            c = scorer(src, dst)
            if c > best:
                best = c
    return best if best > 0.0 else 0.3   # default if no explicit bridge found


# ---------------------------------------------------------------------------
# Condition generators
# ---------------------------------------------------------------------------

def _load_c2_pool() -> list[dict[str, Any]]:
    """Load 70 C2 multi-op hypotheses from run_018."""
    with open(_C2_POOL_PATH, encoding="utf-8") as f:
        return json.load(f)["hypotheses"]


def _load_novelty_index() -> dict[str, float]:
    """Return {hypothesis_id: combined_novelty} from run_019."""
    with open(_NOVELTY_PATH, encoding="utf-8") as f:
        records = json.load(f)
    return {r["id"]: r["combined_novelty"] for r in records}


def _select(
    pool: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    target: int,
    rng: random.Random,
    condition: str,
) -> list[dict[str, Any]]:
    """Filter pool by predicate, shuffle deterministically, take up to target."""
    qualified = [h for h in pool if predicate(h)]
    rng.shuffle(qualified)
    selected = qualified[:target]
    print(
        f"  [{condition}] pool={len(pool)}, qualified={len(qualified)}, "
        f"selected={len(selected)}"
    )
    return selected


def _tag(hyps: list[dict[str, Any]], condition: str) -> list[dict[str, Any]]:
    """Return shallow copies of hyps with condition tag added."""
    return [{**h, "condition": condition} for h in hyps]


def generate_conditions(
    pool: list[dict[str, Any]],
    novelty_index: dict[str, float],
    rng: random.Random,
) -> dict[str, list[dict[str, Any]]]:
    """Generate all 5 experimental conditions from the C2 pool."""

    # C2_baseline: first TARGET_PER_COND (no filter), stable order by ID
    baseline_sorted = sorted(pool, key=lambda h: h["id"])
    baseline = baseline_sorted[:TARGET_PER_COND]
    print(f"  [C2_baseline] selected={len(baseline)}")

    # C2_bridge_quality: broad bridge ≥ 0.7
    bq = _select(
        pool,
        predicate=lambda h: max_bridge_confidence(h, score_bridge_broad) >= 0.7,
        target=TARGET_PER_COND,
        rng=random.Random(SEED),
        condition="C2_bridge_quality",
    )

    # C2_alignment_precision: strict token-overlap ≥ 0.8
    ap = _select(
        pool,
        predicate=lambda h: max_bridge_confidence(h, score_bridge_strict) >= 0.8,
        target=TARGET_PER_COND,
        rng=random.Random(SEED),
        condition="C2_alignment_precision",
    )

    # C2_novelty_ceiling: combined_novelty ≤ T_HIGH
    nc = _select(
        pool,
        predicate=lambda h: novelty_index.get(h["id"], 1.0) <= T_HIGH,
        target=TARGET_PER_COND,
        rng=random.Random(SEED),
        condition="C2_novelty_ceiling",
    )

    # C2_combined: broad bridge ≥ 0.7 AND novelty ≤ T_HIGH
    comb = _select(
        pool,
        predicate=lambda h: (
            max_bridge_confidence(h, score_bridge_broad) >= 0.7
            and novelty_index.get(h["id"], 1.0) <= T_HIGH
        ),
        target=TARGET_PER_COND,
        rng=random.Random(SEED),
        condition="C2_combined",
    )

    return {
        "C2_baseline":            _tag(baseline, "C2_baseline"),
        "C2_bridge_quality":      _tag(bq,       "C2_bridge_quality"),
        "C2_alignment_precision": _tag(ap,       "C2_alignment_precision"),
        "C2_novelty_ceiling":     _tag(nc,       "C2_novelty_ceiling"),
        "C2_combined":            _tag(comb,     "C2_combined"),
    }


# ---------------------------------------------------------------------------
# Bridge confidence diagnostics
# ---------------------------------------------------------------------------

def compute_bridge_stats(
    pool: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compute per-hypothesis bridge confidence scores for both scorers."""
    rows: list[dict[str, Any]] = []
    for h in pool:
        broad_c = max_bridge_confidence(h, score_bridge_broad)
        strict_c = max_bridge_confidence(h, score_bridge_strict)
        rows.append({
            "id": h["id"],
            "subject_id": h["subject_id"],
            "object_id": h["object_id"],
            "bridge_confidence_broad": broad_c,
            "bridge_confidence_strict": strict_c,
        })
    broad_ge07 = sum(1 for r in rows if r["bridge_confidence_broad"] >= 0.7)
    strict_ge08 = sum(1 for r in rows if r["bridge_confidence_strict"] >= 0.8)
    return {
        "total_pool": len(rows),
        "broad_ge_0_7": broad_ge07,
        "strict_ge_0_8": strict_ge08,
        "per_hypothesis": rows,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate 5 × N hypotheses for run_020 and write all artifacts."""
    print(f"\n{'='*60}")
    print(f"  generate_hypotheses_v2.py — P1 Phase A: bridge_quality / alignment_precision")
    print(f"  Seed={SEED}, T_high={T_HIGH}, target_per_cond={TARGET_PER_COND}")
    print(f"{'='*60}\n")

    rng = random.Random(SEED)
    pool = _load_c2_pool()
    novelty_index = _load_novelty_index()
    print(f"[Step 1] Loaded {len(pool)} C2 hypotheses from run_018")
    print(f"         Novelty scores: {len(novelty_index)} entries from run_019\n")

    print("[Step 2] Bridge confidence diagnostics...")
    bridge_stats = compute_bridge_stats(pool)
    print(f"  Broad ≥ 0.7:  {bridge_stats['broad_ge_0_7']} / {bridge_stats['total_pool']}")
    print(f"  Strict ≥ 0.8: {bridge_stats['strict_ge_0_8']} / {bridge_stats['total_pool']}\n")

    print("[Step 3] Generating 5 conditions...")
    conditions = generate_conditions(pool, novelty_index, rng)

    total = sum(len(v) for v in conditions.values())
    print(f"\n  Total hypotheses across conditions: {total}")

    os.makedirs(RUN_DIR, exist_ok=True)

    def p(fname: str) -> str:
        return os.path.join(RUN_DIR, fname)

    print("\n[Step 4] Saving condition files...")
    condition_counts: dict[str, int] = {}
    for cond_name, hyps in conditions.items():
        fname = f"hypotheses_{cond_name.lower()}.json"
        _save_json(
            {
                "run_id": RUN_ID,
                "condition": cond_name,
                "count": len(hyps),
                "hypotheses": hyps,
            },
            p(fname),
        )
        condition_counts[cond_name] = len(hyps)

    _save_json(bridge_stats, p("bridge_confidence_stats.json"))

    # Unique hypothesis IDs across all conditions (for deduped PubMed validation)
    all_ids: dict[str, dict[str, Any]] = {}
    for cond_hyps in conditions.values():
        for h in cond_hyps:
            all_ids[h["id"]] = h
    unique_hyps = list(all_ids.values())
    _save_json(
        {"run_id": RUN_ID, "unique_hypothesis_pool": unique_hyps},
        p("unique_hypotheses.json"),
    )
    print(f"\n  Unique hypotheses (for PubMed): {len(unique_hyps)}")

    # Run config
    cfg = {
        "run_id": RUN_ID,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "P1 Phase A: bridge_quality / alignment_precision conditions. "
            f"5 conditions, pool=70 C2 from run_018, T_high={T_HIGH}."
        ),
        "seed": SEED,
        "t_high": T_HIGH,
        "target_per_condition": TARGET_PER_COND,
        "condition_counts": condition_counts,
        "total_unique_hypotheses": len(unique_hyps),
        "source": {
            "hypothesis_pool": "runs/run_018_investigability_replication/hypotheses_c2.json",
            "novelty_scores": "runs/run_019_novelty_tradeoff_analysis/novelty_scores.json",
        },
        "conditions": {
            "C2_baseline": "First 30 from C2 pool (no filter), ordered by ID",
            "C2_bridge_quality": "Bridge broad confidence ≥ 0.7 (broad semantic synonyms)",
            "C2_alignment_precision": "Bridge strict confidence ≥ 0.8 (token-overlap only)",
            "C2_novelty_ceiling": f"combined_novelty ≤ {T_HIGH} (from run_019)",
            "C2_combined": f"bridge_broad ≥ 0.7 AND novelty ≤ {T_HIGH}",
        },
        "note_underpowered": (
            "C2_alignment_precision, C2_novelty_ceiling, and C2_combined may have "
            "N < 30 due to structural constraints of the run_018 pool. "
            "C2_novelty_ceiling: pool mean combined_novelty = 0.833 > T_high=0.75; "
            "only ~8/70 hypotheses qualify."
        ),
        "success_criteria": {
            "primary": (
                "bridge_quality OR alignment_precision investigability ≥ 0.95"
            ),
            "go_phase_b": (
                "At least one filtered condition achieves investigability ≥ 0.95"
            ),
            "no_go": (
                "All conditions investigability ≤ 0.92 → structural KG problem"
            ),
        },
        "reference": {
            "C1_investigability": 0.971,
            "C2_baseline_investigability_run018": 0.914,
        },
    }
    _save_json(cfg, p("run_config.json"))

    print(f"\n{'='*60}")
    print(f"  Conditions generated:")
    for cond_name, cnt in condition_counts.items():
        note = " ← underpowered" if cnt < 20 else (" ← reduced N" if cnt < 30 else "")
        print(f"    {cond_name:30s}: N={cnt}{note}")
    print(f"  Artifacts saved to {RUN_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
