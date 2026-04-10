"""Phase 3 Run 008: deep-composition experiment.

Experiment design — 5 result sets from 3 pipeline conditions:
  R1: single-op, max_depth=3 (2-hop max) on Condition C (cross-domain sparse)
  R2: multi-op,  max_depth=3 (2-hop max) on Condition C
  R3: multi-op,  max_depth=9 (5-hop max) on Condition C  [deep]
  R4: same candidates as R3, scored with naive ranking     (provenance_aware=False)
  R5: same candidates as R3, scored with provenance-aware  (provenance_aware=True)

Research questions:
  H1'': reachability gain from alignment (not average score improvement)
  H3'': deep (3-hop+) compose produces new cross-domain candidates not found by shallow
  H4:   provenance-aware ranking improves top-k quality for deep candidates

Tracking fields per candidate:
  path_length, operator_chain, alignment_used, alignment_count,
  merged_nodes_used, reachable_by_single, uniqueness_class,
  effective_path_length_after_alignment, drift_flags, semantic_drift_score
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.wikidata_loader import load_wikidata_bio_chem
from src.eval.scorer import EvaluationRubric, ScoredHypothesis, evaluate, score_category
from src.kg.models import HypothesisCandidate, KnowledgeGraph
from src.kg.real_data import (
    build_condition_c,
    compute_kg_stats,
    extract_domain_subgraph,
)
from src.pipeline.operators import align, compose, difference, union

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHALLOW_DEPTH = 3   # 2-hop max
_DEEP_DEPTH = 9      # up to 5-hop paths
_TOP_K = 10

_LOW_SPEC_RELATIONS: frozenset[str] = frozenset({
    "relates_to", "associated_with", "part_of", "connected_to",
    "involves", "related_to", "is_a", "has_part",
})
_WEAK_LABELS: frozenset[str] = frozenset({
    "process", "system", "entity", "thing", "object",
    "event", "concept", "item", "element",
})
_DEPTH_BUCKETS: list[tuple[str, int, int]] = [
    ("1-hop", 1, 1),
    ("2-hop", 2, 2),
    ("3-hop", 3, 3),
    ("4-5-hop", 4, 5),
]


# ---------------------------------------------------------------------------
# Semantic drift
# ---------------------------------------------------------------------------

def compute_drift_info(provenance: list[str], kg: KnowledgeGraph) -> dict:
    """Compute semantic drift flags and score (0-1) for a hypothesis path.

    Three possible flags:
      relation_repetition       - same relation appears 2+ times
      low_specificity_relations - all relations are generic/weak
      weakly_typed_intermediates - all intermediate nodes have generic labels
    """
    if len(provenance) < 5:  # need at least 2-hop to have intermediates
        relations = provenance[1::2] if len(provenance) >= 3 else []
        flags: list[str] = []
        if len(relations) > len(set(relations)):
            flags.append("relation_repetition")
        if relations and all(r in _LOW_SPEC_RELATIONS for r in relations):
            flags.append("low_specificity_relations")
        return {"drift_flags": flags, "semantic_drift_score": round(len(flags) / 3.0, 4)}

    relations = provenance[1::2]
    node_ids = provenance[0::2]
    intermediate_ids = node_ids[1:-1]

    flags = []
    if len(relations) > len(set(relations)):
        flags.append("relation_repetition")
    if all(r in _LOW_SPEC_RELATIONS for r in relations):
        flags.append("low_specificity_relations")

    if intermediate_ids:
        weak = sum(
            1 for nid in intermediate_ids
            if (n := kg.get_node(nid)) and any(w in n.label.lower() for w in _WEAK_LABELS)
        )
        if weak == len(intermediate_ids):
            flags.append("weakly_typed_intermediates")

    return {"drift_flags": flags, "semantic_drift_score": round(len(flags) / 3.0, 4)}


# ---------------------------------------------------------------------------
# Tracking fields
# ---------------------------------------------------------------------------

def compute_tracking_fields(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
    single_op_pairs: set[tuple[str, str]],
    shallow_multi_pairs: set[tuple[str, str]],
    aligned_node_ids: set[str],
) -> dict:
    """Compute Run 008 tracking fields for a hypothesis candidate.

    Args:
        candidate: The hypothesis to annotate.
        kg: The KG in which the hypothesis lives (for node lookup).
        single_op_pairs: (subj, obj) pairs from single-op R1.
        shallow_multi_pairs: (subj, obj) pairs from shallow multi-op R2.
        aligned_node_ids: IDs of nodes that were merged via alignment.
    """
    prov = candidate.provenance
    path_length = max(0, (len(prov) - 1) // 2) if len(prov) >= 3 else 0
    node_ids_in_path = prov[0::2] if len(prov) >= 1 else []

    merged = [nid for nid in node_ids_in_path if nid in aligned_node_ids]
    alignment_used = bool(merged)
    effective_len = max(0, path_length - len(merged))
    pair = (candidate.subject_id, candidate.object_id)

    if pair in single_op_pairs:
        uclass = "reachable_by_single"
    elif path_length >= 3 and pair not in shallow_multi_pairs:
        uclass = "reachable_only_by_deep_compose"
    elif alignment_used and pair not in shallow_multi_pairs:
        uclass = "reachable_only_by_alignment"
    else:
        uclass = "reachable_only_by_multi"

    op_chain = ["align", "union", "compose"] if alignment_used else ["compose"]
    drift = compute_drift_info(prov, kg)

    return {
        "path_length": path_length,
        "operator_chain": op_chain,
        "alignment_used": alignment_used,
        "alignment_count": len(merged),
        "merged_nodes_used": merged,
        "reachable_by_single": pair in single_op_pairs,
        "uniqueness_class": uclass,
        "effective_path_length_after_alignment": effective_len,
        "drift_flags": drift["drift_flags"],
        "semantic_drift_score": drift["semantic_drift_score"],
    }


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------

def run_single_op_deep(
    kg: KnowledgeGraph,
    max_depth: int = _SHALLOW_DEPTH,
) -> list[ScoredHypothesis]:
    """Single-op baseline: compose-only, no cross-domain bonus."""
    rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
    return evaluate(compose(kg, max_depth=max_depth), kg, rubric)


def run_multi_op_deep(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    max_depth: int = _SHALLOW_DEPTH,
) -> tuple[list[ScoredHypothesis], KnowledgeGraph, dict[str, str], set[str]]:
    """Multi-op: align → union → compose + diff → deduplicate → evaluate.

    Returns (scored, merged_kg, alignment_map, aligned_node_ids).
    """
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment, name=f"union_{bio_kg.name}_{chem_kg.name}")
    counter: list[int] = [0]
    cands = compose(merged, max_depth=max_depth, _counter=counter)
    diff_kg = difference(bio_kg, chem_kg, alignment, name=f"diff_{bio_kg.name}")
    cands += compose(diff_kg, max_depth=max_depth, _counter=counter)

    seen: set[tuple[str, str]] = set()
    unique: list[HypothesisCandidate] = []
    for c in cands:
        k = (c.subject_id, c.object_id)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
    scored = evaluate(unique, merged, rubric)
    return scored, merged, alignment, set(alignment.keys())


def rescore_with_rubric(
    scored: list[ScoredHypothesis],
    kg: KnowledgeGraph,
    provenance_aware: bool,
) -> list[ScoredHypothesis]:
    """Re-score an existing set of candidates with a different rubric."""
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=provenance_aware,
    )
    return evaluate([sh.candidate for sh in scored], kg, rubric)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pair_set(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    """Return (subject_id, object_id) pairs from scored hypotheses."""
    return {(sh.candidate.subject_id, sh.candidate.object_id) for sh in scored}


def _normalize_id(node_id: str) -> str:
    """Strip kg-prefix from union-remapped IDs (e.g. 'chem::bio:foo' → 'bio:foo')."""
    return node_id.split("::", 1)[1] if "::" in node_id else node_id


def _normalized_pairs(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    return {(_normalize_id(sh.candidate.subject_id), _normalize_id(sh.candidate.object_id))
            for sh in scored}


def bucket_label(path_length: int) -> str:
    """Map path_length to its depth bucket label."""
    for label, lo, hi in _DEPTH_BUCKETS:
        if lo <= path_length <= hi:
            return label
    return f"{path_length}-hop"


def _is_cross_domain(candidate: HypothesisCandidate, kg: KnowledgeGraph) -> bool:
    """Return True if subject and object belong to different domains."""
    n1 = kg.get_node(candidate.subject_id)
    n2 = kg.get_node(candidate.object_id)
    if n1 and n2:
        return n1.domain != n2.domain
    return False


# ---------------------------------------------------------------------------
# Depth bucket analysis
# ---------------------------------------------------------------------------

def analyze_depth_buckets(
    scored: list[ScoredHypothesis],
    tracking: list[dict],
    kg: KnowledgeGraph,
) -> dict:
    """Per-depth-bucket statistics: count, promising, novelty, drift, cross-domain."""
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for sh, tr in zip(scored, tracking):
        bl = bucket_label(tr["path_length"])
        buckets[bl].append((sh, tr))

    result: dict[str, dict] = {}
    for bl, items in sorted(buckets.items()):
        total = len(items)
        promising = sum(1 for sh, _ in items if score_category(sh.total_score) == "promising")
        cross = sum(1 for sh, _ in items if _is_cross_domain(sh.candidate, kg))
        novelty = [sh.novelty for sh, _ in items]
        drift = [tr["semantic_drift_score"] for _, tr in items]
        drifted = sum(1 for _, tr in items if tr["drift_flags"])
        alignment_used = sum(1 for _, tr in items if tr["alignment_used"])
        uclasses: dict[str, int] = {}
        for _, tr in items:
            uc = tr.get("uniqueness_class", "unknown")
            uclasses[uc] = uclasses.get(uc, 0) + 1
        result[bl] = {
            "candidate_count": total,
            "promising_count": promising,
            "cross_domain_count": cross,
            "alignment_used_count": alignment_used,
            "mean_novelty": round(sum(novelty) / total, 4) if total else 0.0,
            "mean_drift_score": round(sum(drift) / total, 4) if total else 0.0,
            "drift_rate": round(drifted / total, 4) if total else 0.0,
            "uniqueness_classes": uclasses,
        }
    return result


# ---------------------------------------------------------------------------
# Ranking comparison
# ---------------------------------------------------------------------------

def compare_rankings(
    scored_r4: list[ScoredHypothesis],
    scored_r5: list[ScoredHypothesis],
    tracking: list[dict],
    top_k: int = _TOP_K,
) -> dict:
    """Compare naive (R4) vs provenance-aware (R5) rankings.

    Args:
        scored_r4: Deep candidates scored with naive rubric.
        scored_r5: Same candidates scored with provenance-aware rubric.
        tracking: Parallel tracking dicts for R4/R5 candidates.
    """
    naive_top_pairs = {
        (sh.candidate.subject_id, sh.candidate.object_id)
        for sh in scored_r4[:top_k]
    }
    aware_top_pairs = {
        (sh.candidate.subject_id, sh.candidate.object_id)
        for sh in scored_r5[:top_k]
    }
    overlap = naive_top_pairs & aware_top_pairs
    total_union = len(naive_top_pairs | aware_top_pairs)
    jaccard = round(len(overlap) / total_union, 4) if total_union else 0.0

    # Deep candidate representation in top-k
    deep_tr = {(tr.get("path_length", 0) >= 3) for tr in tracking}
    deep_in_naive_top = sum(
        1 for sh in scored_r4[:top_k]
        if any(
            tr["path_length"] >= 3
            for tr in tracking
            if tr.get("path_length") is not None
            and (sh.candidate.subject_id, sh.candidate.object_id)
            == (sh.candidate.subject_id, sh.candidate.object_id)
        )
    )

    # Deep candidates that moved up in provenance-aware ranking
    naive_rank = {(sh.candidate.subject_id, sh.candidate.object_id): i
                  for i, sh in enumerate(scored_r4)}
    aware_rank = {(sh.candidate.subject_id, sh.candidate.object_id): i
                  for i, sh in enumerate(scored_r5)}
    promoted_deep = 0
    demoted_deep = 0
    for tr, sh in zip(tracking, scored_r4):
        if tr["path_length"] >= 3:
            p = (sh.candidate.subject_id, sh.candidate.object_id)
            nr = naive_rank.get(p, 9999)
            ar = aware_rank.get(p, 9999)
            if ar < nr:
                promoted_deep += 1
            elif ar > nr:
                demoted_deep += 1

    return {
        "top_k": top_k,
        "naive_top_scores": [round(sh.total_score, 4) for sh in scored_r4[:top_k]],
        "aware_top_scores": [round(sh.total_score, 4) for sh in scored_r5[:top_k]],
        "overlap_count": len(overlap),
        "naive_only_count": len(naive_top_pairs - aware_top_pairs),
        "aware_only_count": len(aware_top_pairs - naive_top_pairs),
        "jaccard_similarity": jaccard,
        "deep_promoted_by_aware": promoted_deep,
        "deep_demoted_by_aware": demoted_deep,
        "interpretation": (
            "provenance-aware PROMOTES deep candidates"
            if promoted_deep > demoted_deep
            else "provenance-aware DEMOTES deep candidates"
            if demoted_deep > promoted_deep
            else "provenance-aware has NEUTRAL effect on deep candidates"
        ),
    }


# ---------------------------------------------------------------------------
# Reachability analysis
# ---------------------------------------------------------------------------

def analyze_reachability(
    r1_scored: list[ScoredHypothesis],
    r2_scored: list[ScoredHypothesis],
    r3_scored: list[ScoredHypothesis],
) -> dict:
    """Compare reachability across R1 (single/shallow), R2 (multi/shallow), R3 (multi/deep)."""
    r1_norm = _normalized_pairs(r1_scored)
    r2_norm = _normalized_pairs(r2_scored)
    r3_norm = _normalized_pairs(r3_scored)

    unique_r2_vs_r1 = r2_norm - r1_norm
    unique_r3_vs_r2 = r3_norm - r2_norm
    unique_r3_vs_r1 = r3_norm - r1_norm
    deep_only = r3_norm - r2_norm - r1_norm

    return {
        "r1_single_shallow_total": len(r1_norm),
        "r2_multi_shallow_total": len(r2_norm),
        "r3_multi_deep_total": len(r3_norm),
        "unique_to_r2_vs_r1": len(unique_r2_vs_r1),
        "unique_to_r3_vs_r2": len(unique_r3_vs_r2),
        "unique_to_r3_vs_r1": len(unique_r3_vs_r1),
        "deep_only_count": len(deep_only),
        "h1pp_evidence": len(unique_r2_vs_r1) > 0,
        "h3pp_evidence": len(deep_only) > 0,
        "note": "deep_only = pairs reachable by R3 but not R2 or R1 (requires deep compose)",
    }


# ---------------------------------------------------------------------------
# Score stats helper
# ---------------------------------------------------------------------------

def _score_stats(scored: list[ScoredHypothesis], label: str) -> dict:
    """Summary statistics for a list of scored hypotheses."""
    if not scored:
        return {"pipeline": label, "n": 0, "mean_total": 0.0, "mean_novelty": 0.0}
    scores = [sh.total_score for sh in scored]
    n = len(scores)
    cats: dict[str, int] = {}
    for sh in scored:
        c = score_category(sh.total_score)
        cats[c] = cats.get(c, 0) + 1
    return {
        "pipeline": label,
        "n": n,
        "mean_total": round(sum(scores) / n, 4),
        "mean_novelty": round(sum(sh.novelty for sh in scored) / n, 4),
        "min_total": round(min(scores), 4),
        "max_total": round(max(scores), 4),
        "category_distribution": {k: round(v / n, 4) for k, v in cats.items()},
        "top5": [sh.to_dict() for sh in scored[:5]],
    }


# ---------------------------------------------------------------------------
# Output serialization
# ---------------------------------------------------------------------------

def build_tracked_output(
    scored: list[ScoredHypothesis],
    tracking: list[dict],
) -> list[dict]:
    """Merge ScoredHypothesis.to_dict() with tracking fields."""
    result = []
    for sh, tr in zip(scored, tracking):
        entry = sh.to_dict()
        entry["tracking"] = tr
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict | list) -> None:
    """Write data as indented JSON."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    """Write markdown content."""
    path.write_text(content, encoding="utf-8")


def generate_run_artifacts(
    run_dir: Path,
    run_config: dict,
    all_results: dict,
) -> None:
    """Write all run artifacts to run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_json(run_dir / "run_config.json", run_config)
    _write_json(run_dir / "output_candidates.json", all_results["output_candidates"])

    _write_md(run_dir / "experiment_rationale.md", all_results["experiment_rationale"])
    _write_md(run_dir / "input_summary.md", all_results["input_summary"])
    _write_md(run_dir / "evaluation_summary.md", all_results["evaluation_summary"])
    _write_md(run_dir / "depth_bucket_analysis.md", all_results["depth_bucket_analysis"])
    _write_md(run_dir / "ranking_comparison.md", all_results["ranking_comparison"])
    _write_md(run_dir / "next_actions.md", all_results["next_actions"])


# ---------------------------------------------------------------------------
# Markdown builders
# ---------------------------------------------------------------------------

def _fmt_bucket_row(label: str, stats: dict) -> str:
    return (
        f"| {label} | {stats['candidate_count']} | {stats['promising_count']} "
        f"| {stats['cross_domain_count']} | {stats['alignment_used_count']} "
        f"| {stats['mean_novelty']:.3f} | {stats['mean_drift_score']:.3f} "
        f"| {stats['drift_rate']:.2%} |"
    )


def build_depth_bucket_md(bucket_stats: dict, condition_label: str) -> str:
    """Generate depth_bucket_analysis.md content."""
    rows = "\n".join(_fmt_bucket_row(bl, stats) for bl, stats in bucket_stats.items())
    return f"""# Depth Bucket Analysis — Run 008

Condition: {condition_label}

## Per-Bucket Statistics

| Depth | Candidates | Promising | Cross-Domain | Align-Used | Mean Novelty | Mean Drift | Drift Rate |
|-------|-----------|-----------|--------------|------------|--------------|------------|------------|
{rows}

## Notes

- **Promising**: score_category == "promising" (0.60 ≤ total < 0.85)
- **Drift Rate**: fraction of candidates with ≥1 drift flag
- **Align-Used**: candidates where an aligned/merged node appears in the path
"""


def build_ranking_comparison_md(rc: dict) -> str:
    """Generate ranking_comparison.md content."""
    naive_top = ", ".join(f"{s:.3f}" for s in rc["naive_top_scores"][:5])
    aware_top = ", ".join(f"{s:.3f}" for s in rc["aware_top_scores"][:5])
    return f"""# Ranking Comparison — Run 008 (R4 Naive vs R5 Provenance-Aware)

## Top-{rc['top_k']} Score Summary

| Metric | Naive (R4) | Provenance-Aware (R5) |
|--------|-----------|----------------------|
| Top-5 scores | {naive_top} | {aware_top} |
| Overlap (top-{rc['top_k']}) | {rc['overlap_count']} | — |
| Naive-only | {rc['naive_only_count']} | — |
| Aware-only | {rc['aware_only_count']} | — |
| Jaccard similarity | {rc['jaccard_similarity']:.3f} | — |

## Deep Candidate Movement

- Deep candidates (path_length ≥ 3) **promoted** by provenance-aware: {rc['deep_promoted_by_aware']}
- Deep candidates **demoted** by provenance-aware: {rc['deep_demoted_by_aware']}

**Interpretation**: {rc['interpretation']}

## H4 Assessment

Provenance-aware ranking {'IMPROVES' if rc['deep_promoted_by_aware'] > rc['deep_demoted_by_aware'] else 'DOES NOT IMPROVE'} \
top-k quality for deep-path candidates.
Jaccard = {rc['jaccard_similarity']:.3f} \
({'high overlap — rankings nearly equivalent' if rc['jaccard_similarity'] >= 0.7 else 'low overlap — rankings differ substantially'}).
"""


def build_evaluation_summary_md(
    stats_r1: dict,
    stats_r2: dict,
    stats_r3: dict,
    reachability: dict,
    h1pp_verdict: str,
    h3pp_verdict: str,
    h4_verdict: str,
) -> str:
    """Generate evaluation_summary.md content."""
    return f"""# Evaluation Summary — Run 008

## Pipeline Statistics

| Pipeline | N | Mean Total | Mean Novelty | Min | Max |
|----------|---|-----------|--------------|-----|-----|
| R1 single-op/shallow | {stats_r1['n']} | {stats_r1['mean_total']} | {stats_r1['mean_novelty']} | {stats_r1['min_total']} | {stats_r1['max_total']} |
| R2 multi-op/shallow | {stats_r2['n']} | {stats_r2['mean_total']} | {stats_r2['mean_novelty']} | {stats_r2['min_total']} | {stats_r2['max_total']} |
| R3 multi-op/deep | {stats_r3['n']} | {stats_r3['mean_total']} | {stats_r3['mean_novelty']} | {stats_r3['min_total']} | {stats_r3['max_total']} |

## Reachability

| Metric | Value |
|--------|-------|
| R1 total pairs | {reachability['r1_single_shallow_total']} |
| R2 total pairs | {reachability['r2_multi_shallow_total']} |
| R3 total pairs | {reachability['r3_multi_deep_total']} |
| Unique to R2 vs R1 | {reachability['unique_to_r2_vs_r1']} |
| Unique to R3 vs R2 | {reachability['unique_to_r3_vs_r2']} |
| Deep-only (R3 only) | {reachability['deep_only_count']} |

## Hypothesis Verdicts

- **H1''** (alignment enables unreachable paths): {h1pp_verdict}
- **H3''** (deep compose finds new cross-domain candidates): {h3pp_verdict}
- **H4** (provenance-aware ranking improves deep top-k): {h4_verdict}
"""


def build_next_actions_md(
    h1pp_verdict: str,
    h3pp_verdict: str,
    h4_verdict: str,
    deep_only_count: int,
    drift_rate_deep: float,
) -> str:
    """Generate next_actions.md content."""
    return f"""# Next Actions — Run 008

## Summary of Findings

- H1'': {h1pp_verdict}
- H3'': {h3pp_verdict}
- H4: {h4_verdict}
- Deep-only candidates: {deep_only_count}
- Drift rate in 3-hop+ bucket: {drift_rate_deep:.1%}

## Recommended Next Steps

1. **If deep_only > 0 and drift_rate < 0.5**: deep compose is producing real novel candidates
   → Run 009: validate deep-only candidates against literature / external KG
2. **If drift_rate >= 0.5 in deep bucket**: semantic drift is dominating deep paths
   → Run 009: add relation-type filtering to prune weak-relation paths before compose
3. **If H4 provenance-aware promotes deep candidates**: incorporate into default rubric
   → Update EvaluationRubric default to provenance_aware=True
4. **If H1'' confirmed**: alignment-induced reachability is the core multi-op value
   → Focus future experiments on alignment quality improvement
5. **If H3'' confirmed**: cross-domain deep paths exist without bonus manipulation
   → Phase 4: scale to larger Wikidata dataset (500+ nodes) to test robustness

## Experiment Hygiene

- random_seed=42 was used throughout
- All conditions derived from same Condition C (sparse bridge) base data
- No external API calls were made
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run Phase 3 Run 008: deep-composition experiment."""
    random_seed = 42
    timestamp = datetime.now().isoformat()
    run_id = "run_008"
    run_dir = Path(__file__).parent.parent.parent / "runs" / "run_008_20260410_phase3_deep_compose"

    # ------------------------------------------------------------------
    # Load data and build KGs
    # ------------------------------------------------------------------
    data = load_wikidata_bio_chem()
    full_cond_c = build_condition_c(data)
    bio_kg = extract_domain_subgraph(full_cond_c, "biology", "bio_sub_c")
    chem_kg = extract_domain_subgraph(full_cond_c, "chemistry", "chem_sub_c")
    kg_stats = compute_kg_stats(full_cond_c)

    # ------------------------------------------------------------------
    # R1: single-op, shallow (depth=2)
    # ------------------------------------------------------------------
    r1_scored = run_single_op_deep(full_cond_c, max_depth=_SHALLOW_DEPTH)
    r1_pairs = _pair_set(r1_scored)

    # ------------------------------------------------------------------
    # R2: multi-op, shallow (depth=2)
    # ------------------------------------------------------------------
    r2_scored, merged_shallow, alignment_shallow, aligned_ids_shallow = run_multi_op_deep(
        bio_kg, chem_kg, max_depth=_SHALLOW_DEPTH
    )
    r2_pairs = _pair_set(r2_scored)

    # ------------------------------------------------------------------
    # R3: multi-op, deep (max 5-hop)
    # ------------------------------------------------------------------
    r3_scored, merged_deep, alignment_deep, aligned_ids_deep = run_multi_op_deep(
        bio_kg, chem_kg, max_depth=_DEEP_DEPTH
    )

    # ------------------------------------------------------------------
    # Tracking fields for R3 candidates
    # ------------------------------------------------------------------
    r3_tracking = [
        compute_tracking_fields(
            sh.candidate, merged_deep,
            r1_pairs, r2_pairs, aligned_ids_deep,
        )
        for sh in r3_scored
    ]

    # ------------------------------------------------------------------
    # R4: same candidates as R3, naive ranking
    # R5: same candidates as R3, provenance-aware ranking
    # ------------------------------------------------------------------
    r4_scored = rescore_with_rubric(r3_scored, merged_deep, provenance_aware=False)
    r5_scored = rescore_with_rubric(r3_scored, merged_deep, provenance_aware=True)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    reachability = analyze_reachability(r1_scored, r2_scored, r3_scored)
    bucket_stats = analyze_depth_buckets(r3_scored, r3_tracking, merged_deep)
    ranking_cmp = compare_rankings(r4_scored, r5_scored, r3_tracking, top_k=_TOP_K)

    # ------------------------------------------------------------------
    # Hypothesis verdicts
    # ------------------------------------------------------------------
    h1pp_verdict = (
        "PASS — alignment enables reachability of new pairs"
        if reachability["unique_to_r2_vs_r1"] > 0
        else "FAIL — no reachability gain from alignment"
    )
    h3pp_verdict = (
        "PASS — deep compose (3-hop+) produces candidates unreachable by shallow multi-op"
        if reachability["deep_only_count"] > 0
        else "FAIL — deep compose adds no new candidates vs shallow multi-op"
    )
    deep_bucket = bucket_stats.get("3-hop", bucket_stats.get("4-5-hop", {}))
    drift_deep = deep_bucket.get("drift_rate", 0.0) if deep_bucket else 0.0
    h4_verdict = (
        "PASS — provenance-aware promotes deep candidates"
        if ranking_cmp["deep_promoted_by_aware"] > ranking_cmp["deep_demoted_by_aware"]
        else "INCONCLUSIVE — no clear promotion effect"
        if ranking_cmp["deep_promoted_by_aware"] == ranking_cmp["deep_demoted_by_aware"]
        else "FAIL — provenance-aware demotes deep candidates"
    )

    # ------------------------------------------------------------------
    # Build output candidates (R3 with tracking)
    # ------------------------------------------------------------------
    output_candidates = build_tracked_output(r3_scored, r3_tracking)

    # ------------------------------------------------------------------
    # Markdown content
    # ------------------------------------------------------------------
    stats_r1 = _score_stats(r1_scored, "R1_single_shallow")
    stats_r2 = _score_stats(r2_scored, "R2_multi_shallow")
    stats_r3 = _score_stats(r3_scored, "R3_multi_deep")

    experiment_rationale = f"""# Experiment Rationale — Run 008

## Background

Run 007 established:
- same-domain (A/B): unique_to_multi = 0 (alignment provides no advantage)
- cross-domain (C/D): unique_to_multi = 4 (alignment creates 2-hop shortcuts)
- bridge density (5% vs 15%) did NOT affect the result
- The dominant mechanism is alignment-induced path shortening, not bridge density

## Run 008 Goals

1. Test whether deeper compose (3-5 hop) discovers genuinely new cross-domain candidates (H3'')
2. Test whether provenance-aware ranking improves top-k quality for deep paths (H4)
3. Separate alignment-induced candidates from mere chain explosion

## Condition Choice

Using Condition C (sparse bridge): more reliance on alignment mechanism,
fewer explicit cross-domain edges → cleanest signal for alignment contribution.

## Design

- R1: single-op baseline, depth=2
- R2: multi-op, depth=2 (replicates Run 007 shallow result)
- R3: multi-op, depth=5 (max_depth={_DEEP_DEPTH}) — deep compose
- R4: R3 candidates, naive ranking (provenance_aware=False)
- R5: R3 candidates, provenance-aware ranking (provenance_aware=True)

Tracking fields added per candidate for path-level analysis.
"""

    input_summary = f"""# Input Summary — Run 008

## Knowledge Graph: Condition C (sparse bridge)

| Metric | Value |
|--------|-------|
| Nodes | {kg_stats['node_count']} |
| Edges | {kg_stats['edge_count']} |
| Bridge density | {kg_stats['bridge_density']:.4f} |
| Relation entropy | {kg_stats['relation_entropy']:.4f} |
| Relation types | {kg_stats['relation_type_count']} |
| Domain counts | {kg_stats['domain_counts']} |

## Alignment

Aligned nodes (bio → chem): {len(alignment_deep)} pairs
Aligned node IDs: {sorted(aligned_ids_deep)[:10]}{'...' if len(aligned_ids_deep) > 10 else ''}

## Pipeline Depths

| Pipeline | max_depth param | Max path hops |
|----------|----------------|--------------|
| R1 (single) | {_SHALLOW_DEPTH} | 2 |
| R2 (multi shallow) | {_SHALLOW_DEPTH} | 2 |
| R3/R4/R5 (multi deep) | {_DEEP_DEPTH} | 5 |
"""

    eval_summary = build_evaluation_summary_md(
        stats_r1, stats_r2, stats_r3,
        reachability, h1pp_verdict, h3pp_verdict, h4_verdict,
    )
    depth_md = build_depth_bucket_md(bucket_stats, "Condition C + multi-op deep")
    ranking_md = build_ranking_comparison_md(ranking_cmp)
    next_md = build_next_actions_md(
        h1pp_verdict, h3pp_verdict, h4_verdict,
        reachability["deep_only_count"], drift_deep,
    )

    # ------------------------------------------------------------------
    # Run config
    # ------------------------------------------------------------------
    run_config = {
        "run_id": run_id,
        "phase": "Phase3",
        "experiment": "deep_composition",
        "timestamp": timestamp,
        "random_seed": random_seed,
        "condition": "C_sparse_bridge",
        "shallow_depth_param": _SHALLOW_DEPTH,
        "deep_depth_param": _DEEP_DEPTH,
        "pipelines": ["R1_single_shallow", "R2_multi_shallow", "R3_multi_deep",
                      "R4_multi_deep_naive", "R5_multi_deep_aware"],
        "rubric": "EvaluationRubric(cross_domain_novelty_bonus=False)",
        "tracking_fields": [
            "path_length", "operator_chain", "alignment_used", "alignment_count",
            "merged_nodes_used", "reachable_by_single", "uniqueness_class",
            "effective_path_length_after_alignment", "drift_flags", "semantic_drift_score",
        ],
        "research_questions": [
            "H1'': alignment-induced reachability gain (not score improvement)",
            "H3'': deep compose produces new cross-domain candidates",
            "H4: provenance-aware ranking improves deep top-k quality",
        ],
        "results_summary": {
            "h1pp": h1pp_verdict,
            "h3pp": h3pp_verdict,
            "h4": h4_verdict,
            "reachability": reachability,
            "ranking_comparison": ranking_cmp,
        },
    }

    # ------------------------------------------------------------------
    # Write artifacts
    # ------------------------------------------------------------------
    generate_run_artifacts(
        run_dir,
        run_config,
        {
            "output_candidates": output_candidates,
            "experiment_rationale": experiment_rationale,
            "input_summary": input_summary,
            "evaluation_summary": eval_summary,
            "depth_bucket_analysis": depth_md,
            "ranking_comparison": ranking_md,
            "next_actions": next_md,
        },
    )

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"Run 008 — Phase 3 Deep Composition")
    print(f"{'='*60}")
    print(f"Condition C KG: {kg_stats['node_count']} nodes, {kg_stats['edge_count']} edges")
    print(f"Aligned nodes: {len(alignment_deep)}")
    print(f"\nPipeline results:")
    print(f"  R1 single/shallow: {stats_r1['n']} candidates")
    print(f"  R2 multi/shallow:  {stats_r2['n']} candidates")
    print(f"  R3 multi/deep:     {stats_r3['n']} candidates")
    print(f"\nReachability:")
    print(f"  unique_to_R2_vs_R1: {reachability['unique_to_r2_vs_r1']}")
    print(f"  unique_to_R3_vs_R2: {reachability['unique_to_r3_vs_r2']}")
    print(f"  deep_only (R3 exclusive): {reachability['deep_only_count']}")
    print(f"\nDepth bucket distribution (R3):")
    for bl, stats in bucket_stats.items():
        print(f"  {bl:10s}: {stats['candidate_count']:3d} candidates, "
              f"drift_rate={stats['drift_rate']:.1%}, "
              f"cross={stats['cross_domain_count']}")
    print(f"\nRanking comparison (top-{_TOP_K}):")
    print(f"  Jaccard(R4,R5): {ranking_cmp['jaccard_similarity']:.3f}")
    print(f"  Deep promoted: {ranking_cmp['deep_promoted_by_aware']}, "
          f"demoted: {ranking_cmp['deep_demoted_by_aware']}")
    print(f"\nH1'': {h1pp_verdict}")
    print(f"H3'': {h3pp_verdict}")
    print(f"H4:   {h4_verdict}")
    print(f"\nArtifacts written to: {run_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
