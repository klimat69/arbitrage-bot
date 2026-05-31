"""
Multi-pair trading manager - chạy giao dịch đồng thời trên nhiều cặp.
"""
import asyncio
import time
from typing import Any, Callable, Optional
from utils.logger import log_info, log_error, log_warning


class MultiPairManager:
    """
    Quản lý giao dịch đồng thời trên nhiều cặp tiền.
    Mỗi cặp chạy trong một bot instance riêng.
    """

    def __init__(self, bot_factory: Callable[[], Any], symbols: list[str], exchanges: list[str],
                 usdt_amount: float, renew_time: int,
                 notification_service: Any = None) -> None:
        """
        Khởi tạo multi-pair manager.

        Args:
            bot_factory (callable): Hàm tạo bot, nhận () và trả về bot instance
            symbols (list): Danh sách các cặp giao dịch (vd: ['BTC/USDT', 'ETH/USDT'])
            exchanges (list): Danh sách sàn giao dịch
            usdt_amount (float): Tổng số USDT
            renew_time (int): Thời gian làm mới (phút)
            notification_service: Dịch vụ thông báo
        """
        self.bot_factory = bot_factory
        self.symbols = symbols
        self.exchanges = exchanges
        self.usdt_amount = usdt_amount
        self.renew_time = renew_time
        self.notification_service = notification_service

        # Phân bổ vốn đều cho mỗi cặp
        self.amount_per_pair = usdt_amount / len(symbols) if symbols else 0

        # State
        self._bots = {}     # symbol -> bot instance
        self._results = {}  # symbol -> profit_pct
        self._running = False

    @property
    def total_profit_pct(self) -> float:
        """Tổng lợi nhuận trung bình từ tất cả cặp."""
        if not self._results:
            return 0.0
        return sum(self._results.values()) / len(self._results)

    @property
    def pair_results(self) -> dict[str, float]:
        """Kết quả từng cặp."""
        return dict(self._results)

    async def start(self) -> dict[str, float]:
        """
        Bắt đầu giao dịch trên tất cả các cặp đồng thời.

        Returns:
            dict: Kết quả {symbol: profit_pct}
        """
        if not self.symbols:
            log_warning("Không có cặp giao dịch nào để chạy")
            return {}

        self._running = True
        log_info(
            f"Khởi động multi-pair với {len(self.symbols)} cặp: "
            f"{', '.join(self.symbols)}, "
            f"mỗi cặp {self.amount_per_pair:.2f} USDT"
        )

        if self.notification_service:
            self.notification_service.send_message(
                f"🚀 Multi-pair: Bắt đầu {len(self.symbols)} cặp\n"
                f"Cặp: {', '.join(self.symbols)}\n"
                f"Vốn/cặp: {self.amount_per_pair:.2f} USDT"
            )

        # Tạo task cho mỗi cặp
        tasks = []
        for symbol in self.symbols:
            tasks.append(self._run_pair(symbol))

        # Chạy tất cả đồng thời
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Thu thập kết quả
        for symbol, result in zip(self.symbols, results):
            if isinstance(result, Exception):
                log_error(f"Lỗi trên cặp {symbol}: {str(result)}")
                self._results[symbol] = 0.0
            else:
                self._results[symbol] = result

        self._running = False

        # Log tổng kết
        self._display_summary()

        return self._results

    async def _run_pair(self, symbol: str) -> float:
        """
        Chạy bot cho một cặp giao dịch.

        Args:
            symbol (str): Cặp giao dịch

        Returns:
            float: Lợi nhuận (%)
        """
        try:
            log_info(f"[{symbol}] Khởi tạo bot...")
            bot = self.bot_factory()
            self._bots[symbol] = bot

            # Cấu hình bot
            timeout = self.renew_time * 60
            bot.configure(symbol, self.exchanges, timeout,
                         self.amount_per_pair, symbol)

            # Chạy bot
            profit_pct = await bot.start()
            log_info(f"[{symbol}] Kết thúc. Lợi nhuận: {profit_pct:.4f}%")
            return profit_pct

        except Exception as e:
            log_error(f"[{symbol}] Lỗi: {str(e)}")
            return 0.0

    async def stop_all(self) -> None:
        """Dừng tất cả các bot đang chạy."""
        log_info("Đang dừng tất cả các cặp giao dịch...")
        for symbol, bot in self._bots.items():
            try:
                await bot.stop()
                log_info(f"[{symbol}] Đã dừng")
            except Exception as e:
                log_error(f"[{symbol}] Lỗi khi dừng: {str(e)}")

    def _display_summary(self) -> None:
        """Hiển thị tổng kết multi-pair."""
        log_info("\n" + "=" * 60)
        log_info("TỔNG KẾT MULTI-PAIR TRADING")
        log_info("=" * 60)

        total_profit_usd = 0
        for symbol, profit_pct in self._results.items():
            profit_usd = (profit_pct / 100) * self.amount_per_pair
            total_profit_usd += profit_usd
            log_info(
                f"  {symbol}: {profit_pct:+.4f}% ({profit_usd:+.4f} USDT)"
            )

        log_info(f"\nTổng: {total_profit_usd:+.4f} USDT "
                 f"({self.total_profit_pct:+.4f}%)")
        log_info(f"Vốn ban đầu: {self.usdt_amount:.2f} USDT")
        log_info(f"Vốn hiện tại: {self.usdt_amount + total_profit_usd:.2f} USDT")
        log_info("=" * 60)

        if self.notification_service:
            lines = [f"📊 Multi-pair kết thúc:"]
            for symbol, profit_pct in self._results.items():
                profit_usd = (profit_pct / 100) * self.amount_per_pair
                lines.append(f"  {symbol}: {profit_pct:+.4f}% ({profit_usd:+.4f} USDT)")
            lines.append(f"\nTổng: {total_profit_usd:+.4f} USDT")
            self.notification_service.send_message("\n".join(lines))
