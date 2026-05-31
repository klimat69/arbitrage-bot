# Skill: Run Backtest# Skill: Run Backtest















































































- `slippage_pct` mô phỏng slippage thực tế- `initial_balance` ảnh hưởng đến position sizing (40% cho crypto init)- Spread test data phải > fee threshold (ví dụ: spread 200 USD vs fee ~100 USD)## Lưu ý```pytest tests/test_backtest.py -v```bash## Validation```print(comparison)comparison = BacktestAnalyzer.compare_results(results))    slippages=[0.05, 0.1]    min_spreads=[0.1, 0.2, 0.3],    fee_rates=[0.001, 0.0015],    exchanges=['binance', 'kucoin'],    symbol='BTC/USDT',results = engine.run_parameter_sweep(```python### Bước 4: Parameter sweep (tùy chọn)```# Metrics: total_trades, win_rate, sharpe_ratio, max_drawdown, profit_factorprint(report)report = analyzer.generate_report()analyzer = BacktestAnalyzer(result)from backtest.analyzer import BacktestAnalyzer```python### Bước 3: Phân tích kết quả```result = engine.run(symbol='BTC/USDT', exchanges=['binance', 'kucoin']))    slippage_pct=0.05    min_spread_pct=0.1,    fee_rate=0.001,    initial_balance=10000.0,    recorder=recorder,engine = BacktestEngine(from backtest.engine import BacktestEngine```python### Bước 2: Chạy backtest```)    spread_range=(50.0, 300.0)    base_price=50000.0,    num_snapshots=1000,    exchanges=['binance', 'kucoin'],    symbol='BTC/USDT',recorder.generate_sample_data(# Tạo dữ liệu mẫurecorder = DataRecorder(db_path=':memory:')from backtest.data_recorder import DataRecorder```python### Bước 1: Tạo hoặc load dữ liệu## Cách thực hiện- So sánh các bộ tham số khác nhau- Cần đánh giá hiệu suất trước khi chạy real money- User yêu cầu backtest chiến lược giao dịch## Khi nào sử dụngChạy backtest để đánh giá chiến lược arbitrage trên dữ liệu lịch sử.
Chạy backtest cho crypto arbitrage bot với dữ liệu lịch sử hoặc synthetic data.

## When to Use

- Khi cần đánh giá hiệu suất chiến lược arbitrage
- Khi cần so sánh tham số (parameter sweep)
- Khi cần validate thay đổi logic giao dịch

## Prerequisites

- Python 3.10+, các dependencies trong `requirements.txt` đã cài
- Module `backtest/` có sẵn: `data_recorder.py`, `engine.py`, `analyzer.py`

## Instructions

### Bước 1: Tạo hoặc load dữ liệu

```python
from backtest.data_recorder import DataRecorder

recorder = DataRecorder(db_path=':memory:')
# Synthetic data với 500 snapshots, spread 100-300 USD
recorder.generate_sample_data(
    symbol='BTC/USDT',
    exchanges=['binance', 'kucoin'],
    num_snapshots=500,
    base_price=50000.0,
    spread_range=(100, 300)
)
```

### Bước 2: Chạy backtest

```python
from backtest.engine import BacktestEngine

engine = BacktestEngine(
    data_source=recorder,
    initial_balance=10000.0,
    fee_rate=0.001,
    min_spread_pct=0.1,
    slippage_pct=0.05
)
result = engine.run(symbol='BTC/USDT', exchanges=['binance', 'kucoin'])
```

### Bước 3: Phân tích kết quả

```python
from backtest.analyzer import BacktestAnalyzer

analyzer = BacktestAnalyzer()
analyzer.add_result('default', result)
report = analyzer.generate_report('default')
print(report)
```

### Bước 4: Parameter sweep

```python
results = engine.run_parameter_sweep(
    symbol='BTC/USDT',
    exchanges=['binance', 'kucoin'],
    fee_rates=[0.001, 0.0015, 0.002],
    min_spreads=[0.05, 0.1, 0.2]
)
comparison = analyzer.compare_results(results)
print(comparison)
```

## Key Metrics

| Metric | Mô tả | Tốt |
|--------|--------|-----|
| `win_rate` | Tỷ lệ giao dịch có lãi | > 60% |
| `sharpe_ratio` | Risk-adjusted return | > 1.0 |
| `max_drawdown` | Mức giảm vốn tối đa | < 5% |
| `profit_factor` | Gross profit / Gross loss | > 1.5 |
| `total_pnl` | Tổng lợi nhuận (USD) | > 0 |

## Verify

Chạy tests để đảm bảo backtest module hoạt động:
```bash
pytest tests/test_backtest.py -v
```
