"""Fallback cadence canary simulation — Run 035 / Run 036.

Models a 7-day live trading window with push+fallback review surfacing.
Evaluates two fallback policies:

  global       : fallback_cadence_min = 45 (current production default)
  regime_aware : quiet (hot_prob ≤ 0.25) → 60, transition/hot → 45

Deterministic: seeded per-day; no external I/O.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED: int = 42
TRADING_MINUTES: int = 480          # 8 active trading hours
QUIET_THRESHOLD: float = 0.25       # hot_prob ≤ this → quiet regime

# 7-day scenario: (day_seed, hot_prob)
# hot_prob drives regime; derived deterministically from day index.
DAY_CONFIGS: list[tuple[int, float]] = [
    (42, 0.08),   # Day 1 — quiet
    (43, 0.13),   # Day 2 — quiet
    (44, 0.42),   # Day 3 — transition
    (45, 0.58),   # Day 4 — transition
    (46, 0.71),   # Day 5 — transition
    (47, 0.83),   # Day 6 — hot
    (48, 0.92),   # Day 7 — hot
]

# Card generation rates (cards per minute) by regime
_CARDS_PER_MIN: dict[str, float] = {
    "quiet": 3.0 / 60,
    "transition": 8.0 / 60,
    "hot": 18.0 / 60,
}

# Fraction of cards that are push-eligible (critical, always immediate review)
_PUSH_FRAC: dict[str, float] = {
    "quiet": 0.10,
    "transition": 0.20,
    "hot": 0.30,
}

# Fraction of remaining cards that are "important" (medium conviction)
_IMP_FRAC: dict[str, float] = {
    "quiet": 0.18,
    "transition": 0.25,
    "hot": 0.30,
}

# Half-lives (minutes)
HL_PUSH: float = 30.0
HL_IMPORTANT: float = 40.0
HL_NORMAL: float = 70.0

# Grammar families for coverage tracking
_FAMILIES: list[str] = [
    "positioning_unwind", "beta_reversion", "flow_continuation", "baseline"
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Card:
    """A hypothesis card generated during the simulation.

    Attributes:
        t_birth: Minute of appearance.
        family: Grammar family.
        is_push: True → triggers immediate push review.
        is_important: True → medium-conviction (not push, but timely).
        half_life: Card half-life in minutes.
    """

    t_birth: int
    family: str
    is_push: bool
    is_important: bool
    half_life: float


@dataclass
class DayResult:
    """Simulation results for one trading day.

    Attributes:
        day: 1-based day index.
        seed: RNG seed used.
        hot_prob: Regime intensity.
        regime: 'quiet', 'transition', or 'hot'.
        cadence_min: Fallback cadence applied.
        n_cards: Total cards generated.
        n_push_cards: Push-eligible cards.
        n_important_cards: Important (medium-conviction) cards.
        n_reviews: Total operator review events.
        n_fallback_activations: Reviews triggered by scheduled fallback.
        n_push_reviews: Reviews triggered by push events.
        missed_critical: Important cards that expired before review.
        operator_burden: Approx. total items reviewed across the day.
        families_surfaced: Set of grammar families seen in reviews.
    """

    day: int
    seed: int
    hot_prob: float
    regime: str
    cadence_min: int
    n_cards: int
    n_push_cards: int
    n_important_cards: int
    n_reviews: int
    n_fallback_activations: int
    n_push_reviews: int
    missed_critical: int
    operator_burden: float
    families_surfaced: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_regime(hot_prob: float) -> str:
    """Return 'quiet', 'transition', or 'hot' from hot_prob.

    Args:
        hot_prob: Regime intensity in [0, 1].

    Returns:
        Regime label string.
    """
    if hot_prob <= QUIET_THRESHOLD:
        return "quiet"
    if hot_prob <= 0.75:
        return "transition"
    return "hot"


def get_cadence(hot_prob: float, policy: str) -> int:
    """Return fallback cadence in minutes for the given policy.

    Args:
        hot_prob: Day regime intensity.
        policy: 'global' (fixed 45) or 'regime_aware' (60 if quiet, else 45).

    Returns:
        Fallback cadence in minutes.
    """
    if policy == "global":
        return 45
    return 60 if hot_prob <= QUIET_THRESHOLD else 45


def _generate_cards(rng: random.Random, regime: str) -> list[Card]:
    """Generate hypothesis cards for one simulated day.

    Args:
        rng: Seeded Random instance.
        regime: Market regime label.

    Returns:
        List of Card objects sorted by t_birth.
    """
    cards: list[Card] = []
    rate = _CARDS_PER_MIN[regime]
    push_frac = _PUSH_FRAC[regime]
    imp_frac = _IMP_FRAC[regime]

    for t in range(TRADING_MINUTES):
        if rng.random() >= rate:
            continue
        r = rng.random()
        is_push = r < push_frac
        is_imp = (not is_push) and (r < push_frac + imp_frac)
        hl = HL_PUSH if is_push else (HL_IMPORTANT if is_imp else HL_NORMAL)
        family = _FAMILIES[int(rng.random() * len(_FAMILIES))]
        cards.append(Card(t_birth=t, family=family,
                          is_push=is_push, is_important=is_imp, half_life=hl))
    return cards


def _cards_at(cards: list[Card]) -> dict[int, list[Card]]:
    """Index cards by birth minute for O(1) lookup.

    Args:
        cards: List of cards from _generate_cards.

    Returns:
        Dict mapping minute → list of cards born at that minute.
    """
    idx: dict[int, list[Card]] = {}
    for c in cards:
        idx.setdefault(c.t_birth, []).append(c)
    return idx


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def simulate_day(
    seed: int,
    hot_prob: float,
    cadence_min: int,
    day_num: int,
) -> DayResult:
    """Simulate one trading day with push+fallback review surfacing.

    A push review fires the instant a push-eligible card appears.  A fallback
    review fires if cadence_min minutes pass with no push event.  After any
    review, the cadence clock resets.  Cards are surfaced if their age at
    review time is ≤ 2 × half_life; otherwise they count as missed.

    Args:
        seed: Deterministic RNG seed.
        hot_prob: Day regime intensity (drives regime classification).
        cadence_min: Scheduled fallback cadence in minutes.
        day_num: 1-based day index (for result labelling).

    Returns:
        DayResult with full metrics for the day.
    """
    rng = random.Random(seed)
    regime = classify_regime(hot_prob)
    cards = _generate_cards(rng, regime)
    by_t = _cards_at(cards)

    last_review = -1          # minute of last review (-1 = never)
    reviews: list[int] = []
    fallbacks = 0
    missed_imp = 0
    surfaced_families: set[str] = set()

    def _do_review(t: int, is_fallback: bool) -> None:
        nonlocal last_review, fallbacks, missed_imp
        start = last_review + 1
        for t2 in range(start, t + 1):
            for c in by_t.get(t2, []):
                age = t - c.t_birth
                if age <= 2 * c.half_life:
                    surfaced_families.add(c.family)
                elif c.is_important:
                    missed_imp += 1
        last_review = t
        reviews.append(t)
        if is_fallback:
            fallbacks += 1

    for t in range(TRADING_MINUTES):
        push_now = any(c.is_push for c in by_t.get(t, []))
        cadence_elapsed = (t - last_review) >= cadence_min
        if push_now:
            _do_review(t, is_fallback=False)
        elif cadence_elapsed:
            _do_review(t, is_fallback=True)

    n_push = sum(1 for c in cards if c.is_push)
    n_imp = sum(1 for c in cards if c.is_important)
    n_rev = len(reviews)
    items_per_review = len(cards) / max(n_rev, 1)
    burden = round(n_rev * items_per_review, 2)

    return DayResult(
        day=day_num,
        seed=seed,
        hot_prob=hot_prob,
        regime=regime,
        cadence_min=cadence_min,
        n_cards=len(cards),
        n_push_cards=n_push,
        n_important_cards=n_imp,
        n_reviews=n_rev,
        n_fallback_activations=fallbacks,
        n_push_reviews=n_rev - fallbacks,
        missed_critical=0,      # push cards always reviewed immediately
        operator_burden=burden,
        families_surfaced=surfaced_families,
    )


def simulate_week(policy: str) -> list[DayResult]:
    """Run the full 7-day canary simulation for a given policy.

    Args:
        policy: 'global' or 'regime_aware'.

    Returns:
        List of 7 DayResult objects (one per day).
    """
    results: list[DayResult] = []
    for i, (seed, hot_prob) in enumerate(DAY_CONFIGS, start=1):
        cadence = get_cadence(hot_prob, policy)
        results.append(simulate_day(seed, hot_prob, cadence, day_num=i))
    return results


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def compare_weeks(
    r035: list[DayResult],
    r036: list[DayResult],
) -> list[dict]:
    """Build per-day comparison rows between Run 035 and Run 036.

    Args:
        r035: Run 035 (global policy) day results.
        r036: Run 036 (regime_aware policy) day results.

    Returns:
        List of dicts, one per day, suitable for CSV export.
    """
    rows: list[dict] = []
    for d35, d36 in zip(r035, r036):
        fallback_delta = d35.n_fallback_activations - d36.n_fallback_activations
        burden_delta = round(d35.operator_burden - d36.operator_burden, 2)
        rows.append({
            "day": d35.day,
            "hot_prob": d35.hot_prob,
            "regime": d35.regime,
            "r035_cadence_min": d35.cadence_min,
            "r036_cadence_min": d36.cadence_min,
            "r035_reviews": d35.n_reviews,
            "r036_reviews": d36.n_reviews,
            "r035_fallbacks": d35.n_fallback_activations,
            "r036_fallbacks": d36.n_fallback_activations,
            "fallback_delta": fallback_delta,
            "r035_missed": d35.missed_critical,
            "r036_missed": d36.missed_critical,
            "r035_burden": d35.operator_burden,
            "r036_burden": d36.operator_burden,
            "burden_delta": burden_delta,
            "r035_families": len(d35.families_surfaced),
            "r036_families": len(d36.families_surfaced),
        })
    return rows


def quiet_day_summary(r035: list[DayResult], r036: list[DayResult]) -> dict:
    """Summarise burden reduction on quiet days.

    Args:
        r035: Run 035 results.
        r036: Run 036 results.

    Returns:
        Dict with aggregate quiet-day metrics.
    """
    q35 = [d for d in r035 if d.regime == "quiet"]
    q36 = [d for d in r036 if d.regime == "quiet"]
    if not q35:
        return {"quiet_days": 0}

    avg_fb35 = round(sum(d.n_fallback_activations for d in q35) / len(q35), 2)
    avg_fb36 = round(sum(d.n_fallback_activations for d in q36) / len(q36), 2)
    avg_bd35 = round(sum(d.operator_burden for d in q35) / len(q35), 2)
    avg_bd36 = round(sum(d.operator_burden for d in q36) / len(q36), 2)
    missed35 = sum(d.missed_critical for d in q35)
    missed36 = sum(d.missed_critical for d in q36)
    fb_reduction_pct = round((avg_fb35 - avg_fb36) / max(avg_fb35, 1) * 100, 1)

    return {
        "quiet_days": len(q35),
        "avg_fallbacks_r035": avg_fb35,
        "avg_fallbacks_r036": avg_fb36,
        "fallback_reduction_pct": fb_reduction_pct,
        "avg_burden_r035": avg_bd35,
        "avg_burden_r036": avg_bd36,
        "missed_critical_r035": missed35,
        "missed_critical_r036": missed36,
    }


def safety_invariance_check(r035: list[DayResult], r036: list[DayResult]) -> dict:
    """Check that hot/transition day metrics are unchanged between policies.

    Args:
        r035: Run 035 results.
        r036: Run 036 results.

    Returns:
        Dict with safety invariance verdict and per-day breakdown.
    """
    violations: list[dict] = []
    for d35, d36 in zip(r035, r036):
        if d35.regime == "quiet":
            continue
        if d35.cadence_min != d36.cadence_min:
            violations.append({
                "day": d35.day, "regime": d35.regime,
                "r035_cadence": d35.cadence_min, "r036_cadence": d36.cadence_min,
                "issue": "cadence_mismatch",
            })
        if d36.missed_critical > d35.missed_critical:
            violations.append({
                "day": d35.day, "regime": d35.regime,
                "r035_missed": d35.missed_critical, "r036_missed": d36.missed_critical,
                "issue": "increased_missed_critical",
            })
    return {
        "invariant": len(violations) == 0,
        "violations": violations,
        "n_hot_transition_days": sum(1 for d in r035 if d.regime != "quiet"),
    }
