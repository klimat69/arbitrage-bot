# Arbitrage Bot — Binance (signals) → MEXC (execution)

Production-ready crypto arbitrage bot built on the [bmlb-arbitrage-bot](https://github.com/nguyenngocbinhneu/bmlb-arbitrage-bot) framework, extended with large-order detection, advanced risk controls, Telegram alerts, cross-platform packaging, and license verification.

## Strategy

1. **Binance (signals)** — watches the incremental order book via `ccxt.pro` and detects large resting limit orders.
2. **Anti-spoofing (BTQuant-style)** — orders must remain visible for at least `ORDER_TTL_SECONDS` before a signal is emitted.
3. **MEXC (execution)** — on a validated signal, the bot opens a position on MEXC (buy on large bid wall, sell on large ask wall).
4. **Risk manager** — position size limits, daily loss cap, consecutive-loss circuit breaker.
5. **Telegram** — async notifications for signals, entries, closes, and critical errors.

## Requirements

- Python **3.11+**
- API keys for Binance and MEXC
- Valid license key (see [Licensing](#licensing))
- Optional: Telegram bot token

## Quick start

```bash
git clone https://github.com/klimat69/arbitrage-bot.git
cd arbitrage-bot
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in keys and license
```

Run in classic mode (Binance signal → MEXC execution):

```bash
python main.py classic 60 100 binance mexc mexc BTC/USDT
```

Arguments: `mode`, `renew_minutes`, `usdt_amount`, `exchange1`, `exchange2`, `exchange3`, `[symbol]`.

Dry-run (no real orders):

```bash
python main.py classic 60 100 binance mexc mexc BTC/USDT --dry-run
```

## Configuration (`.env`)

Copy `.env.example` to `.env`. Key variables:

| Variable | Description |
|----------|-------------|
| `SIGNAL_EXCHANGE` | Signal source (default: `binance`) |
| `EXECUTION_EXCHANGE` | Execution venue (default: `mexc`) |
| `LARGE_ORDER_THRESHOLD_BTC` | Min tracked order size (BTC equiv.) |
| `ORDER_TTL_SECONDS` | Anti-spoofing TTL |
| `MAX_POSITION_USDT` | Max position per symbol |
| `MAX_DAILY_LOSS_USDT` | Daily loss limit |
| `LICENSE_KEY` | Your license key |
| `LICENSE_SERVER_URL` | License verification endpoint |
| `TELEGRAM_API_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram alerts |

## Build standalone executable (PyInstaller)

Install dependencies (includes `pyinstaller`):

```bash
pip install -r requirements.txt
```

### Windows (.exe)

```bash
pyinstaller build_windows.spec
# Output: dist/arbitrage-bot.exe
```

### macOS Intel (.app)

```bash
pyinstaller build_macos_intel.spec
# Output: dist/arbitrage-bot.app
```

### macOS Apple Silicon (.app)

```bash
pyinstaller build_macos_arm.spec
# Output: dist/arbitrage-bot.app
```

Place a valid `.env` next to the executable (or set environment variables) before running.

## Licensing

On every startup the bot sends a POST request to `LICENSE_SERVER_URL`:

```json
{"license": "<LICENSE_KEY>", "hwid": "<machine-id>"}
```

If the server responds `{"valid": true}`, the bot runs. Otherwise it exits with an error message.

The result is cached in `license.cache` for **24 hours** (no auto-updates or version checks).

**To obtain a license key**, contact the bot author / your deployment provider with your hardware ID (printed on first failed check, or run `python -c "from utils.license import get_hardware_id; print(get_hardware_id())"`).

## Project structure

```
strategies/large_order_detector.py   # Large order + TTL anti-spoofing
risk/risk_manager.py                 # Advanced risk / circuit breaker
utils/telegram.py                    # Async Telegram notifier
utils/license.py                     # License verification + cache
bots/classic_bot.py                  # Binance → MEXC pipeline
build_*.spec                         # PyInstaller specs
```

## Tests

```bash
pytest tests/test_large_order_detector.py tests/test_advanced_risk_manager.py tests/test_license.py -q
```

## License

MIT — see [LICENSE](LICENSE). Original framework © nguyenngocbinhneu.
