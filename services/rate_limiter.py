"""
Rate limiter cho exchange API calls - ngăn chặn bị ban bởi các sàn giao dịch.
Hỗ trợ cấu hình riêng cho từng sàn.
"""
import time
import asyncio
from typing import Any, Optional
from collections import defaultdict
from utils.logger import log_warning, log_debug


class RateLimiter:
    """
    Rate limiter dựa trên token bucket algorithm.
    Mỗi sàn có giới hạn riêng biệt.
    """

    # Giới hạn mặc định cho từng sàn (requests/giây)
    DEFAULT_LIMITS = {
        'binance': {'requests_per_second': 10, 'burst': 20},
        'kucoin': {'requests_per_second': 8, 'burst': 15},
        'okx': {'requests_per_second': 5, 'burst': 10},
        'bybit': {'requests_per_second': 10, 'burst': 20},
        'kucoinfutures': {'requests_per_second': 5, 'burst': 10},
    }

    def __init__(self, custom_limits: Optional[dict[str, dict[str, int]]] = None) -> None:
        """
        Khởi tạo rate limiter.

        Args:
            custom_limits (dict, optional): Giới hạn tùy chỉnh cho các sàn.
                Format: {'exchange_id': {'requests_per_second': N, 'burst': M}}
        """
        self._limits = dict(self.DEFAULT_LIMITS)
        if custom_limits:
            self._limits.update(custom_limits)

        # Token bucket cho mỗi sàn
        self._tokens = defaultdict(lambda: 0.0)
        self._last_refill = defaultdict(lambda: time.monotonic())

        # Thống kê
        self._total_requests = defaultdict(int)
        self._total_waits = defaultdict(int)
        self._total_wait_time = defaultdict(float)

    def _get_limit(self, exchange_id: str) -> dict[str, int]:
        """Lấy cấu hình limit cho sàn."""
        default = {'requests_per_second': 5, 'burst': 10}
        return self._limits.get(exchange_id, default)

    def _refill(self, exchange_id: str) -> None:
        """Nạp lại tokens dựa trên thời gian đã trôi qua."""
        now = time.monotonic()
        elapsed = now - self._last_refill[exchange_id]
        limit = self._get_limit(exchange_id)

        tokens_to_add = elapsed * limit['requests_per_second']
        self._tokens[exchange_id] = min(
            self._tokens[exchange_id] + tokens_to_add,
            float(limit['burst'])
        )
        self._last_refill[exchange_id] = now

    def acquire(self, exchange_id: str) -> None:
        """
        Lấy token đồng bộ (blocking nếu cần).

        Args:
            exchange_id (str): ID sàn giao dịch
        """
        self._refill(exchange_id)
        self._total_requests[exchange_id] += 1

        if self._tokens[exchange_id] >= 1.0:
            self._tokens[exchange_id] -= 1.0
            return

        # Tính thời gian chờ
        limit = self._get_limit(exchange_id)
        wait_time = (1.0 - self._tokens[exchange_id]) / limit['requests_per_second']

        self._total_waits[exchange_id] += 1
        self._total_wait_time[exchange_id] += wait_time
        log_debug(f"Rate limit {exchange_id}: chờ {wait_time:.3f}s")

        time.sleep(wait_time)
        self._tokens[exchange_id] = 0.0

    async def async_acquire(self, exchange_id: str) -> None:
        """
        Lấy token bất đồng bộ (non-blocking wait).

        Args:
            exchange_id (str): ID sàn giao dịch
        """
        self._refill(exchange_id)
        self._total_requests[exchange_id] += 1

        if self._tokens[exchange_id] >= 1.0:
            self._tokens[exchange_id] -= 1.0
            return

        # Tính thời gian chờ
        limit = self._get_limit(exchange_id)
        wait_time = (1.0 - self._tokens[exchange_id]) / limit['requests_per_second']

        self._total_waits[exchange_id] += 1
        self._total_wait_time[exchange_id] += wait_time
        log_debug(f"Rate limit {exchange_id}: chờ {wait_time:.3f}s (async)")

        await asyncio.sleep(wait_time)
        self._tokens[exchange_id] = 0.0

    def get_stats(self, exchange_id: Optional[str] = None) -> dict[str, Any]:
        """
        Lấy thống kê rate limiting.

        Args:
            exchange_id (str, optional): Lọc theo sàn

        Returns:
            dict: Thống kê
        """
        if exchange_id:
            return {
                'exchange': exchange_id,
                'total_requests': self._total_requests[exchange_id],
                'total_waits': self._total_waits[exchange_id],
                'total_wait_time_sec': round(self._total_wait_time[exchange_id], 3),
                'avg_wait_time_sec': round(
                    self._total_wait_time[exchange_id] / max(1, self._total_waits[exchange_id]),
                    3
                ),
            }

        return {
            ex_id: {
                'total_requests': self._total_requests[ex_id],
                'total_waits': self._total_waits[ex_id],
                'total_wait_time_sec': round(self._total_wait_time[ex_id], 3),
            }
            for ex_id in self._total_requests
        }

    def reset_stats(self) -> None:
        """Reset thống kê."""
        self._total_requests.clear()
        self._total_waits.clear()
        self._total_wait_time.clear()


# Singleton global rate limiter
_global_rate_limiter = None


def get_rate_limiter(custom_limits: Optional[dict[str, dict[str, int]]] = None) -> RateLimiter:
    """
    Lấy global rate limiter (singleton).

    Args:
        custom_limits (dict, optional): Giới hạn tùy chỉnh

    Returns:
        RateLimiter: Instance singleton
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(custom_limits)
    return _global_rate_limiter
