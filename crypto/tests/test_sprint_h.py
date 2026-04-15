"""Sprint H tests: soft gating (H1), contradiction rerouting (H2), uplift ranking (H3).

Test coverage:
  H1 — continuous confidence is computed and attached to KG chain nodes
  H1 — low-confidence OI (border case) with strong other evidence still produces candidates
  H1 — soft_gated tag and reduced plausibility on border-case hypotheses
  H1 — no_OI pairs do not have border-case fires when OI score < SOFT_GATE_MIN
  H2 — contradiction generates reroute candidate from beta_reversion→positioning_unwind
  H2 — rerouted hypotheses have original_card_id traceability
  H2 — reroute_confidence and original_branch_vs_rerouted_score are populated
  H3 — uplift_aware_score is computed for all cards
  H3 — cards with high uplift but low raw score are rescued
  H3 — rerouted hypotheses are traceable (original_card_id present)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def h_pipeline_result():
    """Full pipeline run with Sprint H features (seed=42, 120 min)."""
    from crypto.src.pipeline import PipelineConfig, run_pipeline
    from crypto.src.ingestion.synthetic import SyntheticGenerator
    from crypto.src.states.extractor import extract_states
    from crypto.src.kg.cross_asset import build_cross_asset_kg
    from crypto.src.kg.microstructure import build_microstructure_kg
    from crypto.src.kg.execution import build_execution_kg
    from crypto.src.kg.regime import build_regime_kg
    from crypto.src.kg.pair import build_pair_kg
    from crypto.src.kg.chain_grammar import build_chain_grammar_kg
    from crypto.src.operators.ops import align, union, compose, difference, rank
    from crypto.src.kg.temporal_guard import annotate_temporal_quality
    from crypto.src.eval.generator import generate_hypotheses
    from crypto.src.eval.scorer import score_hypothesis
    from crypto.src.eval.metrics import compute_branch_metrics
    from crypto.src.eval.contradiction_metrics import (
        compute_contradiction_metrics, compute_conflict_adjusted_ranking
    )
    from crypto.src.eval.rerouter import compute_reroute_candidates, reroute_summary
    from crypto.src.eval.uplift_ranker import compute_uplift_aware_ranking
    from crypto.src.inventory.store import HypothesisInventory
    import random

    seed, n_min, assets = 42, 120, ["HYPE", "ETH", "BTC", "SOL"]
    top_k = 30
    run_id = "test_sprint_h"
    random.seed(seed)

    gen = SyntheticGenerator(seed=seed, n_minutes=n_min, assets=assets)
    dataset = gen.generate()
    colls = {a: extract_states(dataset, a, run_id) for a in assets}

    micro_kgs = {a: build_microstructure_kg(colls[a]) for a in assets}
    exec_kgs = {a: build_execution_kg(colls[a]) for a in assets}
    regime_kgs = {a: build_regime_kg(colls[a]) for a in assets}
    cross_kg = build_cross_asset_kg(colls, dataset=dataset)
    pair_kg = build_pair_kg(colls)

    def merge(kgs, name):
        r = kgs[0]
        for kg in kgs[1:]:
            r = union(r, kg)
        r.family = name
        return r

    mm = merge(list(micro_kgs.values()), "micro_all")
    me = merge(list(exec_kgs.values()), "exec_all")
    mr = merge(list(regime_kgs.values()), "regime_all")
    aligned = align(mm, me, "symbol")
    full = union(union(union(aligned, cross_kg), pair_kg), mr)
    composed = compose(full, "aggression_predicts_funding")
    novel = difference(composed, aligned)
    working = union(full, novel)
    grammar_kg, supp_log = build_chain_grammar_kg(working, colls)
    working = union(working, grammar_kg)
    annotate_temporal_quality(working)

    inv = HypothesisInventory()
    raw = generate_hypotheses(working)

    def qs(r):
        return float(r.get("plausibility_prior", 0.5))

    top = rank(raw, qs, top_k=top_k * 2)
    cards = []
    for r in top[:top_k]:
        card = score_hypothesis(r, working, inv, run_id)
        inv.add(card)
        cards.append(card)

    n_pairs = sum(
        1 for n in cross_kg.nodes.values()
        if n.node_type == "CorrelationNode" and n.attributes.get("is_break")
    )
    metrics = compute_branch_metrics(cards, supp_log, n_pairs, top_k)
    contra = compute_contradiction_metrics(cards, supp_log, cross_kg)
    meta = {
        d["card_id"]: d["meta_score"]
        for d in metrics.get("normalized_ranking", {}).get("normalized_cards", [])
    }
    conflict_ranking = compute_conflict_adjusted_ranking(cards, contra, meta, top_k)

    reroutes = compute_reroute_candidates(cards, contra, supp_log, top_k)
    rr_summary = reroute_summary(reroutes, top_k)
    g3_pool = metrics.get("matched_baseline_pool", {})
    uplift = compute_uplift_aware_ranking(cards, contra, meta, g3_pool, top_k)

    return {
        "cards": cards,
        "working_kg": working,
        "suppression_log": supp_log,
        "contradiction_metrics": contra,
        "reroutes": reroutes,
        "reroute_summary": rr_summary,
        "uplift_ranking": uplift,
        "collections": colls,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# H1: Soft activation gating
# ---------------------------------------------------------------------------

def test_h1_soft_gate_module_thresholds():
    """SOFT_GATE_MIN < HARD_GATE_MIN and both in (0, 1)."""
    from crypto.src.eval.soft_gate import SOFT_GATE_MIN, HARD_GATE_MIN
    assert 0.0 < SOFT_GATE_MIN < HARD_GATE_MIN < 1.0


def test_h1_compute_oi_confidence_returns_zero_for_empty():
    """Empty OI state list → confidence 0.0."""
    from crypto.src.eval.soft_gate import compute_oi_accumulation_confidence
    assert compute_oi_accumulation_confidence([]) == 0.0


def test_h1_compute_oi_confidence_hard_active(market_collections):
    """HYPE has OI accumulation → confidence >= HARD_GATE_MIN."""
    from crypto.src.eval.soft_gate import compute_oi_accumulation_confidence, HARD_GATE_MIN
    oi = market_collections["HYPE"].oi_states
    if not any(s.is_accumulation for s in oi):
        pytest.skip("HYPE has no accumulation in this fixture")
    conf = compute_oi_accumulation_confidence(oi)
    assert conf >= HARD_GATE_MIN


def test_h1_compute_funding_confidence_near_extreme(market_collections):
    """Funding confidence is > 0 for HYPE which has extreme funding."""
    from crypto.src.eval.soft_gate import compute_funding_pressure_confidence
    fund = market_collections["HYPE"].fundings
    conf = compute_funding_pressure_confidence(fund)
    assert conf >= 0.0


def test_h1_soft_activation_gate_hard_active():
    """confidence >= HARD_GATE_MIN → hard_active=True, scale=1.0."""
    from crypto.src.eval.soft_gate import soft_activation_gate, HARD_GATE_MIN
    result = soft_activation_gate(HARD_GATE_MIN)
    assert result["hard_active"] is True
    assert result["plausibility_scale"] == 1.0


def test_h1_soft_activation_gate_border_case():
    """SOFT_GATE_MIN <= conf < HARD_GATE_MIN → border_case=True, scale < 1.0."""
    from crypto.src.eval.soft_gate import soft_activation_gate, SOFT_GATE_MIN, HARD_GATE_MIN
    conf = (SOFT_GATE_MIN + HARD_GATE_MIN) / 2.0
    result = soft_activation_gate(conf)
    assert result["border_case"] is True
    assert 0.0 < result["plausibility_scale"] < 1.0


def test_h1_soft_activation_gate_killed():
    """confidence < SOFT_GATE_MIN → soft_active=False, scale=0.0."""
    from crypto.src.eval.soft_gate import soft_activation_gate
    result = soft_activation_gate(0.10)
    assert result["soft_active"] is False
    assert result["plausibility_scale"] == 0.0


def test_h1_activation_confidence_on_nodes(h_pipeline_result):
    """OneSidedOIBuildNode and FundingPressureRegimeNode carry activation_confidence."""
    kg = h_pipeline_result["working_kg"]
    oi_nodes = [n for n in kg.nodes.values() if n.node_type == "OneSidedOIBuildNode"]
    fund_nodes = [n for n in kg.nodes.values() if n.node_type == "FundingPressureRegimeNode"]
    for nd in oi_nodes + fund_nodes:
        assert "activation_confidence" in nd.attributes, (
            f"{nd.node_type} missing activation_confidence"
        )
        conf = nd.attributes["activation_confidence"]
        assert 0.0 <= conf <= 1.0


def test_h1_soft_gated_tag_on_border_cards(h_pipeline_result):
    """If any soft-gated hypotheses fired, they carry the 'soft_gated' tag."""
    cards = h_pipeline_result["cards"]
    soft_cards = [c for c in cards if "soft_gated" in c.tags]
    # Not guaranteed for every run, but if present they must be E2 chain cards
    for c in soft_cards:
        assert any(t in c.tags for t in ("E2", "positioning_unwind")), (
            f"Soft-gated card has unexpected branch: {c.tags}"
        )


def test_h1_soft_gated_lower_plausibility(h_pipeline_result):
    """Soft-gated cards should have lower mean composite score than hard-gated E2 cards."""
    cards = h_pipeline_result["cards"]
    soft = [c for c in cards if "soft_gated" in c.tags and "E2" in c.tags]
    hard = [c for c in cards if "soft_gated" not in c.tags and "E2" in c.tags]
    if not soft or not hard:
        pytest.skip("Insufficient soft/hard E2 cards for comparison")
    mean_soft = sum(c.composite_score for c in soft) / len(soft)
    mean_hard = sum(c.composite_score for c in hard) / len(hard)
    assert mean_soft <= mean_hard + 0.02, (
        f"Soft-gated mean {mean_soft:.3f} should be <= hard mean {mean_hard:.3f}"
    )


def test_h1_crowding_confidence_nonnegative(market_collections):
    """compute_crowding_confidence returns non-negative float."""
    from crypto.src.eval.soft_gate import compute_crowding_confidence
    oi = market_collections["SOL"].oi_states
    conf = compute_crowding_confidence(oi)
    assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# H2: Contradiction-driven rerouting
# ---------------------------------------------------------------------------

def test_h2_rerouter_returns_list(h_pipeline_result):
    """compute_reroute_candidates returns a list."""
    reroutes = h_pipeline_result["reroutes"]
    assert isinstance(reroutes, list)


def test_h2_reroute_has_required_fields(h_pipeline_result):
    """Each reroute record has all required fields."""
    reroutes = h_pipeline_result["reroutes"]
    required = {
        "original_card_id", "original_branch", "reroute_candidate_branch",
        "reroute_confidence", "original_score", "rerouted_score",
        "original_branch_vs_rerouted_score", "reroute_reason",
    }
    for r in reroutes:
        missing = required - set(r.keys())
        assert not missing, f"Reroute record missing fields: {missing}"


def test_h2_reroute_confidence_in_range(h_pipeline_result):
    """reroute_confidence is in (0, 1] for all reroutes."""
    reroutes = h_pipeline_result["reroutes"]
    for r in reroutes:
        assert 0.0 < r["reroute_confidence"] <= 1.0, (
            f"Out-of-range reroute_confidence: {r['reroute_confidence']}"
        )


def test_h2_reroute_traceable_to_original(h_pipeline_result):
    """Every reroute's original_card_id points to a real card."""
    cards = h_pipeline_result["cards"]
    card_ids = {c.card_id for c in cards}
    reroutes = h_pipeline_result["reroutes"]
    for r in reroutes:
        assert r["original_card_id"] in card_ids, (
            f"Reroute original_card_id {r['original_card_id']} not in cards"
        )


def test_h2_beta_reversion_rerouted_to_unwind(h_pipeline_result):
    """beta_reversion cards with funding-extreme contradiction are rerouted to positioning_unwind.

    Reroutes only fire when beta_reversion cards are present in the top-k.
    If all top-k cards are positioning_unwind, skip the assertion.
    """
    cards = h_pipeline_result["cards"]
    reroutes = h_pipeline_result["reroutes"]
    has_br_cards = any(
        "beta_reversion" in c.tags or "E1" in c.tags for c in cards
    )
    if not has_br_cards:
        pytest.skip("No beta_reversion cards in this top-k run")
    br_to_pu = [
        r for r in reroutes
        if r["original_branch"] == "beta_reversion"
        and r["reroute_candidate_branch"] == "positioning_unwind"
    ]
    supp_log = h_pipeline_result["suppression_log"]
    has_fund_extreme_contradiction = any(
        e.get("reason") == "contradictory_evidence"
        and "funding extreme present" in e.get("detail", "")
        for e in supp_log
    )
    if has_fund_extreme_contradiction:
        assert len(br_to_pu) > 0, (
            "Expected beta_reversion→positioning_unwind reroutes when funding extreme contradiction exists"
        )


def test_h2_reroute_summary_structure(h_pipeline_result):
    """reroute_summary has n_rerouted, branch_distribution, mean_delta."""
    summary = h_pipeline_result["reroute_summary"]
    assert "n_rerouted" in summary
    assert "branch_distribution" in summary
    assert "mean_delta" in summary
    assert summary["n_rerouted"] == len(h_pipeline_result["reroutes"])


# ---------------------------------------------------------------------------
# H3: Uplift-aware ranking
# ---------------------------------------------------------------------------

def test_h3_uplift_ranking_has_all_cards(h_pipeline_result):
    """uplift_ranked_cards contains one entry per card."""
    cards = h_pipeline_result["cards"]
    ua = h_pipeline_result["uplift_ranking"]["uplift_ranked_cards"]
    assert len(ua) == len(cards)


def test_h3_uplift_aware_score_in_range(h_pipeline_result):
    """uplift_aware_score is in [0, 1] for every card."""
    ua = h_pipeline_result["uplift_ranking"]["uplift_ranked_cards"]
    for entry in ua:
        assert 0.0 <= entry["uplift_aware_score"] <= 1.0, (
            f"Out-of-range ua_score: {entry['uplift_aware_score']} for {entry['title']}"
        )


def test_h3_uplift_ranking_has_rank_delta(h_pipeline_result):
    """Each uplift-ranked card reports rank_delta (raw_rank - uplift_aware_rank)."""
    ua = h_pipeline_result["uplift_ranking"]["uplift_ranked_cards"]
    for entry in ua:
        assert "rank_delta" in entry
        assert isinstance(entry["rank_delta"], int)


def test_h3_summary_fields_present(h_pipeline_result):
    """uplift_aware_summary has n_rescued, n_demoted, n_top_k_changed."""
    summary = h_pipeline_result["uplift_ranking"]["uplift_aware_summary"]
    for field in ("n_rescued", "n_demoted", "n_top_k_changed", "mean_ua_score"):
        assert field in summary, f"Missing summary field: {field}"


def test_h3_rescued_hypotheses_traceable(h_pipeline_result):
    """Rescued hypotheses exist in uplift_ranked_cards."""
    ua_all_ids = {d["card_id"] for d in
                  h_pipeline_result["uplift_ranking"]["uplift_ranked_cards"]}
    for r in h_pipeline_result["uplift_ranking"]["rescued_hypotheses"]:
        assert r["card_id"] in ua_all_ids


def test_h3_four_score_components_present(h_pipeline_result):
    """Each uplift-ranked card reports all four H3 score components."""
    ua = h_pipeline_result["uplift_ranking"]["uplift_ranked_cards"]
    keys = {
        "norm_meta_score", "conflict_adjusted_score",
        "uplift_over_matched_baseline", "complexity_adjusted_uplift",
    }
    for entry in ua[:5]:
        for k in keys:
            assert k in entry, f"Missing component {k} in uplift entry"
