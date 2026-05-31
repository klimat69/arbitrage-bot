"""
Tests cho Backtest Framework.
"""
import os
import time
import tempfile
import random
import pytest

from backtest.data_recorder import DataRecorder
from backtest.engine import BacktestEngine, BacktestResult
from backtest.analyzer import BacktestAnalyzer


# ─── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def tmp_db():
    """Tạo database tạm thời."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def recorder(tmp_db):
    """Data recorder với database tạm thời."""
    return DataRecorder(db_path=tmp_db)


@pytest.fixture
def engine(recorder):
    """Backtest engine với recorder."""
    return BacktestEngine(data_recorder=recorder)


@pytest.fixture
def sample_data(recorder):
    """Tạo dữ liệu mẫu cho backtest."""
    symbol = 'BTC/USDT'
    exchanges = ['binance', 'kucoin']
    base_time = time.time()

    snapshots = []
    for i in range(100):
        ts = base_time + i

        # Binance: giá thấp hơn (mua)
        snapshots.append({
            'timestamp': ts,
            'symbol': symbol,
            'exchange': 'binance',
            'best_bid': 50000 + i * 0.5,
            'best_ask': 50001 + i * 0.5,
            'bid_volume': 1.0,
            'ask_volume': 1.0,
        })

        # KuCoin: giá cao hơn nhiều (bán) — spread ~200 USD để vượt phí
        snapshots.append({
            'timestamp': ts,
            'symbol': symbol,
            'exchange': 'kucoin',
            'best_bid': 50200 + i * 0.5,
            'best_ask': 50201 + i * 0.5,
            'bid_volume': 1.0,
            'ask_volume': 1.0,
        })

    recorder.record_batch(snapshots)
    return {'symbol': symbol, 'exchanges': exchanges, 'base_time': base_time}


# ─── DataRecorder Tests ──────────────────────────────────────────

class TestDataRecorder:

    def test_record_single_snapshot(self, recorder):
        recorder.record_snapshot(
            time.time(), 'BTC/USDT', 'binance', 50000, 50001, 1.0, 1.0
        )
        assert recorder.get_snapshot_count() == 1

    def test_record_batch(self, recorder):
        batch = [
            {'timestamp': time.time(), 'symbol': 'BTC/USDT', 'exchange': 'binance',
             'best_bid': 50000, 'best_ask': 50001},
            {'timestamp': time.time(), 'symbol': 'BTC/USDT', 'exchange': 'kucoin',
             'best_bid': 50010, 'best_ask': 50011},
        ]
        recorder.record_batch(batch)
        assert recorder.get_snapshot_count() == 2

    def test_get_snapshots_filter_symbol(self, recorder):
        recorder.record_snapshot(time.time(), 'BTC/USDT', 'binance', 50000, 50001)
        recorder.record_snapshot(time.time(), 'ETH/USDT', 'binance', 3000, 3001)
        snaps = recorder.get_snapshots('BTC/USDT')
        assert len(snaps) == 1
        assert snaps[0]['symbol'] == 'BTC/USDT'

    def test_get_snapshots_filter_exchange(self, recorder):
        recorder.record_snapshot(time.time(), 'BTC/USDT', 'binance', 50000, 50001)
        recorder.record_snapshot(time.time(), 'BTC/USDT', 'kucoin', 50010, 50011)
        snaps = recorder.get_snapshots('BTC/USDT', exchanges=['binance'])
        assert len(snaps) == 1
        assert snaps[0]['exchange'] == 'binance'

    def test_get_snapshots_filter_time(self, recorder):
        t1 = time.time()
        t2 = t1 + 100
        t3 = t1 + 200
        recorder.record_snapshot(t1, 'BTC/USDT', 'binance', 50000, 50001)
        recorder.record_snapshot(t2, 'BTC/USDT', 'binance', 50100, 50101)
        recorder.record_snapshot(t3, 'BTC/USDT', 'binance', 50200, 50201)

        snaps = recorder.get_snapshots('BTC/USDT', start_time=t2, end_time=t2)
        assert len(snaps) == 1
        assert snaps[0]['best_bid'] == 50100

    def test_recording_session(self, recorder):
        sid = recorder.start_recording_session('BTC/USDT', ['binance', 'kucoin'])
        assert sid > 0
        recorder.end_recording_session(sid, 100)
        sessions = recorder.get_recording_sessions()
        assert len(sessions) == 1
        assert sessions[0]['status'] == 'completed'
        assert sessions[0]['snapshot_count'] == 100

    def test_generate_synthetic_data(self, recorder):
        count = recorder.generate_synthetic_data(
            'BTC/USDT', ['binance', 'kucoin'],
            duration_minutes=1, interval_seconds=1
        )
        assert count == 120  # 60 steps * 2 exchanges
        assert recorder.get_snapshot_count() == 120

    def test_snapshot_count_by_symbol(self, recorder):
        recorder.record_snapshot(time.time(), 'BTC/USDT', 'binance', 50000, 50001)
        recorder.record_snapshot(time.time(), 'BTC/USDT', 'binance', 50000, 50001)
        recorder.record_snapshot(time.time(), 'ETH/USDT', 'binance', 3000, 3001)
        assert recorder.get_snapshot_count('BTC/USDT') == 2
        assert recorder.get_snapshot_count('ETH/USDT') == 1
        assert recorder.get_snapshot_count() == 3


# ─── BacktestResult Tests ────────────────────────────────────────

class TestBacktestResult:

    def test_empty_result(self):
        result = BacktestResult()
        assert result.total_trades == 0
        assert result.win_rate == 0
        assert result.total_profit_usd == 0
        assert result.max_drawdown_pct == 0
        assert result.sharpe_ratio == 0
        assert result.profit_factor == 0

    def test_result_with_trades(self):
        result = BacktestResult()
        result.trades = [
            {'profit_usd': 5.0, 'profit_pct': 0.5, 'fee_usd': 0.1},
            {'profit_usd': -2.0, 'profit_pct': -0.2, 'fee_usd': 0.1},
            {'profit_usd': 3.0, 'profit_pct': 0.3, 'fee_usd': 0.1},
        ]
        assert result.total_trades == 3
        assert result.winning_trades == 2
        assert result.losing_trades == 1
        assert abs(result.win_rate - 66.67) < 0.1
        assert abs(result.total_profit_usd - 6.0) < 0.01
        assert result.total_fees_usd == pytest.approx(0.3)

    def test_best_worst_trade(self):
        result = BacktestResult()
        result.trades = [
            {'profit_usd': 10.0, 'profit_pct': 1.0, 'fee_usd': 0},
            {'profit_usd': -5.0, 'profit_pct': -0.5, 'fee_usd': 0},
        ]
        assert result.best_trade_usd == 10.0
        assert result.worst_trade_usd == -5.0

    def test_profit_factor(self):
        result = BacktestResult()
        result.trades = [
            {'profit_usd': 10.0, 'profit_pct': 1.0, 'fee_usd': 0},
            {'profit_usd': -5.0, 'profit_pct': -0.5, 'fee_usd': 0},
        ]
        assert result.profit_factor == 2.0

    def test_profit_factor_no_losses(self):
        result = BacktestResult()
        result.trades = [
            {'profit_usd': 5.0, 'profit_pct': 0.5, 'fee_usd': 0},
        ]
        assert result.profit_factor == float('inf')

    def test_max_drawdown(self):
        result = BacktestResult()
        result.equity_curve = [1000, 1050, 1030, 1080, 1020, 1100]
        # Peak at 1080, low after at 1020: dd = (1080-1020)/1080 = 5.56%
        assert result.max_drawdown_pct == pytest.approx(5.5556, abs=0.01)

    def test_summary(self):
        result = BacktestResult()
        result.config = {'symbol': 'BTC/USDT'}
        summary = result.summary()
        assert 'total_trades' in summary
        assert 'total_profit_usd' in summary
        assert 'config' in summary


# ─── BacktestEngine Tests ────────────────────────────────────────

class TestBacktestEngine:

    def test_run_no_data(self, engine):
        result = engine.run('ETH/USDT', ['binance', 'kucoin'])
        assert result.total_trades == 0
        assert result.config['symbol'] == 'ETH/USDT'

    def test_run_with_data(self, engine, sample_data):
        result = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
        )
        # Spread nhất quán = ~9 USD, nên phải có trades
        assert result.total_trades > 0
        assert result.total_profit_usd > 0

    def test_run_high_threshold_no_trades(self, engine, sample_data):
        result = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=1000000,
        )
        assert result.total_trades == 0

    def test_run_with_slippage(self, engine, sample_data):
        result_no_slip = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
            slippage_bps=0,
        )
        result_with_slip = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
            slippage_bps=50,
        )
        # Slippage giảm lợi nhuận
        assert result_with_slip.total_profit_usd <= result_no_slip.total_profit_usd

    def test_run_with_cooldown(self, engine, sample_data):
        result_no_cd = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
        )
        result_with_cd = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
            cooldown_seconds=10,
        )
        # Cooldown giảm số trades
        assert result_with_cd.total_trades <= result_no_cd.total_trades

    def test_equity_curve_tracked(self, engine, sample_data):
        result = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
        )
        # Initial equity + 1 per trade
        assert len(result.equity_curve) == result.total_trades + 1

    def test_run_with_synthetic_data(self, recorder):
        recorder.generate_synthetic_data(
            'ETH/USDT', ['binance', 'okx'],
            duration_minutes=5, interval_seconds=1,
            base_price=3000, spread_bps=5, volatility_bps=15,
        )
        engine = BacktestEngine(data_recorder=recorder)
        result = engine.run(
            'ETH/USDT', ['binance', 'okx'],
            initial_balance_usd=5000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
        )
        assert result.config['symbol'] == 'ETH/USDT'
        # Dữ liệu synthetic có thể có trades hoặc không
        assert isinstance(result.total_trades, int)

    def test_parameter_sweep(self, engine, sample_data):
        results = engine.run_parameter_sweep(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            slippage_range=[0, 10],
            profit_threshold_range=[0],
        )
        assert len(results) == 2
        # Đã sort theo profit giảm dần
        assert results[0]['summary']['total_profit_usd'] >= results[1]['summary']['total_profit_usd']
        assert 'params' in results[0]

    def test_opportunities_recorded(self, engine, sample_data):
        result = engine.run(
            sample_data['symbol'],
            sample_data['exchanges'],
            initial_balance_usd=10000,
            profit_threshold_usd=0,
            profit_threshold_pct=0,
        )
        assert len(result.opportunities) > 0


# ─── Analyzer Tests ───────────────────────────────────────────────

class TestBacktestAnalyzer:

    def test_analyze_empty(self):
        result = BacktestResult()
        analysis = BacktestAnalyzer.analyze(result)
        assert analysis['total_trades'] == 0
        assert analysis['max_consecutive_wins'] == 0

    def test_analyze_with_trades(self):
        result = BacktestResult()
        result.config = {'symbol': 'BTC/USDT', 'exchanges': ['binance', 'kucoin']}
        result.trades = [
            {'trade_number': 1, 'timestamp': 100, 'buy_exchange': 'binance',
             'sell_exchange': 'kucoin', 'profit_usd': 5.0, 'profit_pct': 0.5, 'fee_usd': 0.1},
            {'trade_number': 2, 'timestamp': 110, 'buy_exchange': 'binance',
             'sell_exchange': 'kucoin', 'profit_usd': 3.0, 'profit_pct': 0.3, 'fee_usd': 0.1},
            {'trade_number': 3, 'timestamp': 120, 'buy_exchange': 'kucoin',
             'sell_exchange': 'binance', 'profit_usd': -1.0, 'profit_pct': -0.1, 'fee_usd': 0.1},
        ]
        result.opportunities = [{'timestamp': t} for t in range(50)]
        analysis = BacktestAnalyzer.analyze(result)

        assert analysis['total_trades'] == 3
        assert analysis['max_consecutive_wins'] == 2
        assert analysis['max_consecutive_losses'] == 1
        assert 'binance->kucoin' in analysis['exchange_pairs']
        assert analysis['exchange_pairs']['binance->kucoin']['count'] == 2
        assert analysis['opportunity_conversion_rate'] == 6.0  # 3/50*100

    def test_compare_results(self):
        r1 = BacktestResult()
        r1.config = {'symbol': 'BTC/USDT'}
        r1.trades = [
            {'profit_usd': 10.0, 'profit_pct': 1.0, 'fee_usd': 0.1},
        ]

        r2 = BacktestResult()
        r2.config = {'symbol': 'BTC/USDT'}
        r2.trades = [
            {'profit_usd': 20.0, 'profit_pct': 2.0, 'fee_usd': 0.2},
        ]

        comparisons = BacktestAnalyzer.compare([r1, r2])
        assert len(comparisons) == 2
        assert comparisons[0]['total_profit_usd'] == 20.0  # r2 đứng đầu
        assert comparisons[0]['rank'] == 1

    def test_format_report(self):
        result = BacktestResult()
        result.config = {'symbol': 'BTC/USDT', 'exchanges': ['binance', 'kucoin'],
                         'initial_balance_usd': 1000, 'slippage_bps': 0}
        result.trades = [
            {'trade_number': 1, 'timestamp': 100, 'buy_exchange': 'binance',
             'sell_exchange': 'kucoin', 'profit_usd': 5.0, 'profit_pct': 0.5, 'fee_usd': 0.1},
        ]
        report = BacktestAnalyzer.format_report(result)
        assert 'BÁO CÁO BACKTEST' in report
        assert 'BTC/USDT' in report
        assert 'binance' in report

    def test_compare_sweep_results(self):
        r1 = BacktestResult()
        r1.trades = [{'profit_usd': 5.0, 'profit_pct': 0.5, 'fee_usd': 0.1}]
        r1.config = {}

        r2 = BacktestResult()
        r2.trades = [{'profit_usd': 15.0, 'profit_pct': 1.5, 'fee_usd': 0.2}]
        r2.config = {}

        sweep_results = [
            {'params': {'slippage_bps': 0}, 'result': r1, 'summary': r1.summary()},
            {'params': {'slippage_bps': 10}, 'result': r2, 'summary': r2.summary()},
        ]
        comparisons = BacktestAnalyzer.compare(sweep_results)
        assert len(comparisons) == 2
        assert comparisons[0]['params']['slippage_bps'] == 10  # r2 có profit cao hơn

    def test_avg_time_between_trades(self):
        result = BacktestResult()
        result.config = {}
        result.trades = [
            {'timestamp': 100, 'profit_usd': 1, 'profit_pct': 0.1,
             'fee_usd': 0, 'buy_exchange': 'a', 'sell_exchange': 'b'},
            {'timestamp': 120, 'profit_usd': 1, 'profit_pct': 0.1,
             'fee_usd': 0, 'buy_exchange': 'a', 'sell_exchange': 'b'},
            {'timestamp': 150, 'profit_usd': 1, 'profit_pct': 0.1,
             'fee_usd': 0, 'buy_exchange': 'a', 'sell_exchange': 'b'},
        ]
        analysis = BacktestAnalyzer.analyze(result)
        assert analysis['avg_time_between_trades_sec'] == 25.0  # (20+30)/2
