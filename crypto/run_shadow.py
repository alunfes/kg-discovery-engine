"""Shadow Trading CLI エントリポイント。

使い方:
    python -m crypto.run_shadow [--replay] [--cycles N] [--assets A B C]

shadow_mode=True で LivePipelineRunner を実行し、
StateEvent を ShadowTrader に渡してシグナル記録・P&L 計算を行う。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# crypto パッケージをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crypto.src.pipeline_live import LivePipelineConfig, LivePipelineRunner
from crypto.src.shadow.shadow_daemon import ShadowTrader, ShadowTraderConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_shadow")

_DEFAULT_ASSETS = ["HYPE", "BTC", "ETH", "SOL"]
_DEFAULT_ARTIFACT_DIR = os.path.join(
    os.path.dirname(__file__), "artifacts", "shadow"
)
_PARTIAL_CANARY_INTERVAL = 10


def _parse_args() -> argparse.Namespace:
    """CLI 引数を解析する。"""
    p = argparse.ArgumentParser(description="Shadow Trading daemon")
    p.add_argument("--replay", action="store_true", help="ライブ接続なし（replay モード）")
    p.add_argument("--cycles", type=int, default=0, help="最大サイクル数（0=無制限）")
    p.add_argument("--assets", nargs="+", default=_DEFAULT_ASSETS)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--artifact-dir", default=_DEFAULT_ARTIFACT_DIR)
    p.add_argument("--notional", type=float, default=100.0, help="名目元本 USD")
    p.add_argument("--partial-canary", type=int, default=_PARTIAL_CANARY_INTERVAL,
                    help="partial canary snapshot 間隔 (cycles)")
    return p.parse_args()


def _run_shadow(args: argparse.Namespace) -> None:
    """Shadow Trading メインループを実行する。"""
    os.makedirs(args.artifact_dir, exist_ok=True)

    trader_cfg = ShadowTraderConfig(
        artifact_dir=args.artifact_dir,
        notional_usd=args.notional,
        use_price_cache=True,
    )
    trader = ShadowTrader(config=trader_cfg)
    partial_interval = args.partial_canary
    cycle_stats = {"total_events": 0, "total_signals": 0, "ws_stale_count": 0}

    def _on_cycle(result: dict, new_events: list) -> None:
        """毎サイクル呼ばれるコールバック: インクリメンタルにイベントを処理。"""
        cycle = result["cycle"]

        # failure telemetry: WS 切断検知
        if not result.get("event_types"):
            pass  # events=0 は正常（静かな市場）
        # ws_alive は heartbeat で確認済み — ここでは event 側で検知

        # イベントをインクリメンタルに ShadowTrader に投入
        for event in new_events:
            surfaced = event.severity >= 0.6
            sig = trader.process_event(event, surfaced=surfaced, source_run="run_shadow")
            if sig is not None:
                cycle_stats["total_signals"] += 1
        cycle_stats["total_events"] += len(new_events)

        # pending シグナルの解決チェック
        trader.maybe_resolve()

        # partial canary: N cycle ごとに中間 snapshot
        if partial_interval > 0 and cycle > 0 and cycle % partial_interval == 0:
            snap = trader.canary_snapshot()
            snap_path = trader.save_canary_snapshot()
            pending = len(trader._pending)
            settled = len(trader._settled_ids)
            logger.info(
                "partial_canary cycle=%d sign_error=%.3f fetch_miss=%d dup=%d "
                "pending=%d settled=%d signals=%d halt=%s warns=%s",
                cycle, snap.sign_error_rate or 0.0,
                snap.fetch_miss_count, snap.duplicate_count,
                pending, settled, cycle_stats["total_signals"],
                snap.halt_triggered, snap.warn_flags,
            )
            if snap.halt_triggered:
                logger.warning("partial HALT: %s", snap.halt_reasons)
                trader.enter_halt(snap.halt_reasons)

    pipe_cfg = LivePipelineConfig(
        assets=args.assets,
        live=not args.replay,
        seed=args.seed,
        max_cycles=args.cycles,
        shadow_mode=True,
        output_dir=os.path.join(args.artifact_dir, "pipeline_out"),
    )

    logger.info("Shadow Trading 開始: replay=%s assets=%s partial_canary=%d",
                args.replay, args.assets, partial_interval)
    t_start = time.time()
    runner = LivePipelineRunner(pipe_cfg)

    try:
        results = runner.run(on_cycle_complete=_on_cycle)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — 終了処理中...")
        results = []

    elapsed_min = (time.time() - t_start) / 60.0
    logger.info("パイプライン完了: %.1f分, %d cycles, %d events, %d signals",
                elapsed_min, len(results), cycle_stats["total_events"],
                cycle_stats["total_signals"])

    if cycle_stats["total_events"] == 0:
        logger.warning("plumbing:no_events — パイプライン完了したがイベント 0 件")

    # final drain の新規イベントも処理
    for event in getattr(runner, "_all_events", [])[cycle_stats["total_events"]:]:
        surfaced = event.severity >= 0.6
        trader.process_event(event, surfaced=surfaced, source_run="run_shadow")

    # 残 pending シグナルを強制解決
    trader._resolve_expired(time.time() + 10 ** 8)

    # 最終 canary スナップショット
    snap_path = trader.save_canary_snapshot()
    snap = trader.canary_snapshot()
    pending = len(trader._pending)
    settled = len(trader._settled_ids)

    logger.info("最終 Canary: %s", snap_path)
    logger.info(
        "sign_error=%.3f missed_critical=%.3f fetch_miss=%d dup=%d "
        "pending=%d settled=%d halt=%s warns=%s",
        snap.sign_error_rate or 0.0, snap.missed_critical_rate,
        snap.fetch_miss_count, snap.duplicate_count,
        pending, settled, snap.halt_triggered, snap.warn_flags,
    )

    summary = {"n_results": len(results), "canary": snap.to_dict()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if snap.halt_triggered:
        logger.warning("HALT 条件に抵触: %s", snap.halt_reasons)
        trader.enter_halt(snap.halt_reasons)

    # Post-processing: competition analysis (offline, does not affect shadow trading)
    try:
        from crypto.src.kg.competition_runner import run_competition_analysis
        comp_out = os.path.join(args.artifact_dir, "competition")
        pipeline_out = os.path.join(args.artifact_dir, "pipeline_out")
        comp = run_competition_analysis(
            pipeline_out, regime="correlation_break",
            group_fn="cycle_asset", output_dir=comp_out,
        )
        cs = comp.summary_table()
        logger.info(
            "competition: groups=%d null_win=%.1f%% conf=%.3f fam/grp=%.1f",
            cs.get("n_groups", 0), cs.get("null_win_pct", 0),
            cs.get("confidence_median", 0), cs.get("families_per_group_mean", 0),
        )
    except Exception as e:
        logger.warning("competition analysis failed: %s", e)


def main() -> None:
    """エントリポイント。"""
    args = _parse_args()
    _run_shadow(args)


if __name__ == "__main__":
    main()
