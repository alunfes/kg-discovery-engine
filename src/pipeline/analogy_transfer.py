"""analogy_transfer operator: transfer relational patterns across KG domains."""

from __future__ import annotations

from typing import Optional

from src.kg.models import HypothesisCandidate, KnowledgeGraph
from src.pipeline.operators import AlignmentMap

# Edge tuple: (source_id, relation, target_id)
PatternEdge = tuple[str, str, str]
# Ordered sequence of edges forming a subgraph pattern
SubgraphPattern = list[PatternEdge]

# Causal/mechanistic relations — Phase A typed relation set.
_CAUSAL_RELATIONS: frozenset[str] = frozenset({
    "inhibits", "activates", "catalyzes", "produces", "encodes",
    "accelerates", "yields", "facilitates",
})


def _is_causal(relation: str) -> bool:
    """Return True if relation is causal/mechanistic."""
    return relation in _CAUSAL_RELATIONS


def _extract_patterns(
    kg: KnowledgeGraph,
    max_hops: int = 2,
) -> list[SubgraphPattern]:
    """Extract 1- and 2-hop subgraph patterns from kg.

    Returns deduplicated list of edge sequences (SubgraphPattern).

    Args:
        kg: Source knowledge graph.
        max_hops: Maximum path length (1 or 2). Default 2.
    """
    patterns: list[SubgraphPattern] = []
    seen: set[tuple[PatternEdge, ...]] = set()

    for node in kg.nodes():
        for e1 in kg.neighbors(node.id):
            # 1-hop pattern
            key1: tuple[PatternEdge, ...] = ((e1.source_id, e1.relation, e1.target_id),)
            if key1 not in seen:
                seen.add(key1)
                patterns.append(list(key1))

            if max_hops < 2:
                continue

            # 2-hop patterns
            for e2 in kg.neighbors(e1.target_id):
                if e2.target_id == node.id:
                    continue  # skip back-cycles
                edge1: PatternEdge = (e1.source_id, e1.relation, e1.target_id)
                edge2: PatternEdge = (e2.source_id, e2.relation, e2.target_id)
                key2: tuple[PatternEdge, ...] = (edge1, edge2)
                if key2 not in seen:
                    seen.add(key2)
                    patterns.append([edge1, edge2])

    return patterns


def _map_pattern_nodes(
    pattern: SubgraphPattern,
    alignment: AlignmentMap,
) -> Optional[dict[str, str]]:
    """Map source pattern node IDs to target node IDs via alignment.

    Returns {source_node_id: target_node_id} or None if any node is unaligned.
    """
    node_ids: set[str] = set()
    for src, _rel, tgt in pattern:
        node_ids.add(src)
        node_ids.add(tgt)

    node_map: dict[str, str] = {}
    for nid in node_ids:
        if nid not in alignment:
            return None
        node_map[nid] = alignment[nid]
    return node_map


def _pattern_exists_in_target(
    pattern: SubgraphPattern,
    node_map: dict[str, str],
    target_kg: KnowledgeGraph,
) -> bool:
    """Return True if ALL edges in mapped pattern already exist in target_kg."""
    for src, rel, tgt in pattern:
        t_src = node_map[src]
        t_tgt = node_map[tgt]
        found = any(
            e.relation == rel and e.target_id == t_tgt
            for e in target_kg.neighbors(t_src)
        )
        if not found:
            return False
    return True


def _causal_transfer_allowed(
    pattern: SubgraphPattern,
    node_map: dict[str, str],
    target_kg: KnowledgeGraph,
) -> bool:
    """Enforce causal-type transfer constraint.

    If ALL pattern edges are causal, the target must have at least one causal
    edge from any mapped source node (causal→causal only rule).
    Mixed/associative patterns always pass.
    """
    pattern_rels = [rel for _, rel, _ in pattern]
    if not all(_is_causal(r) for r in pattern_rels):
        return True  # mixed/associative: no restriction

    for src, _rel, _tgt in pattern:
        t_src = node_map[src]
        if any(_is_causal(e.relation) for e in target_kg.neighbors(t_src)):
            return True

    return False  # pure causal pattern but no causal context in target


def _analogy_strength(
    pattern: SubgraphPattern,
    node_map: dict[str, str],
    source_kg: KnowledgeGraph,
    target_kg: KnowledgeGraph,
) -> float:
    """Compute analogy strength in [0.0, 1.0].

    Formula:
    - avg_source_weight: mean edge weight from source pattern (confidence proxy)
    - category_bonus: +0.1 if >= 50% of pattern edges have causal context in target
    - depth_factor: 1.0 for 1-hop, 0.7 for 2-hop (uncertainty penalty)

    Returns rounded score floored at 0.0.
    """
    if not pattern:
        return 0.0

    weight_sum = 0.0
    causal_context_hits = 0

    for src, rel, tgt in pattern:
        src_edges = source_kg.neighbors(src)
        src_weight = next(
            (e.weight for e in src_edges if e.relation == rel and e.target_id == tgt),
            1.0,
        )
        weight_sum += src_weight

        t_src = node_map[src]
        target_cats = {_is_causal(e.relation) for e in target_kg.neighbors(t_src)}
        if _is_causal(rel) and True in target_cats:
            causal_context_hits += 1

    avg_weight = weight_sum / len(pattern)
    category_bonus = 0.1 if causal_context_hits / len(pattern) >= 0.5 else 0.0
    depth_factor = 1.0 if len(pattern) == 1 else 0.7

    return round(min(1.0, avg_weight * depth_factor + category_bonus), 4)


def _build_provenance(pattern: SubgraphPattern) -> list[str]:
    """Build provenance list from pattern edge sequence.

    Format: [src0, rel0, tgt0, rel1, tgt1, ...]
    """
    if not pattern:
        return []
    provenance: list[str] = [pattern[0][0]]
    for src, rel, tgt in pattern:
        provenance.extend([rel, tgt])
    return provenance


def analogy_transfer(
    source_kg: KnowledgeGraph,
    target_kg: KnowledgeGraph,
    alignment: AlignmentMap,
    max_hops: int = 2,
    min_analogy_strength: float = 0.1,
    _counter: Optional[list[int]] = None,
) -> list[HypothesisCandidate]:
    """Transfer relational patterns from source_kg to target_kg via alignment.

    Algorithm:
    1. Extract 1–2 hop patterns from source_kg
    2. Map each pattern to target_kg nodes via alignment
    3. Skip patterns already present in target_kg
    4. Apply causal-type transfer constraint (causal→causal only)
    5. Generate HypothesisCandidate for each novel transferred pattern

    Args:
        source_kg: KG containing source patterns.
        target_kg: KG to transfer patterns into.
        alignment: {source_node_id: target_node_id} mapping.
        max_hops: Maximum pattern depth (1 or 2). Default 2.
        min_analogy_strength: Discard candidates below this threshold.
        _counter: Shared ID counter for stable hypothesis IDs.

    Returns:
        List of HypothesisCandidate, sorted by provenance length (ascending).
    """
    if _counter is None:
        _counter = [0]

    patterns = _extract_patterns(source_kg, max_hops=max_hops)
    candidates: list[HypothesisCandidate] = []

    for pattern in patterns:
        node_map = _map_pattern_nodes(pattern, alignment)
        if node_map is None:
            continue

        if _pattern_exists_in_target(pattern, node_map, target_kg):
            continue

        if not _causal_transfer_allowed(pattern, node_map, target_kg):
            continue

        strength = _analogy_strength(pattern, node_map, source_kg, target_kg)
        if strength < min_analogy_strength:
            continue

        src_id = node_map[pattern[0][0]]
        tgt_id = node_map[pattern[-1][2]]
        src_node = target_kg.get_node(src_id)
        tgt_node = target_kg.get_node(tgt_id)
        if src_node is None or tgt_node is None:
            continue

        _counter[0] += 1
        hyp_id = f"H{_counter[0]:04d}"

        pattern_desc = " -> ".join(
            f"{node_map[s]} -[{r}]-> {node_map[t]}" for s, r, t in pattern
        )
        description = (
            f"[analogy] {src_node.label} may relate to {tgt_node.label} "
            f"by analogy from {source_kg.name}: {pattern_desc} "
            f"(strength={strength:.3f})"
        )

        candidates.append(
            HypothesisCandidate(
                id=hyp_id,
                subject_id=src_id,
                relation="analogy_of",
                object_id=tgt_id,
                description=description,
                provenance=_build_provenance(pattern),
                operator="analogy_transfer",
                source_kg_name=source_kg.name,
            )
        )

    # Shorter provenance = simpler/more direct analogy = more reliable
    candidates.sort(key=lambda c: len(c.provenance))
    return candidates
