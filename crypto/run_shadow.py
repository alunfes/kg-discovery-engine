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


def _parse_args() -> argparse.Namespace:
    """CLI 引数を解析する。"""
    p = argparse.ArgumentParser(description="Shadow Trading daemon")
    p.add_argument("--replay", action="store_true", help="ライブ接続なし（replay モード）")
    p.add_argument("--cycles", type=int, default=0, help="最大サイクル数（0=無制限）")
    p.add_argument("--assets", nargs="+", default=_DEFAULT_ASSETS)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--artifact-dir", default=_DEFAULT_ARTIFACT_DIR)
    p.add_argument("--notional", type=float, default=100.0, help="名目元本 USD")
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

    pipe_cfg = LivePipelineConfig(
        assets=args.assets,
        live=not args.replay,
        seed=args.seed,
        max_cycles=args.cycles,
        shadow_mode=True,
        output_dir=os.path.join(args.artifact_dir, "pipeline_out"),
    )

    logger.info("Shadow Trading 開始: replay=%s assets=%s", args.replay, args.assets)
    t_start = time.time()
    runner = LivePipelineRunner(pipe_cfg)

    try:
        results = runner.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — 終了処理中...")
        results = []

    elapsed_min = (time.time() - t_start) / 60.0
    n_events = len(getattr(runner, "_all_events", []))
    logger.info("パイプライン完了: %.1f分, %d cycles, %d events", elapsed_min, len(results), n_events)
    if n_events == 0:
        logger.warning("plumbing:no_events — パイプライン完了したがイベント 0 件")

    # 全 StateEvent を ShadowTrader に通知（replay / live 共通）
    # idempotency ガードにより重複は自動排除される
    for event in getattr(runner, "_all_events", []):
        surfaced = event.severity >= 0.6
        trader.process_event(event, surfaced=surfaced, source_run="run_shadow")

    # 残 pending シグナルを強制解決（セッション終了時）
    trader._resolve_expired(time.time() + 10 ** 8)

    # canary スナップショットを保存
    snap_path = trader.save_canary_snapshot()
    snap = trader.canary_snapshot()

    logger.info("Canary スナップショット保存: %s", snap_path)
    logger.info(
        "sign_error=%.3f missed_critical=%.3f fetch_miss=%d dup=%d halt=%s warns=%s",
        snap.sign_error_rate or 0.0,
        snap.missed_critical_rate,
        snap.fetch_miss_count,
        snap.duplicate_count,
        snap.halt_triggered,
        snap.warn_flags,
    )

    # サマリーを stdout に出力（HALT でも exit(1) しない — 配管 HALT で無限再起動ループを防ぐ）
    summary = {
        "n_results": len(results),
        "canary": snap.to_dict(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if snap.halt_triggered:
        logger.warning("HALT 条件に抵触: %s", snap.halt_reasons)
        trader.enter_halt(snap.halt_reasons)


def main() -> None:
    """エントリポイント。"""
    args = _parse_args()
    _run_shadow(args)


if __name__ == "__main__":
    main()
