"""Hyperliquid REST API からマーク価格を取得する。

既存の hyperliquid_connector.py の HTTP ロジックを再利用。
ディスクキャッシュ付きで replay モードでも決定論的に動作する。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

_HL_INFO_URL = "https://api.hyperliquid.xyz/info"
_CACHE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "artifacts", "shadow", "price_cache"
)
_REQUEST_TIMEOUT_S = 10


def _cache_path(asset: str, timestamp_iso: str) -> str:
    """キャッシュファイルのパスを返す。"""
    safe_ts = timestamp_iso.replace(":", "-")
    return os.path.join(_CACHE_DIR, f"{asset}_{safe_ts}.json")


def _fetch_mark_price_live(asset: str) -> Optional[float]:
    """Hyperliquid REST から現在のマーク価格を取得する。

    Args:
        asset: アセット名（例: "HYPE"）。

    Returns:
        マーク価格（USD）。取得失敗時は None。
    """
    payload = json.dumps({"type": "metaAndAssetCtxs"}).encode()
    req = urllib.request.Request(
        _HL_INFO_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
        # data = [meta, [assetCtx, ...]]
        meta = data[0]
        ctxs = data[1]
        universe = meta.get("universe", [])
        for i, info in enumerate(universe):
            if info.get("name") == asset and i < len(ctxs):
                return float(ctxs[i].get("markPx", 0.0))
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TypeError):
        pass
    return None


def _load_cached(path: str) -> Optional[float]:
    """キャッシュファイルから価格を読み込む。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return float(json.load(f)["price"])
    except (KeyError, ValueError, OSError):
        return None


def _save_cache(path: str, price: float) -> None:
    """価格をキャッシュファイルに保存する。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"price": price, "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f)


class PriceFetcher:
    """マーク価格を取得するクラス。キャッシュ済みなら再取得しない。

    Args:
        use_cache: True の場合、ディスクキャッシュを利用する（replay モード用）。
        cache_dir: キャッシュ保存先ディレクトリ。
    """

    def __init__(self, use_cache: bool = True, cache_dir: str = _CACHE_DIR) -> None:
        """PriceFetcher を初期化する。"""
        self._use_cache = use_cache
        self._cache_dir = cache_dir
        self._in_memory: dict[str, float] = {}

    def fetch(self, asset: str, timestamp_iso: str) -> Optional[float]:
        """指定アセットのマーク価格を返す。

        timestamp_iso はキャッシュキーとして使用。ライブモードでは
        「取得時点の現在価格」を返し、その結果をキャッシュする。

        Args:
            asset:         アセット名（例: "HYPE"）。
            timestamp_iso: 価格取得タイミングを示す ISO-8601 文字列（キャッシュキー）。

        Returns:
            マーク価格（USD）。取得失敗時は None。
        """
        cache_key = f"{asset}|{timestamp_iso}"
        if cache_key in self._in_memory:
            return self._in_memory[cache_key]

        if self._use_cache:
            path = _cache_path(asset, timestamp_iso)
            cached = _load_cached(path)
            if cached is not None:
                self._in_memory[cache_key] = cached
                return cached

        price = _fetch_mark_price_live(asset)
        if price is not None:
            self._in_memory[cache_key] = price
            if self._use_cache:
                _save_cache(_cache_path(asset, timestamp_iso), price)

        return price

    def fetch_now(self, asset: str) -> Optional[float]:
        """現在時刻のマーク価格を取得する（ライブ用ショートカット）。

        Args:
            asset: アセット名。

        Returns:
            マーク価格（USD）。取得失敗時は None。
        """
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return self.fetch(asset, now_iso)
