"""Cross-asset hypothesis subtype classifier.

Classifies cross_asset hypothesis cards into subtypes based on claim content
and evidence structure. This enables within-family differentiation for
competition groups where all candidates are cross_asset.

Subtypes:
- true_break: strong correlation breakdown with supporting evidence
- transient_dislocation: temporary dislocation, likely to revert
- crowding_unwind: OI buildup + position crowding → unwind expected
- false_alarm: weak or contradictory evidence, likely noise
"""
from __future__ import annotations

import re
from typing import Optional

from .hypothesis import HypothesisNode


class CrossAssetSubtype:
    TRUE_BREAK = "true_break"
    TRANSIENT_DISLOCATION = "transient_dislocation"
    CROWDING_UNWIND = "crowding_unwind"
    FALSE_ALARM = "false_alarm"


def classify_subtype(hypothesis: HypothesisNode) -> str:
    """Classify a cross_asset hypothesis into a subtype.

    Uses claim text patterns, evidence count, and score heuristics.
    """
    claim = hypothesis.claim.lower()
    evidence_count = len(hypothesis.supporting_evidence)
    net_ev = hypothesis.net_evidence()

    if net_ev < 0.35:
        return CrossAssetSubtype.FALSE_ALARM

    has_oi = "oi" in claim or "onesidedoi" in claim.replace(" ", "")
    has_crowding = "crowding" in claim or "crowd" in claim
    has_break = "break" in claim
    has_fragile = "fragile" in claim or "dislocation" in claim

    if has_oi and has_crowding:
        return CrossAssetSubtype.CROWDING_UNWIND

    if has_fragile or (has_break and evidence_count <= 1):
        return CrossAssetSubtype.TRANSIENT_DISLOCATION

    if has_break and evidence_count >= 2 and net_ev >= 0.5:
        return CrossAssetSubtype.TRUE_BREAK

    return CrossAssetSubtype.TRANSIENT_DISLOCATION


def annotate_subtypes(hypotheses: list[HypothesisNode]) -> None:
    """Add subtype metadata to cross_asset hypotheses. Mutates in place."""
    for h in hypotheses:
        if h.family == "cross_asset":
            h.metadata["subtype"] = classify_subtype(h)
