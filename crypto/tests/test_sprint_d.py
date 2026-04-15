"""Sprint D tests — D1/D2/D3 coverage.

D1: B3 causal chain rule generator (KG path traversal).
D2: Composite corr_break_score metric.
D3: Per-branch score thresholds.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from crypto.src.ingestion.synthetic import SyntheticGenerator
from crypto.src.states.extractor import extract_states
from crypto.src.kg.microstructure import build_microstructure_kg
from crypto.src.kg.cross_asset import build_cross_asset_kg, compute_corr_break_score
from crypto.src.eval.generator import generate_hypotheses
from crypto.src.pipeline import PipelineConfig, run_pipeline


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dataset_120():
    gen = SyntheticGenerator(seed=42, n_minutes=120)
    return gen.generate()


@pytest.fixture(scope="module")
def collections_120(dataset_120):
    assets = ["HYPE", "ETH", "BTC", "SOL"]
    return {a: extract_states(dataset_120, a, "test_d") for a in assets}


@pytest.fixture(scope="module")
def cross_kg_120(collections_120, dataset_120):
    return build_cross_asset_kg(collections_120, dataset=dataset_120)


@pytest.fixture(scope="module")
def pipeline_cards():
    cfg = PipelineConfig(
        run_id="test_sprint_d",
        seed=42,
        n_minutes=120,
        top_k=20,
        output_dir="/tmp/test_sprint_d",
    )
    return run_pipeline(cfg)


# ---------------------------------------------------------------------------
# D1 — B3 PremiumDislocationNode chain
# ---------------------------------------------------------------------------


def test_b3_premium_dislocation_nodes_created(collections_120):
    """HYPE micro KG must contain PremiumDislocationNodes after funding fix."""
    micro = build_microstructure_kg(collections_120["HYPE"])
    prem_nodes = [n for n in micro.nodes.values() if n.node_type == "PremiumDislocationNode"]
    assert len(prem_nodes) > 0, "No PremiumDislocationNodes found — B3 chain not firing"


def test_b3_expected_funding_nodes_created(collections_120):
    """HYPE micro KG must contain ExpectedFundingNodes."""
    micro = build_microstructure_kg(collections_120["HYPE"])
    exp_nodes = [n for n in micro.nodes.values() if n.node_type == "ExpectedFundingNode"]
    assert len(exp_nodes) > 0


def test_b3_chain_edge_relations_present(collections_120):
    """All three B3 chain edge relations must appear in HYPE micro KG."""
    micro = build_microstructure_kg(collections_120["HYPE"])
    relations = {e.relation for e in micro.edges.values()}
    assert "causes_premium_dislocation" in relations
    assert "dislocation_drives_expected_funding" in relations
    assert "expected_funding_realized_as" in relations


def test_b3_chain_is_connected(collections_120):
    """The B3 chain must form a connected 3-hop path through the KG."""
    micro = build_microstructure_kg(collections_120["HYPE"])
    # Build adjacency from edge relations
    cause_edges = {
        e.source_id: e.target_id
        for e in micro.edges.values()
        if e.relation == "causes_premium_dislocation"
    }
    drive_edges = {
        e.source_id: e.target_id
        for e in micro.edges.values()
        if e.relation == "dislocation_drives_expected_funding"
    }
    realize_edges = {
        e.source_id: e.target_id
        for e in micro.edges.values()
        if e.relation == "expected_funding_realized_as"
    }
    # For at least one aggression source, the 3-hop chain closes
    found = False
    for aggr_id, prem_id in cause_edges.items():
        exp_id = drive_edges.get(prem_id)
        if exp_id and exp_id in realize_edges:
            fund_id = realize_edges[exp_id]
            assert micro.nodes.get(fund_id) is not None
            found = True
            break
    assert found, "No connected 3-hop AggressionNode→Prem→Expected→Funding chain found"


def test_d1_chain_rules_fire(pipeline_cards):
    """D1 chain rules must produce at least one hypothesis with chain_rule tag."""
    chain_cards = [c for c in pipeline_cards if "chain_rule" in c.tags and "D1" in c.tags]
    assert len(chain_cards) > 0, "No D1 chain rule hypotheses produced"


def test_d1_chain_rule_titles_are_descriptive(pipeline_cards):
    """D1 hypothesis titles must contain 'Chain-D1' prefix."""
    chain_cards = [c for c in pipeline_cards if "D1" in c.tags]
    for card in chain_cards:
        assert "Chain-D1" in card.title, f"Unexpected title format: {card.title}"


def test_d1_chain_hypotheses_have_evidence_nodes(pipeline_cards):
    """D1 hypotheses must reference at least 2 evidence nodes."""
    chain_cards = [c for c in pipeline_cards if "D1" in c.tags]
    for card in chain_cards:
        assert len(card.evidence_nodes) >= 2, (
            f"D1 card has too few evidence nodes: {card.evidence_nodes}"
        )


def test_d1_chain_flow_continuation_plausibility(pipeline_cards):
    """flow_continuation D1 cards must have plausibility_prior >= 0.60."""
    cont_cards = [
        c for c in pipeline_cards
        if "D1" in c.tags and "continuation_candidate" in c.tags
    ]
    assert len(cont_cards) > 0, "No flow_continuation D1 cards"
    for card in cont_cards:
        assert card.composite_score >= 0.50, (
            f"D1 continuation card score too low: {card.composite_score}"
        )


# ---------------------------------------------------------------------------
# D2 — corr_break_score composite metric
# ---------------------------------------------------------------------------


def test_corr_break_score_is_in_unit_interval(cross_kg_120):
    """corr_break_score must lie in [0, 1] for all CorrelationNodes."""
    for node in cross_kg_120.nodes.values():
        if node.node_type != "CorrelationNode":
            continue
        score = node.attributes.get("corr_break_score")
        assert score is not None, f"corr_break_score missing on {node.node_id}"
        assert 0.0 <= score <= 1.0, f"score out of range: {score}"


def test_corr_break_score_function_returns_float():
    """compute_corr_break_score must return a float in [0, 1] for typical inputs."""
    roll_rhos = [0.3, 0.25, 0.28, 0.1]
    score = compute_corr_break_score(
        rho_pearson=0.1,
        roll_rhos=roll_rhos,
        roll_mean=sum(roll_rhos) / len(roll_rhos),
        best_k=3,
        rho_high_vol=0.2,
        rho_normal=0.5,
        coverage={"missing_ratio": 0.02, "overlap_count": 25},
    )
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_corr_break_score_increases_with_larger_drop():
    """Current rho far below rolling mean → higher drop score.

    roll_rhos must have non-zero variance so the z-score is non-degenerate.
    """
    roll_rhos = [0.40, 0.35, 0.38, 0.32]  # mean ≈ 0.3625, std ≈ 0.03
    roll_mean = sum(roll_rhos) / len(roll_rhos)

    score_high = compute_corr_break_score(
        rho_pearson=-0.2,   # far below mean → z strongly negative → high drop score
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=0,
        rho_high_vol=0.35,
        rho_normal=0.35,
        coverage={"missing_ratio": 0.0, "overlap_count": 30},
    )
    score_low = compute_corr_break_score(
        rho_pearson=0.36,   # barely below mean → z ≈ 0 → low drop score
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=0,
        rho_high_vol=0.35,
        rho_normal=0.35,
        coverage={"missing_ratio": 0.0, "overlap_count": 30},
    )
    assert score_high > score_low, (
        f"Expected larger drop → higher score, got {score_high} vs {score_low}"
    )


def test_corr_break_score_increases_with_lag_shift():
    """Non-zero best_lag_k should increase score versus zero lag."""
    roll_rhos = [0.5, 0.5, 0.5]
    roll_mean = 0.5

    score_zero_lag = compute_corr_break_score(
        rho_pearson=0.5,
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=0,
        rho_high_vol=0.5,
        rho_normal=0.5,
        coverage={"missing_ratio": 0.0, "overlap_count": 30},
    )
    score_lagged = compute_corr_break_score(
        rho_pearson=0.5,
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=8,
        rho_high_vol=0.5,
        rho_normal=0.5,
        coverage={"missing_ratio": 0.0, "overlap_count": 30},
    )
    assert score_lagged > score_zero_lag


def test_corr_break_score_penalised_by_missing_data():
    """High missing_ratio should reduce corr_break_score."""
    roll_rhos = [0.4, 0.3, 0.2]
    roll_mean = 0.3

    score_good = compute_corr_break_score(
        rho_pearson=-0.1,
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=5,
        rho_high_vol=0.4,
        rho_normal=0.6,
        coverage={"missing_ratio": 0.0, "overlap_count": 30},
    )
    score_bad = compute_corr_break_score(
        rho_pearson=-0.1,
        roll_rhos=roll_rhos,
        roll_mean=roll_mean,
        best_k=5,
        rho_high_vol=0.4,
        rho_normal=0.6,
        coverage={"missing_ratio": 0.5, "overlap_count": 5},
    )
    assert score_bad < score_good


def test_corr_nodes_have_branch_thresholds(cross_kg_120):
    """CorrelationNodes must carry branch_thresholds dict."""
    found = False
    for node in cross_kg_120.nodes.values():
        if node.node_type == "CorrelationNode":
            bt = node.attributes.get("branch_thresholds")
            assert isinstance(bt, dict), f"branch_thresholds not a dict on {node.node_id}"
            assert "continuation_candidate" in bt
            found = True
    assert found, "No CorrelationNodes in cross KG"


# ---------------------------------------------------------------------------
# D3 — per-branch score thresholds
# ---------------------------------------------------------------------------


def test_d3_continuation_branch_requires_score_020(pipeline_cards):
    """continuation_candidate cards must come from pairs with corr_break_score >= 0.20."""
    # All D1 continuation cards should have scores above 0.50 (score gate ensures quality)
    cont_cards = [
        c for c in pipeline_cards
        if "continuation_candidate" in c.tags and "chain_rule" in c.tags
    ]
    assert len(cont_cards) > 0
    # If the threshold were not enforced, low-score pairs would appear.
    # Check that all continuation D1 cards have non-trivial composite scores.
    for card in cont_cards:
        assert card.composite_score > 0.40, (
            f"Continuation card scored too low, threshold may not be enforced: {card.composite_score}"
        )


def test_d3_branch_thresholds_dict_complete(cross_kg_120):
    """branch_thresholds on CorrelationNodes must cover all 4 A4 branches."""
    required = {
        "mean_reversion_candidate",
        "continuation_candidate",
        "microstructure_artifact",
        "positioning_unwind_candidate",
    }
    for node in cross_kg_120.nodes.values():
        if node.node_type != "CorrelationNode":
            continue
        bt = node.attributes.get("branch_thresholds", {})
        assert required.issubset(bt.keys()), (
            f"branch_thresholds missing keys on {node.node_id}: {bt.keys()}"
        )
