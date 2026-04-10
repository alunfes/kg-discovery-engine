"""Run 013: Reproducibility / robustness test across 3 bio-chem subsets.

Applies the Run 012 drift-filtered pipeline (unchanged) to 3 subsets:
  Subset A: Original Phase 4 KG (bio:/chem:, cancer signaling + metabolic chemistry)
  Subset B: Immunology (imm:) + Natural products (nat:)
  Subset C: Neuroscience (neu:) + Neuro-pharmacology (phar:)

Parameters are NOT retuned per subset — same filter spec as Run 012.

Success: ≥2 subsets reproduce:
  - alignment-dependent reachability (unique_to_multi > 0)
  - deep cross-domain candidates (≥3-hop, count ≥ 1)
  - filter-surviving promising candidates (≥ 1 after filter)

Failure: Run 012 results are Subset A-specific artifacts.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.wikidata_phase4_loader import WD4Data, load_phase4_data
from src.data.wikidata_phase4_subset_b import load_subset_b_data
from src.data.wikidata_phase4_subset_c import load_subset_c_data
from src.eval.scorer import EvaluationRubric, ScoredHypothesis, evaluate, score_category
from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
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
# Constants — identical to Run 012 (NOT retuned)
# ---------------------------------------------------------------------------

_RUN_ID = "run_013"
_DATE = datetime.now().strftime("%Y%m%d")
_RUN_DIR_NAME = f"run_013_{_DATE}_reproducibility"
_TOP_K = 20

# Filter spec (same as Run 012)
_FILTER_RELATIONS: frozenset[str] = frozenset({
    "contains",
    "is_product_of",
    "is_reverse_of",
    "is_isomer_of",
})
_MIN_STRONG_RATIO = 0.40
_GUARD_CONSECUTIVE = True
_FILTER_GENERIC_INTERMEDIATES = True

_SUBSET_NAMES = ("A", "B", "C")

# ---------------------------------------------------------------------------
# KG construction helpers
# ---------------------------------------------------------------------------


def _build_bio_chem_kgs(data: WD4Data) -> tuple[KnowledgeGraph, KnowledgeGraph]:
    """Extract bio-only and chem-only KGs from a WD4Data (Condition C: sparse bridge).

    Args:
        data: WD4Data to extract from.

    Returns:
        Tuple of (bio_kg, chem_kg).
    """
    # Build merged condition-C graph using Phase 4 builder logic
    from src.kg.phase4_data import _build_kg, _build_merged_kg
    bio_kg_full = _build_kg(data.bio_nodes, data.bio_edges, "biology", "bio_sub")
    chem_kg_full = _build_kg(data.chem_nodes, data.chem_edges, "chemistry", "chem_sub")
    merged = _build_merged_kg(bio_kg_full, chem_kg_full, data.bridge_edges_sparse, "merged")

    bio_kg = KnowledgeGraph(name="bio_run013")
    chem_kg = KnowledgeGraph(name="chem_run013")
    bio_ids: set[str] = set()
    chem_ids: set[str] = set()

    for node in merged.nodes():
        if node.domain == "biology":
            bio_kg.add_node(node)
            bio_ids.add(node.id)
        else:
            chem_kg.add_node(node)
            chem_ids.add(node.id)

    for edge in merged.edges():
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

    return bio_kg, chem_kg


# ---------------------------------------------------------------------------
# Pipeline (same as Run 012, parameterised)
# ---------------------------------------------------------------------------


def _run_filtered_pipeline(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    subset_label: str,
) -> tuple[list[HypothesisCandidate], KnowledgeGraph, set[str]]:
    """Apply Run 012 drift-filtered pipeline to a bio/chem KG pair.

    Args:
        bio_kg: Biology-domain knowledge graph.
        chem_kg: Chemistry-domain knowledge graph.
        subset_label: Label for naming merged/diff graphs.

    Returns:
        Tuple of (candidates, merged_kg, aligned_node_ids).
    """
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment,
                   name=f"union_{subset_label}")

    counter: list[int] = [0]
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
                         name=f"diff_{subset_label}")
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

    seen: set[tuple[str, str]] = set()
    unique: list[HypothesisCandidate] = []
    for c in cands:
        k = (c.subject_id, c.object_id)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    return unique, merged, set(alignment.keys())


def _run_baseline_pipeline(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    subset_label: str,
) -> tuple[list[HypothesisCandidate], KnowledgeGraph, set[str]]:
    """Run pipeline WITHOUT filters (for pre-filter count).

    Args:
        bio_kg: Biology-domain knowledge graph.
        chem_kg: Chemistry-domain knowledge graph.
        subset_label: Label for naming merged/diff graphs.

    Returns:
        Tuple of (candidates, merged_kg, aligned_node_ids).
    """
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment,
                   name=f"union_{subset_label}_baseline")

    counter: list[int] = [0]
    cands = compose(merged, max_depth=_DEEP_DEPTH,
                    max_per_source=_MAX_PER_SOURCE_DEEP, _counter=counter)

    diff_kg = difference(bio_kg, chem_kg, alignment,
                         name=f"diff_{subset_label}_baseline")
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
# Analysis helpers
# ---------------------------------------------------------------------------


def _score_revised(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
) -> list[ScoredHypothesis]:
    """Score with revised_traceability rubric (same as Run 012).

    Args:
        candidates: Hypothesis candidates to score.
        kg: Knowledge graph providing context.

    Returns:
        Scored and sorted hypotheses.
    """
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=False,
        revised_traceability=True,
    )
    return evaluate(candidates, kg, rubric)


def _candidate_path_length(c: HypothesisCandidate) -> int:
    """Return hop count for a candidate.

    Args:
        c: Hypothesis candidate.

    Returns:
        Number of hops in provenance path.
    """
    prov = c.provenance
    return max(0, (len(prov) - 1) // 2) if len(prov) >= 3 else 0


def _is_cross_domain(c: HypothesisCandidate, kg: KnowledgeGraph) -> bool:
    """Check if subject and object are in different domains.

    Args:
        c: Hypothesis candidate.
        kg: Knowledge graph.

    Returns:
        True if cross-domain pair.
    """
    n1 = kg.get_node(c.subject_id)
    n2 = kg.get_node(c.object_id)
    if n1 and n2:
        return n1.domain != n2.domain
    s_pref = c.subject_id.split(":")[0] if ":" in c.subject_id else ""
    t_pref = c.object_id.split(":")[0] if ":" in c.object_id else ""
    return bool(s_pref) and bool(t_pref) and s_pref != t_pref


def _strong_ratio(c: HypothesisCandidate) -> float:
    """Compute fraction of strong mechanistic relations in path.

    Args:
        c: Hypothesis candidate.

    Returns:
        Ratio of strong relations (0.0 to 1.0).
    """
    rels = c.provenance[1::2]
    if not rels:
        return 0.0
    return sum(1 for r in rels if r in _STRONG_MECHANISTIC) / len(rels)


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


def _assign_label(c: HypothesisCandidate) -> tuple[str, str]:
    """Assign quality label to a deep cross-domain candidate.

    Uses same logic as Run 012 assign_label.

    Args:
        c: Hypothesis candidate.

    Returns:
        Tuple of (label, reason) where label is
        'promising', 'weak_speculative', or 'drift_heavy'.
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
            f"Majority structural/generic connectors (hard_drift_ratio={hard_ratio:.2f})"
        )
    if has_repeat and strong_ratio == 0.0:
        return "drift_heavy", (
            "Consecutive repeated relation + no strong mechanistic relations"
        )
    if semi_ratio >= 0.5 and hard_ratio == 0.0:
        return "promising", (
            f"{_candidate_path_length(c)}-hop cross-domain path with "
            f"strong relations ({semi_ratio:.2f}) and no generic connectors"
        )
    if strong_count >= 2 and hard_ratio == 0.0 and mild_ratio <= 0.5:
        return "promising", (
            f"High strong-relation ratio ({strong_ratio:.2f}) with no hard-drift connectors"
        )
    return "weak_speculative", (
        f"Mixed chain: strong_ratio={strong_ratio:.2f}, "
        f"hard_drift={hard_ratio:.2f}, mild_drift={mild_ratio:.2f}"
    )


def _compute_subset_metrics(
    subset_label: str,
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    single_op_pairs: set[tuple[str, str]],
    shallow_pairs: set[tuple[str, str]],
) -> dict:
    """Compute all required metrics for one subset.

    Args:
        subset_label: Subset identifier (A, B, or C).
        bio_kg: Biology KG for this subset.
        chem_kg: Chemistry KG for this subset.
        single_op_pairs: Pairs from single-op baseline.
        shallow_pairs: Pairs from shallow pipeline.

    Returns:
        Dict of metrics including candidate counts, label distribution,
        alignment stats, top-20 composition, and drift rates.
    """
    # Per-subset single-op pairs for accurate uniqueness_class calculation
    from src.pipeline.operators import compose as _compose_op
    from src.eval.scorer import EvaluationRubric as _RubricLocal
    _p1_rubric = _RubricLocal(cross_domain_novelty_bonus=False)
    _p1_scored = evaluate(_compose_op(bio_kg, max_depth=_SHALLOW_DEPTH), bio_kg, _p1_rubric)
    local_single_op_pairs = {
        (sh.candidate.subject_id, sh.candidate.object_id) for sh in _p1_scored
    }

    print(f"\n  [Subset {subset_label}] Running baseline pipeline...")
    baseline_cands, merged_kg, aligned_ids = _run_baseline_pipeline(
        bio_kg, chem_kg, subset_label
    )
    print(f"  [Subset {subset_label}] Baseline candidates: {len(baseline_cands)}")

    baseline_tracking = [
        compute_tracking_fields(c, merged_kg, local_single_op_pairs, shallow_pairs, aligned_ids)
        for c in baseline_cands
    ]
    baseline_deep_cd = [
        c for c, tr in zip(baseline_cands, baseline_tracking)
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    ]

    print(f"  [Subset {subset_label}] Running filtered pipeline...")
    filtered_cands, _, _ = _run_filtered_pipeline(bio_kg, chem_kg, subset_label)
    print(f"  [Subset {subset_label}] Filtered candidates: {len(filtered_cands)}")

    filtered_scored = _score_revised(filtered_cands, merged_kg)
    filtered_tracking = [
        compute_tracking_fields(c, merged_kg, local_single_op_pairs, shallow_pairs, aligned_ids)
        for c in filtered_cands
    ]
    filtered_deep_cd = [
        c for c, tr in zip(filtered_cands, filtered_tracking)
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    ]

    # Label distribution for filtered deep CD
    labeled = []
    for c in filtered_deep_cd:
        label, reason = _assign_label(c)
        labeled.append({
            "id": c.id,
            "subject_id": c.subject_id,
            "object_id": c.object_id,
            "path_length": _candidate_path_length(c),
            "label": label,
            "reason": reason,
            "strong_ratio": round(_strong_ratio(c), 4),
            "provenance": c.provenance,
        })

    label_counts = {"promising": 0, "weak_speculative": 0, "drift_heavy": 0}
    for item in labeled:
        label_counts[item["label"]] = label_counts.get(item["label"], 0) + 1

    # Alignment-dependent reachability: candidates only reachable via alignment
    # uniqueness_class == "reachable_only_by_alignment" means the pair uses an
    # aligned (merged) node and is not reachable by single-op baseline.
    unique_to_multi = sum(
        1 for tr in filtered_tracking
        if tr.get("uniqueness_class") == "reachable_only_by_alignment"
    )

    # Top-20 analysis
    top20 = filtered_scored[:_TOP_K]
    depth_dist: dict[str, int] = {}
    cd_count = 0
    scores = []
    for sh in top20:
        pl = _candidate_path_length(sh.candidate)
        lbl = bucket_label(pl)
        depth_dist[lbl] = depth_dist.get(lbl, 0) + 1
        if _is_cross_domain(sh.candidate, merged_kg):
            cd_count += 1
        scores.append(round(sh.total_score, 4))

    mean_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    # Drift rate by depth bucket (baseline) — uses semantic_drift_score as proxy
    from src.pipeline.run_phase4 import compute_drift_info  # noqa: F811
    bucket_drift: dict[str, list[float]] = {}
    for c, tr in zip(baseline_cands, baseline_tracking):
        pl = tr["path_length"]
        if pl < 1:
            continue
        bl = bucket_label(pl)
        # Use pre-computed semantic_drift_score from tracking fields
        score = tr.get("semantic_drift_score", 0.0)
        bucket_drift.setdefault(bl, []).append(score)

    drift_by_bucket: dict[str, float] = {}
    for bl, rates in bucket_drift.items():
        drift_by_bucket[bl] = round(sum(rates) / len(rates), 4) if rates else 0.0

    # KG stats
    kg_stats = {
        "bio_nodes": len(list(bio_kg.nodes())),
        "bio_edges": len(list(bio_kg.edges())),
        "chem_nodes": len(list(chem_kg.nodes())),
        "chem_edges": len(list(chem_kg.edges())),
        "aligned_pairs": len(aligned_ids),
    }

    return {
        "subset": subset_label,
        "kg_stats": kg_stats,
        "metric_1_total_candidates": {
            "baseline": len(baseline_cands),
            "filtered": len(filtered_cands),
        },
        "metric_2_deep_cross_domain": {
            "baseline": len(baseline_deep_cd),
            "filtered": len(filtered_deep_cd),
        },
        "metric_3_label_distribution": {
            "total": len(labeled),
            "promising": label_counts["promising"],
            "weak_speculative": label_counts["weak_speculative"],
            "drift_heavy": label_counts["drift_heavy"],
            "promising_pct": round(
                label_counts["promising"] / len(labeled) * 100, 1
            ) if labeled else 0.0,
            "drift_heavy_pct": round(
                label_counts["drift_heavy"] / len(labeled) * 100, 1
            ) if labeled else 0.0,
        },
        "metric_4_alignment_reachability": {
            "unique_to_multi": unique_to_multi,
            "aligned_pairs": len(aligned_ids),
        },
        "metric_5_top20": {
            "depth_distribution": depth_dist,
            "cross_domain_count": cd_count,
            "mean_score": mean_score,
            "scores": scores,
        },
        "metric_6_drift_by_depth": drift_by_bucket,
        "deep_cd_labeled": labeled,
    }


# ---------------------------------------------------------------------------
# Reproducibility verdict
# ---------------------------------------------------------------------------


def _compute_verdict(results: dict[str, dict]) -> dict:
    """Determine reproducibility verdict across subsets.

    Success: ≥2 subsets reproduce all three phenomena.

    Args:
        results: Dict mapping subset label to metric dict.

    Returns:
        Dict with per-subset pass/fail and overall verdict.
    """
    per_subset: dict[str, dict] = {}
    for s_label, r in results.items():
        align_ok = r["metric_4_alignment_reachability"]["unique_to_multi"] > 0
        deep_cd_ok = r["metric_2_deep_cross_domain"]["filtered"] >= 1
        promising_ok = r["metric_3_label_distribution"]["promising"] >= 1

        per_subset[s_label] = {
            "alignment_dependent_reachability": align_ok,
            "deep_cross_domain_candidates": deep_cd_ok,
            "filter_surviving_promising": promising_ok,
            "all_pass": align_ok and deep_cd_ok and promising_ok,
        }

    passing = sum(1 for v in per_subset.values() if v["all_pass"])
    verdict = "SUCCESS" if passing >= 2 else "FAILURE"
    reason = (
        f"{passing}/3 subsets reproduce all three phenomena "
        "(alignment-dependent reachability + deep CD + filter-surviving promising)"
    )

    return {
        "overall_verdict": verdict,
        "passing_subsets": passing,
        "reason": reason,
        "per_subset": per_subset,
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: object) -> None:
    """Write data as JSON to path.

    Args:
        path: Output file path.
        data: JSON-serializable object.
    """
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    """Write markdown content to path.

    Args:
        path: Output file path.
        content: Markdown string.
    """
    path.write_text(content, encoding="utf-8")


def _build_comparison_md(
    results: dict[str, dict],
    verdict: dict,
) -> str:
    """Build cross-subset comparison markdown.

    Args:
        results: Per-subset metric dicts.
        verdict: Overall verdict dict.

    Returns:
        Markdown string.
    """
    lines = [
        "# Run 013: Cross-Subset Comparison",
        "",
        f"**Date**: {_DATE}",
        f"**Overall Verdict**: {verdict['overall_verdict']} "
        f"({verdict['passing_subsets']}/3 subsets pass)",
        "",
        f"> {verdict['reason']}",
        "",
        "## KG Stats",
        "",
        "| Subset | Bio nodes | Chem nodes | Aligned pairs |",
        "|--------|-----------|-----------|---------------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        r = results[s]
        ks = r["kg_stats"]
        lines.append(
            f"| {s} | {ks['bio_nodes']} | {ks['chem_nodes']} | "
            f"{ks['aligned_pairs']} |"
        )

    lines += [
        "",
        "## Metric 1: Candidate Counts",
        "",
        "| Subset | Before filter | After filter | Reduction |",
        "|--------|--------------|-------------|-----------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_1_total_candidates"]
        red = m["baseline"] - m["filtered"]
        pct = round(red / m["baseline"] * 100, 1) if m["baseline"] else 0.0
        lines.append(f"| {s} | {m['baseline']} | {m['filtered']} | {red} ({pct}%) |")

    lines += [
        "",
        "## Metric 2: Deep Cross-Domain (≥3-hop)",
        "",
        "| Subset | Before filter | After filter |",
        "|--------|--------------|-------------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_2_deep_cross_domain"]
        lines.append(f"| {s} | {m['baseline']} | {m['filtered']} |")

    lines += [
        "",
        "## Metric 3: Label Distribution (filtered deep CD)",
        "",
        "| Subset | Total | Promising | Weak Spec | Drift Heavy |",
        "|--------|-------|-----------|-----------|-------------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_3_label_distribution"]
        lines.append(
            f"| {s} | {m['total']} | {m['promising']} ({m['promising_pct']}%) | "
            f"{m['weak_speculative']} | {m['drift_heavy']} ({m['drift_heavy_pct']}%) |"
        )

    lines += [
        "",
        "## Metric 4: Alignment-Dependent Reachability",
        "",
        "| Subset | unique_to_multi | Aligned pairs |",
        "|--------|----------------|---------------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_4_alignment_reachability"]
        lines.append(f"| {s} | {m['unique_to_multi']} | {m['aligned_pairs']} |")

    lines += [
        "",
        "## Metric 5: Top-20 Composition",
        "",
        "| Subset | Mean score | CD in top-20 | Depth dist |",
        "|--------|-----------|-------------|-----------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_5_top20"]
        depth = ", ".join(f"{k}:{v}" for k, v in sorted(m["depth_distribution"].items()))
        lines.append(
            f"| {s} | {m['mean_score']} | {m['cross_domain_count']} | {depth} |"
        )

    lines += [
        "",
        "## Metric 6: Drift Rate by Depth Bucket (semantic_drift_score)",
        "",
        "| Subset | 2-hop | 3-hop | 4-5-hop |",
        "|--------|-------|-------|---------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        m = results[s]["metric_6_drift_by_depth"]
        lines.append(
            f"| {s} | {m.get('2-hop', 'N/A')} | "
            f"{m.get('3-hop', 'N/A')} | {m.get('4-5-hop', 'N/A')} |"
        )

    lines += [
        "",
        "## Reproducibility Verdict",
        "",
        f"**Overall: {verdict['overall_verdict']}**",
        "",
        "| Subset | Alignment reachability | Deep CD | Promising survivors | All pass |",
        "|--------|----------------------|---------|---------------------|----------|",
    ]
    for s in _SUBSET_NAMES:
        if s not in verdict["per_subset"]:
            continue
        v = verdict["per_subset"][s]
        lines.append(
            f"| {s} | {'✓' if v['alignment_dependent_reachability'] else '✗'} | "
            f"{'✓' if v['deep_cross_domain_candidates'] else '✗'} | "
            f"{'✓' if v['filter_surviving_promising'] else '✗'} | "
            f"{'✓' if v['all_pass'] else '✗'} |"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> None:
    """Run 013: cross-subset reproducibility test."""
    import random
    random.seed(_RANDOM_SEED)

    print(f"=== Run 013: Reproducibility Test ({_DATE}) ===")
    print(f"Filter spec: {sorted(_FILTER_RELATIONS)}")
    print(f"Guards: consecutive_repeat={_GUARD_CONSECUTIVE}, "
          f"min_strong_ratio={_MIN_STRONG_RATIO}")

    # --- Output directory ---
    base_dir = Path(__file__).parent.parent.parent
    run_dir = base_dir / "runs" / _RUN_DIR_NAME
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput: {run_dir}")

    # --- P1 single-op baseline for tracking fields (Subset A bio KG) ---
    print("\n[1/5] Loading Phase 4 data (Subset A)...")
    data_a = load_phase4_data()
    bio_a, chem_a = _build_bio_chem_kgs(data_a)
    print(f"  Subset A — bio: {len(list(bio_a.nodes()))} nodes, "
          f"chem: {len(list(chem_a.nodes()))} nodes")

    from src.pipeline.operators import compose as _compose
    from src.eval.scorer import EvaluationRubric as _Rubric
    p1_rubric = _Rubric(cross_domain_novelty_bonus=False)
    p1_scored = evaluate(_compose(bio_a, max_depth=_SHALLOW_DEPTH), bio_a, p1_rubric)
    single_op_pairs = {(sh.candidate.subject_id, sh.candidate.object_id)
                       for sh in p1_scored}
    shallow_pairs: set[tuple[str, str]] = set()

    # --- Load Subset B and C ---
    print("\n[2/5] Loading Subset B (Immunology + Natural products)...")
    data_b = load_subset_b_data()
    bio_b, chem_b = _build_bio_chem_kgs(data_b)
    print(f"  Subset B — bio: {len(list(bio_b.nodes()))} nodes, "
          f"chem: {len(list(chem_b.nodes()))} nodes")

    print("\n[3/5] Loading Subset C (Neuroscience + Neuro-pharmacology)...")
    data_c = load_subset_c_data()
    bio_c, chem_c = _build_bio_chem_kgs(data_c)
    print(f"  Subset C — bio: {len(list(bio_c.nodes()))} nodes, "
          f"chem: {len(list(chem_c.nodes()))} nodes")

    # --- Run pipeline on each subset ---
    print("\n[4/5] Running filtered pipeline on all 3 subsets...")
    results: dict[str, dict] = {}
    for s_label, bio_kg, chem_kg in [
        ("A", bio_a, chem_a),
        ("B", bio_b, chem_b),
        ("C", bio_c, chem_c),
    ]:
        print(f"\n--- Subset {s_label} ---")
        results[s_label] = _compute_subset_metrics(
            s_label, bio_kg, chem_kg, single_op_pairs, shallow_pairs
        )

    # --- Verdict ---
    verdict = _compute_verdict(results)
    print(f"\n{'=' * 50}")
    print(f"VERDICT: {verdict['overall_verdict']}")
    print(f"  {verdict['reason']}")
    for s_label, v in verdict["per_subset"].items():
        status = "PASS" if v["all_pass"] else "FAIL"
        print(f"  Subset {s_label}: {status} "
              f"(align={v['alignment_dependent_reachability']}, "
              f"deep_cd={v['deep_cross_domain_candidates']}, "
              f"promising={v['filter_surviving_promising']})")
    print('=' * 50)

    # --- Save artifacts ---
    print("\n[5/5] Saving artifacts...")

    # run_config.json
    run_config = {
        "run_id": _RUN_ID,
        "date": _DATE,
        "purpose": "Cross-subset reproducibility test for Run 012 pipeline",
        "subsets": {
            "A": "Original Phase 4 KG (bio:/chem:, cancer signaling + metabolic chemistry)",
            "B": "Immunology (imm:) + Natural products (nat:)",
            "C": "Neuroscience (neu:) + Neuro-pharmacology (phar:)",
        },
        "pipeline_spec": {
            "filter_relations": sorted(_FILTER_RELATIONS),
            "guard_consecutive_repeat": _GUARD_CONSECUTIVE,
            "min_strong_ratio": _MIN_STRONG_RATIO,
            "filter_generic_intermediates": _FILTER_GENERIC_INTERMEDIATES,
            "max_depth": _DEEP_DEPTH,
            "max_per_source": _MAX_PER_SOURCE_DEEP,
            "random_seed": _RANDOM_SEED,
            "note": "Identical to Run 012 — NOT retuned per subset",
        },
        "success_criteria": {
            "passing_subsets_required": 2,
            "per_subset_criteria": [
                "unique_to_multi > 0 (alignment-dependent reachability)",
                "filtered deep CD count >= 1",
                "promising label count >= 1 after filter",
            ],
        },
    }
    _write_json(run_dir / "run_config.json", run_config)

    # per_subset_results.json
    per_subset_out = {}
    for s_label, r in results.items():
        per_subset_out[s_label] = {k: v for k, v in r.items() if k != "deep_cd_labeled"}
    _write_json(run_dir / "per_subset_results.json", per_subset_out)

    # deep_cd_labeled per subset
    for s_label, r in results.items():
        _write_json(
            run_dir / f"subset_{s_label}_deep_cd_labeled.json",
            r["deep_cd_labeled"],
        )

    # cross_subset_comparison.md
    comparison_md = _build_comparison_md(results, verdict)
    _write_md(run_dir / "cross_subset_comparison.md", comparison_md)

    # decision_memo.md
    decision_memo = _build_decision_memo(results, verdict)
    _write_md(run_dir / "decision_memo.md", decision_memo)

    # subset_construction.md
    subset_construction = _build_subset_construction_md(results)
    _write_md(run_dir / "subset_construction.md", subset_construction)

    print(f"  Artifacts written to {run_dir}/")
    print("  Files:")
    for f in sorted(run_dir.iterdir()):
        print(f"    {f.name}")

    return results, verdict


def _build_decision_memo(
    results: dict[str, dict],
    verdict: dict,
) -> str:
    """Build decision memo markdown.

    Args:
        results: Per-subset metric dicts.
        verdict: Overall verdict dict.

    Returns:
        Markdown string.
    """
    lines = [
        "# Run 013 Decision Memo",
        "",
        f"**Date**: {_DATE}",
        f"**Verdict**: {verdict['overall_verdict']}",
        "",
        "## Summary",
        "",
        f"{verdict['passing_subsets']}/3 subsets passed all three reproducibility criteria.",
        "",
        "## Per-Subset Observations",
        "",
    ]

    for s in _SUBSET_NAMES:
        if s not in results:
            continue
        r = results[s]
        v = verdict["per_subset"].get(s, {})
        m2 = r["metric_2_deep_cross_domain"]
        m3 = r["metric_3_label_distribution"]
        m4 = r["metric_4_alignment_reachability"]

        status = "PASS" if v.get("all_pass") else "FAIL"
        lines += [
            f"### Subset {s}: {status}",
            "",
            f"- Deep CD candidates: baseline={m2['baseline']}, filtered={m2['filtered']}",
            f"- Label distribution: promising={m3['promising']}, "
            f"weak_spec={m3['weak_speculative']}, drift_heavy={m3['drift_heavy']}",
            f"- Alignment-dependent reachability: unique_to_multi={m4['unique_to_multi']}",
            "",
        ]

        if r["deep_cd_labeled"]:
            lines.append("Top deep CD candidates (filtered, promising):")
            for item in r["deep_cd_labeled"][:3]:
                if item["label"] == "promising":
                    lines.append(
                        f"  - [{item['label']}] {item['subject_id']} → ... → "
                        f"{item['object_id']} "
                        f"(depth={item['path_length']}, strong_ratio={item['strong_ratio']})"
                    )
            lines.append("")

    lines += [
        "## Next Steps",
        "",
    ]
    if verdict["overall_verdict"] == "SUCCESS":
        lines += [
            "Run 013 PASSED. The pipeline shows robustness across different domain pairs.",
            "",
            "Recommended next actions:",
            "1. Quantitative analysis of which structural properties drive reproducibility",
            "2. H1''/H3'' re-verification with filter-cleaned candidates",
            "3. Investigation of why certain subsets produce fewer promising candidates",
        ]
    else:
        lines += [
            "Run 013 FAILED. Run 012 results may be Subset A-specific.",
            "",
            "Recommended next actions:",
            "1. Investigate why non-A subsets fail to produce deep CD candidates",
            "2. Consider whether bridge density or alignment quality is limiting",
            "3. Revisit H3'' status — may require domain-specific calibration",
        ]

    return "\n".join(lines) + "\n"


def _build_subset_construction_md(results: dict[str, dict]) -> str:
    """Build subset construction detail markdown.

    Args:
        results: Per-subset metric dicts.

    Returns:
        Markdown string.
    """
    lines = [
        "# Subset Construction Details",
        "",
        f"**Date**: {_DATE}",
        "",
        "## Design Principles",
        "",
        "Each subset targets a different bio/chem domain pair to test pipeline robustness:",
        "",
        "- **Overlap minimization**: Different entity prefixes (bio:/chem:, imm:/nat:, neu:/phar:)",
        "- **Bridge structure**: Same-entity bridges + drug/compound-enzyme inhibition bridges",
        "- **Size target**: 400-600 nodes per subset",
        "- **Relation diversity**: Same relation types used across subsets",
        "",
        "## Subset Specifications",
        "",
        "### Subset A (Reference)",
        "- **Bio domain**: Cancer signaling (TP53, KRAS, PI3K, HIF1A pathways)",
        "  + metabolic enzymes (glycolysis, TCA cycle, fatty acid)",
        "- **Chem domain**: Energy molecules, organic acids, drugs, cofactors",
        "- **Bridge type**: Metabolite identity bridges (bio:m_NADH ↔ chem:NADH)",
        "- **Key finding (Run 012)**: VHL/HIF1A/LDHA/NADH cascade — 3 promising deep CD",
        "",
        "### Subset B (Immunology + Natural Products)",
        "- **Bio domain**: Immune signaling (TLR, NLRP3, JAK-STAT, eicosanoid pathway)",
        "- **Chem domain**: Flavonoids, terpenoids, alkaloids, isothiocyanates",
        "- **Bridge type**: Eicosanoid identity (imm:m_AA ↔ nat:ArachidonicAcid)",
        "  + compound-enzyme inhibition (nat:Berberine → inhibits → imm:NLRP3)",
        "",
        "### Subset C (Neuroscience + Neuro-pharmacology)",
        "- **Bio domain**: Neurotransmitter synthesis, receptors, synaptic signaling",
        "- **Chem domain**: Psychiatric drugs, neurotransmitter chemistry",
        "- **Bridge type**: Neurotransmitter identity (neu:m_Dopamine ↔ phar:Dopamine)",
        "  + drug-receptor inhibition (phar:Haloperidol → inhibits → neu:DRD2)",
        "",
        "## Bridge Density",
        "",
        "| Subset | Sparse bridges | Medium bridges | Approx density |",
        "|--------|---------------|---------------|----------------|",
    ]

    for s, sparse, medium in [
        ("A", 12, 31),
        ("B", 13, 32),
        ("C", 12, 31),
    ]:
        if s in results:
            ks = results[s]["kg_stats"]
            total_n = ks["bio_nodes"] + ks["chem_nodes"]
            lines.append(
                f"| {s} | {sparse} | {medium} | ~{round(sparse / max(total_n, 1) * 100, 1)}% |"
            )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
