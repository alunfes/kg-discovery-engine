"""Run 014: Half-life calibration by decision tier and grammar family.

Analyzes watchlist_outcomes.csv from Run 013 to determine whether the
current one-dimensional HALF_LIFE_BY_TIER settings are appropriately
calibrated. Recommends 2D (tier × grammar_family) half-life values
based on p90 of observed time-to-outcome per group.

Why 2D calibration (tier × family, not just tier):
  Different grammar families produce events at different cadences.
  positioning_unwind (E2) events arrive in 7-25 min; using a 40-50 min
  window wastes monitoring capacity. beta_reversion events have similar
  timing. flow_continuation and baseline have no observed hits and must
  retain conservative windows until more data is available.

Design choice — p90 + 5 min buffer:
  p90 captures the 90th-percentile observed hit time. Adding a 5-min
  buffer guards against small-sample noise and unseen slightly-slower
  events. Using p99 would be over-conservative given sparse data;
  using p50 would cause excessive false-expiry.
"""
from __future__ import annotations

import csv
from statistics import mean, median
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENT_HALF_LIFE_BY_TIER: dict[str, int] = {
    "actionable_watch":   40,
    "research_priority":  50,
    "monitor_borderline": 60,
    "baseline_like":      90,
    "reject_conflicted":  20,
}

# Buffer added to p90(tte) for the recommended half-life.
# Provides a safety margin without over-extending the window.
P90_BUFFER_MIN: int = 5

# Minimum hit samples required for data-driven calibration.
# Below this threshold we fall back to the current half-life.
MIN_CALIBRATION_SAMPLES: int = 2

OUTCOME_HIT: str = "hit"
OUTCOME_EXPIRED: str = "expired"


# ---------------------------------------------------------------------------
# Grammar family inference
# ---------------------------------------------------------------------------

def infer_grammar_family(branch: str, title: str) -> str:
    """Infer grammar family from branch label and card title.

    Uses the CSV branch column as the primary signal. For branch="other"
    (Chain-D1 cards, correlation breaks, funding extremes), derives from
    the card title. Chain-D1 positioning_unwind cards are classified as
    "baseline" because they are control cards (no expected events).

    Args:
        branch: CSV branch column value.
        title: Card title string.

    Returns:
        One of: positioning_unwind, beta_reversion, flow_continuation, baseline.
    """
    if branch == "positioning_unwind":
        return "positioning_unwind"
    if branch == "beta_reversion":
        return "beta_reversion"
    if branch == "flow_continuation":
        return "flow_continuation"
    # branch="other" — derive from title keyword
    if "flow continuation" in title.lower():
        return "flow_continuation"
    return "baseline"


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def compute_percentile(values: list[float], p: float) -> float:
    """Compute p-th percentile with linear interpolation.

    Args:
        values: Numeric values (unsorted).
        p: Percentile in [0, 100].

    Returns:
        Interpolated percentile value. Returns 0.0 for empty lists.
    """
    if not values:
        return 0.0
    sv = sorted(values)
    n = len(sv)
    if n == 1:
        return float(sv[0])
    idx = (p / 100.0) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    return sv[lo] + (idx - lo) * (sv[hi] - sv[lo])


def _hit_ttimes(records: list[dict]) -> list[int]:
    """Extract time-to-outcome minutes from hit records only."""
    return [
        int(r["time_to_outcome_min"])
        for r in records
        if r["outcome_result"] == OUTCOME_HIT and r["time_to_outcome_min"]
    ]


def compute_group_stats(records: list[dict], current_hl: int) -> dict[str, Any]:
    """Compute hit statistics and half-life adequacy for one group.

    Args:
        records: CSV row dicts for one (tier, grammar_family) group.
        current_hl: Current half-life assigned to this tier (minutes).

    Returns:
        Dict with hit_rate, tte distribution, expiry metrics, recommended HL.
    """
    n = len(records)
    hits = [r for r in records if r["outcome_result"] == OUTCOME_HIT]
    expired = [r for r in records if r["outcome_result"] == OUTCOME_EXPIRED]
    ttimes = _hit_ttimes(records)
    # Cards where hit would be missed if HL were tighter than actual tte
    expiry_before_hit = sum(1 for t in ttimes if t > current_hl)
    # Hits that arrived after the current HL window (late hits)
    decayed_but_late_hit = expiry_before_hit  # same concept in this dataset
    return {
        "n_cards": n,
        "hit_count": len(hits),
        "expired_count": len(expired),
        "hit_rate": round(len(hits) / n, 3) if n else 0.0,
        "tte_mean": round(mean(ttimes), 1) if ttimes else None,
        "tte_median": float(median(ttimes)) if ttimes else None,
        "tte_p25": round(compute_percentile(ttimes, 25), 1) if ttimes else None,
        "tte_p75": round(compute_percentile(ttimes, 75), 1) if ttimes else None,
        "tte_p90": round(compute_percentile(ttimes, 90), 1) if ttimes else None,
        "expiry_before_hit": expiry_before_hit,
        "decayed_but_late_hit": decayed_but_late_hit,
        "current_hl_min": current_hl,
    }


# ---------------------------------------------------------------------------
# Half-life recommendation
# ---------------------------------------------------------------------------

def recommend_half_life(
    ttimes: list[int],
    current_hl: int,
    min_samples: int = MIN_CALIBRATION_SAMPLES,
) -> int:
    """Recommend half-life from p90(tte) + buffer, or fall back to current.

    Why fallback to current: groups with fewer than min_samples hit
    records lack statistical basis for calibration. Applying p90 to
    1-2 samples would produce noisy, unreliable recommendations.

    Args:
        ttimes: Time-to-outcome values (minutes) for hit records.
        current_hl: Current half-life for this tier.
        min_samples: Minimum hit count to apply data-driven calibration.

    Returns:
        Recommended half-life in minutes.
    """
    if len(ttimes) < min_samples:
        return current_hl
    return int(compute_percentile(ttimes, 90)) + P90_BUFFER_MIN


# ---------------------------------------------------------------------------
# Calibration aggregation
# ---------------------------------------------------------------------------

def calibrate_all_groups(records: list[dict]) -> dict[str, dict[str, Any]]:
    """Compute calibration recommendations for all (tier, family) groups.

    Args:
        records: All CSV row dicts from watchlist_outcomes.csv.

    Returns:
        Nested dict: {tier: {family: stats_with_recommended_hl}}.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        key = (r["decision_tier"], infer_grammar_family(r["branch"], r["title"]))
        groups.setdefault(key, []).append(r)
    result: dict[str, dict[str, Any]] = {}
    for (tier, family), recs in sorted(groups.items()):
        current_hl = CURRENT_HALF_LIFE_BY_TIER.get(tier, 45)
        stats = compute_group_stats(recs, current_hl)
        ttimes = _hit_ttimes(recs)
        stats["recommended_hl_min"] = recommend_half_life(ttimes, current_hl)
        result.setdefault(tier, {})[family] = stats
    return result


def build_hl_map(calibration: dict[str, dict[str, Any]]) -> dict[tuple[str, str], int]:
    """Build (tier, family) → recommended_hl lookup from calibration output.

    Args:
        calibration: Output of calibrate_all_groups.

    Returns:
        Dict mapping (tier, family) tuples to recommended half-life minutes.
    """
    hl_map: dict[tuple[str, str], int] = {}
    for tier, families in calibration.items():
        for family, stats in families.items():
            hl_map[(tier, family)] = stats["recommended_hl_min"]
    return hl_map


# ---------------------------------------------------------------------------
# Before/after simulation
# ---------------------------------------------------------------------------

def simulate_scenario(
    records: list[dict],
    hl_resolver: Callable[[str, str], int],
) -> dict[str, Any]:
    """Simulate outcome classification under a given half-life resolver.

    For each record, applies the resolver to determine effective HL, then
    checks whether a hit would be caught (tte <= hl) or falsely expired.
    Expired control cards are excluded from precision/recall denominators.

    Args:
        records: CSV row dicts from watchlist_outcomes.csv.
        hl_resolver: Callable(tier, family) returning half-life in minutes.

    Returns:
        Dict with precision, recall, false_expiry_rate, total_hl_min.
    """
    evaluable = [r for r in records if r["outcome_result"] != OUTCOME_EXPIRED]
    n_ev = len(evaluable)
    caught = false_expiry = total_hl = 0
    for r in records:
        tier = r["decision_tier"]
        family = infer_grammar_family(r["branch"], r["title"])
        hl = hl_resolver(tier, family)
        total_hl += hl
        if r["outcome_result"] == OUTCOME_HIT:
            tte = int(r["time_to_outcome_min"]) if r["time_to_outcome_min"] else 9999
            if tte <= hl:
                caught += 1
            else:
                false_expiry += 1
    n_hits = caught + false_expiry
    precision = round(caught / n_ev, 3) if n_ev else 0.0
    recall = round(caught / len(records), 3) if records else 0.0
    fe_rate = round(false_expiry / max(n_hits, 1), 3)
    return {
        "precision": precision,
        "recall": recall,
        "false_expiry_rate": fe_rate,
        "n_caught": caught,
        "n_false_expiry": false_expiry,
        "total_hl_min": total_hl,
    }


def compare_before_after(
    records: list[dict],
    calibration: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare current (1D tier) vs calibrated (2D tier×family) half-life regimes.

    Args:
        records: CSV rows from watchlist_outcomes.csv.
        calibration: Output of calibrate_all_groups.

    Returns:
        Dict with before/after scenario stats and delta metrics.
    """
    hl_map = build_hl_map(calibration)

    def current(tier: str, family: str) -> int:
        return CURRENT_HALF_LIFE_BY_TIER.get(tier, 45)

    def calibrated(tier: str, family: str) -> int:
        return hl_map.get((tier, family), CURRENT_HALF_LIFE_BY_TIER.get(tier, 45))

    before = simulate_scenario(records, current)
    after = simulate_scenario(records, calibrated)
    total_before = max(before["total_hl_min"], 1)
    hl_pct = round((after["total_hl_min"] - total_before) / total_before * 100, 1)
    return {
        "before": before,
        "after": after,
        "delta": {
            "precision_delta": round(after["precision"] - before["precision"], 3),
            "recall_delta": round(after["recall"] - before["recall"], 3),
            "false_expiry_delta": round(
                after["false_expiry_rate"] - before["false_expiry_rate"], 3
            ),
            "total_hl_min_delta": after["total_hl_min"] - before["total_hl_min"],
            "total_hl_pct_change": hl_pct,
        },
    }


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def load_outcomes_csv(path: str) -> list[dict]:
    """Load watchlist_outcomes.csv into a list of row dicts.

    Args:
        path: Absolute or relative path to watchlist_outcomes.csv.

    Returns:
        List of dicts, one per data row (header row excluded).
    """
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_stats_csv(flat_rows: list[dict], path: str) -> None:
    """Write flat calibration stats to half_life_stats.csv.

    Args:
        flat_rows: Flattened calibration rows from run_calibration.
        path: Output file path.
    """
    if not flat_rows:
        return
    fieldnames = list(flat_rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_calibration(outcomes_csv_path: str) -> dict[str, Any]:
    """Load CSV, calibrate half-lives, and return full analysis results.

    Args:
        outcomes_csv_path: Path to watchlist_outcomes.csv (from run_013).

    Returns:
        Dict with n_records, calibration, flat_stats, before_after.
    """
    records = load_outcomes_csv(outcomes_csv_path)
    calibration = calibrate_all_groups(records)
    before_after = compare_before_after(records, calibration)
    flat_rows: list[dict] = []
    for tier, families in calibration.items():
        for family, stats in families.items():
            flat_rows.append({"tier": tier, "grammar_family": family, **stats})
    return {
        "n_records": len(records),
        "calibration": calibration,
        "flat_stats": flat_rows,
        "before_after": before_after,
    }
