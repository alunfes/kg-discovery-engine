"""Layer 3: Rule engine tests.

Covers:
- B2: Temporal look-ahead guard (violation detection, edge rejection)
- Support strength labelling (weakly_supported threshold)
- Watchlist threshold consistency
- Hypothesis generator rules produce valid dicts
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from crypto.src.kg.base import KGEdge, KGNode, KGraph
from crypto.src.kg.temporal_guard import (
    temporal_violation,
    filter_lookahead_edges,
    annotate_temporal_quality,
)
from crypto.src.eval.generator import generate_hypotheses
from crypto.src.eval.scorer import (
    score_hypothesis,
    WEAKLY_SUPPORTED_THRESHOLD,
)
from crypto.src.inventory.store import HypothesisInventory
from crypto.src.schema.task_status import ValidationStatus


# ── B2: Temporal look-ahead guard ──────────────────────────────────────────

def _make_node(nid: str, event_time: int = 0, observable_time: int = 0) -> KGNode:
    return KGNode(
        node_id=nid,
        node_type="TestNode",
        attributes={"event_time": event_time, "observable_time": observable_time},
    )


def test_temporal_violation_detected_when_source_observable_after_target_event():
    """observable_time(src) >= event_time(tgt) → violation."""
    nodes = {
        "src": _make_node("src", event_time=1000, observable_time=5000),
        "tgt": _make_node("tgt", event_time=3000, observable_time=6000),
    }
    edge = KGEdge("e1", "src", "tgt", "causes", {})
    # src.observable_time=5000 >= tgt.event_time=3000 → VIOLATION
    assert temporal_violation(edge, nodes) is True


def test_temporal_violation_not_detected_when_source_observable_before_target_event():
    """observable_time(src) < event_time(tgt) → valid."""
    nodes = {
        "src": _make_node("src", event_time=1000, observable_time=1500),
        "tgt": _make_node("tgt", event_time=5000, observable_time=7000),
    }
    edge = KGEdge("e1", "src", "tgt", "causes", {})
    assert temporal_violation(edge, nodes) is False


def test_temporal_violation_conservative_for_missing_metadata():
    """If nodes lack temporal metadata → not a violation (keep edge)."""
    nodes = {
        "src": KGNode("src", "TestNode", {}),  # no temporal fields
        "tgt": KGNode("tgt", "TestNode", {}),
    }
    edge = KGEdge("e1", "src", "tgt", "causes", {})
    assert temporal_violation(edge, nodes) is False


def test_filter_lookahead_removes_violating_edges():
    kg = KGraph(family="test")
    kg.nodes["src"] = _make_node("src", event_time=100, observable_time=500)
    kg.nodes["tgt"] = _make_node("tgt", event_time=300, observable_time=800)
    kg.edges["e_bad"] = KGEdge("e_bad", "src", "tgt", "causes", {})  # violation
    # Valid edge: src2.observable_time=50 < tgt.event_time=300
    kg.nodes["src2"] = _make_node("src2", event_time=10, observable_time=50)
    kg.edges["e_good"] = KGEdge("e_good", "src2", "tgt", "caused_by", {})

    clean = filter_lookahead_edges(kg)
    assert "e_bad" not in clean.edges
    assert "e_good" in clean.edges


def test_annotate_temporal_quality_flags_bad_edges():
    kg = KGraph(family="test")
    kg.nodes["src"] = _make_node("src", event_time=100, observable_time=500)
    kg.nodes["tgt"] = _make_node("tgt", event_time=300, observable_time=800)
    kg.edges["e_bad"] = KGEdge("e_bad", "src", "tgt", "causes", {})

    annotate_temporal_quality(kg)
    assert kg.edges["e_bad"].attributes["temporal_valid"] is False


# ── Hypothesis generator produces valid structure ──────────────────────────

def test_generate_hypotheses_returns_list(full_kg):
    results = generate_hypotheses(full_kg)
    assert isinstance(results, list)


def test_all_hypotheses_have_required_keys(full_kg):
    required = {"title", "claim", "mechanism", "evidence_nodes", "evidence_edges",
                "operator_trace", "secrecy_level", "kg_families", "plausibility_prior"}
    for hyp in generate_hypotheses(full_kg):
        missing = required - hyp.keys()
        assert not missing, f"Missing keys in hypothesis: {missing}"


def test_hypothesis_deduplication(full_kg):
    """Duplicate (title, claim) pairs must be removed."""
    results = generate_hypotheses(full_kg)
    seen = set()
    for h in results:
        key = (h.get("title", ""), h.get("claim", ""))
        assert key not in seen, f"Duplicate hypothesis: {key}"
        seen.add(key)


# ── Scoring / validation status ─────────────────────────────────────────────

def test_weakly_supported_threshold_applied_correctly(full_kg):
    """Cards with composite >= 0.60 → WEAKLY_SUPPORTED; others → UNTESTED."""
    inventory = HypothesisInventory()
    for hyp in generate_hypotheses(full_kg):
        card = score_hypothesis(hyp, full_kg, inventory, "test_run")
        if card.composite_score >= WEAKLY_SUPPORTED_THRESHOLD:
            assert card.validation_status == ValidationStatus.WEAKLY_SUPPORTED
        else:
            assert card.validation_status == ValidationStatus.UNTESTED


# ── A4: Correlation break branches ─────────────────────────────────────────

def test_a4_no_event_context_produces_mean_reversion(full_kg):
    """With no burst or spread widening, break should → mean_reversion_candidate."""
    # Build a minimal KG with only a correlation_break edge and no context
    kg = KGraph(family="test")
    kg.add_node(KGNode("asset:A", "AssetNode", {"symbol": "A"}))
    kg.add_node(KGNode("corr:A:B", "CorrelationNode", {
        "asset_a": "A", "asset_b": "B",
        "rho": 0.1, "roll_min": 0.05, "best_lag_rho": 0.1, "is_break": True,
    }))
    kg.add_edge(KGEdge("e1", "asset:A", "corr:A:B", "correlation_break", {"rho": 0.1}))

    hypotheses = generate_hypotheses(kg)
    titles = [h["title"] for h in hypotheses]
    assert any("mean_reversion_candidate" in t for t in titles), \
        f"Expected mean_reversion_candidate, got: {titles}"
