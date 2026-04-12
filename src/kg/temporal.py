"""Temporal attribute helpers for KGNode and KGEdge (Phase A / Phase C).

Stores valid_from, valid_to, observed_at, confidence as standard keys
in the existing ``attributes`` dict on KGNode and KGEdge objects.
No schema changes to the core models are required.
"""

from __future__ import annotations

from typing import Union

from src.kg.models import KGEdge, KGNode

# ---------------------------------------------------------------------------
# Standard temporal attribute keys
# ---------------------------------------------------------------------------

ATTR_VALID_FROM = "valid_from"    # Unix ms: earliest validity
ATTR_VALID_TO = "valid_to"        # Unix ms: latest validity (inclusive)
ATTR_OBSERVED_AT = "observed_at"  # Unix ms: when this fact was observed
ATTR_CONFIDENCE = "confidence"    # float 0.0-1.0

_DEFAULT_CONFIDENCE: float = 1.0

TemporalObj = Union[KGNode, KGEdge]


def set_temporal(
    obj: TemporalObj,
    *,
    valid_from: int | None = None,
    valid_to: int | None = None,
    observed_at: int | None = None,
    confidence: float = _DEFAULT_CONFIDENCE,
) -> None:
    """Set temporal attributes on a KGNode or KGEdge in-place.

    Only writes keys for non-None values; confidence is always written.
    """
    if valid_from is not None:
        obj.attributes[ATTR_VALID_FROM] = valid_from
    if valid_to is not None:
        obj.attributes[ATTR_VALID_TO] = valid_to
    if observed_at is not None:
        obj.attributes[ATTR_OBSERVED_AT] = observed_at
    obj.attributes[ATTR_CONFIDENCE] = confidence


def get_temporal(obj: TemporalObj) -> dict:
    """Return temporal attributes as a dict.

    Keys: valid_from, valid_to, observed_at, confidence.
    Missing keys return None (except confidence which defaults to 1.0).
    """
    return {
        ATTR_VALID_FROM: obj.attributes.get(ATTR_VALID_FROM),
        ATTR_VALID_TO: obj.attributes.get(ATTR_VALID_TO),
        ATTR_OBSERVED_AT: obj.attributes.get(ATTR_OBSERVED_AT),
        ATTR_CONFIDENCE: obj.attributes.get(ATTR_CONFIDENCE, _DEFAULT_CONFIDENCE),
    }


def is_valid_at(obj: TemporalObj, timestamp_ms: int) -> bool:
    """Return True if obj is temporally valid at the given Unix ms timestamp.

    An object without valid_from/valid_to bounds is always considered valid.
    """
    vf = obj.attributes.get(ATTR_VALID_FROM)
    vt = obj.attributes.get(ATTR_VALID_TO)
    if vf is not None and timestamp_ms < vf:
        return False
    if vt is not None and timestamp_ms > vt:
        return False
    return True


def filter_valid_at(
    nodes: list[KGNode], timestamp_ms: int
) -> list[KGNode]:
    """Return only nodes that are temporally valid at the given timestamp."""
    return [n for n in nodes if is_valid_at(n, timestamp_ms)]
