"""Shadow Trading オーケストレーター。

pipeline_live.py の LivePipelineRunner をラップし、
各サイクルで ShadowSignal を記録・解決・P&L 計算する。
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from ..eval.delivery_state import _HL_BY_TIER
from ..states.event_detector import StateEvent
from .canary_monitor import CanaryMonitor
from .pnl_calculator import aggregate_pnl, batch_compute_pnl, compute_pnl
from .price_fetcher import PriceFetcher
from .signal_logger import SignalLogger, make_signal_id
from .types import ShadowSignal

_NON_TRADABLE_ASSETS = frozenset({"multi"})

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Direction 推定テーブル
# ---------------------------------------------------------------------------

_FAMILY_DIRECTION: dict[str, str] = {
    "flow_continuation": "long",
    "momentum":          "long",
    "positioning_unwind": "short",
    "unwind":            "short",
    "beta_reversion":    "short",
    "reversion":         "short",
    "cross_asset":       "neutral",
    "null_baseline":     "neutral",
    "null":              "neutral",
}

_EVENT_DIRECTION: dict[str, str] = {
    "buy_burst":          "long",
    "sell_burst":         "short",
    "book_thinning":      "short",
    "cross_asset_stress": "short",
    "spread_widening":    "neutral",
}

_DEFAULT_HALF_LIFE_MIN = 40.0  # actionable_watch tier のデフォルト


def infer_direction(event: StateEvent) -> str:
    """StateEvent から取引方向を推定する。

    event_type を優先し、次に grammar_family にフォールバックする。
    OI change は metadata["direction"] を参照する。

    Args:
        event: 解析対象の StateEvent。

    Returns:
        "long" / "short" / "neutral"。
    """
    if event.event_type == "oi_change":
        meta_dir = event.metadata.get("direction", "")
        return "long" if meta_dir == "accumulation" else "short"
    if event.event_type in _EVENT_DIRECTION:
        return _EVENT_DIRECTION[event.event_type]
    return _FAMILY_DIRECTION.get(event.grammar_family, "neutral")


def event_to_signal(
    event: StateEvent,
    entry_price: float,
    surfaced: bool,
    source_run: str = "",
) -> ShadowSignal:
    """StateEvent を ShadowSignal に変換する。

    Args:
        event:       元の StateEvent。
        entry_price: シグナル生成時のマーク価格（USD）。
        surfaced:    operator に配信されたか否か。
        source_run:  パイプライン run_id（任意）。

    Returns:
        ShadowSignal レコード。
    """
    timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event.timestamp_ms / 1000))
    signal_id = make_signal_id(event.asset, event.timestamp_ms, event.event_type, event.metadata)
    direction = infer_direction(event)
    half_life = _HL_BY_TIER.get("actionable_watch", _DEFAULT_HALF_LIFE_MIN)

    return ShadowSignal(
        signal_id=signal_id,
        timestamp_iso=timestamp_iso,
        asset=event.asset,
        direction=direction,
        conviction=event.severity,
        entry_price=entry_price,
        half_life_min=half_life,
        grammar_family=event.grammar_family,
        event_type=event.event_type,
        surfaced=surfaced,
        source_run=source_run,
        metadata=dict(event.metadata),
    )


# ---------------------------------------------------------------------------
# 未決シグナル管理
# ---------------------------------------------------------------------------

@dataclass
class _PendingSignal:
    """P&L 計算待ちのシグナル。"""

    signal: ShadowSignal
    resolve_at: float  # Unix 時刻


# ---------------------------------------------------------------------------
# ShadowTrader
# ---------------------------------------------------------------------------

@dataclass
class ShadowTraderConfig:
    """ShadowTrader の設定。

    Attributes:
        artifact_dir:   ログ出力先。
        notional_usd:   名目元本（USD）。
        use_price_cache: True = ディスクキャッシュを使用。
        resolve_check_interval_s: 未決シグナルの解決チェック間隔（秒）。
    """

    artifact_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "..", "..", "artifacts", "shadow"
    ))
    notional_usd: float = 100.0
    use_price_cache: bool = True
    resolve_check_interval_s: float = 60.0


class ShadowTrader:
    """Shadow Trading の中核クラス。

    StateEvent を受け取り、シグナルを記録・解決・P&L 計算する。
    CanaryMonitor を内包し、いつでも snapshot() で指標を取得できる。

    Args:
        config: ShadowTraderConfig。
    """

    def __init__(self, config: ShadowTraderConfig | None = None) -> None:
        """ShadowTrader を初期化する。"""
        self._cfg = config or ShadowTraderConfig()
        self._logger = SignalLogger(artifact_dir=self._cfg.artifact_dir)
        self._fetcher = PriceFetcher(use_cache=self._cfg.use_price_cache)
        self._canary = CanaryMonitor()
        self._pending: list[_PendingSignal] = []
        self._last_resolve_check = time.time()
        self._settled_ids: set[str] = set()
        self._halted = False
        self._load_settled_from_ledger()

    def _load_settled_from_ledger(self) -> None:
        """起動時に既存 pnl ファイルから settled signal_id を読み込む（replay 安全性）。"""
        for date in self._logger.available_dates():
            for trade in self._logger.iter_trades(date):
                self._settled_ids.add(trade.signal_id)
        if self._settled_ids:
            logger.info("Ledger から %d 件の settled signal_id を復元", len(self._settled_ids))

    def process_event(
        self,
        event: StateEvent,
        surfaced: bool,
        source_run: str = "",
    ) -> Optional[ShadowSignal]:
        """1 件の StateEvent をシグナルとして記録する。

        non-tradable イベント (asset="multi" 等) は regime ログに退避し、
        P&L 評価対象からは除外する。重複シグナルは idempotency ガードで排除。
        HALT 中は regime logging と監視のみ継続し、新規シグナル確定は停止する。

        Args:
            event:      処理する StateEvent。
            surfaced:   True = operator に配信された。
            source_run: パイプライン run_id（任意）。

        Returns:
            生成した ShadowSignal。スキップ時は None。
        """
        if event.asset in _NON_TRADABLE_ASSETS:
            self._logger.log_regime_event(event)
            return None

        if self._halted:
            self._logger.log_regime_event(event)
            return None

        timestamp_iso = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(event.timestamp_ms / 1000)
        )

        signal_id = make_signal_id(event.asset, event.timestamp_ms, event.event_type, dict(event.metadata))
        if signal_id in self._settled_ids:
            self._canary.record_duplicate()
            return None

        entry_price = self._fetcher.fetch(event.asset, timestamp_iso)
        if entry_price is None:
            logger.warning("価格取得失敗: asset=%s ts=%s", event.asset, timestamp_iso)
            self._canary.record_fetch_miss()
            return None

        signal = event_to_signal(event, entry_price, surfaced, source_run)
        self._settled_ids.add(signal.signal_id)
        self._logger.log_signal(signal)

        if surfaced:
            self._canary.record_surfaced_family(signal.grammar_family)

        resolve_at = time.time() + signal.half_life_min * 60.0
        self._pending.append(_PendingSignal(signal=signal, resolve_at=resolve_at))
        logger.debug("シグナル記録: %s %s %s", signal.asset, signal.direction, signal.signal_id)
        return signal

    def enter_halt(self, reasons: list[str]) -> None:
        """HALT 状態に移行する。新規シグナル確定を停止し、監視のみ継続する。"""
        if not self._halted:
            self._halted = True
            logger.warning("HALT 移行: %s — 新規シグナル確定を停止、監視継続", reasons)

    def record_review(self, *, is_fallback: bool, is_hot: bool) -> None:
        """レビュー 1 件を canary モニターに記録する。

        Args:
            is_fallback: fallback トリガーの場合 True。
            is_hot:      hot regime の場合 True。
        """
        self._canary.record_review(is_fallback=is_fallback, is_hot=is_hot)

    def record_latency(self, latency_ms: float) -> None:
        """処理遅延を canary モニターに記録する。

        Args:
            latency_ms: 遅延（ミリ秒）。
        """
        self._canary.record_latency(latency_ms)

    def record_operator_action(self) -> None:
        """計画外の手動介入を記録する。"""
        self._canary.record_operator_action()

    def maybe_resolve(self) -> list[str]:
        """半減期を超えた pending シグナルを解決し、P&L を記録する。

        resolve_check_interval_s 経過していない場合は何もしない。

        Returns:
            解決した signal_id のリスト。
        """
        now = time.time()
        if now - self._last_resolve_check < self._cfg.resolve_check_interval_s:
            return []
        self._last_resolve_check = now
        return self._resolve_expired(now)

    def _resolve_expired(self, now: float) -> list[str]:
        """now 時点で期限切れの pending シグナルを解決する。"""
        due = [p for p in self._pending if p.resolve_at <= now]
        if not due:
            return []

        # アセット別にまとめて価格取得
        exit_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        assets = {p.signal.asset for p in due}
        exit_prices: dict[str, float] = {}
        for asset in assets:
            price = self._fetcher.fetch(asset, exit_time_iso)
            if price is not None:
                exit_prices[asset] = price

        resolved_ids: list[str] = []
        remaining: list[_PendingSignal] = []

        for pending in self._pending:
            if pending.resolve_at > now:
                remaining.append(pending)
                continue
            sig = pending.signal
            exit_price = exit_prices.get(sig.asset)
            if exit_price is None:
                # 価格取得失敗 → 期限を 5 分延長してリトライ
                pending.resolve_at = now + 300.0
                remaining.append(pending)
                continue
            trade = compute_pnl(sig, exit_price, exit_time_iso, self._cfg.notional_usd)
            self._logger.log_trade(trade)
            resolved_ids.append(sig.signal_id)
            logger.info(
                "P&L 確定: %s %s pnl=%.4f%% hit=%s",
                sig.asset, sig.signal_id[:8], trade.pnl_pct * 100, trade.hit
            )

        self._pending = remaining

        if resolved_ids:
            self._refresh_canary_pnl_rates()

        return resolved_ids

    def _refresh_canary_pnl_rates(self) -> None:
        """今日の VirtualTrade を集計して canary 指標を更新する。"""
        today_iso = time.strftime("%Y-%m-%d", time.gmtime())
        trades = list(self._logger.iter_trades(today_iso))
        if not trades:
            return
        result = aggregate_pnl(trades, today_iso)
        self._canary.update_pnl_rates(
            sign_error_rate=result.sign_error_rate,
            missed_critical_rate=result.missed_critical_rate,
        )

    def canary_snapshot(self) -> "CanarySnapshot":  # type: ignore[name-defined]
        """現在の canary スナップショットを返す。

        Returns:
            CanarySnapshot（halt 判定含む）。
        """
        from .types import CanarySnapshot  # noqa: F401
        return self._canary.snapshot()

    def save_canary_snapshot(self) -> str:
        """canary スナップショットを JSON ファイルに保存し、パスを返す。

        Returns:
            保存先ファイルパス。
        """
        snap = self.canary_snapshot()
        today = time.strftime("%Y-%m-%d", time.gmtime())
        path = os.path.join(self._cfg.artifact_dir, f"canary_{today}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap.to_dict(), f, ensure_ascii=False, indent=2)
        return path
