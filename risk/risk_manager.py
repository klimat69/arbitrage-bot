"""
Advanced risk management with position limits and circuit breaker.

Concepts adapted from Centralized-Arbitrage-bot: session PnL tracking,
consecutive loss limits, daily drawdown, and circuit breaker halt.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

from utils.logger import log_error, log_info, log_warning


class RiskManager:
    """
    In-memory risk controller for pre-trade checks and post-trade recording.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        config = config or {}
        self.enabled = config.get('enabled', True)
        self.max_position_usdt = float(
            config.get('max_position_usdt', os.getenv('MAX_POSITION_USDT', '500'))
        )
        self.max_daily_loss_usdt = float(
            config.get('max_daily_loss_usdt', os.getenv('MAX_DAILY_LOSS_USDT', '100'))
        )
        self.max_drawdown_pct = config.get('max_drawdown_pct', 5.0)
        self.max_loss_per_trade_usd = config.get('max_loss_per_trade_usd', 10.0)
        self.max_session_loss_pct = config.get('max_session_loss_pct', 3.0)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)
        self.max_slippage_pct = config.get('max_slippage_pct', 0.5)
        self.cooldown_after_loss_sec = config.get('cooldown_after_loss_sec', 30)
        self.circuit_breaker_losses = int(
            config.get('circuit_breaker_losses', os.getenv('CIRCUIT_BREAKER_LOSSES', '3'))
        )

        self._consecutive_losses = 0
        self._peak_profit_pct = 0.0
        self._total_profit_pct = 0.0
        self._session_pnl_usdt = 0.0
        self._daily_pnl_usdt = 0.0
        self._total_slippage_usd = 0.0
        self._trade_count = 0
        self._open_positions_usdt: dict[str, float] = {}
        self._stopped = False
        self._stop_reason: Optional[str] = None
        self._cooldown_until = 0.0
        self._circuit_breaker_active = False

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def stop_reason(self) -> Optional[str]:
        return self._stop_reason

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def peak_profit_pct(self) -> float:
        return self._peak_profit_pct

    @property
    def current_drawdown_pct(self) -> float:
        if self._peak_profit_pct <= 0:
            return abs(min(0, self._total_profit_pct))
        return self._peak_profit_pct - self._total_profit_pct

    def reset(self) -> None:
        self._consecutive_losses = 0
        self._peak_profit_pct = 0.0
        self._total_profit_pct = 0.0
        self._session_pnl_usdt = 0.0
        self._total_slippage_usd = 0.0
        self._trade_count = 0
        self._open_positions_usdt.clear()
        self._stopped = False
        self._stop_reason = None
        self._cooldown_until = 0.0
        self._circuit_breaker_active = False

    def can_open(
        self,
        symbol: str,
        proposed_usdt: float,
        current_time: float = 0,
    ) -> tuple[bool, Optional[str]]:
        """Check whether a new position may be opened."""
        if not self.enabled:
            return True, None

        if self._stopped or self._circuit_breaker_active:
            reason = self._stop_reason or "Circuit breaker active"
            return False, reason

        now = current_time or time.time()
        if now < self._cooldown_until:
            remaining = int(self._cooldown_until - now)
            return False, f"Đang trong cooldown, còn {remaining}s"

        if proposed_usdt > self.max_position_usdt:
            return False, (
                f"Position size {proposed_usdt:.2f} USDT exceeds limit "
                f"{self.max_position_usdt:.2f} USDT"
            )

        current_exposure = self._open_positions_usdt.get(symbol, 0.0)
        if current_exposure + proposed_usdt > self.max_position_usdt:
            return False, (
                f"Total exposure for {symbol} would exceed "
                f"{self.max_position_usdt:.2f} USDT"
            )

        if self._daily_pnl_usdt <= -self.max_daily_loss_usdt:
            self._trip_circuit_breaker(
                f"Daily loss {self._daily_pnl_usdt:.2f} USDT hit limit "
                f"{self.max_daily_loss_usdt:.2f} USDT"
            )
            return False, self._stop_reason

        if self._consecutive_losses >= self.max_consecutive_losses:
            self._trip_circuit_breaker(
                f"Đã lỗ liên tiếp {self._consecutive_losses} lần, "
                f"vượt giới hạn {self.max_consecutive_losses}"
            )
            return False, self._stop_reason

        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self._trip_circuit_breaker(
                f"Drawdown {self.current_drawdown_pct:.2f}% >= "
                f"{self.max_drawdown_pct:.2f}%"
            )
            return False, self._stop_reason

        return True, None

    def record_trade(self, pnl_usdt: float, symbol: Optional[str] = None) -> None:
        """Record realized PnL and update risk state."""
        self._trade_count += 1
        self._session_pnl_usdt += pnl_usdt
        self._daily_pnl_usdt += pnl_usdt

        if pnl_usdt < 0:
            self._consecutive_losses += 1
            if abs(pnl_usdt) > self.max_loss_per_trade_usd:
                self._cooldown_until = time.time() + self.cooldown_after_loss_sec
                log_warning(
                    f"Large loss {pnl_usdt:.2f} USDT — cooldown "
                    f"{self.cooldown_after_loss_sec}s"
                )
        else:
            self._consecutive_losses = 0

        if symbol and pnl_usdt != 0:
            self._open_positions_usdt[symbol] = max(
                0.0, self._open_positions_usdt.get(symbol, 0.0) + pnl_usdt
            )

        if self._consecutive_losses >= self.circuit_breaker_losses:
            self._trip_circuit_breaker(
                f"Đã lỗ liên tiếp {self._consecutive_losses} lần (circuit breaker)"
            )

        if self._daily_pnl_usdt <= -self.max_daily_loss_usdt:
            self._trip_circuit_breaker(
                f"Daily loss limit reached: {self._daily_pnl_usdt:.2f} USDT"
            )

        log_info(
            f"Trade recorded: PnL {pnl_usdt:+.4f} USDT | "
            f"session {self._session_pnl_usdt:+.4f} | "
            f"daily {self._daily_pnl_usdt:+.4f}"
        )

    def check_pre_trade(
        self,
        estimated_profit_usd: float,
        current_time: float = 0,
    ) -> tuple[bool, Optional[str]]:
        """Backward-compatible pre-trade check used by BaseBot."""
        return self.can_open(
            symbol='default',
            proposed_usdt=max(estimated_profit_usd, 1.0),
            current_time=current_time,
        )

    def check_post_trade(
        self,
        profit_usd: float,
        profit_pct: float,
        slippage_usd: float = 0,
        total_profit_pct: Optional[float] = None,
        current_time: float = 0,
    ) -> tuple[bool, Optional[str]]:
        """Backward-compatible post-trade check used by BaseBot."""
        if not self.enabled:
            return True, None

        self.record_trade(profit_usd)
        self._total_slippage_usd += abs(slippage_usd)

        if total_profit_pct is not None:
            self._total_profit_pct = total_profit_pct
        else:
            self._total_profit_pct += profit_pct

        if self._total_profit_pct > self._peak_profit_pct:
            self._peak_profit_pct = self._total_profit_pct

        if self._total_profit_pct < -self.max_session_loss_pct:
            self._stop(
                "session_loss",
                f"Lỗ phiên {self._total_profit_pct:.2f}% "
                f"vượt giới hạn {self.max_session_loss_pct:.2f}%",
            )
            return False, self._stop_reason

        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self._stop(
                "max_drawdown",
                f"Drawdown {self.current_drawdown_pct:.2f}% "
                f"vượt giới hạn {self.max_drawdown_pct:.2f}%",
            )
            return False, self._stop_reason

        if self._consecutive_losses >= self.max_consecutive_losses:
            self._stop(
                "consecutive_losses",
                f"Đã lỗ liên tiếp {self._consecutive_losses} lần, "
                f"vượt giới hạn {self.max_consecutive_losses}",
            )
            return False, self._stop_reason

        if self._stopped or self._circuit_breaker_active:
            return False, self._stop_reason

        return True, None

    def _trip_circuit_breaker(self, reason: str) -> None:
        self._circuit_breaker_active = True
        self._stopped = True
        self._stop_reason = reason
        log_error(f"CIRCUIT BREAKER: {reason}")

    def _stop(self, reason_code: str, reason_message: str) -> None:
        self._stopped = True
        self._stop_reason = reason_message
        log_error(f"RISK MANAGER - STOP: {reason_message}")

    def get_status(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'stopped': self._stopped,
            'circuit_breaker': self._circuit_breaker_active,
            'stop_reason': self._stop_reason,
            'trade_count': self._trade_count,
            'consecutive_losses': self._consecutive_losses,
            'session_pnl_usdt': self._session_pnl_usdt,
            'daily_pnl_usdt': self._daily_pnl_usdt,
            'total_profit_pct': self._total_profit_pct,
            'peak_profit_pct': self._peak_profit_pct,
            'current_drawdown_pct': self.current_drawdown_pct,
            'total_slippage_usd': self._total_slippage_usd,
            'limits': {
                'max_position_usdt': self.max_position_usdt,
                'max_daily_loss_usdt': self.max_daily_loss_usdt,
                'max_drawdown_pct': self.max_drawdown_pct,
                'max_loss_per_trade_usd': self.max_loss_per_trade_usd,
                'max_session_loss_pct': self.max_session_loss_pct,
                'max_consecutive_losses': self.max_consecutive_losses,
                'circuit_breaker_losses': self.circuit_breaker_losses,
            },
        }
