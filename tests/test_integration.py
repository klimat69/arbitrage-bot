"""
Integration tests cho Arbitrage Bot.
Sử dụng mock exchange để test toàn bộ flow mà không cần kết nối thật.
"""
import os
import asyncio
import time
import tempfile
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from services.exchange_service import ExchangeService
from services.balance_service import BalanceService
from services.order_service import OrderService
from services.async_order_service import AsyncOrderService
from services.notification_service import NotificationService
from services.database_service import DatabaseService
from utils.exceptions import (
    ExchangeError, InsufficientBalanceError, OrderError,
    OrderFillTimeoutError, FuturesError
)
from configs import EXCHANGE_FEES


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Tạo database tạm cho test."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    service = DatabaseService(db_path=db_path)
    yield service
    os.unlink(db_path)


@pytest.fixture
def mock_exchange_service():
    """Tạo mock ExchangeService."""
    service = MagicMock(spec=ExchangeService)
    
    # Mock sync methods
    service.get_ticker.return_value = {
        'bid': 50000.0, 'ask': 50100.0, 'last': 50050.0
    }
    service.get_balance.return_value = 1000.0
    service.create_limit_buy_order.return_value = {
        'id': 'order_buy_1', 'status': 'open', 'filled': 0
    }
    service.create_limit_sell_order.return_value = {
        'id': 'order_sell_1', 'status': 'open', 'filled': 0
    }
    service.create_market_buy_order.return_value = {
        'id': 'order_market_buy_1', 'status': 'closed', 'filled': 0.01
    }
    service.create_market_sell_order.return_value = {
        'id': 'order_market_sell_1', 'status': 'closed', 'filled': 0.01
    }
    service.fetch_open_orders.return_value = []
    service.fetch_closed_orders.return_value = [
        {'id': 'order_1', 'filled': 0.01, 'status': 'closed'}
    ]
    service.cancel_order.return_value = {'id': 'order_1', 'status': 'canceled'}
    service.emergency_convert.return_value = {'id': 'sell_all', 'status': 'closed'}
    
    # Mock async methods
    service.async_create_limit_buy_order = AsyncMock(return_value={
        'id': 'async_buy_1', 'status': 'open'
    })
    service.async_create_limit_sell_order = AsyncMock(return_value={
        'id': 'async_sell_1', 'status': 'open'
    })
    service.async_create_market_buy_order = AsyncMock(return_value={
        'id': 'async_market_buy_1', 'status': 'closed', 'filled': 0.01
    })
    service.async_create_market_sell_order = AsyncMock(return_value={
        'id': 'async_market_sell_1', 'status': 'closed', 'filled': 0.01
    })
    service.async_fetch_open_orders = AsyncMock(return_value=[])
    service.async_fetch_closed_orders = AsyncMock(return_value=[
        {'id': 'order_1', 'filled': 0.01, 'status': 'closed'}
    ])
    service.async_cancel_order = AsyncMock(return_value={'id': 'order_1', 'status': 'canceled'})
    service.async_emergency_convert = AsyncMock(return_value={'id': 'sell_all', 'status': 'closed'})
    service.async_get_ticker = AsyncMock(return_value={
        'bid': 50000.0, 'ask': 50100.0, 'last': 50050.0
    })
    service.async_get_balance = AsyncMock(return_value=1000.0)
    service.async_create_futures_order = AsyncMock(return_value={
        'id': 'futures_1', 'status': 'closed'
    })
    
    # Mock get_global_average_price
    service.get_global_average_price = AsyncMock(return_value=50050.0)
    
    # Mock exchanges config
    service.exchanges = {
        'binance': {'apiKey': 'test', 'secret': 'test'},
        'kucoin': {'apiKey': 'test', 'secret': 'test', 'password': 'test'},
        'okx': {'apiKey': 'test', 'secret': 'test', 'password': 'test'},
    }
    
    return service


@pytest.fixture
def balance_service(mock_exchange_service):
    """Tạo BalanceService thật với mock exchange."""
    return BalanceService(mock_exchange_service)


@pytest.fixture
def order_service(mock_exchange_service):
    """Tạo OrderService thật với mock exchange."""
    return OrderService(mock_exchange_service)


@pytest.fixture
def async_order_service(mock_exchange_service):
    """Tạo AsyncOrderService thật với mock exchange."""
    return AsyncOrderService(mock_exchange_service)


@pytest.fixture
def notification_service():
    """Tạo mock NotificationService."""
    service = MagicMock(spec=NotificationService)
    service.enabled = False
    service.send_message.return_value = False
    service.send_telegram.return_value = False
    service.send_opportunity.return_value = False
    return service


# ─── Integration: BalanceService + ExchangeService ────────────────────

class TestBalanceServiceIntegration:
    """Test tích hợp giữa BalanceService và ExchangeService."""

    @pytest.mark.asyncio
    async def test_check_balances_sufficient(self, balance_service, mock_exchange_service):
        """Test khi có đủ số dư trên tất cả sàn."""
        mock_exchange_service.async_get_balance.return_value = 500.0
        result = await balance_service.check_balances(
            ['binance', 'kucoin', 'okx'], 'USDT', 1000.0
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_balances_insufficient(self, balance_service, mock_exchange_service):
        """Test khi không đủ số dư."""
        mock_exchange_service.async_get_balance.return_value = 50.0
        with pytest.raises(InsufficientBalanceError):
            await balance_service.check_balances(
                ['binance', 'kucoin', 'okx'], 'USDT', 1000.0
            )

    def test_initialize_balances(self, balance_service):
        """Test khởi tạo số dư ảo."""
        usd = balance_service.initialize_balances(
            ['binance', 'kucoin'], 'BTC/USDT', 1000.0
        )
        assert len(usd) == 2
        assert usd['binance'] == 250.0  # 1000 / 2 / 2
        assert usd['kucoin'] == 250.0

    def test_initialize_crypto_balances(self, balance_service):
        """Test khởi tạo số dư crypto ảo."""
        crypto = balance_service.initialize_crypto_balances(
            ['binance', 'kucoin'], 'BTC/USDT', 50000.0, 1000.0
        )
        assert len(crypto) == 2
        assert crypto['binance'] == pytest.approx(0.005)  # (1000/2) / 50000 / 2
        assert crypto['kucoin'] == pytest.approx(0.005)

    @pytest.mark.asyncio
    async def test_balance_caching(self, balance_service, mock_exchange_service):
        """Test rằng caching hoạt động."""
        mock_exchange_service.async_get_balance.return_value = 500.0
        await balance_service.get_balance('binance', 'USDT')
        await balance_service.get_balance('binance', 'USDT')
        # API chỉ gọi 1 lần nhờ cache
        assert mock_exchange_service.async_get_balance.call_count == 1

    def test_balance_file_operations(self, balance_service):
        """Test đọc/ghi file số dư."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('1000')
            tmp_path = f.name
        try:
            balance_service.initialize_balance_files(1000.0)
            result = balance_service.update_balance_with_profit(10.0)
            assert result == 1100.0
        finally:
            os.unlink(tmp_path) if os.path.exists(tmp_path) else None

    def test_emergency_convert_all(self, balance_service, mock_exchange_service):
        """Test bán khẩn cấp trên tất cả sàn."""
        result = balance_service.emergency_convert_all(
            'BTC/USDT', ['binance', 'kucoin']
        )
        assert result is True
        assert mock_exchange_service.emergency_convert.call_count == 2


# ─── Integration: OrderService + ExchangeService ─────────────────────

class TestOrderServiceIntegration:
    """Test tích hợp OrderService với ExchangeService (sync)."""

    def test_place_initial_orders_all_fill(self, order_service, mock_exchange_service):
        """Test đặt lệnh ban đầu khi tất cả đều khớp."""
        mock_exchange_service.fetch_open_orders.return_value = []
        result = order_service.place_initial_orders(
            ['binance', 'kucoin'], 'BTC/USDT', 0.01, 50000.0
        )
        assert result is True
        assert mock_exchange_service.create_limit_buy_order.call_count == 2

    def test_place_arbitrage_orders_both_fill(self, order_service, mock_exchange_service):
        """Test đặt lệnh arbitrage khi cả hai đều khớp."""
        mock_exchange_service.fetch_open_orders.return_value = []
        result = order_service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert result is True

    def test_emergency_sell(self, order_service, mock_exchange_service):
        """Test bán khẩn cấp."""
        result = order_service.emergency_sell('BTC/USDT', ['binance', 'kucoin'])
        assert result is True
        assert mock_exchange_service.emergency_convert.call_count == 2


# ─── Integration: AsyncOrderService + ExchangeService ────────────────

class TestAsyncOrderServiceIntegration:
    """Test tích hợp AsyncOrderService (async) với ExchangeService."""

    @pytest.mark.asyncio
    async def test_async_place_initial_orders(self, async_order_service, mock_exchange_service):
        """Test đặt lệnh ban đầu async khi tất cả đều khớp."""
        result = await async_order_service.place_initial_orders(
            ['binance', 'kucoin'], 'BTC/USDT', 0.01, 50000.0
        )
        assert result is True
        assert mock_exchange_service.async_create_limit_buy_order.call_count == 2

    @pytest.mark.asyncio
    async def test_async_place_arbitrage_orders(self, async_order_service, mock_exchange_service):
        """Test đặt lệnh arbitrage async đồng thời mua + bán."""
        result = await async_order_service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert isinstance(result, dict)
        assert result['success'] is True
        assert result['expected_buy_price'] == 50000.0
        assert result['expected_sell_price'] == 50100.0
        assert 'buy_slippage_pct' in result
        assert 'sell_slippage_pct' in result
        assert 'total_slippage_usd' in result
        # Cả mua và bán phải được gọi
        mock_exchange_service.async_create_limit_buy_order.assert_called_once()
        mock_exchange_service.async_create_limit_sell_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_emergency_sell(self, async_order_service, mock_exchange_service):
        """Test bán khẩn cấp async trên nhiều sàn đồng thời."""
        result = await async_order_service.async_emergency_sell(
            'BTC/USDT', ['binance', 'kucoin', 'okx']
        )
        assert result is True
        assert mock_exchange_service.async_emergency_convert.call_count == 3

    @pytest.mark.asyncio
    async def test_async_place_initial_orders_partial_fail(self, async_order_service, mock_exchange_service):
        """Test khi 1 sàn lỗi nhưng sàn khác thành công."""
        call_count = 0

        async def mock_buy(exchange_id, symbol, amount, price):
            nonlocal call_count
            call_count += 1
            if exchange_id == 'kucoin':
                raise ExchangeError('kucoin', 'Connection timeout')
            return {'id': f'order_{exchange_id}', 'status': 'open'}

        mock_exchange_service.async_create_limit_buy_order = AsyncMock(side_effect=mock_buy)
        result = await async_order_service.place_initial_orders(
            ['binance', 'kucoin'], 'BTC/USDT', 0.01, 50000.0
        )
        # Vẫn thành công vì binance khớp
        assert result is True

    @pytest.mark.asyncio
    async def test_async_futures_short_order(self, async_order_service, mock_exchange_service):
        """Test đặt lệnh short futures async."""
        result = await async_order_service.place_futures_short_order(
            'kucoinfutures', 'BTC/USDT', 0.01, leverage=2
        )
        assert result is not None
        mock_exchange_service.async_create_futures_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_close_futures_short(self, async_order_service, mock_exchange_service):
        """Test đóng lệnh short futures async."""
        result = await async_order_service.close_futures_short_order(
            'kucoinfutures', 'BTC/USDT', 0.01, leverage=2
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_async_wait_for_futures_fill(self, async_order_service, mock_exchange_service):
        """Test chờ lệnh futures khớp."""
        mock_exchange_service.async_fetch_open_orders = AsyncMock(return_value=[])
        result = await async_order_service.wait_for_futures_order_fill(
            'kucoinfutures', 'BTC:USDT', timeout=5
        )
        assert result is True


# ─── Integration: DatabaseService + Bot Flow ──────────────────────────

class TestDatabaseBotFlowIntegration:
    """Test tích hợp database với flow bot từ đầu đến cuối."""

    def test_full_session_lifecycle(self, db):
        """Test vòng đời đầy đủ: tạo phiên → ghi giao dịch → kết thúc."""
        # Tạo phiên
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin', 'okx'], 1000.0, 15
        )
        assert session_id > 0

        # Ghi snapshot số dư ban đầu
        db.record_all_balances(
            session_id,
            {'binance': 333.33, 'kucoin': 333.33, 'okx': 333.34},
            {'binance': 0, 'kucoin': 0, 'okx': 0},
            'BTC/USDT'
        )

        # Ghi cơ hội
        db.record_opportunity(
            session_id, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.2, 1.0, executed=True
        )

        # Ghi trade
        db.record_trade(
            session_id, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.15, 1.0, 0.5, 0.00001,
            0.15, 1.0, status='executed'
        )

        # Ghi thêm trade
        db.record_trade(
            session_id, 2, 'BTC/USDT', 'kucoin', 'okx',
            50020.0, 50120.0, 0.01, 0.12, 0.8, 0.5, 0.00001,
            0.27, 1.8
        )

        # Ghi snapshot số dư sau giao dịch
        db.record_all_balances(
            session_id,
            {'binance': 332.0, 'kucoin': 334.5, 'okx': 334.0},
            {'binance': 0.005, 'kucoin': 0.003, 'okx': 0.005},
            'BTC/USDT'
        )

        # Kết thúc phiên
        db.end_session(
            session_id,
            total_profit_pct=0.27,
            total_profit_usd=1.8,
            total_fees_usd=1.0,
            opportunities_found=2,
            trades_executed=2,
            trades_failed=0,
            total_volume_usd=1001.2,
            final_balance=1001.8
        )

        # Verify session
        session = db.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['trades_executed'] == 2

        # Verify trades
        trades = db.get_trades_by_session(session_id)
        assert len(trades) == 2
        assert trades[0]['buy_exchange'] == 'binance'
        assert trades[1]['buy_exchange'] == 'kucoin'

        # Verify balance history
        history = db.get_balance_history(session_id)
        assert len(history) == 6  # 3 exchanges × 2 snapshots

        # Verify stats
        stats = db.get_overall_stats()
        assert stats['total_sessions'] == 1
        assert stats['total_trades'] == 2

    def test_error_session_flow(self, db):
        """Test flow khi phiên gặp lỗi."""
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 500.0, 10
        )

        # Ghi lỗi
        db.record_error(
            'network', 'Connection refused',
            exchange='binance', session_id=session_id
        )
        db.record_error(
            'order', 'Insufficient balance',
            exchange='kucoin', session_id=session_id,
            details='Required: 250 USDT, Available: 100 USDT'
        )

        # Cập nhật trạng thái phiên
        db.update_session(session_id, status='error', error_message='Multiple errors')

        # Verify
        session = db.get_session(session_id)
        assert session['status'] == 'error'
        errors = db.get_errors(session_id=session_id)
        assert len(errors) == 2

    def test_multiple_sessions_analytics(self, db):
        """Test analytics khi có nhiều phiên."""
        # Session 1: BTC - thành công
        s1 = db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15)
        db.record_trade(s1, 1, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.01, 0.15, 1.0, 0.5, 0.00001, 0.15, 1.0)
        db.record_trade(s1, 2, 'BTC/USDT', 'kucoin', 'binance', 50050, 50150, 0.01, 0.10, 0.8, 0.5, 0.00001, 0.25, 1.8)
        db.end_session(s1, 0.25, 1.8, 1.0, 5, 2, 0, 1000, 1001.8)

        # Session 2: ETH - thành công
        s2 = db.create_session('fake-money', 'ETH/USDT', ['binance', 'okx'], 500.0, 10)
        db.record_trade(s2, 1, 'ETH/USDT', 'binance', 'okx', 3000, 3010, 0.1, 0.20, 1.0, 0.3, 0.0001, 0.20, 1.0)
        db.end_session(s2, 0.20, 1.0, 0.3, 3, 1, 0, 300, 501.0)

        # Session 3: BTC - lỗi
        s3 = db.create_session('delta-neutral', 'BTC/USDT', ['binance', 'kucoin'], 2000.0, 30)
        db.update_session(s3, status='error', error_message='Failed to open short')

        # Verify overall stats
        stats = db.get_overall_stats()
        assert stats['total_sessions'] == 3
        assert stats['completed_sessions'] == 2
        assert stats['error_sessions'] == 1
        assert stats['total_trades'] == 3

        # Verify by symbol
        symbol_stats = db.get_profit_by_symbol()
        btc = next(s for s in symbol_stats if s['symbol'] == 'BTC/USDT')
        eth = next(s for s in symbol_stats if s['symbol'] == 'ETH/USDT')
        assert btc['trade_count'] == 2
        assert eth['trade_count'] == 1

        # Verify exchange performance
        perf = db.get_exchange_performance()
        assert len(perf['buy_performance']) >= 2
        assert len(perf['sell_performance']) >= 2

        # Verify exchange pair stats
        pairs = db.get_profit_by_exchange_pair()
        assert len(pairs) >= 2


# ─── Integration: Bot Constructor + Services ──────────────────────────

class TestBotConstructorIntegration:
    """Test tích hợp construction of bots với tất cả services."""

    def test_classic_bot_creation(self, mock_exchange_service, balance_service,
                                   order_service, notification_service, db):
        """Test tạo ClassicBot với tất cả services."""
        from bots.classic_bot import ClassicBot
        bot = ClassicBot(
            mock_exchange_service, balance_service, order_service,
            notification_service, db
        )
        assert bot.exchange_service is mock_exchange_service
        assert bot.db is db
        assert bot.async_order_service is not None

    def test_fake_money_bot_creation(self, mock_exchange_service, balance_service,
                                      order_service, notification_service, db):
        """Test tạo FakeMoneyBot với tất cả services."""
        from bots.fake_money_bot import FakeMoneyBot
        bot = FakeMoneyBot(
            mock_exchange_service, balance_service, order_service,
            notification_service, db
        )
        assert bot.exchange_service is mock_exchange_service
        assert bot.db is db

    def test_delta_neutral_bot_creation(self, mock_exchange_service, balance_service,
                                         order_service, notification_service, db):
        """Test tạo DeltaNeutralBot với tất cả services."""
        from bots.delta_neutral_bot import DeltaNeutralBot
        bot = DeltaNeutralBot(
            mock_exchange_service, balance_service, order_service,
            notification_service, db
        )
        assert bot.futures_exchange == 'kucoinfutures'
        assert bot.db is db


# ─── Integration: Notification Service ────────────────────────────────

class TestNotificationServiceIntegration:
    """Test NotificationService integration."""

    def test_disabled_notification(self):
        """Test khi notification bị tắt."""
        service = NotificationService(enabled=False)
        result = service.send_message("Test message")
        assert result is False

    def test_send_opportunity_disabled(self):
        """Test gửi thông báo cơ hội khi tắt."""
        service = NotificationService(enabled=False)
        result = service.send_opportunity(
            1, 'binance', 50000.0, 'kucoin', 50100.0,
            0.15, 1.0, 0.15, 1.0, 0.5, 0.00001,
            'BTC/USDT', '00:05:30',
            {'binance': {'crypto': 0.01, 'usd': 500}, 'kucoin': {'crypto': 0.01, 'usd': 500}},
            1001.0
        )
        assert result is False


# ─── Integration: BaseBot process_orderbook ───────────────────────────

class TestBaseBotOrderbookIntegration:
    """Test xử lý orderbook trong BaseBot."""

    def _create_bot(self, exchange_service, balance_service, order_service,
                    notification_service, db):
        from bots.base_bot import BaseBot
        bot = BaseBot(
            exchange_service, balance_service, order_service,
            notification_service, {'fees': EXCHANGE_FEES}, db
        )
        bot.symbol = 'BTC/USDT'
        bot.exchanges = ['binance', 'kucoin']
        bot.usd = {'binance': 500.0, 'kucoin': 500.0}
        bot.crypto = {'binance': 0.01, 'kucoin': 0.01}
        bot.crypto_per_transaction = 0.005
        bot.bid_prices = {'binance': 50000, 'kucoin': 49950}
        bot.ask_prices = {'binance': 50100, 'kucoin': 50050}
        bot.howmuchusd = 1000.0
        bot.start_time = time.time()
        return bot

    def test_process_orderbook_no_opportunity(self, mock_exchange_service,
                                              balance_service, order_service,
                                              notification_service, db):
        """Test khi không có cơ hội (giá chênh quá nhỏ)."""
        bot = self._create_bot(
            mock_exchange_service, balance_service, order_service,
            notification_service, db
        )
        
        orderbook = {
            'bids': [[50000, 1]],
            'asks': [[50001, 1]]
        }
        result = asyncio.run(bot.process_orderbook('binance', orderbook))
        assert result is False

    def test_process_orderbook_zero_balance(self, mock_exchange_service,
                                            balance_service, order_service,
                                            notification_service, db):
        """Test khi số dư = 0."""
        bot = self._create_bot(
            mock_exchange_service, balance_service, order_service,
            notification_service, db
        )
        bot.usd = {'binance': 0, 'kucoin': 0}
        
        orderbook = {
            'bids': [[50000, 1]],
            'asks': [[50100, 1]]
        }
        result = asyncio.run(bot.process_orderbook('binance', orderbook))
        assert result is False


# ─── Integration: Config Validation ──────────────────────────────────

class TestConfigIntegration:
    """Test tính nhất quán của cấu hình."""

    def test_all_supported_exchanges_have_fees(self):
        """Test rằng tất cả sàn hỗ trợ đều có phí."""
        from configs import SUPPORTED_EXCHANGES, EXCHANGE_FEES
        for exchange in SUPPORTED_EXCHANGES:
            assert exchange in EXCHANGE_FEES, f"Missing fees for {exchange}"
            assert 'give' in EXCHANGE_FEES[exchange]
            assert 'receive' in EXCHANGE_FEES[exchange]

    def test_fee_ranges(self):
        """Test phí trong khoảng hợp lý (0% - 1%)."""
        for exchange, fees in EXCHANGE_FEES.items():
            assert 0 <= fees['give'] <= 0.01, f"Fee too high for {exchange}"
            assert 0 <= fees['receive'] <= 0.01, f"Fee too high for {exchange}"

    def test_bot_modes_valid(self):
        """Test chế độ bot hợp lệ."""
        from configs import BOT_MODES
        assert len(BOT_MODES) >= 3
        for mode in ['fake-money', 'classic', 'delta-neutral']:
            assert mode in BOT_MODES
