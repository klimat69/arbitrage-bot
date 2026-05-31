# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_database_service.py -v
pytest tests/test_risk_manager.py -v

# Stop on first failure
pytest tests/ -v -x

# Lint (CI threshold: score >= 5, warnings/refactors disabled)
pylint $(git ls-files '*.py') --disable=C,R --fail-under=5

# Run the bot (fake-money demo, no API keys needed)
python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit --duration 5

# Run the bot via main entry point
python main.py fake-money <renew_minutes> <usdt_amount> <exchange1> <exchange2> <exchange3> [symbol]
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT --dry-run

# Multi-pair mode
python main.py fake-money 15 1000 binance kucoin okx --symbols BTC/USDT ETH/USDT SOL/USDT

# Web dashboard
python -m uvicorn web.app:app --reload --port 8000
```

## Architecture

### Request flow

`main.py` parses CLI args → instantiates all services → creates the appropriate bot → calls `bot.configure()` then `bot.start()` in an async loop that repeats each `renew_time` minute session until interrupted.

On Windows, `aiohttp.ThreadedResolver` is forced at startup to avoid `aiodns` DNS errors.

### Bot hierarchy

```
BaseBot (bots/base_bot.py)
├── ClassicBot        — buy lowest-ask exchange, sell highest-bid exchange
├── DeltaNeutralBot   — spot arbitrage + short futures hedge on kucoinfutures
└── FakeMoneyBot      — full simulation with no real orders
```

`BaseBot._start_orderbook_loop()` fans out one `asyncio` task per exchange using `ccxt.pro.watch_order_book`. Each tick calls `process_orderbook()` which detects spread, checks `RiskManager`, then calls `_execute_trade()`. Real orders are placed via `AsyncOrderService.place_arbitrage_orders()` which fires buy and sell simultaneously with `asyncio.gather`.

`MultiPairManager` (services/multi_pair_manager.py) runs one bot instance per symbol in parallel for multi-pair mode.

### Services

| Service | Responsibility |
|---|---|
| `ExchangeService` | Wraps ccxt/ccxt.pro; reads API keys from env; token-bucket rate limiting per exchange; optional sandbox mode via `USE_SANDBOX=true` |
| `BalanceService` | Reads/writes `balance.txt` and `start_balance.txt`; emergency USDT conversion on Ctrl+C |
| `AsyncOrderService` | Concurrent limit/market order placement and fill-polling; returns slippage data |
| `OrderService` | Synchronous order placement fallback |
| `DatabaseService` | SQLite (WAL mode) at `data/arbitrage.db`; tables: sessions, trades, opportunities, balances |
| `RiskManager` | Pre/post-trade guards: max drawdown, per-trade loss, consecutive losses, slippage, cooldown |
| `NotificationService` | Telegram alerts; enabled by `ENABLE_TELEGRAM=true` |
| `SessionRecovery` | Detects `status='interrupted'` sessions in DB on startup and offers resume |
| `RateLimiter` | Token bucket per exchange (services/rate_limiter.py) |

### Configuration

All tunable constants live in `configs.py`:
- `PROFIT_CRITERIA_PCT` / `PROFIT_CRITERIA_USD` — minimum spread thresholds to fire a trade
- `EXCHANGE_FEES` — per-exchange maker/taker rates used in profit calculation
- `RISK_CONFIG` — drawdown, loss, slippage, cooldown limits
- `SUPPORTED_EXCHANGES` — `['kucoin', 'binance', 'bybit', 'okx', 'kucoinfutures']`

### Environment variables (`.env`)

```
BINANCE_API_KEY / BINANCE_SECRET
KUCOIN_API_KEY / KUCOIN_SECRET / KUCOIN_PASSWORD
OKX_API_KEY / OKX_SECRET / OKX_PASSWORD
BYBIT_API_KEY / BYBIT_SECRET
TELEGRAM_TOKEN / CHAT_ID
USE_SANDBOX=true          # routes to testnet keys (BINANCE_TESTNET_API_KEY etc.)
ENABLE_TELEGRAM=true
ENABLE_CTRL_C_HANDLING=true
```

### Backtest framework

`backtest/data_recorder.py` records live orderbook snapshots to SQLite. `backtest/engine.py` replays them and supports parameter sweeps. `backtest/analyzer.py` computes win rate, Sharpe ratio, and max drawdown. Tests in `tests/test_backtest.py`.

### Web dashboard

FastAPI app at `web/app.py` serves Jinja2 templates and a REST API. Key routes: `/dashboard`, `/getting-started`, `/docs` (OpenAPI). Reads from `DatabaseService` for session/trade history.

### Custom exceptions (`utils/exceptions.py`)

All exceptions inherit from `ArbitrageError`. Key types: `ExchangeError`, `InsufficientBalanceError`, `OrderError`, `OrderFillTimeoutError`, `FuturesError`, `DeltaNeutralError`.

## Testing notes

- Tests use `tempfile`-backed SQLite instances — never the live `data/arbitrage.db`.
- Exchange interactions are mocked with `unittest.mock.MagicMock` / `AsyncMock`; do not add real network calls to tests.
- CI runs on Python 3.10, 3.11, 3.12 (see `.github/workflows/pylint.yml`).
