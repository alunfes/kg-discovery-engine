"""Shadow Trading 共通データクラス定義。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShadowSignal:
    """パイプラインが生成した 1 件のシグナル記録。

    Attributes:
        signal_id:       UUID v4 文字列（衝突回避のため signal_logger が付与）。
        timestamp_iso:   シグナル生成時刻（UTC ISO-8601）。
        asset:           対象アセット（例: "HYPE", "BTC"）。
        direction:       推定方向 "long" / "short" / "neutral"。
        conviction:      確信度 [0.0, 1.0]（StateEvent.severity から）。
        entry_price:     シグナル生成時の mark price（USD）。
        half_life_min:   P&L 計測ウィンドウ（カードのティアに基づく）。
        grammar_family:  KG ファミリー名。
        event_type:      StateEvent.event_type。
        surfaced:        True = operator に配信、False = drop/archive。
        card_id:         元の HypothesisCard.card_id（任意）。
        source_run:      パイプライン run_id。
        metadata:        追加コンテキスト（z-score など）。
    """

    signal_id: str
    timestamp_iso: str
    asset: str
    direction: str
    conviction: float
    entry_price: float
    half_life_min: float
    grammar_family: str
    event_type: str
    surfaced: bool
    card_id: Optional[str] = None
    source_run: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """JSON 直列化用辞書を返す。"""
        return {
            "signal_id": self.signal_id,
            "timestamp_iso": self.timestamp_iso,
            "asset": self.asset,
            "direction": self.direction,
            "conviction": self.conviction,
            "entry_price": self.entry_price,
            "half_life_min": self.half_life_min,
            "grammar_family": self.grammar_family,
            "event_type": self.event_type,
            "surfaced": self.surfaced,
            "card_id": self.card_id,
            "source_run": self.source_run,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShadowSignal":
        """辞書から復元する。"""
        return cls(
            signal_id=d["signal_id"],
            timestamp_iso=d["timestamp_iso"],
            asset=d["asset"],
            direction=d["direction"],
            conviction=float(d["conviction"]),
            entry_price=float(d["entry_price"]),
            half_life_min=float(d["half_life_min"]),
            grammar_family=d["grammar_family"],
            event_type=d["event_type"],
            surfaced=bool(d["surfaced"]),
            card_id=d.get("card_id"),
            source_run=d.get("source_run", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class VirtualTrade:
    """P&L が確定した仮想取引の記録。

    Attributes:
        signal_id:     元の ShadowSignal.signal_id。
        asset:         対象アセット。
        direction:     "long" / "short" / "neutral"。
        entry_price:   エントリー価格（USD）。
        entry_time_iso: エントリー時刻（UTC ISO-8601）。
        exit_price:    エグジット価格（USD）。
        exit_time_iso: エグジット時刻（UTC ISO-8601）。
        notional_usd:  名目元本（USD）。
        pnl_usd:       仮想損益（USD）。
        pnl_pct:       損益率（小数）。
        hit:           方向が正しかった場合 True。
        surfaced:      元シグナルが配信されたか否か。
    """

    signal_id: str
    asset: str
    direction: str
    entry_price: float
    entry_time_iso: str
    exit_price: float
    exit_time_iso: str
    notional_usd: float
    pnl_usd: float
    pnl_pct: float
    hit: bool
    surfaced: bool

    def to_dict(self) -> dict:
        """JSON 直列化用辞書を返す。"""
        return {
            "signal_id": self.signal_id,
            "asset": self.asset,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time_iso": self.entry_time_iso,
            "exit_price": self.exit_price,
            "exit_time_iso": self.exit_time_iso,
            "notional_usd": self.notional_usd,
            "pnl_usd": round(self.pnl_usd, 4),
            "pnl_pct": round(self.pnl_pct, 6),
            "hit": self.hit,
            "surfaced": self.surfaced,
        }


@dataclass
class PnLResult:
    """Shadow Trading セッションの集計 P&L 結果。

    Attributes:
        date_iso:          集計日（UTC ISO-8601 日付）。
        n_surfaced:        配信シグナル数。
        n_dropped:         ドロップシグナル数。
        n_resolved:        P&L 確定済みシグナル数。
        total_pnl_usd:     累計仮想損益（配信シグナルのみ）。
        win_rate:          勝率（0.0〜1.0）。
        avg_pnl_pct:       平均損益率。
        sharpe_approx:     簡易シャープレシオ（標準偏差ベース）。
        sign_error_rate: 方向を外した surfaced カード比率 (= 1 - win_rate)。
        missed_critical_rate: ±5% 超えのドロップカード比率。
    """

    date_iso: str
    n_surfaced: int
    n_dropped: int
    n_resolved: int
    total_pnl_usd: float
    win_rate: float
    avg_pnl_pct: float
    sharpe_approx: float
    sign_error_rate: Optional[float]
    missed_critical_rate: float

    def to_dict(self) -> dict:
        """JSON 直列化用辞書を返す。"""
        return {
            "date_iso": self.date_iso,
            "n_surfaced": self.n_surfaced,
            "n_dropped": self.n_dropped,
            "n_resolved": self.n_resolved,
            "total_pnl_usd": round(self.total_pnl_usd, 4),
            "win_rate": round(self.win_rate, 4),
            "avg_pnl_pct": round(self.avg_pnl_pct, 6),
            "sharpe_approx": round(self.sharpe_approx, 4),
            "sign_error_rate": self.sign_error_rate,
            "missed_critical_rate": round(self.missed_critical_rate, 4),
        }


@dataclass
class CanarySnapshot:
    """1 日分の canary 指標スナップショット。

    3系統に分離された品質指標:
      - 方向性品質: sign_error_rate, missed_critical_rate
      - 運用品質: fetch_miss_count, duplicate_count, latency
      - 配信品質: reviews_per_day, fallback_rate, family_coverage

    HALT は 2 種に分離:
      - plumbing_halt: 配管異常（fetch miss / duplicate / latency）
      - strategy_halt: 戦略品質（sign error / missed critical）
    """

    date_iso: str
    reviews_per_day: float
    sign_error_rate: Optional[float]
    missed_critical_rate: float
    latency_p50_ms: Optional[float]
    latency_p95_ms: Optional[float]
    fallback_rate_overall: float
    fallback_rate_hot: float
    family_coverage: int
    operator_burden: int
    fetch_miss_count: int = 0
    duplicate_count: int = 0
    halt_triggered: bool = False
    halt_reasons: list[str] = field(default_factory=list)
    warn_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON 直列化用辞書を返す。"""
        return {
            "date_iso": self.date_iso,
            "reviews_per_day": round(self.reviews_per_day, 2),
            "sign_error_rate": self.sign_error_rate,
            "missed_critical_rate": round(self.missed_critical_rate, 4),
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "fallback_rate_overall": round(self.fallback_rate_overall, 4),
            "fallback_rate_hot": round(self.fallback_rate_hot, 4),
            "family_coverage": self.family_coverage,
            "operator_burden": self.operator_burden,
            "fetch_miss_count": self.fetch_miss_count,
            "duplicate_count": self.duplicate_count,
            "halt_triggered": self.halt_triggered,
            "halt_reasons": self.halt_reasons,
            "warn_flags": self.warn_flags,
        }
