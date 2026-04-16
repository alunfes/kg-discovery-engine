"""belief_update operator: Bayesian belief revision of scored hypotheses.

After the evaluate operator scores hypothesis candidates, belief_update
revises those scores as new evidence arrives.  Each piece of evidence is
classified into one of four types and a log-odds delta is applied so the
update is composable: multiple evidence edges are simply accumulated.

Evidence types
--------------
supporting    — edge (src, rel, tgt) exactly matches a step in the
                provenance path.  Directly confirms the chain.
contradicting — edge carries a negative relation AND one of its endpoints
                is a node in the provenance path.  Casts doubt on the chain.
strengthening — edge arrives at a bridge (intermediate) node via a
                non-negative relation not already in the path.  Provides an
                independent corroborating path to the same bridge.
weakening     — edge carries hub_artifact or generic_bridge relation
                AND its source is a bridge node.  Flags the bridge as
                unreliable.

Log-odds update model
---------------------
  prior_lo  = log(p / (1 - p))   clamped to [0.01, 0.99]
  updated_lo = prior_lo + sum(delta[etype] for each evidence edge)
  new_score  = sigmoid(updated_lo)

Deltas:  supporting +0.5 | strengthening +0.3 | weakening -0.3 | contradicting -0.5
"""

from __future__ import annotations

import math
from typing import Literal

from src.eval.scorer import ScoredHypothesis
from src.kg.models import KGEdge
from src.kg.relation_types import NEGATIVE_RELATIONS, WEAKENING_RELATIONS

# ---------------------------------------------------------------------------
# Evidence type
# ---------------------------------------------------------------------------

EvidenceType = Literal["supporting", "contradicting", "strengthening", "weakening"]

# Log-odds delta applied per evidence edge type
_DELTA: dict[str, float] = {
    "supporting": 0.5,
    "strengthening": 0.3,
    "weakening": -0.3,
    "contradicting": -0.5,
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _path_nodes(hypothesis: ScoredHypothesis) -> frozenset[str]:
    """Return all node IDs in the hypothesis provenance path."""
    path = hypothesis.candidate.provenance
    return frozenset(path[0::2])


def _path_edge_tuples(
    hypothesis: ScoredHypothesis,
) -> frozenset[tuple[str, str, str]]:
    """Return (source_id, relation, target_id) tuples from provenance."""
    path = hypothesis.candidate.provenance
    tuples: set[tuple[str, str, str]] = set()
    for i in range(0, len(path) - 2, 2):
        tuples.add((path[i], path[i + 1], path[i + 2]))
    return frozenset(tuples)


def _bridge_nodes(hypothesis: ScoredHypothesis) -> frozenset[str]:
    """Return intermediate node IDs (excludes subject and object)."""
    path = hypothesis.candidate.provenance
    all_nodes = path[0::2]
    if len(all_nodes) <= 2:
        return frozenset()
    return frozenset(all_nodes[1:-1])


# ---------------------------------------------------------------------------
# Evidence classification
# ---------------------------------------------------------------------------


def classify_evidence_edge(
    edge: KGEdge,
    hypothesis: ScoredHypothesis,
) -> EvidenceType | None:
    """Classify a single evidence edge relative to a hypothesis.

    Returns None when the edge is irrelevant to the hypothesis path.

    Priority order (highest first):
    1. supporting   — exact provenance step match
    2. weakening    — hub_artifact / generic_bridge on a bridge node
    3. contradicting — any negative relation touching a path node
    4. strengthening — positive edge arriving at a bridge node
    """
    path_edges = _path_edge_tuples(hypothesis)
    path_nodes = _path_nodes(hypothesis)
    bridges = _bridge_nodes(hypothesis)
    key = (edge.source_id, edge.relation, edge.target_id)

    if key in path_edges:
        return "supporting"

    if edge.relation in WEAKENING_RELATIONS:
        if edge.source_id in bridges or edge.target_id in bridges:
            return "weakening"

    if edge.relation in NEGATIVE_RELATIONS:
        if edge.source_id in path_nodes or edge.target_id in path_nodes:
            return "contradicting"

    if edge.target_id in bridges and edge.relation not in NEGATIVE_RELATIONS:
        return "strengthening"

    return None


# ---------------------------------------------------------------------------
# Log-odds update
# ---------------------------------------------------------------------------


def _to_log_odds(p: float) -> float:
    """Convert probability to log-odds, clamped to avoid ±infinity."""
    p = max(0.01, min(0.99, p))
    return math.log(p / (1.0 - p))


def _from_log_odds(lo: float) -> float:
    """Convert log-odds back to probability via sigmoid."""
    return math.exp(lo) / (1.0 + math.exp(lo))


# ---------------------------------------------------------------------------
# Single-hypothesis update
# ---------------------------------------------------------------------------


def _update_single(
    hypothesis: ScoredHypothesis,
    evidence_edges: list[KGEdge],
) -> ScoredHypothesis:
    """Apply Bayesian log-odds update to one hypothesis.

    Records the pre-update score in belief_history.
    Increments contradiction_count for each contradicting evidence edge.
    """
    prior = hypothesis.total_score
    lo = _to_log_odds(prior)
    contra_count = hypothesis.contradiction_count

    for edge in evidence_edges:
        etype = classify_evidence_edge(edge, hypothesis)
        if etype is None:
            continue
        lo += _DELTA[etype]
        if etype == "contradicting":
            contra_count += 1

    new_score = _from_log_odds(lo)
    new_history = list(hypothesis.belief_history) + [prior]

    return ScoredHypothesis(
        candidate=hypothesis.candidate,
        plausibility=hypothesis.plausibility,
        novelty=hypothesis.novelty,
        testability=hypothesis.testability,
        traceability=hypothesis.traceability,
        evidence_support=hypothesis.evidence_support,
        total_score=new_score,
        score_breakdown=hypothesis.score_breakdown,
        contradiction_count=contra_count,
        belief_history=new_history,
    )


# ---------------------------------------------------------------------------
# Public operator
# ---------------------------------------------------------------------------


def belief_update(
    hypotheses: list[ScoredHypothesis],
    evidence_edges: list[KGEdge],
) -> list[ScoredHypothesis]:
    """Update belief scores based on new evidence edges.

    Each hypothesis is revised independently using a Bayesian log-odds model.
    Supporting and strengthening evidence raise the score; contradicting and
    weakening evidence lower it.  The result is sorted by total_score
    descending, consistent with the evaluate operator's output contract.

    Args:
        hypotheses: Scored hypotheses from the evaluate operator.
        evidence_edges: New KGEdges serving as evidence.  An edge's relation
            type determines how it is classified (see module docstring).

    Returns:
        Updated list sorted by total_score descending.
    """
    if not evidence_edges:
        return sorted(hypotheses, key=lambda h: h.total_score, reverse=True)

    updated = [_update_single(h, evidence_edges) for h in hypotheses]
    updated.sort(key=lambda h: h.total_score, reverse=True)
    return updated
