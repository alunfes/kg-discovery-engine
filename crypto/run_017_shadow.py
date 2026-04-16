"""Run 017: Real-data shadow deployment.

End-to-end test of the calibrated monitoring engine using live Hyperliquid
market data. Shadow mode: pipeline runs but no trades are placed.

Usage:
  # Live fetch from Hyperliquid API:
  python -m crypto.run_017_shadow

  # Replay from cache (offline/deterministic):
  python -m crypto.run_017_shadow --offline

  # Custom output dir:
  python -m crypto.run_017_shadow --output-dir /tmp/run_017

Why shadow mode (no trades):
  Run 017 is a diagnostic run to verify the calibrated pipeline behaves
  correctly on real data. Trading decisions require additional validation
  of the pipeline's signal quality on live data before enabling execution.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

# Add project root to path when run directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.ingestion.hyperliquid_connector import HyperliquidConnector
from crypto.src.ingestion.data_adapter import RealDataAdapter, fetch_oi_from_market_data
from crypto.src.pipeline import PipelineConfig, run_pipeline

ASSETS = ["HYPE", "BTC", "ETH", "SOL"]
RUN_ID = "run_017_shadow"
N_MINUTES = 120
TOP_K = 10
DEFAULT_OUT = "crypto/artifacts/runs/run_017_shadow"


def fetch_real_dataset(connector: HyperliquidConnector, n_minutes: int):
    """Fetch real market data for all assets and build a SyntheticDataset.

    Returns the dataset and a metadata dict describing fetch status.
    """
    adapter = RealDataAdapter(seed=42)
    candles_by_asset: dict = {}
    fundings_by_asset: dict = {}
    book_by_asset: dict = {}
    ctx_by_asset: dict = {}
    fetch_meta: dict = {}

    ctx_records = connector.fetch_asset_contexts()
    ctx_map = {r.asset: r for r in ctx_records}

    for asset in ASSETS:
        candles = connector.fetch_candles(asset, n_minutes)
        funding = connector.fetch_funding(asset, n_epochs=10)
        book = connector.fetch_book(asset)
        ctx = ctx_map.get(asset)

        candles_by_asset[asset] = candles
        fundings_by_asset[asset] = funding
        book_by_asset[asset] = book
        ctx_by_asset[asset] = ctx

        fetch_meta[asset] = {
            "n_candles": len(candles),
            "n_funding_records": len(funding),
            "book_available": book is not None,
            "ctx_available": ctx is not None,
            "oi_snapshot": round(ctx.open_interest, 2) if ctx else None,
            "mark_price": round(ctx.mark_price, 4) if ctx else None,
        }

    oi_series_by_asset = {
        asset: fetch_oi_from_market_data(asset, n_minutes)
        for asset in ASSETS
    }
    oi_series_by_asset = {k: v for k, v in oi_series_by_asset.items() if v}

    dataset = adapter.build_dataset(
        candles_by_asset, fundings_by_asset,
        book_by_asset, ctx_by_asset, n_minutes=n_minutes,
        oi_series_by_asset=oi_series_by_asset or None,
    )
    return dataset, fetch_meta


def run_shadow(output_dir: str, live: bool = True) -> dict:
    """Execute the full shadow pipeline on real data.

    Args:
        output_dir: Directory to write all output artifacts.
        live:       True = fetch from Hyperliquid API; False = use cache.

    Returns:
        Summary dict with run metadata and key metrics.
    """
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    print(f"[Run 017] Starting shadow pipeline (live={live})")
    cache_dir = os.path.join(output_dir, "api_cache")
    connector = HyperliquidConnector(cache_dir=cache_dir, live=live)

    print("[Run 017] Fetching real market data...")
    dataset, fetch_meta = fetch_real_dataset(connector, N_MINUTES)
    n_price = len(dataset.price_ticks)
    n_trade = len(dataset.trade_ticks)
    n_fund = len(dataset.funding_samples)
    print(f"[Run 017] Dataset: {n_price} price ticks, {n_trade} trade ticks, {n_fund} funding samples")

    if n_price == 0:
        print("[Run 017] WARNING: No price data fetched. Using synthetic fallback.")
        dataset = None

    config = PipelineConfig(
        run_id=RUN_ID,
        seed=42,
        n_minutes=N_MINUTES,
        assets=ASSETS,
        top_k=TOP_K,
        output_dir=output_dir,
        dataset=dataset,
    )

    print("[Run 017] Running pipeline (shadow mode, no trades)...")
    cards = run_pipeline(config)
    elapsed = round(time.time() - t0, 2)
    print(f"[Run 017] Pipeline complete in {elapsed}s — {len(cards)} hypothesis cards")

    # Load tier/watchlist data from pipeline-saved artifacts (not on card obj).
    tier_data = _load_artifact_json(output_dir, "i1_decision_tiers.json")
    watchlist_data = _load_artifact_json(output_dir, "i4_watchlist.json")
    branch_data = _load_artifact_json(output_dir, "branch_metrics.json")

    summary = _build_summary(cards, fetch_meta, elapsed, live, output_dir,
                             tier_data, branch_data)
    _write_run_config(output_dir, fetch_meta, live)
    _write_live_watchlist_log(output_dir, cards, watchlist_data, tier_data)
    _write_replay_vs_real_gap(output_dir, cards, fetch_meta, tier_data, branch_data)
    _write_failure_taxonomy(output_dir, fetch_meta)
    _write_family_hit_rate(output_dir, cards, tier_data, branch_data)

    summary_path = os.path.join(output_dir, "shadow_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[Run 017] Artifacts written to {output_dir}")
    return summary


def _load_artifact_json(output_dir: str, filename: str) -> dict:
    """Load a JSON artifact from the pipeline output directory.

    Returns {} if the file does not exist or is unparseable.
    """
    path = os.path.join(output_dir, RUN_ID, filename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _tier_counts_from_artifact(tier_data: dict) -> dict:
    """Extract tier distribution from i1_decision_tiers artifact.

    tier_assignments is a list of dicts (one per card), each with a
    'decision_tier' key. Aggregate into a tier → count dict.
    """
    assignments = tier_data.get("tier_assignments", [])
    counts: dict = {}
    for item in (assignments if isinstance(assignments, list) else []):
        tier = item.get("decision_tier", "unknown")
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def _family_counts_from_artifact(branch_data: dict) -> dict:
    """Extract grammar family distribution from branch_metrics artifact."""
    dist = branch_data.get("branch_distribution", {})
    return {k: v for k, v in dist.items() if k != "__total__"}


def _build_summary(cards, fetch_meta, elapsed, live, output_dir,
                   tier_data, branch_data):
    """Build a summary dict from the pipeline results and saved artifacts."""
    tier_counts = _tier_counts_from_artifact(tier_data) or {"n/a": len(cards)}
    family_counts = _family_counts_from_artifact(branch_data)
    return {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "offline_cache",
        "n_assets": len(ASSETS),
        "n_cards": len(cards),
        "elapsed_s": elapsed,
        "tier_distribution": tier_counts,
        "family_distribution": family_counts,
        "fetch_meta": fetch_meta,
        "output_dir": output_dir,
    }


def _write_run_config(output_dir, fetch_meta, live):
    """Write run_config.json."""
    cfg = {
        "run_id": RUN_ID,
        "sprint": "Q",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "objective": "Real-data shadow deployment — end-to-end test of calibrated monitoring engine",
        "assets": ASSETS,
        "n_minutes": N_MINUTES,
        "top_k": TOP_K,
        "mode": "shadow",
        "live_fetch": live,
        "data_source": "hyperliquid_public_api",
        "fetch_meta": fetch_meta,
        "calibration_source": "run_014_half_life + run_015_monitoring_budget + run_016_sparse_family",
        "pipeline_changes": ["PipelineConfig.dataset field added for real-data injection"],
        "new_files": [
            "crypto/src/ingestion/hyperliquid_connector.py",
            "crypto/src/ingestion/data_adapter.py",
            "crypto/run_017_shadow.py",
            "crypto/tests/test_run017_shadow.py",
            "docs/run017_shadow_deployment.md",
        ],
    }
    with open(os.path.join(output_dir, "run_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)


def _write_live_watchlist_log(output_dir, cards, watchlist_data, tier_data):
    """Write live_watchlist_log.csv.

    Merges HypothesisCard fields with tier (from i1) and watch_label (from i4).
    """
    # tier_assignments is a list of dicts; build card_id → decision_tier map.
    tier_assign = {
        item["card_id"]: item.get("decision_tier", "")
        for item in tier_data.get("tier_assignments", [])
        if isinstance(item, dict) and "card_id" in item
    }
    # i4 watchlist_cards: list of dicts with card_id, watch_label, branch, etc.
    watch_map = {
        w.get("card_id", ""): w
        for w in watchlist_data.get("watchlist_cards", [])
    }
    path = os.path.join(output_dir, "live_watchlist_log.csv")
    fieldnames = [
        "card_id", "title", "branch", "decision_tier", "grammar_family",
        "composite_score", "assets_mentioned", "watch_label", "tags",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in cards:
            cid = getattr(c, "card_id", "")
            w = watch_map.get(cid, {})
            writer.writerow({
                "card_id": cid,
                "title": getattr(c, "title", ""),
                "branch": w.get("branch", getattr(c, "kg_families", [""])[0] if getattr(c, "kg_families", []) else ""),
                "decision_tier": tier_assign.get(cid, ""),
                "grammar_family": w.get("grammar_family", ""),
                "composite_score": getattr(c, "composite_score", ""),
                "assets_mentioned": "",
                "watch_label": w.get("watch_label", ""),
                "tags": "|".join(getattr(c, "tags", []) or []),
            })


def _write_replay_vs_real_gap(output_dir, cards, fetch_meta, tier_data, branch_data):
    """Write replay_vs_real_gap.md comparing synthetic vs real data behaviour."""
    path = os.path.join(output_dir, "replay_vs_real_gap.md")
    tier_counts = _tier_counts_from_artifact(tier_data) or {"n/a": len(cards)}
    family_counts = _family_counts_from_artifact(branch_data)

    lines = [
        "# Run 017: Replay vs Real Data Gap Analysis",
        "",
        "## Data Coverage",
        "",
        "| Asset | Candles | Funding epochs | Book | OI snapshot |",
        "|-------|---------|----------------|------|-------------|",
    ]
    for asset in ASSETS:
        m = fetch_meta.get(asset, {})
        lines.append(
            f"| {asset} | {m.get('n_candles', 0)} | "
            f"{m.get('n_funding_records', 0)} | "
            f"{'Y' if m.get('book_available') else 'N'} | "
            f"{m.get('oi_snapshot', 'N/A')} |"
        )
    lines += [
        "",
        "## Card Distribution (Real Data)",
        "",
        "### By Tier",
        "",
    ]
    for tier, n in sorted(tier_counts.items()):
        lines.append(f"- {tier}: {n}")
    lines += [
        "",
        "### By Grammar Family",
        "",
    ]
    for fam, n in sorted(family_counts.items()):
        lines.append(f"- {fam}: {n}")
    lines += [
        "",
        "## Known Gaps vs Synthetic Replay",
        "",
        "| Gap | Impact | Root Cause |",
        "|-----|--------|------------|",
        "| No OI time-series | OI accumulation nodes absent | Single snapshot from API |",
        "| Derived trade ticks | Aggression signal approximate | No public trade tick endpoint |",
        "| Single book snapshot | Spread signal static | Only current book available |",
        "| Funding epochs may be sparse | Fewer FundingState transitions | Short lookback window |",
        "",
        "## Observations",
        "",
        f"- Total cards generated: {len(cards)}",
        f"- Data source: Hyperliquid public API (n_minutes={N_MINUTES})",
        "- Shadow mode: no trades placed",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_failure_taxonomy(output_dir, fetch_meta):
    """Write failure_taxonomy.md classifying real-data-specific issues."""
    path = os.path.join(output_dir, "failure_taxonomy.md")
    lines = [
        "# Run 017: Failure Taxonomy — Real Data Issues",
        "",
        "## Category 1: Data Coverage Issues",
        "",
        "| Issue | Affected Signal | Severity | Mitigation |",
        "|-------|-----------------|----------|------------|",
        "| No OI time-series (single snapshot) | OI accumulation, one_sided_position | Medium | Subscribe to OI WS feed for continuous series |",
        "| Derived trade ticks (not real fills) | Aggression bias, buy_ratio | Low-Medium | Use Hyperliquid WS trades feed for real fills |",
        "| Single book snapshot (not historical) | Spread z-score variation | Low | Book WS subscription for rolling snapshots |",
        "",
        "## Category 2: Data Quality Issues",
        "",
        "| Issue | Detection | Status |",
        "|-------|-----------|--------|",
        "| Zero candles returned (API unavailable) | fetch_meta.n_candles = 0 | Fallback to synthetic triggered |",
        "| Stale funding (no epochs in window) | fetch_meta.n_funding_records = 0 | Funding state extraction returns [] |",
        "| Price spike / outlier candle | |close - open| > 5% | Not filtered; treated as real signal |",
        "",
        "## Category 3: Timing Issues",
        "",
        "| Issue | Root Cause | Impact |",
        "|-------|------------|--------|",
        "| Clock skew between candle timestamps | API server time vs local time | ±1 min timing jitter in regime detection |",
        "| Candle boundary aggression window misalignment | 5-min rolling window vs 1-min candles | Aggression states may lag by up to 5 min |",
        "",
        "## Category 4: Grammar Mismatch",
        "",
        "| Issue | Description |",
        "|-------|-------------|",
        "| Synthetic scenario injection not present | HYPE burst at min 20-30 is a synthetic artifact; real data has no guaranteed burst |",
        "| Regime prevalence differs | Real data may show UNDEFINED regime more often if volatility is low |",
        "| SOL positioning_unwind scenario | Only fires in synthetic (min 65-80 burst); real SOL may show different patterns |",
        "",
        "## Asset-Level Fetch Status",
        "",
        "| Asset | Candles | Funding | Book | OI |",
        "|-------|---------|---------|------|----|",
    ]
    for asset in ASSETS:
        m = fetch_meta.get(asset, {})
        lines.append(
            f"| {asset} | {m.get('n_candles', 0)} | {m.get('n_funding_records', 0)} | "
            f"{'OK' if m.get('book_available') else 'MISS'} | "
            f"{'OK' if m.get('ctx_available') else 'MISS'} |"
        )
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_family_hit_rate(output_dir, cards, tier_data, branch_data):
    """Write family_hit_rate_real.md showing card distribution by family."""
    path = os.path.join(output_dir, "family_hit_rate_real.md")
    from collections import defaultdict
    # Build family→tier counts using kg_families from card + tier from artifact.
    tier_assign = {
        item["card_id"]: item.get("decision_tier", "unknown")
        for item in tier_data.get("tier_assignments", [])
        if isinstance(item, dict) and "card_id" in item
    }
    family_tier: dict = defaultdict(lambda: defaultdict(int))
    for c in cards:
        cid = getattr(c, "card_id", "")
        fam = (getattr(c, "kg_families", None) or ["unknown"])[0]
        tier = tier_assign.get(cid, "unknown")
        family_tier[fam][tier] += 1

    lines = [
        "# Run 017: Grammar Family Card Distribution (Real Data)",
        "",
        "Note: 'hit rate' for real data cannot be verified in a single run.",
        "This table shows tier distribution as a proxy for expected outcome quality.",
        "",
        "## Card Counts by Family and Tier",
        "",
        "| Grammar Family | actionable_watch | research_priority | monitor_borderline | baseline_like | reject_conflicted | total |",
        "|----------------|-----------------|-------------------|--------------------|---------------|-------------------|-------|",
    ]
    all_tiers = [
        "actionable_watch", "research_priority", "monitor_borderline",
        "baseline_like", "reject_conflicted",
    ]
    for fam, tier_counts in sorted(family_tier.items()):
        total = sum(tier_counts.values())
        row = f"| {fam} |"
        for t in all_tiers:
            row += f" {tier_counts.get(t, 0)} |"
        row += f" {total} |"
        lines.append(row)
    lines += [
        "",
        "## Comparison vs Synthetic Baseline",
        "",
        "| Family | Synthetic Hit Rate (Run 016) | Real Data (this run) |",
        "|--------|-----------------------------|--------------------|",
        "| positioning_unwind | 1.0 (SOL burst scenario) | TBD — outcome window not elapsed |",
        "| beta_reversion | 0.667 (calibrated) | TBD — outcome window not elapsed |",
        "| flow_continuation | 0.0 (no hits in synthetic) | TBD |",
        "| baseline | varies | TBD |",
        "",
        "Real-data outcome verification requires a follow-up run after the half-life window elapses.",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run 017: real-data shadow deployment")
    parser.add_argument(
        "--offline", action="store_true",
        help="Use cached data only (no live API calls)"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})"
    )
    args = parser.parse_args()

    summary = run_shadow(output_dir=args.output_dir, live=not args.offline)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
