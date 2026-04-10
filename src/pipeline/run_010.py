"""Run 010: H4 rubric revision — re-ranking with revised traceability.

Re-uses Run 009 Condition C/D KG and generates all P4 candidates,
then applies three ranking schemes:
  1. naive            (provenance_aware=False, revised_traceability=False)
  2. old_aware        (provenance_aware=True,  revised_traceability=False)
  3. revised_aware    (provenance_aware=False,  revised_traceability=True)

No new KG construction: reuses load_phase4_data + build_condition_c/d.
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
from src.pipeline.operators import align, compose, difference, union
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

_TOP_K = 20  # wider window for comparison
_RUN_ID = "run_010"
_CONDITION = "C"  # sparse-bridge cross-domain condition


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _pair_set(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    return {(sh.candidate.subject_id, sh.candidate.object_id) for sh in scored}


def run_pipelines(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
) -> tuple[
    list[ScoredHypothesis],
    list[ScoredHypothesis],
    KnowledgeGraph,
    set[str],
]:
    """Run P1 (single/shallow) and P4 (multi/deep) and return all candidates.

    Returns: (p1_scored, p4_scored, merged_kg, aligned_node_ids)
    """
    # Neutral rubric for generation — cross_domain bonus off (Run 009 setting)
    rubric_base = EvaluationRubric(cross_domain_novelty_bonus=False)

    # P1: single-op baseline
    p1 = evaluate(compose(bio_kg, max_depth=_SHALLOW_DEPTH), bio_kg, rubric_base)

    # P4: full multi-op deep pipeline
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

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique: list[HypothesisCandidate] = []
    for c in cands:
        k = (c.subject_id, c.object_id)
        if k not in seen:
            seen.add(k)
            unique.append(c)

    p4 = evaluate(unique, merged, rubric_base)
    aligned_ids = set(alignment.keys())
    return p1, p4, merged, aligned_ids


# ---------------------------------------------------------------------------
# Three-way ranking
# ---------------------------------------------------------------------------

def rank_naive(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
) -> list[ScoredHypothesis]:
    """Ranking 1: naive — fixed traceability=0.7, no depth penalty."""
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=False,
        revised_traceability=False,
    )
    scored = evaluate(candidates, kg, rubric)
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored


def rank_old_aware(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
) -> list[ScoredHypothesis]:
    """Ranking 2: old provenance-aware — inversely proportional to depth."""
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=True,
        revised_traceability=False,
    )
    scored = evaluate(candidates, kg, rubric)
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored


def rank_revised_aware(
    candidates: list[HypothesisCandidate],
    kg: KnowledgeGraph,
) -> list[ScoredHypothesis]:
    """Ranking 3: revised provenance-aware — quality-based penalty (Run 010)."""
    rubric = EvaluationRubric(
        cross_domain_novelty_bonus=False,
        provenance_aware=False,
        revised_traceability=True,
    )
    scored = evaluate(candidates, kg, rubric)
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _rank_map(scored: list[ScoredHypothesis]) -> dict[tuple[str, str], int]:
    return {(sh.candidate.subject_id, sh.candidate.object_id): i
            for i, sh in enumerate(scored)}


def jaccard(a: set, b: set) -> float:
    u = len(a | b)
    return round(len(a & b) / u, 4) if u else 0.0


def analyze_ranking_changes(
    tracking: list[dict],
    candidates: list[HypothesisCandidate],
    naive: list[ScoredHypothesis],
    old_aware: list[ScoredHypothesis],
    revised: list[ScoredHypothesis],
    top_k: int = _TOP_K,
) -> dict:
    """Compute rank-change statistics across the three schemes."""
    naive_rank = _rank_map(naive)
    old_rank = _rank_map(old_aware)
    rev_rank = _rank_map(revised)

    naive_top = {(sh.candidate.subject_id, sh.candidate.object_id)
                 for sh in naive[:top_k]}
    old_top = {(sh.candidate.subject_id, sh.candidate.object_id)
               for sh in old_aware[:top_k]}
    rev_top = {(sh.candidate.subject_id, sh.candidate.object_id)
               for sh in revised[:top_k]}

    # Deep candidates: path_length >= 3
    deep_pairs = {
        (c.subject_id, c.object_id)
        for c, tr in zip(candidates, tracking)
        if tr["path_length"] >= 3
    }
    cross_pairs = {
        (c.subject_id, c.object_id)
        for c, tr in zip(candidates, tracking)
        if tr.get("is_cross_domain", False)
    }
    deep_cross_pairs = deep_pairs & cross_pairs

    def _movement(pairs: set, rank_a: dict, rank_b: dict) -> tuple[int, int, int]:
        promoted = demoted = unchanged = 0
        for p in pairs:
            a = rank_a.get(p, 9999)
            b = rank_b.get(p, 9999)
            if b < a:
                promoted += 1
            elif b > a:
                demoted += 1
            else:
                unchanged += 1
        return promoted, demoted, unchanged

    rev_vs_naive_deep = _movement(deep_pairs, naive_rank, rev_rank)
    rev_vs_old_deep = _movement(deep_pairs, old_rank, rev_rank)
    rev_vs_naive_cross = _movement(deep_cross_pairs, naive_rank, rev_rank)

    return {
        "top_k": top_k,
        "total_candidates": len(candidates),
        "deep_candidates": len(deep_pairs),
        "cross_domain_candidates": len(cross_pairs),
        "deep_cross_domain_candidates": len(deep_cross_pairs),
        "jaccard_naive_vs_old": jaccard(naive_top, old_top),
        "jaccard_naive_vs_revised": jaccard(naive_top, rev_top),
        "jaccard_old_vs_revised": jaccard(old_top, rev_top),
        "naive_top_k_scores": [round(sh.total_score, 4) for sh in naive[:top_k]],
        "old_aware_top_k_scores": [round(sh.total_score, 4) for sh in old_aware[:top_k]],
        "revised_top_k_scores": [round(sh.total_score, 4) for sh in revised[:top_k]],
        "revised_vs_naive_deep_promoted": rev_vs_naive_deep[0],
        "revised_vs_naive_deep_demoted": rev_vs_naive_deep[1],
        "revised_vs_naive_deep_unchanged": rev_vs_naive_deep[2],
        "revised_vs_old_deep_promoted": rev_vs_old_deep[0],
        "revised_vs_old_deep_demoted": rev_vs_old_deep[1],
        "revised_vs_old_deep_unchanged": rev_vs_old_deep[2],
        "revised_vs_naive_deep_cross_promoted": rev_vs_naive_cross[0],
        "revised_vs_naive_deep_cross_demoted": rev_vs_naive_cross[1],
        "revised_vs_naive_deep_cross_unchanged": rev_vs_naive_cross[2],
        "new_entries_in_revised_top_k": len(rev_top - naive_top),
        "h4_verdict_old": (
            "PASS" if _movement(deep_pairs, naive_rank, old_rank)[0] >
            _movement(deep_pairs, naive_rank, old_rank)[1] else "FAIL"
        ),
        "h4_verdict_revised": (
            "PASS" if rev_vs_naive_deep[0] > rev_vs_naive_deep[1]
            else "FAIL" if rev_vs_naive_deep[0] < rev_vs_naive_deep[1]
            else "INCONCLUSIVE"
        ),
    }


def analyze_depth_composition(
    tracking: list[dict],
    naive: list[ScoredHypothesis],
    revised: list[ScoredHypothesis],
    top_k: int = _TOP_K,
) -> dict:
    """Compare depth distribution in top-k between naive and revised."""
    tr_map = {
        (sh.candidate.subject_id, sh.candidate.object_id): tr
        for sh, tr in zip(naive, tracking)  # tracking aligns with original candidate order
    }

    def _depth_dist(ranked: list[ScoredHypothesis]) -> dict[str, int]:
        dist: dict[str, int] = {}
        for sh in ranked[:top_k]:
            p = (sh.candidate.subject_id, sh.candidate.object_id)
            tr = tr_map.get(p)
            if tr:
                bl = bucket_label(tr["path_length"])
                dist[bl] = dist.get(bl, 0) + 1
        return dist

    def _cross_count(ranked: list[ScoredHypothesis]) -> int:
        return sum(
            1 for sh in ranked[:top_k]
            if tr_map.get((sh.candidate.subject_id, sh.candidate.object_id),
                          {}).get("is_cross_domain", False)
        )

    return {
        "naive_top_k_depth_dist": _depth_dist(naive),
        "old_aware_not_computed": "skipped",
        "revised_top_k_depth_dist": _depth_dist(revised),
        "naive_cross_in_top_k": _cross_count(naive),
        "revised_cross_in_top_k": _cross_count(revised),
    }


# ---------------------------------------------------------------------------
# Artifact builders
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_ranking_comparison_md(
    analysis: dict,
    depth_comp: dict,
    top_k: int,
) -> str:
    """Build ranking_comparison.md."""
    lines = [
        "# Ranking Comparison — Run 010 (3-way: naive / old aware / revised aware)",
        "",
        f"## Overview (top-{top_k})",
        "",
        f"| Metric | Value |",
        "|--------|-------|",
        f"| Total candidates | {analysis['total_candidates']} |",
        f"| Deep candidates (≥3-hop) | {analysis['deep_candidates']} |",
        f"| Cross-domain candidates | {analysis['cross_domain_candidates']} |",
        f"| Deep cross-domain | {analysis['deep_cross_domain_candidates']} |",
        "",
        "## Jaccard Similarity (top-k overlap)",
        "",
        "| Pair | Jaccard |",
        "|------|---------|",
        f"| naive vs old_aware | {analysis['jaccard_naive_vs_old']} |",
        f"| naive vs revised | {analysis['jaccard_naive_vs_revised']} |",
        f"| old_aware vs revised | {analysis['jaccard_old_vs_revised']} |",
        "",
        "## Deep Candidate Movement (revised vs naive)",
        "",
        f"| Movement | Count |",
        "|----------|-------|",
        f"| Deep promoted | {analysis['revised_vs_naive_deep_promoted']} |",
        f"| Deep demoted | {analysis['revised_vs_naive_deep_demoted']} |",
        f"| Deep unchanged | {analysis['revised_vs_naive_deep_unchanged']} |",
        "",
        "## Deep Cross-Domain Movement (revised vs naive)",
        "",
        f"| Movement | Count |",
        "|----------|-------|",
        f"| Promoted | {analysis['revised_vs_naive_deep_cross_promoted']} |",
        f"| Demoted | {analysis['revised_vs_naive_deep_cross_demoted']} |",
        f"| Unchanged | {analysis['revised_vs_naive_deep_cross_unchanged']} |",
        "",
        f"## New entries in revised top-{top_k}: {analysis['new_entries_in_revised_top_k']}",
        "",
        "## H4 Verdicts",
        "",
        f"| Scheme | Verdict |",
        "|--------|---------|",
        f"| old provenance-aware | {analysis['h4_verdict_old']} |",
        f"| revised aware | {analysis['h4_verdict_revised']} |",
        "",
        "## Depth Distribution in Top-k",
        "",
        "| Bucket | Naive | Revised |",
        "|--------|-------|---------|",
    ]
    naive_dist = depth_comp["naive_top_k_depth_dist"]
    rev_dist = depth_comp["revised_top_k_depth_dist"]
    all_buckets = sorted(set(naive_dist) | set(rev_dist))
    for bl in all_buckets:
        lines.append(f"| {bl} | {naive_dist.get(bl, 0)} | {rev_dist.get(bl, 0)} |")
    lines += [
        "",
        f"| Cross-domain in top-k | {depth_comp['naive_cross_in_top_k']} | "
        f"{depth_comp['revised_cross_in_top_k']} |",
    ]
    return "\n".join(lines)


def build_decision_memo_md(analysis: dict) -> str:
    """Build decision_memo.md."""
    old_verdict = analysis["h4_verdict_old"]
    rev_verdict = analysis["h4_verdict_revised"]
    deep_promoted = analysis["revised_vs_naive_deep_promoted"]
    deep_demoted = analysis["revised_vs_naive_deep_demoted"]
    cross_promoted = analysis["revised_vs_naive_deep_cross_promoted"]

    verdict_text = (
        "PASS — revised traceability promotes more deep candidates than it demotes."
        if rev_verdict == "PASS"
        else "FAIL — deep candidates still demoted under revised rubric."
        if rev_verdict == "FAIL"
        else "INCONCLUSIVE — equal promotion/demotion of deep candidates."
    )

    return f"""# Decision Memo — Run 010 H4 Rubric Revision

## What Changed
- Old traceability: `1.0 / hop_count` → longer paths always score lower
- Revised traceability: quality-based penalty (low-spec relations, repeated
  consecutive relations, generic intermediate nodes) → length-neutral

## Key Results
- Old provenance-aware H4 verdict: **{old_verdict}**
- Revised provenance-aware H4 verdict: **{rev_verdict}**
- Deep candidates promoted by revised vs naive: {deep_promoted}
- Deep candidates demoted by revised vs naive: {deep_demoted}
- Deep cross-domain promoted by revised vs naive: {cross_promoted}
- New deep entries in top-{analysis['top_k']}: {analysis['new_entries_in_revised_top_k']}

## Verdict
{verdict_text}

## Interpretation
{"The revised rubric successfully re-ranks deep candidates by chain quality rather than length, enabling high-quality deep paths to rise above shallow-but-generic ones." if rev_verdict == "PASS" else "Even quality-based traceability cannot rescue the deep candidates in this dataset — the underlying chains are weak regardless of the metric used."}

## Next Step
{"Run 012: pre-compose relation filtering to suppress low-specificity paths before compose(), then re-test H4 with revised rubric." if rev_verdict == "FAIL" else "Adopt revised_traceability=True as default for H4 evaluation going forward."}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 010: H4 rubric revision re-ranking experiment."""
    import random
    random.seed(_RANDOM_SEED)

    run_date = "20260410"
    run_dir = (
        Path(__file__).parent.parent.parent
        / "runs"
        / f"run_010_{run_date}_h4_rubric_fix"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()

    print(f"\n{'='*60}")
    print("Run 010 — H4 Rubric Revision (Re-ranking)")
    print(f"{'='*60}")

    # Load KG (reuse Run 009 data — same data, no new construction)
    print("\nLoading Phase 4 data (Run 009 KG)...")
    data = load_phase4_data()
    print(f"  Source: {data.source}")

    kg_c = build_condition_c(data)
    stats = compute_kg_stats(kg_c)
    print(f"  Condition C: {stats['node_count']} nodes, {stats['edge_count']} edges")

    # Extract bio/chem subgraphs for multi-op
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

    # Run pipelines
    print("\nRunning P1 (single/shallow) and P4 (multi/deep)...")
    p1_scored, p4_scored, merged_kg, aligned_ids = run_pipelines(bio_kg, chem_kg)
    print(f"  P1: {len(p1_scored)} candidates")
    print(f"  P4: {len(p4_scored)} candidates")

    # Compute tracking for ALL P4 candidates
    p1_pairs = _pair_set(p1_scored)
    p2_pairs: set[tuple[str, str]] = set()  # placeholder (not needed for uniqueness)
    tracking = [
        compute_tracking_fields(sh.candidate, merged_kg, p1_pairs, p2_pairs, aligned_ids)
        for sh in p4_scored
    ]

    candidates = [sh.candidate for sh in p4_scored]

    # Deep cross-domain stats
    deep_cross = [
        (c, tr) for c, tr in zip(candidates, tracking)
        if tr["path_length"] >= 3 and tr.get("is_cross_domain", False)
    ]
    print(f"  Deep cross-domain (≥3-hop): {len(deep_cross)}")

    # Apply three rankings
    print("\nApplying 3 ranking schemes...")
    naive_ranked = rank_naive(candidates, merged_kg)
    old_aware_ranked = rank_old_aware(candidates, merged_kg)
    revised_ranked = rank_revised_aware(candidates, merged_kg)
    print("  Done.")

    # Analysis
    analysis = analyze_ranking_changes(
        tracking, candidates, naive_ranked, old_aware_ranked, revised_ranked, _TOP_K
    )
    depth_comp = analyze_depth_composition(
        tracking, naive_ranked, revised_ranked, _TOP_K
    )

    # Print summary
    print(f"\n{'='*60}")
    print(f"  Total P4 candidates: {analysis['total_candidates']}")
    print(f"  Deep (≥3-hop):       {analysis['deep_candidates']}")
    print(f"  Deep cross-domain:   {analysis['deep_cross_domain_candidates']}")
    print(f"  Jaccard naive/revised (top-{_TOP_K}): {analysis['jaccard_naive_vs_revised']}")
    print(f"  Deep promoted by revised vs naive: {analysis['revised_vs_naive_deep_promoted']}")
    print(f"  Deep demoted  by revised vs naive: {analysis['revised_vs_naive_deep_demoted']}")
    print(f"  H4 (old aware):  {analysis['h4_verdict_old']}")
    print(f"  H4 (revised):    {analysis['h4_verdict_revised']}")
    print(f"{'='*60}\n")

    # Write artifacts
    print("Writing artifacts...")

    run_config = {
        "run_id": _RUN_ID,
        "phase": "Phase4",
        "experiment": "h4_rubric_revision_reranking",
        "timestamp": timestamp,
        "random_seed": _RANDOM_SEED,
        "data_source": data.source,
        "condition": _CONDITION,
        "reuses_run_009_kg": True,
        "ranking_schemes": [
            "naive (provenance_aware=False, revised=False)",
            "old_aware (provenance_aware=True, revised=False)",
            "revised_aware (revised_traceability=True)",
        ],
        "revised_traceability_design": {
            "base_score": 1.0,
            "floor": 0.1,
            "penalties": {
                "low_specificity_relation": -0.1,
                "consecutive_repeated_relation": -0.15,
                "generic_intermediate_node": -0.05,
            },
            "low_spec_relations": [
                "relates_to", "associated_with", "part_of", "has_part",
                "interacts_with", "is_a", "connected_to", "involves", "related_to",
            ],
            "weak_node_labels": [
                "process", "system", "entity", "substance", "compound",
            ],
        },
        "top_k": _TOP_K,
        "results": {
            "total_candidates": analysis["total_candidates"],
            "deep_candidates": analysis["deep_candidates"],
            "deep_cross_domain": analysis["deep_cross_domain_candidates"],
            "h4_verdict_old_aware": analysis["h4_verdict_old"],
            "h4_verdict_revised": analysis["h4_verdict_revised"],
            "jaccard_naive_vs_revised": analysis["jaccard_naive_vs_revised"],
            "deep_promoted_by_revised": analysis["revised_vs_naive_deep_promoted"],
            "deep_demoted_by_revised": analysis["revised_vs_naive_deep_demoted"],
        },
    }
    _write_json(run_dir / "run_config.json", run_config)

    # output_candidates_reranked.json — all P4 candidates with all three scores
    reranked_records = []
    naive_rank_map = _rank_map(naive_ranked)
    old_rank_map = _rank_map(old_aware_ranked)
    rev_rank_map = _rank_map(revised_ranked)
    naive_score_map = {
        (sh.candidate.subject_id, sh.candidate.object_id): sh.total_score
        for sh in naive_ranked
    }
    old_score_map = {
        (sh.candidate.subject_id, sh.candidate.object_id): sh.total_score
        for sh in old_aware_ranked
    }
    rev_score_map = {
        (sh.candidate.subject_id, sh.candidate.object_id): sh.total_score
        for sh in revised_ranked
    }

    for c, tr in zip(candidates, tracking):
        p = (c.subject_id, c.object_id)
        reranked_records.append({
            "id": c.id,
            "subject_id": c.subject_id,
            "relation": c.relation,
            "object_id": c.object_id,
            "description": c.description,
            "path_length": tr["path_length"],
            "is_cross_domain": tr.get("is_cross_domain", False),
            "drift_flags": tr["drift_flags"],
            "semantic_drift_score": tr["semantic_drift_score"],
            "provenance": c.provenance,
            "rankings": {
                "naive_rank": naive_rank_map.get(p, -1),
                "old_aware_rank": old_rank_map.get(p, -1),
                "revised_rank": rev_rank_map.get(p, -1),
                "naive_score": round(naive_score_map.get(p, 0.0), 4),
                "old_aware_score": round(old_score_map.get(p, 0.0), 4),
                "revised_score": round(rev_score_map.get(p, 0.0), 4),
                "rank_change_naive_to_revised": (
                    naive_rank_map.get(p, 0) - rev_rank_map.get(p, 0)
                ),
            },
        })
    _write_json(run_dir / "output_candidates_reranked.json", reranked_records)

    _write_md(run_dir / "ranking_comparison.md",
              build_ranking_comparison_md(analysis, depth_comp, _TOP_K))
    _write_md(run_dir / "decision_memo.md", build_decision_memo_md(analysis))

    print(f"Artifacts: {run_dir}")
    print(f"{'='*60}\n")

    return {
        "analysis": analysis,
        "depth_comp": depth_comp,
        "candidates": candidates,
        "tracking": tracking,
        "naive_ranked": naive_ranked,
        "old_aware_ranked": old_aware_ranked,
        "revised_ranked": revised_ranked,
        "merged_kg": merged_kg,
        "run_dir": run_dir,
    }


if __name__ == "__main__":
    main()
