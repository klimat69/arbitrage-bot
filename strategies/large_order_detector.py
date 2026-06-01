"""
Large limit order detector with anti-spoofing (TTL filter).

Inspired by BTQuant order-book analysis: track large resting orders and only
emit signals when they persist longer than ORDER_TTL_SECONDS.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import os

from strategies.binance_futures_ws import stream_depth
from utils.logger import log_debug, log_info, log_warning


SignalCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class TrackedOrder:
    """Resting order tracked for TTL validation."""

    price: float
    amount: float
    side: str
    first_seen: float
    last_seen: float
    btc_volume: float


@dataclass
class LargeOrderDetector:
    """
    Detects large limit orders on Binance order book with anti-spoofing.

    Subscribes to incremental order book updates via ccxt.pro and validates
    that large orders remain visible for at least ORDER_TTL_SECONDS before
    emitting a signal.
    """

    symbol: str
    threshold_btc: float
    order_ttl_seconds: float
    on_valid_signal: SignalCallback
    signal_exchange: str = "binance"
    _tracked: dict[str, TrackedOrder] = field(default_factory=dict, init=False)
    _last_bids: dict[float, float] = field(default_factory=dict, init=False)
    _last_asks: dict[float, float] = field(default_factory=dict, init=False)
    _running: bool = field(default=False, init=False)

    @classmethod
    def from_env(
        cls,
        symbol: str,
        on_valid_signal: SignalCallback,
        signal_exchange: str = "binance",
    ) -> LargeOrderDetector:
        threshold = float(os.getenv("LARGE_ORDER_THRESHOLD_BTC", "5.0"))
        ttl = float(os.getenv("ORDER_TTL_SECONDS", "3.0"))
        return cls(
            symbol=symbol,
            threshold_btc=threshold,
            order_ttl_seconds=ttl,
            on_valid_signal=on_valid_signal,
            signal_exchange=signal_exchange,
        )

    def _order_key(self, side: str, price: float) -> str:
        return f"{side}:{price:.8f}"

    def _btc_volume(self, amount: float, price: float) -> float:
        base = self.symbol.split("/")[0].split(":")[0].upper()
        if base == "BTC":
            return amount
        if base == "ETH":
            return amount * (price / 100_000.0)
        return amount * price / 50_000.0

    def _parse_levels(self, levels: list[list[float]]) -> dict[float, float]:
        parsed: dict[float, float] = {}
        for level in levels or []:
            if len(level) < 2:
                continue
            price, amount = float(level[0]), float(level[1])
            if amount > 0:
                parsed[price] = amount
        return parsed

    def _detect_new_large_orders(
        self,
        side: str,
        current: dict[float, float],
        previous: dict[float, float],
        now: float,
    ) -> list[TrackedOrder]:
        large_orders: list[TrackedOrder] = []
        for price, amount in current.items():
            prev_amount = previous.get(price, 0.0)
            if amount <= prev_amount:
                continue
            btc_vol = self._btc_volume(amount, price)
            if btc_vol < self.threshold_btc:
                continue
            key = self._order_key(side, price)
            tracked = TrackedOrder(
                price=price,
                amount=amount,
                side=side,
                first_seen=now,
                last_seen=now,
                btc_volume=btc_vol,
            )
            self._tracked[key] = tracked
            log_debug(
                f"Tracking large {side} @ {price}: {amount} "
                f"(~{btc_vol:.2f} BTC equiv, threshold {self.threshold_btc})"
            )
            large_orders.append(tracked)
        return large_orders

    def _update_existing(self, side: str, current: dict[float, float], now: float) -> None:
        prefix = f"{side}:"
        for key, tracked in list(self._tracked.items()):
            if not key.startswith(prefix):
                continue
            amount = current.get(tracked.price, 0.0)
            if amount > 0:
                tracked.last_seen = now
                tracked.amount = amount
                tracked.btc_volume = self._btc_volume(amount, tracked.price)
            else:
                lifetime = now - tracked.first_seen
                if lifetime < self.order_ttl_seconds:
                    log_debug(
                        f"Spoofing filter: removed {side} @ {tracked.price} "
                        f"after {lifetime:.2f}s (< {self.order_ttl_seconds}s TTL)"
                    )
                del self._tracked[key]

    def _emit_mature_signals(self, now: float) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        for key, tracked in list(self._tracked.items()):
            lifetime = now - tracked.first_seen
            if lifetime < self.order_ttl_seconds:
                continue
            if tracked.btc_volume < self.threshold_btc:
                continue
            signal = {
                "exchange": self.signal_exchange,
                "symbol": self.symbol,
                "side": tracked.side,
                "price": tracked.price,
                "amount": tracked.amount,
                "btc_volume": tracked.btc_volume,
                "lifetime_seconds": lifetime,
                "timestamp": now,
            }
            signals.append(signal)
            log_info(
                f"Valid large order signal: {tracked.side.upper()} "
                f"{tracked.amount} @ {tracked.price} "
                f"(~{tracked.btc_volume:.2f} BTC, TTL {lifetime:.1f}s)"
            )
            del self._tracked[key]
        return signals

    async def process_orderbook(self, orderbook: dict[str, Any]) -> list[dict[str, Any]]:
        """Process one order book snapshot/update and return validated signals."""
        now = time.time()
        bids = self._parse_levels(orderbook.get("bids", []))
        asks = self._parse_levels(orderbook.get("asks", []))

        self._detect_new_large_orders("bid", bids, self._last_bids, now)
        self._detect_new_large_orders("ask", asks, self._last_asks, now)
        self._update_existing("bid", bids, now)
        self._update_existing("ask", asks, now)

        self._last_bids = bids
        self._last_asks = asks

        emitted: list[dict[str, Any]] = []
        for signal in self._emit_mature_signals(now):
            emitted.append(signal)
            await self.on_valid_signal(signal)
        return emitted

    async def watch_public_ws(self, timeout_at: float) -> None:
        """Watch Binance futures depth via public WebSocket (no API keys)."""
        self._running = True
        log_info(
            f"LargeOrderDetector watching {self.symbol} via Binance fstream "
            f"(threshold={self.threshold_btc} BTC, TTL={self.order_ttl_seconds}s)"
        )
        def _should_continue() -> bool:
            return self._running and time.time() <= timeout_at

        try:
            async for orderbook in stream_depth(should_continue=_should_continue):
                await self.process_orderbook(orderbook)
        except asyncio.CancelledError:
            raise
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False
