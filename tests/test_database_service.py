"""
Unit tests for services/database_service.py
"""
import os
import pytest
import tempfile
from services.database_service import DatabaseService


@pytest.fixture
def db():
    """Tạo database tạm thời cho mỗi test."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    service = DatabaseService(db_path=db_path)
    yield service
    os.unlink(db_path)


class TestSessionManagement:
    def test_create_session(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin', 'okx'], 1000.0, 15
        )
        assert session_id is not None
        assert session_id > 0

    def test_get_session(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 500.0, 10
        )
        session = db.get_session(session_id)
        assert session is not None
        assert session['mode'] == 'classic'
        assert session['symbol'] == 'BTC/USDT'
        assert session['usdt_amount'] == 500.0
        assert session['status'] == 'running'

    def test_update_session(self, db):
        session_id = db.create_session(
            'fake-money', 'ETH/USDT', ['binance'], 200.0, 5
        )
        db.update_session(session_id, status='completed', total_profit_pct=1.5)
        session = db.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['total_profit_pct'] == 1.5

    def test_end_session(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        db.end_session(
            session_id,
            total_profit_pct=2.5,
            total_profit_usd=25.0,
            total_fees_usd=5.0,
            opportunities_found=10,
            trades_executed=5,
            trades_failed=1,
            total_volume_usd=5000.0,
            final_balance=1025.0
        )
        session = db.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['total_profit_pct'] == 2.5
        assert session['total_profit_usd'] == 25.0
        assert session['trades_executed'] == 5

    def test_get_nonexistent_session(self, db):
        session = db.get_session(9999)
        assert session is None

    def test_get_all_sessions(self, db):
        db.create_session('classic', 'BTC/USDT', ['binance'], 100.0, 5)
        db.create_session('fake-money', 'ETH/USDT', ['kucoin'], 200.0, 10)
        sessions = db.get_all_sessions()
        assert len(sessions) == 2

    def test_get_all_sessions_filter_status(self, db):
        sid1 = db.create_session('classic', 'BTC/USDT', ['binance'], 100.0, 5)
        db.create_session('fake-money', 'ETH/USDT', ['kucoin'], 200.0, 10)
        db.update_session(sid1, status='completed')
        sessions = db.get_all_sessions(status='completed')
        assert len(sessions) == 1
        assert sessions[0]['mode'] == 'classic'

    def test_get_all_sessions_filter_symbol(self, db):
        db.create_session('classic', 'BTC/USDT', ['binance'], 100.0, 5)
        db.create_session('fake-money', 'ETH/USDT', ['kucoin'], 200.0, 10)
        sessions = db.get_all_sessions(symbol='ETH/USDT')
        assert len(sessions) == 1
        assert sessions[0]['symbol'] == 'ETH/USDT'

    def test_update_session_ignores_invalid_fields(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance'], 100.0, 5
        )
        db.update_session(session_id, invalid_field='bad', status='completed')
        session = db.get_session(session_id)
        assert session['status'] == 'completed'


class TestTradeManagement:
    def test_record_trade(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        trade_id = db.record_trade(
            session_id=session_id,
            trade_number=1,
            symbol='BTC/USDT',
            buy_exchange='binance',
            sell_exchange='kucoin',
            buy_price=50000.0,
            sell_price=50100.0,
            amount=0.01,
            profit_pct=0.15,
            profit_usd=1.0,
            fee_usd=0.5,
            fee_crypto=0.00001,
            cumulative_profit_pct=0.15,
            cumulative_profit_usd=1.0
        )
        assert trade_id is not None
        assert trade_id > 0

    def test_get_trades_by_session(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        for i in range(3):
            db.record_trade(
                session_id=session_id,
                trade_number=i + 1,
                symbol='BTC/USDT',
                buy_exchange='binance',
                sell_exchange='kucoin',
                buy_price=50000.0 + i * 10,
                sell_price=50100.0 + i * 10,
                amount=0.01,
                profit_pct=0.1 * (i + 1),
                profit_usd=1.0 * (i + 1),
                fee_usd=0.5,
                fee_crypto=0.00001,
                cumulative_profit_pct=0.1 * (i + 1),
                cumulative_profit_usd=1.0 * (i + 1)
            )
        trades = db.get_trades_by_session(session_id)
        assert len(trades) == 3
        assert trades[0]['trade_number'] == 1
        assert trades[2]['trade_number'] == 3

    def test_get_all_trades_filter_symbol(self, db):
        sid1 = db.create_session('classic', 'BTC/USDT', ['binance'], 100.0, 5)
        sid2 = db.create_session('classic', 'ETH/USDT', ['binance'], 100.0, 5)
        db.record_trade(sid1, 1, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.01, 0.1, 1, 0.5, 0.00001, 0.1, 1)
        db.record_trade(sid2, 1, 'ETH/USDT', 'binance', 'kucoin', 3000, 3010, 0.1, 0.1, 1, 0.5, 0.0001, 0.1, 1)
        trades = db.get_all_trades(symbol='ETH/USDT')
        assert len(trades) == 1
        assert trades[0]['symbol'] == 'ETH/USDT'

    def test_get_all_trades_filter_exchange(self, db):
        sid = db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin', 'okx'], 100.0, 5)
        db.record_trade(sid, 1, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.01, 0.1, 1, 0.5, 0.00001, 0.1, 1)
        db.record_trade(sid, 2, 'BTC/USDT', 'okx', 'kucoin', 50000, 50100, 0.01, 0.1, 1, 0.5, 0.00001, 0.2, 2)
        trades = db.get_all_trades(buy_exchange='okx')
        assert len(trades) == 1
        assert trades[0]['buy_exchange'] == 'okx'


class TestOpportunityManagement:
    def test_record_opportunity(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        opp_id = db.record_opportunity(
            session_id=session_id,
            symbol='BTC/USDT',
            buy_exchange='binance',
            sell_exchange='kucoin',
            buy_price=50000.0,
            sell_price=50100.0,
            spread_pct=0.2,
            estimated_profit_usd=1.0,
            executed=True
        )
        assert opp_id is not None

    def test_get_opportunities_by_session(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        db.record_opportunity(session_id, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.2, 1.0, True)
        db.record_opportunity(session_id, 'BTC/USDT', 'kucoin', 'binance', 50050, 50150, 0.2, 1.0, False)
        opps = db.get_opportunities_by_session(session_id)
        assert len(opps) == 2

    def test_get_opportunities_executed_only(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15
        )
        db.record_opportunity(session_id, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.2, 1.0, True)
        db.record_opportunity(session_id, 'BTC/USDT', 'kucoin', 'binance', 50050, 50150, 0.2, 1.0, False)
        opps = db.get_opportunities_by_session(session_id, executed_only=True)
        assert len(opps) == 1


class TestBalanceSnapshots:
    def test_record_balance_snapshot(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance'], 100.0, 5
        )
        snap_id = db.record_balance_snapshot(
            session_id, 'binance', 500.0, 0.01, 'BTC'
        )
        assert snap_id is not None

    def test_record_all_balances(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 100.0, 5
        )
        db.record_all_balances(
            session_id,
            {'binance': 250.0, 'kucoin': 250.0},
            {'binance': 0.005, 'kucoin': 0.005},
            'BTC/USDT'
        )
        history = db.get_balance_history(session_id)
        assert len(history) == 2

    def test_get_balance_history_filter_exchange(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance', 'kucoin'], 100.0, 5
        )
        db.record_all_balances(
            session_id,
            {'binance': 250.0, 'kucoin': 250.0},
            {'binance': 0.005, 'kucoin': 0.005},
            'BTC/USDT'
        )
        history = db.get_balance_history(session_id, exchange='binance')
        assert len(history) == 1
        assert history[0]['exchange'] == 'binance'


class TestErrorLog:
    def test_record_error(self, db):
        session_id = db.create_session(
            'classic', 'BTC/USDT', ['binance'], 100.0, 5
        )
        db.record_error(
            'network', 'Connection timeout', 
            exchange='binance', session_id=session_id
        )
        errors = db.get_errors(session_id=session_id)
        assert len(errors) == 1
        assert errors[0]['error_type'] == 'network'
        assert errors[0]['exchange'] == 'binance'

    def test_record_error_without_session(self, db):
        db.record_error('config', 'Invalid API key')
        errors = db.get_errors()
        assert len(errors) == 1

    def test_get_errors_filter_type(self, db):
        db.record_error('network', 'Timeout')
        db.record_error('order', 'Insufficient funds')
        db.record_error('network', 'DNS error')
        errors = db.get_errors(error_type='network')
        assert len(errors) == 2


class TestStatistics:
    def _create_sample_data(self, db):
        """Tạo dữ liệu mẫu cho test thống kê."""
        sid = db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 15)
        db.record_trade(sid, 1, 'BTC/USDT', 'binance', 'kucoin', 50000, 50100, 0.01, 0.15, 1.0, 0.5, 0.00001, 0.15, 1.0)
        db.record_trade(sid, 2, 'BTC/USDT', 'kucoin', 'binance', 50050, 50150, 0.01, 0.10, 0.8, 0.5, 0.00001, 0.25, 1.8)
        db.end_session(sid, 0.25, 1.8, 1.0, 2, 2, 0, 1000.0, 1001.8)

        sid2 = db.create_session('classic', 'ETH/USDT', ['binance', 'okx'], 500.0, 10)
        db.record_trade(sid2, 1, 'ETH/USDT', 'binance', 'okx', 3000, 3010, 0.1, 0.20, 1.0, 0.3, 0.0001, 0.20, 1.0)
        db.end_session(sid2, 0.20, 1.0, 0.3, 1, 1, 0, 300.0, 501.0)
        return sid, sid2

    def test_get_overall_stats(self, db):
        self._create_sample_data(db)
        stats = db.get_overall_stats()
        assert stats['total_sessions'] == 2
        assert stats['completed_sessions'] == 2
        assert stats['total_trades'] == 3
        assert stats['total_profit_usd'] == pytest.approx(2.8, abs=0.01)

    def test_get_profit_by_exchange_pair(self, db):
        self._create_sample_data(db)
        pairs = db.get_profit_by_exchange_pair()
        assert len(pairs) >= 2

    def test_get_profit_by_symbol(self, db):
        self._create_sample_data(db)
        symbols = db.get_profit_by_symbol()
        assert len(symbols) == 2
        btc = next(s for s in symbols if s['symbol'] == 'BTC/USDT')
        assert btc['trade_count'] == 2

    def test_get_daily_profit(self, db):
        self._create_sample_data(db)
        daily = db.get_daily_profit(days=1)
        assert len(daily) >= 1
        assert daily[0]['trade_count'] == 3

    def test_get_exchange_performance(self, db):
        self._create_sample_data(db)
        perf = db.get_exchange_performance()
        assert 'buy_performance' in perf
        assert 'sell_performance' in perf
        assert len(perf['buy_performance']) >= 1


class TestDatabaseInit:
    def test_creates_db_file(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            db = DatabaseService(db_path=db_path)
            assert os.path.exists(db_path)
        finally:
            os.unlink(db_path)

    def test_creates_data_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'subdir', 'test.db')
            db = DatabaseService(db_path=db_path)
            assert os.path.exists(db_path)

    def test_idempotent_initialization(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            db1 = DatabaseService(db_path=db_path)
            sid = db1.create_session('classic', 'BTC/USDT', ['binance'], 100.0, 5)
            db2 = DatabaseService(db_path=db_path)
            session = db2.get_session(sid)
            assert session is not None
            assert session['mode'] == 'classic'
        finally:
            os.unlink(db_path)
