"""Sprint J tests: J1 grammar disambiguation gate — beta_reversion vs positioning_unwind.

Coverage:
  J1 gate in _e1_transient_aggression_chain:
    - fires when funding_extreme AND OI_accumulation both present
    - does NOT fire when only one condition is met
    - suppression entry has j1_discriminative_gate=True flag
    - NoPersistentAggressionNode NOT built when J1 fires
  Rerouter J1 high-confidence rule:
    - fires when j1 gate suppression present in log
    - confidence == 0.85 (higher than standard 0.70)
  Pipeline integration:
    - run_009 produces 0 reject_conflicted cards
    - run_009 produces 0 reroutes (with seed=42 / SOL funding-extreme scenario)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import Optional

from src.kg.base import KGNode, KGEdge, KGraph
from src.schema.market_state import (
    MarketStateCollection,
    FundingState,
    OIState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_merged_kg(
    *,
    has_corr_break: bool = True,
    funding_extreme_assets: list[str] | None = None,
    aggression_burst_assets: list[str] | None = None,
    premium_assets: list[str] | None = None,
    corr_break_score: float = 0.5,
    a1: str = "HYPE",
    a2: str = "SOL",
) -> KGraph:
    """Build a minimal merged KG for chain grammar tests."""
    kg = KGraph(family="test_merged")
    if has_corr_break:
        nid = f"corr:{a1}:{a2}"
        kg.add_node(KGNode(nid, "CorrelationNode", {
            "asset_a": a1, "asset_b": a2,
            "is_break": True,
            "corr_break_score": corr_break_score,
            "correlation": 0.05,
        }))

    for asset in (funding_extreme_assets or []):
        fid = f"funding:{asset}:0"
        kg.add_node(KGNode(fid, "FundingNode", {
            "asset": asset, "is_extreme": True, "z_score": 3.5,
        }))

    for asset in (aggression_burst_assets or []):
        for idx in range(3):  # 3 burst windows per asset
            aid = f"aggr:{asset}:{idx}"
            kg.add_node(KGNode(aid, "AggressionNode", {
                "is_burst": True,
                "intensity": 1.5,
            }))

    for asset in (premium_assets or []):
        pid = f"prem:{asset}:0"
        kg.add_node(KGNode(pid, "PremiumDislocationNode", {
            "asset": asset, "dislocation": 0.03,
        }))

    return kg


def _make_collections(
    *,
    oi_accumulation_assets: list[str] | None = None,
    assets: list[str] | None = None,
) -> dict:
    """Build minimal MarketStateCollections for chain grammar tests."""
    all_assets = assets or ["HYPE", "SOL", "ETH", "BTC"]
    accum_set = set(oi_accumulation_assets or [])
    result = {}
    for a in all_assets:
        fundings = [
            FundingState(
                asset=a, timestamp_ms=0, funding_rate=0.001,
                annualised=0.365, z_score=1.0,
            )
        ]
        if a in accum_set:
            oi_states = [
                OIState(
                    asset=a, timestamp_ms=t * 1000,
                    oi=1000.0 + t * 10, oi_prev=1000.0 + (t - 1) * 10,
                    oi_change_pct=0.05 + t * 0.002,
                    state_score=min(1.0, 0.3 + t * 0.07),
                    build_duration=t + 1,
                    is_accumulation=True,
                    is_one_sided=True,
                )
                for t in range(5)
            ]
        else:
            oi_states = [
                OIState(
                    asset=a, timestamp_ms=t * 1000,
                    oi=1000.0, oi_prev=1000.0,
                    oi_change_pct=0.01,
                    state_score=0.1,
                    build_duration=1,
                    is_accumulation=False,
                    is_one_sided=False,
                )
                for t in range(3)
            ]
        result[a] = MarketStateCollection(
            asset=a,
            run_id="test_j1",
            fundings=fundings,
            oi_states=oi_states,
        )
    return result


# ---------------------------------------------------------------------------
# J1 gate unit tests
# ---------------------------------------------------------------------------

class TestJ1GateFiring:
    """J1 discriminative gate fires when funding_extreme AND OI_accum both present."""

    def _run_e1_transient(
        self, merged_kg: KGraph, collections: dict, a1: str = "HYPE", a2: str = "SOL"
    ) -> list[dict]:
        """Run _e1_transient_aggression_chain and return suppression log."""
        from src.kg.chain_grammar import _e1_transient_aggression_chain
        kg = KGraph(family="test_grammar")
        log: list[dict] = []
        corr_nid = f"corr:{a1}:{a2}"
        _e1_transient_aggression_chain(kg, merged_kg, collections, a1, a2, corr_nid, 0.5, log)
        return log, kg

    def test_j1_gate_fires_when_both_conditions_met(self):
        """If funding_extreme AND OI_accum both True → J1 gate suppresses E1 Chain 2."""
        merged_kg = _make_merged_kg(
            funding_extreme_assets=["SOL"],          # extreme funding
            aggression_burst_assets=["HYPE", "SOL"], # 3 bursts each → burst_min=3
        )
        collections = _make_collections(oi_accumulation_assets=["SOL"])  # OI accum

        log, kg = self._run_e1_transient(merged_kg, collections)

        j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
        assert len(j1_entries) == 1, "J1 gate should fire exactly once"
        assert j1_entries[0]["reason"] == "contradictory_evidence"
        assert "funding extreme + OI accumulation" in j1_entries[0]["detail"]

    def test_j1_gate_prevents_npa_node_creation(self):
        """When J1 fires, NoPersistentAggressionNode must NOT be created."""
        merged_kg = _make_merged_kg(
            funding_extreme_assets=["SOL"],
            aggression_burst_assets=["HYPE", "SOL"],
        )
        collections = _make_collections(oi_accumulation_assets=["SOL"])

        log, kg = self._run_e1_transient(merged_kg, collections)

        npa_nodes = [n for n in kg.nodes if "no_persistent_aggr" in n]
        assert npa_nodes == [], "NoPersistentAggressionNode must not be built when J1 fires"
        recoup_nodes = [n for n in kg.nodes if "correlation_recoupling" in n]
        assert recoup_nodes == [], "CorrelationRecouplingNode must not be built when J1 fires"

    def test_j1_gate_does_not_fire_without_funding_extreme(self):
        """If funding_extreme = False, J1 gate must NOT suppress even with OI_accum."""
        merged_kg = _make_merged_kg(
            funding_extreme_assets=[],               # no extreme funding
            aggression_burst_assets=["HYPE", "SOL"],
        )
        collections = _make_collections(oi_accumulation_assets=["SOL"])

        log, kg = self._run_e1_transient(merged_kg, collections)

        j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
        assert j1_entries == [], "J1 gate must not fire without funding_extreme"
        # With 3 burst windows each (burst_min=3, <= 4), chain should proceed
        npa_nodes = [n for n in kg.nodes if "no_persistent_aggr" in n]
        assert len(npa_nodes) == 1, "NoPersistentAggressionNode should be built without J1 gate"

    def test_j1_gate_does_not_fire_without_oi_accumulation(self):
        """If OI_accum = False, J1 gate must NOT suppress even with funding_extreme."""
        merged_kg = _make_merged_kg(
            funding_extreme_assets=["SOL"],
            aggression_burst_assets=["HYPE", "SOL"],
        )
        collections = _make_collections(oi_accumulation_assets=[])  # no OI accum

        log, kg = self._run_e1_transient(merged_kg, collections)

        j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
        assert j1_entries == [], "J1 gate must not fire without OI_accumulation"

    def test_j1_gate_does_not_fire_for_true_beta_reversion(self):
        """ETH/BTC scenario: no funding_extreme, no OI_accum → J1 must not fire."""
        merged_kg = _make_merged_kg(
            a1="ETH", a2="BTC",
            funding_extreme_assets=[],
            aggression_burst_assets=["ETH", "BTC"],
        )
        collections = _make_collections(
            assets=["ETH", "BTC"],
            oi_accumulation_assets=[],
        )

        log, kg = self._run_e1_transient(merged_kg, collections, a1="ETH", a2="BTC")

        j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
        assert j1_entries == [], "J1 gate must NOT fire for true beta_reversion (ETH/BTC)"


# ---------------------------------------------------------------------------
# J1 suppression log flag
# ---------------------------------------------------------------------------

class TestJ1SuppressionFlag:
    """J1 suppression entries are tagged for auditability."""

    def test_j1_flag_present_in_suppression_entry(self):
        """Suppression entry from J1 gate must carry j1_discriminative_gate=True."""
        from src.kg.chain_grammar import _e1_transient_aggression_chain
        merged_kg = _make_merged_kg(
            funding_extreme_assets=["HYPE"],
            aggression_burst_assets=["HYPE", "SOL"],
        )
        collections = _make_collections(oi_accumulation_assets=["HYPE"])
        kg = KGraph(family="test")
        log: list[dict] = []
        _e1_transient_aggression_chain(kg, merged_kg, collections, "HYPE", "SOL",
                                       "corr:HYPE:SOL", 0.4, log)
        j1_entries = [e for e in log if e.get("j1_discriminative_gate")]
        assert j1_entries, "At least one J1 entry expected"
        for entry in j1_entries:
            assert entry["j1_discriminative_gate"] is True
            assert entry["neg_evidence_taxonomy"] == "contradictory_evidence"
            assert entry["chain"] == "beta_reversion_transient_aggr"


# ---------------------------------------------------------------------------
# Rerouter: J1 high-confidence rule
# ---------------------------------------------------------------------------

class TestRerouterJ1Rule:
    """J1 high-confidence reroute rule has correct confidence and source branch."""

    def test_j1_reroute_rule_exists_with_high_confidence(self):
        """_REROUTE_RULES must include a J1 rule with confidence=0.85."""
        from src.eval.rerouter import _REROUTE_RULES
        j1_rules = [
            r for r in _REROUTE_RULES
            if r.get("source_branch") == "beta_reversion"
            and "j1_discriminative_gate" in r.get("reason", "").lower()
               or "funding extreme + OI" in r.get("reason", "")
               or r.get("trigger_detail_keyword", "").startswith("funding extreme + OI")
        ]
        assert j1_rules, "J1 reroute rule must exist in _REROUTE_RULES"
        conf = j1_rules[0]["confidence"]
        assert conf >= 0.80, f"J1 reroute confidence must be >= 0.80, got {conf}"
        assert j1_rules[0]["reroute_to"] == "positioning_unwind"

    def test_j1_reroute_fires_for_j1_suppression(self):
        """Rerouter generates a reroute record when J1 gate suppression is present."""
        from src.eval.rerouter import compute_reroute_candidates
        from src.schema.hypothesis_card import HypothesisCard, ScoreBundle
        from src.schema.task_status import SecrecyLevel, ValidationStatus

        # Build a beta_reversion card for HYPE/SOL
        scores = ScoreBundle(
            plausibility=0.7, novelty=0.6, actionability=0.7,
            traceability=0.8, reproducibility=0.5, secrecy=0.75,
        )
        card = HypothesisCard(
            card_id="test-j1-card",
            version=1,
            created_at="2026-04-15T00:00:00+00:00",
            title="E1 beta reversion: (HYPE,SOL) — transient aggression",
            claim="...",
            mechanism="...",
            evidence_nodes=["n1"],
            evidence_edges=[],
            operator_trace=["chain_grammar"],
            secrecy_level=SecrecyLevel.INTERNAL_WATCHLIST,
            validation_status=ValidationStatus.WEAKLY_SUPPORTED,
            scores=scores,
            composite_score=0.70,
            run_id="test",
            kg_families=["chain_grammar"],
            tags=["E1", "beta_reversion"],
        )

        suppression_log = [
            {
                "chain": "beta_reversion_transient_aggr",
                "pair": "HYPE/SOL",
                "reason": "contradictory_evidence",
                "detail": "funding extreme + OI accumulation both present — aggression is unwind-context signal",
                "neg_evidence_taxonomy": "contradictory_evidence",
                "j1_discriminative_gate": True,
            }
        ]
        contradiction_metrics = {
            "test-j1-card": {
                "contradiction_severity": 6.0,
                "conflict_penalty": 0.23,
            }
        }

        reroutes = compute_reroute_candidates([card], contradiction_metrics, suppression_log, 10)
        j1_reroutes = [
            r for r in reroutes
            if r["reroute_candidate_branch"] == "positioning_unwind"
            and r["reroute_confidence"] >= 0.80
        ]
        assert j1_reroutes, "J1 reroute to positioning_unwind should fire"
        assert j1_reroutes[0]["reroute_confidence"] == 0.85


# ---------------------------------------------------------------------------
# Integration: run_009 produces 0 reject_conflicted / 0 reroutes
# ---------------------------------------------------------------------------

class TestRun009Integration:
    """Integration test: run_009 pipeline with J1 fix must produce clean output."""

    def test_run009_zero_reject_conflicted(self):
        """run_009 (J1 fix, seed=42) must produce 0 reject_conflicted cards."""
        from src.pipeline import PipelineConfig, run_pipeline
        import json, tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                run_id="test_j1_integration",
                seed=42,
                n_minutes=120,
                assets=["HYPE", "ETH", "BTC", "SOL"],
                top_k=60,
                output_dir=tmpdir,
            )
            run_pipeline(config)

            with open(os.path.join(tmpdir, "test_j1_integration", "i1_decision_tiers.json")) as f:
                tiers = json.load(f)

        reject = [c for c in tiers["tier_assignments"]
                  if c["decision_tier"] == "reject_conflicted"]
        assert reject == [], (
            f"Expected 0 reject_conflicted with J1 fix, got {len(reject)}: "
            + str([c["title"] for c in reject])
        )

    def test_run009_zero_reroutes(self):
        """run_009 (J1 fix, seed=42) must produce 0 reroute records."""
        from src.pipeline import PipelineConfig, run_pipeline
        import json, tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                run_id="test_j1_integration_reroutes",
                seed=42,
                n_minutes=120,
                assets=["HYPE", "ETH", "BTC", "SOL"],
                top_k=60,
                output_dir=tmpdir,
            )
            run_pipeline(config)

            with open(os.path.join(tmpdir, "test_j1_integration_reroutes",
                                   "h2_reroute_candidates.json")) as f:
                reroutes = json.load(f)

        assert reroutes == [], (
            f"Expected 0 reroutes with J1 fix, got {len(reroutes)}"
        )

    def test_run009_preserves_eth_btc_beta_reversion(self):
        """ETH/BTC beta_reversion card must remain actionable_watch after J1 fix."""
        from src.pipeline import PipelineConfig, run_pipeline
        import json, tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            config = PipelineConfig(
                run_id="test_j1_eth_btc",
                seed=42,
                n_minutes=120,
                assets=["HYPE", "ETH", "BTC", "SOL"],
                top_k=60,
                output_dir=tmpdir,
            )
            run_pipeline(config)

            with open(os.path.join(tmpdir, "test_j1_eth_btc", "i1_decision_tiers.json")) as f:
                tiers = json.load(f)

        eth_btc_br = [
            c for c in tiers["tier_assignments"]
            if "ETH,BTC" in c["title"] or "ETH/BTC" in c["title"]
            if "beta_reversion" in c.get("branch", "")
        ]
        assert eth_btc_br, "At least one ETH/BTC beta_reversion card must exist"
        actionable = [c for c in eth_btc_br if c["decision_tier"] == "actionable_watch"]
        assert actionable, (
            f"ETH/BTC beta_reversion must be actionable_watch, got: "
            + str([c["decision_tier"] for c in eth_btc_br])
        )
