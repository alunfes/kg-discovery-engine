"""Tests for Run 004 additions: mixed_hop_kg, compose_cross_domain, H4 mixed test."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kg.toy_data import build_mixed_hop_kg
from src.pipeline.operators import compose, compose_cross_domain
from src.pipeline.run_experiment import (
    run_condition_c2_xdomain,
    run_h4_mixed_hop,
)


class TestMixedHopKG:
    """Tests for build_mixed_hop_kg()."""

    def test_node_count(self):
        kg = build_mixed_hop_kg()
        assert len(kg.nodes()) == 6

    def test_edge_count(self):
        kg = build_mixed_hop_kg()
        assert len(kg.edges()) == 5

    def test_two_domains(self):
        kg = build_mixed_hop_kg()
        domains = {n.domain for n in kg.nodes()}
        assert "bio" in domains
        assert "chem" in domains

    def test_three_bio_nodes(self):
        kg = build_mixed_hop_kg()
        bio_nodes = [n for n in kg.nodes() if n.domain == "bio"]
        assert len(bio_nodes) == 3

    def test_three_chem_nodes(self):
        kg = build_mixed_hop_kg()
        chem_nodes = [n for n in kg.nodes() if n.domain == "chem"]
        assert len(chem_nodes) == 3

    def test_cross_domain_bridge_edge(self):
        """mhk:C (bio) catalyzes mhk:X (chem) must exist."""
        kg = build_mixed_hop_kg()
        assert kg.has_direct_edge("mhk:C", "mhk:X")

    def test_no_direct_a_to_x(self):
        """No shortcut: mhk:A→mhk:X must not exist as a direct edge."""
        kg = build_mixed_hop_kg()
        assert not kg.has_direct_edge("mhk:A", "mhk:X")

    def test_compose_generates_both_hop_depths(self):
        """compose(max_depth=5) must produce both 2-hop and 3-hop candidates."""
        from src.pipeline.run_experiment import _provenance_hop_count
        kg = build_mixed_hop_kg()
        candidates = compose(kg, max_depth=5)
        hops = {_provenance_hop_count(c) for c in candidates}
        assert 2 in hops, "Expected at least one 2-hop hypothesis"
        assert 3 in hops, "Expected at least one 3-hop hypothesis"

    def test_compose_total_candidates(self):
        """Expect 7 hypotheses (4 two-hop + 3 three-hop)."""
        kg = build_mixed_hop_kg()
        candidates = compose(kg, max_depth=5)
        assert len(candidates) == 7

    def test_compose_default_depth_gives_2hop_only(self):
        """With default max_depth=3, only 2-hop paths are reachable."""
        from src.pipeline.run_experiment import _provenance_hop_count
        kg = build_mixed_hop_kg()
        candidates = compose(kg)  # default max_depth=3
        hops = {_provenance_hop_count(c) for c in candidates}
        assert 2 in hops
        assert 3 not in hops, "Default max_depth=3 should not reach 3-hop paths"


class TestComposeCrossDomain:
    """Tests for compose_cross_domain()."""

    def test_only_cross_domain_candidates(self):
        """All returned candidates must have subject.domain != object.domain."""
        from src.kg.toy_data import build_biology_kg, build_chemistry_kg
        from src.pipeline.operators import align, union
        kg1, kg2 = build_biology_kg(), build_chemistry_kg()
        alignment = align(kg1, kg2, threshold=0.4)
        merged = union(kg1, kg2, alignment, name="test_union")
        candidates = compose_cross_domain(merged)
        for c in candidates:
            src = merged.get_node(c.subject_id)
            tgt = merged.get_node(c.object_id)
            if src and tgt:
                assert src.domain != tgt.domain, (
                    f"Same-domain candidate slipped through: {c.subject_id} ({src.domain}) "
                    f"-> {c.object_id} ({tgt.domain})"
                )

    def test_fewer_or_equal_candidates_than_compose(self):
        """compose_cross_domain returns ≤ compose candidates."""
        from src.kg.toy_data import build_biology_kg, build_chemistry_kg
        from src.pipeline.operators import align, union
        kg1, kg2 = build_biology_kg(), build_chemistry_kg()
        alignment = align(kg1, kg2, threshold=0.4)
        merged = union(kg1, kg2, alignment, name="test_union")
        all_cands = compose(merged)
        xd_cands = compose_cross_domain(merged)
        assert len(xd_cands) <= len(all_cands)

    def test_at_least_one_cross_domain_candidate(self):
        """Merged bio+chem KG must yield some cross-domain candidates."""
        from src.kg.toy_data import build_biology_kg, build_chemistry_kg
        from src.pipeline.operators import align, union
        kg1, kg2 = build_biology_kg(), build_chemistry_kg()
        alignment = align(kg1, kg2, threshold=0.4)
        merged = union(kg1, kg2, alignment, name="test_union")
        xd_cands = compose_cross_domain(merged)
        assert len(xd_cands) > 0

    def test_on_single_domain_kg_returns_empty(self):
        """compose_cross_domain on a single-domain KG should return no candidates."""
        from src.kg.toy_data import build_biology_kg
        kg = build_biology_kg()
        cands = compose_cross_domain(kg)
        assert len(cands) == 0


class TestRunConditionC2Xdomain:
    """Tests for run_condition_c2_xdomain()."""

    def test_returns_list(self):
        results = run_condition_c2_xdomain()
        assert isinstance(results, list)

    def test_all_novelty_1(self):
        """All returned candidates are cross-domain → novelty=1.0."""
        results = run_condition_c2_xdomain()
        for s in results:
            assert s.novelty == 1.0, f"Non-cross-domain candidate: {s.candidate.subject_id}"

    def test_mean_total_higher_than_c1(self):
        """C2_xdomain mean total must exceed C1 mean total (cross-domain selection effect)."""
        from src.pipeline.run_experiment import run_condition_c1, summarize
        c1 = run_condition_c1()
        c2_xd = run_condition_c2_xdomain()
        c1_mean = sum(s.total_score for s in c1) / len(c1)
        c2_xd_mean = sum(s.total_score for s in c2_xd) / len(c2_xd)
        assert c2_xd_mean > c1_mean, (
            f"Expected C2_xdomain ({c2_xd_mean:.4f}) > C1 ({c1_mean:.4f})"
        )


class TestH4MixedHop:
    """Tests for run_h4_mixed_hop()."""

    def test_required_keys(self):
        result = run_h4_mixed_hop()
        required = {
            "candidate_count", "hop_distribution", "naive_mean_traceability",
            "aware_mean_traceability", "spearman_naive", "spearman_aware",
            "gold_proxy", "pass",
        }
        assert required <= set(result.keys())

    def test_has_both_hop_depths(self):
        result = run_h4_mixed_hop()
        hop_dist = result["hop_distribution"]
        assert 2 in hop_dist, "Should have 2-hop hypotheses"
        assert 3 in hop_dist, "Should have 3-hop hypotheses"

    def test_aware_traceability_lower_than_naive(self):
        """aware mode should penalize 3-hop hypotheses, lowering mean traceability."""
        result = run_h4_mixed_hop()
        assert result["aware_mean_traceability"] < result["naive_mean_traceability"], (
            "Aware traceability should be lower (3-hop penalized)"
        )

    def test_spearman_values_in_range(self):
        result = run_h4_mixed_hop()
        assert -1.0 <= result["spearman_naive"] <= 1.0
        assert -1.0 <= result["spearman_aware"] <= 1.0

    def test_h4_pass(self):
        """H4 must PASS on mixed-hop KG (spearman_aware > spearman_naive)."""
        result = run_h4_mixed_hop()
        assert result["pass"] is True, (
            f"H4 expected PASS: aware={result['spearman_aware']} "
            f"vs naive={result['spearman_naive']}"
        )

    def test_spearman_aware_substantially_higher(self):
        """The gap should be at least 0.5 to confirm meaningful differentiation."""
        result = run_h4_mixed_hop()
        gap = result["spearman_aware"] - result["spearman_naive"]
        assert gap >= 0.5, f"Expected Spearman gap ≥ 0.5, got {gap:.4f}"

    def test_gold_proxy_uses_hop_first(self):
        """Confirm the new gold standard uses hop_count first."""
        result = run_h4_mixed_hop()
        assert "hop_count_asc" in result["gold_proxy"]
