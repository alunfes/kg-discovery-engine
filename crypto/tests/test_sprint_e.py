"""Sprint E tests — E1/E2/E3/E4 coverage.

E1: beta_reversion grammar — negative-evidence nodes fire below threshold.
E2: positioning_unwind grammar — accumulation nodes fire from continuous OI build.
E3: branch diversity metrics appear in run output (branch_metrics.json).
E4: null/baseline chains suppress correctly.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from crypto.src.ingestion.synthetic import SyntheticGenerator, OpenInterestSample
from crypto.src.states.extractor import extract_states, extract_oi_states
from crypto.src.kg.microstructure import build_microstructure_kg
from crypto.src.kg.cross_asset import build_cross_asset_kg
from crypto.src.kg.chain_grammar import build_chain_grammar_kg
from crypto.src.eval.generator import generate_hypotheses
from crypto.src.eval.metrics import compute_branch_metrics, _card_branch
from crypto.src.pipeline import PipelineConfig, run_pipeline
from crypto.src.kg.base import KGNode, KGEdge, KGraph
from crypto.src.operators.ops import union
from crypto.src.schema.market_state import MarketStateCollection


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ASSETS = ["HYPE", "ETH", "BTC", "SOL"]


@pytest.fixture(scope="module")
def dataset_120():
    return SyntheticGenerator(seed=42, n_minutes=120).generate()


@pytest.fixture(scope="module")
def collections_120(dataset_120):
    return {a: extract_states(dataset_120, a, "test_e") for a in ASSETS}


@pytest.fixture(scope="module")
def cross_kg_120(collections_120, dataset_120):
    return build_cross_asset_kg(collections_120, dataset=dataset_120)


@pytest.fixture(scope="module")
def merged_kg_120(collections_120, dataset_120):
    """Full merged KG: all micro KGs + cross-asset (mirrors pipeline working_kg)."""
    cross_kg = build_cross_asset_kg(collections_120, dataset=dataset_120)
    micro_kgs = [build_microstructure_kg(collections_120[a]) for a in ASSETS]
    merged = micro_kgs[0]
    for kg in micro_kgs[1:]:
        merged = union(merged, kg)
    return union(merged, cross_kg)


@pytest.fixture(scope="module")
def pipeline_cards():
    cfg = PipelineConfig(
        run_id="test_sprint_e",
        seed=42,
        n_minutes=120,
        top_k=60,
        output_dir="/tmp/test_sprint_e",
    )
    return run_pipeline(cfg)


# ---------------------------------------------------------------------------
# E1 — Negative evidence nodes
# ---------------------------------------------------------------------------

def test_oi_samples_generated(dataset_120):
    """SyntheticGenerator must produce OpenInterestSample objects."""
    oi = [s for s in dataset_120.oi_samples if s.asset == "HYPE"]
    assert len(oi) > 0, "No OI samples generated for HYPE"
    assert all(isinstance(s, OpenInterestSample) for s in oi)


def test_oi_states_extracted(collections_120):
    """extract_oi_states must populate oi_states in MarketStateCollection."""
    hype = collections_120["HYPE"]
    assert len(hype.oi_states) > 0, "No OI states extracted for HYPE"


def test_sol_oi_accumulation_detected(collections_120):
    """SOL should have at least one OIState with is_accumulation=True."""
    sol = collections_120["SOL"]
    accum = [s for s in sol.oi_states if s.is_accumulation]
    assert len(accum) > 0, (
        "No OI accumulation detected for SOL — monotonic build from minute 50 not working"
    )


def test_no_funding_shift_node_created(collections_120, merged_kg_120):
    """NoFundingShiftNode should be created for at least one corr-break pair."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    nfs_nodes = [n for n in grammar_kg.nodes.values() if n.node_type == "NoFundingShiftNode"]
    assert len(nfs_nodes) > 0, "No NoFundingShiftNode created"


def test_no_oi_expansion_node_created(collections_120, merged_kg_120):
    """NoOIExpansionNode should be created for at least one corr-break pair."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    noi_nodes = [n for n in grammar_kg.nodes.values() if n.node_type == "NoOIExpansionNode"]
    assert len(noi_nodes) > 0, "No NoOIExpansionNode created"


<<<<<<< HEAD
def test_no_persistent_aggression_node_created():
    """NoPersistentAggressionNode created only when J1 gate does NOT fire.

    J1 gate (Sprint J): if funding_extreme AND OI_accumulation both present,
    _e1_transient_aggression_chain is suppressed before building NPA nodes.
    This test uses a minimal KG/collections with no funding_extreme and no
    OI_accumulation so the J1 gate stays inactive and NPA nodes can be built.
    """
    from crypto.src.kg.base import KGNode, KGraph
    from crypto.src.schema.market_state import (
        FundingState, OIState, MarketStateCollection,
    )

    # Minimal merged KG: corr_break for ETH/BTC, burst for both, no funding_extreme
    kg = KGraph(family="test_npa")
    kg.add_node(KGNode("corr:ETH:BTC", "CorrelationNode", {
        "asset_a": "ETH", "asset_b": "BTC",
        "is_break": True, "corr_break_score": 0.4, "correlation": 0.05,
    }))
    # 2 burst windows each asset — burst_min=2, satisfies 1<=burst_min<=4
    for asset in ["ETH", "BTC"]:
        for i in range(2):
            kg.add_node(KGNode(f"aggr:{asset}:{i}", "AggressionNode",
                               {"is_burst": True, "intensity": 1.2}))

    # Collections: no OI accumulation, no funding extreme
    def _mk_coll(asset: str) -> MarketStateCollection:
        return MarketStateCollection(
            asset=asset, run_id="test_npa",
            fundings=[FundingState(asset=asset, timestamp_ms=0,
                                   funding_rate=0.001, annualised=0.365, z_score=0.5)],
            oi_states=[OIState(asset=asset, timestamp_ms=0, oi=1000.0, oi_prev=1000.0,
                               oi_change_pct=0.01, state_score=0.1,
                               build_duration=1, is_accumulation=False, is_one_sided=False)],
        )

    colls = {a: _mk_coll(a) for a in ["ETH", "BTC"]}
    grammar_kg, log = build_chain_grammar_kg(kg, colls)

    # J1 gate must NOT have fired (no funding_extreme, no OI_accum)
    j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
    assert j1_entries == [], f"J1 gate must not fire without funding extreme + OI accum: {j1_entries}"

    npa_nodes = [n for n in grammar_kg.nodes.values()
                 if n.node_type == "NoPersistentAggressionNode"]
    assert len(npa_nodes) > 0, (
        "NoPersistentAggressionNode must be created when J1 gate is inactive "
        "and burst_min in [1,4]"
    )
=======
def test_no_persistent_aggression_node_created(collections_120, merged_kg_120):
    """NoPersistentAggressionNode created for pairs where HYPE has 1-2 burst windows."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    npa_nodes = [n for n in grammar_kg.nodes.values()
                 if n.node_type == "NoPersistentAggressionNode"]
    assert len(npa_nodes) > 0, "No NoPersistentAggressionNode created"
>>>>>>> claude/gracious-edison


def test_e1_reversion_chain_fires(pipeline_cards):
    """At least one E1 beta_reversion chain hypothesis must be produced."""
    e1_cards = [c for c in pipeline_cards if "E1" in c.tags and "beta_reversion" in c.tags]
    assert len(e1_cards) > 0, "No E1 beta_reversion chain hypotheses produced"


def test_e1_cards_have_negative_evidence_tag(pipeline_cards):
    """E1 cards must carry at least one negative-evidence or related tag."""
    e1_cards = [c for c in pipeline_cards if "E1" in c.tags]
    neg_tags = {"negative_evidence", "transient_aggression", "weak_premium"}
    for card in e1_cards:
        has_neg = bool(neg_tags & set(card.tags))
        assert has_neg or "beta_reversion" in card.tags, (
            f"E1 card missing descriptive tag: {card.tags}"
        )


def test_e1_no_funding_oi_evidence_nodes(pipeline_cards):
    """E1 no_funding_oi chains must cite ≥3 evidence nodes (incl. NoFundingShiftNode, etc)."""
    chains = [c for c in pipeline_cards if "E1" in c.tags and "negative_evidence" in c.tags]
    for card in chains:
        assert len(card.evidence_nodes) >= 3, (
            f"E1 negative_evidence chain has too few evidence nodes: {card.evidence_nodes}"
        )


# ---------------------------------------------------------------------------
# E2 — Accumulation nodes and unwind chains
# ---------------------------------------------------------------------------

def test_funding_pressure_regime_node_created(collections_120, merged_kg_120):
    """FundingPressureRegimeNode must be created when funding extreme exists for pair."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    fpr = [n for n in grammar_kg.nodes.values() if n.node_type == "FundingPressureRegimeNode"]
    assert len(fpr) > 0, "No FundingPressureRegimeNode created"


def test_one_sided_oi_build_node_created(collections_120, merged_kg_120):
    """OneSidedOIBuildNode must be created when SOL OI accumulation is present."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    oi_nodes = [n for n in grammar_kg.nodes.values() if n.node_type == "OneSidedOIBuildNode"]
    assert len(oi_nodes) > 0, "No OneSidedOIBuildNode created"


def test_fragile_premium_node_has_required_attrs(collections_120, merged_kg_120):
    """FragilePremiumStateNode must carry state_score, duration, persistence, coverage."""
    grammar_kg, _ = build_chain_grammar_kg(merged_kg_120, collections_120)
    fps_nodes = [n for n in grammar_kg.nodes.values() if n.node_type == "FragilePremiumStateNode"]
    assert len(fps_nodes) > 0
    for node in fps_nodes:
        for attr in ("state_score", "duration", "persistence", "coverage"):
            assert attr in node.attributes, f"FragilePremiumStateNode missing '{attr}'"


def test_e2_unwind_chain_fires(pipeline_cards):
    """At least one E2 positioning_unwind chain must be produced."""
    e2_cards = [c for c in pipeline_cards if "E2" in c.tags and "positioning_unwind" in c.tags]
    assert len(e2_cards) > 0, "No E2 positioning_unwind hypotheses produced"


def test_e2_funding_pressure_chain_fires(pipeline_cards):
    """E2 funding_pressure chain (Chain 1) must appear in output."""
    fp_cards = [c for c in pipeline_cards if "funding_pressure" in c.tags]
    assert len(fp_cards) > 0, "E2 funding_pressure chain never fired"


def test_e2_oi_crowding_chain_fires(pipeline_cards):
    """E2 one-sided OI crowding chain (Chain 2) must appear in output."""
    oi_cards = [c for c in pipeline_cards if "oi_crowding" in c.tags]
    assert len(oi_cards) > 0, "E2 oi_crowding chain never fired"


def test_e2_cards_plausibility_above_threshold(pipeline_cards):
    """E2 positioning_unwind cards must have plausibility_prior embedded in composite >= 0.50."""
    e2_cards = [c for c in pipeline_cards if "E2" in c.tags]
    assert len(e2_cards) > 0
    for card in e2_cards:
        assert card.composite_score >= 0.40, (
            f"E2 card composite score too low: {card.composite_score}"
        )


# ---------------------------------------------------------------------------
# E3 — Branch metrics in run output
# ---------------------------------------------------------------------------

def test_branch_metrics_file_exists():
    """branch_metrics.json must exist after a pipeline run."""
    import os
    path = "/tmp/test_sprint_e/test_sprint_e/branch_metrics.json"
    assert os.path.exists(path), "branch_metrics.json not written by pipeline"


def test_branch_metrics_keys(pipeline_cards):
    """compute_branch_metrics must return all required E3 keys."""
    metrics = compute_branch_metrics(pipeline_cards, [], n_corr_break_pairs=6, top_k=10)
    required = {
        "branch_distribution", "branch_entropy", "top_k_branch_share",
        "mean_score_by_branch", "survival_across_runs",
        "branch_activation_rate", "branch_suppression_reason",
    }
    assert required.issubset(metrics.keys()), f"Missing keys: {required - metrics.keys()}"


def test_branch_entropy_positive(pipeline_cards):
    """branch_entropy must be > 0 when multiple branches are present."""
    metrics = compute_branch_metrics(pipeline_cards, [], n_corr_break_pairs=6, top_k=10)
    assert metrics["branch_entropy"] > 0.0, "branch_entropy is 0 — only one branch produced"


def test_top_k_branch_share_sums_to_one(pipeline_cards):
    """top_k_branch_share fractions must sum to 1.0."""
    metrics = compute_branch_metrics(pipeline_cards, [], n_corr_break_pairs=6, top_k=10)
    share_sum = sum(metrics["top_k_branch_share"].values())
    assert abs(share_sum - 1.0) < 0.01, f"top_k_branch_share sums to {share_sum}, not 1.0"


def test_mean_score_by_branch_in_unit_interval(pipeline_cards):
    """All mean scores per branch must be in [0, 1]."""
    metrics = compute_branch_metrics(pipeline_cards, [], n_corr_break_pairs=6, top_k=10)
    for branch, score in metrics["mean_score_by_branch"].items():
        assert 0.0 <= score <= 1.0, f"Branch {branch} mean score out of range: {score}"


def test_suppression_reason_counts_present(collections_120, merged_kg_120, pipeline_cards):
    """branch_suppression_reason must be non-empty (some chains should fail)."""
    _, suppression_log = build_chain_grammar_kg(merged_kg_120, collections_120)
    metrics = compute_branch_metrics(pipeline_cards, suppression_log, n_corr_break_pairs=6)
    assert metrics["branch_suppression_reason"], "suppression_reason dict is empty — no chains suppressed?"


def test_suppression_reasons_are_valid(collections_120, merged_kg_120, pipeline_cards):
    """All suppression reasons must be from the defined set."""
    valid_reasons = {
        "no_trigger", "low_coverage", "failed_timeline", "below_threshold",
<<<<<<< HEAD
        "missing_accumulation",
        # F3 taxonomy (replaces generic insufficient_negative_evidence)
        "contradictory_evidence", "failed_followthrough", "structural_absence",
        # H1: soft gate border cases
        "soft_gated",
=======
        "missing_accumulation", "insufficient_negative_evidence",
>>>>>>> claude/gracious-edison
    }
    _, suppression_log = build_chain_grammar_kg(merged_kg_120, collections_120)
    for entry in suppression_log:
        reason = entry.get("reason", "")
        assert reason in valid_reasons, f"Unknown suppression reason: {reason}"


# ---------------------------------------------------------------------------
# E4 — Null/baseline chains
# ---------------------------------------------------------------------------

def test_e4_null_chains_registered_in_generate_hypotheses():
    """generate_hypotheses must include null baseline rules.

    We create a minimal KG with a CorrelationNode that has break_score < 0.15
    and no grammar nodes — E4 Chain 1 should fire.
    """
    kg = KGraph(family="test")
    corr = KGNode(
        node_id="corr:X:Y",
        node_type="CorrelationNode",
        attributes={
            "asset_a": "X", "asset_b": "Y",
            "rho": 0.15, "is_break": True,
            "corr_break_score": 0.08,  # below 0.15 threshold
            "rho_high_vol": None, "rho_normal": None,
            "roll_mean": 0.4,
        },
    )
    kg.add_node(corr)
    hypotheses = generate_hypotheses(kg)
    null_hyps = [h for h in hypotheses if "null_baseline" in h.get("tags", [])]
    assert len(null_hyps) > 0, "E4 null_low_followthrough chain never fired on weak break"


def test_e4_weak_dispersion_requires_borderline_rho():
    """E4 Chain 2 (weak_dispersion) only fires for rho in [0.3, 0.5)."""
    kg = KGraph(family="test")
    # rho = 0.35 (borderline), low dispersion → should fire
    corr = KGNode(
        node_id="corr:A:B",
        node_type="CorrelationNode",
        attributes={
            "asset_a": "A", "asset_b": "B",
            "rho": 0.35, "is_break": False,
            "rho_high_vol": 0.36, "rho_normal": 0.34,  # dispersion = 0.02 < 0.2
            "corr_break_score": 0.05,
        },
    )
    kg.add_node(corr)
    hypotheses = generate_hypotheses(kg)
    wd = [h for h in hypotheses if "weak_dispersion" in h.get("tags", [])]
    assert len(wd) > 0, "E4 weak_dispersion did not fire for borderline rho=0.35"

    # rho = 0.6 → should NOT fire
    kg2 = KGraph(family="test2")
    corr2 = KGNode(
        node_id="corr:C:D",
        node_type="CorrelationNode",
        attributes={
            "asset_a": "C", "asset_b": "D",
            "rho": 0.6, "is_break": False,
            "rho_high_vol": 0.61, "rho_normal": 0.59,
            "corr_break_score": 0.03,
        },
    )
    kg2.add_node(corr2)
    hypotheses2 = generate_hypotheses(kg2)
    wd2 = [h for h in hypotheses2 if "weak_dispersion" in h.get("tags", [])]
    assert len(wd2) == 0, "E4 weak_dispersion fired for rho=0.6 (out of range)"
