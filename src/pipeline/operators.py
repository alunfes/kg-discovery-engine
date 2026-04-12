"""KG operators: align, union, difference, compose, and placeholders."""

from __future__ import annotations

import re
from collections import deque
from typing import Optional

from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph

# AlignmentMap: {node_id_in_kg1: node_id_in_kg2}
AlignmentMap = dict[str, str]

# Cross-domain synonym dictionary for analogical label matching.
# Maps a concept token to semantically equivalent tokens in other domains.
_SYNONYM_DICT: dict[str, frozenset[str]] = {
    "enzyme": frozenset({"catalyst"}),
    "catalyst": frozenset({"enzyme"}),
    "protein": frozenset({"compound", "molecule"}),
    "compound": frozenset({"protein", "molecule"}),
    "molecule": frozenset({"protein", "compound"}),
    "inhibit": frozenset({"block", "suppress"}),
    "block": frozenset({"inhibit"}),
    "suppress": frozenset({"inhibit"}),
    "reaction": frozenset({"process"}),
    "process": frozenset({"reaction"}),
}


# ---------------------------------------------------------------------------
# String similarity helpers
# ---------------------------------------------------------------------------

def _split_camel(label: str) -> list[str]:
    """Split a CamelCase label into lowercase tokens.

    "EnzymeX" → ["enzyme", "x"]
    "CatalystM" → ["catalyst", "m"]
    """
    parts = re.sub(r"([A-Z])", r" \1", label).strip().split()
    return [p.lower() for p in parts if p.strip()]


def _token_set(label: str) -> set[str]:
    """Produce a lowercase token set from a label.

    Handles both space-separated and CamelCase labels.
    """
    space_tokens = {t.lower() for t in label.split() if t}
    camel_tokens = set(_split_camel(label))
    return space_tokens | camel_tokens


def _jaccard(a: str, b: str) -> float:
    """Jaccard similarity with cross-domain synonym bridge detection.

    If any token in label_a is a direct synonym of any token in label_b
    (or vice versa), a synonym-bridge score of 0.5 is returned.  This
    ensures cross-domain analogues such as "enzyme"↔"catalyst" clear the
    default threshold (0.4) regardless of identifier suffixes ("EnzymeX",
    "CatalystM") that would otherwise dilute the Jaccard score.
    """
    ta = _token_set(a)
    tb = _token_set(b)

    # Synonym-bridge check: a token in ta has a direct synonym present in tb
    for token in ta:
        if _SYNONYM_DICT.get(token, frozenset()) & tb:
            return 0.5
    for token in tb:
        if _SYNONYM_DICT.get(token, frozenset()) & ta:
            return 0.5

    # Standard token Jaccard (no synonym bridge)
    if not ta and not tb:
        return 1.0
    intersection = len(ta & tb)
    union_size = len(ta | tb)
    return intersection / union_size if union_size > 0 else 0.0


def _label_similarity(label_a: str, label_b: str) -> float:
    """Combined similarity: exact match=1.0, synonym-aware Jaccard otherwise."""
    if label_a.lower() == label_b.lower():
        return 1.0
    return _jaccard(label_a, label_b)


# ---------------------------------------------------------------------------
# align
# ---------------------------------------------------------------------------

def align(
    kg1: KnowledgeGraph,
    kg2: KnowledgeGraph,
    threshold: float = 0.5,
) -> AlignmentMap:
    """Align nodes between two KGs using label similarity.

    Returns a mapping {node_id_in_kg1: node_id_in_kg2}.
    Uses a greedy approach: sorts by similarity descending, picks best pairs.
    """
    candidates: list[tuple[float, str, str]] = []

    for n1 in kg1.nodes():
        for n2 in kg2.nodes():
            sim = _label_similarity(n1.label, n2.label)
            if sim >= threshold:
                candidates.append((sim, n1.id, n2.id))

    # Greedy 1-to-1 matching: highest similarity first
    candidates.sort(key=lambda x: x[0], reverse=True)

    alignment: AlignmentMap = {}
    used_kg2: set[str] = set()

    for sim, id1, id2 in candidates:
        if id1 not in alignment and id2 not in used_kg2:
            alignment[id1] = id2
            used_kg2.add(id2)

    return alignment


# ---------------------------------------------------------------------------
# union
# ---------------------------------------------------------------------------

def union(
    kg1: KnowledgeGraph,
    kg2: KnowledgeGraph,
    alignment: Optional[AlignmentMap] = None,
    name: str = "union",
) -> KnowledgeGraph:
    """Merge two KGs into one.

    Aligned nodes from kg2 are merged into kg1 nodes (kg1 node wins).
    Unaligned kg2 nodes are added with a namespace prefix to avoid ID collision.
    """
    merged = KnowledgeGraph(name=name)
    alignment = alignment or {}
    reverse_alignment = {v: k for k, v in alignment.items()}

    # Add all kg1 nodes
    for node in kg1.nodes():
        merged.add_node(node)

    # Add kg2 nodes (skip those already aligned to kg1)
    for node in kg2.nodes():
        if node.id in reverse_alignment:
            continue  # this kg2 node is merged into a kg1 node
        # prefix to avoid collision
        new_id = f"{kg2.name}::{node.id}" if "::" not in node.id else node.id
        merged.add_node(KGNode(new_id, node.label, node.domain, node.attributes))

    # Add kg1 edges
    for edge in kg1.edges():
        try:
            merged.add_edge(edge)
        except ValueError:
            pass  # ignore if nodes missing (shouldn't happen)

    # Add kg2 edges (remap node IDs through alignment and prefix)
    def _remap(node_id: str) -> str:
        if node_id in reverse_alignment:
            return reverse_alignment[node_id]
        return f"{kg2.name}::{node_id}" if "::" not in node_id else node_id

    for edge in kg2.edges():
        src = _remap(edge.source_id)
        tgt = _remap(edge.target_id)
        new_edge = KGEdge(src, edge.relation, tgt, edge.weight, edge.attributes)
        try:
            merged.add_edge(new_edge)
        except ValueError:
            pass

    return merged


# ---------------------------------------------------------------------------
# difference
# ---------------------------------------------------------------------------

def difference(
    kg1: KnowledgeGraph,
    kg2: KnowledgeGraph,
    alignment: Optional[AlignmentMap] = None,
    name: str = "difference",
) -> KnowledgeGraph:
    """Extract nodes and edges in kg1 that have no counterpart in kg2.

    A node is 'unique to kg1' if it is not in the alignment.
    An edge is 'unique' if its source is a kg1-unique node.
    """
    alignment = alignment or {}
    aligned_kg1_ids = set(alignment.keys())

    diff = KnowledgeGraph(name=name)

    unique_node_ids: set[str] = set()
    for node in kg1.nodes():
        if node.id not in aligned_kg1_ids:
            diff.add_node(node)
            unique_node_ids.add(node.id)

    for edge in kg1.edges():
        if edge.source_id in unique_node_ids:
            if edge.target_id in diff._nodes:
                diff.add_edge(edge)

    return diff


# ---------------------------------------------------------------------------
# compose — filter helpers (Run 012)
# ---------------------------------------------------------------------------

# Relations considered mechanistically strong for strong-ratio guard.
_STRONG_MECHANISTIC: frozenset[str] = frozenset({
    "inhibits", "activates", "catalyzes", "produces", "encodes",
    "accelerates", "yields", "facilitates",
})

# Generic intermediate-node labels that reduce path specificity.
_GENERIC_INTERMEDIATE_LABELS: frozenset[str] = frozenset({
    "process", "system", "entity", "substance", "compound",
})


def _path_relations(path: list[str]) -> list[str]:
    """Extract relation types from a provenance path list."""
    return path[1::2]


def _path_intermediate_ids(path: list[str]) -> list[str]:
    """Extract intermediate node IDs (excluding source and target)."""
    node_ids = path[0::2]
    return node_ids[1:-1]


def _has_filtered_relation(
    path: list[str],
    filter_relations: frozenset[str],
) -> bool:
    """Return True if any relation in the path is in filter_relations."""
    return any(r in filter_relations for r in _path_relations(path))


def _has_consecutive_repeat(path: list[str]) -> bool:
    """Return True if the same relation type appears consecutively in the path."""
    rels = _path_relations(path)
    return any(rels[i] == rels[i + 1] for i in range(len(rels) - 1))


def _strong_ratio(path: list[str]) -> float:
    """Return fraction of relations in _STRONG_MECHANISTIC."""
    rels = _path_relations(path)
    if not rels:
        return 0.0
    return sum(1 for r in rels if r in _STRONG_MECHANISTIC) / len(rels)


def _has_generic_intermediate(path: list[str], kg: KnowledgeGraph) -> bool:
    """Return True if any intermediate node has a generic label."""
    for nid in _path_intermediate_ids(path):
        node = kg.get_node(nid)
        if node and any(w in node.label.lower() for w in _GENERIC_INTERMEDIATE_LABELS):
            return True
    return False


def _passes_compose_filters(
    path: list[str],
    kg: KnowledgeGraph,
    filter_relations: frozenset[str] | None,
    guard_consecutive_repeat: bool,
    min_strong_ratio: float,
    filter_generic_intermediates: bool,
) -> bool:
    """Return True if the path passes all enabled compose filters.

    Filters applied (each independently enabled/disabled):
    1. filter_relations: reject if any relation is in the blocked set.
    2. guard_consecutive_repeat: reject if same relation appears consecutively.
    3. min_strong_ratio: for depth≥3 paths, reject if strong-relation ratio < threshold.
    4. filter_generic_intermediates: reject if any intermediate node is generic.
    """
    hops = max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0

    if filter_relations and _has_filtered_relation(path, filter_relations):
        return False

    if guard_consecutive_repeat and _has_consecutive_repeat(path):
        return False

    if min_strong_ratio > 0.0 and hops >= 3:
        if _strong_ratio(path) < min_strong_ratio:
            return False

    if filter_generic_intermediates and _has_generic_intermediate(path, kg):
        return False

    return True


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------

def compose(
    kg: KnowledgeGraph,
    max_depth: int = 3,
    max_per_source: int = 0,
    _counter: list[int] | None = None,
    filter_relations: frozenset[str] | None = None,
    guard_consecutive_repeat: bool = False,
    min_strong_ratio: float = 0.0,
    filter_generic_intermediates: bool = False,
) -> list[HypothesisCandidate]:
    """Generate hypotheses by finding transitive paths in the KG.

    For each pair (A, C) where A->...->C exists but A->C does not,
    generate a HypothesisCandidate.

    Args:
        kg: Input knowledge graph.
        max_depth: BFS expansion depth limit. To get k-hop paths, use max_depth = 2k-1.
            Default 3 → 2-hop max. Use 9 for up to 5-hop paths.
        max_per_source: Cap on candidates per source node (0 = unlimited).
            Use to limit path explosion on large graphs.
        _counter: Shared ID counter (list of one int) for stable hypothesis IDs.
        filter_relations: Frozenset of relation types to exclude. Any path containing
            one of these relations is dropped before emitting a candidate.
            Default None (no filtering). Run 012 uses: contains, is_product_of,
            is_reverse_of, is_isomer_of.
        guard_consecutive_repeat: If True, reject paths where the same relation
            type appears consecutively (e.g. A→r→B→r→C). Default False.
        min_strong_ratio: Minimum fraction of relations in the path that must belong
            to _STRONG_MECHANISTIC. Applied only to paths with depth≥3. 0.0 = disabled.
        filter_generic_intermediates: If True, reject paths whose intermediate nodes
            have generic labels (process, system, entity, substance, compound).
            Default False.
    """
    if _counter is None:
        _counter = [0]

    use_filters = bool(
        filter_relations
        or guard_consecutive_repeat
        or min_strong_ratio > 0.0
        or filter_generic_intermediates
    )

    candidates: list[HypothesisCandidate] = []
    node_ids = [n.id for n in kg.nodes()]

    for source_id in node_ids:
        # BFS to find all reachable nodes within max_depth
        visited: dict[str, list[str]] = {source_id: [source_id]}  # node_id -> path
        queue: deque[tuple[str, list[str]]] = deque([(source_id, [source_id])])

        while queue:
            current_id, path = queue.popleft()
            if len(path) > max_depth + 1:
                continue

            for edge in kg.neighbors(current_id):
                neighbor_id = edge.target_id
                if neighbor_id == source_id:
                    continue  # skip self-loops
                if neighbor_id not in visited:
                    new_path = path + [edge.relation, neighbor_id]
                    visited[neighbor_id] = new_path
                    queue.append((neighbor_id, new_path))

        # Generate hypothesis for each reachable node (depth >= 2)
        source_candidates: list[HypothesisCandidate] = []
        for target_id, path in visited.items():
            if target_id == source_id:
                continue
            # path format: [src, rel1, mid1, rel2, ..., target]
            # length 3 = direct edge (src, rel, tgt) → skip
            if len(path) <= 3:
                continue  # direct path, not interesting
            if kg.has_direct_edge(source_id, target_id):
                continue  # already known

            # Apply compose filters (Run 012+) — skipped when all flags are off
            if use_filters and not _passes_compose_filters(
                path, kg,
                filter_relations=filter_relations,
                guard_consecutive_repeat=guard_consecutive_repeat,
                min_strong_ratio=min_strong_ratio,
                filter_generic_intermediates=filter_generic_intermediates,
            ):
                continue

            src_node = kg.get_node(source_id)
            tgt_node = kg.get_node(target_id)
            if src_node is None or tgt_node is None:
                continue

            _counter[0] += 1
            hyp_id = f"H{_counter[0]:04d}"
            inferred_relation = "transitively_related_to"
            description = (
                f"{src_node.label} may {inferred_relation} {tgt_node.label} "
                f"via path: {' -> '.join(str(p) for p in path)}"
            )
            source_candidates.append(
                HypothesisCandidate(
                    id=hyp_id,
                    subject_id=source_id,
                    relation=inferred_relation,
                    object_id=target_id,
                    description=description,
                    provenance=list(path),
                    operator="compose",
                    source_kg_name=kg.name,
                )
            )

        if max_per_source > 0:
            # Keep shortest paths first (BFS already tends this way)
            source_candidates.sort(key=lambda c: len(c.provenance))
            source_candidates = source_candidates[:max_per_source]

        candidates.extend(source_candidates)

    return candidates


# ---------------------------------------------------------------------------
# Cross-domain compose variant (Run 004)
# ---------------------------------------------------------------------------

def compose_cross_domain(
    kg: KnowledgeGraph,
    max_depth: int = 3,
    _counter: list[int] | None = None,
) -> list[HypothesisCandidate]:
    """Generate hypotheses restricted to cross-domain (subject.domain ≠ object.domain).

    Wrapper around compose() that filters out same-domain candidates.
    Useful for isolating the cross-domain contribution of the multi-op pipeline (H1 test).
    """
    all_candidates = compose(kg, max_depth=max_depth, _counter=_counter)
    return [
        c for c in all_candidates
        if _is_cross_domain_candidate(c, kg)
    ]


def _is_cross_domain_candidate(
    candidate: HypothesisCandidate,
    kg: KnowledgeGraph,
) -> bool:
    """Return True if subject and object belong to different domains."""
    src = kg.get_node(candidate.subject_id)
    tgt = kg.get_node(candidate.object_id)
    if src and tgt:
        return src.domain != tgt.domain
    # Fallback: parse domain from ID prefix
    s_prefix = candidate.subject_id.split(":")[0] if ":" in candidate.subject_id else ""
    t_prefix = candidate.object_id.split(":")[0] if ":" in candidate.object_id else ""
    return bool(s_prefix) and bool(t_prefix) and s_prefix != t_prefix


# ---------------------------------------------------------------------------
# Placeholder operators
# ---------------------------------------------------------------------------

def analogy_transfer_placeholder(
    source_kg: KnowledgeGraph,
    target_kg: KnowledgeGraph,
    alignment: AlignmentMap,
) -> list[HypothesisCandidate]:
    """Placeholder for analogy-transfer operator (not implemented in v0)."""
    return []


def belief_update_placeholder(
    hypotheses: list,
    evidence_kg: KnowledgeGraph,
) -> list:
    """Kept for backward compatibility. Use belief_update from pipeline.belief."""
    return hypotheses


# Re-export belief_update so callers can import from operators
from src.pipeline.belief import belief_update as belief_update  # noqa: E402,F401
