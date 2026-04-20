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


def _calibrate_evidence(
    base: float,
    source_evidence: float,
    counter_family: str = "",
    signal_rho: float | None = None,
    signal_break_score: float | None = None,
) -> float:
    """Scale counter-hypothesis evidence relative to source strength and signal metrics.

    Dynamic calibration: the "most plausible counter" gets boosted based on signal.
    - high |rho| → reversion counter is stronger (trend exhaustion likely)
    - low |rho| → momentum counter is stronger (trend may persist)
    - high break_score → regime_continuation gets a slight boost
    """
    rho_abs = min(abs(signal_rho), 1.0) if signal_rho is not None else 0.0
    bs_norm = min((signal_break_score or 0.0) / 2.0, 1.0)

    if counter_family == "reversion":
        ratio = 0.50 + 0.20 * rho_abs + 0.08 * bs_norm
    elif counter_family == "momentum":
        ratio = 0.50 + 0.20 * (1.0 - rho_abs) + 0.06 * bs_norm
    elif counter_family == "regime_continuation":
        ratio = 0.45 + 0.15 * bs_norm
    else:
        ratio = 0.50

    ratio = max(0.40, min(0.78, ratio))
    calibrated = source_evidence * ratio
    floor = max(0.10, 0.30 * source_evidence)
    return max(floor, min(calibrated, source_evidence - 0.01))


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
        evidence = _calibrate_evidence(
            template["base_evidence"],
            source.evidence_strength,
            counter_family=fam,
            signal_rho=source.metadata.get("signal_rho"),
            signal_break_score=source.metadata.get("signal_break_score"),
        )

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
    group_key: str = "cycle_asset",
) -> list[HypothesisNode]:
    """Ensure hypothesis diversity by generating counter-hypotheses where needed.

    Groups hypotheses by (asset, cycle) and ensures each group has at least
    min_families distinct families. This aligns with cycle_asset competition grouping.

    Args:
        hypotheses: input candidates (may be family-homogeneous)
        min_families: minimum family count per group (default 3)
        group_key: "cycle_asset" (recommended) or "asset"

    Returns:
        original hypotheses + generated counter-hypotheses
    """
    from collections import defaultdict

    groups: dict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        asset = h.metadata.get("asset", "unknown")
        if group_key == "cycle_asset":
            cycle = h.metadata.get("_cycle", 0)
            key = f"{asset}:c{cycle:03d}"
        else:
            key = asset
        groups[key].append(h)

    result = list(hypotheses)
    for key, group in groups.items():
        existing_families = {h.family for h in group}
        if len(existing_families) >= min_families:
            continue

        missing = [f for f in _COUNTER_FAMILIES if f not in existing_families]
        best = max(group, key=lambda h: h.evidence_strength)
        for fam in missing:
            counters = generate_counter_hypotheses(best, families=[fam])
            for c in counters:
                c.metadata["_cycle"] = best.metadata.get("_cycle", 0)
            result.extend(counters)

    return result
