"""Run 012: Boundary-case detector for grammar chains.

Pre-adjudication warning for R1-type threshold-boundary confusion:
grammar chains that activate at or near minimum threshold while a
contradicting regime is simultaneously active.

## Problem addressed

Grammar chains activate when evidence crosses a minimum threshold.
Near-threshold activations are weak; if a contradicting regime co-occurs,
the resulting card will likely conflict with stronger-evidence cards
downstream (→ reject_conflicted, spurious reroutes).

This module detects these "fragile" activations BEFORE adjudication so
that R1-candidate chains can be suppressed, flagged for manual review,
or monitored.

## Public API

    from crypto.src.eval.boundary_detector import BoundaryDetector

    detector = BoundaryDetector()
    records = detector.detect_from_kg(grammar_kg, suppression_log, merged_kg, collections)
    warnings = detector.generate_warnings(records)

    # Retrospective over past runs
    results = run_retrospective_analysis(["path/to/run_009", ...])
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ..eval.soft_gate import HARD_GATE_MIN, SOFT_GATE_MIN
from ..kg.base import KGraph
from ..kg.regime_dominance_gate import resolve_regime_states

# ---------------------------------------------------------------------------
# Threshold catalog
# ---------------------------------------------------------------------------

@dataclass
class ThresholdSpec:
    """Catalog entry describing one activation threshold for a grammar chain.

    Attributes:
        chain_type: Suppression-log chain identifier.
        threshold_name: Human-readable label for the threshold.
        threshold_value: Numeric activation boundary.
        boundary_direction: "lower" — value must be ≥ threshold to activate;
            "upper" — value must be ≤ threshold to activate.
        expected_outcome: Outcome the chain normally produces.
        contradicting_regime_signals: Regime signal names (registered in
            regime_dominance_gate) that contradict expected_outcome.
            If active alongside a near-threshold activation → R1 candidate.
        node_type: Grammar KG node type that records this activation.
        attr_key: Node attribute key holding the measured value.
    """
    chain_type: str
    threshold_name: str
    threshold_value: float
    boundary_direction: str  # "lower" | "upper"
    expected_outcome: str
    contradicting_regime_signals: list = field(default_factory=list)
    node_type: str = ""
    attr_key: str = ""


# Full production catalog: all known activation thresholds in grammar chains.
# Update this when new chain builders are added.
CHAIN_THRESHOLDS: dict[str, ThresholdSpec] = {
    # E1 transient aggression — burst_count upper bound (> 4 → failed_followthrough)
    "e1_transient_aggr_burst_upper": ThresholdSpec(
        chain_type="beta_reversion_transient_aggr",
        threshold_name="burst_count_max",
        threshold_value=4.0,
        boundary_direction="upper",
        expected_outcome="beta_reversion",
        contradicting_regime_signals=["funding_extreme", "oi_accumulation"],
        node_type="NoPersistentAggressionNode",
        attr_key="burst_count",
    ),
    # E1 transient aggression — burst_count lower bound (< 1 → no_trigger)
    "e1_transient_aggr_burst_lower": ThresholdSpec(
        chain_type="beta_reversion_transient_aggr",
        threshold_name="burst_count_min",
        threshold_value=1.0,
        boundary_direction="lower",
        expected_outcome="beta_reversion",
        contradicting_regime_signals=["funding_extreme", "oi_accumulation"],
        node_type="NoPersistentAggressionNode",
        attr_key="burst_count",
    ),
    # E2 funding pressure — soft-gate lower bound
    "e2_funding_soft_gate": ThresholdSpec(
        chain_type="positioning_unwind_funding_pressure",
        threshold_name="funding_confidence_min",
        threshold_value=SOFT_GATE_MIN,
        boundary_direction="lower",
        expected_outcome="positioning_unwind",
        # E2 is the unwind chain; funding_extreme is the *trigger*, not a contradiction.
        # No R1-type contradiction applies here.
        contradicting_regime_signals=[],
        node_type="FundingPressureRegimeNode",
        attr_key="activation_confidence",
    ),
    # E2 OI crowding — soft-gate lower bound
    "e2_oi_soft_gate": ThresholdSpec(
        chain_type="positioning_unwind_oi_crowding",
        threshold_name="oi_confidence_min",
        threshold_value=SOFT_GATE_MIN,
        boundary_direction="lower",
        expected_outcome="positioning_unwind",
        contradicting_regime_signals=[],
        node_type="OneSidedOIBuildNode",
        attr_key="activation_confidence",
    ),
    # D3 continuation — corr_break_score lower bound (< 0.20 → branch not activated)
    "d3_continuation_break_score": ThresholdSpec(
        chain_type="continuation_candidate",
        threshold_name="corr_break_score_min",
        threshold_value=0.20,
        boundary_direction="lower",
        expected_outcome="flow_continuation",
        # Funding extreme → unwind context, contradicts continuation claim
        contradicting_regime_signals=["funding_extreme"],
        node_type="CorrelationNode",
        attr_key="corr_break_score",
    ),
}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class BoundaryActivationRecord:
    """One near-threshold chain activation captured at detection time.

    Attributes:
        chain_type: Chain type that activated.
        pair: Asset pair string, e.g. "HYPE/SOL".
        threshold_key: Key in CHAIN_THRESHOLDS.
        threshold_name: Human-readable threshold label.
        threshold_value: Numeric threshold.
        actual_value: Measured value at activation time.
        boundary_proximity: Normalised distance from threshold; near 0 = boundary.
            For lower-bound: (actual - threshold) / threshold.
            For upper-bound: (threshold - actual) / threshold.
        dominant_regime_signals: Active contradicting regime signal names.
        expected_outcome: Chain's expected outcome category.
        regime_contradiction_flag: True when active regime signals contradict
            expected_outcome per the ThresholdSpec.
    """
    chain_type: str
    pair: str
    threshold_key: str
    threshold_name: str
    threshold_value: float
    actual_value: float
    boundary_proximity: float
    dominant_regime_signals: list
    expected_outcome: str
    regime_contradiction_flag: bool


@dataclass
class BoundaryWarning:
    """Pre-adjudication warning emitted for fragile boundary-case activations.

    Warning level rules (evaluated in order, first match wins):
        HIGH:   boundary_proximity < 0.20 AND regime_contradiction_flag = True
        MEDIUM: boundary_proximity < 0.50 AND regime_contradiction_flag = True
        LOW:    boundary_proximity < 0.20 AND regime_contradiction_flag = False
        suppressed: boundary_proximity >= 0.50 (not near enough)

    Recommended action mapping:
        HIGH   → r1_candidate  (apply R1 gate to this chain/threshold)
        MEDIUM → manual_review
        LOW    → monitor
    """
    chain_type: str
    pair: str
    warning_level: str
    boundary_proximity: float
    regime_contradiction_flag: bool
    recommended_action: str
    active_regime_signals: list
    details: str


# Normalised proximity thresholds for warning escalation
_PROXIMITY_HIGH: float = 0.20
_PROXIMITY_MEDIUM: float = 0.50

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_proximity(spec: ThresholdSpec, actual: float) -> float:
    """Normalised distance from threshold (0 = at boundary, >0 = inside zone).

    Returns negative if actual is on the WRONG side of the threshold
    (chain should not have activated — guards against stale KG nodes).
    """
    if spec.threshold_value == 0.0:
        return abs(actual)
    if spec.boundary_direction == "lower":
        return (actual - spec.threshold_value) / abs(spec.threshold_value)
    else:  # upper
        return (spec.threshold_value - actual) / abs(spec.threshold_value)


def _check_regime_contradiction(
    spec: ThresholdSpec,
    merged_kg: KGraph,
    collections: dict,
    assets: list,
) -> tuple[bool, list]:
    """Resolve spec's contradicting signals; return (flag, active_signal_names)."""
    if not spec.contradicting_regime_signals:
        return False, []
    states = resolve_regime_states(
        spec.contradicting_regime_signals, merged_kg, collections, assets
    )
    active = [sig for sig, is_active in states.items() if is_active]
    return bool(active), active


def _parse_pair(node) -> tuple[str, str, str]:
    """Extract (pair_str, a1, a2) from a grammar KG node's attributes."""
    a1 = node.attributes.get("asset_a", "A")
    a2 = node.attributes.get("asset_b", "B")
    return f"{a1}/{a2}", a1, a2


# ---------------------------------------------------------------------------
# BoundaryDetector
# ---------------------------------------------------------------------------


class BoundaryDetector:
    """Detects near-threshold grammar chain activations and generates warnings.

    Scans the chain grammar KG (output of build_chain_grammar_kg) for nodes
    that represent activations near their minimum thresholds, then checks
    whether contradicting regime signals are simultaneously active.

    Why operate on the KG rather than the suppression log:
        The suppression log captures *suppressed* chains; this detector
        captures *activated* chains that are fragile.  The KG nodes carry
        the measured values (burst_count, activation_confidence, etc.) that
        make proximity computation possible.
    """

    def __init__(self, thresholds: dict | None = None) -> None:
        """Create detector, optionally with a custom threshold catalog.

        Args:
            thresholds: Override the CHAIN_THRESHOLDS catalog for testing.
                Pass None (default) for the full production catalog.
        """
        self.thresholds: dict = thresholds if thresholds is not None else CHAIN_THRESHOLDS

    def detect_from_kg(
        self,
        grammar_kg: KGraph,
        suppression_log: list,
        merged_kg: KGraph,
        collections: dict,
    ) -> list:
        """Return BoundaryActivationRecord list for all near-threshold activations.

        Covers two activation sources:
        1. Grammar KG nodes (NoPersistentAggressionNode, FundingPressureRegimeNode…)
        2. Soft-gated suppression log entries (near soft_gate lower bound)

        Args:
            grammar_kg: KG returned by build_chain_grammar_kg (activation nodes).
            suppression_log: Log returned by build_chain_grammar_kg.
            merged_kg: Working merged KG — used for regime signal resolution.
            collections: Per-asset MarketStateCollections for regime resolution.

        Returns:
            Records with 0 ≤ boundary_proximity < 1.0 (inside activation zone
            but within 100 % of the threshold).
        """
        records: list[BoundaryActivationRecord] = []
        records.extend(self._scan_node_activations(grammar_kg, merged_kg, collections))
        records.extend(self._scan_soft_gated_log(suppression_log, merged_kg, collections))
        return records

    def _scan_node_activations(
        self, grammar_kg: KGraph, merged_kg: KGraph, collections: dict
    ) -> list:
        """Scan grammar KG nodes against each threshold spec."""
        records: list[BoundaryActivationRecord] = []
        for node in grammar_kg.nodes.values():
            for tkey, spec in self.thresholds.items():
                if not spec.node_type or node.node_type != spec.node_type:
                    continue
                raw = node.attributes.get(spec.attr_key)
                if raw is None:
                    continue
                actual = float(raw)
                prox = _compute_proximity(spec, actual)
                if prox < 0 or prox >= 1.0:
                    continue  # outside activation zone or too far from boundary
                pair, a1, a2 = _parse_pair(node)
                contradiction, active_sigs = _check_regime_contradiction(
                    spec, merged_kg, collections, [a1, a2]
                )
                records.append(BoundaryActivationRecord(
                    chain_type=spec.chain_type,
                    pair=pair,
                    threshold_key=tkey,
                    threshold_name=spec.threshold_name,
                    threshold_value=spec.threshold_value,
                    actual_value=actual,
                    boundary_proximity=round(prox, 4),
                    dominant_regime_signals=active_sigs,
                    expected_outcome=spec.expected_outcome,
                    regime_contradiction_flag=contradiction,
                ))
        return records

    def _scan_soft_gated_log(
        self, suppression_log: list, merged_kg: KGraph, collections: dict
    ) -> list:
        """Extract soft-gated entries from the suppression log as boundary records.

        Soft-gated entries (reason="soft_gated") represent chains that cleared
        SOFT_GATE_MIN but not HARD_GATE_MIN.  These are logged in the suppression
        log even though the chain was allowed through (as a border-case note).
        They are included here as low-proximity activation records.
        """
        records: list[BoundaryActivationRecord] = []
        for entry in suppression_log:
            if entry.get("reason") != "soft_gated":
                continue
            chain = entry.get("chain", "")
            pair = entry.get("pair", "")
            act_conf = float(entry.get("activation_confidence", 0.0))
            assets = pair.split("/") if "/" in pair else ["A", "B"]
            for tkey, spec in self.thresholds.items():
                if chain != spec.chain_type:
                    continue
                prox = _compute_proximity(spec, act_conf)
                if prox < 0:
                    continue
                contradiction, active_sigs = _check_regime_contradiction(
                    spec, merged_kg, collections, assets
                )
                records.append(BoundaryActivationRecord(
                    chain_type=chain,
                    pair=pair,
                    threshold_key=tkey,
                    threshold_name=spec.threshold_name,
                    threshold_value=spec.threshold_value,
                    actual_value=act_conf,
                    boundary_proximity=round(prox, 4),
                    dominant_regime_signals=active_sigs,
                    expected_outcome=spec.expected_outcome,
                    regime_contradiction_flag=contradiction,
                ))
        return records

    def generate_warnings(self, records: list) -> list:
        """Emit BoundaryWarning list from activation records.

        Returns warnings sorted HIGH → MEDIUM → LOW.
        Records with boundary_proximity ≥ _PROXIMITY_MEDIUM are suppressed
        (far enough from threshold to not require pre-adjudication action).
        """
        warnings: list[BoundaryWarning] = []
        for rec in records:
            level, action = self._classify(rec)
            if level is None:
                continue
            detail = (
                f"{rec.chain_type} pair={rec.pair} "
                f"{rec.threshold_name}={rec.threshold_value:.3f} "
                f"actual={rec.actual_value:.3f} prox={rec.boundary_proximity:.3f}"
            )
            if rec.regime_contradiction_flag:
                detail += f" contradicting_regime={rec.dominant_regime_signals}"
            warnings.append(BoundaryWarning(
                chain_type=rec.chain_type,
                pair=rec.pair,
                warning_level=level,
                boundary_proximity=rec.boundary_proximity,
                regime_contradiction_flag=rec.regime_contradiction_flag,
                recommended_action=action,
                active_regime_signals=rec.dominant_regime_signals,
                details=detail,
            ))
        _ORDER = {"high": 0, "medium": 1, "low": 2}
        warnings.sort(key=lambda w: _ORDER.get(w.warning_level, 9))
        return warnings

    def _classify(self, rec: BoundaryActivationRecord) -> tuple:
        """Map (proximity, contradiction) to (level, action) or (None, None)."""
        p = rec.boundary_proximity
        c = rec.regime_contradiction_flag
        if p < _PROXIMITY_HIGH and c:
            return "high", "r1_candidate"
        if p < _PROXIMITY_MEDIUM and c:
            return "medium", "manual_review"
        if p < _PROXIMITY_HIGH:
            return "low", "monitor"
        return None, None


# ---------------------------------------------------------------------------
# dict helpers for serialisation
# ---------------------------------------------------------------------------


def record_to_dict(r: BoundaryActivationRecord) -> dict:
    """Serialise a BoundaryActivationRecord to a plain dict (JSON-safe)."""
    return {
        "chain_type": r.chain_type,
        "pair": r.pair,
        "threshold_key": r.threshold_key,
        "threshold_name": r.threshold_name,
        "threshold_value": r.threshold_value,
        "actual_value": r.actual_value,
        "boundary_proximity": r.boundary_proximity,
        "dominant_regime_signals": r.dominant_regime_signals,
        "expected_outcome": r.expected_outcome,
        "regime_contradiction_flag": r.regime_contradiction_flag,
    }


def warning_to_dict(w: BoundaryWarning) -> dict:
    """Serialise a BoundaryWarning to a plain dict (JSON-safe)."""
    return {
        "chain_type": w.chain_type,
        "pair": w.pair,
        "warning_level": w.warning_level,
        "boundary_proximity": w.boundary_proximity,
        "regime_contradiction_flag": w.regime_contradiction_flag,
        "recommended_action": w.recommended_action,
        "active_regime_signals": w.active_regime_signals,
        "details": w.details,
    }


# ---------------------------------------------------------------------------
# Retrospective analysis
# ---------------------------------------------------------------------------


def run_retrospective_analysis(run_dirs: list, detector: BoundaryDetector | None = None) -> dict:
    """Apply the boundary detector to past pipeline runs (deterministic re-runs).

    For each run directory, reads run_config.json to reproduce the exact
    pipeline state (same seed), then runs boundary detection on the
    reconstructed grammar KG.

    Why re-run rather than parsing JSON artifacts:
        Grammar KG nodes and merged KG are not serialised in run artifacts.
        Re-running with the same seed is 100 % deterministic and gives the
        exact intermediate states needed for regime signal resolution.

    Args:
        run_dirs: List of run artifact directories (must each have run_config.json).
        detector: Detector instance.  Creates a default one if None.

    Returns:
        Dict keyed by run basename, each containing records/warnings/stats,
        plus an "__aggregate__" key with cross-run stats.
    """
    if detector is None:
        detector = BoundaryDetector()
    results: dict = {}
    all_records: list[BoundaryActivationRecord] = []
    for run_dir in run_dirs:
        run_result, records = _analyze_one_run(run_dir, detector)
        results[os.path.basename(run_dir)] = run_result
        all_records.extend(records)
    results["__aggregate__"] = _aggregate_stats(all_records)
    return results


def _analyze_one_run(run_dir: str, detector: BoundaryDetector) -> tuple:
    """Analyze a single run directory; return (result_dict, records_list)."""
    cfg_path = os.path.join(run_dir, "run_config.json")
    if not os.path.exists(cfg_path):
        return {"error": "run_config.json not found"}, []
    with open(cfg_path) as f:
        cfg = json.load(f)
    grammar_kg, suppression_log, working_kg, collections = _rebuild_chain_state(cfg)
    records = detector.detect_from_kg(grammar_kg, suppression_log, working_kg, collections)
    warnings = detector.generate_warnings(records)
    result = {
        "records": [record_to_dict(r) for r in records],
        "warnings": [warning_to_dict(w) for w in warnings],
        "n_records": len(records),
        "n_warnings": len(warnings),
        "high_warnings": sum(1 for w in warnings if w.warning_level == "high"),
        "medium_warnings": sum(1 for w in warnings if w.warning_level == "medium"),
        "low_warnings": sum(1 for w in warnings if w.warning_level == "low"),
    }
    return result, records


def _rebuild_chain_state(cfg: dict) -> tuple:
    """Re-run pipeline steps up to build_chain_grammar_kg using a saved config.

    Returns (grammar_kg, suppression_log, working_kg, collections).
    Mirrors the KG build sequence in pipeline.run_pipeline exactly.
    """
    import random
    from ..ingestion.synthetic import SyntheticGenerator
    from ..kg.chain_grammar import build_chain_grammar_kg
    from ..kg.cross_asset import build_cross_asset_kg
    from ..kg.execution import build_execution_kg
    from ..kg.microstructure import build_microstructure_kg
    from ..kg.pair import build_pair_kg
    from ..kg.regime import build_regime_kg
    from ..operators.ops import align, compose, difference, union
    from ..states.extractor import extract_states

    seed = cfg.get("seed", 42)
    assets = cfg.get("assets", ["HYPE", "ETH", "BTC", "SOL"])
    n_minutes = cfg.get("n_minutes", 60)
    run_id = cfg.get("run_id", "retro")

    random.seed(seed)
    gen = SyntheticGenerator(seed=seed, n_minutes=n_minutes, assets=assets)
    dataset = gen.generate()
    collections = {a: extract_states(dataset, a, run_id) for a in assets}
    micro_kgs = {a: build_microstructure_kg(collections[a]) for a in assets}
    exec_kgs = {a: build_execution_kg(collections[a]) for a in assets}
    regime_kgs = {a: build_regime_kg(collections[a]) for a in assets}
    cross_kg = build_cross_asset_kg(collections, dataset=dataset)
    pair_kg = build_pair_kg(collections)
    working_kg = _build_working_kg(
        micro_kgs, exec_kgs, regime_kgs, cross_kg, pair_kg, align, compose, difference, union
    )
    grammar_kg, suppression_log = build_chain_grammar_kg(working_kg, collections)
    return grammar_kg, suppression_log, working_kg, collections


def _build_working_kg(
    micro_kgs: dict, exec_kgs: dict, regime_kgs: dict,
    cross_kg: KGraph, pair_kg: KGraph,
    align, compose, difference, union,
) -> KGraph:
    """Merge per-asset KGs and run operator chain to produce the working KG.

    Extracted from _rebuild_chain_state to stay within the 40-line function limit.
    Mirrors steps 3-5 of pipeline.run_pipeline.
    """
    def _merge(kgs: list, fam: str) -> KGraph:
        result = KGraph(family=fam)
        for kg in kgs:
            for n in kg.nodes.values():
                result.add_node(n)
            for e in kg.edges.values():
                result.add_edge(e)
        return result

    merged_micro = _merge(list(micro_kgs.values()), "micro_all")
    merged_exec = _merge(list(exec_kgs.values()), "exec_all")
    merged_regime = _merge(list(regime_kgs.values()), "regime_all")
    aligned = align(merged_micro, merged_exec, "symbol")
    full_kg = union(union(union(aligned, cross_kg), pair_kg), merged_regime)
    composed = compose(full_kg, "aggression_predicts_funding")
    novel_kg = difference(composed, aligned)
    return union(full_kg, novel_kg)


def _aggregate_stats(records: list) -> dict:
    """Compute cross-run aggregate stats from all boundary activation records."""
    if not records:
        return {"n_total": 0, "chain_exposure": {}, "pair_exposure": {}}
    chain_counts: dict[str, int] = {}
    pair_counts: dict[str, int] = {}
    high_risk = 0
    for r in records:
        chain_counts[r.chain_type] = chain_counts.get(r.chain_type, 0) + 1
        pair_counts[r.pair] = pair_counts.get(r.pair, 0) + 1
        if r.regime_contradiction_flag and r.boundary_proximity < _PROXIMITY_HIGH:
            high_risk += 1
    return {
        "n_total": len(records),
        "n_high_risk": high_risk,
        "chain_exposure": dict(sorted(chain_counts.items(), key=lambda x: -x[1])),
        "pair_exposure": dict(sorted(pair_counts.items(), key=lambda x: -x[1])),
    }
