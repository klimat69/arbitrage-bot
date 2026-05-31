"""
Tests cho RateLimiter - giới hạn tần suất gọi API.
"""
import time
import pytest
import asyncio
from services.rate_limiter import RateLimiter, get_rate_limiter


class TestRateLimiterInit:
    """Test khởi tạo."""

    def test_default_limits(self):
        """Giới hạn mặc định cho các sàn."""
        rl = RateLimiter()
        assert 'binance' in rl.DEFAULT_LIMITS
        assert 'kucoin' in rl.DEFAULT_LIMITS
        assert rl.DEFAULT_LIMITS['binance']['requests_per_second'] > 0

    def test_custom_limits(self):
        """Giới hạn tùy chỉnh."""
        rl = RateLimiter({'test_exchange': {'requests_per_second': 2, 'burst': 5}})
        limit = rl._get_limit('test_exchange')
        assert limit['requests_per_second'] == 2
        assert limit['burst'] == 5

    def test_unknown_exchange_default(self):
        """Sàn không biết dùng giá trị mặc định."""
        rl = RateLimiter()
        limit = rl._get_limit('unknown_exchange')
        assert limit['requests_per_second'] == 5
        assert limit['burst'] == 10


class TestRateLimiterAcquire:
    """Test acquire token."""

    def test_acquire_within_burst(self):
        """Acquire nhanh trong burst limit."""
        rl = RateLimiter({'test': {'requests_per_second': 10, 'burst': 5}})
        # Đầu tiên refill sẽ cho burst tokens
        start = time.monotonic()
        for _ in range(5):
            rl.acquire('test')
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Không cần chờ

    def test_acquire_rate_limited(self):
        """Chờ khi vượt bursts."""
        rl = RateLimiter({'test': {'requests_per_second': 100, 'burst': 2}})
        # Drain burst tokens
        rl.acquire('test')
        rl.acquire('test')
        # Lần tiếp theo sẽ phải chờ nhưng rất ngắn (0.01s)
        start = time.monotonic()
        rl.acquire('test')
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # Chờ rất ngắn

    def test_acquire_tracks_stats(self):
        """Thống kê requests."""
        rl = RateLimiter({'test': {'requests_per_second': 100, 'burst': 50}})
        for _ in range(10):
            rl.acquire('test')
        stats = rl.get_stats('test')
        assert stats['total_requests'] == 10


class TestRateLimiterAsync:
    """Test async acquire."""

    @pytest.mark.asyncio
    async def test_async_acquire_within_burst(self):
        """Async acquire nhanh trong burst."""
        rl = RateLimiter({'test': {'requests_per_second': 10, 'burst': 5}})
        start = time.monotonic()
        for _ in range(5):
            await rl.async_acquire('test')
        elapsed = time.monotonic() - start
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_async_non_blocking(self):
        """Async acquire không block event loop."""
        rl = RateLimiter({'test': {'requests_per_second': 100, 'burst': 2}})
        await rl.async_acquire('test')
        await rl.async_acquire('test')
        # Tiếp theo có thể chờ nhưng async
        await rl.async_acquire('test')
        stats = rl.get_stats('test')
        assert stats['total_requests'] == 3

    @pytest.mark.asyncio
    async def test_concurrent_different_exchanges(self):
        """Concurrent requests trên sàn khác nhau không block lẫn nhau."""
        rl = RateLimiter({
            'exchange_a': {'requests_per_second': 100, 'burst': 10},
            'exchange_b': {'requests_per_second': 100, 'burst': 10},
        })

        async def make_requests(exchange_id, count):
            for _ in range(count):
                await rl.async_acquire(exchange_id)

        start = time.monotonic()
        await asyncio.gather(
            make_requests('exchange_a', 5),
            make_requests('exchange_b', 5),
        )
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Song song nên nhanh


class TestRateLimiterStats:
    """Test thống kê."""

    def test_stats_per_exchange(self):
        """Thống kê riêng cho từng sàn."""
        rl = RateLimiter({'a': {'requests_per_second': 100, 'burst': 50},
                          'b': {'requests_per_second': 100, 'burst': 50}})
        for _ in range(3):
            rl.acquire('a')
        for _ in range(5):
            rl.acquire('b')

        stats_a = rl.get_stats('a')
        stats_b = rl.get_stats('b')
        assert stats_a['total_requests'] == 3
        assert stats_b['total_requests'] == 5

    def test_stats_all(self):
        """Thống kê tổng hợp."""
        rl = RateLimiter({'a': {'requests_per_second': 100, 'burst': 50}})
        rl.acquire('a')
        rl.acquire('a')
        all_stats = rl.get_stats()
        assert 'a' in all_stats
        assert all_stats['a']['total_requests'] == 2

    def test_reset_stats(self):
        """Reset thống kê."""
        rl = RateLimiter({'a': {'requests_per_second': 100, 'burst': 50}})
        rl.acquire('a')
        rl.reset_stats()
        assert rl.get_stats('a')['total_requests'] == 0


class TestGetRateLimiter:
    """Test singleton."""

    def test_singleton(self):
        """get_rate_limiter trả về cùng instance."""
        # Reset singleton
        import services.rate_limiter
        services.rate_limiter._global_rate_limiter = None

        rl1 = get_rate_limiter()
        rl2 = get_rate_limiter()
        assert rl1 is rl2

        # Cleanup
        services.rate_limiter._global_rate_limiter = None
