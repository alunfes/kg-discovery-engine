"""シグナルの JSONL 記録・読み込みを担う。

1 日 1 ファイル形式:
    crypto/artifacts/shadow/signals_YYYY-MM-DD.jsonl
    crypto/artifacts/shadow/pnl_YYYY-MM-DD.jsonl
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Iterator

from .types import ShadowSignal, VirtualTrade

_DEFAULT_ARTIFACT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "artifacts", "shadow"
)


def _make_signal_id(asset: str, timestamp_iso: str, event_type: str) -> str:
    """シグナル ID を決定論的に生成する（衝突回避のため内容ハッシュ使用）。

    Args:
        asset:         アセット名。
        timestamp_iso: ISO-8601 タイムスタンプ文字列。
        event_type:    StateEvent.event_type。

    Returns:
        16 文字の hex 文字列。
    """
    raw = f"{asset}|{timestamp_iso}|{event_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _today_iso() -> str:
    """UTC 今日の日付を YYYY-MM-DD 形式で返す。"""
    return time.strftime("%Y-%m-%d", time.gmtime())


class SignalLogger:
    """ShadowSignal / VirtualTrade を JSONL ファイルに追記するロガー。

    スレッドセーフではない（シングルスレッド前提）。
    ファイルは artifact_dir 配下に日次ローテーション。

    Args:
        artifact_dir: ログファイルの書き込みディレクトリ。
    """

    def __init__(self, artifact_dir: str = _DEFAULT_ARTIFACT_DIR) -> None:
        """SignalLogger を初期化する。"""
        self._dir = os.path.abspath(artifact_dir)
        os.makedirs(self._dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 書き込み
    # ------------------------------------------------------------------

    def log_signal(self, signal: ShadowSignal) -> None:
        """ShadowSignal を JSONL に追記する。

        Args:
            signal: 記録するシグナル。
        """
        path = os.path.join(self._dir, f"signals_{_today_iso()}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(signal.to_dict(), ensure_ascii=False) + "\n")

    def log_trade(self, trade: VirtualTrade) -> None:
        """VirtualTrade（P&L 確定後）を JSONL に追記する。

        Args:
            trade: 記録する仮想取引。
        """
        path = os.path.join(self._dir, f"pnl_{_today_iso()}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trade.to_dict(), ensure_ascii=False) + "\n")

    def log_regime_event(self, event: object) -> None:
        """non-tradable イベント（asset="multi" 等）を regime ログに退避する。

        P&L 評価対象外だが、regime shift 分析のために保存する。

        Args:
            event: StateEvent（型ヒントは循環 import 回避のため object）。
        """
        path = os.path.join(self._dir, f"regime_events_{_today_iso()}.jsonl")
        record = {
            "timestamp_ms": getattr(event, "timestamp_ms", 0),
            "asset": getattr(event, "asset", "unknown"),
            "event_type": getattr(event, "event_type", "unknown"),
            "severity": getattr(event, "severity", 0.0),
            "grammar_family": getattr(event, "grammar_family", "unknown"),
            "metadata": dict(getattr(event, "metadata", {})),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # 読み込み
    # ------------------------------------------------------------------

    def iter_signals(self, date_iso: str | None = None) -> Iterator[ShadowSignal]:
        """指定日（省略時は今日）のシグナルをイテレートする。

        Args:
            date_iso: "YYYY-MM-DD" 形式の日付。None の場合は今日。

        Yields:
            ShadowSignal レコード。
        """
        date = date_iso or _today_iso()
        path = os.path.join(self._dir, f"signals_{date}.jsonl")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield ShadowSignal.from_dict(json.loads(line))

    def iter_trades(self, date_iso: str | None = None) -> Iterator[VirtualTrade]:
        """指定日（省略時は今日）の仮想取引をイテレートする。

        Args:
            date_iso: "YYYY-MM-DD" 形式の日付。None の場合は今日。

        Yields:
            VirtualTrade レコード。
        """
        date = date_iso or _today_iso()
        path = os.path.join(self._dir, f"pnl_{date}.jsonl")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    yield VirtualTrade(**d)

    def available_dates(self) -> list[str]:
        """ログが存在する日付一覧を昇順で返す。

        Returns:
            "YYYY-MM-DD" 文字列のリスト。
        """
        dates: set[str] = set()
        for fname in os.listdir(self._dir):
            if fname.startswith("signals_") and fname.endswith(".jsonl"):
                dates.add(fname[len("signals_"):-len(".jsonl")])
        return sorted(dates)


def make_signal_id(asset: str, timestamp_iso: str, event_type: str) -> str:
    """モジュールレベルの signal_id 生成関数（テスト用に公開）。

    Args:
        asset:         アセット名。
        timestamp_iso: ISO-8601 タイムスタンプ文字列。
        event_type:    StateEvent.event_type。

    Returns:
        16 文字の hex 文字列。
    """
    return _make_signal_id(asset, timestamp_iso, event_type)
