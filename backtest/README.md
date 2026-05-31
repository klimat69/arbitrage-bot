# Backtest

Framework backtesting cho chiến lược arbitrage. Hỗ trợ record dữ liệu thực, replay, và phân tích kết quả.

## Các file

| File | Mô tả |
|------|--------|
| `data_recorder.py` | Ghi orderbook snapshot từ sàn vào SQLite, tạo dữ liệu synthetic |
| `engine.py` | Replay dữ liệu lịch sử, mô phỏng giao dịch, tính equity curve |
| `analyzer.py` | Phân tích kết quả: win rate, Sharpe ratio, max drawdown, profit factor |

## Sử dụng nhanh

```python
from backtest.data_recorder import DataRecorder
from backtest.engine import BacktestEngine
from backtest.analyzer import BacktestAnalyzer

# 1. Tạo dữ liệu mẫu
recorder = DataRecorder(db_path=':memory:')
recorder.generate_sample_data(
    symbol='BTC/USDT',
    exchanges=['binance', 'kucoin'],
    num_snapshots=500,
    base_price=50000.0,
    spread_range=(100, 300)
)

# 2. Chạy backtest
engine = BacktestEngine(
    data_source=recorder,
    initial_balance=10000.0,
    fee_rate=0.001,
    min_spread_pct=0.1
)
result = engine.run(symbol='BTC/USDT', exchanges=['binance', 'kucoin'])

# 3. Phân tích
analyzer = BacktestAnalyzer()
analyzer.add_result('default', result)
print(analyzer.generate_report('default'))
```

## Metrics chính

| Metric | Mô tả |
|--------|--------|
| `total_trades` | Tổng số giao dịch |
| `win_rate` | Tỷ lệ giao dịch có lãi |
| `total_pnl` | Tổng P&L (USD) |
| `sharpe_ratio` | Risk-adjusted return |
| `max_drawdown` | Mức giảm vốn tối đa (%) |
| `profit_factor` | Gross profit / Gross loss |

## Chạy tests

```bash
pytest tests/test_backtest.py -v
```
