"""KG operators implementation.

All operators are pure functions: no side effects, no global state.
Same inputs + same seed → identical outputs.

See docs/kg_operator_spec.md for the full economic semantics of each operator.
"""

from typing import Callable

from ..kg.base import KGEdge, KGNode, KGraph

MAX_COMPOSE_DEPTH = 3


def align(g1: KGraph, g2: KGraph, key: str) -> KGraph:
    """Find nodes in g1 and g2 sharing a common attribute value on `key`.

    Returns a new graph containing all nodes from both inputs plus
    cross-graph _aligned_to edges where the key attribute matches.

    Economic meaning: identifies co-moving or co-behaving assets across
    different KG families (e.g., same funding direction in regime KG and
    microstructure KG).
    """
    result = KGraph(family=f"aligned:{g1.family}:{g2.family}")

    for node in g1.nodes.values():
        result.add_node(node)
    for node in g2.nodes.values():
        result.add_node(node)
    for edge in g1.edges.values():
        result.add_edge(edge)
    for edge in g2.edges.values():
        result.add_edge(edge)

    for n1 in g1.nodes.values():
        v1 = n1.attributes.get(key)
        if v1 is None:
            continue
        for n2 in g2.nodes.values():
            v2 = n2.attributes.get(key)
            if v2 is None or n1.node_id == n2.node_id:
                continue
            if v1 == v2:
                edge_id = f"aligned:{n1.node_id}:{n2.node_id}:{key}"
                result.add_edge(KGEdge(
                    edge_id=edge_id,
                    source_id=n1.node_id,
                    target_id=n2.node_id,
                    relation="_aligned_to",
                    attributes={"key": key, "value": str(v1)},
                ))

    return result


def union(g1: KGraph, g2: KGraph) -> KGraph:
    """Merge two KGs, deduplicating nodes by node_id.

    Edge conflicts are resolved by keeping both (union semantics —
    no information is discarded).

    Economic meaning: expands evidence base when two independent KG
    families provide complementary observations.
    """
    family = f"union:{g1.family}:{g2.family}"
    result = KGraph(family=family)

    for node in g1.nodes.values():
        result.add_node(node)
    for node in g2.nodes.values():
        result.add_node(node)
    for edge in g1.edges.values():
        result.add_edge(edge)
    for edge in g2.edges.values():
        result.add_edge(edge)

    return result


def compose(g: KGraph, relation_type: str) -> KGraph:
    """Follow chains of a relation to surface transitive connections.

    Adds _composed edges for paths of length 2..MAX_COMPOSE_DEPTH.
    Does NOT add self-loops.

    Economic meaning: discovers indirect causal chains — e.g., asset A
    impacts B via liquidity_shift; B impacts C via funding_pressure;
    compose reveals A → C with a single transitive edge.

    Why BFS not DFS: BFS discovers shortest paths first, which have
    stronger causal interpretability than long indirect chains.
    """
    result = KGraph(family=f"composed:{g.family}:{relation_type}")

    for node in g.nodes.values():
        result.add_node(node)
    for edge in g.edges.values():
        result.add_edge(edge)

    # BFS from every node
    for start_id in list(g.nodes.keys()):
        _bfs_compose(g, result, start_id, relation_type)

    return result


def _bfs_compose(
    g: KGraph,
    result: KGraph,
    start_id: str,
    relation_type: str,
) -> None:
    """BFS to find transitive successors of start_id via relation_type."""
    # (current_node_id, depth, path)
    queue: list[tuple[str, int]] = [(start_id, 0)]
    visited: set[str] = {start_id}

    while queue:
        current_id, depth = queue.pop(0)
        if depth >= MAX_COMPOSE_DEPTH:
            continue

        for edge in g.edges.values():
            if edge.source_id != current_id or edge.relation != relation_type:
                continue
            next_id = edge.target_id
            if next_id == start_id:
                continue  # no self-loops
            # Add transitive edge from start → next (if path length > 1)
            if depth >= 1:
                composed_id = f"_composed:{start_id}:{next_id}:{depth + 1}"
                result.add_edge(KGEdge(
                    edge_id=composed_id,
                    source_id=start_id,
                    target_id=next_id,
                    relation="_composed",
                    attributes={
                        "via": relation_type,
                        "depth": depth + 1,
                    },
                ))
            if next_id not in visited:
                visited.add(next_id)
                queue.append((next_id, depth + 1))


def difference(g1: KGraph, g2: KGraph) -> KGraph:
    """Return nodes/edges in g1 that are NOT in g2.

    Economic meaning: finds structure present in one regime but absent in
    another — the core primitive for regime-change hypothesis generation.
    """
    result = KGraph(family=f"diff:{g1.family}:{g2.family}")

    for node in g1.nodes.values():
        if node.node_id not in g2.nodes:
            result.add_node(node)

    for edge in g1.edges.values():
        if edge.edge_id not in g2.edges:
            result.add_edge(edge)

    return result


def rank(
    candidates: list[dict],
    scorer: Callable[[dict], float],
    top_k: int,
) -> list[dict]:
    """Score hypothesis candidates and return the top-k.

    Args:
        candidates: List of raw hypothesis dicts.
        scorer: Pure function (dict → float) — must be deterministic.
        top_k: Maximum number of results to return.

    Returns:
        At most top_k candidates sorted descending by score.

    Selection artifact note: when top_k << len(candidates), naive ranking
    selects low-variance hypotheses.  The scorer must embed a novelty
    penalty.  See docs/kg_operator_spec.md §rank.
    """
    if not candidates:
        return []
    scored = [(c, scorer(c)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:top_k]]
