"""
Classic bot: Binance futures order-book signals → MEXC futures execution.
"""
import time
import asyncio
import traceback

from typing import Any, Optional

from utils.logger import log_info, log_error, log_warning, log_debug
from utils.exceptions import InsufficientBalanceError, OrderError
from bots.base_bot import BaseBot
from configs import (
    EXCHANGE_FEES,
    RISK_CONFIG,
    SIGNAL_EXCHANGE,
    EXECUTION_EXCHANGE,
    FUTURES_SYMBOL,
)
from strategies.large_order_detector import LargeOrderDetector


class ClassicBot(BaseBot):
    """Binance fstream signals → MEXC swap execution (BTC/USDT perpetual)."""

    def __init__(
        self,
        exchange_service: Any,
        balance_service: Any,
        order_service: Any,
        notification_service: Any,
        db_service: Any = None,
        risk_config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            exchange_service,
            balance_service,
            order_service,
            notification_service,
            {'fees': EXCHANGE_FEES},
            db_service,
            risk_config or RISK_CONFIG,
        )
        self.retry_count = 0
        self.max_retries = 3
        self.error_counts = {'balance': 0, 'order': 0, 'network': 0, 'other': 0}
        self.stats = {
            'opportunities_found': 0,
            'trades_executed': 0,
            'failed_trades': 0,
            'total_volume': 0,
        }
        self.signal_exchange = SIGNAL_EXCHANGE
        self.execution_exchange = EXECUTION_EXCHANGE
        self.large_order_detector: Optional[LargeOrderDetector] = None
        self._signal_cooldown_until = 0.0

    def configure(
        self,
        symbol: str,
        exchanges: list[str],
        timeout: int,
        amount_usd: float,
        indicatif: Optional[str] = None,
    ) -> None:
        """Configure session; force futures symbol for this pipeline."""
        futures_symbol = symbol if ':' in symbol else FUTURES_SYMBOL
        super().configure(futures_symbol, exchanges, timeout, amount_usd, indicatif or futures_symbol)
        log_info(
            f'Futures pipeline: {self.signal_exchange} (public WS) → '
            f'{self.execution_exchange} ({futures_symbol})'
        )

    async def start(self) -> float:
        """Start futures signal session (MEXC balance only, no Binance orders)."""
        try:
            log_info(
                f'Starting futures session: {self.symbol}, '
                f'{self.howmuchusd} USDT, execution={self.execution_exchange}'
            )
            self.start_time = time.time()
            exec_ex = self.execution_exchange

            try:
                self.session_id = self.db.create_session(
                    'classic', self.symbol, self.exchanges,
                    self.howmuchusd, int(self.timeout - time.time()) // 60,
                )
            except Exception as e:
                log_error(f'Database session error: {e}')

            try:
                await self.balance_service.check_balances(
                    [exec_ex],
                    'USDT',
                    self.howmuchusd,
                    self.notification_service,
                )
            except InsufficientBalanceError as e:
                log_error(f'Insufficient MEXC balance: {e}')
                self.error_counts['balance'] += 1
                return 0

            average_price = await self._resolve_reference_price(exec_ex)
            if average_price <= 0:
                log_error('Could not resolve BTC reference price')
                return 0

            total_crypto = self.howmuchusd / average_price
            self.crypto_per_transaction = total_crypto * 0.99
            log_info(
                f'Position size ~{self.crypto_per_transaction:.6f} BTC '
                f'@ ref {average_price:.2f}'
            )

            self.usd = {exec_ex: self.howmuchusd}
            self.crypto = {exec_ex: 0.0}

            await self._start_signal_detector_loop()
            self._display_stats()
            return await self.stop()

        except Exception as e:
            log_error(f'Bot error: {e}')
            log_debug(traceback.format_exc())
            if self.session_id:
                try:
                    self.db.record_error(
                        'bot_crash', str(e),
                        session_id=self.session_id,
                        details=traceback.format_exc(),
                    )
                    self.db.update_session(self.session_id, status='error', error_message=str(e))
                except Exception:
                    pass
            return 0

    async def _resolve_reference_price(self, exchange_id: str) -> float:
        try:
            ticker = await self.exchange_service.get_ticker(exchange_id, self.symbol)
            return (float(ticker['bid']) + float(ticker['ask'])) / 2
        except Exception as e:
            log_warning(f'MEXC ticker failed: {e}; using fallback 50000')
            return 50_000.0

    async def _start_signal_detector_loop(self) -> float:
        try:
            self.large_order_detector = LargeOrderDetector.from_env(
                symbol=self.symbol,
                on_valid_signal=self._on_large_order_signal,
                signal_exchange=self.signal_exchange,
            )
            log_info(
                f'Watching Binance fstream → executing on {self.execution_exchange}'
            )
            await self.large_order_detector.watch_public_ws(self.timeout)
            return self.total_absolute_profit_pct
        except Exception as e:
            log_error(f'Signal detector error: {e}')
            log_debug(traceback.format_exc())
            raise
        finally:
            if self.large_order_detector:
                self.large_order_detector.stop()

    async def _on_large_order_signal(self, signal: dict[str, Any]) -> None:
        now = time.time()
        if now < self._signal_cooldown_until:
            return

        notifier = getattr(self, 'telegram_notifier', None)
        self.stats['opportunities_found'] += 1
        side = signal['side']
        price = signal['price']
        amount = min(signal['amount'], self.crypto_per_transaction or 0.001)
        proposed_usdt = amount * price

        allowed, reason = self.risk_manager.can_open(
            self.symbol, proposed_usdt, current_time=now,
        )
        if not allowed:
            log_warning(f'Risk manager blocked: {reason}')
            return

        if self.notification_service:
            self.notification_service.send_message(
                f'Large order signal ({self.signal_exchange})\n'
                f'{side.upper()} {amount:.6f} @ {price}\n'
                f'BTC equiv: ~{signal["btc_volume"]:.2f}'
            )
        if notifier:
            await notifier.notify_signal(
                self.signal_exchange, side, price, amount, signal['btc_volume'],
            )

        try:
            execution_ex = self.execution_exchange
            if side == 'bid':
                log_info(f'MEXC futures BUY {amount} @ {price}')
                order = await self.exchange_service.async_create_limit_buy_order(
                    execution_ex, self.symbol, amount, price,
                )
            else:
                log_info(f'MEXC futures SELL {amount} @ {price}')
                order = await self.exchange_service.async_create_limit_sell_order(
                    execution_ex, self.symbol, amount, price,
                )

            estimated_pnl = amount * price * 0.001
            self.risk_manager.record_trade(estimated_pnl)
            self.stats['trades_executed'] += 1
            self.stats['total_volume'] += proposed_usdt
            self._signal_cooldown_until = now + 5

            if self.notification_service:
                self.notification_service.send_message(
                    f'Position opened on {execution_ex}\n'
                    f'{side.upper()} {amount:.6f} {self.symbol}\n'
                    f'Order: {order.get("id", "n/a")}'
                )
            if notifier:
                await notifier.notify_position_opened(
                    execution_ex, side, self.symbol, amount, str(order.get('id', 'n/a')),
                )
        except Exception as exc:
            self.stats['failed_trades'] += 1
            self.risk_manager.record_trade(-proposed_usdt * 0.001)
            log_error(f'MEXC execution failed: {exc}')
            if self.notification_service:
                self.notification_service.send_message(f'Execution failed: {exc}')
            if notifier:
                await notifier.notify_critical_error('MEXC execution', str(exc))

    def _display_stats(self) -> None:
        elapsed_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self.start_time))
        log_info('\n' + '=' * 50)
        log_info(f'SESSION STATS - {self.symbol}')
        log_info('=' * 50)
        log_info(f'Runtime: {elapsed_time}')
        log_info(f'Signals: {self.stats["opportunities_found"]}')
        log_info(f'Trades OK: {self.stats["trades_executed"]}')
        log_info(f'Trades failed: {self.stats["failed_trades"]}')
        log_info(f'Volume: {self.stats["total_volume"]:.4f} USDT')
        log_info('=' * 50 + '\n')

    async def stop(self) -> float:
        """End session; futures cleanup is position-specific (no spot emergency sell)."""
        if self.session_id:
            try:
                total_profit_usd = (self.total_absolute_profit_pct / 100) * self.howmuchusd
                self.db.end_session(
                    self.session_id,
                    total_profit_pct=self.total_absolute_profit_pct,
                    total_profit_usd=total_profit_usd,
                    total_fees_usd=self.total_fees_usd,
                    opportunities_found=self.stats['opportunities_found'],
                    trades_executed=self.stats['trades_executed'],
                    trades_failed=self.stats['failed_trades'],
                    total_volume_usd=self.stats['total_volume'],
                    status='completed',
                )
            except Exception as e:
                log_error(f'End session error: {e}')

        message = (
            f'Session ended ({self.symbol}).\n'
            f'Profit: {self.total_absolute_profit_pct:.4f}%'
        )
        log_info(message)
        if self.notification_service:
            self.notification_service.send_message(message)
        return self.total_absolute_profit_pct
