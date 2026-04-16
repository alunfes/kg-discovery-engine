"""Relation type definitions and path-level type compatibility checks (Phase A)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.kg.models import KGEdge

# ---------------------------------------------------------------------------
# Canonical relation type labels
# ---------------------------------------------------------------------------

RELATION_TYPES: frozenset[str] = frozenset({
    "causal",       # X causes / enables / drives Y
    "structural",   # X is-part-of / is-component-of Y
    "statistical",  # X correlates-with / predicts Y
    "temporal",     # X precedes / follows / overlaps-with Y
    "evidential",   # X supports / contradicts / confirms Y
    "ontological",  # X is-a / subclass-of / equivalent-to Y
})

# ---------------------------------------------------------------------------
# Specific negative / weakening relation labels
# ---------------------------------------------------------------------------

CONTRADICTS: str = "contradicts"
TEMPORALLY_INCONSISTENT: str = "temporally_inconsistent"
CONFOUNDED_BY: str = "confounded_by"
HUB_ARTIFACT: str = "hub_artifact"
GENERIC_BRIDGE: str = "generic_bridge"

# Relations that cast doubt on or negate a hypothesis path
NEGATIVE_RELATIONS: frozenset[str] = frozenset({
    CONTRADICTS,
    TEMPORALLY_INCONSISTENT,
    CONFOUNDED_BY,
    HUB_ARTIFACT,
    GENERIC_BRIDGE,
})

# Subset used to classify "weakening" evidence (unreliable bridge signals)
WEAKENING_RELATIONS: frozenset[str] = frozenset({
    HUB_ARTIFACT,
    GENERIC_BRIDGE,
})


# ---------------------------------------------------------------------------
# Path type validation
# ---------------------------------------------------------------------------

def path_type_check(
    edges: list["KGEdge"],
    allowed: frozenset[tuple[str, str]] | None,
    flagged: frozenset[tuple[str, str]] | None,
) -> tuple[bool, list[str]]:
    """Check relation-type compatibility along a sequence of edges.

    Only consecutive pairs where **both** edges have a ``relation_type`` set
    are evaluated.  Edges without a type are exempt from all checks.

    Args:
        edges: Ordered list of KGEdge objects forming a path.
        allowed: If not None, only these ``(type_a, type_b)`` consecutive
                 pairs are permitted.  Any other typed pair causes rejection.
        flagged: If not None, these ``(type_a, type_b)`` pairs are allowed but
                 trigger a warning flag in the returned list.

    Returns:
        ``(is_allowed, flags)`` — ``is_allowed`` is False when the path must
        be rejected; ``flags`` contains human-readable warning strings for
        flagged transitions.
    """
    flags: list[str] = []

    for i in range(len(edges) - 1):
        t1 = edges[i].relation_type
        t2 = edges[i + 1].relation_type

        if t1 is None or t2 is None:
            continue  # at least one edge untyped — exempt

        pair = (t1, t2)

        if allowed is not None and pair not in allowed:
            return False, []

        if flagged is not None and pair in flagged:
            flags.append(f"type_transition:{t1}->{t2}")

    return True, flags
