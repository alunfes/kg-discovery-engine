"""Shadow Trading フレームワーク — Phase 1.

シグナル記録・仮想 P&L 計算・canary 指標監視を提供する。
外部依存なし（Python 標準ライブラリのみ）。
"""
from .types import ShadowSignal, VirtualTrade, PnLResult, CanarySnapshot
from .signal_logger import SignalLogger
from .price_fetcher import PriceFetcher
from .pnl_calculator import compute_pnl, batch_compute_pnl
from .canary_monitor import CanaryMonitor

__all__ = [
    "ShadowSignal",
    "VirtualTrade",
    "PnLResult",
    "CanarySnapshot",
    "SignalLogger",
    "PriceFetcher",
    "compute_pnl",
    "batch_compute_pnl",
    "CanaryMonitor",
]
