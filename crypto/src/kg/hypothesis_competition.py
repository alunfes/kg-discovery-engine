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
    InvalidationCondition,
    SemanticRelation,
    make_hypothesis_id,
    make_semantic_edge,
)

# ---------------------------------------------------------------------------
# Null Hypothesis — baseline that every group must beat
# ---------------------------------------------------------------------------

_NULL_EVIDENCE = 0.35  # null must be beaten by this margin to justify a trade

# ---------------------------------------------------------------------------
# Regime-conditioned Evidence Decay
# ---------------------------------------------------------------------------

_FAMILY_PREFERRED_REGIMES: dict[str, set[str]] = {
    "momentum": {"aggressive_buying", "aggressive_selling"},
    "flow_continuation": {"aggressive_buying", "aggressive_selling"},
    "reversion": {"spread_widening", "funding_extreme_long", "funding_extreme_short"},
    "beta_reversion": {"correlation_break", "spread_widening"},
    "cross_asset": {"correlation_break"},
    "positioning_unwind": {"funding_extreme_long", "funding_extreme_short"},
    "regime_continuation": {"resting_liquidity"},
    "null": set(),  # null is regime-agnostic
}

_REGIME_DECAY_FACTOR = 0.5


def apply_regime_decay(
    hypotheses: list["HypothesisNode"],
    current_regime: str,
) -> None:
    """Decay evidence_strength for hypotheses whose preferred regime doesn't match.

    Mutates hypotheses in place. Null hypotheses are unaffected.
    A momentum hypothesis in a resting_liquidity regime gets its evidence halved.
    """
    for h in hypotheses:
        if h.metadata.get("is_null"):
            continue
        preferred = _FAMILY_PREFERRED_REGIMES.get(h.family, set())
        if not preferred:
            continue
        if current_regime not in preferred:
            h.evidence_strength *= _REGIME_DECAY_FACTOR
            h.metadata["regime_decayed"] = True
            h.metadata["regime_mismatch"] = current_regime


def make_null_hypothesis(group_key: str, timestamp_ms: int = 0) -> HypothesisNode:
    """Create a "no edge / do nothing" baseline hypothesis.

    Any real hypothesis that can't beat the null should not produce a signal.
    """
    return HypothesisNode(
        hypothesis_id=make_hypothesis_id(f"null:{group_key}", "null", timestamp_ms),
        claim=f"No actionable edge exists for {group_key}",
        family="null",
        status=HypothesisStatus.ACTIVE,
        evidence_strength=_NULL_EVIDENCE,
        contradiction_pressure=0.0,
        execution_feasibility=1.0,
        invalidation_conditions=[
            InvalidationCondition(description="any hypothesis beats null with margin > 0.1"),
        ],
        metadata={"is_null": True},
    )


# ---------------------------------------------------------------------------
# Arbitration Scope
# ---------------------------------------------------------------------------

def group_by_scope(
    hypotheses: list[HypothesisNode],
) -> dict[str, list[HypothesisNode]]:
    """Group by arbitration scope: asset × regime.

    This is the recommended grouping for competition — hypotheses compete
    within the same asset and regime context.
    """
    groups: dict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        asset = h.metadata.get("asset", _extract_asset_from_claim(h.claim))
        regime = h.regime_dependency[0] if h.regime_dependency else "any"
        key = f"{asset}:{regime}"
        groups[key].append(h)
    return dict(groups)


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
    """Whether two families represent opposing market views.

    null contradicts every non-null family — it claims "no edge exists."
    """
    if fam_a == "null" or fam_b == "null":
        return fam_a != fam_b
    opposing = {
        frozenset({"momentum", "reversion"}),
        frozenset({"flow_continuation", "positioning_unwind"}),
        frozenset({"momentum", "beta_reversion"}),
        frozenset({"cross_asset", "reversion"}),
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
    inject_null: bool = True,
) -> Optional[CompetitionResult]:
    """Rank competing hypotheses and select primary.

    A null hypothesis is automatically injected unless disabled.
    Hypotheses are ranked by net_evidence(). Opposing families generate
    contradiction edges. Observations are suggested to resolve ambiguity.

    Args:
        hypotheses: candidates competing for the same market explanation
        group_key:  label for this competition group
        inject_null: auto-inject a null baseline (default True)

    Returns:
        CompetitionResult or None if no candidates
    """
    if not hypotheses:
        return None

    if inject_null and not any(h.metadata.get("is_null") for h in hypotheses):
        ts = hypotheses[0].created_at_ms if hypotheses else 0
        hypotheses = list(hypotheses) + [make_null_hypothesis(group_key, ts)]

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
    inject_null: bool = True,
) -> list[CompetitionResult]:
    """Run arbitration across all groups.

    Args:
        hypotheses: all hypothesis candidates from a pipeline run
        group_fn:   "asset", "family", or "scope" (asset×regime) grouping
        inject_null: auto-inject null baseline per group (default True)

    Returns:
        list of CompetitionResult, one per group
    """
    if group_fn == "family":
        groups = group_by_family(hypotheses)
    elif group_fn == "scope":
        groups = group_by_scope(hypotheses)
    else:
        groups = group_by_asset(hypotheses)

    results: list[CompetitionResult] = []
    for key, group in sorted(groups.items()):
        result = arbitrate(group, group_key=key, inject_null=inject_null)
        if result is not None:
            results.append(result)
    return results
