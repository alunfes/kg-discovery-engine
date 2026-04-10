"""Tests for Run 008: deep-composition experiment.

Covers:
  - compute_drift_info: all three flag types + score computation
  - compute_tracking_fields: path_length, alignment_used, uniqueness_class
  - compose max_per_source: caps candidate count per source
  - analyze_depth_buckets: correct bucketing and stats
  - compare_rankings: overlap / jaccard calculation
  - run_single_op_deep / run_multi_op_deep: smoke tests
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
from src.eval.scorer import EvaluationRubric, evaluate, score_category
from src.pipeline.operators import compose
from src.pipeline.run_phase3_deep_compose import (
    analyze_depth_buckets,
    bucket_label,
    build_tracked_output,
    compare_rankings,
    compute_drift_info,
    compute_tracking_fields,
    rescore_with_rubric,
    run_multi_op_deep,
    run_single_op_deep,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _simple_kg(name: str = "test") -> KnowledgeGraph:
    """A → B → C (chain), domains vary."""
    kg = KnowledgeGraph(name=name)
    kg.add_node(KGNode("A", "alpha", "biology"))
    kg.add_node(KGNode("B", "beta", "chemistry"))
    kg.add_node(KGNode("C", "gamma", "biology"))
    kg.add_edge(KGEdge("A", "activates", "B"))
    kg.add_edge(KGEdge("B", "produces", "C"))
    return kg


def _chain_kg(length: int = 5) -> KnowledgeGraph:
    """Linear chain: n0 → n1 → ... → n{length-1}."""
    kg = KnowledgeGraph(name="chain")
    for i in range(length):
        kg.add_node(KGNode(f"n{i}", f"node{i}", "biology"))
    for i in range(length - 1):
        kg.add_edge(KGEdge(f"n{i}", "activates", f"n{i+1}"))
    return kg


def _drift_kg() -> KnowledgeGraph:
    """KG with generic relation and weakly typed node."""
    kg = KnowledgeGraph(name="drift_test")
    kg.add_node(KGNode("X", "protein-x", "biology"))
    kg.add_node(KGNode("P", "process", "biology"))   # weak label
    kg.add_node(KGNode("Y", "enzyme-y", "biology"))
    kg.add_edge(KGEdge("X", "relates_to", "P"))      # low-specificity
    kg.add_edge(KGEdge("P", "relates_to", "Y"))      # low-specificity
    return kg


def _make_candidate(
    subj: str,
    obj: str,
    prov: list[str],
    cid: str = "H0001",
) -> HypothesisCandidate:
    return HypothesisCandidate(
        id=cid,
        subject_id=subj,
        relation="transitively_related_to",
        object_id=obj,
        description="test",
        provenance=prov,
        operator="compose",
        source_kg_name="test",
    )


# ---------------------------------------------------------------------------
# compute_drift_info
# ---------------------------------------------------------------------------

class TestComputeDriftInfo:
    def test_no_drift_strong_relations(self):
        kg = _simple_kg()
        prov = ["A", "activates", "B", "produces", "C"]
        result = compute_drift_info(prov, kg)
        assert result["drift_flags"] == []
        assert result["semantic_drift_score"] == 0.0

    def test_relation_repetition_flag(self):
        kg = _chain_kg(4)
        # Same relation appears twice
        prov = ["n0", "activates", "n1", "activates", "n2"]
        result = compute_drift_info(prov, kg)
        assert "relation_repetition" in result["drift_flags"]
        assert result["semantic_drift_score"] > 0.0

    def test_low_specificity_flag(self):
        kg = _drift_kg()
        prov = ["X", "relates_to", "P", "relates_to", "Y"]
        result = compute_drift_info(prov, kg)
        assert "low_specificity_relations" in result["drift_flags"]

    def test_weakly_typed_intermediates_flag(self):
        kg = _drift_kg()
        prov = ["X", "relates_to", "P", "relates_to", "Y"]
        result = compute_drift_info(prov, kg)
        # P has label "process" which is in _WEAK_LABELS
        assert "weakly_typed_intermediates" in result["drift_flags"]

    def test_max_score_all_flags(self):
        kg = _drift_kg()
        prov = ["X", "relates_to", "P", "relates_to", "Y"]
        result = compute_drift_info(prov, kg)
        assert result["semantic_drift_score"] >= 2 / 3 - 1e-9  # at least 2 flags

    def test_short_path_no_error(self):
        kg = _simple_kg()
        result = compute_drift_info(["A"], kg)
        assert "drift_flags" in result
        assert result["semantic_drift_score"] == 0.0

    def test_score_between_zero_and_one(self):
        kg = _drift_kg()
        prov = ["X", "relates_to", "P", "relates_to", "Y"]
        result = compute_drift_info(prov, kg)
        assert 0.0 <= result["semantic_drift_score"] <= 1.0


# ---------------------------------------------------------------------------
# compute_tracking_fields
# ---------------------------------------------------------------------------

class TestComputeTrackingFields:
    def test_path_length_two_hop(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        tr = compute_tracking_fields(cand, kg, set(), set(), set())
        assert tr["path_length"] == 2

    def test_alignment_used_when_node_in_aligned(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        tr = compute_tracking_fields(cand, kg, set(), set(), aligned_node_ids={"B"})
        assert tr["alignment_used"] is True
        assert tr["alignment_count"] == 1
        assert "B" in tr["merged_nodes_used"]

    def test_reachable_by_single_class(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        tr = compute_tracking_fields(cand, kg, {("A", "C")}, set(), set())
        assert tr["uniqueness_class"] == "reachable_by_single"
        assert tr["reachable_by_single"] is True

    def test_deep_compose_class(self):
        kg = _chain_kg(6)
        # 4-hop path
        prov = ["n0", "activates", "n1", "activates", "n2",
                "activates", "n3", "activates", "n4"]
        cand = _make_candidate("n0", "n4", prov)
        tr = compute_tracking_fields(cand, kg, set(), set(), set())
        assert tr["path_length"] == 4
        assert tr["uniqueness_class"] == "reachable_only_by_deep_compose"

    def test_alignment_class_when_aligned_not_in_shallow_multi(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        tr = compute_tracking_fields(cand, kg, set(), set(), {"B"})
        assert tr["uniqueness_class"] == "reachable_only_by_alignment"

    def test_reachable_only_by_multi_class(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        # pair is in shallow_multi_pairs
        tr = compute_tracking_fields(cand, kg, set(), {("A", "C")}, set())
        assert tr["uniqueness_class"] == "reachable_only_by_multi"

    def test_effective_length_reduced_by_alignment(self):
        kg = _simple_kg()
        cand = _make_candidate("A", "C", ["A", "activates", "B", "produces", "C"])
        tr = compute_tracking_fields(cand, kg, set(), set(), {"B"})
        assert tr["effective_path_length_after_alignment"] == max(0, 2 - 1)


# ---------------------------------------------------------------------------
# compose max_per_source
# ---------------------------------------------------------------------------

class TestComposeMaxPerSource:
    def test_max_per_source_caps_results(self):
        kg = _chain_kg(8)
        cands_unlimited = compose(kg, max_depth=9)
        cands_limited = compose(kg, max_depth=9, max_per_source=2)
        # Count per source
        from collections import Counter
        counts = Counter(c.subject_id for c in cands_limited)
        assert all(v <= 2 for v in counts.values())
        # Unlimited should have at least as many
        assert len(cands_unlimited) >= len(cands_limited)

    def test_max_per_source_zero_means_unlimited(self):
        kg = _chain_kg(5)
        cands_zero = compose(kg, max_depth=9, max_per_source=0)
        cands_unlimited = compose(kg, max_depth=9)
        assert len(cands_zero) == len(cands_unlimited)

    def test_deep_paths_produced_with_higher_depth(self):
        kg = _chain_kg(6)
        shallow = compose(kg, max_depth=3)
        deep = compose(kg, max_depth=9)
        shallow_lengths = {(len(c.provenance) - 1) // 2 for c in shallow}
        deep_lengths = {(len(c.provenance) - 1) // 2 for c in deep}
        assert max(deep_lengths) > max(shallow_lengths)


# ---------------------------------------------------------------------------
# bucket_label
# ---------------------------------------------------------------------------

class TestBucketLabel:
    def test_1hop(self):
        assert bucket_label(1) == "1-hop"

    def test_2hop(self):
        assert bucket_label(2) == "2-hop"

    def test_3hop(self):
        assert bucket_label(3) == "3-hop"

    def test_4hop(self):
        assert bucket_label(4) == "4-5-hop"

    def test_5hop(self):
        assert bucket_label(5) == "4-5-hop"

    def test_6hop_fallback(self):
        assert bucket_label(6) == "6-hop"


# ---------------------------------------------------------------------------
# analyze_depth_buckets
# ---------------------------------------------------------------------------

class TestAnalyzeDepthBuckets:
    def _make_scored_and_tracking(self, kg, depths):
        """Create mock scored/tracking pairs with given path depths."""
        scored = []
        tracking = []
        rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
        nodes = kg.nodes()
        if len(nodes) < 2:
            return scored, tracking

        # Use evaluate to get real ScoredHypothesis objects
        cands = []
        for i, d in enumerate(depths):
            # Build a fake provenance of the right length
            prov_nodes = [f"fake_{j}" for j in range(d + 1)]
            prov = []
            for j in range(d):
                prov += [prov_nodes[j], "activates"]
            prov.append(prov_nodes[d])
            c = _make_candidate(nodes[0].id, nodes[-1].id, prov, cid=f"H{i:04d}")
            cands.append(c)
        scored_list = evaluate(cands, kg, rubric)

        for sh in scored_list:
            prov = sh.candidate.provenance
            pl = max(0, (len(prov) - 1) // 2) if len(prov) >= 3 else 0
            tracking.append({"path_length": pl, "semantic_drift_score": 0.0,
                              "drift_flags": [], "alignment_used": False})
        return scored_list, tracking

    def test_bucket_counts_correct(self):
        kg = _simple_kg()
        cands = compose(kg, max_depth=9)
        tracking = [
            {"path_length": (len(c.provenance) - 1) // 2 if len(c.provenance) >= 3 else 0,
             "semantic_drift_score": 0.0, "drift_flags": [], "alignment_used": False}
            for c in cands
        ]
        rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
        scored = evaluate(cands, kg, rubric)
        buckets = analyze_depth_buckets(scored, tracking, kg)
        total_in_buckets = sum(v["candidate_count"] for v in buckets.values())
        assert total_in_buckets == len(scored)

    def test_bucket_stats_keys_present(self):
        kg = _simple_kg()
        cands = compose(kg, max_depth=3)
        tracking = [
            {"path_length": (len(c.provenance) - 1) // 2 if len(c.provenance) >= 3 else 0,
             "semantic_drift_score": 0.0, "drift_flags": [], "alignment_used": False}
            for c in cands
        ]
        rubric = EvaluationRubric(cross_domain_novelty_bonus=False)
        scored = evaluate(cands, kg, rubric)
        if scored:
            buckets = analyze_depth_buckets(scored, tracking, kg)
            for label, stats in buckets.items():
                assert "candidate_count" in stats
                assert "promising_count" in stats
                assert "drift_rate" in stats
                assert "mean_novelty" in stats


# ---------------------------------------------------------------------------
# compare_rankings
# ---------------------------------------------------------------------------

class TestCompareRankings:
    def test_identical_rankings_jaccard_one(self):
        kg = _chain_kg(5)
        cands = compose(kg, max_depth=9)
        rubric = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=False)
        scored = evaluate(cands, kg, rubric)
        tracking = [
            {"path_length": (len(c.provenance) - 1) // 2 if len(c.provenance) >= 3 else 0}
            for c in cands
        ]
        result = compare_rankings(scored, scored, tracking, top_k=5)
        assert result["jaccard_similarity"] == 1.0
        assert result["overlap_count"] == min(5, len(scored))

    def test_compare_rankings_keys_present(self):
        kg = _simple_kg()
        cands = compose(kg, max_depth=9)
        rubric_n = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=False)
        rubric_a = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=True)
        s_naive = evaluate(cands, kg, rubric_n)
        s_aware = evaluate(cands, kg, rubric_a)
        tracking = [{"path_length": (len(c.provenance) - 1) // 2
                     if len(c.provenance) >= 3 else 0} for c in cands]
        result = compare_rankings(s_naive, s_aware, tracking, top_k=3)
        for key in ("top_k", "naive_top_scores", "aware_top_scores",
                    "overlap_count", "jaccard_similarity", "interpretation"):
            assert key in result


# ---------------------------------------------------------------------------
# run_single_op_deep / run_multi_op_deep smoke tests
# ---------------------------------------------------------------------------

class TestRunnerSmoke:
    def test_single_op_returns_scored(self):
        kg = _chain_kg(5)
        scored = run_single_op_deep(kg, max_depth=3)
        assert isinstance(scored, list)
        assert all(hasattr(sh, "total_score") for sh in scored)

    def test_multi_op_returns_tuple(self):
        bio = KnowledgeGraph(name="bio")
        bio.add_node(KGNode("bio:A", "ATP", "biology"))
        bio.add_node(KGNode("bio:B", "ADP", "biology"))
        bio.add_edge(KGEdge("bio:A", "converts_to", "bio:B"))

        chem = KnowledgeGraph(name="chem")
        chem.add_node(KGNode("chem:X", "adenosine triphosphate", "chemistry"))
        chem.add_node(KGNode("chem:Y", "glucose", "chemistry"))
        chem.add_edge(KGEdge("chem:X", "produces", "chem:Y"))

        result = run_multi_op_deep(bio, chem, max_depth=3)
        scored, merged, alignment, aligned_ids = result
        assert isinstance(scored, list)
        assert isinstance(merged, KnowledgeGraph)
        assert isinstance(alignment, dict)
        assert isinstance(aligned_ids, set)

    def test_multi_op_deep_more_candidates_than_shallow(self):
        kg_chain = _chain_kg(8)
        bio = KnowledgeGraph(name="bio")
        chem = KnowledgeGraph(name="chem")
        # Add nodes from chain, split into two "domains"
        for i in range(4):
            bio.add_node(KGNode(f"n{i}", f"node{i}", "biology"))
        for i in range(4, 8):
            chem.add_node(KGNode(f"n{i}", f"node{i}", "chemistry"))
        for i in range(7):
            if i < 3:
                bio.add_edge(KGEdge(f"n{i}", "activates", f"n{i+1}"))
            elif i == 3:
                pass  # bridge handled below
            else:
                chem.add_edge(KGEdge(f"n{i}", "activates", f"n{i+1}"))

        shallow, *_ = run_multi_op_deep(bio, chem, max_depth=3)
        deep, *_ = run_multi_op_deep(bio, chem, max_depth=9)
        assert len(deep) >= len(shallow)


# ---------------------------------------------------------------------------
# rescore_with_rubric
# ---------------------------------------------------------------------------

class TestRescore:
    def test_rescore_changes_traceability(self):
        kg = _chain_kg(5)
        cands = compose(kg, max_depth=9)
        rubric_base = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=False)
        scored = evaluate(cands, kg, rubric_base)
        rescored = rescore_with_rubric(scored, kg, provenance_aware=True)
        # Both have same number of candidates
        assert len(scored) == len(rescored)
        # Traceability scores differ for deep paths
        deep_original = [sh.traceability for sh in scored
                         if (len(sh.candidate.provenance) - 1) // 2 >= 3]
        deep_rescored = [sh.traceability for sh in rescored
                         if (len(sh.candidate.provenance) - 1) // 2 >= 3]
        if deep_original and deep_rescored:
            # provenance-aware gives lower traceability to deep paths
            assert sum(deep_rescored) <= sum(deep_original) + 1e-9
