"""Temporal attributes and consistency helpers for KG nodes/edges."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.kg.models import KGEdge, KGNode

# ---------------------------------------------------------------------------
# Attribute key constants
# ---------------------------------------------------------------------------

ATTR_VALID_FROM: str = "valid_from"
ATTR_VALID_TO: str = "valid_to"
ATTR_OBSERVED_AT: str = "observed_at"
ATTR_CONFIDENCE: str = "confidence"


# ---------------------------------------------------------------------------
# Temporal attribute helpers
# ---------------------------------------------------------------------------

def set_temporal(
    item: "Union[KGNode, KGEdge]",
    *,
    valid_from: int | None = None,
    valid_to: int | None = None,
    observed_at: int | None = None,
    confidence: float = 1.0,
) -> None:
    """Write temporal attributes onto a KGNode or KGEdge.

    None values for valid_from, valid_to, observed_at are skipped (not written).
    confidence always defaults to 1.0 and is always written.
    """
    if valid_from is not None:
        item.attributes[ATTR_VALID_FROM] = valid_from
    if valid_to is not None:
        item.attributes[ATTR_VALID_TO] = valid_to
    if observed_at is not None:
        item.attributes[ATTR_OBSERVED_AT] = observed_at
    item.attributes[ATTR_CONFIDENCE] = confidence


def get_temporal(item: "Union[KGNode, KGEdge]") -> dict:
    """Return a dict with all four temporal keys for the given node or edge.

    Missing values are returned as None; confidence defaults to 1.0.
    """
    attrs = item.attributes
    return {
        ATTR_VALID_FROM: attrs.get(ATTR_VALID_FROM),
        ATTR_VALID_TO: attrs.get(ATTR_VALID_TO),
        ATTR_OBSERVED_AT: attrs.get(ATTR_OBSERVED_AT),
        ATTR_CONFIDENCE: attrs.get(ATTR_CONFIDENCE, 1.0),
    }


def is_valid_at(item: "Union[KGNode, KGEdge]", timestamp: int) -> bool:
    """Return True if the item is valid at the given timestamp (closed interval)."""
    attrs = item.attributes
    vf = attrs.get(ATTR_VALID_FROM)
    vt = attrs.get(ATTR_VALID_TO)
    if vf is not None and timestamp < vf:
        return False
    if vt is not None and timestamp > vt:
        return False
    return True


def filter_valid_at(items: list, timestamp: int) -> list:
    """Return only those items that are valid at the given timestamp."""
    return [it for it in items if is_valid_at(it, timestamp)]


def _intervals_overlap(from1: str, to1: str, from2: str, to2: str) -> bool:
    """Return True if the closed intervals [from1, to1] and [from2, to2] overlap.

    Uses lexicographic ISO 8601 comparison, which is correct for YYYY-MM-DD
    and YYYY-MM-DDTHH:MM:SS formats.
    """
    return from1 <= to2 and from2 <= to1


def edges_temporally_consistent(edges: list["KGEdge"]) -> bool:
    """Check whether a sequence of edges is temporally consistent.

    Two consecutive edges fail the check when:
    - Both have ``observed_at`` and the first's value is strictly greater than
      the second's (observations must be non-decreasing along the path).
    - Both have ``valid_from`` **and** ``valid_to`` and the validity intervals
      do not overlap (no common time window where both edges co-exist).

    Edges that lack the relevant temporal fields are exempt from each check.
    An empty or single-edge list is always consistent.

    Args:
        edges: Ordered list of KGEdge objects forming a path.

    Returns:
        True if no temporal contradiction is found, False otherwise.
    """
    for i in range(len(edges) - 1):
        e1, e2 = edges[i], edges[i + 1]

        # Check observed_at ordering
        if e1.observed_at is not None and e2.observed_at is not None:
            if e1.observed_at > e2.observed_at:
                return False

        # Check validity interval overlap
        if (
            e1.valid_from is not None and e1.valid_to is not None
            and e2.valid_from is not None and e2.valid_to is not None
        ):
            if not _intervals_overlap(e1.valid_from, e1.valid_to,
                                      e2.valid_from, e2.valid_to):
                return False

    return True
