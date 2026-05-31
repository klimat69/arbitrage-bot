"""
Tests cho MultiPairManager - giao dịch đồng thời nhiều cặp.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from services.multi_pair_manager import MultiPairManager


class MockBot:
    """Mock bot cho testing."""

    def __init__(self, profit=0.1):
        self._profit = profit
        self.configured = False
        self.started = False

    def configure(self, symbol, exchanges, timeout, amount, indicatif=None):
        self.configured = True
        self.symbol = symbol
        self.exchanges = exchanges
        self.timeout = timeout
        self.amount = amount

    async def start(self):
        self.started = True
        return self._profit

    async def stop(self):
        pass


class TestMultiPairManagerInit:
    """Test khởi tạo."""

    def test_basic_init(self):
        manager = MultiPairManager(
            lambda: MockBot(), ['BTC/USDT', 'ETH/USDT'],
            ['binance', 'kucoin'], 1000.0, 60
        )
        assert manager.amount_per_pair == 500.0
        assert len(manager.symbols) == 2

    def test_amount_split_three_pairs(self):
        manager = MultiPairManager(
            lambda: MockBot(), ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            ['binance'], 900.0, 60
        )
        assert manager.amount_per_pair == pytest.approx(300.0)

    def test_empty_symbols(self):
        manager = MultiPairManager(
            lambda: MockBot(), [],
            ['binance'], 1000.0, 60
        )
        assert manager.amount_per_pair == 0


class TestMultiPairStart:
    """Test chạy multi-pair."""

    @pytest.mark.asyncio
    async def test_start_two_pairs(self):
        """Chạy 2 cặp đồng thời."""
        manager = MultiPairManager(
            lambda: MockBot(0.15),
            ['BTC/USDT', 'ETH/USDT'],
            ['binance', 'kucoin'], 1000.0, 60
        )
        results = await manager.start()
        assert len(results) == 2
        assert 'BTC/USDT' in results
        assert 'ETH/USDT' in results
        assert results['BTC/USDT'] == 0.15
        assert results['ETH/USDT'] == 0.15

    @pytest.mark.asyncio
    async def test_start_empty_symbols(self):
        """Không chạy khi không có cặp nào."""
        manager = MultiPairManager(
            lambda: MockBot(), [], ['binance'], 1000.0, 60
        )
        results = await manager.start()
        assert results == {}

    @pytest.mark.asyncio
    async def test_different_profits(self):
        """Các cặp có lợi nhuận khác nhau."""
        profits = iter([0.1, 0.2, 0.3])

        def factory():
            return MockBot(next(profits))

        manager = MultiPairManager(
            factory,
            ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
            ['binance'], 900.0, 60
        )
        results = await manager.start()
        assert len(results) == 3
        # Total profit = average
        assert manager.total_profit_pct == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_handles_bot_error(self):
        """Xử lý lỗi từ 1 bot mà không ảnh hưởng cặp khác."""
        call_count = 0

        class ErrorBot(MockBot):
            def __init__(self):
                super().__init__(0)

            async def start(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Test error")
                return 0.2

        manager = MultiPairManager(
            lambda: ErrorBot(),
            ['BTC/USDT', 'ETH/USDT'],
            ['binance'], 1000.0, 60
        )
        results = await manager.start()
        assert len(results) == 2
        # Cặp lỗi trả về 0
        assert results['BTC/USDT'] == 0.0
        assert results['ETH/USDT'] == 0.2

    @pytest.mark.asyncio
    async def test_bot_configured_correctly(self):
        """Bot được cấu hình đúng symbol và amount."""
        bots = []

        def factory():
            bot = MockBot(0.1)
            bots.append(bot)
            return bot

        manager = MultiPairManager(
            factory,
            ['BTC/USDT', 'ETH/USDT'],
            ['binance', 'kucoin'], 1000.0, 30
        )
        await manager.start()

        assert len(bots) == 2
        # Mỗi bot nhận đúng amount
        for bot in bots:
            assert bot.configured
            assert bot.started
            assert bot.amount == 500.0
            assert bot.exchanges == ['binance', 'kucoin']
            assert bot.timeout == 30 * 60


class TestMultiPairProperties:
    """Test properties."""

    def test_total_profit_empty(self):
        manager = MultiPairManager(
            lambda: MockBot(), ['BTC/USDT'], ['binance'], 1000.0, 60
        )
        assert manager.total_profit_pct == 0.0

    def test_pair_results(self):
        manager = MultiPairManager(
            lambda: MockBot(), ['BTC/USDT'], ['binance'], 1000.0, 60
        )
        manager._results = {'BTC/USDT': 0.5, 'ETH/USDT': 0.3}
        assert manager.pair_results == {'BTC/USDT': 0.5, 'ETH/USDT': 0.3}
        assert manager.total_profit_pct == pytest.approx(0.4)


class TestMultiPairStopAll:
    """Test dừng tất cả."""

    @pytest.mark.asyncio
    async def test_stop_all_bots(self):
        """Dừng tất cả bot."""
        bots = []

        def factory():
            bot = MockBot()
            bots.append(bot)
            return bot

        manager = MultiPairManager(
            factory,
            ['BTC/USDT', 'ETH/USDT'],
            ['binance'], 1000.0, 60
        )
        await manager.start()
        await manager.stop_all()
        # Không crash = thành công

    @pytest.mark.asyncio
    async def test_stop_handles_error(self):
        """Dừng xử lý lỗi gracefully."""
        class ErrorStopBot(MockBot):
            async def stop(self):
                raise RuntimeError("Stop error")

        manager = MultiPairManager(
            lambda: ErrorStopBot(),
            ['BTC/USDT'],
            ['binance'], 1000.0, 60
        )
        await manager.start()
        # Không crash dù stop() lỗi
        await manager.stop_all()
