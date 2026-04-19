"""Hypothesis Diversifier — generate competing interpretations for the same market state.

The existing pipeline produces mostly cross_asset (correlation_break) hypotheses.
This module takes a set of hypothesis candidates and generates counter-hypotheses
from alternative families to ensure the competition engine has meaningful choices.

Offline module — does not modify the live pipeline.
"""
from __future__ import annotations

from .hypothesis import (
    HypothesisNode,
    HypothesisStatus,
    InvalidationCondition,
    make_hypothesis_id,
)

_COUNTER_FAMILIES: dict[str, list[dict]] = {
    "momentum": {
        "claim_template": "{asset} price trend continues in current direction",
        "invalidation": "price reverses >50% of move within horizon",
        "horizon_min": 60.0,
        "base_evidence": 0.4,
    },
    "reversion": {
        "claim_template": "{asset} reverts to mean after recent dislocation",
        "invalidation": "spread continues widening beyond 2σ",
        "horizon_min": 40.0,
        "base_evidence": 0.4,
    },
    "regime_continuation": {
        "claim_template": "{asset} current regime persists — no structural change",
        "invalidation": "regime transition detected within horizon",
        "horizon_min": 120.0,
        "base_evidence": 0.45,
    },
}


def _calibrate_evidence(base: float, source_evidence: float) -> float:
    """Scale counter-hypothesis evidence relative to source strength.

    Stronger source evidence slightly boosts counter-evidence to maintain tension.
    Weaker source evidence reduces counter-evidence proportionally.
    """
    return min(0.9, base * (0.5 + 0.5 * source_evidence))


def generate_counter_hypotheses(
    source: HypothesisNode,
    families: list[str] | None = None,
) -> list[HypothesisNode]:
    """Generate counter-hypotheses for alternative family interpretations.

    For a given hypothesis, produce competing explanations from other families.
    Each counter-hypothesis has calibrated evidence strength and
    appropriate invalidation conditions.

    Args:
        source: the original hypothesis to generate counters for
        families: which families to generate (default: all non-source families)

    Returns:
        list of counter-hypothesis candidates
    """
    asset = source.metadata.get("asset", "unknown")
    target_families = families or [f for f in _COUNTER_FAMILIES if f != source.family]

    counters: list[HypothesisNode] = []
    for fam in target_families:
        template = _COUNTER_FAMILIES.get(fam)
        if template is None:
            continue

        claim = template["claim_template"].format(asset=asset)
        evidence = _calibrate_evidence(template["base_evidence"], source.evidence_strength)

        counter = HypothesisNode(
            hypothesis_id=make_hypothesis_id(
                claim, fam, source.created_at_ms + hash(fam) % 1000
            ),
            claim=claim,
            family=fam,
            status=HypothesisStatus.CANDIDATE,
            regime_dependency=list(source.regime_dependency),
            horizon_min=template["horizon_min"],
            evidence_strength=evidence,
            novelty=0.1,
            execution_feasibility=0.5,
            invalidation_conditions=[
                InvalidationCondition(description=template["invalidation"]),
            ],
            created_at_ms=source.created_at_ms,
            source_event_types=list(source.source_event_types),
            metadata={"asset": asset, "counter_to": source.hypothesis_id},
        )
        counters.append(counter)

    return counters


def diversify(
    hypotheses: list[HypothesisNode],
    min_families: int = 3,
) -> list[HypothesisNode]:
    """Ensure hypothesis diversity by generating counter-hypotheses where needed.

    For each asset group, if fewer than min_families families are represented,
    generate counter-hypotheses from missing families.

    Args:
        hypotheses: input candidates (may be family-homogeneous)
        min_families: minimum family count per asset (default 3)

    Returns:
        original hypotheses + generated counter-hypotheses
    """
    from collections import defaultdict

    by_asset: dict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        asset = h.metadata.get("asset", "unknown")
        by_asset[asset].append(h)

    result = list(hypotheses)
    for asset, group in by_asset.items():
        existing_families = {h.family for h in group}
        if len(existing_families) >= min_families:
            continue

        missing = [f for f in _COUNTER_FAMILIES if f not in existing_families]
        best = max(group, key=lambda h: h.evidence_strength)
        for fam in missing:
            counters = generate_counter_hypotheses(best, families=[fam])
            result.extend(counters)

    return result
