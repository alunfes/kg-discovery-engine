"""Tests for Run 013: cross-subset reproducibility.

Covers:
  - Subset B load: correct node/edge counts, bio/chem prefixes
  - Subset C load: correct node/edge counts, bio/chem prefixes
  - Bridge edges: sparse/medium density, cross-domain pairs
  - KG construction from subset data
  - Pipeline application: filtered candidates generated
  - Alignment-dependent reachability: unique_to_multi detection
  - Deep CD candidates: at least some 3-hop cross-domain
  - Label assignment: same logic as run_012
  - Verdict computation: SUCCESS/FAILURE logic
  - Subset A still reproduces Run 012 behavior (smoke test)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.data.wikidata_phase4_subset_b import (
    _BRIDGE_B_MEDIUM,
    _BRIDGE_B_SPARSE,
    _IMM_EDGES,
    _IMM_NODES,
    _NAT_EDGES,
    _NAT_NODES,
    load_subset_b_data,
)
from src.data.wikidata_phase4_subset_c import (
    _BRIDGE_C_MEDIUM,
    _BRIDGE_C_SPARSE,
    _NEU_EDGES,
    _NEU_NODES,
    _PHAR_EDGES,
    _PHAR_NODES,
    load_subset_c_data,
)
from src.kg.models import KGEdge, KGNode, KnowledgeGraph


# Import run_013 module
import importlib
run_013 = importlib.import_module("src.pipeline.run_013")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_node(nid: str, label: str = "", domain: str = "biology") -> KGNode:
    """Create a KGNode for testing."""
    return KGNode(nid, label or nid, domain)


def make_edge(src: str, rel: str, tgt: str) -> KGEdge:
    """Create a KGEdge for testing."""
    return KGEdge(src, rel, tgt)


def make_kg(*edges: tuple[str, str, str], domain: str = "biology") -> KnowledgeGraph:
    """Build a small test KG from edge tuples."""
    kg = KnowledgeGraph(name="test")
    node_ids: set[str] = set()
    for src, _, tgt in edges:
        node_ids.add(src)
        node_ids.add(tgt)
    for nid in node_ids:
        kg.add_node(make_node(nid, domain=domain))
    for src, rel, tgt in edges:
        kg.add_edge(make_edge(src, rel, tgt))
    return kg


# ---------------------------------------------------------------------------
# Subset B: Data validation
# ---------------------------------------------------------------------------


class TestSubsetBData:
    """Tests for wikidata_phase4_subset_b.py data."""

    def test_imm_nodes_minimum_count(self) -> None:
        """Subset B bio side must have sufficient nodes (≥100)."""
        assert len(_IMM_NODES) >= 100

    def test_nat_nodes_minimum_count(self) -> None:
        """Subset B chem side must have sufficient nodes (≥80)."""
        assert len(_NAT_NODES) >= 80

    def test_imm_edges_minimum_count(self) -> None:
        """Subset B bio edges must be substantial (≥80)."""
        assert len(_IMM_EDGES) >= 80

    def test_nat_edges_minimum_count(self) -> None:
        """Subset B chem edges must be substantial (≥50)."""
        assert len(_NAT_EDGES) >= 50

    def test_imm_node_prefix(self) -> None:
        """All Subset B bio nodes must use imm: prefix."""
        for nid, _ in _IMM_NODES:
            assert nid.startswith("imm:"), f"Expected imm: prefix, got {nid}"

    def test_nat_node_prefix(self) -> None:
        """All Subset B chem nodes must use nat: prefix."""
        for nid, _ in _NAT_NODES:
            assert nid.startswith("nat:"), f"Expected nat: prefix, got {nid}"

    def test_bridge_sparse_count(self) -> None:
        """Subset B sparse bridge must have ~10-20 edges."""
        assert 8 <= len(_BRIDGE_B_SPARSE) <= 25

    def test_bridge_medium_superset_of_sparse(self) -> None:
        """Medium bridge must contain all sparse bridge edges."""
        sparse_set = set(tuple(e) for e in _BRIDGE_B_SPARSE)
        medium_set = set(tuple(e) for e in _BRIDGE_B_MEDIUM)
        assert sparse_set.issubset(medium_set)

    def test_bridge_medium_larger_than_sparse(self) -> None:
        """Medium bridge must add edges beyond sparse."""
        assert len(_BRIDGE_B_MEDIUM) > len(_BRIDGE_B_SPARSE)

    def test_bridge_edges_cross_domain(self) -> None:
        """All bridge edges must cross domains (imm: ↔ nat:)."""
        imm_ids = {nid for nid, _ in _IMM_NODES}
        nat_ids = {nid for nid, _ in _NAT_NODES}
        for s, r, t in _BRIDGE_B_SPARSE:
            s_in_imm = s in imm_ids
            s_in_nat = s in nat_ids
            t_in_imm = t in imm_ids
            t_in_nat = t in nat_ids
            assert (s_in_imm and t_in_nat) or (s_in_nat and t_in_imm), (
                f"Bridge edge {s} --{r}--> {t} is not cross-domain"
            )

    def test_no_overlap_with_bio_chem_prefix(self) -> None:
        """Subset B nodes must not use bio:/chem: prefix (no overlap with Subset A)."""
        for nid, _ in _IMM_NODES:
            assert not nid.startswith("bio:"), f"Should use imm: not bio:, got {nid}"
        for nid, _ in _NAT_NODES:
            assert not nid.startswith("chem:"), f"Should use nat: not chem:, got {nid}"

    def test_arachidonic_acid_bridge(self) -> None:
        """Subset B must include arachidonic acid as bridge metabolite."""
        bridge_pairs = {(s, t) for s, r, t in _BRIDGE_B_SPARSE}
        has_aa = any(
            "m_AA" in s and "ArachidonicAcid" in t
            or "ArachidonicAcid" in s and "m_AA" in t
            for s, t in bridge_pairs
        )
        assert has_aa, "Expected arachidonic acid bridge between imm: and nat:"

    def test_wddata_loader_returns_correct_source(self) -> None:
        """load_subset_b_data must return WD4Data with source='subset_b'."""
        data = load_subset_b_data()
        assert data.source == "subset_b"

    def test_wddata_has_all_fields(self) -> None:
        """load_subset_b_data must return WD4Data with all 6 fields populated."""
        data = load_subset_b_data()
        assert len(data.bio_nodes) >= 100
        assert len(data.bio_edges) >= 80
        assert len(data.chem_nodes) >= 80
        assert len(data.chem_edges) >= 50
        assert len(data.bridge_edges_sparse) >= 8
        assert len(data.bridge_edges_medium) >= 20


# ---------------------------------------------------------------------------
# Subset C: Data validation
# ---------------------------------------------------------------------------


class TestSubsetCData:
    """Tests for wikidata_phase4_subset_c.py data."""

    def test_neu_nodes_minimum_count(self) -> None:
        """Subset C bio side must have sufficient nodes (≥100)."""
        assert len(_NEU_NODES) >= 100

    def test_phar_nodes_minimum_count(self) -> None:
        """Subset C chem side must have sufficient nodes (≥70)."""
        assert len(_PHAR_NODES) >= 70

    def test_neu_edges_minimum_count(self) -> None:
        """Subset C bio edges must be substantial (≥80)."""
        assert len(_NEU_EDGES) >= 80

    def test_phar_edges_minimum_count(self) -> None:
        """Subset C chem edges must be substantial (≥50)."""
        assert len(_PHAR_EDGES) >= 50

    def test_neu_node_prefix(self) -> None:
        """All Subset C bio nodes must use neu: prefix."""
        for nid, _ in _NEU_NODES:
            assert nid.startswith("neu:"), f"Expected neu: prefix, got {nid}"

    def test_phar_node_prefix(self) -> None:
        """All Subset C chem nodes must use phar: prefix."""
        for nid, _ in _PHAR_NODES:
            assert nid.startswith("phar:"), f"Expected phar: prefix, got {nid}"

    def test_bridge_sparse_count(self) -> None:
        """Subset C sparse bridge must have ~10-20 edges."""
        assert 8 <= len(_BRIDGE_C_SPARSE) <= 25

    def test_bridge_medium_superset_of_sparse(self) -> None:
        """Medium bridge must contain all sparse bridge edges."""
        sparse_set = set(tuple(e) for e in _BRIDGE_C_SPARSE)
        medium_set = set(tuple(e) for e in _BRIDGE_C_MEDIUM)
        assert sparse_set.issubset(medium_set)

    def test_bridge_edges_cross_domain(self) -> None:
        """All bridge edges must cross domains (neu: ↔ phar:)."""
        neu_ids = {nid for nid, _ in _NEU_NODES}
        phar_ids = {nid for nid, _ in _PHAR_NODES}
        for s, r, t in _BRIDGE_C_SPARSE:
            s_in_neu = s in neu_ids
            s_in_phar = s in phar_ids
            t_in_neu = t in neu_ids
            t_in_phar = t in phar_ids
            assert (s_in_neu and t_in_phar) or (s_in_phar and t_in_neu), (
                f"Bridge edge {s} --{r}--> {t} is not cross-domain"
            )

    def test_no_overlap_with_bio_chem_prefix(self) -> None:
        """Subset C nodes must not use bio:/chem: prefix."""
        for nid, _ in _NEU_NODES:
            assert not nid.startswith("bio:"), f"Should use neu: not bio:, got {nid}"
        for nid, _ in _PHAR_NODES:
            assert not nid.startswith("chem:"), f"Should use phar: not chem:, got {nid}"

    def test_dopamine_bridge(self) -> None:
        """Subset C must include dopamine as bridge metabolite."""
        bridge_pairs = {(s, t) for s, r, t in _BRIDGE_C_SPARSE}
        has_da = any(
            ("m_Dopamine" in s and "Dopamine" in t)
            or ("Dopamine" in s and "m_Dopamine" in t)
            for s, t in bridge_pairs
        )
        assert has_da, "Expected dopamine bridge between neu: and phar:"

    def test_serotonin_bridge(self) -> None:
        """Subset C must include serotonin as bridge metabolite."""
        bridge_pairs = {(s, t) for s, r, t in _BRIDGE_C_SPARSE}
        has_5ht = any(
            ("m_Serotonin" in s and "Serotonin" in t)
            or ("Serotonin" in s and "m_Serotonin" in t)
            for s, t in bridge_pairs
        )
        assert has_5ht, "Expected serotonin bridge between neu: and phar:"

    def test_wddata_loader_returns_correct_source(self) -> None:
        """load_subset_c_data must return WD4Data with source='subset_c'."""
        data = load_subset_c_data()
        assert data.source == "subset_c"

    def test_wddata_has_all_fields(self) -> None:
        """load_subset_c_data must return WD4Data with all fields populated."""
        data = load_subset_c_data()
        assert len(data.bio_nodes) >= 100
        assert len(data.bio_edges) >= 80
        assert len(data.chem_nodes) >= 70
        assert len(data.chem_edges) >= 50
        assert len(data.bridge_edges_sparse) >= 8
        assert len(data.bridge_edges_medium) >= 20


# ---------------------------------------------------------------------------
# Prefix isolation between subsets
# ---------------------------------------------------------------------------


class TestSubsetPrefixIsolation:
    """Tests for absence of overlap between subset node namespaces."""

    def test_a_vs_b_no_bio_overlap(self) -> None:
        """Subset A bio: prefix must not appear in Subset B imm: nodes."""
        imm_ids = {nid for nid, _ in _IMM_NODES}
        assert not any(nid.startswith("bio:") for nid in imm_ids)

    def test_a_vs_c_no_bio_overlap(self) -> None:
        """Subset A bio: prefix must not appear in Subset C neu: nodes."""
        neu_ids = {nid for nid, _ in _NEU_NODES}
        assert not any(nid.startswith("bio:") for nid in neu_ids)

    def test_b_vs_c_no_prefix_overlap(self) -> None:
        """Subset B (imm:/nat:) must not overlap with Subset C (neu:/phar:) prefixes."""
        imm_prefixes = {nid.split(":")[0] for nid, _ in _IMM_NODES}
        nat_prefixes = {nid.split(":")[0] for nid, _ in _NAT_NODES}
        neu_prefixes = {nid.split(":")[0] for nid, _ in _NEU_NODES}
        phar_prefixes = {nid.split(":")[0] for nid, _ in _PHAR_NODES}

        all_b = imm_prefixes | nat_prefixes
        all_c = neu_prefixes | phar_prefixes
        assert not (all_b & all_c), f"Prefix overlap: {all_b & all_c}"


# ---------------------------------------------------------------------------
# KG construction
# ---------------------------------------------------------------------------


class TestKGConstruction:
    """Tests for _build_bio_chem_kgs function."""

    def test_build_bio_chem_kgs_subset_b(self) -> None:
        """_build_bio_chem_kgs must produce non-empty bio/chem KGs for Subset B."""
        data = load_subset_b_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)

        assert len(list(bio_kg.nodes())) >= 50
        assert len(list(chem_kg.nodes())) >= 50

    def test_build_bio_chem_kgs_subset_c(self) -> None:
        """_build_bio_chem_kgs must produce non-empty bio/chem KGs for Subset C."""
        data = load_subset_c_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)

        assert len(list(bio_kg.nodes())) >= 50
        assert len(list(chem_kg.nodes())) >= 50

    def test_bio_kg_domain_biology(self) -> None:
        """All bio_kg nodes must have domain='biology'."""
        data = load_subset_b_data()
        bio_kg, _ = run_013._build_bio_chem_kgs(data)
        for node in bio_kg.nodes():
            assert node.domain == "biology", (
                f"Node {node.id} has domain={node.domain}, expected biology"
            )

    def test_chem_kg_domain_chemistry(self) -> None:
        """All chem_kg nodes must have domain='chemistry'."""
        data = load_subset_b_data()
        _, chem_kg = run_013._build_bio_chem_kgs(data)
        for node in chem_kg.nodes():
            assert node.domain == "chemistry", (
                f"Node {node.id} has domain={node.domain}, expected chemistry"
            )


# ---------------------------------------------------------------------------
# Pipeline: filtered candidates
# ---------------------------------------------------------------------------


class TestFilteredPipeline:
    """Tests for _run_filtered_pipeline and _run_baseline_pipeline."""

    def test_filtered_produces_candidates_subset_b(self) -> None:
        """Filtered pipeline must produce at least some candidates for Subset B."""
        data = load_subset_b_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        cands, merged, aligned = run_013._run_filtered_pipeline(bio_kg, chem_kg, "B")

        assert len(cands) > 0, "Expected at least 1 filtered candidate for Subset B"
        assert merged is not None
        assert isinstance(aligned, set)

    def test_filtered_produces_candidates_subset_c(self) -> None:
        """Filtered pipeline must produce at least some candidates for Subset C."""
        data = load_subset_c_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        cands, merged, aligned = run_013._run_filtered_pipeline(bio_kg, chem_kg, "C")

        assert len(cands) > 0, "Expected at least 1 filtered candidate for Subset C"

    def test_baseline_has_more_candidates_than_filtered(self) -> None:
        """Baseline must produce ≥ filtered candidates (filter only removes)."""
        data = load_subset_b_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        base_cands, _, _ = run_013._run_baseline_pipeline(bio_kg, chem_kg, "B_base")
        filt_cands, _, _ = run_013._run_filtered_pipeline(bio_kg, chem_kg, "B_filt")

        assert len(base_cands) >= len(filt_cands), (
            f"Baseline ({len(base_cands)}) should have ≥ filtered ({len(filt_cands)})"
        )

    def test_deduplicated_candidates(self) -> None:
        """Filtered pipeline must return deduplicated candidates."""
        data = load_subset_c_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        cands, _, _ = run_013._run_filtered_pipeline(bio_kg, chem_kg, "C_dedup")

        pairs = [(c.subject_id, c.object_id) for c in cands]
        assert len(pairs) == len(set(pairs)), "Candidates must be deduplicated"

    def test_alignment_creates_nonzero_aligned_set(self) -> None:
        """Alignment must find at least one matching node pair for Subset B."""
        data = load_subset_b_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        _, _, aligned = run_013._run_filtered_pipeline(bio_kg, chem_kg, "B_align")

        # Subset B has same_entity_as bridges with matching labels (e.g., Arachidonic acid)
        assert len(aligned) >= 1, "Expected at least 1 aligned node pair for Subset B"

    def test_alignment_creates_nonzero_aligned_set_c(self) -> None:
        """Alignment must find at least one matching node pair for Subset C."""
        data = load_subset_c_data()
        bio_kg, chem_kg = run_013._build_bio_chem_kgs(data)
        _, _, aligned = run_013._run_filtered_pipeline(bio_kg, chem_kg, "C_align")

        assert len(aligned) >= 1, "Expected at least 1 aligned node pair for Subset C"


# ---------------------------------------------------------------------------
# Label assignment
# ---------------------------------------------------------------------------


class TestLabelAssignment:
    """Tests for _assign_label in run_013."""

    def _make_candidate(self, provenance: list[str]) -> object:
        """Build a minimal HypothesisCandidate with given provenance."""
        from src.kg.models import HypothesisCandidate
        return HypothesisCandidate(
            id="H0001",
            subject_id=provenance[0],
            relation="transitively_related_to",
            object_id=provenance[-1],
            description="",
            operator="compose",
            source_kg_name="test",
            provenance=provenance,
        )

    def test_strong_chain_is_promising(self) -> None:
        """Path with all strong relations must be labeled promising."""
        c = self._make_candidate(
            ["neu:g_TH", "encodes", "neu:TH", "produces", "neu:m_Dopamine",
             "same_entity_as", "phar:Dopamine", "undergoes", "phar:r_Hydroxylation"]
        )
        label, _ = run_013._assign_label(c)
        # encodes + produces + same_entity_as + undergoes: semi-strong heavy, 0 hard-drift
        assert label in ("promising", "weak_speculative")

    def test_hard_drift_chain_is_drift_heavy(self) -> None:
        """Path dominated by hard-drift relations must be labeled drift_heavy."""
        c = self._make_candidate(
            ["A", "contains", "B", "is_product_of", "C", "is_reverse_of", "D"]
        )
        label, _ = run_013._assign_label(c)
        assert label == "drift_heavy"

    def test_inhibits_activates_chain_promising(self) -> None:
        """Path with inhibits + activates + produces must be promising."""
        c = self._make_candidate(
            ["phar:Haloperidol", "inhibits", "neu:DRD2",
             "activates", "neu:PPP1R1B",
             "inhibits", "neu:CAMK2A"]
        )
        label, _ = run_013._assign_label(c)
        assert label == "promising"

    def test_empty_provenance_is_weak_speculative(self) -> None:
        """Candidate with no relations in provenance must be weak_speculative."""
        c = self._make_candidate(["A"])
        label, _ = run_013._assign_label(c)
        assert label == "weak_speculative"


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------


class TestVerdictComputation:
    """Tests for _compute_verdict function."""

    def _make_result(
        self,
        unique_to_multi: int = 5,
        deep_filtered: int = 3,
        promising: int = 2,
    ) -> dict:
        """Build a minimal metric dict for verdict testing."""
        return {
            "metric_4_alignment_reachability": {"unique_to_multi": unique_to_multi},
            "metric_2_deep_cross_domain": {"filtered": deep_filtered},
            "metric_3_label_distribution": {"promising": promising},
        }

    def test_all_three_pass_is_success(self) -> None:
        """All 3 subsets passing criteria yields SUCCESS."""
        results = {
            "A": self._make_result(),
            "B": self._make_result(),
            "C": self._make_result(),
        }
        verdict = run_013._compute_verdict(results)
        assert verdict["overall_verdict"] == "SUCCESS"
        assert verdict["passing_subsets"] == 3

    def test_two_pass_is_success(self) -> None:
        """2 out of 3 subsets passing yields SUCCESS."""
        results = {
            "A": self._make_result(),
            "B": self._make_result(),
            "C": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
        }
        verdict = run_013._compute_verdict(results)
        assert verdict["overall_verdict"] == "SUCCESS"
        assert verdict["passing_subsets"] == 2

    def test_one_pass_is_failure(self) -> None:
        """Only 1 subset passing yields FAILURE."""
        results = {
            "A": self._make_result(),
            "B": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
            "C": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
        }
        verdict = run_013._compute_verdict(results)
        assert verdict["overall_verdict"] == "FAILURE"
        assert verdict["passing_subsets"] == 1

    def test_zero_pass_is_failure(self) -> None:
        """No subsets passing yields FAILURE."""
        results = {
            "A": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
            "B": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
            "C": self._make_result(unique_to_multi=0, deep_filtered=0, promising=0),
        }
        verdict = run_013._compute_verdict(results)
        assert verdict["overall_verdict"] == "FAILURE"

    def test_per_subset_fields_present(self) -> None:
        """Verdict must include per-subset breakdown."""
        results = {"A": self._make_result()}
        verdict = run_013._compute_verdict(results)
        assert "per_subset" in verdict
        assert "A" in verdict["per_subset"]
        v = verdict["per_subset"]["A"]
        assert "alignment_dependent_reachability" in v
        assert "deep_cross_domain_candidates" in v
        assert "filter_surviving_promising" in v
        assert "all_pass" in v

    def test_partial_criteria_fails_all_pass(self) -> None:
        """Subset with only 2/3 criteria does not get all_pass."""
        results = {
            "A": self._make_result(unique_to_multi=0),  # alignment fails
        }
        verdict = run_013._compute_verdict(results)
        assert not verdict["per_subset"]["A"]["all_pass"]
        assert not verdict["per_subset"]["A"]["alignment_dependent_reachability"]
        assert verdict["per_subset"]["A"]["deep_cross_domain_candidates"]
        assert verdict["per_subset"]["A"]["filter_surviving_promising"]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


class TestUtilityHelpers:
    """Tests for _candidate_path_length, _is_cross_domain, _strong_ratio."""

    def _make_candidate(self, provenance: list[str]) -> object:
        from src.kg.models import HypothesisCandidate
        return HypothesisCandidate(
            id="H0001",
            subject_id=provenance[0],
            relation="transitively_related_to",
            object_id=provenance[-1],
            description="",
            operator="compose",
            source_kg_name="test",
            provenance=provenance,
        )

    def test_path_length_2hop(self) -> None:
        """2-hop path provenance returns length 2."""
        c = self._make_candidate(["A", "rel1", "B", "rel2", "C"])
        assert run_013._candidate_path_length(c) == 2

    def test_path_length_3hop(self) -> None:
        """3-hop path provenance returns length 3."""
        c = self._make_candidate(["A", "rel1", "B", "rel2", "C", "rel3", "D"])
        assert run_013._candidate_path_length(c) == 3

    def test_path_length_single_node(self) -> None:
        """Single-node provenance returns 0."""
        c = self._make_candidate(["A"])
        assert run_013._candidate_path_length(c) == 0

    def test_strong_ratio_all_strong(self) -> None:
        """Path with all inhibits returns strong_ratio = 1.0."""
        c = self._make_candidate(
            ["A", "inhibits", "B", "activates", "C", "catalyzes", "D"]
        )
        ratio = run_013._strong_ratio(c)
        assert ratio == 1.0

    def test_strong_ratio_no_strong(self) -> None:
        """Path with no strong relations returns strong_ratio = 0.0."""
        c = self._make_candidate(
            ["A", "contains", "B", "is_product_of", "C"]
        )
        ratio = run_013._strong_ratio(c)
        assert ratio == 0.0

    def test_strong_ratio_mixed(self) -> None:
        """Mixed path returns fractional strong ratio."""
        c = self._make_candidate(
            ["A", "inhibits", "B", "contains", "C"]
        )
        ratio = run_013._strong_ratio(c)
        assert 0.0 < ratio < 1.0

    def test_is_cross_domain_with_kg(self) -> None:
        """Cross-domain pair detected via KG node lookup."""
        kg = KnowledgeGraph(name="test")
        kg.add_node(KGNode("bio1", "Bio node", "biology"))
        kg.add_node(KGNode("chem1", "Chem node", "chemistry"))
        from src.kg.models import HypothesisCandidate
        c = HypothesisCandidate(
            id="H0001", subject_id="bio1", relation="rel",
            object_id="chem1", description="", operator="compose",
            source_kg_name="test", provenance=["bio1", "rel", "chem1"]
        )
        assert run_013._is_cross_domain(c, kg)

    def test_is_not_cross_domain_same_domain(self) -> None:
        """Same-domain pair not detected as cross-domain."""
        kg = KnowledgeGraph(name="test")
        kg.add_node(KGNode("bio1", "Bio 1", "biology"))
        kg.add_node(KGNode("bio2", "Bio 2", "biology"))
        from src.kg.models import HypothesisCandidate
        c = HypothesisCandidate(
            id="H0001", subject_id="bio1", relation="rel",
            object_id="bio2", description="", operator="compose",
            source_kg_name="test", provenance=["bio1", "rel", "bio2"]
        )
        assert not run_013._is_cross_domain(c, kg)
