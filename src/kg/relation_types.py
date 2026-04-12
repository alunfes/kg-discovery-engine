"""Typed relation constants for the KG belief update system.

Defines negative (contradicting/weakening) and positive relation categories
used by the belief_update operator to classify evidence edges.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Negative relation constants
# ---------------------------------------------------------------------------

CONTRADICTS = "contradicts"
"""Direct logical contradiction of a hypothesis path relationship."""

TEMPORALLY_INCONSISTENT = "temporally_inconsistent"
"""Temporal ordering in the evidence conflicts with the hypothesis path."""

CONFOUNDED_BY = "confounded_by"
"""A confounding factor undermines the causal claim in the path."""

HUB_ARTIFACT = "hub_artifact"
"""Bridge node appears in too many unrelated contexts (hub node bias)."""

GENERIC_BRIDGE = "generic_bridge"
"""Bridge node is too generic to support a specific hypothesis chain."""

# ---------------------------------------------------------------------------
# Grouped relation sets
# ---------------------------------------------------------------------------

NEGATIVE_RELATIONS: frozenset[str] = frozenset({
    CONTRADICTS,
    TEMPORALLY_INCONSISTENT,
    CONFOUNDED_BY,
    HUB_ARTIFACT,
    GENERIC_BRIDGE,
})
"""All relations that degrade hypothesis confidence when found on path nodes."""

WEAKENING_RELATIONS: frozenset[str] = frozenset({
    HUB_ARTIFACT,
    GENERIC_BRIDGE,
})
"""Subset of negative relations that indicate path quality issues (weakening)."""

STRONG_POSITIVE_RELATIONS: frozenset[str] = frozenset({
    "inhibits",
    "activates",
    "catalyzes",
    "produces",
    "encodes",
    "accelerates",
    "yields",
    "facilitates",
})
"""Mechanistically strong positive relations that provide robust support."""
