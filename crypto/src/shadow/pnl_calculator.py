"""仮想 P&L の計算ロジック。

ShadowSignal + エグジット価格 → VirtualTrade を生成する。
"""
from __future__ import annotations

import math
import time
from typing import Optional

from .types import ShadowSignal, VirtualTrade, PnLResult

_DEFAULT_NOTIONAL_USD = 100.0


def _direction_multiplier(direction: str) -> float:
    """direction 文字列を損益乗数に変換する。

    Args:
        direction: "long" / "short" / "neutral"。

    Returns:
        1.0（long）、-1.0（short）、0.0（neutral）。
    """
    return {"long": 1.0, "short": -1.0, "neutral": 0.0}.get(direction, 0.0)


def compute_pnl(
    signal: ShadowSignal,
    exit_price: float,
    exit_time_iso: str,
    notional_usd: float = _DEFAULT_NOTIONAL_USD,
) -> VirtualTrade:
    """1 件の ShadowSignal から VirtualTrade を計算する。

    Args:
        signal:        元のシグナル（エントリー情報を含む）。
        exit_price:    エグジット時点のマーク価格（USD）。
        exit_time_iso: エグジット時刻（UTC ISO-8601）。
        notional_usd:  名目元本（USD）。

    Returns:
        P&L が確定した VirtualTrade。
    """
    mult = _direction_multiplier(signal.direction)
    if signal.entry_price <= 0:
        pnl_pct = 0.0
    else:
        pnl_pct = mult * (exit_price - signal.entry_price) / signal.entry_price

    position_usd = notional_usd * signal.conviction
    pnl_usd = pnl_pct * position_usd

    return VirtualTrade(
        signal_id=signal.signal_id,
        asset=signal.asset,
        direction=signal.direction,
        entry_price=signal.entry_price,
        entry_time_iso=signal.timestamp_iso,
        exit_price=exit_price,
        exit_time_iso=exit_time_iso,
        notional_usd=position_usd,
        pnl_usd=pnl_usd,
        pnl_pct=pnl_pct,
        hit=(pnl_pct > 0.0),
        surfaced=signal.surfaced,
    )


def batch_compute_pnl(
    signals: list[ShadowSignal],
    exit_prices: dict[str, float],
    exit_time_iso: str,
    notional_usd: float = _DEFAULT_NOTIONAL_USD,
) -> list[VirtualTrade]:
    """複数シグナルを一括で VirtualTrade に変換する。

    exit_prices に含まれないアセットのシグナルはスキップする。

    Args:
        signals:       処理対象のシグナルリスト。
        exit_prices:   アセット名 → マーク価格（USD）の辞書。
        exit_time_iso: エグジット時刻（UTC ISO-8601）。
        notional_usd:  名目元本（USD）。

    Returns:
        VirtualTrade のリスト。
    """
    trades: list[VirtualTrade] = []
    for sig in signals:
        price = exit_prices.get(sig.asset)
        if price is None:
            continue
        trades.append(compute_pnl(sig, price, exit_time_iso, notional_usd))
    return trades


def _safe_std(values: list[float]) -> float:
    """母標準偏差を安全に計算する（空・単要素は 0 を返す）。"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var) if var > 0 else 0.0


def aggregate_pnl(trades: list[VirtualTrade], date_iso: str) -> PnLResult:
    """VirtualTrade リストから日次 PnLResult を集計する。

    sign_error_rate (方向ミス率 = 1 - win_rate) と
    missed_critical_rate (±5% 超えドロップ) を計算する。

    Args:
        trades:   集計対象の VirtualTrade リスト。
        date_iso: 集計日（YYYY-MM-DD）。

    Returns:
        集計済み PnLResult。
    """
    surfaced = [t for t in trades if t.surfaced]
    dropped = [t for t in trades if not t.surfaced]

    total_pnl = sum(t.pnl_usd for t in surfaced)
    pnl_pcts = [t.pnl_pct for t in surfaced]
    hits = [t for t in surfaced if t.hit]

    win_rate = len(hits) / len(surfaced) if surfaced else 0.0
    avg_pnl_pct = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0.0
    std = _safe_std(pnl_pcts)
    sharpe = (avg_pnl_pct / std) if std > 0 else 0.0

    # sign_error_rate: 方向を外した surfaced カード比率 (= 1 - win_rate)
    sign_error_rate: Optional[float] = None
    if surfaced:
        sign_error_rate = 1.0 - win_rate

    # missed_critical_rate: dropped で |pnl_pct| >= 0.05 の比率
    missed_critical_rate = 0.0
    if dropped:
        mc_count = sum(1 for t in dropped if abs(t.pnl_pct) >= 0.05)
        missed_critical_rate = mc_count / len(dropped)

    return PnLResult(
        date_iso=date_iso,
        n_surfaced=len(surfaced),
        n_dropped=len(dropped),
        n_resolved=len(trades),
        total_pnl_usd=total_pnl,
        win_rate=win_rate,
        avg_pnl_pct=avg_pnl_pct,
        sharpe_approx=sharpe,
        sign_error_rate=sign_error_rate,
        missed_critical_rate=missed_critical_rate,
    )
