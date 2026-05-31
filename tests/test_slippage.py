"""
Tests cho tính năng slippage tracking.
Kiểm tra tính toán slippage, lưu trữ database, và analytics.
"""
import os
import tempfile
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.async_order_service import AsyncOrderService
from services.database_service import DatabaseService


# ─── Tests cho AsyncOrderService slippage helpers ─────────────────────


class TestExtractFillPrice:
    """Test trích xuất giá fill thực tế từ order response."""

    def test_extract_from_average(self):
        """Ưu tiên trường 'average' khi có."""
        order = {'average': 50100.5, 'price': 50000.0, 'filled': 0.01}
        result = AsyncOrderService._extract_fill_price(order, 50000.0)
        assert result == 50100.5

    def test_extract_from_price_when_no_average(self):
        """Fallback sang 'price' khi không có 'average'."""
        order = {'price': 50050.0, 'filled': 0.01}
        result = AsyncOrderService._extract_fill_price(order, 50000.0)
        assert result == 50050.0

    def test_extract_fallback_expected(self):
        """Trả về giá kỳ vọng khi order response rỗng."""
        result = AsyncOrderService._extract_fill_price({}, 50000.0)
        assert result == 50000.0

    def test_extract_none_response(self):
        """Trả về giá kỳ vọng khi response là None."""
        result = AsyncOrderService._extract_fill_price(None, 50000.0)
        assert result == 50000.0

    def test_extract_zero_average(self):
        """Bỏ qua average = 0, dùng price."""
        order = {'average': 0, 'price': 50050.0}
        result = AsyncOrderService._extract_fill_price(order, 50000.0)
        assert result == 50050.0

    def test_extract_zero_both(self):
        """Trả về expected khi cả average và price đều 0."""
        order = {'average': 0, 'price': 0}
        result = AsyncOrderService._extract_fill_price(order, 50000.0)
        assert result == 50000.0

    def test_extract_non_dict_response(self):
        """Trả về expected khi response không phải dict."""
        result = AsyncOrderService._extract_fill_price("invalid", 50000.0)
        assert result == 50000.0


class TestCalculateSlippage:
    """Test tính toán slippage."""

    def test_no_slippage(self):
        """Không có slippage khi giá thực tế = kỳ vọng."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 50000.0,
            'actual_sell_price': 50100.0,
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == 0.0
        assert fill['sell_slippage_pct'] == 0.0
        assert fill['total_slippage_usd'] == 0.0

    def test_positive_buy_slippage(self):
        """Mua đắt hơn kỳ vọng = slippage dương (bất lợi)."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 50050.0,
            'actual_sell_price': 50100.0,
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == pytest.approx(0.1, rel=1e-3)  # 50/50000 * 100
        assert fill['sell_slippage_pct'] == 0.0
        assert fill['total_slippage_usd'] == pytest.approx(0.5, rel=1e-3)  # 50 * 0.01

    def test_negative_sell_slippage(self):
        """Bán rẻ hơn kỳ vọng = cost dương."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 50000.0,
            'actual_sell_price': 50050.0,
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == 0.0
        assert fill['sell_slippage_pct'] == pytest.approx(-0.0998, rel=1e-2)
        assert fill['total_slippage_usd'] == pytest.approx(0.5, rel=1e-3)  # (50100-50050)*0.01

    def test_both_slippage(self):
        """Slippage cả mua và bán."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 50025.0,   # Mua đắt hơn 25
            'actual_sell_price': 50075.0,  # Bán rẻ hơn 25
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == pytest.approx(0.05, rel=1e-2)
        assert fill['sell_slippage_pct'] == pytest.approx(-0.0499, rel=1e-2)
        assert fill['total_slippage_usd'] == pytest.approx(0.50, rel=1e-2)

    def test_favorable_slippage(self):
        """Slippage có lợi (mua rẻ hơn hoặc bán đắt hơn)."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 49950.0,   # Mua rẻ hơn 50
            'actual_sell_price': 50150.0,  # Bán đắt hơn 50
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] < 0  # Có lợi
        assert fill['sell_slippage_pct'] > 0  # Có lợi
        assert fill['total_slippage_usd'] < 0  # Tổng slippage âm = lợi nhuận thêm

    def test_zero_expected_price(self):
        """Không tính slippage khi giá kỳ vọng = 0."""
        fill = {
            'expected_buy_price': 0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': 50000.0,
            'actual_sell_price': 50100.0,
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == 0.0

    def test_none_actual_price_uses_expected(self):
        """Khi actual_price là None, dùng expected để tính (slippage = 0)."""
        fill = {
            'expected_buy_price': 50000.0,
            'expected_sell_price': 50100.0,
            'actual_buy_price': None,
            'actual_sell_price': None,
        }
        AsyncOrderService._calculate_slippage(fill, 0.01)
        assert fill['buy_slippage_pct'] == 0.0
        assert fill['sell_slippage_pct'] == 0.0
        assert fill['total_slippage_usd'] == 0.0


# ─── Tests cho Database slippage ─────────────────────────────────────


class TestDatabaseSlippage:
    """Test lưu trữ và truy vấn slippage trong database."""

    @pytest.fixture
    def db(self):
        """Tạo database tạm thời cho test."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db_service = DatabaseService(db_path=path)
        yield db_service
        try:
            os.unlink(path)
        except OSError:
            pass

    def _create_session(self, db):
        """Helper tạo session."""
        return db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 60)

    def test_record_trade_with_slippage(self, db):
        """Ghi giao dịch với thông tin slippage."""
        session_id = self._create_session(db)
        trade_id = db.record_trade(
            session_id, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0,
            actual_buy_price=50025.0,
            actual_sell_price=50075.0,
            buy_slippage_pct=0.05,
            sell_slippage_pct=-0.05,
            total_slippage_usd=0.5
        )
        assert trade_id is not None

        # Verify trade stored correctly
        trades = db.get_trades_by_session(session_id)
        assert len(trades) == 1
        trade = trades[0]
        assert trade['actual_buy_price'] == 50025.0
        assert trade['actual_sell_price'] == 50075.0
        assert trade['buy_slippage_pct'] == pytest.approx(0.05)
        assert trade['sell_slippage_pct'] == pytest.approx(-0.05)
        assert trade['total_slippage_usd'] == pytest.approx(0.5)

    def test_record_trade_without_slippage(self, db):
        """Ghi giao dịch không có slippage (backward compatible)."""
        session_id = self._create_session(db)
        trade_id = db.record_trade(
            session_id, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0
        )
        assert trade_id is not None

        trades = db.get_trades_by_session(session_id)
        trade = trades[0]
        assert trade['actual_buy_price'] is None
        assert trade['actual_sell_price'] is None
        assert trade['buy_slippage_pct'] == 0
        assert trade['sell_slippage_pct'] == 0
        assert trade['total_slippage_usd'] == 0

    def test_slippage_stats_empty(self, db):
        """Thống kê slippage khi chưa có dữ liệu."""
        stats = db.get_slippage_stats()
        assert stats['trades_with_slippage'] == 0
        assert stats['avg_buy_slippage_pct'] == 0
        assert stats['total_slippage_usd'] == 0

    def test_slippage_stats_with_data(self, db):
        """Thống kê slippage với nhiều giao dịch."""
        session_id = self._create_session(db)

        # Trade 1: slippage nhỏ
        db.record_trade(
            session_id, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0,
            actual_buy_price=50010.0,
            actual_sell_price=50090.0,
            buy_slippage_pct=0.02,
            sell_slippage_pct=-0.02,
            total_slippage_usd=0.2
        )

        # Trade 2: slippage lớn
        db.record_trade(
            session_id, 2, 'BTC/USDT', 'kucoin', 'binance',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.2, 2.0,
            actual_buy_price=50050.0,
            actual_sell_price=50050.0,
            buy_slippage_pct=0.1,
            sell_slippage_pct=-0.1,
            total_slippage_usd=1.0
        )

        stats = db.get_slippage_stats()
        assert stats['trades_with_slippage'] == 2
        assert stats['avg_buy_slippage_pct'] == pytest.approx(0.06, rel=1e-2)
        assert stats['total_slippage_usd'] == pytest.approx(1.2, rel=1e-2)
        assert stats['max_buy_slippage_pct'] == pytest.approx(0.1, rel=1e-2)

    def test_slippage_stats_by_session(self, db):
        """Thống kê slippage lọc theo phiên."""
        s1 = self._create_session(db)
        s2 = self._create_session(db)

        db.record_trade(
            s1, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0,
            actual_buy_price=50010.0, actual_sell_price=50090.0,
            buy_slippage_pct=0.02, sell_slippage_pct=-0.02,
            total_slippage_usd=0.2
        )

        db.record_trade(
            s2, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0,
            actual_buy_price=50050.0, actual_sell_price=50050.0,
            buy_slippage_pct=0.1, sell_slippage_pct=-0.1,
            total_slippage_usd=1.0
        )

        stats_s1 = db.get_slippage_stats(session_id=s1)
        stats_s2 = db.get_slippage_stats(session_id=s2)

        assert stats_s1['trades_with_slippage'] == 1
        assert stats_s1['total_slippage_usd'] == pytest.approx(0.2)
        assert stats_s2['trades_with_slippage'] == 1
        assert stats_s2['total_slippage_usd'] == pytest.approx(1.0)

    def test_slippage_by_exchange(self, db):
        """Thống kê slippage theo sàn."""
        session_id = self._create_session(db)

        # Binance là sàn mua 2 lần
        db.record_trade(
            session_id, 1, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.1, 1.0,
            actual_buy_price=50010.0, actual_sell_price=50090.0,
            buy_slippage_pct=0.02, sell_slippage_pct=-0.02,
            total_slippage_usd=0.2
        )
        db.record_trade(
            session_id, 2, 'BTC/USDT', 'binance', 'kucoin',
            50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
            0.2, 2.0,
            actual_buy_price=50020.0, actual_sell_price=50080.0,
            buy_slippage_pct=0.04, sell_slippage_pct=-0.04,
            total_slippage_usd=0.4
        )

        result = db.get_slippage_by_exchange()
        assert 'buy_slippage' in result
        assert 'sell_slippage' in result
        assert len(result['buy_slippage']) == 1  # Only binance as buyer
        assert result['buy_slippage'][0]['exchange'] == 'binance'
        assert result['buy_slippage'][0]['trade_count'] == 2


# ─── Tests cho async place_arbitrage_orders return dict ──────────────


class TestArbitrageOrdersSlippageResult:
    """Test kết quả trả về từ place_arbitrage_orders bao gồm slippage."""

    @pytest.fixture
    def mock_exchange_service(self):
        mock = MagicMock()
        mock.async_create_limit_buy_order = AsyncMock(return_value={
            'id': 'buy_1', 'status': 'open', 'average': 50010.0, 'price': 50000.0
        })
        mock.async_create_limit_sell_order = AsyncMock(return_value={
            'id': 'sell_1', 'status': 'open', 'average': 50090.0, 'price': 50100.0
        })
        mock.async_fetch_open_orders = AsyncMock(return_value=[])
        mock.async_fetch_closed_orders = AsyncMock(return_value=[
            {'id': 'buy_1', 'average': 50010.0, 'filled': 0.01},
        ])
        return mock

    @pytest.fixture
    def service(self, mock_exchange_service):
        return AsyncOrderService(mock_exchange_service)

    @pytest.mark.asyncio
    async def test_result_contains_slippage_fields(self, service):
        """Kết quả chứa tất cả trường slippage."""
        result = await service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'expected_buy_price' in result
        assert 'expected_sell_price' in result
        assert 'actual_buy_price' in result
        assert 'actual_sell_price' in result
        assert 'buy_slippage_pct' in result
        assert 'sell_slippage_pct' in result
        assert 'total_slippage_usd' in result

    @pytest.mark.asyncio
    async def test_result_success_true(self, service):
        """Kết quả success = True khi lệnh gửi thành công."""
        result = await service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert result['success'] is True

    @pytest.mark.asyncio
    async def test_result_expected_prices(self, service):
        """Kết quả chứa đúng giá kỳ vọng."""
        result = await service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert result['expected_buy_price'] == 50000.0
        assert result['expected_sell_price'] == 50100.0

    @pytest.mark.asyncio
    async def test_result_actual_prices_from_order(self, service):
        """Giá thực tế được trích xuất từ order response."""
        result = await service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        # actual_buy_price lấy từ order response 'average' = 50010.0
        assert result['actual_buy_price'] is not None

    @pytest.mark.asyncio
    async def test_result_is_truthy(self, service):
        """Dict kết quả luôn truthy khi thành công (backward compat)."""
        result = await service.place_arbitrage_orders(
            'binance', 'kucoin', 'BTC/USDT', 0.01, 50000.0, 50100.0
        )
        assert result  # dict is truthy
