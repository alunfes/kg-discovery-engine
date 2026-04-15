"""Hyperliquid WebSocket ingestion — live and replay modes.

Live mode: connects to wss://api.hyperliquid.xyz/ws and subscribes to
  trades and l2Book channels for configured assets.

Replay mode (live=False): generates deterministic synthetic WebSocket-style
  events from a seeded RNG.  Safe for offline testing and CI.

Why stdlib-only WebSocket:
  Project prohibits external dependencies.  The WebSocket handshake (RFC 6455)
  and frame encoding/decoding are implemented using only asyncio, ssl, struct,
  hashlib, base64, os, and json.

Reconnect/heartbeat policy:
  - Reconnect on any error after RECONNECT_DELAY_S seconds (live mode only).
  - Send ping frame every HEARTBEAT_INTERVAL_S; raise ConnectionError on timeout.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import random
import ssl
import struct
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

HL_WS_HOST = "api.hyperliquid.xyz"
HL_WS_PATH = "/ws"
HL_WS_PORT = 443
HL_WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

RECONNECT_DELAY_S = 5.0
HEARTBEAT_INTERVAL_S = 30.0
CONNECT_TIMEOUT_S = 10.0
MAX_FRAME_BYTES = 1_048_576  # 1 MB safety cap

DEFAULT_ASSETS = ["HYPE", "BTC", "ETH", "SOL"]

# Base prices for replay mode synthetic data
_REPLAY_BASE_PRICES: dict[str, float] = {
    "HYPE": 40.0,
    "BTC": 70000.0,
    "ETH": 2300.0,
    "SOL": 80.0,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WSTradeEvent:
    """A single trade received from the WebSocket trades channel."""

    asset: str
    side: str         # "B" = buy aggressor, "A" = ask/sell aggressor
    price: float
    size: float
    timestamp_ms: int

    @property
    def is_buy(self) -> bool:
        """True when the aggressor side was a buyer."""
        return self.side == "B"


@dataclass
class WSBookEvent:
    """An order book update received from the l2Book channel."""

    asset: str
    timestamp_ms: int
    bids: list        # list of (price, size) tuples, best bid first
    asks: list        # list of (price, size) tuples, best ask first


@dataclass
class WSMessage:
    """A parsed Hyperliquid WebSocket message.

    Exactly one of ``trades`` or ``book`` will be populated depending on
    the ``channel`` value.
    """

    channel: str                                           # "trades" | "l2Book"
    asset: Optional[str]
    trades: list[WSTradeEvent] = field(default_factory=list)
    book: Optional[WSBookEvent] = None


# ---------------------------------------------------------------------------
# WebSocket handshake helpers
# ---------------------------------------------------------------------------

def _make_ws_key() -> str:
    """Generate a random base64-encoded WebSocket key (Sec-WebSocket-Key).

    Returns the key string to send in the HTTP upgrade request.
    """
    return base64.b64encode(os.urandom(16)).decode()


async def _ws_handshake(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    path: str,
) -> None:
    """Send WebSocket upgrade request and validate the 101 response.

    Raises:
        ConnectionError: if the server does not return HTTP 101.
    """
    key = _make_ws_key()
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    writer.write(request.encode())
    await writer.drain()
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=CONNECT_TIMEOUT_S)
        if not chunk:
            raise ConnectionError("Connection closed during WS handshake")
        response += chunk
    if b"101" not in response:
        raise ConnectionError(f"WS upgrade failed (no 101): {response[:100]!r}")


# ---------------------------------------------------------------------------
# Frame I/O
# ---------------------------------------------------------------------------

async def _read_frame(
    reader: asyncio.StreamReader,
) -> tuple[int, bytes]:
    """Read one complete WebSocket frame from ``reader``.

    Returns:
        (opcode, payload) where opcode follows RFC 6455:
        1=text, 2=binary, 8=close, 9=ping, 10=pong.

    Raises:
        ValueError: if the frame payload exceeds MAX_FRAME_BYTES.
    """
    header = await reader.readexactly(2)
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", await reader.readexactly(8))[0]
    if length > MAX_FRAME_BYTES:
        raise ValueError(f"WS frame too large: {length} bytes")
    mask = await reader.readexactly(4) if masked else b""
    payload = await reader.readexactly(length)
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


async def _write_frame(
    writer: asyncio.StreamWriter,
    data: bytes,
    opcode: int = 1,
) -> None:
    """Write a masked client WebSocket frame.

    RFC 6455 §5.3: all client-to-server frames MUST be masked.
    """
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
    length = len(data)
    if length < 126:
        header = bytes([0x80 | opcode, 0x80 | length]) + mask_key
    elif length < 65536:
        header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", length) + mask_key
    else:
        header = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", length) + mask_key
    writer.write(header + masked)
    await writer.drain()


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------

def _parse_trades(data: list) -> tuple[Optional[str], list[WSTradeEvent]]:
    """Parse a trades channel data array into WSTradeEvent list.

    Returns (asset, trades).  Silently skips malformed records.
    """
    trades: list[WSTradeEvent] = []
    for t in data:
        try:
            trades.append(WSTradeEvent(
                asset=t["coin"],
                side=t["side"],
                price=float(t["px"]),
                size=float(t["sz"]),
                timestamp_ms=int(t["time"]),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    asset = trades[0].asset if trades else None
    return asset, trades


def _parse_book(data: dict) -> WSBookEvent:
    """Parse an l2Book channel data dict into a WSBookEvent.

    Takes the top 5 levels on each side.
    """
    coin = data.get("coin", "")
    ts = int(data.get("time", int(time.time() * 1000)))
    levels = data.get("levels", [[], []])
    bids = [
        (float(b["px"]), float(b["sz"]))
        for b in levels[0][:5]
        if isinstance(b, dict) and "px" in b and "sz" in b
    ]
    asks = [
        (float(a["px"]), float(a["sz"]))
        for a in levels[1][:5]
        if isinstance(a, dict) and "px" in a and "sz" in a
    ]
    return WSBookEvent(asset=coin, timestamp_ms=ts, bids=bids, asks=asks)


def parse_ws_message(raw: bytes) -> Optional[WSMessage]:
    """Parse a raw WebSocket text frame payload into a WSMessage.

    Returns None for subscription confirmations and unrecognised channels.
    """
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    channel = obj.get("channel", "")
    data = obj.get("data")
    if channel == "trades" and isinstance(data, list):
        asset, trades = _parse_trades(data)
        return WSMessage(channel=channel, asset=asset, trades=trades)
    if channel == "l2Book" and isinstance(data, dict):
        book = _parse_book(data)
        return WSMessage(channel=channel, asset=book.asset, book=book)
    return None


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------

def build_replay_messages(
    assets: list[str],
    n_minutes: int,
    seed: int,
    burst_asset: Optional[str] = None,
    burst_at_min: Optional[int] = None,
) -> list[WSMessage]:
    """Build a deterministic WSMessage stream simulating n_minutes of data.

    One trade event per 10-second interval per asset, plus book updates every
    30 seconds.  Optionally injects a buy-aggression burst for testing.

    Args:
        assets:       Asset symbols to generate events for.
        n_minutes:    Duration of replay window.
        seed:         RNG seed for determinism.
        burst_asset:  If given, inject a burst at burst_at_min.
        burst_at_min: Minute offset at which to inject the burst.

    Returns:
        Ordered list of WSMessage objects.
    """
    rng = random.Random(seed)
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - n_minutes * 60_000
    messages: list[WSMessage] = []
    step_ms = 10_000

    for t_ms in range(start_ms, now_ms, step_ms):
        min_offset = (t_ms - start_ms) // 60_000
        for asset in assets:
            base = _REPLAY_BASE_PRICES.get(asset, 100.0)
            price = base * (1 + rng.gauss(0, 0.001))
            n_trades = 1
            # Inject burst: 15 trades in 10s instead of 1
            if asset == burst_asset and burst_at_min is not None:
                if abs(min_offset - burst_at_min) < 2:
                    n_trades = 15
            for _ in range(n_trades):
                side = "B" if rng.random() > 0.45 else "A"
                size = round(rng.uniform(1.0, 30.0), 2)
                trade = WSTradeEvent(
                    asset=asset, side=side,
                    price=round(price, 4), size=size,
                    timestamp_ms=t_ms,
                )
                messages.append(WSMessage(channel="trades", asset=asset, trades=[trade]))
        # Book update every 30 seconds
        if (t_ms - start_ms) % 30_000 == 0:
            for asset in assets:
                base = _REPLAY_BASE_PRICES.get(asset, 100.0)
                mid = base * (1 + rng.gauss(0, 0.001))
                spread_half = base * 0.0003
                bids = [(round(mid - spread_half * i, 4), round(rng.uniform(5, 80), 2)) for i in range(1, 4)]
                asks = [(round(mid + spread_half * i, 4), round(rng.uniform(5, 80), 2)) for i in range(1, 4)]
                book = WSBookEvent(asset=asset, timestamp_ms=t_ms, bids=bids, asks=asks)
                messages.append(WSMessage(channel="l2Book", asset=asset, book=book))
    return messages


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class HyperliquidWSClient:
    """WebSocket client for Hyperliquid live market data.

    Two modes:

    Live (``live=True``):
      Connects to ``wss://api.hyperliquid.xyz/ws``, subscribes to trades
      and l2Book channels, and yields WSMessage objects indefinitely with
      automatic reconnection on error.

    Replay (``live=False``):
      Yields deterministic WSMessage objects built from a seeded RNG.
      All messages are emitted without I/O — safe for offline tests and CI.

    Usage::

        client = HyperliquidWSClient(assets=["HYPE"], live=False, seed=42)
        async for msg in client.messages():
            handle(msg)
    """

    def __init__(
        self,
        assets: Optional[list[str]] = None,
        live: bool = True,
        seed: int = 42,
        replay_n_minutes: int = 60,
        max_replay_messages: Optional[int] = None,
    ) -> None:
        """Initialise the WebSocket client.

        Args:
            assets:               Asset symbols to subscribe/replay.
            live:                 True = live WS; False = replay mode.
            seed:                 RNG seed for replay determinism.
            replay_n_minutes:     Simulated window length in replay mode.
            max_replay_messages:  Cap replay length (None = unlimited).
        """
        self.assets = assets or DEFAULT_ASSETS
        self.live = live
        self.seed = seed
        self.replay_n_minutes = replay_n_minutes
        self.max_replay_messages = max_replay_messages
        self._stop = False

    def stop(self) -> None:
        """Signal the client to stop yielding messages after the current one."""
        self._stop = True

    async def messages(self) -> AsyncIterator[WSMessage]:
        """Async generator yielding parsed WSMessage objects.

        Live mode: reconnects automatically on error.
        Replay mode: yields all replay messages then stops.
        """
        if not self.live:
            async for msg in self._replay():
                yield msg
            return
        while not self._stop:
            try:
                async for msg in self._live():
                    if self._stop:
                        return
                    yield msg
            except (ConnectionError, OSError, asyncio.TimeoutError, EOFError) as exc:
                import sys
                print(f"[hyperliquid_ws] reconnect after: {exc}", file=sys.stderr)
                await asyncio.sleep(RECONNECT_DELAY_S)

    async def _replay(self) -> AsyncIterator[WSMessage]:
        """Yield deterministic replay messages."""
        msgs = build_replay_messages(self.assets, self.replay_n_minutes, self.seed)
        if self.max_replay_messages is not None:
            msgs = msgs[: self.max_replay_messages]
        for msg in msgs:
            if self._stop:
                return
            yield msg

    async def _live(self) -> AsyncIterator[WSMessage]:
        """Open one live WebSocket session and yield messages until error."""
        ssl_ctx = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(HL_WS_HOST, HL_WS_PORT, ssl=ssl_ctx),
            timeout=CONNECT_TIMEOUT_S,
        )
        try:
            await _ws_handshake(reader, writer, HL_WS_HOST, HL_WS_PATH)
            await self._subscribe_all(writer)
            async for msg in self._recv_loop(reader, writer):
                yield msg
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _subscribe_all(self, writer: asyncio.StreamWriter) -> None:
        """Send subscription requests for all assets and channels."""
        for asset in self.assets:
            for sub_type in ("trades", "l2Book"):
                payload = json.dumps({
                    "method": "subscribe",
                    "subscription": {"type": sub_type, "coin": asset},
                }).encode()
                await _write_frame(writer, payload)
                await asyncio.sleep(0.05)

    async def _recv_loop(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> AsyncIterator[WSMessage]:
        """Read frames, handle control frames, yield parsed data messages."""
        last_ping = time.monotonic()
        while not self._stop:
            if time.monotonic() - last_ping > HEARTBEAT_INTERVAL_S:
                await _write_frame(writer, b"", opcode=9)
                last_ping = time.monotonic()
            timeout = HEARTBEAT_INTERVAL_S + 5.0
            try:
                opcode, payload = await asyncio.wait_for(
                    _read_frame(reader), timeout=timeout
                )
            except asyncio.TimeoutError:
                raise ConnectionError("WS heartbeat timeout")
            if opcode == 8:
                break
            if opcode == 9:
                await _write_frame(writer, payload, opcode=10)
                continue
            if opcode in (1, 2):
                msg = parse_ws_message(payload)
                if msg is not None:
                    yield msg
