"""Phase 4 Run 009: Scale-up experiment on 500+ node Wikidata-derived KG.

Experiment design:
  Each condition (A bio-only, B chem-only, C sparse-bridge, D medium-bridge):
    P1: single-op, depth=2
    P2: multi-op,  depth=2
    P3: multi-op,  depth=3
    P4: multi-op,  depth=4-5  (max_per_source=50 safety cap)

Research questions:
  H3'': Does 500+ node KG enable deep (3-hop+) cross-domain candidates?
  H4:   Does provenance-aware ranking improve top-k in this larger space?
  Scale: Is drift rate lower at 500+ nodes than at 57 nodes?
  H1'': How many unique pairs does alignment unlock at scale?

Safety cap: max_per_source=50 for depth=4-5 to prevent candidate explosion.
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
from src.kg.phase4_data import (
    build_condition_a,
    build_condition_b,
    build_condition_c,
    build_condition_d,
    compute_kg_stats,
    extract_bio_subgraph,
    extract_chem_subgraph,
)
from src.pipeline.operators import align, compose, difference, union

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHALLOW_DEPTH = 3    # 2-hop max
_MID_DEPTH = 5        # 3-hop max
_DEEP_DEPTH = 9       # up to 5-hop
_MAX_PER_SOURCE_DEEP = 50   # explosion safety cap
_TOP_K = 10
_RANDOM_SEED = 42

_LOW_SPEC_RELATIONS: frozenset[str] = frozenset({
    "relates_to", "associated_with", "part_of", "connected_to",
    "involves", "related_to", "is_a", "has_part", "contains",
    "is_type_of", "same_entity_as",
})
_WEAK_LABELS: frozenset[str] = frozenset({
    "process", "system", "entity", "thing", "object",
    "event", "concept", "item", "element", "group",
})
_DEPTH_BUCKETS: list[tuple[str, int, int]] = [
    ("2-hop", 2, 2),
    ("3-hop", 3, 3),
    ("4-5-hop", 4, 5),
]

# Run 008 drift rates for comparison
_RUN008_DRIFT = {"2-hop": 0.37, "3-hop": 0.67, "4-5-hop": 0.83}


# ---------------------------------------------------------------------------
# Semantic drift
# ---------------------------------------------------------------------------

def compute_drift_info(provenance: list[str], kg: KnowledgeGraph) -> dict:
    """Compute semantic drift flags and score (0-1) for a hypothesis path."""
    if len(provenance) < 5:
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
    """Compute per-candidate tracking fields."""
    prov = candidate.provenance
    path_length = max(0, (len(prov) - 1) // 2) if len(prov) >= 3 else 0
    node_ids_in_path = prov[0::2] if prov else []

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

    n1 = kg.get_node(candidate.subject_id)
    n2 = kg.get_node(candidate.object_id)
    is_cross_domain = bool(n1 and n2 and n1.domain != n2.domain)

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
        "is_cross_domain": is_cross_domain,
    }


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------

def run_single_op(kg: KnowledgeGraph, max_depth: int) -> list[ScoredHypothesis]:
    """Single-op baseline: compose-only."""
    rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
    return evaluate(compose(kg, max_depth=max_depth), kg, rubric)


def run_multi_op(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    max_depth: int,
    max_per_source: int = 0,
) -> tuple[list[ScoredHypothesis], KnowledgeGraph, dict[str, str], set[str]]:
    """Multi-op pipeline: align → union → compose + diff → evaluate."""
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment,
                   name=f"union_{bio_kg.name}_{chem_kg.name}")
    counter: list[int] = [0]
    cands = compose(merged, max_depth=max_depth, max_per_source=max_per_source,
                    _counter=counter)
    diff_kg = difference(bio_kg, chem_kg, alignment,
                         name=f"diff_{bio_kg.name}")
    cands += compose(diff_kg, max_depth=max_depth, max_per_source=max_per_source,
                     _counter=counter)

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pair_set(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    return {(sh.candidate.subject_id, sh.candidate.object_id) for sh in scored}


def bucket_label(path_length: int) -> str:
    for label, lo, hi in _DEPTH_BUCKETS:
        if lo <= path_length <= hi:
            return label
    return f"{path_length}-hop"


def _score_stats(scored: list[ScoredHypothesis], label: str) -> dict:
    if not scored:
        return {"pipeline": label, "n": 0, "mean_total": 0.0,
                "mean_novelty": 0.0, "min_total": 0.0, "max_total": 0.0,
                "category_distribution": {}}
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
    }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_reachability(
    p1: list[ScoredHypothesis],
    p2: list[ScoredHypothesis],
    p3: list[ScoredHypothesis],
    p4: list[ScoredHypothesis],
) -> dict:
    """Reachability comparison across pipeline/depth combinations."""
    s1 = _pair_set(p1)
    s2 = _pair_set(p2)
    s3 = _pair_set(p3)
    s4 = _pair_set(p4)
    return {
        "p1_single_shallow": len(s1),
        "p2_multi_shallow": len(s2),
        "p3_multi_mid": len(s3),
        "p4_multi_deep": len(s4),
        "unique_p2_vs_p1": len(s2 - s1),
        "unique_p3_vs_p2": len(s3 - s2),
        "unique_p4_vs_p3": len(s4 - s3),
        "deep_only_p4": len(s4 - s2 - s1),
        "h1pp_evidence": len(s2 - s1) > 0,
        "h3pp_evidence": len((s4 | s3) - s2) > 0,
    }


def analyze_depth_buckets(
    scored: list[ScoredHypothesis],
    tracking: list[dict],
    kg: KnowledgeGraph,
) -> dict:
    """Per-depth-bucket statistics."""
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for sh, tr in zip(scored, tracking):
        bl = bucket_label(tr["path_length"])
        buckets[bl].append((sh, tr))

    result: dict[str, dict] = {}
    for bl, items in sorted(buckets.items()):
        total = len(items)
        if total == 0:
            continue
        promising = sum(1 for sh, _ in items if score_category(sh.total_score) == "promising")
        cross = sum(1 for _, tr in items if tr.get("is_cross_domain", False))
        novelty = [sh.novelty for sh, _ in items]
        drift = [tr["semantic_drift_score"] for _, tr in items]
        drifted = sum(1 for _, tr in items if tr["drift_flags"])
        alignment_used = sum(1 for _, tr in items if tr["alignment_used"])
        uclasses: dict[str, int] = {}
        for _, tr in items:
            uc = tr.get("uniqueness_class", "unknown")
            uclasses[uc] = uclasses.get(uc, 0) + 1
        drift_rate = round(drifted / total, 4)
        run008_rate = _RUN008_DRIFT.get(bl, None)
        result[bl] = {
            "candidate_count": total,
            "promising_count": promising,
            "cross_domain_count": cross,
            "alignment_used_count": alignment_used,
            "mean_novelty": round(sum(novelty) / total, 4),
            "mean_drift_score": round(sum(drift) / total, 4),
            "drift_rate": drift_rate,
            "drift_rate_run008": run008_rate,
            "drift_delta_vs_run008": (
                round(drift_rate - run008_rate, 4) if run008_rate is not None else None
            ),
            "uniqueness_classes": uclasses,
        }
    return result


def compare_naive_vs_aware(
    scored_deep: list[ScoredHypothesis],
    merged_kg: KnowledgeGraph,
    tracking: list[dict],
    top_k: int = _TOP_K,
) -> dict:
    """Re-score with provenance-aware rubric and compare top-k (H4 test)."""
    rubric_aware = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=True,
    )
    scored_aware = evaluate([sh.candidate for sh in scored_deep], merged_kg, rubric_aware)

    naive_top = {(sh.candidate.subject_id, sh.candidate.object_id)
                 for sh in scored_deep[:top_k]}
    aware_top = {(sh.candidate.subject_id, sh.candidate.object_id)
                 for sh in scored_aware[:top_k]}
    overlap = naive_top & aware_top
    union_size = len(naive_top | aware_top)
    jaccard = round(len(overlap) / union_size, 4) if union_size else 0.0

    naive_rank = {(sh.candidate.subject_id, sh.candidate.object_id): i
                  for i, sh in enumerate(scored_deep)}
    aware_rank = {(sh.candidate.subject_id, sh.candidate.object_id): i
                  for i, sh in enumerate(scored_aware)}

    promoted_deep = demoted_deep = 0
    for tr, sh in zip(tracking, scored_deep):
        if tr["path_length"] >= 3:
            p = (sh.candidate.subject_id, sh.candidate.object_id)
            if aware_rank.get(p, 9999) < naive_rank.get(p, 9999):
                promoted_deep += 1
            elif aware_rank.get(p, 9999) > naive_rank.get(p, 9999):
                demoted_deep += 1

    cross_in_aware_top = sum(
        1 for sh in scored_aware[:top_k]
        if (n1 := merged_kg.get_node(sh.candidate.subject_id)) and
           (n2 := merged_kg.get_node(sh.candidate.object_id)) and
           n1.domain != n2.domain
    )

    if promoted_deep > demoted_deep:
        interpretation = "PROMOTES deep candidates"
    elif demoted_deep > promoted_deep:
        interpretation = "DEMOTES deep candidates"
    else:
        interpretation = "NEUTRAL effect on deep candidates"

    return {
        "top_k": top_k,
        "naive_top_scores": [round(sh.total_score, 4) for sh in scored_deep[:top_k]],
        "aware_top_scores": [round(sh.total_score, 4) for sh in scored_aware[:top_k]],
        "overlap_count": len(overlap),
        "jaccard_similarity": jaccard,
        "deep_promoted_by_aware": promoted_deep,
        "deep_demoted_by_aware": demoted_deep,
        "cross_domain_in_aware_top": cross_in_aware_top,
        "interpretation": f"provenance-aware {interpretation}",
        "h4_verdict": (
            "PASS" if promoted_deep > demoted_deep else
            "FAIL" if demoted_deep > promoted_deep else
            "INCONCLUSIVE"
        ),
    }


# ---------------------------------------------------------------------------
# Per-condition runner
# ---------------------------------------------------------------------------

def run_condition(
    label: str,
    kg: KnowledgeGraph,
    stats: dict,
) -> dict:
    """Run all 4 pipelines on a single condition and return results."""
    print(f"\n  --- Condition {label} ({stats['node_count']} nodes) ---")

    if stats["domain_counts"].get("biology") and stats["domain_counts"].get("chemistry"):
        bio_kg = KnowledgeGraph(name=f"bio_{label}")
        chem_kg = KnowledgeGraph(name=f"chem_{label}")
        for node in kg.nodes():
            if node.domain == "biology":
                bio_kg.add_node(node)
            else:
                chem_kg.add_node(node)
        bio_ids = {n.id for n in bio_kg.nodes()}
        chem_ids = {n.id for n in chem_kg.nodes()}
        for edge in kg.edges():
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
        is_cross_domain = True
    else:
        # Single-domain: use kg as both bio and chem for multi-op
        bio_kg = kg
        chem_kg = kg
        is_cross_domain = False

    # P1: single-op, depth=2
    p1 = run_single_op(kg, _SHALLOW_DEPTH)
    print(f"    P1 single/shallow: {len(p1)} candidates")

    # P2: multi-op, depth=2
    p2, merged2, align2, aligned2 = run_multi_op(bio_kg, chem_kg, _SHALLOW_DEPTH)
    print(f"    P2 multi/shallow:  {len(p2)} candidates, {len(align2)} aligned")

    # P3: multi-op, depth=3
    p3, merged3, align3, aligned3 = run_multi_op(bio_kg, chem_kg, _MID_DEPTH)
    print(f"    P3 multi/mid:      {len(p3)} candidates")

    # P4: multi-op, depth=4-5 (with safety cap)
    p4, merged4, align4, aligned4 = run_multi_op(
        bio_kg, chem_kg, _DEEP_DEPTH, _MAX_PER_SOURCE_DEEP
    )
    print(f"    P4 multi/deep:     {len(p4)} candidates")

    # Tracking for P4 (deepest pipeline)
    p1_pairs = _pair_set(p1)
    p2_pairs = _pair_set(p2)
    p4_tracking = [
        compute_tracking_fields(
            sh.candidate, merged4, p1_pairs, p2_pairs, aligned4
        )
        for sh in p4
    ]

    # Reachability
    reach = analyze_reachability(p1, p2, p3, p4)

    # Depth bucket analysis for P4
    buckets = analyze_depth_buckets(p4, p4_tracking, merged4)

    # H4: provenance-aware vs naive for P4
    if p4:
        ranking_cmp = compare_naive_vs_aware(p4, merged4, p4_tracking)
    else:
        ranking_cmp = {"h4_verdict": "SKIP (no P4 candidates)", "jaccard_similarity": 0}

    # H3'' assessment: are there deep cross-domain candidates?
    deep_cross_count = sum(
        1 for tr in p4_tracking
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    )
    h3pp_verdict = (
        f"PASS — {deep_cross_count} deep cross-domain candidates found"
        if deep_cross_count > 0
        else "FAIL — 0 deep cross-domain candidates (same-domain saturation)"
    )
    h1pp_verdict = (
        f"PASS — {reach['unique_p2_vs_p1']} unique pairs via alignment"
        if reach["unique_p2_vs_p1"] > 0
        else "FAIL — 0 unique pairs from alignment"
    )

    return {
        "label": label,
        "kg_stats": stats,
        "is_cross_domain_condition": is_cross_domain,
        "alignment_count": len(align2),
        "reachability": reach,
        "depth_buckets": buckets,
        "ranking_comparison": ranking_cmp,
        "h1pp_verdict": h1pp_verdict,
        "h3pp_verdict": h3pp_verdict,
        "h4_verdict": ranking_cmp.get("h4_verdict", "SKIP"),
        "deep_cross_domain_count": deep_cross_count,
        "pipeline_stats": {
            "P1": _score_stats(p1, "P1_single_shallow"),
            "P2": _score_stats(p2, "P2_multi_shallow"),
            "P3": _score_stats(p3, "P3_multi_mid"),
            "P4": _score_stats(p4, "P4_multi_deep"),
        },
        "p4_candidates_sample": [
            {**sh.to_dict(), "tracking": tr}
            for sh, tr in zip(p4[:20], p4_tracking[:20])
        ],
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_input_summary_md(
    conditions: dict[str, dict],
    data_source: str,
) -> str:
    """Build input_summary.md."""
    rows = "\n".join(
        f"| {label} | {c['kg_stats']['node_count']} | {c['kg_stats']['edge_count']} "
        f"| {c['kg_stats']['bridge_density']:.4f} "
        f"| {c['kg_stats']['relation_type_count']} |"
        for label, c in conditions.items()
    )
    return f"""# Input Summary — Run 009 Phase 4 Scale-Up

## Data Source
Source: {data_source} (curated fallback with Wikidata entity IDs)

## Conditions

| Condition | Nodes | Edges | Bridge Density | Relation Types |
|-----------|-------|-------|---------------|----------------|
{rows}

## Relation Types (Condition C)
{', '.join(conditions.get('C', {}).get('kg_stats', {}).get('relation_types', [])[:20])}

## Scale Comparison
- Phase 3 Run 008: 57 nodes (Condition C)
- Phase 4 Run 009: {conditions.get('C', {}).get('kg_stats', {}).get('node_count', '?')} nodes (Condition C) — {conditions.get('C', {}).get('kg_stats', {}).get('node_count', 0) // 57}x larger
"""


def build_evaluation_summary_md(conditions: dict[str, dict]) -> str:
    """Build evaluation_summary.md."""
    rows = []
    for label, c in conditions.items():
        ps = c["pipeline_stats"]
        rows.append(
            f"| {label} | {ps['P1']['n']} | {ps['P2']['n']} "
            f"| {ps['P3']['n']} | {ps['P4']['n']} "
            f"| {c['alignment_count']} "
            f"| {c['reachability']['unique_p2_vs_p1']} "
            f"| {c['deep_cross_domain_count']} |"
        )

    return f"""# Evaluation Summary — Run 009 Phase 4

## Pipeline Candidate Counts

| Cond | P1(single/2) | P2(multi/2) | P3(multi/3) | P4(multi/4-5) | Aligned | UniqueViaAlign | DeepCross |
|------|-------------|------------|------------|--------------|---------|----------------|-----------|
{chr(10).join(rows)}

## Hypothesis Verdicts

| Condition | H1'' | H3'' | H4 |
|-----------|------|------|-----|
{chr(10).join(f"| {label} | {c['h1pp_verdict'][:40]} | {c['h3pp_verdict'][:40]} | {c['h4_verdict']} |" for label, c in conditions.items())}

## Key Finding
H3'' testable: {"YES — deep cross-domain candidates found in at least one condition" if any(c['deep_cross_domain_count'] > 0 for c in conditions.values()) else "NO — 0 deep cross-domain candidates across all conditions"}
"""


def build_depth_bucket_md(conditions: dict[str, dict]) -> str:
    """Build depth_bucket_analysis.md."""
    sections = []
    for label, c in conditions.items():
        buckets = c["depth_buckets"]
        if not buckets:
            sections.append(f"## Condition {label}\nNo P4 candidates.\n")
            continue
        def _fmt_r008(st: dict) -> str:
            r = st.get("drift_rate_run008")
            return f"{r:.2%}" if r is not None else "N/A"

        def _fmt_delta(st: dict) -> str:
            d = st.get("drift_delta_vs_run008")
            return f"{d:+.2%}" if d is not None else "N/A"

        rows = "\n".join(
            f"| {bl} | {st['candidate_count']} | {st['cross_domain_count']} "
            f"| {st['drift_rate']:.2%} | {_fmt_r008(st)} | {_fmt_delta(st)} |"
            for bl, st in sorted(buckets.items())
        )
        sections.append(f"""## Condition {label}

| Depth | Candidates | Cross-Domain | Drift Rate | Run008 Rate | Delta |
|-------|-----------|-------------|-----------|------------|-------|
{rows}
""")
    return "# Depth Bucket Analysis — Run 009 Phase 4\n\n" + "\n".join(sections)


def build_drift_comparison_md(conditions: dict[str, dict]) -> str:
    """Build drift_scaleup_comparison.md."""
    lines = [
        "# Drift Scaleup Comparison — 57 nodes (Run 008) vs 500+ nodes (Run 009)",
        "",
        "## Run 008 Drift (57 nodes, Condition C)",
        "| Depth | Drift Rate |",
        "|-------|-----------|",
        "| 2-hop | 37% |",
        "| 3-hop | 67% |",
        "| 4-5-hop | 83% |",
        "",
        "## Run 009 Drift (500+ nodes, per condition)",
        "",
    ]
    for label, c in conditions.items():
        lines.append(f"### Condition {label}")
        if not c["depth_buckets"]:
            lines.append("No deep candidates.\n")
            continue
        lines.append("| Depth | Run009 Rate | Delta vs Run008 |")
        lines.append("|-------|------------|----------------|")
        for bl, st in sorted(c["depth_buckets"].items()):
            delta = st.get("drift_delta_vs_run008")
            delta_str = f"{delta:+.2%}" if delta is not None else "N/A"
            lines.append(f"| {bl} | {st['drift_rate']:.2%} | {delta_str} |")
        lines.append("")

    lines += [
        "## Interpretation",
        "",
        "- Negative delta → drift DECREASED at larger scale (scale artifact confirmed)",
        "- Positive delta → drift INCREASED (structural problem, not scale artifact)",
        "- ~0 delta → drift is scale-independent (operator design issue)",
    ]
    return "\n".join(lines)


def build_ranking_comparison_md(conditions: dict[str, dict]) -> str:
    """Build ranking_comparison.md."""
    lines = ["# Ranking Comparison — Run 009 Phase 4 (Naive vs Provenance-Aware)", ""]
    for label, c in conditions.items():
        rc = c["ranking_comparison"]
        lines.append(f"## Condition {label}")
        lines.append(f"- Jaccard (top-{rc.get('top_k',10)}): {rc.get('jaccard_similarity', 'N/A')}")
        lines.append(f"- Deep promoted: {rc.get('deep_promoted_by_aware', 'N/A')}")
        lines.append(f"- Deep demoted:  {rc.get('deep_demoted_by_aware', 'N/A')}")
        lines.append(f"- H4 verdict:    {rc.get('h4_verdict', 'SKIP')}")
        if rc.get("interpretation"):
            lines.append(f"- {rc['interpretation']}")
        lines.append("")
    return "\n".join(lines)


def build_condition_comparison_md(conditions: dict[str, dict]) -> str:
    """Build condition_comparison.md."""
    lines = ["# Condition Comparison — Run 009 Phase 4", ""]
    lines.append("| Condition | Nodes | Aligned | UniqueViaAlign | DeepCross | H1'' | H3'' | H4 |")
    lines.append("|-----------|-------|---------|----------------|-----------|------|------|-----|")
    for label, c in conditions.items():
        lines.append(
            f"| {label} "
            f"| {c['kg_stats']['node_count']} "
            f"| {c['alignment_count']} "
            f"| {c['reachability']['unique_p2_vs_p1']} "
            f"| {c['deep_cross_domain_count']} "
            f"| {'PASS' if 'PASS' in c['h1pp_verdict'] else 'FAIL'} "
            f"| {'PASS' if 'PASS' in c['h3pp_verdict'] else 'FAIL'} "
            f"| {c['h4_verdict']} |"
        )
    return "\n".join(lines)


def build_next_actions_md(conditions: dict[str, dict]) -> str:
    """Build next_actions.md."""
    any_h3pp = any("PASS" in c["h3pp_verdict"] for c in conditions.values())
    any_h4_pass = any(c["h4_verdict"] == "PASS" for c in conditions.values())
    any_h1pp = any("PASS" in c["h1pp_verdict"] for c in conditions.values())

    return f"""# Next Actions — Run 009 Phase 4

## Summary

- H1'' at scale: {"CONFIRMED in some conditions" if any_h1pp else "NOT confirmed"}
- H3'' at scale: {"CONFIRMED — deep cross-domain candidates exist" if any_h3pp else "STILL FAILING — structural issue persists at 500+ nodes"}
- H4 at scale: {"CONFIRMED — provenance-aware promotes deep candidates" if any_h4_pass else "STILL FAILING — provenance-aware demotes deep candidates"}

## Recommended Next Steps

{"1. H3'' confirmed: scale was the bottleneck. Deep cross-domain paths now exist." if any_h3pp else "1. H3'' still fails: drift is not a scale artifact — it is an operator design problem."}
{"   → Phase 5: relation filtering (pre-compose) to improve cross-domain path quality." if any_h3pp else "   → Phase 5: pre-compose relation filtering to suppress low-spec paths."}

{"2. H4 confirmed: provenance-aware ranking works for deep paths at scale." if any_h4_pass else "2. H4 still fails: need revised scoring rubric that rewards structural diversity."}
{"   → Incorporate provenance_aware=True as default rubric." if any_h4_pass else "   → Revise H4 rubric: quality_aware_traceability penalizes only weak/mixed paths."}

3. H1'' alignment mechanism: {"validated at scale — more unique pairs than Run 008." if any_h1pp else "needs larger alignment bridges."}
   → Consider lower alignment threshold (0.4) and synonym expansion.

4. Drift comparison: see drift_scaleup_comparison.md for scale-dependence analysis.
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run Phase 4 Run 009 scale-up experiment."""
    timestamp = datetime.now().isoformat()
    run_dir = (
        Path(__file__).parent.parent.parent
        / "runs"
        / "run_009_20260410_phase4_scaleup"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("Run 009 — Phase 4 Scale-Up (500+ nodes)")
    print(f"{'='*60}")

    # Load data
    print("\nLoading Phase 4 KG data...")
    data = load_phase4_data()
    print(f"  Source: {data.source}")
    print(f"  Bio nodes: {len(data.bio_nodes)}, Bio edges: {len(data.bio_edges)}")
    print(f"  Chem nodes: {len(data.chem_nodes)}, Chem edges: {len(data.chem_edges)}")
    print(f"  Bridge sparse: {len(data.bridge_edges_sparse)}, medium: {len(data.bridge_edges_medium)}")

    # Build KGs
    kg_a = build_condition_a(data)
    kg_b = build_condition_b(data)
    kg_c = build_condition_c(data)
    kg_d = build_condition_d(data)

    stats_a = compute_kg_stats(kg_a)
    stats_b = compute_kg_stats(kg_b)
    stats_c = compute_kg_stats(kg_c)
    stats_d = compute_kg_stats(kg_d)

    print(f"\n  KG sizes:")
    print(f"    A (bio-only):      {stats_a['node_count']} nodes, {stats_a['edge_count']} edges")
    print(f"    B (chem-only):     {stats_b['node_count']} nodes, {stats_b['edge_count']} edges")
    print(f"    C (sparse bridge): {stats_c['node_count']} nodes, {stats_c['edge_count']} edges")
    print(f"    D (medium bridge): {stats_d['node_count']} nodes, {stats_d['edge_count']} edges")

    # Run conditions
    print("\nRunning experiments...")
    results: dict[str, dict] = {}
    for label, kg, stats in [
        ("A", kg_a, stats_a),
        ("B", kg_b, stats_b),
        ("C", kg_c, stats_c),
        ("D", kg_d, stats_d),
    ]:
        results[label] = run_condition(label, kg, stats)

    # Build artifacts
    print("\nWriting artifacts...")

    # run_config.json
    run_config = {
        "run_id": "run_009",
        "phase": "Phase4",
        "experiment": "scale_up_500plus_nodes",
        "timestamp": timestamp,
        "random_seed": _RANDOM_SEED,
        "data_source": data.source,
        "conditions": ["A_bio_only", "B_chem_only", "C_sparse_bridge", "D_medium_bridge"],
        "pipelines": ["P1_single_shallow", "P2_multi_shallow", "P3_multi_mid", "P4_multi_deep"],
        "depths": {
            "P1": f"max_depth={_SHALLOW_DEPTH} (2-hop)",
            "P2": f"max_depth={_SHALLOW_DEPTH} (2-hop)",
            "P3": f"max_depth={_MID_DEPTH} (3-hop)",
            "P4": f"max_depth={_DEEP_DEPTH} (4-5-hop, max_per_source={_MAX_PER_SOURCE_DEEP})",
        },
        "rubric": "EvaluationRubric(cross_domain_novelty_bonus=False)",
        "research_questions": [
            "H3'': Does 500+ node KG enable deep cross-domain candidates?",
            "H4: Does provenance-aware ranking improve top-k at scale?",
            "Scale: Is drift rate lower at 500+ nodes (scale artifact vs operator issue)?",
            "H1'': How many unique alignment pairs at scale?",
        ],
        "phase3_baseline": {
            "run": "Run 008",
            "node_count": 57,
            "drift_2hop": 0.37,
            "drift_3hop": 0.67,
            "drift_4hop": 0.83,
            "unique_via_alignment": 4,
            "deep_cross_domain": 0,
        },
        "verdicts": {
            label: {
                "h1pp": c["h1pp_verdict"],
                "h3pp": c["h3pp_verdict"],
                "h4": c["h4_verdict"],
            }
            for label, c in results.items()
        },
    }
    _write_json(run_dir / "run_config.json", run_config)

    # output_candidates.json (P4 candidates from Condition C)
    cond_c = results.get("C", {})
    _write_json(run_dir / "output_candidates.json", cond_c.get("p4_candidates_sample", []))

    # Markdown artifacts
    _write_md(run_dir / "input_summary.md", build_input_summary_md(results, data.source))
    _write_md(run_dir / "evaluation_summary.md", build_evaluation_summary_md(results))
    _write_md(run_dir / "depth_bucket_analysis.md", build_depth_bucket_md(results))
    _write_md(run_dir / "drift_scaleup_comparison.md", build_drift_comparison_md(results))
    _write_md(run_dir / "ranking_comparison.md", build_ranking_comparison_md(results))
    _write_md(run_dir / "condition_comparison.md", build_condition_comparison_md(results))
    _write_md(run_dir / "next_actions.md", build_next_actions_md(results))

    # data_construction.md
    _write_md(run_dir / "data_construction.md", f"""# Data Construction — Run 009 Phase 4

## Source
{data.source} (curated fallback with Wikidata entity structure)

## Biology Subgraph
- {len(data.bio_nodes)} nodes covering:
  - Proteins/kinases (TP53, EGFR, KRAS, BRAF, PI3K, AKT, mTOR...)
  - Metabolic enzymes (glycolysis, TCA cycle, fatty acid oxidation)
  - Metabolites (ATP, NADH, pyruvate, citrate, amino acids...)
  - Genes, diseases, signaling molecules, organelles
- {len(data.bio_edges)} edges with {stats_a['relation_type_count']} relation types

## Chemistry Subgraph
- {len(data.chem_nodes)} nodes covering:
  - Energy molecules (ATP, NAD+, CoA as chemical compounds)
  - Organic acids, sugars, amino acids (chemical perspective)
  - Drugs/pharmaceuticals (kinase inhibitors, statins, NSAIDs)
  - Metal ions, vitamins, cofactors, ROS, solvents
  - Chemical reactions/processes as nodes
- {len(data.chem_edges)} edges with {stats_b['relation_type_count']} relation types

## Bridge Entities
- Sparse ({len(data.bridge_edges_sparse)} edges): metabolite identity bridges (ATP, NAD+, CoA, TCA acids)
- Medium ({len(data.bridge_edges_medium)} edges): + amino acids, drug-enzyme links, metal cofactors

## Scale vs Phase 3
- Phase 3 Condition C: 57 nodes, 6 aligned pairs
- Phase 4 Condition C: {stats_c['node_count']} nodes, {cond_c.get('alignment_count', '?')} aligned pairs
""")

    # Console summary
    print(f"\n{'='*60}")
    print("Run 009 Results")
    print(f"{'='*60}")
    for label, c in results.items():
        print(f"\n  Condition {label} ({c['kg_stats']['node_count']} nodes):")
        ps = c["pipeline_stats"]
        print(f"    P1={ps['P1']['n']} P2={ps['P2']['n']} P3={ps['P3']['n']} P4={ps['P4']['n']}")
        print(f"    Aligned pairs: {c['alignment_count']}")
        print(f"    Unique via alignment: {c['reachability']['unique_p2_vs_p1']}")
        print(f"    Deep cross-domain:    {c['deep_cross_domain_count']}")
        print(f"    H1'': {c['h1pp_verdict'][:60]}")
        print(f"    H3'': {c['h3pp_verdict'][:60]}")
        print(f"    H4:   {c['h4_verdict']}")
        if c["depth_buckets"]:
            print("    Drift by depth:")
            for bl, st in sorted(c["depth_buckets"].items()):
                r008 = st.get("drift_rate_run008")
                delta = st.get("drift_delta_vs_run008")
                r008_str = f"{r008:.0%}" if r008 is not None else "N/A"
                delta_str = f"{delta:+.2%}" if delta is not None else "N/A"
                print(f"      {bl}: {st['drift_rate']:.0%} "
                      f"(R008={r008_str}, Δ={delta_str})")

    print(f"\nArtifacts: {run_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
