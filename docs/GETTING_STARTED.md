# Beginner Guide

This guide is for new users who want to test BMLB Arbitrage Bot safely before any live trading.

## The safe path

Use this order:

1. Run the standalone fake-money demo.
2. Run a full `fake-money` bot session.
3. Open the dashboard and review sessions, trades, fees, PnL, and slippage.
4. Test the same command shape with `--dry-run`.
5. Only consider live trading after you understand the results and risks.

## Mode overview

| Mode | What it does | Beginner safe? |
|------|--------------|----------------|
| `python -m bots.demo_fake_bot` | Uses live market data with fake money and no exchange API keys. | Yes |
| `fake-money` | Runs the normal bot flow through `FakeMoneyBot`; simulated trades are recorded for review. | Yes |
| `--dry-run` | Forces `classic` or `delta-neutral` commands to use `FakeMoneyBot`. | Yes |
| `classic` | Can place real spot arbitrage orders when API keys are configured. | No |
| `delta-neutral` | Can place real spot/futures hedge orders when API keys are configured. | No |

## 1. Install

```bash
git clone https://github.com/nguyenngocbinhneu/bmlb-arbitrage-bot.git
cd bmlb-arbitrage-bot
pip install -r requirements.txt
```

For your first run, do not add real exchange API keys. The fake-money demo does not need them.

## Exchange account links

If you do not already have exchange accounts, these referral links can be used to sign up:

| Exchange | Sign-up link |
|----------|--------------|
| Binance | [Open Binance account](https://www.binance.com/vi/referral/earn-together/refer2earn-usdc/claim?hl=vi&ref=GRO_28502_F9YAO&utm_source=referral_entrance) |
| Bybit | [Open Bybit account](https://www.bybitglobal.com/invite?ref=LJ7X7P) |
| OKX | [Open OKX account](https://www.okx.com/vi/join/8978408) |
| KuCoin | [Open KuCoin account](https://www.kucoin.com/ucenter/signup?rcode=QBSYA6AQ&utm_source=rf) |

These may be referral links. Check each exchange's fees, regional availability, KYC rules, API permissions, and risk terms before using live trading features.

## 2. Run the safest demo

This reads live market data but does not place real orders.

```bash
python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit --duration 5
```

Use this to confirm that dependencies, exchange connectivity, and your local environment work.

## 3. Run full paper trading

`fake-money` uses the regular bot workflow but simulates trades.

```bash
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT
```

Then open the dashboard:

```bash
python -m uvicorn web.app:app --reload --port 8000
```

Open:

```text
http://localhost:8000/dashboard
```

### Common error: WinError 10013 on port 8000

If Uvicorn shows this error:

```text
ERROR:    [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions
```

Port `8000` is usually already being used by another Uvicorn process, or Windows is blocking that socket. Check whether the dashboard is already running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

If it returns `ok`, open:

```text
http://127.0.0.1:8000/dashboard
```

To stop the existing process, find the PID and stop it:

```powershell
netstat -ano | Select-String ':8000'
Stop-Process -Id <PID>
```

Or run the dashboard on another port:

```powershell
python -m uvicorn web.app:app --reload --port 8001
```

Review:

- sessions
- simulated trades
- estimated profit/loss
- fees
- slippage
- failed or skipped opportunities

## 4. Use dry-run before live modes

`--dry-run` is a safety flag. In `main.py`, when `--dry-run` is present, the bot creates `FakeMoneyBot` even if the selected mode is `classic` or `delta-neutral`.

```bash
# Same command shape as classic mode, but no real orders are sent.
python main.py classic 15 1000 binance kucoin okx BTC/USDT --dry-run

# Same command shape as delta-neutral mode, but still simulated.
python main.py delta-neutral 15 1000 binance kucoin okx BTC/USDT --dry-run
```

Use `--dry-run` to test the exact command you might later run live, while keeping execution simulated.

## 5. Multi-pair paper trading

Start with a small fake balance and a few liquid pairs.

```bash
python main.py fake-money 15 1000 binance kucoin okx --symbols BTC/USDT ETH/USDT SOL/USDT
```

You can also add `--dry-run` to classic or delta-neutral multi-pair commands.

## Before live trading

Do not run live trading until:

- you have completed fake-money tests on the same exchanges and symbols
- you have reviewed dashboard results
- you understand fee impact and slippage
- you have set risk limits in `configs.py`
- you have disabled withdrawals on exchange API keys
- you have tested with the smallest practical trade size
- you accept that live execution can differ from paper trading

## Risk disclaimer

BMLB Arbitrage Bot is research and automation software, not financial advice. Crypto trading can lose money due to market volatility, latency, fees, slippage, liquidity, partial fills, liquidation, exchange outages, and API failures. No profit is promised. Users are responsible for configuration, legal compliance, and all trading outcomes.
