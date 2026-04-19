"""Competing Hypotheses Engine — offline arbitration between hypothesis candidates.

Given a set of HypothesisNodes derived from the same market window,
this module identifies competing explanations, scores them relative to each other,
and recommends which to pursue and what observations would resolve ambiguity.

This is an offline / post-processing module. It does NOT modify the live pipeline.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .base import KGEdge, KGraph
from .hypothesis import (
    HypothesisNode,
    HypothesisStatus,
    SemanticRelation,
    make_semantic_edge,
)


@dataclass
class CompetitionResult:
    """Output of hypothesis arbitration for one competition group.

    Attributes:
        group_key:        what these hypotheses compete over (e.g. asset or regime)
        primary:          highest net-evidence hypothesis
        alternatives:     other candidates in descending net-evidence order
        contradiction_edges: edges recording inter-hypothesis contradictions
        discriminating_observations: observations that would distinguish alternatives
        confidence:       how clearly the primary separates from alternatives [0, 1]
    """

    group_key: str
    primary: HypothesisNode
    alternatives: list[HypothesisNode]
    contradiction_edges: list[KGEdge] = field(default_factory=list)
    discriminating_observations: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "group_key": self.group_key,
            "primary_id": self.primary.hypothesis_id,
            "primary_claim": self.primary.claim,
            "primary_net_evidence": round(self.primary.net_evidence(), 4),
            "n_alternatives": len(self.alternatives),
            "alternatives": [
                {
                    "id": a.hypothesis_id,
                    "claim": a.claim,
                    "net_evidence": round(a.net_evidence(), 4),
                }
                for a in self.alternatives
            ],
            "discriminating_observations": self.discriminating_observations,
            "confidence": round(self.confidence, 4),
        }


def group_by_asset(hypotheses: list[HypothesisNode]) -> dict[str, list[HypothesisNode]]:
    """Group hypotheses by the asset they reference (from metadata or claim)."""
    groups: dict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        asset = h.metadata.get("asset", _extract_asset_from_claim(h.claim))
        groups[asset].append(h)
    return dict(groups)


def group_by_family(hypotheses: list[HypothesisNode]) -> dict[str, list[HypothesisNode]]:
    """Group hypotheses by grammar family."""
    groups: dict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        groups[h.family].append(h)
    return dict(groups)


def _extract_asset_from_claim(claim: str) -> str:
    """Best-effort asset extraction from claim text."""
    for token in ["BTC", "ETH", "HYPE", "SOL"]:
        if token in claim.upper():
            return token
    return "unknown"


def _family_contradicts(fam_a: str, fam_b: str) -> bool:
    """Whether two families represent opposing market views."""
    opposing = {
        frozenset({"momentum", "reversion"}),
        frozenset({"flow_continuation", "positioning_unwind"}),
        frozenset({"momentum", "beta_reversion"}),
    }
    return frozenset({fam_a, fam_b}) in opposing


def _compute_confidence(primary: HypothesisNode, alternatives: list[HypothesisNode]) -> float:
    """How clearly the primary separates from the best alternative."""
    if not alternatives:
        return 1.0
    gap = primary.net_evidence() - alternatives[0].net_evidence()
    return max(0.0, min(1.0, gap * 2.0))


def _suggest_observations(
    primary: HypothesisNode,
    alternatives: list[HypothesisNode],
) -> list[str]:
    """Suggest observations that would distinguish competing hypotheses."""
    suggestions: list[str] = []
    for alt in alternatives:
        if primary.family != alt.family:
            if _family_contradicts(primary.family, alt.family):
                suggestions.append(
                    f"observe price action at horizon={primary.horizon_min:.0f}min "
                    f"to distinguish {primary.family} vs {alt.family}"
                )
        for ic in alt.invalidation_conditions:
            if ic.metric:
                suggestions.append(f"check {ic.metric} {ic.operator} {ic.threshold}")

    primary_obs = list(primary.next_observations)
    for alt in alternatives:
        primary_obs.extend(alt.next_observations)

    return list(dict.fromkeys(suggestions + primary_obs))[:5]


def arbitrate(
    hypotheses: list[HypothesisNode],
    group_key: str = "default",
) -> Optional[CompetitionResult]:
    """Rank competing hypotheses and select primary.

    Hypotheses are ranked by net_evidence(). Opposing families generate
    contradiction edges. Observations are suggested to resolve ambiguity.

    Args:
        hypotheses: candidates competing for the same market explanation
        group_key:  label for this competition group

    Returns:
        CompetitionResult or None if no candidates
    """
    if not hypotheses:
        return None

    ranked = sorted(hypotheses, key=lambda h: h.net_evidence(), reverse=True)
    primary = ranked[0]
    alternatives = ranked[1:]

    contradiction_edges: list[KGEdge] = []
    for alt in alternatives:
        if _family_contradicts(primary.family, alt.family):
            edge = make_semantic_edge(
                primary.hypothesis_id,
                alt.hypothesis_id,
                SemanticRelation.CONTRADICTS,
                reason=f"opposing families: {primary.family} vs {alt.family}",
            )
            contradiction_edges.append(edge)
            primary.alternative_ids.append(alt.hypothesis_id)
            alt.alternative_ids.append(primary.hypothesis_id)

    observations = _suggest_observations(primary, alternatives)
    confidence = _compute_confidence(primary, alternatives)

    return CompetitionResult(
        group_key=group_key,
        primary=primary,
        alternatives=alternatives,
        contradiction_edges=contradiction_edges,
        discriminating_observations=observations,
        confidence=confidence,
    )


def compete_all(
    hypotheses: list[HypothesisNode],
    group_fn: str = "asset",
) -> list[CompetitionResult]:
    """Run arbitration across all groups.

    Args:
        hypotheses: all hypothesis candidates from a pipeline run
        group_fn:   "asset" or "family" grouping strategy

    Returns:
        list of CompetitionResult, one per group
    """
    if group_fn == "family":
        groups = group_by_family(hypotheses)
    else:
        groups = group_by_asset(hypotheses)

    results: list[CompetitionResult] = []
    for key, group in sorted(groups.items()):
        result = arbitrate(group, group_key=key)
        if result is not None:
            results.append(result)
    return results
