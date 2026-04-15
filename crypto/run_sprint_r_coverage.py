"""Sprint R: Multi-window real-data coverage expansion runner.

Extends Run 017's single-snapshot approach to a multi-window pipeline that
exposes the engine to different market regimes and grammar families.

What this script does:
  1. Fetches real Hyperliquid data for 4 time windows (1h, 4h, 8h, 7d).
  2. Runs the KG discovery pipeline on each window with real_data_mode=True.
  3. Tracks grammar family and regime coverage across all windows.
  4. Writes four coverage reports to the output directory.
  5. Produces run_config.json and shadow_summary.json for reproducibility.

Usage:
  # Live fetch from Hyperliquid API:
  python -m crypto.run_sprint_r_coverage

  # Offline replay from cached data:
  python -m crypto.run_sprint_r_coverage --offline

  # Custom output directory:
  python -m crypto.run_sprint_r_coverage --output-dir /tmp/sprint_r

Why multi-window:
  A single 120-min snapshot sees only one micro-regime. Longer windows
  allow funding extremes, OI accumulation, and correlation breaks to
  develop and be captured by the engine.

Why real_data_mode=True:
  Synthetic-data threshold presets (OI_BUILD_RATE=0.05, BUY_STRONG=0.70,
  FUNDING_Z_WINDOW=10) were calibrated on artificial data. Real data has
  smaller OI moves, and candle-derived trade ticks have fixed buy_ratio
  that previously never exceeded 0.70. Sprint R adjusts these thresholds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.ingestion.multi_window_fetcher import (
    MultiWindowFetcher,
    DEFAULT_WINDOWS,
    DEFAULT_ASSETS,
)
from crypto.src.pipeline import PipelineConfig, run_pipeline
from crypto.src.states.extractor import extract_states
from crypto.src.coverage_tracker import (
    CoverageReport,
    WindowCoverage,
    extract_coverage_from_cards,
    write_family_coverage_csv,
    write_regime_coverage_csv,
    write_missing_condition_map,
    write_recommended_state_expansions,
)

RUN_ID = "sprint_r_coverage"
DEFAULT_OUT = "crypto/artifacts/runs/sprint_r_coverage"
TOP_K = 20
SEED = 42


def _extract_regime_counts(
    dataset,
    assets: list[str],
    run_id: str,
    n_minutes: int,
) -> dict[str, int]:
    """Count regime labels across all assets in the dataset.

    Extracts state collections directly from the dataset rather than relying
    on HypothesisCard attributes (which don't carry regime labels).

    Returns dict mapping regime value string → observation count.
    """
    from collections import defaultdict
    counts: dict[str, int] = defaultdict(int)
    for asset in assets:
        try:
            coll = extract_states(
                dataset, asset, run_id,
                real_data_mode=True,
            )
            for _, regime in coll.regime_labels:
                counts[regime.value] += 1
        except Exception:
            pass
    return dict(counts)


def _load_tier_counts(window_output_dir: str) -> dict[str, int]:
    """Load tier counts from decision_tiers.json written by the pipeline.

    Returns {} if the file doesn't exist or parse fails.
    """
    from collections import defaultdict
    path = os.path.join(window_output_dir, "decision_tiers.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        counts: dict[str, int] = defaultdict(int)
        for item in data.get("tier_assignments", []):
            if isinstance(item, dict):
                tier = item.get("decision_tier", "unknown")
                counts[str(tier)] += 1
        return dict(counts)
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def run_coverage_expansion(output_dir: str, live: bool = True) -> dict:
    """Execute the multi-window coverage expansion pipeline.

    Args:
        output_dir: Directory to write all output artifacts.
        live:       True = live API fetch; False = offline cache replay.

    Returns:
        Summary dict with coverage metrics.
    """
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    fetcher = MultiWindowFetcher(
        assets=DEFAULT_ASSETS,
        windows=DEFAULT_WINDOWS,
        cache_dir="crypto/artifacts/cache/hl_api",
        live=live,
        seed=SEED,
    )

    print(f"[sprint_r] Fetching {len(DEFAULT_WINDOWS)} windows "
          f"({'live' if live else 'offline'})...")
    window_results = fetcher.fetch_all_windows()

    report = CoverageReport()
    all_summaries = []

    for wr in window_results:
        label = wr.spec.label
        print(f"[sprint_r] Running pipeline on window={label} "
              f"(n_minutes={wr.spec.n_minutes})...")

        cfg = PipelineConfig(
            run_id=f"{RUN_ID}_{label}",
            seed=SEED,
            n_minutes=wr.spec.n_minutes,
            assets=DEFAULT_ASSETS,
            top_k=TOP_K,
            output_dir=os.path.join(output_dir, f"window_{label}"),
            dataset=wr.dataset,
            real_data_mode=True,
        )
        cards = run_pipeline(cfg)

        # Extract regime counts from state collections (not on HypothesisCard).
        regime_counts = _extract_regime_counts(
            wr.dataset, DEFAULT_ASSETS, cfg.run_id, wr.spec.n_minutes
        )

        # Load tier data from decision_tiers.json written by pipeline.
        tier_counts = _load_tier_counts(
            os.path.join(output_dir, f"window_{label}")
        )

        cov = extract_coverage_from_cards(
            cards=cards,
            window_label=label,
            fetch_meta=wr.fetch_meta,
        )
        # Enrich with regime and tier data from supplemental sources.
        cov.regime_counts.update(regime_counts)
        cov.tier_counts = tier_counts if tier_counts else cov.tier_counts
        report.windows.append(cov)

        all_summaries.append({
            "window": label,
            "n_minutes": wr.spec.n_minutes,
            "n_cards": len(cards),
            "families_fired": sorted(cov.family_counts.keys()),
            "regimes_observed": sorted(cov.regime_counts.keys()),
            "tier_distribution": cov.tier_counts,
            "fetch_meta": wr.fetch_meta,
        })
        print(f"  → {len(cards)} cards | "
              f"families: {sorted(cov.family_counts.keys())} | "
              f"regimes: {sorted(cov.regime_counts.keys())}")

    # Write coverage reports
    fam_csv = write_family_coverage_csv(report, output_dir)
    reg_csv = write_regime_coverage_csv(report, output_dir)
    missing_md = write_missing_condition_map(report, output_dir)
    expansions_md = write_recommended_state_expansions(report, output_dir)

    elapsed = round(time.time() - t0, 2)
    absent_fam = report.absent_families()
    absent_reg = report.absent_regimes()
    total_cards = sum(w.n_cards for w in report.windows)
    all_families = sorted(report.total_family_counts().keys())
    all_regimes = sorted(report.total_regime_counts().keys())

    summary = {
        "run_id": RUN_ID,
        "timestamp": timestamp,
        "mode": "live" if live else "offline_cache",
        "n_windows": len(window_results),
        "n_assets": len(DEFAULT_ASSETS),
        "total_cards": total_cards,
        "families_covered": all_families,
        "families_absent": absent_fam,
        "regimes_covered": all_regimes,
        "regimes_absent": absent_reg,
        "elapsed_s": elapsed,
        "windows": all_summaries,
        "artifacts": {
            "family_coverage_csv": fam_csv,
            "regime_coverage_csv": reg_csv,
            "missing_condition_map": missing_md,
            "recommended_state_expansions": expansions_md,
        },
    }

    # Write run_config.json
    run_config = {
        "run_id": RUN_ID,
        "timestamp": timestamp,
        "windows": [
            {"label": w.label, "n_minutes": w.n_minutes,
             "funding_epochs": w.funding_epochs}
            for w in DEFAULT_WINDOWS
        ],
        "assets": DEFAULT_ASSETS,
        "top_k": TOP_K,
        "seed": SEED,
        "mode": "live" if live else "offline_cache",
        "real_data_mode": True,
        "threshold_overrides": {
            "FUNDING_Z_WINDOW_REAL": 5,
            "FUNDING_ABS_EXTREME": 0.0003,
            "OI_BUILD_RATE_REAL": 0.005,
            "buy_ratio_0.5pct_candle": 0.80,
        },
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(run_config, f, indent=2)

    with open(os.path.join(output_dir, "shadow_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sprint R: multi-window real-data coverage expansion"
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Use cached data only (no live API calls)"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})"
    )
    args = parser.parse_args()

    summary = run_coverage_expansion(
        output_dir=args.output_dir,
        live=not args.offline,
    )
    print("\n=== Sprint R Coverage Summary ===")
    print(f"Total cards: {summary['total_cards']}")
    print(f"Families covered: {summary['families_covered']}")
    print(f"Families absent:  {summary['families_absent']}")
    print(f"Regimes covered:  {summary['regimes_covered']}")
    print(f"Regimes absent:   {summary['regimes_absent']}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
