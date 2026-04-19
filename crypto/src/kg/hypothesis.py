"""First-class Hypothesis nodes and semantic relations.

A hypothesis is not a signal. A signal is one expression of a hypothesis.
Multiple signals can derive from the same hypothesis, and multiple hypotheses
can compete to explain the same market state.

This module introduces:
- HypothesisStatus: lifecycle enum (candidate → active → invalidated / rerouted / archived)
- HypothesisNode: first-class KG node with evidence, contradiction, invalidation semantics
- SemanticRelation: typed enum for hypothesis-level relations
- HypothesisEdge: convenience constructor for semantic edges
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .base import KGEdge, KGNode


class HypothesisStatus(Enum):
    """Lifecycle state of a hypothesis."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    REROUTED = "rerouted"
    ARCHIVED = "archived"


class SemanticRelation(Enum):
    """Typed relations between hypothesis nodes and evidence.

    These extend the existing 14+ observation-level relations
    (exhibits_spread, in_regime, etc.) with hypothesis-level semantics.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REROUTES_TO = "reroutes_to"
    INVALIDATES = "invalidates"
    DEPENDS_ON = "depends_on"
    EXPLAINS = "explains"
    CO_OCCURS_WITH = "co_occurs_with"
    REQUIRES_OBSERVATION = "requires_observation"


@dataclass
class InvalidationCondition:
    """A falsifiable condition that would invalidate a hypothesis.

    Attributes:
        description: human-readable condition (e.g. "funding rate normalizes within 2h")
        metric:      observable metric name (e.g. "funding_rate_1h")
        operator:    comparison operator (gt, lt, eq, crosses_zero)
        threshold:   trigger value
        window_min:  observation window in minutes
    """

    description: str
    metric: str = ""
    operator: str = ""
    threshold: float = 0.0
    window_min: float = 60.0

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "window_min": self.window_min,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InvalidationCondition:
        return cls(
            description=d["description"],
            metric=d.get("metric", ""),
            operator=d.get("operator", ""),
            threshold=float(d.get("threshold", 0.0)),
            window_min=float(d.get("window_min", 60.0)),
        )


@dataclass
class HypothesisNode:
    """A first-class hypothesis in the Knowledge Graph.

    Hypotheses are not immutable cards — they have a lifecycle.
    Events support or contradict them. Regime shifts can invalidate them.
    Alternative hypotheses compete with them.

    Attributes:
        hypothesis_id:         unique identifier
        claim:                 falsifiable assertion
        family:                grammar family (momentum, reversion, cross_asset, etc.)
        status:                lifecycle state
        regime_dependency:     which regime(s) this hypothesis requires
        horizon_min:           expected validity horizon in minutes
        evidence_strength:     aggregate evidence score [0.0, 1.0]
        contradiction_pressure: aggregate contradiction score [0.0, 1.0]
        novelty:               distance from known patterns [0.0, 1.0]
        execution_feasibility: how tradeable this is [0.0, 1.0]
        invalidation_conditions: conditions that would falsify this
        alternative_ids:       hypothesis_ids of competing alternatives
        next_observations:     what additional data would resolve uncertainty
        supporting_evidence:   (node_id, relation) pairs
        contradicting_evidence: (node_id, relation) pairs
        created_at_ms:         creation timestamp (ms)
        source_card_id:        HypothesisCard.card_id if derived from existing card
        source_event_types:    StateEvent types that contributed
        metadata:              additional context
    """

    hypothesis_id: str
    claim: str
    family: str
    status: HypothesisStatus = HypothesisStatus.CANDIDATE
    regime_dependency: list[str] = field(default_factory=list)
    horizon_min: float = 40.0
    evidence_strength: float = 0.0
    contradiction_pressure: float = 0.0
    novelty: float = 0.0
    execution_feasibility: float = 0.0
    invalidation_conditions: list[InvalidationCondition] = field(default_factory=list)
    alternative_ids: list[str] = field(default_factory=list)
    next_observations: list[str] = field(default_factory=list)
    supporting_evidence: list[tuple[str, str]] = field(default_factory=list)
    contradicting_evidence: list[tuple[str, str]] = field(default_factory=list)
    created_at_ms: int = 0
    source_card_id: Optional[str] = None
    source_event_types: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_kg_node(self) -> KGNode:
        """Convert to a KGNode for storage in KGraph."""
        return KGNode(
            node_id=self.hypothesis_id,
            node_type="hypothesis",
            attributes=self.to_dict(),
        )

    def net_evidence(self) -> float:
        """evidence_strength - contradiction_pressure, clamped to [0, 1]."""
        return max(0.0, min(1.0, self.evidence_strength - self.contradiction_pressure))

    def is_actionable(self) -> bool:
        """A hypothesis is actionable if it has positive net evidence and is feasible."""
        return (
            self.status == HypothesisStatus.ACTIVE
            and self.net_evidence() > 0.3
            and self.execution_feasibility > 0.3
        )

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "claim": self.claim,
            "family": self.family,
            "status": self.status.value,
            "regime_dependency": self.regime_dependency,
            "horizon_min": self.horizon_min,
            "evidence_strength": self.evidence_strength,
            "contradiction_pressure": self.contradiction_pressure,
            "novelty": self.novelty,
            "execution_feasibility": self.execution_feasibility,
            "invalidation_conditions": [ic.to_dict() for ic in self.invalidation_conditions],
            "alternative_ids": self.alternative_ids,
            "next_observations": self.next_observations,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "created_at_ms": self.created_at_ms,
            "source_card_id": self.source_card_id,
            "source_event_types": self.source_event_types,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> HypothesisNode:
        return cls(
            hypothesis_id=d["hypothesis_id"],
            claim=d["claim"],
            family=d["family"],
            status=HypothesisStatus(d.get("status", "candidate")),
            regime_dependency=d.get("regime_dependency", []),
            horizon_min=float(d.get("horizon_min", 40.0)),
            evidence_strength=float(d.get("evidence_strength", 0.0)),
            contradiction_pressure=float(d.get("contradiction_pressure", 0.0)),
            novelty=float(d.get("novelty", 0.0)),
            execution_feasibility=float(d.get("execution_feasibility", 0.0)),
            invalidation_conditions=[
                InvalidationCondition.from_dict(ic)
                for ic in d.get("invalidation_conditions", [])
            ],
            alternative_ids=d.get("alternative_ids", []),
            next_observations=d.get("next_observations", []),
            supporting_evidence=[tuple(e) for e in d.get("supporting_evidence", [])],
            contradicting_evidence=[tuple(e) for e in d.get("contradicting_evidence", [])],
            created_at_ms=int(d.get("created_at_ms", 0)),
            source_card_id=d.get("source_card_id"),
            source_event_types=d.get("source_event_types", []),
            metadata=d.get("metadata", {}),
        )


def make_hypothesis_id(claim: str, family: str, timestamp_ms: int) -> str:
    """Deterministic hypothesis ID from content."""
    raw = f"{claim}|{family}|{timestamp_ms}"
    return f"hyp_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def make_semantic_edge(
    source_id: str,
    target_id: str,
    relation: SemanticRelation,
    **attrs: object,
) -> KGEdge:
    """Create a KGEdge with semantic relation typing."""
    edge_id = f"{relation.value}:{source_id}->{target_id}"
    return KGEdge(
        edge_id=edge_id,
        source_id=source_id,
        target_id=target_id,
        relation=relation.value,
        attributes=dict(attrs),
    )
