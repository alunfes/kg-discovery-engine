"""Run 015: Monitoring budget allocation by value density.

Computes monitoring efficiency (hit_rate / monitoring_cost) per
(tier, grammar_family) group and assigns each group to one of four
allocation categories. Simulates three monitoring strategies and
compares their budget/precision trade-offs.

Why value_density = hit_rate / monitoring_cost:
  Monitoring cost (calibrated half-life window) is the resource we spend
  per card. hit_rate is the expected return. Dividing gives hits-per-minute
  — a comparable efficiency metric across groups with different window sizes.

Design choice — MIN_ALLOCATION_SAMPLES = 3:
  Groups with fewer than 3 observed cards lack enough data to distinguish
  signal from noise. These get 'insufficient_evidence' rather than a
  data-driven category. Run 014 groups with n<3 also failed p90 calibration
  for the same reason — the thresholds are consistent.

Three strategies:
  uniform:          all cards monitored with UNIFORM_HL_MIN (50 min)
  calibrated_only:  apply Run 014 calibrated HL per group (1D->2D tightening)
  budget_aware:     further reduce windows for zero-hit groups by 50%;
                    sparse groups (insufficient_evidence) to 40%
"""
from __future__ import annotations

from typing import Any

from .half_life_calibrator import (
    CURRENT_HALF_LIFE_BY_TIER,
    OUTCOME_HIT,
    OUTCOME_EXPIRED,
    calibrate_all_groups,
    infer_grammar_family,
    load_outcomes_csv,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Single HL value used for the uniform strategy baseline.
UNIFORM_HL_MIN: int = 50

# Minimum cards in a group to support data-driven allocation.
MIN_ALLOCATION_SAMPLES: int = 3

# Calibrated HL at or below this threshold → short_high_priority.
SHORT_PRIORITY_HL_MAX: int = 35

# Floor for any budget-aware HL (never reduce below 15 min).
BUDGET_AWARE_HL_FLOOR: int = 15

# Scaling factors applied to calibrated HL per allocation category
# in the budget_aware strategy.
# Why 0.5 for low_background: no observed hits → halve the window to
# free budget while retaining minimal coverage for unexpected events.
# Why 0.4 for insufficient_evidence: sparse data → conservative short
# window until more samples accumulate.
_BUDGET_FACTOR: dict[str, float] = {
    "short_high_priority":  1.0,
    "medium_default":       1.0,
    "low_background":       0.5,
    "insufficient_evidence": 0.4,
}

ALLOCATION_STRATEGIES = ("uniform", "calibrated_only", "budget_aware")


# ---------------------------------------------------------------------------
# Value density
# ---------------------------------------------------------------------------

def compute_value_density(hit_rate: float, monitoring_cost_min: int) -> float:
    """Compute value density as hit_rate / monitoring_cost (hits per minute).

    Why divide by monitoring cost and not hits directly: a group with
    hit_rate=1.0 and cost=50 min is less efficient than one with cost=30 min.
    The ratio makes efficiency comparable across groups.

    Args:
        hit_rate: Fraction of cards with a hit outcome [0, 1].
        monitoring_cost_min: Calibrated half-life window in minutes.

    Returns:
        Value density in hits-per-minute; 0.0 if monitoring_cost_min == 0.
    """
    if monitoring_cost_min <= 0:
        return 0.0
    return round(hit_rate / monitoring_cost_min, 6)


# ---------------------------------------------------------------------------
# Allocation categories
# ---------------------------------------------------------------------------

def assign_allocation_category(
    hit_rate: float,
    n_cards: int,
    monitoring_cost_min: int,
    min_samples: int = MIN_ALLOCATION_SAMPLES,
) -> str:
    """Assign one of four monitoring allocation categories to a group.

    Priority order (checked top-down):
      1. insufficient_evidence: n_cards < min_samples (no reliable data)
      2. low_background:        hit_rate == 0 (enough data, no signal)
      3. short_high_priority:   hit_rate > 0 and cost <= SHORT_PRIORITY_HL_MAX
      4. medium_default:        hit_rate > 0 and cost > SHORT_PRIORITY_HL_MAX

    Args:
        hit_rate: Observed group hit rate [0, 1].
        n_cards: Number of cards observed in this group.
        monitoring_cost_min: Calibrated half-life in minutes.
        min_samples: Minimum sample count for data-driven classification.

    Returns:
        One of: short_high_priority, medium_default, low_background,
        insufficient_evidence.
    """
    if n_cards < min_samples:
        return "insufficient_evidence"
    if hit_rate == 0.0:
        return "low_background"
    if monitoring_cost_min <= SHORT_PRIORITY_HL_MAX:
        return "short_high_priority"
    return "medium_default"


# ---------------------------------------------------------------------------
# Budget-aware HL
# ---------------------------------------------------------------------------

def compute_budget_aware_hl(
    calibrated_hl: int,
    allocation_category: str,
) -> int:
    """Scale calibrated HL by allocation category factor.

    Why separate function (not inline in simulation): makes the adjustment
    transparent and independently testable.

    Args:
        calibrated_hl: Recommended HL from run_014 (minutes).
        allocation_category: One of the four allocation category strings.

    Returns:
        Budget-aware HL in minutes, floored at BUDGET_AWARE_HL_FLOOR.
    """
    factor = _BUDGET_FACTOR.get(allocation_category, 1.0)
    return max(BUDGET_AWARE_HL_FLOOR, int(calibrated_hl * factor))


# ---------------------------------------------------------------------------
# Allocation table row builder
# ---------------------------------------------------------------------------

def build_allocation_row(
    tier: str,
    family: str,
    n_cards: int,
    hit_rate: float,
    mean_tte: Any,
    calibrated_hl: int,
) -> dict[str, Any]:
    """Build one allocation table row for a (tier, grammar_family) group.

    Args:
        tier: Decision tier string.
        family: Grammar family string.
        n_cards: Observed card count for this group.
        hit_rate: Observed hit rate [0, 1].
        mean_tte: Mean time-to-outcome (minutes) or None if no hits.
        calibrated_hl: Recommended HL from run_014 (minutes).

    Returns:
        Dict with tier, grammar_family, n_cards, hit_rate,
        mean_time_to_outcome_min, monitoring_cost_min, value_density,
        allocation_category, budget_aware_hl_min.
    """
    vd = compute_value_density(hit_rate, calibrated_hl)
    cat = assign_allocation_category(hit_rate, n_cards, calibrated_hl)
    budget_hl = compute_budget_aware_hl(calibrated_hl, cat)
    return {
        "tier": tier,
        "grammar_family": family,
        "n_cards": n_cards,
        "hit_rate": hit_rate,
        "mean_time_to_outcome_min": mean_tte,
        "monitoring_cost_min": calibrated_hl,
        "value_density": vd,
        "allocation_category": cat,
        "budget_aware_hl_min": budget_hl,
    }


# ---------------------------------------------------------------------------
# Allocation table
# ---------------------------------------------------------------------------

def build_allocation_table(
    calibration: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the full allocation table from calibrate_all_groups output.

    Args:
        calibration: Output of calibrate_all_groups
                     {tier: {family: stats_dict}}.

    Returns:
        List of allocation row dicts, sorted by value_density descending.
    """
    rows: list[dict[str, Any]] = []
    for tier, families in sorted(calibration.items()):
        for family, stats in sorted(families.items()):
            row = build_allocation_row(
                tier=tier,
                family=family,
                n_cards=stats["n_cards"],
                hit_rate=stats["hit_rate"],
                mean_tte=stats.get("tte_mean"),
                calibrated_hl=stats["recommended_hl_min"],
            )
            rows.append(row)
    rows.sort(key=lambda r: r["value_density"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Strategy HL resolver
# ---------------------------------------------------------------------------

def resolve_strategy_hl(
    strategy: str,
    calibrated_hl: int,
    allocation_category: str,
) -> int:
    """Return the monitoring HL for a given strategy.

    Why isolate: keeps strategy switching out of the simulation loop,
    making each strategy's policy easy to audit.

    Args:
        strategy: One of ALLOCATION_STRATEGIES.
        calibrated_hl: Calibrated HL from run_014 (minutes).
        allocation_category: Pre-computed allocation category for the group.

    Returns:
        Half-life in minutes for this card under the given strategy.
    """
    if strategy == "uniform":
        return UNIFORM_HL_MIN
    if strategy == "calibrated_only":
        return calibrated_hl
    # budget_aware
    return compute_budget_aware_hl(calibrated_hl, allocation_category)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_one_strategy(
    records: list[dict],
    strategy: str,
    allocation_lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Simulate outcome metrics under one monitoring strategy.

    Evaluates each record under the strategy's HL policy. Expired cards
    (control cards with no expected events) are excluded from
    precision/recall denominators but included in total_monitoring_minutes.

    Args:
        records: Row dicts from watchlist_outcomes.csv (or i5 outcome_records).
        strategy: One of ALLOCATION_STRATEGIES.
        allocation_lookup: (tier, family) -> allocation row dict.

    Returns:
        Dict with strategy, total_monitoring_minutes, precision, recall,
        cost_per_hit, monitoring_efficiency.
    """
    n_caught = n_false_expiry = total_hl = 0
    n_evaluable = sum(1 for r in records if r["outcome_result"] != OUTCOME_EXPIRED)
    for r in records:
        tier = r["decision_tier"]
        family = infer_grammar_family(r.get("branch", "other"), r.get("title", ""))
        alloc = allocation_lookup.get((tier, family), {})
        cat = alloc.get("allocation_category", "insufficient_evidence")
        cal_hl = alloc.get("monitoring_cost_min", CURRENT_HALF_LIFE_BY_TIER.get(tier, 50))
        hl = resolve_strategy_hl(strategy, cal_hl, cat)
        total_hl += hl
        if r["outcome_result"] == OUTCOME_HIT:
            raw_tte = r.get("time_to_outcome_min")
            tte = int(raw_tte) if raw_tte else 9999
            if tte <= hl:
                n_caught += 1
            else:
                n_false_expiry += 1
    n_hits = n_caught + n_false_expiry
    precision = round(n_caught / n_evaluable, 3) if n_evaluable else 0.0
    recall = round(n_caught / max(n_hits, 1), 3)
    cost_per_hit = round(total_hl / max(n_caught, 1), 1)
    efficiency = round(n_caught / max(total_hl, 1), 6)
    return {
        "strategy": strategy,
        "total_monitoring_minutes": total_hl,
        "n_caught": n_caught,
        "n_false_expiry": n_false_expiry,
        "precision": precision,
        "recall": recall,
        "cost_per_hit": cost_per_hit,
        "monitoring_efficiency": efficiency,
    }


# ---------------------------------------------------------------------------
# Three-strategy comparison
# ---------------------------------------------------------------------------

def compare_three_strategies(
    records: list[dict],
    allocation_table: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare all three monitoring strategies on a set of outcome records.

    Args:
        records: Row dicts from watchlist_outcomes.csv.
        allocation_table: Output of build_allocation_table.

    Returns:
        Dict with per-strategy results, summary with best strategy names,
        and budget_aware_vs_uniform reduction percentage.
    """
    lookup: dict[tuple[str, str], dict[str, Any]] = {
        (r["tier"], r["grammar_family"]): r for r in allocation_table
    }
    results = {
        s: simulate_one_strategy(records, s, lookup)
        for s in ALLOCATION_STRATEGIES
    }
    base_hl = results["uniform"]["total_monitoring_minutes"]
    ba_hl = results["budget_aware"]["total_monitoring_minutes"]
    pct_vs_uniform = round((ba_hl - base_hl) / max(base_hl, 1) * 100, 1)
    cal_hl = results["calibrated_only"]["total_monitoring_minutes"]
    pct_vs_calibrated = round((ba_hl - cal_hl) / max(cal_hl, 1) * 100, 1)
    return {
        "strategies": results,
        "summary": {
            "best_efficiency": max(
                ALLOCATION_STRATEGIES,
                key=lambda s: results[s]["monitoring_efficiency"],
            ),
            "best_recall": max(
                ALLOCATION_STRATEGIES,
                key=lambda s: results[s]["recall"],
            ),
            "budget_aware_vs_uniform_pct": pct_vs_uniform,
            "budget_aware_vs_calibrated_pct": pct_vs_calibrated,
        },
    }


# ---------------------------------------------------------------------------
# Pipeline integration helper
# ---------------------------------------------------------------------------

def build_allocation_table_from_outcomes(
    outcome_records: list[dict],
) -> dict[str, Any]:
    """Build allocation table and run budget analysis from i5 outcome records.

    Intended for pipeline integration: accepts in-memory outcome_records
    directly rather than loading a CSV file.

    Why separate from run_budget_analysis: pipeline produces outcome records
    in-memory. Writing + re-reading a CSV mid-run would break the single-pass
    design and add I/O latency.

    Args:
        outcome_records: List of dicts from i5_outcome_tracking.outcome_records.

    Returns:
        Dict with allocation_table (list of rows) and strategy_comparison.
    """
    calibration = calibrate_all_groups(outcome_records)
    allocation_table = build_allocation_table(calibration)
    strategy_comparison = compare_three_strategies(outcome_records, allocation_table)
    return {
        "allocation_table": allocation_table,
        "strategy_comparison": strategy_comparison,
    }


# ---------------------------------------------------------------------------
# Offline analysis entry point
# ---------------------------------------------------------------------------

def run_budget_analysis(outcomes_csv_path: str) -> dict[str, Any]:
    """Load CSV, calibrate, build allocation table, compare strategies.

    Args:
        outcomes_csv_path: Path to watchlist_outcomes.csv from run_013.

    Returns:
        Dict with n_records, calibration, allocation_table,
        strategy_comparison.
    """
    records = load_outcomes_csv(outcomes_csv_path)
    calibration = calibrate_all_groups(records)
    allocation_table = build_allocation_table(calibration)
    strategy_comparison = compare_three_strategies(records, allocation_table)
    return {
        "n_records": len(records),
        "calibration": calibration,
        "allocation_table": allocation_table,
        "strategy_comparison": strategy_comparison,
    }
