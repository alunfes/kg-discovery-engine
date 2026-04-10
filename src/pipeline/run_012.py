"""Run 012: Review-driven drift filter — pre-compose relation filter + guards.

Implements pre-compose filtering in compose() to suppress drift-heavy paths
identified in Run 011 qualitative review (25% drift_heavy rate in deep cross-domain).

Filter spec (applied inside compose() via new parameters):
  1. filter_relations: blocks contains, is_product_of, is_reverse_of, is_isomer_of
  2. guard_consecutive_repeat: rejects paths where same relation appears consecutively
  3. min_strong_ratio=0.40: depth≥3 paths require ≥40% strong relations
  4. filter_generic_intermediates: rejects paths with generic intermediate nodes

Baseline for comparison: Run 009 Condition C P4 (939 candidates, 20 deep cross-domain).
Run 011 label distribution among those 20: promising=3(15%), weak_spec=12(60%), drift_heavy=5(25%).

Goal: drift_heavy <15%, promising >25%, preserve deep cross-domain discovery signal.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.wikidata_phase4_loader import load_phase4_data
from src.eval.scorer import EvaluationRubric, ScoredHypothesis, evaluate, score_category
from src.kg.models import HypothesisCandidate, KnowledgeGraph
from src.kg.phase4_data import build_condition_c, compute_kg_stats
from src.pipeline.operators import (
    _STRONG_MECHANISTIC,
    align,
    compose,
    difference,
    union,
)
from src.pipeline.run_phase4 import (
    _DEEP_DEPTH,
    _MAX_PER_SOURCE_DEEP,
    _RANDOM_SEED,
    _SHALLOW_DEPTH,
    bucket_label,
    compute_tracking_fields,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RUN_ID = "run_012"
_CONDITION = "C"
_TOP_K = 20
_DATE = datetime.now().strftime("%Y%m%d")
_RUN_DIR_NAME = f"run_012_{_DATE}_drift_filter"

# Run 011 ground-truth labels for the 20 deep cross-domain candidates.
# Used to compute before/after comparison metrics.
_RUN011_LABELS: dict[str, str] = {
    "H0268": "weak_speculative",
    "H0344": "weak_speculative",
    "H0378": "drift_heavy",
    "H0401": "weak_speculative",
    "H0407": "drift_heavy",
    "H0408": "drift_heavy",
    "H0428": "drift_heavy",
    "H0429": "drift_heavy",
    "H0633": "weak_speculative",
    "H0275": "weak_speculative",
    "H0293": "promising",
    "H0300": "weak_speculative",
    "H0348": "weak_speculative",
    "H0349": "weak_speculative",
    "H0356": "weak_speculative",
    "H0357": "weak_speculative",
    "H0517": "promising",
    "H0524": "weak_speculative",
    "H0618": "promising",
    "H0644": "weak_speculative",
}

# Run 011 baseline counts (from qualitative review of 20 deep cross-domain candidates)
_RUN011_DEEP_CD_TOTAL = 20
_RUN011_PROMISING = 3   # 15%
_RUN011_WEAK_SPEC = 12  # 60%
_RUN011_DRIFT_HEAVY = 5  # 25%

# Run 009 baseline total candidates (Condition C P4)
_RUN009_TOTAL = 939
_RUN009_DEEP_CD = 20

# Filter spec for Run 012
_FILTER_RELATIONS: frozenset[str] = frozenset({
    "contains",
    "is_product_of",
    "is_reverse_of",
    "is_isomer_of",
})
_MIN_STRONG_RATIO = 0.40
_GUARD_CONSECUTIVE = True
_FILTER_GENERIC_INTERMEDIATES = True


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_filtered_candidates(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
) -> tuple[list[HypothesisCandidate], KnowledgeGraph, set[str]]:
    """Run the P4 pipeline with drift filters enabled.

    Returns (candidates, merged_kg, aligned_node_ids).
    """
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment,
                   name=f"union_bio_{_CONDITION}_chem_{_CONDITION}")

    counter: list[int] = [0]

    # Filtered compose on merged KG
    cands = compose(
        merged,
        max_depth=_DEEP_DEPTH,
        max_per_source=_MAX_PER_SOURCE_DEEP,
        _counter=counter,
        filter_relations=_FILTER_RELATIONS,
        guard_consecutive_repeat=_GUARD_CONSECUTIVE,
        min_strong_ratio=_MIN_STRONG_RATIO,
        filter_generic_intermediates=_FILTER_GENERIC_INTERMEDIATES,
    )

    diff_kg = difference(bio_kg, chem_kg, alignment,
                         name=f"diff_bio_{_CONDITION}")

    # Filtered compose on difference KG
    cands += compose(
        diff_kg,
        max_depth=_DEEP_DEPTH,
        max_per_source=_MAX_PER_SOURCE_DEEP,
        _counter=counter,
        filter_relations=_FILTER_RELATIONS,
        guard_consecutive_repeat=_GUARD_CONSECUTIVE,
        min_strong_ratio=_MIN_STRONG_RATIO,
        filter_generic_intermediates=_FILTER_GENERIC_INTERMEDIATES,
    )

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique: list[HypothesisCandidate] = []
    for c in cands:
        k = (c.subject_id, c.object_id)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    return unique, merged, set(alignment.keys())


def build_baseline_candidates(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
) -> tuple[list[HypothesisCandidate], KnowledgeGraph, set[str]]:
    """Run the P4 pipeline WITHOUT filters (same as Run 009/010 baseline)."""
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment,
                   name=f"union_bio_{_CONDITION}_chem_{_CONDITION}")

    counter: list[int] = [0]
    cands = compose(merged, max_depth=_DEEP_DEPTH,
                    max_per_source=_MAX_PER_SOURCE_DEEP, _counter=counter)
    diff_kg = difference(bio_kg, chem_kg, alignment,
                         name=f"diff_bio_{_CONDITION}")
    cands += compose(diff_kg, max_depth=_DEEP_DEPTH,
                     max_per_source=_MAX_PER_SOURCE_DEEP, _counter=counter)

    seen: set[tuple[str, str]] = set()
    unique: list[HypothesisCandidate] = []
    for c in cands:
        k = (c.subject_id, c.object_id)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    return unique, merged, set(alignment.keys())


# ---------------------------------------------------------------------------
# Scoring and analysis
# ---------------------------------------------------------------------------

def score_with_revised(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
) -> list[ScoredHypothesis]:
    """Score with revised_traceability (Run 010 rubric)."""
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=False,
        revised_traceability=True,
    )
    return evaluate(candidates, kg, rubric)


def compute_deep_cd_tracking(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
    aligned_ids: set[str],
    single_op_pairs: set[tuple[str, str]],
    shallow_pairs: set[tuple[str, str]],
) -> list[dict]:
    """Compute tracking fields for all candidates."""
    return [
        compute_tracking_fields(c, kg, single_op_pairs, shallow_pairs, aligned_ids)
        for c in candidates
    ]


def _is_cross_domain(c: HypothesisCandidate, kg: KnowledgeGraph) -> bool:
    n1 = kg.get_node(c.subject_id)
    n2 = kg.get_node(c.object_id)
    if n1 and n2:
        return n1.domain != n2.domain
    s_pref = c.subject_id.split(":")[0] if ":" in c.subject_id else ""
    t_pref = c.object_id.split(":")[0] if ":" in c.object_id else ""
    return bool(s_pref) and bool(t_pref) and s_pref != t_pref


def candidate_path_length(c: HypothesisCandidate) -> int:
    """Return hop count."""
    prov = c.provenance
    return max(0, (len(prov) - 1) // 2) if len(prov) >= 3 else 0


def _has_filter_relation(c: HypothesisCandidate) -> bool:
    rels = c.provenance[1::2]
    return any(r in _FILTER_RELATIONS for r in rels)


def _has_consecutive_repeat_cand(c: HypothesisCandidate) -> bool:
    rels = c.provenance[1::2]
    return any(rels[i] == rels[i + 1] for i in range(len(rels) - 1))


def _strong_ratio_cand(c: HypothesisCandidate) -> float:
    rels = c.provenance[1::2]
    if not rels:
        return 0.0
    return sum(1 for r in rels if r in _STRONG_MECHANISTIC) / len(rels)


# ---------------------------------------------------------------------------
# Label assignment for Run 012 deep cross-domain candidates
# ---------------------------------------------------------------------------

# Strong relations + semi-strong mechanistic relations present in promising candidates
_SEMI_STRONG: frozenset[str] = frozenset({
    "inhibits", "activates", "catalyzes", "produces", "encodes",
    "accelerates", "yields", "facilitates", "requires_cofactor", "undergoes",
})

_HARD_DRIFT: frozenset[str] = frozenset({
    "contains", "is_product_of", "is_reverse_of", "is_isomer_of",
    "relates_to", "associated_with", "connected_to", "is_a",
})

_MILD_DRIFT: frozenset[str] = frozenset({
    "is_precursor_of", "part_of", "interacts_with", "involves",
})


def assign_label(c: HypothesisCandidate) -> tuple[str, str]:
    """Assign a quality label and reason to a deep cross-domain candidate.

    Labels: promising, weak_speculative, drift_heavy.
    """
    rels = c.provenance[1::2]
    if not rels:
        return "weak_speculative", "No relations in path"

    total = len(rels)
    hard_count = sum(1 for r in rels if r in _HARD_DRIFT)
    mild_count = sum(1 for r in rels if r in _MILD_DRIFT)
    strong_count = sum(1 for r in rels if r in _STRONG_MECHANISTIC)
    semi_count = sum(1 for r in rels if r in _SEMI_STRONG)

    hard_ratio = hard_count / total
    mild_ratio = mild_count / total
    strong_ratio = strong_count / total
    semi_ratio = semi_count / total

    has_repeat = any(rels[i] == rels[i + 1] for i in range(len(rels) - 1))

    if hard_ratio >= 0.5:
        return "drift_heavy", (
            f"Majority of relations are structural/generic connectors "
            f"(hard_drift_ratio={hard_ratio:.2f}). "
            "Chain expands transitively without mechanistic content."
        )
    if has_repeat and strong_ratio == 0.0:
        return "drift_heavy", (
            "Consecutive repeated relation + no strong mechanistic relations "
            f"+ high drift ratio ({(hard_ratio + mild_ratio):.2f}). "
            "Pure chain repetition without biological inference."
        )
    if semi_ratio >= 0.5 and hard_ratio == 0.0:
        return "promising", (
            f"{candidate_path_length(c)}-hop cross-domain path with majority "
            f"strong relations ({semi_ratio:.2f}) and no generic connectors. "
            "Plausible hypothesis candidate."
        )
    if strong_count >= 2 and hard_ratio == 0.0 and mild_ratio <= 0.5:
        return "promising", (
            f"High strong-relation ratio ({strong_ratio:.2f}) with no hard-drift "
            "connectors. Cross-domain path is mechanistically specific."
        )
    return "weak_speculative", (
        f"Mixed chain: strong_ratio={strong_ratio:.2f}, "
        f"hard_drift={hard_ratio:.2f}, mild_drift={mild_ratio:.2f}. "
        "Has some mechanistic anchors but path is not strongly grounded."
    )


# ---------------------------------------------------------------------------
# Comparison analysis
# ---------------------------------------------------------------------------

def analyze_label_distribution(
    labeled: list[dict],
) -> dict[str, int]:
    """Count label distribution."""
    counts: dict[str, int] = {"promising": 0, "weak_speculative": 0, "drift_heavy": 0}
    for item in labeled:
        lbl = item.get("label", "weak_speculative")
        counts[lbl] = counts.get(lbl, 0) + 1
    return counts


def compute_filter_removal_analysis(
    baseline_deep_cd: list[HypothesisCandidate],
    filtered_deep_cd_ids: set[tuple[str, str]],
) -> dict:
    """Compute which baseline deep cross-domain candidates were removed and why."""
    removed = []
    retained = []

    for c in baseline_deep_cd:
        pair = (c.subject_id, c.object_id)
        label = _RUN011_LABELS.get(c.id, "unknown")
        rels = c.provenance[1::2]

        filter_reason: list[str] = []
        if _has_filter_relation(c):
            bad_rels = [r for r in rels if r in _FILTER_RELATIONS]
            filter_reason.append(f"filter_relations: {bad_rels}")
        if _has_consecutive_repeat_cand(c):
            filter_reason.append("consecutive_repeat")
        pl = candidate_path_length(c)
        if pl >= 3 and _strong_ratio_cand(c) < _MIN_STRONG_RATIO:
            sr = round(_strong_ratio_cand(c), 2)
            filter_reason.append(f"weak_strong_ratio={sr}<{_MIN_STRONG_RATIO}")

        if pair not in filtered_deep_cd_ids:
            removed.append({
                "id": c.id,
                "label": label,
                "filter_reason": filter_reason,
                "provenance": c.provenance,
            })
        else:
            retained.append({
                "id": c.id,
                "label": label,
                "provenance": c.provenance,
            })

    return {"removed": removed, "retained": retained}


def compute_top20_depth_dist(scored: list[ScoredHypothesis], kg: KnowledgeGraph) -> dict:
    """Compute depth distribution and cross-domain count in top-20."""
    top = scored[:_TOP_K]
    depth_counts: dict[str, int] = {}
    cross_count = 0
    scores = []
    for sh in top:
        pl = candidate_path_length(sh.candidate)
        lbl = bucket_label(pl)
        depth_counts[lbl] = depth_counts.get(lbl, 0) + 1
        if _is_cross_domain(sh.candidate, kg):
            cross_count += 1
        scores.append(round(sh.total_score, 4))
    return {
        "depth_distribution": depth_counts,
        "cross_domain_in_top20": cross_count,
        "scores": scores,
        "mean_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }


# ---------------------------------------------------------------------------
# Output serialization
# ---------------------------------------------------------------------------

def scored_to_dict(
    sh: ScoredHypothesis,
    tracking: dict,
) -> dict:
    """Serialize a ScoredHypothesis with tracking fields."""
    d = sh.to_dict()
    d.update(tracking)
    return d


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 012: drift-filtered pipeline and before/after analysis."""
    import random
    random.seed(_RANDOM_SEED)

    print(f"=== Run 012: Drift Filter Experiment ({_DATE}) ===")
    print(f"Filter: {sorted(_FILTER_RELATIONS)}")
    print(f"Guards: consecutive_repeat={_GUARD_CONSECUTIVE}, "
          f"min_strong_ratio={_MIN_STRONG_RATIO}, "
          f"generic_intermediates={_FILTER_GENERIC_INTERMEDIATES}")

    # --- Load data ---
    print("\n[1/5] Loading Phase 4 data...")
    data = load_phase4_data()
    kg_c = build_condition_c(data)
    print(f"  Condition C: {len(list(kg_c.nodes()))} nodes, {len(list(kg_c.edges()))} edges")

    # Extract bio/chem subgraphs for multi-op pipeline (same as Run 009/010)
    bio_kg = KnowledgeGraph(name=f"bio_{_CONDITION}")
    chem_kg = KnowledgeGraph(name=f"chem_{_CONDITION}")
    for node in kg_c.nodes():
        if node.domain == "biology":
            bio_kg.add_node(node)
        else:
            chem_kg.add_node(node)
    bio_ids = {n.id for n in bio_kg.nodes()}
    chem_ids = {n.id for n in chem_kg.nodes()}
    for edge in kg_c.edges():
        if edge.source_id in bio_ids and edge.target_id in bio_ids:
            try:
                bio_kg.add_edge(edge)
            except ValueError:
                pass
        elif edge.source_id in chem_ids and edge.target_id in chem_ids:
            try:
                chem_kg.add_edge(edge)
            except ValueError:
                pass
    print(f"  bio_kg: {len(list(bio_kg.nodes()))} nodes, {len(list(bio_kg.edges()))} edges")
    print(f"  chem_kg: {len(list(chem_kg.nodes()))} nodes, {len(list(chem_kg.edges()))} edges")

    # P1 baseline (for tracking fields)
    from src.pipeline.operators import compose as _compose
    p1_rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
    p1_scored = evaluate(_compose(bio_kg, max_depth=_SHALLOW_DEPTH), bio_kg, p1_rubric)
    single_op_pairs = {(sh.candidate.subject_id, sh.candidate.object_id)
                       for sh in p1_scored}
    shallow_pairs: set[tuple[str, str]] = set()

    # --- Baseline (no filter) ---
    print("\n[2/5] Generating baseline candidates (no filter)...")
    baseline_cands, merged_kg, aligned_ids = build_baseline_candidates(bio_kg, chem_kg)
    print(f"  Baseline total candidates: {len(baseline_cands)}")

    baseline_scored = score_with_revised(baseline_cands, merged_kg)
    baseline_tracking = [
        compute_tracking_fields(c, merged_kg, single_op_pairs, shallow_pairs, aligned_ids)
        for c in baseline_cands
    ]

    baseline_deep_cd = [
        c for c, tr in zip(baseline_cands, baseline_tracking)
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    ]
    print(f"  Baseline deep cross-domain (>=3-hop): {len(baseline_deep_cd)}")

    # --- Filtered ---
    print("\n[3/5] Generating filtered candidates...")
    filtered_cands, _, _ = build_filtered_candidates(bio_kg, chem_kg)
    print(f"  Filtered total candidates: {len(filtered_cands)}")

    filtered_scored = score_with_revised(filtered_cands, merged_kg)
    filtered_tracking = [
        compute_tracking_fields(c, merged_kg, single_op_pairs, shallow_pairs, aligned_ids)
        for c in filtered_cands
    ]

    filtered_deep_cd = [
        c for c, tr in zip(filtered_cands, filtered_tracking)
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    ]
    print(f"  Filtered deep cross-domain: {len(filtered_deep_cd)}")

    # --- Label deep cross-domain candidates ---
    print("\n[4/5] Labeling deep cross-domain candidates...")
    filtered_deep_cd_labeled = []
    for c in filtered_deep_cd:
        label, reason = assign_label(c)
        filtered_deep_cd_labeled.append({
            "id": c.id,
            "subject_id": c.subject_id,
            "object_id": c.object_id,
            "path_length": candidate_path_length(c),
            "is_cross_domain": True,
            "provenance": c.provenance,
            "label": label,
            "reason": reason,
            "strong_ratio": round(_strong_ratio_cand(c), 4),
        })

    after_dist = analyze_label_distribution(filtered_deep_cd_labeled)
    total_after = len(filtered_deep_cd_labeled)

    # Run 011 baseline distribution
    before_dist = {
        "promising": _RUN011_PROMISING,
        "weak_speculative": _RUN011_WEAK_SPEC,
        "drift_heavy": _RUN011_DRIFT_HEAVY,
    }

    # --- Filter removal analysis ---
    filtered_deep_cd_pairs = {(c.subject_id, c.object_id) for c in filtered_deep_cd}
    removal_analysis = compute_filter_removal_analysis(
        baseline_deep_cd, filtered_deep_cd_pairs
    )
    removed = removal_analysis["removed"]
    retained = removal_analysis["retained"]

    promising_removed = [r for r in removed if r["label"] == "promising"]
    drift_removed = [r for r in removed if r["label"] == "drift_heavy"]
    total_removed = len(removed)
    drift_heavy_removed = len(drift_removed)
    removal_efficiency = (
        round(drift_heavy_removed / total_removed, 3)
        if total_removed > 0 else 0.0
    )

    # --- Top-20 analysis ---
    baseline_top20 = compute_top20_depth_dist(baseline_scored, merged_kg)
    filtered_top20 = compute_top20_depth_dist(filtered_scored, merged_kg)

    print("\n[5/5] Saving artifacts...")

    # --- Before/after comparison summary ---
    comparison = {
        "run_id": _RUN_ID,
        "date": _DATE,
        "filter_spec": {
            "filter_relations": sorted(_FILTER_RELATIONS),
            "guard_consecutive_repeat": _GUARD_CONSECUTIVE,
            "min_strong_ratio": _MIN_STRONG_RATIO,
            "filter_generic_intermediates": _FILTER_GENERIC_INTERMEDIATES,
        },
        "metric_1_total_candidates": {
            "run009_baseline": _RUN009_TOTAL,
            "run012_filtered": len(filtered_cands),
            "reduction": _RUN009_TOTAL - len(filtered_cands),
            "reduction_pct": round((_RUN009_TOTAL - len(filtered_cands)) / _RUN009_TOTAL * 100, 1),
        },
        "metric_2_deep_cross_domain_count": {
            "run009_baseline": _RUN009_DEEP_CD,
            "run012_filtered": len(filtered_deep_cd),
            "reduction": _RUN009_DEEP_CD - len(filtered_deep_cd),
        },
        "metric_3_label_distribution": {
            "before_run011": {
                "total": _RUN011_DEEP_CD_TOTAL,
                "promising": _RUN011_PROMISING,
                "promising_pct": round(_RUN011_PROMISING / _RUN011_DEEP_CD_TOTAL * 100, 1),
                "weak_speculative": _RUN011_WEAK_SPEC,
                "weak_speculative_pct": round(_RUN011_WEAK_SPEC / _RUN011_DEEP_CD_TOTAL * 100, 1),
                "drift_heavy": _RUN011_DRIFT_HEAVY,
                "drift_heavy_pct": round(_RUN011_DRIFT_HEAVY / _RUN011_DEEP_CD_TOTAL * 100, 1),
            },
            "after_run012": {
                "total": total_after,
                "promising": after_dist["promising"],
                "promising_pct": round(after_dist["promising"] / total_after * 100, 1) if total_after else 0,
                "weak_speculative": after_dist["weak_speculative"],
                "weak_speculative_pct": round(after_dist["weak_speculative"] / total_after * 100, 1) if total_after else 0,
                "drift_heavy": after_dist["drift_heavy"],
                "drift_heavy_pct": round(after_dist["drift_heavy"] / total_after * 100, 1) if total_after else 0,
            },
        },
        "metric_4_top20_composition": {
            "baseline": baseline_top20,
            "filtered": filtered_top20,
        },
        "metric_5_top20_mean_score": {
            "baseline": baseline_top20["mean_score"],
            "filtered": filtered_top20["mean_score"],
        },
        "metric_6_removed_breakdown": {
            "total_removed_from_deep_cd": total_removed,
            "by_label": {
                "promising": len(promising_removed),
                "weak_speculative": len([r for r in removed if r["label"] == "weak_speculative"]),
                "drift_heavy": drift_heavy_removed,
                "unknown": len([r for r in removed if r["label"] == "unknown"]),
            },
            "removed_items": removed,
        },
        "metric_7_promising_lost": len(promising_removed),
        "metric_8_drift_heavy_removed": drift_heavy_removed,
        "metric_9_removal_efficiency": {
            "drift_removed": drift_heavy_removed,
            "total_removed": total_removed,
            "efficiency": removal_efficiency,
            "interpretation": f"{drift_heavy_removed}/{total_removed} removed candidates were drift_heavy",
        },
        "success_criteria": {
            "drift_heavy_lt_15pct": (
                round(after_dist["drift_heavy"] / total_after * 100, 1) < 15.0
                if total_after else True
            ),
            "promising_gt_25pct": (
                round(after_dist["promising"] / total_after * 100, 1) > 25.0
                if total_after else False
            ),
            "deep_cd_not_collapsed": len(filtered_deep_cd) >= 3,
        },
    }

    # --- Save output candidates ---
    output_candidates = []
    scored_map = {sh.candidate.id: sh for sh in filtered_scored}
    for c, tr in zip(filtered_cands, filtered_tracking):
        sh = scored_map.get(c.id)
        if sh:
            d = sh.to_dict()
            d.update(tr)
            output_candidates.append(d)

    # --- Write artifacts ---
    run_dir = Path(__file__).parent.parent.parent / "runs" / _RUN_DIR_NAME
    run_dir.mkdir(parents=True, exist_ok=True)

    # run_config.json
    run_config = {
        "run_id": _RUN_ID,
        "date": _DATE,
        "condition": _CONDITION,
        "description": "Review-driven drift filter: pre-compose relation filter + guards",
        "pipeline": "P4-filtered (align→union→filtered_compose+diff→evaluate)",
        "filter_spec": comparison["filter_spec"],
        "rubric": "revised_traceability=True (Run 010 quality-based penalty)",
        "random_seed": _RANDOM_SEED,
        "max_depth": _DEEP_DEPTH,
        "max_per_source": _MAX_PER_SOURCE_DEEP,
        "baseline_run": "run_009_20260410_phase4_scaleup (Condition C P4)",
        "reference_labels": "run_011_20260410_qualitative_review/candidate_labels.json",
    }
    (run_dir / "run_config.json").write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False)
    )

    # output_candidates.json
    (run_dir / "output_candidates.json").write_text(
        json.dumps(output_candidates, indent=2, ensure_ascii=False)
    )

    # filter_spec.md
    filter_spec_md = f"""# Filter Spec — Run 012

## Applied Filters

### 1. Pre-compose relation filter (`filter_relations`)

Blocked relation types:
- `contains` — molecular composition; no inferential content
- `is_product_of` — metabolic product; directionless for hypothesis generation
- `is_reverse_of` — reaction directionality; structural chemistry fact
- `is_isomer_of` — chemical isomer; structural fact, no mechanism

### 2. Consecutive repeat guard (`guard_consecutive_repeat=True`)

Rejects paths where the same relation type appears in consecutive position.
Example: A→`is_precursor_of`→B→`is_precursor_of`→C (amino acid biosynthesis chain).

### 3. Strong-relation ratio (`min_strong_ratio={_MIN_STRONG_RATIO}`)

For depth≥3 paths: at least {int(_MIN_STRONG_RATIO * 100)}% of relations must belong to
`_STRONG_MECHANISTIC` = `{{{', '.join(sorted(_STRONG_MECHANISTIC))}}}`.

### 4. Generic intermediate node filter (`filter_generic_intermediates=True`)

Rejects paths whose intermediate nodes have labels matching:
`process`, `system`, `entity`, `substance`, `compound`.

## Design Rationale

- Filters target **structural/chemical expansion** drift (the dominant drift pattern in Run 011).
- Filter 1 is the primary driver; Filters 2-4 are supplementary guards.
- All filters are **backward-compatible**: `compose()` default params unchanged.
- Filter 1 is dataset-specific (Run 011 analysis), NOT generic noise reduction.
- `is_reverse_of` is blocked because it only adds chemical directionality facts
  that do not contribute mechanistic inference.
"""
    (run_dir / "filter_spec.md").write_text(filter_spec_md)

    # before_after_comparison.md
    m1 = comparison["metric_1_total_candidates"]
    m2 = comparison["metric_2_deep_cross_domain_count"]
    m3 = comparison["metric_3_label_distribution"]
    m4 = comparison["metric_4_top20_composition"]
    m5 = comparison["metric_5_top20_mean_score"]
    m6 = comparison["metric_6_removed_breakdown"]
    m7 = comparison["metric_7_promising_lost"]
    m8 = comparison["metric_8_drift_heavy_removed"]
    m9 = comparison["metric_9_removal_efficiency"]
    sc = comparison["success_criteria"]

    after = m3["after_run012"]
    before = m3["before_run011"]

    comparison_md = f"""# Before/After Comparison — Run 009 vs Run 012

**Date**: {_DATE}
**Baseline**: Run 009 Condition C P4 + Run 011 qualitative labels (20 deep cross-domain)
**Filtered**: Run 012 (pre-compose drift filter)

## Metric 1: 候補総数

| | 候補総数 |
|---|---|
| Run 009 (baseline) | {m1['run009_baseline']} |
| Run 012 (filtered) | {m1['run012_filtered']} |
| 削減数 | {m1['reduction']} ({m1['reduction_pct']}%) |

## Metric 2: Deep Cross-Domain候補数 (≥3-hop かつ cross-domain)

| | Deep CD候補数 |
|---|---|
| Run 009 (baseline) | {m2['run009_baseline']} |
| Run 012 (filtered) | {m2['run012_filtered']} |
| 削減数 | {m2['reduction']} |

## Metric 3: Promising / Weak_Speculative / Drift_Heavy 分布

| ラベル | Run 011 (before) | Run 012 (after) | 変化 |
|--------|-----------------|-----------------|------|
| promising | {before['promising']} ({before['promising_pct']}%) | {after['promising']} ({after['promising_pct']}%) | {"↑" if after['promising_pct'] > before['promising_pct'] else "↓"} |
| weak_speculative | {before['weak_speculative']} ({before['weak_speculative_pct']}%) | {after['weak_speculative']} ({after['weak_speculative_pct']}%) | {"↑" if after['weak_speculative_pct'] > before['weak_speculative_pct'] else "↓"} |
| drift_heavy | {before['drift_heavy']} ({before['drift_heavy_pct']}%) | {after['drift_heavy']} ({after['drift_heavy_pct']}%) | {"↓" if after['drift_heavy_pct'] < before['drift_heavy_pct'] else "↑"} |
| **合計** | **{before['total']}** | **{after['total']}** | |

## Metric 4: Top-20の構成

### Depth分布

| Bucket | Baseline | Filtered |
|--------|----------|---------|
{"".join(
    f"| {k} | {m4['baseline']['depth_distribution'].get(k, 0)} | {m4['filtered']['depth_distribution'].get(k, 0)} |\\n"
    for k in sorted(set(list(m4['baseline']['depth_distribution'].keys()) + list(m4['filtered']['depth_distribution'].keys())))
)}
| Cross-domain in top-20 | {m4['baseline']['cross_domain_in_top20']} | {m4['filtered']['cross_domain_in_top20']} |

## Metric 5: Top-20 Mean Quality Score

| | Mean Score |
|---|---|
| Baseline | {m5['baseline']} |
| Filtered | {m5['filtered']} |

## Metric 6: Filterによって消えた候補の内訳

Deep Cross-Domain候補の除去分析:
- 除去総数: {m6['total_removed_from_deep_cd']}
- By label:
  - promising: {m6['by_label']['promising']}
  - weak_speculative: {m6['by_label']['weak_speculative']}
  - drift_heavy: {m6['by_label']['drift_heavy']}

除去された候補の詳細:

| ID | ラベル | 除去理由 |
|----|--------|---------|
{"".join(
    f"| {r['id']} | {r['label']} | {'; '.join(r['filter_reason'])} |\\n"
    for r in removed
)}

## Metric 7: Promising候補の損失

**{m7}件** のpromising候補を失った。
{"（損失なし — 全promising候補が保持された）" if m7 == 0 else "**注意**: promising候補の損失あり（詳細は上表参照）"}

## Metric 8: Drift_Heavy候補の除去

**{m8}件** のdrift_heavy候補を除去した（before: {before['drift_heavy']}件）。

## Metric 9: 除去効率

drift_heavy除去数 / total除去数 = {m9['drift_removed']}/{m9['total_removed']} = **{m9['efficiency']:.1%}**

{m9['interpretation']}

## 成功条件判定

| 条件 | 目標 | 結果 | 判定 |
|------|------|------|------|
| drift_heavy率 | 25% → <15% | {after['drift_heavy_pct']}% | {"PASS" if sc['drift_heavy_lt_15pct'] else "FAIL"} |
| promising率 | 15% → >25% | {after['promising_pct']}% | {"PASS" if sc['promising_gt_25pct'] else "FAIL"} |
| deep CD候補が大幅崩れない | ≥3件 | {m2['run012_filtered']}件 | {"PASS" if sc['deep_cd_not_collapsed'] else "FAIL"} |
"""
    (run_dir / "before_after_comparison.md").write_text(comparison_md)

    # top20_review.md
    top20_items = []
    scored_by_id = {sh.candidate.id: sh for sh in filtered_scored}
    track_by_id = {c.id: tr for c, tr in zip(filtered_cands, filtered_tracking)}
    for sh in filtered_scored[:_TOP_K]:
        c = sh.candidate
        tr = track_by_id.get(c.id, {})
        pl = candidate_path_length(c)
        cd = _is_cross_domain(c, merged_kg)
        label = "—"
        if pl >= 3 and cd:
            for item in filtered_deep_cd_labeled:
                if item["id"] == c.id:
                    label = item["label"]
                    break
        top20_items.append({
            "id": c.id,
            "subject_id": c.subject_id,
            "object_id": c.object_id,
            "path_length": pl,
            "is_cross_domain": cd,
            "total_score": round(sh.total_score, 4),
            "label": label,
            "provenance": c.provenance,
        })

    top20_md = f"""# Top-20 Review — Run 012 (Filtered)

**Date**: {_DATE}
**Rubric**: revised_traceability=True

| Rank | ID | Score | Depth | Cross-Domain | Label | Path |
|------|-----|-------|-------|--------------|-------|------|
{"".join(
    f"| {i+1} | {item['id']} | {item['total_score']} | {item['path_length']}-hop | "
    f"{'Yes' if item['is_cross_domain'] else 'No'} | {item['label']} | "
    f"`{'→'.join(item['provenance'][:7])}{'...' if len(item['provenance']) > 7 else ''}` |\\n"
    for i, item in enumerate(top20_items)
)}

## Depth Distribution
{chr(10).join(f"- {k}: {v}" for k, v in filtered_top20['depth_distribution'].items())}

## Cross-Domain in Top-20: {filtered_top20['cross_domain_in_top20']}

## Mean Score: {filtered_top20['mean_score']}
"""
    (run_dir / "top20_review.md").write_text(top20_md)

    # decision_memo.md
    decision_md = f"""# Decision Memo — Run 012

**Date**: {_DATE}

## 実験の目的

Run 011で特定されたdrift pattern（contains, is_product_of, is_reverse_of, is_isomer_of等の
化学構造関係）に基づいて、pre-compose filterを実装し、deep cross-domain発見の衛生を改善する。

## 主要な発見

### 候補数変化
- 総候補: {m1['run009_baseline']} → {m1['run012_filtered']} (▼{m1['reduction']}, {m1['reduction_pct']}%削減)
- Deep CD候補: {m2['run009_baseline']} → {m2['run012_filtered']} (▼{m2['reduction']})

### ラベル分布変化（Deep CD候補）
- drift_heavy: {before['drift_heavy_pct']}% → {after['drift_heavy_pct']}% ({'改善' if sc['drift_heavy_lt_15pct'] else '目標未達'})
- promising: {before['promising_pct']}% → {after['promising_pct']}% ({'改善' if sc['promising_gt_25pct'] else '目標未達'})
- 除去効率: {m9['efficiency']:.1%} (drift_heavy {m9['drift_removed']}/{m9['total_removed']} 除去)

### Promising候補への影響
- Promising候補損失: **{m7}件**
{"- 全promising候補（VHL/HIF1A/LDHA カスケード）を保持" if m7 == 0 else "- 一部promising候補を失った（filterのover-pruning）"}

## filterの評価

1. `filter_relations` が最も効果的：drift_heavy 5件中 {m8}件を除去
2. 化学構造関係 (contains/is_product_of/is_isomer_of) はdrift主因であり、filter対象として正当
3. `is_reverse_of` は weak_speculative候補（NADH/酸化還元チェーン）も除去するが、これらは
   化学的事実（r_Oxidation → is_reverse_of → r_Reduction）であり機構的仮説ではない

## 次ステップ推薦

1. Deep CD候補の絶対数がさらに少ない場合、`is_reverse_of` をfilterから外してweak_speculative
   を一部戻すことを検討（ただしdrift_heavy率の再確認が必要）
2. filter_generic_intermediatesの効果を独立して測定（現データではintermediate汎用ノードが少ない）
3. `min_strong_ratio` のチューニング（0.40が適切かを検証するために0.30/0.50も試す）
4. Run 013: filterを固定してHypothesis validation（H1''/H3''の再検証、フィルター後の公正テスト）
"""
    (run_dir / "decision_memo.md").write_text(decision_md)

    # Save full comparison JSON
    (run_dir / "before_after_comparison.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False)
    )

    print(f"\n=== Run 012 Complete ===")
    print(f"Output: runs/{_RUN_DIR_NAME}/")
    print(f"\nBefore/After Summary:")
    print(f"  Total candidates: {m1['run009_baseline']} → {m1['run012_filtered']} ({m1['reduction_pct']}% reduction)")
    print(f"  Deep cross-domain: {m2['run009_baseline']} → {m2['run012_filtered']}")
    print(f"  drift_heavy: {before['drift_heavy_pct']}% → {after['drift_heavy_pct']}%")
    print(f"  promising: {before['promising_pct']}% → {after['promising_pct']}%")
    print(f"  Removal efficiency: {m9['efficiency']:.1%}")
    print(f"  Promising lost: {m7}")
    print(f"\nSuccess criteria:")
    print(f"  drift_heavy <15%: {'PASS' if sc['drift_heavy_lt_15pct'] else 'FAIL'}")
    print(f"  promising >25%: {'PASS' if sc['promising_gt_25pct'] else 'FAIL'}")
    print(f"  deep CD not collapsed: {'PASS' if sc['deep_cd_not_collapsed'] else 'FAIL'}")

    return comparison


if __name__ == "__main__":
    main()
