"""canary-criteria.md で定義された 7 指標のリアルタイム監視。

計測値を蓄積し、CanarySnapshot を生成する。
halt 条件に抵触した場合は halt_triggered=True を返す。
"""
from __future__ import annotations

import statistics
import time
from collections import defaultdict
from typing import Optional

from .types import CanarySnapshot

# ---------------------------------------------------------------------------
# 閾値定数（canary-criteria.md 準拠）
# ---------------------------------------------------------------------------

# 1-A reviews/day
_REVIEWS_WARN = 35.0
_REVIEWS_ALERT = 50.0
_REVIEWS_HALT_DAYS = 3          # ALERT が N 日連続で AUTO-1 停止

# 1-B sign_error_rate (方向ミス率 = 1 - win_rate)
_SIGN_ERROR_WARN = 0.50
_SIGN_ERROR_HALT = 0.65

# 1-C missed_critical_rate
_MISSED_HALT = 0.05             # HALT-1: 1 日でも超えたら即停止

# 1-D latency
_LATENCY_WARN_MS = 5_000.0
_LATENCY_HALT_MS = 15_000.0
_LATENCY_HALT_COUNT = 10        # 1 時間内に N 回超えで HALT-2

# 1-E fallback_rate
_FALLBACK_WARN_OVERALL = 0.30
_FALLBACK_ALERT_OVERALL = 0.60
_FALLBACK_HOT_HALT = 0.50       # hot regime で超えたら HALT-3

# 1-F family_coverage
_FAMILY_WARN = 3                # N 日連続で warn
_FAMILY_HALT = 2                # N 日連続で AUTO-3 停止

# 1-G operator_burden
_BURDEN_WARN = 1
_BURDEN_ALERT_DAYS = 2          # ALERT が N 日連続で MANUAL-1


class CanaryMonitor:
    """インクリメンタルに canary 指標を蓄積・評価するモニター。

    セッション開始時にインスタンス化し、各サイクルで update_* メソッドを
    呼び出す。snapshot() で現在の CanarySnapshot を取得できる。

    Args:
        session_start_time: セッション開始 Unix 時刻（テスト用に注入可能）。
    """

    def __init__(self, session_start_time: Optional[float] = None) -> None:
        """CanaryMonitor を初期化する。"""
        self._start_time = session_start_time or time.time()

        # 1-A
        self._n_reviews: int = 0
        self._n_push: int = 0
        self._n_fallback: int = 0

        # 1-B / 1-C — trades リストは pnl_calculator 側が計算するので受け取るだけ
        self._sign_error_rate: Optional[float] = None
        self._missed_critical_rate: float = 0.0

        # 配管品質（plumbing）
        self._fetch_miss_count: int = 0
        self._duplicate_count: int = 0

        # 1-D
        self._latency_ms_log: list[float] = []
        self._latency_halt_window: list[float] = []  # 直近 1h のタイムスタンプ

        # 1-E
        self._n_hot_reviews: int = 0
        self._n_hot_fallback: int = 0

        # 1-F
        self._surfaced_families: set[str] = set()

        # 1-G
        self._operator_burden: int = 0

    # ------------------------------------------------------------------
    # 更新 API
    # ------------------------------------------------------------------

    def record_review(self, *, is_fallback: bool, is_hot: bool) -> None:
        """レビュー 1 件を記録する。

        Args:
            is_fallback: poll_45min fallback によるレビューの場合 True。
            is_hot:      hot regime（hot_prob ≥ 0.5）の場合 True。
        """
        self._n_reviews += 1
        if is_fallback:
            self._n_fallback += 1
        else:
            self._n_push += 1
        if is_hot:
            self._n_hot_reviews += 1
            if is_fallback:
                self._n_hot_fallback += 1

    def record_latency(self, latency_ms: float) -> None:
        """処理遅延 1 件を記録する。

        Args:
            latency_ms: 遅延時間（ミリ秒）。
        """
        self._latency_ms_log.append(latency_ms)
        now = time.time()
        self._latency_halt_window.append(now)
        # 1h より古いエントリを削除
        cutoff = now - 3600.0
        self._latency_halt_window = [t for t in self._latency_halt_window if t > cutoff]

    def record_surfaced_family(self, family: str) -> None:
        """配信されたカードの grammar_family を記録する。

        Args:
            family: grammar_family 名。
        """
        self._surfaced_families.add(family)

    def record_operator_action(self) -> None:
        """計画外のオペレーター手動介入 1 件を記録する。"""
        self._operator_burden += 1

    def record_fetch_miss(self) -> None:
        """価格取得失敗 1 件を記録する。"""
        self._fetch_miss_count += 1

    def record_duplicate(self) -> None:
        """重複シグナル検出 1 件を記録する。"""
        self._duplicate_count += 1

    def update_pnl_rates(
        self,
        sign_error_rate: Optional[float],
        missed_critical_rate: float,
    ) -> None:
        """P&L 計算後の方向ミス率・見逃し率を更新する。

        Args:
            sign_error_rate:     方向ミス率 (= 1 - win_rate, None = 未計測)。
            missed_critical_rate: ±5% 超えのドロップカード比率。
        """
        self._sign_error_rate = sign_error_rate
        self._missed_critical_rate = missed_critical_rate

    # ------------------------------------------------------------------
    # 集計
    # ------------------------------------------------------------------

    def _elapsed_hours(self) -> float:
        """セッション開始からの経過時間（時間）。最小 1h で割る。"""
        return max((time.time() - self._start_time) / 3600.0, 1.0 / 60)

    def _reviews_per_day(self) -> float:
        """経過時間から外挿した reviews/day を返す。"""
        return self._n_reviews / self._elapsed_hours() * 24.0

    def _fallback_rate_overall(self) -> float:
        """全体の fallback 発火率を返す。"""
        if self._n_reviews == 0:
            return 0.0
        return self._n_fallback / self._n_reviews

    def _fallback_rate_hot(self) -> float:
        """hot regime 限定の fallback 発火率を返す。"""
        if self._n_hot_reviews == 0:
            return 0.0
        return self._n_hot_fallback / self._n_hot_reviews

    def _latency_p50(self) -> Optional[float]:
        """遅延中央値（ms）を返す。データなしは None。"""
        if not self._latency_ms_log:
            return None
        return statistics.median(self._latency_ms_log)

    def _latency_p95(self) -> Optional[float]:
        """遅延 p95（ms）を返す。データなしは None。"""
        if not self._latency_ms_log:
            return None
        sorted_log = sorted(self._latency_ms_log)
        idx = max(0, int(len(sorted_log) * 0.95) - 1)
        return sorted_log[idx]

    def _halt_latency_count_in_window(self) -> int:
        """直近 1h で HALT 閾値を超えた遅延の件数を返す。"""
        cutoff = time.time() - 3600.0
        return sum(
            1
            for i, ts in enumerate(self._latency_halt_window)
            if ts > cutoff and i < len(self._latency_ms_log)
            and self._latency_ms_log[-(len(self._latency_halt_window) - i)] > _LATENCY_HALT_MS
        )

    # ------------------------------------------------------------------
    # スナップショット生成
    # ------------------------------------------------------------------

    def snapshot(self, date_iso: Optional[str] = None) -> CanarySnapshot:
        """現在の計測値から CanarySnapshot を生成する。

        halt 条件・warn 条件を評価し、結果を返す。

        Args:
            date_iso: スナップショット日付（省略時は今日の UTC）。

        Returns:
            評価済み CanarySnapshot。
        """
        import time as _time
        date = date_iso or _time.strftime("%Y-%m-%d", _time.gmtime())

        rpd = self._reviews_per_day()
        fb_overall = self._fallback_rate_overall()
        fb_hot = self._fallback_rate_hot()
        lat_p50 = self._latency_p50()
        lat_p95 = self._latency_p95()

        halt_reasons: list[str] = []
        warn_flags: list[str] = []

        # --- 配管異常 HALT (plumbing) ---
        halt_lat_count = self._halt_latency_count_in_window()
        if halt_lat_count >= _LATENCY_HALT_COUNT:
            halt_reasons.append("plumbing:latency")
        if self._duplicate_count > 0:
            warn_flags.append("plumbing:duplicates_detected")

        # --- 戦略品質 HALT (strategy) ---
        if self._missed_critical_rate > _MISSED_HALT:
            halt_reasons.append("strategy:missed_critical")
        if fb_hot > _FALLBACK_HOT_HALT and self._n_hot_reviews > 0:
            halt_reasons.append("strategy:hot_fallback")

        ser = self._sign_error_rate
        if ser is not None and ser > _SIGN_ERROR_HALT:
            halt_reasons.append("strategy:sign_error")
        elif ser is not None and ser > _SIGN_ERROR_WARN:
            warn_flags.append("strategy:sign_error_warn")

        # --- Warn flags ---
        if rpd > _REVIEWS_ALERT:
            warn_flags.append("reviews_alert")
        elif rpd > _REVIEWS_WARN:
            warn_flags.append("reviews_warn")

        if lat_p50 is not None and lat_p50 > _LATENCY_WARN_MS:
            warn_flags.append("latency_warn")

        if fb_overall > _FALLBACK_ALERT_OVERALL:
            warn_flags.append("fallback_alert")
        elif fb_overall > _FALLBACK_WARN_OVERALL:
            warn_flags.append("fallback_warn")

        if len(self._surfaced_families) < _FAMILY_HALT:
            warn_flags.append("family_coverage_critical")
        elif len(self._surfaced_families) < _FAMILY_WARN:
            warn_flags.append("family_coverage_warn")

        if self._operator_burden > _BURDEN_ALERT_DAYS:
            warn_flags.append("burden_alert")
        elif self._operator_burden > _BURDEN_WARN:
            warn_flags.append("burden_warn")

        if self._fetch_miss_count > 0:
            warn_flags.append(f"plumbing:fetch_miss={self._fetch_miss_count}")

        return CanarySnapshot(
            date_iso=date,
            reviews_per_day=rpd,
            sign_error_rate=self._sign_error_rate,
            missed_critical_rate=self._missed_critical_rate,
            latency_p50_ms=lat_p50,
            latency_p95_ms=lat_p95,
            fallback_rate_overall=fb_overall,
            fallback_rate_hot=fb_hot,
            family_coverage=len(self._surfaced_families),
            operator_burden=self._operator_burden,
            fetch_miss_count=self._fetch_miss_count,
            duplicate_count=self._duplicate_count,
            halt_triggered=bool(halt_reasons),
            halt_reasons=halt_reasons,
            warn_flags=warn_flags,
        )
