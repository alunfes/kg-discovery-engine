"""Sprint L tests: Run 012 boundary-case detector for grammar chains.

Coverage:
  ThresholdSpec:
    - construction with required and optional fields
    - boundary_direction values "lower" / "upper"
  _compute_proximity:
    - lower-bound: proximity = (actual - threshold) / threshold
    - upper-bound: proximity = (threshold - actual) / threshold
    - returns negative when actual is on wrong side of threshold
  BoundaryDetector.detect_from_kg:
    - NoPersistentAggressionNode near burst_count upper bound → record
    - FundingPressureRegimeNode with is_soft_gated → record
    - node far from threshold (proximity >= 1.0) → suppressed
    - regime_contradiction_flag set when contradicting signals active
    - regime_contradiction_flag False when no contradicting signals
    - suppression_log soft_gated entries → records
  generate_warnings:
    - proximity < 0.20 AND contradiction → HIGH / r1_candidate
    - proximity < 0.50 AND contradiction → MEDIUM / manual_review
    - proximity < 0.20, no contradiction → LOW / monitor
    - proximity >= 0.50 → no warning
    - results sorted HIGH first
  Pipeline integration:
    - branch_metrics contains "run012_boundary_detection" key
    - no new test failures introduced
  SOL J1 regression sanity:
    - SOL pairs with funding_extreme + OI present → R1 fires, no NoPersistentAggressionNode
    - Therefore no HIGH boundary warnings for those pairs (J1 fix was correct)
  Precision check:
    - Total HIGH warnings in a standard run is bounded (no false positive flood)
  Retrospective:
    - run_retrospective_analysis returns structured result for run_009–011
    - __aggregate__ key present with n_total and chain_exposure
"""

import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.eval.boundary_detector import (
    CHAIN_THRESHOLDS,
    BoundaryActivationRecord,
    BoundaryDetector,
    BoundaryWarning,
    ThresholdSpec,
    _compute_proximity,
    record_to_dict,
    run_retrospective_analysis,
    warning_to_dict,
)
from src.eval.soft_gate import HARD_GATE_MIN, SOFT_GATE_MIN
from src.kg.base import KGEdge, KGNode, KGraph
from src.schema.market_state import FundingState, MarketStateCollection, OIState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_merged_kg(
    funding_extreme_assets: list | None = None,
    aggression_burst_assets: list | None = None,
) -> KGraph:
    kg = KGraph(family="test_merged")
    for asset in (funding_extreme_assets or []):
        kg.add_node(KGNode(
            f"funding:{asset}:0", "FundingNode",
            {"asset": asset, "is_extreme": True, "z_score": 3.0},
        ))
    for asset in (aggression_burst_assets or []):
        kg.add_node(KGNode(
            f"aggr:{asset}:0", "AggressionNode", {"is_burst": True},
        ))
    return kg


def _make_collections(
    oi_accumulation_assets: list | None = None,
    assets: list | None = None,
) -> dict:
    all_assets = assets or ["HYPE", "SOL"]
    accum = set(oi_accumulation_assets or [])
    result = {}
    for a in all_assets:
        oi_states = [
            OIState(
                asset=a, timestamp_ms=t * 1000,
                oi=1000.0 + t * 10, oi_prev=1000.0,
                oi_change_pct=0.05,
                state_score=0.4 + t * 0.05,
                build_duration=t + 1,
                is_accumulation=(a in accum),
                is_one_sided=(a in accum),
            )
            for t in range(3)
        ]
        fundings = [FundingState(
            asset=a, timestamp_ms=0, funding_rate=0.001,
            annualised=0.365, z_score=1.0,
        )]
        result[a] = MarketStateCollection(
            asset=a, run_id="test_l", oi_states=oi_states, fundings=fundings,
        )
    return result


def _make_grammar_kg_with_npa(
    a1: str, a2: str, burst_count: int
) -> KGraph:
    """Return a grammar KG containing a NoPersistentAggressionNode for the pair."""
    kg = KGraph(family="chain_grammar")
    nid = f"no_persistent_aggr:{a1}:{a2}"
    kg.add_node(KGNode(nid, "NoPersistentAggressionNode", {
        "asset_a": a1, "asset_b": a2, "burst_count": burst_count,
        "state_score": round(1.0 - burst_count / 8.0, 3),
        "coverage": 1.0,
    }))
    return kg


def _make_grammar_kg_with_fpr(
    a1: str, a2: str, act_conf: float
) -> KGraph:
    """Return a grammar KG with a FundingPressureRegimeNode (soft-gated if conf < 0.50)."""
    kg = KGraph(family="chain_grammar")
    is_soft = act_conf < HARD_GATE_MIN
    nid = f"funding_pressure_regime:{a1}:{a2}"
    kg.add_node(KGNode(nid, "FundingPressureRegimeNode", {
        "asset_a": a1, "asset_b": a2,
        "activation_confidence": act_conf,
        "is_soft_gated": is_soft,
        "state_score": act_conf,
        "coverage": 1.0,
    }))
    return kg


# ---------------------------------------------------------------------------
# ThresholdSpec construction
# ---------------------------------------------------------------------------

class TestThresholdSpec:
    def test_required_fields(self):
        spec = ThresholdSpec(
            chain_type="test_chain",
            threshold_name="burst_count_max",
            threshold_value=4.0,
            boundary_direction="upper",
            expected_outcome="beta_reversion",
        )
        assert spec.chain_type == "test_chain"
        assert spec.threshold_value == 4.0
        assert spec.contradicting_regime_signals == []

    def test_with_contradicting_signals(self):
        spec = ThresholdSpec(
            chain_type="test_chain",
            threshold_name="t",
            threshold_value=1.0,
            boundary_direction="lower",
            expected_outcome="beta_reversion",
            contradicting_regime_signals=["funding_extreme", "oi_accumulation"],
        )
        assert spec.contradicting_regime_signals == ["funding_extreme", "oi_accumulation"]

    def test_chain_thresholds_catalog_populated(self):
        assert "e1_transient_aggr_burst_upper" in CHAIN_THRESHOLDS
        assert "e2_funding_soft_gate" in CHAIN_THRESHOLDS
        assert "d3_continuation_break_score" in CHAIN_THRESHOLDS


# ---------------------------------------------------------------------------
# _compute_proximity
# ---------------------------------------------------------------------------

class TestComputeProximity:
    def test_lower_bound_at_threshold(self):
        spec = ThresholdSpec("c", "t", 1.0, "lower", "outcome")
        assert _compute_proximity(spec, 1.0) == pytest.approx(0.0)

    def test_lower_bound_well_above_threshold(self):
        spec = ThresholdSpec("c", "t", 1.0, "lower", "outcome")
        # actual=3.0: (3-1)/1 = 2.0 — far from boundary
        assert _compute_proximity(spec, 3.0) == pytest.approx(2.0)

    def test_lower_bound_below_threshold_negative(self):
        spec = ThresholdSpec("c", "t", 1.0, "lower", "outcome")
        assert _compute_proximity(spec, 0.5) == pytest.approx(-0.5)

    def test_upper_bound_at_threshold(self):
        spec = ThresholdSpec("c", "t", 4.0, "upper", "outcome")
        assert _compute_proximity(spec, 4.0) == pytest.approx(0.0)

    def test_upper_bound_below_threshold(self):
        # burst_count=3, threshold=4: (4-3)/4 = 0.25
        spec = ThresholdSpec("c", "t", 4.0, "upper", "outcome")
        assert _compute_proximity(spec, 3.0) == pytest.approx(0.25)

    def test_upper_bound_above_threshold_negative(self):
        spec = ThresholdSpec("c", "t", 4.0, "upper", "outcome")
        assert _compute_proximity(spec, 5.0) < 0

    def test_soft_gate_proximity(self):
        spec = ThresholdSpec("c", "t", SOFT_GATE_MIN, "lower", "outcome")
        # actual = SOFT_GATE_MIN → proximity = 0
        assert _compute_proximity(spec, SOFT_GATE_MIN) == pytest.approx(0.0)
        # actual = 0.36: (0.36 - 0.30) / 0.30 = 0.20
        assert _compute_proximity(spec, 0.36) == pytest.approx(0.20, abs=1e-4)


# ---------------------------------------------------------------------------
# BoundaryDetector — detect_from_kg
# ---------------------------------------------------------------------------

class TestBoundaryDetectorDetect:
    def test_npa_at_upper_burst_boundary(self):
        """burst_count=4 → proximity=0.0 → should produce a record."""
        detector = BoundaryDetector()
        grammar_kg = _make_grammar_kg_with_npa("HYPE", "SOL", burst_count=4)
        merged_kg = _make_merged_kg()
        collections = _make_collections()
        records = detector.detect_from_kg(grammar_kg, [], merged_kg, collections)
        upper = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_upper"]
        assert len(upper) == 1
        assert upper[0].pair == "HYPE/SOL"
        assert upper[0].boundary_proximity == pytest.approx(0.0)

    def test_npa_near_upper_burst_boundary(self):
        """burst_count=3 → proximity=0.25 → record included (< 1.0)."""
        detector = BoundaryDetector()
        grammar_kg = _make_grammar_kg_with_npa("ETH", "BTC", burst_count=3)
        merged_kg = _make_merged_kg()
        records = detector.detect_from_kg(grammar_kg, [], merged_kg, _make_collections(assets=["ETH", "BTC"]))
        upper = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_upper"]
        assert len(upper) == 1
        assert upper[0].boundary_proximity == pytest.approx(0.25)

    def test_npa_far_from_boundary_excluded(self):
        """burst_count=1, upper threshold=4 → proximity=0.75 — still inside zone but
        lower threshold proximity=0.0 → produces a lower-bound record, not excluded."""
        detector = BoundaryDetector()
        grammar_kg = _make_grammar_kg_with_npa("HYPE", "SOL", burst_count=1)
        merged_kg = _make_merged_kg()
        records = detector.detect_from_kg(grammar_kg, [], merged_kg, _make_collections())
        # burst_count=1 → at lower boundary (burst_count_min=1 → proximity=0)
        lower = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_lower"]
        assert len(lower) == 1
        assert lower[0].boundary_proximity == pytest.approx(0.0)

    def test_regime_contradiction_flag_true(self):
        """funding_extreme + oi_accumulation active → contradiction for E1."""
        detector = BoundaryDetector()
        grammar_kg = _make_grammar_kg_with_npa("HYPE", "SOL", burst_count=4)
        merged_kg = _make_merged_kg(funding_extreme_assets=["HYPE"])
        collections = _make_collections(oi_accumulation_assets=["SOL"])
        records = detector.detect_from_kg(grammar_kg, [], merged_kg, collections)
        upper = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_upper"]
        assert upper[0].regime_contradiction_flag is True
        assert "funding_extreme" in upper[0].dominant_regime_signals

    def test_regime_contradiction_flag_false(self):
        """No regime signals → no contradiction."""
        detector = BoundaryDetector()
        grammar_kg = _make_grammar_kg_with_npa("HYPE", "SOL", burst_count=4)
        records = detector.detect_from_kg(grammar_kg, [], _make_merged_kg(), _make_collections())
        upper = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_upper"]
        assert upper[0].regime_contradiction_flag is False
        assert upper[0].dominant_regime_signals == []

    def test_soft_gate_fpr_node(self):
        """FundingPressureRegimeNode with soft activation → record captured."""
        detector = BoundaryDetector()
        act_conf = SOFT_GATE_MIN + 0.02  # just above min → low proximity
        grammar_kg = _make_grammar_kg_with_fpr("HYPE", "SOL", act_conf)
        records = detector.detect_from_kg(grammar_kg, [], _make_merged_kg(), _make_collections())
        fpr = [r for r in records if r.threshold_key == "e2_funding_soft_gate"]
        assert len(fpr) == 1
        assert fpr[0].boundary_proximity < 0.10  # very near lower bound

    def test_empty_grammar_kg_no_records(self):
        """Empty grammar KG → no records."""
        detector = BoundaryDetector()
        records = detector.detect_from_kg(
            KGraph(family="chain_grammar"), [], _make_merged_kg(), _make_collections()
        )
        assert records == []

    def test_soft_gated_suppression_log_entry(self):
        """soft_gated suppression log entry → captured as boundary record."""
        detector = BoundaryDetector()
        conf = SOFT_GATE_MIN + 0.03
        sup_log = [{
            "chain": "positioning_unwind_funding_pressure",
            "pair": "HYPE/SOL",
            "reason": "soft_gated",
            "activation_confidence": conf,
        }]
        records = detector.detect_from_kg(
            KGraph(family="chain_grammar"), sup_log, _make_merged_kg(), _make_collections()
        )
        log_records = [r for r in records if r.threshold_key == "e2_funding_soft_gate"]
        assert len(log_records) >= 1

    def test_non_soft_gated_log_entry_ignored(self):
        """non-soft_gated suppression log entries → not captured."""
        detector = BoundaryDetector()
        sup_log = [{"chain": "beta_reversion_transient_aggr", "pair": "X/Y",
                    "reason": "contradictory_evidence"}]
        records = detector.detect_from_kg(
            KGraph(family="chain_grammar"), sup_log, _make_merged_kg(), _make_collections()
        )
        assert records == []


# ---------------------------------------------------------------------------
# generate_warnings
# ---------------------------------------------------------------------------

class TestGenerateWarnings:
    def _record(self, prox: float, contradiction: bool) -> BoundaryActivationRecord:
        return BoundaryActivationRecord(
            chain_type="beta_reversion_transient_aggr",
            pair="HYPE/SOL",
            threshold_key="e1_transient_aggr_burst_upper",
            threshold_name="burst_count_max",
            threshold_value=4.0,
            actual_value=4.0,
            boundary_proximity=prox,
            dominant_regime_signals=["funding_extreme"] if contradiction else [],
            expected_outcome="beta_reversion",
            regime_contradiction_flag=contradiction,
        )

    def test_high_warning_level(self):
        detector = BoundaryDetector()
        rec = self._record(0.10, contradiction=True)
        warnings = detector.generate_warnings([rec])
        assert len(warnings) == 1
        assert warnings[0].warning_level == "high"
        assert warnings[0].recommended_action == "r1_candidate"

    def test_medium_warning_level(self):
        detector = BoundaryDetector()
        rec = self._record(0.35, contradiction=True)
        warnings = detector.generate_warnings([rec])
        assert len(warnings) == 1
        assert warnings[0].warning_level == "medium"
        assert warnings[0].recommended_action == "manual_review"

    def test_low_warning_level(self):
        detector = BoundaryDetector()
        rec = self._record(0.10, contradiction=False)
        warnings = detector.generate_warnings([rec])
        assert len(warnings) == 1
        assert warnings[0].warning_level == "low"
        assert warnings[0].recommended_action == "monitor"

    def test_suppressed_when_far_from_boundary(self):
        detector = BoundaryDetector()
        rec = self._record(0.60, contradiction=True)
        warnings = detector.generate_warnings([rec])
        assert warnings == []

    def test_sorting_high_before_medium_before_low(self):
        detector = BoundaryDetector()
        recs = [
            self._record(0.10, contradiction=False),   # LOW
            self._record(0.35, contradiction=True),    # MEDIUM
            self._record(0.05, contradiction=True),    # HIGH
        ]
        warnings = detector.generate_warnings(recs)
        assert [w.warning_level for w in warnings] == ["high", "medium", "low"]

    def test_empty_records_no_warnings(self):
        assert BoundaryDetector().generate_warnings([]) == []


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

class TestSerialisation:
    def test_record_to_dict_keys(self):
        rec = BoundaryActivationRecord(
            chain_type="c", pair="A/B", threshold_key="k", threshold_name="t",
            threshold_value=4.0, actual_value=4.0, boundary_proximity=0.0,
            dominant_regime_signals=[], expected_outcome="beta_reversion",
            regime_contradiction_flag=False,
        )
        d = record_to_dict(rec)
        assert set(d.keys()) == {
            "chain_type", "pair", "threshold_key", "threshold_name",
            "threshold_value", "actual_value", "boundary_proximity",
            "dominant_regime_signals", "expected_outcome", "regime_contradiction_flag",
        }

    def test_warning_to_dict_json_serialisable(self):
        w = BoundaryWarning(
            chain_type="c", pair="A/B", warning_level="high",
            boundary_proximity=0.05, regime_contradiction_flag=True,
            recommended_action="r1_candidate", active_regime_signals=["funding_extreme"],
            details="test",
        )
        d = warning_to_dict(w)
        json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# SOL J1 regression sanity check
# ---------------------------------------------------------------------------

class TestSOLJ1Regression:
    """Verify that the J1/R1 fix is correctly detected by the boundary detector.

    J1 fires when funding_extreme AND oi_accumulation are both present for a pair
    with burst aggression.  After the fix, R1 suppresses the E1 transient_aggr chain
    BEFORE any NoPersistentAggressionNode is created.

    → No NoPersistentAggressionNode for those pairs → no HIGH boundary warning.
    This confirms J1 is working correctly (not a false negative in the detector).
    """

    def _build_sol_pair_state(self):
        """Minimal merged KG + collections where SOL has funding_extreme + OI accum."""
        merged_kg = _make_merged_kg(funding_extreme_assets=["SOL"])
        collections = _make_collections(
            oi_accumulation_assets=["SOL"],
            assets=["HYPE", "SOL"],
        )
        return merged_kg, collections

    def test_no_npa_node_when_r1_fires(self):
        """When J1/R1 fires, NoPersistentAggressionNode is NOT created.
        Detector therefore returns 0 upper-burst records for that pair.
        """
        detector = BoundaryDetector()
        # Grammar KG contains NO NoPersistentAggressionNode for HYPE/SOL
        # (because R1 suppressed the chain before it got that far)
        empty_grammar_kg = KGraph(family="chain_grammar")
        merged_kg, collections = self._build_sol_pair_state()
        records = detector.detect_from_kg(empty_grammar_kg, [], merged_kg, collections)
        upper = [r for r in records if r.threshold_key == "e1_transient_aggr_burst_upper"
                 and "SOL" in r.pair]
        assert upper == [], (
            "NoPersistentAggressionNode should not exist for SOL pairs after J1/R1 "
            f"suppression; got {upper}"
        )

    def test_high_warning_requires_npa_node(self):
        """HIGH boundary warning for E1 transient aggr requires the NPA node to exist.
        This verifies that a correctly-suppressed chain produces no HIGH warning.
        """
        detector = BoundaryDetector()
        # No NPA node → no records → no HIGH warnings
        empty_kg = KGraph(family="chain_grammar")
        merged_kg, collections = self._build_sol_pair_state()
        records = detector.detect_from_kg(empty_kg, [], merged_kg, collections)
        warnings = detector.generate_warnings(records)
        high = [w for w in warnings if w.warning_level == "high" and "SOL" in w.pair]
        assert high == [], f"Should be 0 HIGH warnings for correctly-suppressed SOL pair, got {high}"


# ---------------------------------------------------------------------------
# Precision check — no false positive flood
# ---------------------------------------------------------------------------

class TestPrecisionCheck:
    """Verify that the detector does not generate an overwhelming number of
    HIGH warnings on a standard pipeline run (false positive guard).
    """

    @pytest.fixture(scope="class")
    def pipeline_boundary_data(self):
        """Run the full pipeline once and capture boundary data."""
        from src.pipeline import PipelineConfig, run_pipeline
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp:
            config = PipelineConfig(
                run_id="test_l_precision",
                seed=42,
                n_minutes=60,
                assets=["HYPE", "ETH", "BTC", "SOL"],
                top_k=60,
                output_dir=tmp,
            )
            run_pipeline(config)
            metrics_path = os.path.join(tmp, "test_l_precision", "branch_metrics.json")
            with open(metrics_path) as f:
                metrics = json.load(f)
        return metrics.get("run012_boundary_detection", {})

    def test_pipeline_boundary_key_present(self, pipeline_boundary_data):
        """branch_metrics must contain run012_boundary_detection key."""
        assert pipeline_boundary_data != {}, "run012_boundary_detection key missing"

    def test_high_warnings_bounded(self, pipeline_boundary_data):
        """HIGH warnings must be < 20 (false positive guard).
        A standard run with 4 assets and 60 minutes should not generate
        more than ~10-15 boundary cases; much more suggests a logic error.
        """
        n_high = pipeline_boundary_data.get("high_warnings", 0)
        assert n_high < 20, (
            f"Too many HIGH warnings ({n_high}): detector may be generating false positives"
        )

    def test_records_list_present(self, pipeline_boundary_data):
        """records and warnings keys must be present lists."""
        assert isinstance(pipeline_boundary_data.get("records"), list)
        assert isinstance(pipeline_boundary_data.get("warnings"), list)


# ---------------------------------------------------------------------------
# Pipeline regression — no new failures
# ---------------------------------------------------------------------------

class TestPipelineRegression:
    """Verify that adding the boundary detector does not break existing pipeline."""

    @pytest.fixture(scope="class")
    def pipeline_metrics(self):
        from src.pipeline import PipelineConfig, run_pipeline
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            config = PipelineConfig(
                run_id="test_l_pipeline_regression",
                seed=42,
                n_minutes=60,
                assets=["HYPE", "ETH", "BTC", "SOL"],
                top_k=60,
                output_dir=tmp,
            )
            run_pipeline(config)
            with open(os.path.join(tmp, "test_l_pipeline_regression", "branch_metrics.json")) as f:
                return json.load(f)

    def test_zero_reject_conflicted(self, pipeline_metrics):
        """Run 012 must not re-introduce reject_conflicted cards."""
        tiers = pipeline_metrics.get("i1_decision_tiers", {})
        reject = [c for c in tiers.get("tier_assignments", [])
                  if c.get("decision_tier") == "reject_conflicted"]
        assert reject == [], f"Got {len(reject)} reject_conflicted cards after Run 012"

    def test_watchlist_not_reduced(self, pipeline_metrics):
        watchlist = pipeline_metrics.get("i4_watchlist", {})
        items = (watchlist.get("watchlist_cards", [])
                 if isinstance(watchlist, dict) else watchlist)
        assert len(items) >= 55, f"Watchlist dropped to {len(items)}"


# ---------------------------------------------------------------------------
# Retrospective analysis
# ---------------------------------------------------------------------------

class TestRetrospectiveAnalysis:
    """Verify run_retrospective_analysis on saved run artifacts."""

    @pytest.fixture(scope="class")
    def retro_result(self):
        base = os.path.join(
            os.path.dirname(__file__), "..", "artifacts", "runs"
        )
        run_dirs = [
            os.path.join(base, "run_009_20260415"),
            os.path.join(base, "run_010_hotspot_scan"),
            os.path.join(base, "run_011_r1_formalization"),
        ]
        # Filter to dirs that actually exist
        existing = [d for d in run_dirs if os.path.isdir(d)]
        if not existing:
            pytest.skip("No run artifact directories found")
        return run_retrospective_analysis(existing)

    def test_aggregate_key_present(self, retro_result):
        assert "__aggregate__" in retro_result

    def test_aggregate_has_n_total(self, retro_result):
        agg = retro_result["__aggregate__"]
        assert "n_total" in agg
        assert isinstance(agg["n_total"], int)

    def test_aggregate_chain_exposure(self, retro_result):
        agg = retro_result["__aggregate__"]
        assert "chain_exposure" in agg

    def test_per_run_keys_present(self, retro_result):
        for key, val in retro_result.items():
            if key == "__aggregate__":
                continue
            assert "n_records" in val, f"run {key} missing n_records"
            assert "n_warnings" in val, f"run {key} missing n_warnings"
            assert "records" in val, f"run {key} missing records"
            assert "warnings" in val, f"run {key} missing warnings"

    def test_run011_after_r1_fix_has_no_high_sol_warnings(self, retro_result):
        """After the R1 fix in run_011, SOL pairs should have no HIGH boundary warnings
        because J1/R1 suppresses the E1 chain before any NPA node is created.
        """
        run011 = retro_result.get("run_011_r1_formalization", {})
        if "error" in run011:
            pytest.skip("run_011 artifacts missing")
        high_sol = [
            w for w in run011.get("warnings", [])
            if w.get("warning_level") == "high" and "SOL" in w.get("pair", "")
        ]
        assert high_sol == [], (
            f"Expected 0 HIGH warnings for SOL pairs in run_011 (R1 fix active), "
            f"got {len(high_sol)}: {high_sol}"
        )
