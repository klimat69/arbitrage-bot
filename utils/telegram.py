"""
Async Telegram notifications via aiohttp.

Inspired by FuturesArbitrageBot notification patterns.
"""
from __future__ import annotations

import os
from typing import Optional

import aiohttp

from utils.helpers import format_message
from utils.logger import log_error, log_warning


class TelegramNotifier:
    """Send Telegram alerts for signals, trades, and errors."""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.token = token or os.getenv('TELEGRAM_API_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        env_enabled = os.getenv('ENABLE_TELEGRAM', 'false').lower() == 'true'
        self.enabled = env_enabled if enabled is None else enabled

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        if not self.enabled or not self.is_configured:
            return False

        url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': format_message(text),
            'parse_mode': parse_mode,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log_warning(f"Telegram API {resp.status}: {body[:200]}")
                        return False
                    return True
        except aiohttp.ClientError as exc:
            log_error(f"Telegram send failed: {exc}")
            return False

    async def notify_signal(self, exchange: str, side: str, price: float, amount: float, btc_volume: float) -> bool:
        return await self.send_message(
            f"🔔 <b>Large order signal</b> ({exchange})\n"
            f"Side: {side.upper()}\n"
            f"Price: {price}\n"
            f"Amount: {amount:.6f}\n"
            f"BTC equiv: ~{btc_volume:.2f}"
        )

    async def notify_position_opened(self, exchange: str, side: str, symbol: str, amount: float, order_id: str) -> bool:
        return await self.send_message(
            f"✅ <b>Position opened</b> on {exchange}\n"
            f"{side.upper()} {amount:.6f} {symbol}\n"
            f"Order: {order_id}"
        )

    async def notify_position_closed(self, exchange: str, symbol: str, reason: str, pnl_usdt: float) -> bool:
        emoji = '🟢' if pnl_usdt >= 0 else '🔴'
        return await self.send_message(
            f"{emoji} <b>Position closed</b> ({reason})\n"
            f"{symbol} on {exchange}\n"
            f"PnL: {pnl_usdt:+.4f} USDT"
        )

    async def notify_critical_error(self, context: str, error: str) -> bool:
        return await self.send_message(
            f"🚨 <b>Critical error</b>\n"
            f"Context: {context}\n"
            f"Error: {error}"
        )
