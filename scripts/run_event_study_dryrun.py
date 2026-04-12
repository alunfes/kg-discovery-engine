"""Dry-run script for event study scaffold — 3 candidates C1/C2/C3.

Uses synthetic data to verify the full pipeline end-to-end.
Real data connector integration is deferred (see notes in output report).

Usage:
    python scripts/run_event_study_dryrun.py
"""

from __future__ import annotations

import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eval.event_study import (
    aggregate_metrics,
    apply_regime_slice,
    build_event_windows,
    compute_bridge_metrics,
    compute_metrics_from_windows,
    deduplicate_events,
    extract_chained_events,
    filter_events,
    generate_report,
    load_config,
    run_null_baselines,
    save_run_artifact,
)
from src.schema.market_state import OHLCV, StateEvent

BAR_MS = 3_600_000
N_BARS = 1000  # ~42 days of hourly bars
RANDOM_SEED = 42
RUN_DATE = "20260412"


# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int, symbol: str, base_price: float = 10.0) -> list[OHLCV]:
    """Generate n deterministic hourly OHLCV bars starting at epoch 0."""
    rng = random.Random(RANDOM_SEED)
    candles: list[OHLCV] = []
    price = base_price
    for i in range(n):
        ret = rng.gauss(0, 0.012)
        price = max(0.01, price * math.exp(ret))
        candles.append(OHLCV(
            timestamp=i * BAR_MS,
            symbol=symbol,
            open=price * 0.999,
            high=price * 1.006,
            low=price * 0.994,
            close=price,
            volume=rng.uniform(500, 2000),
            timeframe="1h",
        ))
    return candles


def _make_events(
    symbol: str,
    state_type: str,
    n_events: int,
    intensity_range: tuple[float, float] = (0.5, 1.0),
    rng_seed: int = RANDOM_SEED,
) -> list[StateEvent]:
    """Generate n_events state events at pseudo-random hourly timestamps."""
    rng = random.Random(rng_seed)
    events: list[StateEvent] = []
    for _ in range(n_events):
        ts = rng.randint(200, N_BARS - 200) * BAR_MS
        intensity = rng.uniform(*intensity_range)
        events.append(StateEvent(
            timestamp=ts,
            symbol=symbol,
            state_type=state_type,
            intensity=intensity,
            direction=rng.choice(["up", "down"]),
            duration_bars=1,
            attributes={"_synthetic": True},
        ))
    return sorted(events, key=lambda e: e.timestamp)


# ---------------------------------------------------------------------------
# Run helpers
# ---------------------------------------------------------------------------


def _run_single(
    config_path: str,
    ohlcv_map: dict[str, list[OHLCV]],
    source_events: list[StateEvent],
    run_dir: str,
    null_n_iter: int = 20,
) -> dict:
    """Execute full single-event pipeline and save artifacts."""
    cfg = load_config(config_path)
    if cfg.source_event is None:
        raise ValueError("Expected single-event config")

    deduped = deduplicate_events(source_events, cfg.dedup_window_bars, cfg.bar_duration_ms)
    windows = build_event_windows(deduped, ohlcv_map, cfg)
    metrics = compute_metrics_from_windows(windows)
    null_results = run_null_baselines(deduped, ohlcv_map, cfg, n_iterations=null_n_iter)
    agg = aggregate_metrics(metrics, cfg, null_results=null_results)
    report = generate_report(agg, cfg)
    save_run_artifact(run_dir, cfg, agg, report)

    return {
        "hypothesis_id": cfg.hypothesis_id,
        "event_count": agg.event_count,
        "unique_days": agg.unique_days,
        "mean_return": agg.event_window_mean_return,
        "hit_rate": agg.hit_rate,
        "p_value_approx": agg.p_value_approx,
        "run_dir": run_dir,
    }


def _run_chained(
    config_path: str,
    all_events: list[StateEvent],
    ohlcv_map: dict[str, list[OHLCV]],
    run_dir: str,
    null_n_iter: int = 20,
) -> dict:
    """Execute full chained-event pipeline and save artifacts."""
    cfg = load_config(config_path)
    if cfg.chain is None:
        raise ValueError("Expected chained config")

    events_map: dict[tuple[str, str], list[StateEvent]] = {}
    for e in all_events:
        events_map.setdefault((e.symbol, e.state_type), []).append(e)

    chains = extract_chained_events(events_map, cfg)
    bm = compute_bridge_metrics(chains)

    # Use chain source events to build return windows
    source_evs = [c.source for c in chains]
    source_deduped = deduplicate_events(
        sorted(source_evs, key=lambda e: e.timestamp),
        cfg.dedup_window_bars, cfg.bar_duration_ms,
    )
    windows = build_event_windows(source_deduped, ohlcv_map, cfg)
    metrics = compute_metrics_from_windows(windows)
    null_results = run_null_baselines(source_deduped, ohlcv_map, cfg, n_iterations=null_n_iter)
    agg = aggregate_metrics(metrics, cfg, null_results=null_results, chains=chains)
    report = generate_report(agg, cfg, chains=chains, bridge_metrics=bm)
    save_run_artifact(run_dir, cfg, agg, report, chains=chains, bridge_metrics=bm)

    return {
        "hypothesis_id": cfg.hypothesis_id,
        "chain_count": bm.bridge_frequency,
        "unique_bridges": bm.unique_bridges,
        "bridge_concentration": bm.bridge_concentration,
        "event_count": agg.event_count,
        "mean_return": agg.event_window_mean_return,
        "hit_rate": agg.hit_rate,
        "p_value_approx": agg.p_value_approx,
        "run_dir": run_dir,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run dry-run for all 3 event study candidates."""
    run_base = f"runs/run_015_{RUN_DATE}_event_study_dryrun"
    os.makedirs(run_base, exist_ok=True)

    print("=== Event Study Dry-Run ===")
    print(f"Synthetic data: {N_BARS} hourly bars, seed={RANDOM_SEED}\n")

    # Build synthetic multi-symbol price data
    ohlcv_map = {
        "HYPE": _make_ohlcv(N_BARS, "HYPE", base_price=10.0),
        "SOL":  _make_ohlcv(N_BARS, "SOL",  base_price=150.0),
        "BTC":  _make_ohlcv(N_BARS, "BTC",  base_price=65000.0),
        "ETH":  _make_ohlcv(N_BARS, "ETH",  base_price=3500.0),
    }

    # Build synthetic events for each symbol/type
    sol_fe   = _make_events("SOL",  "funding_extreme", n_events=40, rng_seed=1)
    hype_vb  = _make_events("HYPE", "vol_burst",       n_events=35, rng_seed=2)
    eth_vb   = _make_events("ETH",  "vol_burst",       n_events=30, rng_seed=3)
    btc_vb   = _make_events("BTC",  "vol_burst",       n_events=30, rng_seed=4)
    btc_pm   = _make_events("BTC",  "price_momentum",  n_events=25, rng_seed=5)
    hype_pm  = _make_events("HYPE", "price_momentum",  n_events=25, rng_seed=6)

    results_summary: list[dict] = []

    # --- C1: SOL funding_extreme → HYPE vol_burst (single) ---
    print("Running C1 (single): SOL funding_extreme → HYPE vol_burst")
    r1 = _run_single(
        "configs/event_study_C1_sol_funding_to_hype_vol.json",
        ohlcv_map,
        sol_fe,
        os.path.join(run_base, "C1"),
        null_n_iter=20,
    )
    print(f"  events={r1['event_count']}, mean_ret={r1['mean_return']:.4f}, "
          f"hit_rate={r1['hit_rate']:.2%}, p≈{r1['p_value_approx']}")
    results_summary.append(r1)

    # --- C2: ETH vol_burst → BTC vol_burst → HYPE price_momentum (chained) ---
    print("Running C2 (chained): ETH vol_burst → BTC vol_burst → HYPE price_momentum")
    all_c2 = eth_vb + btc_vb + hype_pm
    r2 = _run_chained(
        "configs/event_study_C2_eth_vol_to_btc_vol_to_hype_pm.json",
        all_c2,
        ohlcv_map,
        os.path.join(run_base, "C2"),
        null_n_iter=20,
    )
    print(f"  chains={r2['chain_count']}, unique_bridges={r2['unique_bridges']}, "
          f"concentration={r2['bridge_concentration']:.2%}, "
          f"events={r2['event_count']}, p≈{r2['p_value_approx']}")
    results_summary.append(r2)

    # --- C3: SOL funding_extreme → BTC price_momentum → HYPE price_momentum (chained) ---
    print("Running C3 (chained): SOL funding_extreme → BTC price_momentum → HYPE price_momentum")
    all_c3 = sol_fe + btc_pm + hype_pm
    r3 = _run_chained(
        "configs/event_study_C3_sol_funding_to_btc_pm_to_hype_pm.json",
        all_c3,
        ohlcv_map,
        os.path.join(run_base, "C3"),
        null_n_iter=20,
    )
    print(f"  chains={r3['chain_count']}, unique_bridges={r3['unique_bridges']}, "
          f"concentration={r3['bridge_concentration']:.2%}, "
          f"events={r3['event_count']}, p≈{r3['p_value_approx']}")
    results_summary.append(r3)

    # Save summary
    summary_path = os.path.join(run_base, "dryrun_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nArtifacts saved to: {run_base}/")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
