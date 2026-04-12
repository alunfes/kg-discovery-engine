"""Temporal consistency helpers for KG edges (Phase A)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.kg.models import KGEdge


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
