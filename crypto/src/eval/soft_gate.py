"""H1: Soft activation gating — continuous confidence scores for branch activation.

Replaces binary boolean gates with continuous [0, 1] confidence values so that
near-threshold cases are not silently killed.

Thresholds:
    SOFT_GATE_MIN = 0.30   below this: hard-killed (no activation)
    HARD_GATE_MIN = 0.50   above this: full activation (normal plausibility)
    Between 0.30 and 0.50: border-case activation (soft_gated=True)

Border-case hypotheses fire at reduced plausibility_prior (×0.55–0.70) and
carry the "soft_gated" tag so they are traceable through ranking.
"""

SOFT_GATE_MIN: float = 0.30
HARD_GATE_MIN: float = 0.50

_BORDER_SCALE_WITH_SUPPORT: float = 0.70
_BORDER_SCALE_WITHOUT_SUPPORT: float = 0.55


def compute_oi_accumulation_confidence(oi_states: list) -> float:
    """Continuous confidence that OI accumulation is genuine [0, 1].

    Full confidence when is_accumulation=True; border confidence when state_score
    exceeds SOFT_GATE_MIN but the accumulation flag is not set.

    Args:
        oi_states: List of OIState objects for the relevant assets.

    Returns:
        Float in [0, 1].  0.0 if no OI data or state_scores too low.
    """
    if not oi_states:
        return 0.0
    hard = [s for s in oi_states if s.is_accumulation]
    near = [s for s in oi_states if not s.is_accumulation and s.state_score > SOFT_GATE_MIN]
    if hard:
        mean_s = sum(s.state_score for s in hard) / len(hard)
        dur = max(s.build_duration for s in hard)
        return round(min(1.0, 0.55 + mean_s * 0.35 + min(0.10, dur * 0.005)), 3)
    if near:
        mean_s = sum(s.state_score for s in near) / len(near)
        return round(mean_s * 0.55, 3)
    return 0.0


def compute_funding_pressure_confidence(funding_states: list) -> float:
    """Continuous confidence that funding pressure is meaningful [0, 1].

    Full confidence when |z_score| >= 2.0.  Border confidence for |z| in [1.5, 2.0).

    Args:
        funding_states: List of FundingState objects for the relevant assets.

    Returns:
        Float in [0, 1].  0.0 if |z| < 1.5 for all states.
    """
    if not funding_states:
        return 0.0
    max_z = max(abs(s.z_score) for s in funding_states)
    if max_z >= 2.0:
        return round(min(1.0, 0.50 + (max_z - 2.0) * 0.10), 3)
    if max_z >= 1.5:
        return round((max_z - 1.5) / 2.0 * 0.35 + 0.10, 3)
    return 0.0


def compute_crowding_confidence(oi_states: list) -> float:
    """Continuous confidence that position crowding is present [0, 1].

    Derived from OI accumulation confidence plus build-duration bonus.

    Args:
        oi_states: List of OIState objects for the relevant assets.

    Returns:
        Float in [0, 1].
    """
    if not oi_states:
        return 0.0
    base = compute_oi_accumulation_confidence(oi_states)
    max_dur = max(s.build_duration for s in oi_states)
    return round(min(1.0, base + min(0.15, max_dur * 0.008)), 3)


def soft_activation_gate(
    primary_conf: float,
    other_evidence_conf: float = 0.0,
) -> dict:
    """Evaluate branch activation status from a continuous confidence score.

    Args:
        primary_conf: Confidence for the primary activation signal [0, 1].
        other_evidence_conf: Confidence of supporting secondary evidence [0, 1].

    Returns:
        Dict with keys hard_active, soft_active, border_case,
        effective_conf, plausibility_scale.
    """
    hard = primary_conf >= HARD_GATE_MIN
    soft = primary_conf >= SOFT_GATE_MIN
    border = soft and not hard
    if hard:
        scale = 1.0
    elif border:
        scale = (
            _BORDER_SCALE_WITH_SUPPORT
            if other_evidence_conf >= 0.60
            else _BORDER_SCALE_WITHOUT_SUPPORT
        )
    else:
        scale = 0.0
    return {
        "hard_active": hard,
        "soft_active": soft,
        "border_case": border,
        "effective_conf": round(primary_conf, 3),
        "plausibility_scale": scale,
    }
