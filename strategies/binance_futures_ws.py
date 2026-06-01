"""Public Binance USDT-M futures depth stream (no API keys)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Callable, Optional

import websockets

from configs import BINANCE_WS_URL
from utils.logger import log_info, log_warning


def parse_depth_message(raw: dict[str, Any]) -> dict[str, list[list[float]]] | None:
    """Convert Binance partial depth payload to orderbook dict."""
    bids_raw = raw.get('b') or raw.get('bids') or []
    asks_raw = raw.get('a') or raw.get('asks') or []
    if not bids_raw and not asks_raw:
        return None
    bids = [[float(p), float(q)] for p, q in bids_raw if float(q) > 0]
    asks = [[float(p), float(q)] for p, q in asks_raw if float(q) > 0]
    return {'bids': bids, 'asks': asks}


async def stream_depth(
    ws_url: str = BINANCE_WS_URL,
    reconnect_delay: float = 2.0,
    should_continue: Optional[Callable[[], bool]] = None,
) -> AsyncIterator[dict[str, list[list[float]]]]:
    """
    Yield order book snapshots from Binance fstream depth stream.

    Reconnects automatically on connection errors.
    """
    delay = reconnect_delay
    while should_continue is None or should_continue():
        try:
            log_info(f'Connecting to Binance futures WS: {ws_url}')
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
            ) as ws:
                delay = reconnect_delay
                async for message in ws:
                    if should_continue is not None and not should_continue():
                        return
                    data = json.loads(message)
                    book = parse_depth_message(data)
                    if book:
                        yield book
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_warning(f'Binance WS disconnected: {exc}; retry in {delay}s')
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)
