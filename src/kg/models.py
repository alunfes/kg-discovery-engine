"""KG data models: KGNode, KGEdge, KnowledgeGraph, HypothesisCandidate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KGNode:
    """A node in a Knowledge Graph."""

    id: str
    label: str
    domain: str  # e.g. "biology", "chemistry", "software", "networking"
    attributes: dict = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KGNode):
            return False
        return self.id == other.id


@dataclass
class KGEdge:
    """A directed edge in a Knowledge Graph."""

    source_id: str
    relation: str
    target_id: str
    weight: float = 1.0
    attributes: dict = field(default_factory=dict)
    # Temporal attributes (Phase A) — all Optional for backward compatibility
    valid_from: Optional[str] = None    # ISO 8601 date/datetime
    valid_to: Optional[str] = None      # ISO 8601 date/datetime
    observed_at: Optional[str] = None   # ISO 8601 date/datetime
    confidence: float = 1.0             # 0.0–1.0
    # Typed relation algebra (Phase A)
    relation_type: Optional[str] = None  # causal|structural|statistical|temporal|evidential|ontological

    def __hash__(self) -> int:
        return hash((self.source_id, self.relation, self.target_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KGEdge):
            return False
        return (
            self.source_id == other.source_id
            and self.relation == other.relation
            and self.target_id == other.target_id
        )


class KnowledgeGraph:
    """A simple directed Knowledge Graph with nodes and edges."""

    def __init__(self, name: str = ""):
        """Initialize an empty Knowledge Graph."""
        self.name = name
        self._nodes: dict[str, KGNode] = {}
        self._edges: list[KGEdge] = []
        # adjacency index: source_id -> list of edges
        self._adj: dict[str, list[KGEdge]] = {}

    def add_node(self, node: KGNode) -> None:
        """Add a node to the graph. Overwrites if ID already exists."""
        self._nodes[node.id] = node
        if node.id not in self._adj:
            self._adj[node.id] = []

    def add_edge(self, edge: KGEdge) -> None:
        """Add an edge. Both endpoints must already exist as nodes."""
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node '{edge.source_id}' not in graph")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node '{edge.target_id}' not in graph")
        if edge not in self._edges:
            self._edges.append(edge)
            self._adj[edge.source_id].append(edge)

    def get_node(self, node_id: str) -> Optional[KGNode]:
        """Return node by ID, or None."""
        return self._nodes.get(node_id)

    def nodes(self) -> list[KGNode]:
        """Return all nodes."""
        return list(self._nodes.values())

    def edges(self) -> list[KGEdge]:
        """Return all edges."""
        return list(self._edges)

    def neighbors(self, node_id: str) -> list[KGEdge]:
        """Return outgoing edges from node_id."""
        return list(self._adj.get(node_id, []))

    def has_direct_edge(self, source_id: str, target_id: str) -> bool:
        """Return True if any direct edge exists from source to target."""
        return any(
            e.target_id == target_id for e in self._adj.get(source_id, [])
        )

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(name={self.name!r}, "
            f"nodes={len(self._nodes)}, edges={len(self._edges)})"
        )


@dataclass
class HypothesisCandidate:
    """A generated hypothesis candidate with provenance information."""

    id: str
    subject_id: str      # source node ID
    relation: str        # proposed relation label
    object_id: str       # target node ID
    description: str     # human-readable hypothesis text
    provenance: list[str] = field(default_factory=list)
    # provenance is a list of node/edge IDs forming the derivation path
    operator: str = ""   # which operator generated this
    source_kg_name: str = ""
    flags: list[str] = field(default_factory=list)  # Phase A: warning flags (e.g. type transition alerts)

    def __repr__(self) -> str:
        return (
            f"HypothesisCandidate(id={self.id!r}, "
            f"subject={self.subject_id!r} -[{self.relation}]-> {self.object_id!r})"
        )
