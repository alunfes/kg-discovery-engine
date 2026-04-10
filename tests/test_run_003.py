"""Tests for Run 003 additions: H2 noise robustness, H4 provenance-aware, toy data extensions."""

from __future__ import annotations

import pytest

from src.kg.models import KGEdge, KGNode, KnowledgeGraph
from src.kg.toy_data import (
    build_bio_chem_bridge_kg,
    build_biology_kg,
    build_noisy_kg,
)
from src.pipeline.operators import align, compose, union
from src.pipeline.run_experiment import (
    evaluate_h3,
    run_condition_c2_bridge,
    run_h2_noise_robustness,
    run_h4_provenance_aware,
)


class TestBiochemBridgeKG:
    def test_bridge_kg_has_cross_domain_nodes(self):
        kg = build_bio_chem_bridge_kg()
        domains = {n.domain for n in kg.nodes()}
        assert "biology" in domains
        assert "chemistry" in domains

    def test_bridge_kg_has_cross_domain_edges(self):
        """At least one edge must connect a bio node to a chem node."""
        kg = build_bio_chem_bridge_kg()
        cross = [
            e for e in kg.edges()
            if (
                kg.get_node(e.source_id)
                and kg.get_node(e.target_id)
                and kg.get_node(e.source_id).domain != kg.get_node(e.target_id).domain
            )
        ]
        assert len(cross) >= 5, f"Expected ≥5 cross-domain edges, got {len(cross)}"

    def test_bridge_kg_compose_produces_cross_domain_hypotheses(self):
        kg = build_bio_chem_bridge_kg()
        candidates = compose(kg)
        cross = [
            c for c in candidates
            if kg.get_node(c.subject_id) and kg.get_node(c.object_id)
            and kg.get_node(c.subject_id).domain != kg.get_node(c.object_id).domain
        ]
        assert len(cross) >= 5, f"Expected ≥5 cross-domain hypotheses, got {len(cross)}"

    def test_c2_bridge_generates_more_candidates_than_c1(self):
        bridge_results = run_condition_c2_bridge()
        from src.pipeline.run_experiment import run_condition_c1
        c1_results = run_condition_c1()
        assert len(bridge_results) > len(c1_results)


class TestNoisyKG:
    def test_noisy_kg_removes_edges(self):
        clean = build_biology_kg()
        noisy_30 = build_noisy_kg(noise_rate=0.30, seed=42)
        noisy_50 = build_noisy_kg(noise_rate=0.50, seed=42)
        assert len(list(noisy_30.edges())) < len(list(clean.edges()))
        assert len(list(noisy_50.edges())) < len(list(noisy_30.edges()))

    def test_noisy_kg_preserves_nodes(self):
        """Edge removal should not remove nodes."""
        clean = build_biology_kg()
        noisy = build_noisy_kg(noise_rate=0.50, seed=42)
        assert len(list(noisy.nodes())) == len(list(clean.nodes()))

    def test_noisy_kg_is_deterministic(self):
        kg1 = build_noisy_kg(noise_rate=0.30, seed=42)
        kg2 = build_noisy_kg(noise_rate=0.30, seed=42)
        e1 = {(e.source_id, e.relation, e.target_id) for e in kg1.edges()}
        e2 = {(e.source_id, e.relation, e.target_id) for e in kg2.edges()}
        assert e1 == e2

    def test_noisy_kg_different_seeds_differ(self):
        kg1 = build_noisy_kg(noise_rate=0.50, seed=42)
        kg2 = build_noisy_kg(noise_rate=0.50, seed=99)
        e1 = {(e.source_id, e.relation, e.target_id) for e in kg1.edges()}
        e2 = {(e.source_id, e.relation, e.target_id) for e in kg2.edges()}
        assert e1 != e2


class TestH2NoiseRobustness:
    def test_h2_returns_required_keys(self):
        result = run_h2_noise_robustness()
        assert "clean_mean_total" in result
        assert "noise_levels" in result
        assert "pass" in result

    def test_h2_has_two_noise_levels(self):
        result = run_h2_noise_robustness()
        assert "noise_30pct" in result["noise_levels"]
        assert "noise_50pct" in result["noise_levels"]

    def test_h2_passes(self):
        """Evaluator should absorb noise: degradation < 20%."""
        result = run_h2_noise_robustness()
        assert result["pass"] is True, (
            f"H2 should PASS but worst degradation = {result['worst_degradation_ratio']:.3f}"
        )

    def test_h2_degradation_under_threshold(self):
        result = run_h2_noise_robustness()
        for label, stats in result["noise_levels"].items():
            assert stats["degradation_ratio"] < result["threshold"], (
                f"{label}: degradation {stats['degradation_ratio']:.3f} ≥ threshold {result['threshold']}"
            )


class TestH3HypothesisLevel:
    def test_evaluate_h3_returns_required_keys(self):
        from src.pipeline.run_experiment import run_condition_c2
        from src.kg.toy_data import get_all_toy_kgs
        from src.pipeline.operators import align, union

        kgs = get_all_toy_kgs()
        alignment = align(kgs["biology"], kgs["chemistry"], threshold=0.4)
        merged = union(kgs["biology"], kgs["chemistry"], alignment, name="merged")
        c2 = run_condition_c2()
        result = evaluate_h3(c2, merged)

        assert "cross_domain_novelty" in result
        assert "same_domain_novelty" in result
        assert "ratio" in result
        assert "pass" in result

    def test_h3_passes(self):
        """Cross-domain hypotheses should have higher novelty (ratio ≥ 1.20)."""
        from src.pipeline.run_experiment import run_condition_c2
        from src.kg.toy_data import get_all_toy_kgs
        from src.pipeline.operators import align, union

        kgs = get_all_toy_kgs()
        alignment = align(kgs["biology"], kgs["chemistry"], threshold=0.4)
        merged = union(kgs["biology"], kgs["chemistry"], alignment, name="merged")
        c2 = run_condition_c2()
        result = evaluate_h3(c2, merged)

        assert result["cross_domain_count"] > 0, "Expected cross-domain hypotheses"
        assert result["same_domain_count"] > 0, "Expected same-domain hypotheses"
        assert result["pass"] is True, (
            f"H3 should PASS: cross={result['cross_domain_novelty']:.3f} "
            f"same={result['same_domain_novelty']:.3f} "
            f"ratio={result['ratio']:.3f}"
        )


class TestH4ProvenanceAware:
    def test_h4_returns_required_keys(self):
        result = run_h4_provenance_aware()
        assert "candidate_count" in result
        assert "spearman_naive" in result
        assert "spearman_aware" in result
        assert "pass" in result

    def test_h4_scores_in_valid_range(self):
        result = run_h4_provenance_aware()
        assert 0.0 <= result["naive_mean_traceability"] <= 1.0
        assert 0.0 <= result["aware_mean_traceability"] <= 1.0
        assert -1.0 <= result["spearman_naive"] <= 1.0
        assert -1.0 <= result["spearman_aware"] <= 1.0

    def test_h4_framework_runs_without_error(self):
        """H4 framework should produce results even if H4 doesn't pass yet."""
        result = run_h4_provenance_aware()
        assert result["candidate_count"] > 0


class TestExpandedBiologyKG:
    def test_expanded_biology_has_more_nodes(self):
        kg = build_biology_kg()
        assert len(list(kg.nodes())) >= 12

    def test_expanded_biology_has_more_edges(self):
        kg = build_biology_kg()
        assert len(list(kg.edges())) >= 14

    def test_expanded_biology_compose_generates_more_candidates(self):
        """Expanded KG should generate more hypotheses than Run 002 (8 nodes → 8 cands)."""
        kg = build_biology_kg()
        candidates = compose(kg)
        assert len(candidates) > 8, f"Expected >8 candidates, got {len(candidates)}"
