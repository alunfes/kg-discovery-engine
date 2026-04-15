"""Temporal look-ahead guard for KG edge validation (B2).

Problem: a causal edge A → B in the KG is only valid if the strategy could
have known about A *before* making the decision about B.  If A's observable
time is >= B's decision time, the edge is a look-ahead (information leak).

This module provides:
  - temporal_violation: checks a single edge
  - filter_lookahead_edges: removes all violating edges from a KGraph
  - annotate_temporal_quality: adds a 'temporal_valid' flag to all edges

Why in a separate module (not inline in builders):
  Each KG builder operates independently on one data family.  The guard must
  run *after* the full KG is assembled so it can resolve both endpoints.
  Separating it also makes the rule explicit and testable in isolation.
"""

from .base import KGEdge, KGNode, KGraph


def temporal_violation(
    edge: KGEdge,
    nodes: dict[str, KGNode],
) -> bool:
    """Return True if this edge violates look-ahead discipline.

    An edge src → tgt violates if:
      src.observable_time >= tgt.event_time

    Nodes without temporal metadata are conservatively treated as valid
    (returns False) to avoid over-pruning nodes from non-temporal KG families.

    Args:
        edge: The edge to check.
        nodes: Full node dict from the KGraph (to look up src and tgt).
    """
    src = nodes.get(edge.source_id)
    tgt = nodes.get(edge.target_id)
    if src is None or tgt is None:
        return False  # conservative: unknown topology → keep edge

    src_obs = src.attributes.get("observable_time", 0)
    tgt_evt = tgt.attributes.get("event_time", 0)

    # Both must be non-zero to perform the check
    if src_obs == 0 or tgt_evt == 0:
        return False  # missing temporal metadata → keep

    return src_obs >= tgt_evt


def filter_lookahead_edges(kg: KGraph) -> KGraph:
    """Return a new KGraph with all look-ahead edges removed.

    Preserves all nodes; only removes edges where the source's observable_time
    is >= the target's event_time.

    Why return a new KGraph: makes the filter pure (no in-place mutation),
    which keeps unit tests clean.
    """
    clean = KGraph(family=kg.family, nodes=dict(kg.nodes))
    removed = 0
    for eid, edge in kg.edges.items():
        if temporal_violation(edge, kg.nodes):
            removed += 1
        else:
            clean.edges[eid] = edge
    if removed > 0:
        # Surface the count as a graph attribute for diagnostics
        clean.nodes["__temporal_guard_stats__"] = type(
            "FakeNode", (), {"node_id": "__temporal_guard_stats__",
                             "node_type": "_meta",
                             "attributes": {"lookahead_edges_removed": removed}}
        )()
    return clean


def annotate_temporal_quality(kg: KGraph) -> None:
    """In-place: add 'temporal_valid' boolean to each edge's attributes.

    Edges that would be removed by filter_lookahead_edges get
    temporal_valid=False; all others get temporal_valid=True.

    Why annotate instead of remove for the pipeline default:
      The full pipeline still runs with all edges to preserve hypothesis
      variety; the annotation lets the scorer penalise look-ahead edges
      rather than silently drop them.  Callers that need strict no-lookahead
      should call filter_lookahead_edges instead.
    """
    for edge in kg.edges.values():
        edge.attributes["temporal_valid"] = not temporal_violation(edge, kg.nodes)
