"""
Service quản lý rủi ro cho bot giao dịch.
Bao gồm: max drawdown, stop-loss, circuit breaker, giới hạn lỗ liên tiếp.
"""
from typing import Any, Optional
from utils.logger import log_info, log_warning, log_error


class RiskManager:
    """
    Quản lý rủi ro giao dịch với nhiều lớp bảo vệ.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        Khởi tạo RiskManager với cấu hình.

        Args:
            config (dict, optional): Cấu hình rủi ro, bao gồm:
                - max_drawdown_pct (float): Drawdown tối đa cho phép (%)
                - max_loss_per_trade_usd (float): Lỗ tối đa mỗi giao dịch (USD)
                - max_session_loss_pct (float): Lỗ tối đa trong phiên (%)
                - max_consecutive_losses (int): Số lần lỗ liên tiếp tối đa
                - max_slippage_pct (float): Slippage tối đa cho phép (%)
                - cooldown_after_loss_sec (int): Thời gian chờ sau lỗ (giây)
                - enabled (bool): Bật/tắt risk management
        """
        config = config or {}
        self.enabled = config.get('enabled', True)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 5.0)
        self.max_loss_per_trade_usd = config.get('max_loss_per_trade_usd', 10.0)
        self.max_session_loss_pct = config.get('max_session_loss_pct', 3.0)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)
        self.max_slippage_pct = config.get('max_slippage_pct', 0.5)
        self.cooldown_after_loss_sec = config.get('cooldown_after_loss_sec', 30)

        # State tracking
        self._consecutive_losses = 0
        self._peak_profit_pct = 0.0
        self._total_profit_pct = 0.0
        self._total_slippage_usd = 0.0
        self._trade_count = 0
        self._stopped = False
        self._stop_reason = None
        self._cooldown_until = 0  # timestamp

    @property
    def is_stopped(self) -> bool:
        """Kiểm tra risk manager đã dừng bot chưa."""
        return self._stopped

    @property
    def stop_reason(self) -> Optional[str]:
        """Lý do dừng bot."""
        return self._stop_reason

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def peak_profit_pct(self) -> float:
        return self._peak_profit_pct

    @property
    def current_drawdown_pct(self) -> float:
        """Drawdown hiện tại so với đỉnh lợi nhuận."""
        if self._peak_profit_pct <= 0:
            return abs(min(0, self._total_profit_pct))
        return self._peak_profit_pct - self._total_profit_pct

    def reset(self) -> None:
        """Reset trạng thái cho phiên mới."""
        self._consecutive_losses = 0
        self._peak_profit_pct = 0.0
        self._total_profit_pct = 0.0
        self._total_slippage_usd = 0.0
        self._trade_count = 0
        self._stopped = False
        self._stop_reason = None
        self._cooldown_until = 0

    def check_pre_trade(self, estimated_profit_usd: float, current_time: float = 0) -> tuple[bool, Optional[str]]:
        """
        Kiểm tra trước khi thực hiện giao dịch.

        Args:
            estimated_profit_usd (float): Lợi nhuận ước tính (USD)
            current_time (float): Timestamp hiện tại (cho cooldown check)

        Returns:
            tuple: (allowed: bool, reason: str|None)
        """
        if not self.enabled:
            return True, None

        if self._stopped:
            return False, f"Bot đã dừng: {self._stop_reason}"

        # Kiểm tra cooldown
        if current_time > 0 and current_time < self._cooldown_until:
            remaining = int(self._cooldown_until - current_time)
            return False, f"Đang trong cooldown, còn {remaining}s"

        # Kiểm tra max drawdown
        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self._stop("max_drawdown",
                       f"Drawdown {self.current_drawdown_pct:.2f}% "
                       f"vượt giới hạn {self.max_drawdown_pct:.2f}%")
            return False, self._stop_reason

        # Kiểm tra consecutive losses
        if self._consecutive_losses >= self.max_consecutive_losses:
            self._stop("consecutive_losses",
                       f"Đã lỗ liên tiếp {self._consecutive_losses} lần, "
                       f"vượt giới hạn {self.max_consecutive_losses}")
            return False, self._stop_reason

        return True, None

    def check_post_trade(self, profit_usd: float, profit_pct: float, slippage_usd: float = 0,
                         total_profit_pct: Optional[float] = None, current_time: float = 0) -> tuple[bool, Optional[str]]:
        """
        Kiểm tra sau giao dịch và cập nhật state.

        Args:
            profit_usd (float): Lợi nhuận giao dịch vừa rồi (USD)
            profit_pct (float): Lợi nhuận giao dịch vừa rồi (%)
            slippage_usd (float): Slippage giao dịch vừa rồi (USD)
            total_profit_pct (float, optional): Tổng lợi nhuận phiên (%)
            current_time (float): Timestamp hiện tại

        Returns:
            tuple: (should_continue: bool, reason: str|None)
        """
        if not self.enabled:
            return True, None

        self._trade_count += 1
        self._total_slippage_usd += abs(slippage_usd)

        # Cập nhật total profit
        if total_profit_pct is not None:
            self._total_profit_pct = total_profit_pct
        else:
            self._total_profit_pct += profit_pct

        # Cập nhật peak profit
        if self._total_profit_pct > self._peak_profit_pct:
            self._peak_profit_pct = self._total_profit_pct

        # Cập nhật consecutive losses
        if profit_usd < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Kiểm tra per-trade loss
        if profit_usd < -self.max_loss_per_trade_usd:
            log_warning(
                f"Lỗ giao dịch {profit_usd:.4f} USD vượt giới hạn "
                f"{self.max_loss_per_trade_usd:.4f} USD"
            )
            if current_time > 0:
                self._cooldown_until = current_time + self.cooldown_after_loss_sec
                log_warning(f"Kích hoạt cooldown {self.cooldown_after_loss_sec}s")

        # Kiểm tra session loss
        if self._total_profit_pct < -self.max_session_loss_pct:
            self._stop("session_loss",
                       f"Lỗ phiên {self._total_profit_pct:.2f}% "
                       f"vượt giới hạn {self.max_session_loss_pct:.2f}%")
            return False, self._stop_reason

        # Kiểm tra drawdown
        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self._stop("max_drawdown",
                       f"Drawdown {self.current_drawdown_pct:.2f}% "
                       f"vượt giới hạn {self.max_drawdown_pct:.2f}%")
            return False, self._stop_reason

        # Kiểm tra consecutive losses
        if self._consecutive_losses >= self.max_consecutive_losses:
            self._stop("consecutive_losses",
                       f"Đã lỗ liên tiếp {self._consecutive_losses} lần, "
                       f"vượt giới hạn {self.max_consecutive_losses}")
            return False, self._stop_reason

        # Kiểm tra slippage quá cao
        if abs(slippage_usd) > 0 and self._trade_count > 0:
            avg_slippage = self._total_slippage_usd / self._trade_count
            # Chuyển avg_slippage thành % của profit
            if abs(profit_usd) > 0:
                slippage_ratio = (abs(slippage_usd) / abs(profit_usd)) * 100
                if slippage_ratio > self.max_slippage_pct * 100:
                    log_warning(
                        f"Slippage cao: {slippage_ratio:.2f}% so với lợi nhuận "
                        f"(giới hạn {self.max_slippage_pct * 100:.2f}%)"
                    )

        return True, None

    def _stop(self, reason_code: str, reason_message: str) -> None:
        """Dừng bot vì lý do rủi ro."""
        self._stopped = True
        self._stop_reason = reason_message
        log_error(f"RISK MANAGER - DỪNG BOT: {reason_message}")

    def get_status(self) -> dict[str, Any]:
        """
        Lấy trạng thái hiện tại của risk manager.

        Returns:
            dict: Trạng thái rủi ro
        """
        return {
            'enabled': self.enabled,
            'stopped': self._stopped,
            'stop_reason': self._stop_reason,
            'trade_count': self._trade_count,
            'consecutive_losses': self._consecutive_losses,
            'total_profit_pct': self._total_profit_pct,
            'peak_profit_pct': self._peak_profit_pct,
            'current_drawdown_pct': self.current_drawdown_pct,
            'total_slippage_usd': self._total_slippage_usd,
            'limits': {
                'max_drawdown_pct': self.max_drawdown_pct,
                'max_loss_per_trade_usd': self.max_loss_per_trade_usd,
                'max_session_loss_pct': self.max_session_loss_pct,
                'max_consecutive_losses': self.max_consecutive_losses,
                'max_slippage_pct': self.max_slippage_pct,
                'cooldown_after_loss_sec': self.cooldown_after_loss_sec,
            }
        }
