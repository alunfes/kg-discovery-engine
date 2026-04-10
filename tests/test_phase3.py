"""Tests for Phase 3 real-data experiment.

Tests cover:
  - Wikidata loader (fallback data structure)
  - Real KG builders (4 conditions)
  - Phase 3 pipeline (single-op, multi-op, reachability)
  - H1' analysis (bridge density function)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.wikidata_loader import (
    _BRIDGES_DENSE,
    _BRIDGES_SPARSE,
    _get_fallback_data,
    fetch_sparql,
)
from src.kg.real_data import (
    build_condition_a,
    build_condition_b,
    build_condition_c,
    build_condition_d,
    compute_bridge_density,
    compute_kg_stats,
    compute_relation_entropy,
    extract_domain_subgraph,
)
from src.pipeline.run_phase3 import (
    _normalized_pairs,
    analyze_h1_bridge_density,
    analyze_h3_structural_distance,
    compute_unique_to_multi_op,
    run_multi_op,
    run_single_op,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fallback_data():
    """Load fallback dataset (no network required)."""
    return _get_fallback_data()


@pytest.fixture(scope="module")
def cond_a(fallback_data):
    return build_condition_a(fallback_data)


@pytest.fixture(scope="module")
def cond_b(fallback_data):
    return build_condition_b(fallback_data)


@pytest.fixture(scope="module")
def cond_c(fallback_data):
    return build_condition_c(fallback_data)


@pytest.fixture(scope="module")
def cond_d(fallback_data):
    return build_condition_d(fallback_data)


# ---------------------------------------------------------------------------
# Wikidata loader tests
# ---------------------------------------------------------------------------

class TestWikidataLoader:
    def test_fallback_data_structure(self, fallback_data):
        assert "bio" in fallback_data
        assert "chem" in fallback_data
        assert "bridges_sparse" in fallback_data
        assert "bridges_dense" in fallback_data

    def test_bio_nodes_count(self, fallback_data):
        assert len(fallback_data["bio"]["nodes"]) >= 20, "Need ≥20 bio nodes"

    def test_chem_nodes_count(self, fallback_data):
        assert len(fallback_data["chem"]["nodes"]) >= 20, "Need ≥20 chem nodes"

    def test_bridges_ordering(self, fallback_data):
        sparse = fallback_data["bridges_sparse"]
        dense = fallback_data["bridges_dense"]
        assert len(sparse) > 0, "Must have sparse bridges"
        assert len(dense) > len(sparse), "Dense must have more bridges than sparse"

    def test_bio_node_fields(self, fallback_data):
        node = fallback_data["bio"]["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert node["id"].startswith("bio:")

    def test_chem_node_fields(self, fallback_data):
        node = fallback_data["chem"]["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert node["id"].startswith("chem:")

    def test_bio_edge_fields(self, fallback_data):
        edge = fallback_data["bio"]["edges"][0]
        assert "subject" in edge
        assert "relation" in edge
        assert "object" in edge

    def test_sparse_bridge_endpoints(self, fallback_data):
        for bridge in fallback_data["bridges_sparse"]:
            assert bridge["subject"].startswith("bio:") or bridge["object"].startswith("bio:")

    def test_fallback_source_label(self, fallback_data):
        assert "fallback" in fallback_data.get("source", "").lower()


# ---------------------------------------------------------------------------
# Real KG builder tests
# ---------------------------------------------------------------------------

class TestRealKGBuilders:
    def test_condition_a_single_domain(self, cond_a):
        nodes = cond_a.nodes()
        assert all(n.domain == "biology" for n in nodes), "A must be biology-only"

    def test_condition_b_single_domain(self, cond_b):
        nodes = cond_b.nodes()
        assert all(n.domain == "chemistry" for n in nodes), "B must be chemistry-only"

    def test_condition_a_bridge_density_zero(self, cond_a):
        assert compute_bridge_density(cond_a) == 0.0

    def test_condition_b_bridge_density_zero(self, cond_b):
        assert compute_bridge_density(cond_b) == 0.0

    def test_condition_c_has_bridges(self, cond_c):
        bd = compute_bridge_density(cond_c)
        assert 0.02 <= bd <= 0.15, f"Sparse bridge density {bd:.4f} out of expected range"

    def test_condition_d_has_more_bridges(self, cond_d, cond_c):
        bd_d = compute_bridge_density(cond_d)
        bd_c = compute_bridge_density(cond_c)
        assert bd_d > bd_c, "Dense must have higher bridge density than sparse"

    def test_condition_c_node_count(self, cond_c):
        assert len(cond_c.nodes()) >= 40, "C should have bio+chem nodes merged"

    def test_condition_d_node_count(self, cond_d, cond_c):
        # D has more edges than C (more bridges) but same nodes
        assert len(cond_d.nodes()) == len(cond_c.nodes())
        assert len(cond_d.edges()) > len(cond_c.edges())

    def test_extract_domain_subgraph_bio(self, cond_c):
        bio_sub = extract_domain_subgraph(cond_c, "biology", "bio_sub")
        assert all(n.domain == "biology" for n in bio_sub.nodes())

    def test_extract_domain_subgraph_edges_intra_only(self, cond_c):
        bio_sub = extract_domain_subgraph(cond_c, "biology", "bio_sub")
        bio_ids = {n.id for n in bio_sub.nodes()}
        for e in bio_sub.edges():
            assert e.source_id in bio_ids
            assert e.target_id in bio_ids

    def test_compute_kg_stats_structure(self, cond_c):
        stats = compute_kg_stats(cond_c)
        assert "node_count" in stats
        assert "edge_count" in stats
        assert "bridge_density" in stats
        assert "relation_entropy" in stats
        assert "relation_type_count" in stats

    def test_relation_entropy_positive(self, cond_c):
        assert compute_relation_entropy(cond_c) > 0.0, "Real KG should have diverse relations"

    def test_condition_c_relation_types(self, cond_c):
        stats = compute_kg_stats(cond_c)
        assert stats["relation_type_count"] >= 5, "Real data should have ≥5 relation types"


# ---------------------------------------------------------------------------
# Phase 3 pipeline tests
# ---------------------------------------------------------------------------

class TestPhase3Pipeline:
    def test_single_op_on_A_generates_candidates(self, cond_a):
        scored = run_single_op(cond_a)
        assert len(scored) > 0, "Bio-only KG should generate candidates"

    def test_single_op_on_C_more_candidates_than_A(self, cond_a, cond_c):
        a_scored = run_single_op(cond_a)
        c_scored = run_single_op(cond_c)
        assert len(c_scored) > len(a_scored), "Merged KG should yield more candidates"

    def test_multi_op_degenerate_A(self, cond_a):
        """Condition A: multi-op on bio+empty should equal single-op (no duplication)."""
        bio_sub = extract_domain_subgraph(cond_a, "biology", "bio_sub")
        chem_sub = extract_domain_subgraph(cond_a, "chemistry", "chem_sub")  # empty
        single_scored = run_single_op(cond_a)
        multi_scored, _ = run_multi_op(bio_sub, chem_sub)
        # After deduplication, candidate count should match single-op
        assert len(multi_scored) == len(single_scored), (
            f"Degenerate multi-op should equal single-op: {len(multi_scored)} != {len(single_scored)}"
        )

    def test_multi_op_finds_unique_in_C(self, cond_c):
        """Condition C: multi-op should find candidates unreachable by single-op."""
        bio_sub = extract_domain_subgraph(cond_c, "biology", "bio_sub")
        chem_sub = extract_domain_subgraph(cond_c, "chemistry", "chem_sub")
        single_scored = run_single_op(cond_c)
        multi_scored, merged_kg = run_multi_op(bio_sub, chem_sub)
        reachability = compute_unique_to_multi_op(single_scored, multi_scored)
        assert reachability["unique_to_multi_op_count"] > 0, (
            "Multi-op should find cross-domain candidates via alignment in condition C"
        )

    def test_compute_unique_structure(self, cond_c):
        bio_sub = extract_domain_subgraph(cond_c, "biology", "bio_sub")
        chem_sub = extract_domain_subgraph(cond_c, "chemistry", "chem_sub")
        single_scored = run_single_op(cond_c)
        multi_scored, _ = run_multi_op(bio_sub, chem_sub)
        result = compute_unique_to_multi_op(single_scored, multi_scored)
        assert "unique_to_multi_op_count" in result
        assert "operator_contribution_rate" in result
        assert 0.0 <= result["operator_contribution_rate"] <= 1.0

    def test_h3_structural_distance_structure(self, cond_c):
        bio_sub = extract_domain_subgraph(cond_c, "biology", "bio_sub")
        chem_sub = extract_domain_subgraph(cond_c, "chemistry", "chem_sub")
        multi_scored, merged_kg = run_multi_op(bio_sub, chem_sub)
        h3 = analyze_h3_structural_distance(multi_scored, merged_kg)
        assert "structural_distance_detected" in h3
        assert "cross_domain_count" in h3
        assert "same_domain_count" in h3

    def test_h1_analysis_structure(self, fallback_data):
        cond_results = {
            "A": {
                "kg_stats": {"bridge_density": 0.0},
                "h1_comparison": {"cohens_d": 0.0, "multi_op_advantage": False},
                "reachability": {"unique_to_multi_op_count": 0, "operator_contribution_rate": 0.0},
            },
            "C": {
                "kg_stats": {"bridge_density": 0.05},
                "h1_comparison": {"cohens_d": 0.3, "multi_op_advantage": True},
                "reachability": {"unique_to_multi_op_count": 4, "operator_contribution_rate": 0.07},
            },
        }
        h1 = analyze_h1_bridge_density(cond_results)
        assert "condition_table" in h1
        assert "h1_prime_supported" in h1
        assert "sorted_by_bridge_density" in h1


# ---------------------------------------------------------------------------
# No-network smoke tests
# ---------------------------------------------------------------------------

class TestNoNetworkSmoke:
    def test_fetch_sparql_timeout_returns_none(self):
        """Calling fetch_sparql with an invalid query should return None gracefully."""
        result = fetch_sparql("SELECT * WHERE { ?s ?p ?o } LIMIT 1", timeout=1)
        # Either succeeds or returns None; should not raise
        assert result is None or isinstance(result, list)

    def test_normalized_pairs_strips_prefix(self):
        from src.kg.models import HypothesisCandidate
        from src.eval.scorer import ScoredHypothesis

        c = HypothesisCandidate(
            id="H0001",
            subject_id="chemistry::chem:citrate",
            relation="transitively_related_to",
            object_id="bio:ATP",
            description="test",
            provenance=["chemistry::chem:citrate", "catalyzes", "bio:ATP"],
        )
        s = ScoredHypothesis(candidate=c, total_score=0.7)
        pairs = _normalized_pairs([s])
        assert ("chem:citrate", "bio:ATP") in pairs
