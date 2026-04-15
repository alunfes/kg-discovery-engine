"""Coverage tracker for Sprint R multi-window pipeline runs.

Aggregates grammar family and regime coverage across multiple time windows
and generates CSV / Markdown reports for the Sprint R coverage expansion.

Key outputs:
  family_coverage.csv          — per-family fire counts and conditions
  regime_coverage.csv          — per-regime observation counts
  missing_condition_map.md     — absent families/regimes and likely root causes
  recommended_state_expansions.md — next state/detector additions

Design decisions:
  - Coverage is tracked at two levels: card-level (what families fired)
    and regime-level (what regimes were observed in each window).
  - "Absent" means a family/regime was expected but never produced a card /
    observed in any window. Expected set is the full grammar family inventory.
  - Reports are intentionally write-only (no caching) — they are regenerated
    from scratch on each run to avoid stale state.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Known grammar families and regimes (full expected set)
# ---------------------------------------------------------------------------

ALL_FAMILIES = [
    "beta_reversion",
    "positioning_unwind",
    "flow_continuation",
    "cross_asset",
    "baseline",
]

ALL_REGIMES = [
    "resting_liquidity",
    "aggressive_buying",
    "aggressive_selling",
    "spread_widening",
    "funding_extreme_long",
    "funding_extreme_short",
    "correlation_break",
    "undefined",
]

# Explanations for why each family might be absent (used in missing_condition_map).
_FAMILY_ABSENT_REASONS: dict[str, str] = {
    "beta_reversion": (
        "Requires corr_break (rho < threshold). "
        "Usually present; check CORR_BREAK_THRESHOLD vs real rho values."
    ),
    "positioning_unwind": (
        "Requires FundingNode(is_extreme=True) OR OIState(is_accumulation=True). "
        "Root causes: (a) funding lookback too short → z-scores near 0; "
        "(b) OI flat series → no build_streak; (c) real funding < FUNDING_ABS_EXTREME."
    ),
    "flow_continuation": (
        "Requires AggressionNode(is_burst=True) on multiple consecutive windows. "
        "Root cause: candle-derived buy_ratio capped below BUY_STRONG=0.70 — "
        "check _infer_buy_ratio magnitude buckets and 0.5% threshold."
    ),
    "cross_asset": (
        "Requires rho < CORR_BREAK_THRESHOLD=0.3 between at least one asset pair. "
        "Root cause: 1h window too short for correlation divergence; "
        "use 4h+ window."
    ),
    "baseline": (
        "Should always fire as a fallback when other families suppress. "
        "Absent baseline usually means reject_conflicted is blocking all cards."
    ),
}

_REGIME_ABSENT_REASONS: dict[str, str] = {
    "funding_extreme_long": (
        "Requires funding z_score > 2.0 or rate > FUNDING_ABS_EXTREME. "
        "Increase funding lookback or check real rate magnitude."
    ),
    "funding_extreme_short": (
        "Requires funding z_score < -2.0 or rate < -FUNDING_ABS_EXTREME. "
        "Negative funding is rare on Hyperliquid; may be genuinely absent."
    ),
    "correlation_break": (
        "Labelled by cross_asset KG only. Requires corr_break_score node. "
        "Use 4h+ windows for reliable cross-asset correlation."
    ),
    "aggressive_buying": (
        "Requires AggressionBias.STRONG_BUY (buy_ratio > 0.70). "
        "With Sprint R buy_ratio fix, should appear on 0.5%+ up candles."
    ),
    "aggressive_selling": (
        "Requires AggressionBias.STRONG_SELL (buy_ratio < 0.30). "
        "Should appear on 0.5%+ down candles."
    ),
    "spread_widening": (
        "Requires spread z_score > 2.0. Spreads are flat (asset default). "
        "Cannot fire until real book data is available."
    ),
    "resting_liquidity": (
        "Requires spread z_score < 0.5 AND neutral aggression. "
        "Should appear in low-volatility windows."
    ),
    "undefined": (
        "Default regime when no condition is met. "
        "High undefined ratio indicates missing signal coverage."
    ),
}


@dataclass
class WindowCoverage:
    """Coverage data collected from one pipeline window run."""

    window_label: str
    n_cards: int
    family_counts: dict[str, int] = field(default_factory=dict)
    regime_counts: dict[str, int] = field(default_factory=dict)
    tier_counts: dict[str, int] = field(default_factory=dict)
    fetch_meta: dict = field(default_factory=dict)


@dataclass
class CoverageReport:
    """Aggregated coverage across all windows."""

    windows: list[WindowCoverage] = field(default_factory=list)

    def total_family_counts(self) -> dict[str, int]:
        """Sum family fire counts across all windows."""
        total: dict[str, int] = defaultdict(int)
        for w in self.windows:
            for fam, cnt in w.family_counts.items():
                total[fam] += cnt
        return dict(total)

    def total_regime_counts(self) -> dict[str, int]:
        """Sum regime observation counts across all windows."""
        total: dict[str, int] = defaultdict(int)
        for w in self.windows:
            for reg, cnt in w.regime_counts.items():
                total[reg] += cnt
        return dict(total)

    def absent_families(self) -> list[str]:
        """Return families in ALL_FAMILIES that never fired in any window."""
        fired = set(self.total_family_counts().keys())
        return [f for f in ALL_FAMILIES if f not in fired]

    def absent_regimes(self) -> list[str]:
        """Return regimes in ALL_REGIMES that were never observed."""
        observed = set(self.total_regime_counts().keys())
        return [r for r in ALL_REGIMES if r not in observed]


def extract_coverage_from_cards(
    cards: list,
    window_label: str,
    fetch_meta: Optional[dict] = None,
) -> WindowCoverage:
    """Extract coverage metrics from a list of HypothesisCard objects.

    Args:
        cards:        Output from run_pipeline (list of HypothesisCard).
        window_label: Label for this window (e.g. "1h", "4h").
        fetch_meta:   Optional fetch metadata from MultiWindowFetcher.

    Returns:
        WindowCoverage with family, regime, and tier counts.
    """
    family_counts: dict[str, int] = defaultdict(int)
    tier_counts: dict[str, int] = defaultdict(int)
    regime_counts: dict[str, int] = defaultdict(int)

    for card in cards:
        families = getattr(card, "kg_families", None) or []
        tier = getattr(card, "decision_tier", "unknown")
        regimes = getattr(card, "regime_labels", None) or []

        for fam in families:
            family_counts[str(fam)] += 1
        tier_counts[str(tier)] += 1
        for reg in regimes:
            regime_counts[str(reg)] += 1

    return WindowCoverage(
        window_label=window_label,
        n_cards=len(cards),
        family_counts=dict(family_counts),
        regime_counts=dict(regime_counts),
        tier_counts=dict(tier_counts),
        fetch_meta=fetch_meta or {},
    )


def write_family_coverage_csv(report: CoverageReport, output_dir: str) -> str:
    """Write family_coverage.csv — one row per (window, family).

    Columns: window, family, fire_count, tier_actionable, tier_research,
    tier_borderline, tier_baseline, tier_rejected.

    Returns path to the written file.
    """
    path = os.path.join(output_dir, "family_coverage.csv")
    tier_cols = [
        "actionable_watch", "research_priority", "monitor_borderline",
        "baseline_like", "reject_conflicted",
    ]
    rows = []
    for w in report.windows:
        for fam in ALL_FAMILIES:
            fire_count = w.family_counts.get(fam, 0)
            row = {
                "window": w.window_label,
                "family": fam,
                "fire_count": fire_count,
                "n_cards_total": w.n_cards,
            }
            for t in tier_cols:
                row[f"tier_{t}"] = w.tier_counts.get(t, 0) if fire_count > 0 else 0
            rows.append(row)
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", newline="") as f:
        fieldnames = ["window", "family", "fire_count", "n_cards_total"] + [
            f"tier_{t}" for t in tier_cols
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_regime_coverage_csv(report: CoverageReport, output_dir: str) -> str:
    """Write regime_coverage.csv — one row per (window, regime).

    Returns path to the written file.
    """
    path = os.path.join(output_dir, "regime_coverage.csv")
    rows = []
    for w in report.windows:
        for reg in ALL_REGIMES:
            rows.append({
                "window": w.window_label,
                "regime": reg,
                "observation_count": w.regime_counts.get(reg, 0),
                "n_cards_total": w.n_cards,
            })
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["window", "regime", "observation_count", "n_cards_total"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_missing_condition_map(report: CoverageReport, output_dir: str) -> str:
    """Write missing_condition_map.md — absent families/regimes with root causes.

    Returns path to the written file.
    """
    path = os.path.join(output_dir, "missing_condition_map.md")
    absent_fam = report.absent_families()
    absent_reg = report.absent_regimes()
    lines = [
        "# Missing Condition Map — Sprint R Coverage Expansion",
        "",
        "Families and regimes not observed in any window, with root-cause analysis.",
        "",
        f"**Windows run:** {', '.join(w.window_label for w in report.windows)}",
        f"**Total cards across all windows:** {sum(w.n_cards for w in report.windows)}",
        "",
    ]
    lines += ["## Absent Grammar Families", ""]
    if absent_fam:
        for fam in absent_fam:
            reason = _FAMILY_ABSENT_REASONS.get(fam, "Unknown root cause.")
            lines += [f"### {fam}", "", f"{reason}", ""]
    else:
        lines += ["*All expected grammar families observed.*", ""]
    lines += ["## Absent Regimes", ""]
    if absent_reg:
        for reg in absent_reg:
            reason = _REGIME_ABSENT_REASONS.get(reg, "Unknown root cause.")
            lines += [f"### {reg}", "", f"{reason}", ""]
    else:
        lines += ["*All expected regimes observed.*", ""]
    lines += ["## Per-Window Summary", ""]
    for w in report.windows:
        fired = sorted(w.family_counts.keys())
        observed = sorted(w.regime_counts.keys())
        lines += [
            f"### Window: {w.window_label}",
            f"- Cards: {w.n_cards}",
            f"- Families fired: {', '.join(fired) if fired else 'none'}",
            f"- Regimes observed: {', '.join(observed) if observed else 'none'}",
            "",
        ]
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def write_recommended_state_expansions(
    report: CoverageReport, output_dir: str
) -> str:
    """Write recommended_state_expansions.md.

    Returns path to the written file.
    """
    path = os.path.join(output_dir, "recommended_state_expansions.md")
    absent_fam = report.absent_families()
    lines = [
        "# Recommended State / Detector Expansions — Sprint R",
        "",
        "Based on coverage gaps, the following additions are recommended for Sprint S.",
        "",
    ]

    recs: list[tuple[str, str, str]] = [
        # (priority, title, description)
        (
            "HIGH",
            "WebSocket trade feed for real aggression states",
            "Subscribe to Hyperliquid WS trades endpoint to get real fill-level "
            "trade ticks. This eliminates the candle-derived buy_ratio approximation "
            "and enables genuine STRONG_BUY/STRONG_SELL detection for flow_continuation.",
        ),
        (
            "HIGH",
            "OI WebSocket subscription for continuous OI time-series",
            "Subscribe to Hyperliquid WS openInterest feed to build a real-time OI "
            "series. Replaces the volume-proxy approach in data_adapter.py with "
            "ground-truth OI for accurate is_accumulation detection.",
        ),
        (
            "MEDIUM",
            "L2 book WebSocket for rolling spread z-score",
            "Subscribe to Hyperliquid WS l2Book to capture spread changes over time. "
            "Current single-snapshot approach yields constant spread z_score=0, "
            "preventing SPREAD_WIDENING regime from ever firing.",
        ),
        (
            "MEDIUM",
            "Candle-interval detector for aggression persistence",
            "Add a per-candle aggression_persistence_score: fraction of candles in "
            "the last N with |delta_pct| > 0.5%. This feeds flow_continuation "
            "directly without requiring real trade ticks.",
        ),
        (
            "LOW",
            "Cross-asset correlation break detector at 4h+ resolution",
            "Log corr_break_score per asset pair per window. Plot rho distribution "
            "in real data to calibrate CORR_BREAK_THRESHOLD (currently 0.3). "
            "Real crypto pairs in trending markets may need threshold 0.5+.",
        ),
    ]
    if "funding_extreme_long" in report.absent_regimes():
        recs.insert(0, (
            "HIGH",
            "Verify funding data availability for target assets",
            "fundingHistory returned 0 records in Run 017. Check if Hyperliquid "
            "API requires different startTime or if these perps have sparse funding. "
            "Consider fetching 30+ days of history on first run to seed the cache.",
        ))

    for priority, title, desc in recs:
        lines += [f"## [{priority}] {title}", "", desc, ""]

    lines += [
        "## Summary Table",
        "",
        "| Priority | Expansion | Families Unblocked |",
        "|----------|-----------|-------------------|",
        "| HIGH | Real trade tick feed | flow_continuation, transient_aggression |",
        "| HIGH | OI WebSocket | positioning_unwind |",
        "| MEDIUM | Book WebSocket | spread_widening regime |",
        "| MEDIUM | Candle aggression persistence | flow_continuation (proxy) |",
        "| LOW | Corr break threshold calibration | cross_asset |",
    ]
    if absent_fam:
        lines += [
            "",
            f"**Families still absent after Sprint R:** {', '.join(absent_fam)}",
        ]
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path
