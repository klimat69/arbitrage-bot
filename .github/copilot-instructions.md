# BMLB Arbitrage Bot — Project Guidelines

## Architecture
- **Python 3.10+** crypto arbitrage bot chạy trên Windows/Linux
- Exchanges: Binance, KuCoin, OKX, Bybit (qua ccxt/ccxt.pro)
- Database: SQLite (lịch sử giao dịch, phiên, thống kê)
- Web Dashboard: FastAPI + Jinja2 (REST API + HTML dashboard)
- Bot modes: `classic`, `delta-neutral`, `fake-money`
- Async: asyncio + ccxt.pro cho WebSocket orderbook

## Project Structure
```
bots/               # Bot implementations (base → classic, delta-neutral, fake-money)
services/           # Business logic services
  ├── exchange_service.py       # Kết nối & quản lý sàn (ccxt.pro)
  ├── balance_service.py        # Quản lý số dư
  ├── order_service.py          # Đặt lệnh đồng bộ
  ├── async_order_service.py    # Đặt lệnh bất đồng bộ
  ├── database_service.py       # SQLite persistence
  ├── notification_service.py   # Telegram notification
  ├── risk_manager.py           # Stop-loss & risk management
  ├── rate_limiter.py           # Rate limiting middleware
  └── multi_pair_manager.py     # Giao dịch đa cặp
utils/              # Helpers, exceptions, logger, env_loader
backtest/           # Backtesting framework (data_recorder, engine, analyzer)
web/                # FastAPI dashboard (app.py, templates/)
tests/              # pytest test suite (12 files, 221+ tests)
configs.py          # Global configuration
main.py             # Entry point
```

## Code Style
- **Vietnamese**: Comments, docstrings, UI text, thông báo lỗi người dùng
- **English**: Variable names, function names, class names, module names
- Type hints cho tất cả function signatures
- Docstrings cho tất cả public classes và methods
- Dùng `async/await` cho tất cả I/O operations
- Context managers cho database connections (`with self._get_connection() as conn:`)
- Custom exceptions trong `utils/exceptions.py`
- Logging qua `utils/logger.py` (log_info, log_error, log_warning, log_profit)

## Key Patterns
- **Inheritance**: BaseBot → ClassicBot, DeltaNeutralBot, FakeMoneyBot
- **Service Layer**: Services tách biệt — exchange, balance, order, database, notification
- **Risk Management**: Drawdown limits, consecutive loss limits, cooldown periods
- **Rate Limiting**: Token bucket per exchange, configurable rates
- **Multi-pair**: Concurrent arbitrage across multiple trading pairs
- **Async Orders**: Parallel order execution trên nhiều sàn cùng lúc
- **Slippage Tracking**: Theo dõi chênh lệch giữa expected vs actual price

## Async Contract (Quan trọng)
- `ExchangeService` I/O với sàn là async (`get_ticker`, `get_balance`, `get_global_average_price`, ccxt.pro methods)
- `BalanceService.check_balances()` và `BalanceService.get_balance()` là async; bot code PHẢI `await`
- Không so sánh trực tiếp coroutine với số (`float`) trong luồng khởi tạo bot
- Khi migrate sync → async, cập nhật đồng thời call sites trong bot + test integration

## Sandbox/Testnet
- Dùng `USE_SANDBOX=true` để bật sandbox mode cho ccxt/ccxt.pro
- Khi bật sandbox, ưu tiên biến môi trường `*_TESTNET_*` trước biến production
- Biến được hỗ trợ:
  - `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_SECRET`
  - `KUCOIN_TESTNET_API_KEY`, `KUCOIN_TESTNET_SECRET`, `KUCOIN_TESTNET_PASSWORD`
  - `OKX_TESTNET_API_KEY`, `OKX_TESTNET_SECRET`, `OKX_TESTNET_PASSWORD`
  - `BYBIT_TESTNET_API_KEY`, `BYBIT_TESTNET_SECRET`
- Không dùng production key cho smoke test mode thật

## Database
- SQLite with WAL mode, foreign keys ON
- Tables: sessions, trades, opportunities, balance_snapshots
- Context manager pattern: `_get_connection()` yields `sqlite3.Connection`
- Parameterized queries only — KHÔNG bao giờ dùng f-string cho SQL

## Web Dashboard
- FastAPI + Jinja2 templates
- Starlette 1.0.0: `TemplateResponse(request, "name.html", context={...})`
- REST API endpoints: `/api/sessions`, `/api/trades`, `/api/stats`
- HTML dashboard: `/`

## Security
- Credentials trong `.env`, KHÔNG commit lên git
- Exchange API keys qua environment variables
- Input validation cho tất cả API endpoints
- OWASP compliance: parameterized queries, no hardcoded secrets

## Build & Run
```bash
pip install -r requirements.txt
python main.py                              # Run bot (interactive mode)
python main.py --mode classic               # Run classic arbitrage
python main.py --mode fake-money            # Run with fake money (testing)
pytest tests/ -v                            # Run all tests
pytest tests/test_backtest.py -v            # Run backtest tests
```

## Testing
- pytest + pytest-asyncio
- 12 test files, 221+ tests
- Tests trong `tests/` directory
- Mock ccxt exchanges cho unit tests
- `pytest tests/ -v` từ project root
- Với thay đổi async contract, chạy thêm: `pytest tests/test_integration.py -q`

## Smoke Test Checklist
- Luôn chạy với `--no-recovery` để tránh prompt tương tác khi test tự động
- Ưu tiên sandbox/testnet key + vốn nhỏ + thời gian ngắn
- Lệnh tham chiếu:
  - `USE_SANDBOX=true python main.py classic 1 50 binance kucoin okx BTC/USDT --no-recovery`
  - `USE_SANDBOX=true python main.py delta-neutral 1 50 binance kucoin okx BTC/USDT --no-recovery`

## Configuration
- `configs.py`: Global settings (exchanges, fees, risk, paths)
- `.env`: Credentials (API keys, Telegram token)
- `SUPPORTED_EXCHANGES`: kucoin, binance, bybit, okx, kucoinfutures
- `EXCHANGE_FEES`: Fee config per exchange
- `RISK_CONFIG`: Drawdown, loss limits, cooldown settings
- `BOT_MODES`: fake-money, classic, delta-neutral
