# Crypto Arbitrage Bot

Bot giao dịch chênh lệch giá crypto tự động giữa nhiều sàn. Hỗ trợ Binance, KuCoin, OKX, Bybit.

## Tính năng

- **3 chế độ bot**: Classic arbitrage, Delta-neutral hedging, Fake money (mô phỏng)
- **Realtime orderbook**: WebSocket qua ccxt.pro, phát hiện cơ hội tức thì
- **Đặt lệnh song song**: Mua/bán đồng thời trên nhiều sàn (async orders)
- **Multi-pair**: Giao dịch nhiều cặp tiền cùng lúc
- **Risk management**: Max drawdown, lỗ liên tiếp, cooldown, circuit breaker
- **Rate limiting**: Token bucket per exchange, tránh bị ban API
- **Slippage tracking**: So sánh giá kỳ vọng vs giá thực tế
- **Database**: SQLite lưu lịch sử sessions, trades, opportunities
- **Web dashboard**: FastAPI + Jinja2 theo dõi giao dịch qua trình duyệt
- **Backtesting**: Replay dữ liệu lịch sử, parameter sweep, phân tích metrics
- **Telegram alerts**: Thông báo cơ hội, giao dịch, lỗi qua Telegram
- **Session Recovery**: 🆕 Khôi phục tự động phiên bị dừng do lỗi hoặc ngắt kết nối

## Cấu trúc dự án

```
bmlb-arbitrage-bot/
├── main.py                 # Entry point
├── configs.py              # Cấu hình: exchanges, fees, risk, paths
├── requirements.txt        # Dependencies
│
├── bots/                   # Bot implementations
│   ├── base_bot.py         #   Lớp cơ sở (orderbook loop, session management)
│   ├── classic_bot.py      #   Mua sàn giá thấp → bán sàn giá cao
│   ├── delta_neutral_bot.py#   Spot arbitrage + short futures hedge
│   ├── fake_money_bot.py   #   Mô phỏng, không đặt lệnh thật
│   └── demo_fake_bot.py    #   Demo standalone (không cần API key)
│
├── services/               # Business logic
│   ├── exchange_service.py #   Kết nối sàn (ccxt/ccxt.pro)
│   ├── balance_service.py  #   Quản lý số dư
│   ├── order_service.py    #   Đặt lệnh đồng bộ
│   ├── async_order_service.py# Đặt lệnh bất đồng bộ (song song)
│   ├── database_service.py #   SQLite persistence
│   ├── notification_service.py# Telegram alerts
│   ├── risk_manager.py     #   Stop-loss & risk management
│   ├── rate_limiter.py     #   Token bucket rate limiting
│   └── multi_pair_manager.py#  Giao dịch đa cặp đồng thời
│
├── backtest/               # Backtesting framework
│   ├── data_recorder.py    #   Ghi orderbook vào SQLite
│   ├── engine.py           #   Replay engine + parameter sweep
│   └── analyzer.py         #   Phân tích: win rate, Sharpe, drawdown
│
├── web/                    # Web dashboard
│   ├── app.py              #   FastAPI app (REST API + HTML)
│   └── templates/          #   Jinja2 templates
│
├── utils/                  # Tiện ích
│   ├── exceptions.py       #   Custom exceptions
│   ├── helpers.py          #   Hàm tiện ích
│   ├── logger.py           #   Logging có màu + file
│   └── env_loader.py       #   Load .env
│
├── tests/                  # 12 test files, 221+ tests
├── data/                   # SQLite database (auto-created)
└── logs/                   # Log files (auto-created)
```

## Cài đặt

```bash
git clone https://github.com/nguyenngocbinhneu/bmlb-arbitrage-bot.git
cd bmlb-arbitrage-bot
pip install -r requirements.txt
```

## Hướng dẫn cho người mới

Người mới nên bắt đầu bằng paper trading trước khi cấu hình API key thật.

- Tài liệu đầy đủ: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
- **Khôi phục phiên bị dừng**: [docs/SESSION_RECOVERY.md](docs/SESSION_RECOVERY.md) 🆕
- Hướng dẫn trên web: chạy `python -m uvicorn web.app:app --reload --port 8000`, rồi mở `http://localhost:8000/getting-started`
- Lệnh an toàn đầu tiên: `python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit --duration 5`

Thứ tự kiểm thử khuyến nghị:

1. Chạy demo fake-money standalone.
2. Chạy mode `fake-money` và xem kết quả trên dashboard.
3. Test command dạng `classic` hoặc `delta-neutral` với `--dry-run`.
4. Chỉ cân nhắc live trading sau khi đã hiểu logs, phí, slippage, quyền API key, và giới hạn rủi ro.

## Mở tài khoản sàn

Nếu bạn chưa có tài khoản trên các sàn được bot hỗ trợ, có thể đăng ký qua các link giới thiệu sau:

| Sàn | Link đăng ký |
|-----|-------------|
| Binance | [Mở tài khoản Binance](https://www.binance.com/vi/referral/earn-together/refer2earn-usdc/claim?hl=vi&ref=GRO_28502_F9YAO&utm_source=referral_entrance) |
| Bybit | [Mở tài khoản Bybit](https://www.bybitglobal.com/invite?ref=LJ7X7P) |
| OKX | [Mở tài khoản OKX](https://www.okx.com/vi/join/8978408) |
| KuCoin | [Mở tài khoản KuCoin](https://www.kucoin.com/ucenter/signup?rcode=QBSYA6AQ&utm_source=rf) |

Các link trên có thể là link giới thiệu. Hãy tự kiểm tra điều khoản, phí, khu vực hỗ trợ, KYC và quyền API của từng sàn trước khi dùng.

## Cấu hình

Tạo file `.env` trong thư mục gốc:

```env
# Exchange API keys (cần cho classic/delta-neutral mode)
BINANCE_API_KEY=your_key
BINANCE_SECRET=your_secret

KUCOIN_API_KEY=your_key
KUCOIN_SECRET=your_secret
KUCOIN_PASSWORD=your_password

OKX_API_KEY=your_key
OKX_SECRET=your_secret
OKX_PASSWORD=your_password

BYBIT_API_KEY=your_key
BYBIT_SECRET=your_secret

# Telegram (tùy chọn)
TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id
```

## Sử dụng

### Demo nhanh (không cần API key)

```bash
# Dữ liệu thực từ sàn, tiền giả
python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit --duration 5
```

### Dry-run / paper trading an toàn

Có 2 cách test an toàn trước khi giao dịch thật:

1. Dùng `fake-money`: chạy bot theo luồng đầy đủ nhưng mô phỏng giao dịch bằng tiền giả.
2. Thêm `--dry-run`: ép `classic` hoặc `delta-neutral` chạy qua `FakeMoneyBot`, không gửi lệnh thật.

```bash
# Paper trading đầy đủ, không cần đặt lệnh thật
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Test command classic nhưng vẫn không đặt lệnh thật
python main.py classic 15 1000 binance kucoin okx BTC/USDT --dry-run

# Test command delta-neutral nhưng vẫn không đặt lệnh thật
python main.py delta-neutral 15 1000 binance kucoin okx BTC/USDT --dry-run
```

Sau khi chạy paper trading, mở dashboard để xem session, simulated trades, PnL, phí và slippage:

```bash
python -m uvicorn web.app:app --reload --port 8000
# Dashboard: http://localhost:8000/dashboard
```

Không chạy live mode nếu bạn chưa kiểm tra dashboard, chưa hiểu phí/slippage, hoặc API key vẫn có quyền rút tiền.

### Chạy bot đầy đủ

```bash
# Fake money — mô phỏng với dữ liệu thực
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Classic arbitrage — giao dịch thật (cần API keys)
python main.py classic 15 1000 binance kucoin okx BTC/USDT

# Delta-neutral — spot + futures hedge
python main.py delta-neutral 15 1000 binance kucoin okx BTC/USDT

# Multi-pair
python main.py fake-money 15 1000 binance kucoin okx --symbols BTC/USDT ETH/USDT SOL/USDT
```

**Tham số**:
| Tham số | Mô tả |
|---------|--------|
| `mode` | `fake-money`, `classic`, `delta-neutral` |
| `renew_time` | Thời gian mỗi phiên (phút) |
| `usdt_amount` | Vốn USDT |
| `exchange1-3` | 3 sàn giao dịch |
| `symbol` | Cặp tiền (tùy chọn, tự tìm nếu bỏ trống) |
| `--symbols` | Nhiều cặp tiền cho multi-pair mode |
| `--debug` | Bật debug logging |
| `--dry-run` | Chạy không đặt lệnh thật |

### Web Dashboard

```bash
python -m uvicorn web.app:app --reload --port 8000
# Landing page: http://localhost:8000
# Hướng dẫn người mới: http://localhost:8000/getting-started
# Dashboard: http://localhost:8000/dashboard
# API docs: http://localhost:8000/docs
```

### Lỗi thường gặp

**`[WinError 10013]` khi chạy Uvicorn trên port 8000**

Lỗi này thường xảy ra khi port `8000` đang được một phiên Uvicorn khác dùng, hoặc Windows đang chặn socket đó.

Kiểm tra dashboard có đang chạy sẵn không:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Nếu trả về `ok`, mở dashboard tại:

```text
http://127.0.0.1:8000/dashboard
```

Nếu muốn dừng process cũ:

```powershell
netstat -ano | Select-String ':8000'
Stop-Process -Id <PID>
```

Hoặc chạy dashboard bằng port khác:

```powershell
python -m uvicorn web.app:app --reload --port 8001
```

### Backtesting

```python
from backtest.data_recorder import DataRecorder
from backtest.engine import BacktestEngine
from backtest.analyzer import BacktestAnalyzer

recorder = DataRecorder(db_path=':memory:')
recorder.generate_sample_data('BTC/USDT', ['binance', 'kucoin'], 500, 50000.0, (100, 300))

engine = BacktestEngine(data_source=recorder, initial_balance=10000.0, fee_rate=0.001)
result = engine.run(symbol='BTC/USDT', exchanges=['binance', 'kucoin'])

analyzer = BacktestAnalyzer()
analyzer.add_result('test', result)
print(analyzer.generate_report('test'))
```

## Testing

```bash
# Tất cả tests (221+ tests)
pytest tests/ -v

# Một module cụ thể
pytest tests/test_backtest.py -v
pytest tests/test_risk_manager.py -v

# Dừng khi gặp lỗi
pytest tests/ -v -x
```

## Sàn hỗ trợ

| Sàn | Spot | Futures | Phí mặc định |
|-----|------|---------|-------------|
| Binance | ✅ | — | 0.1% / 0.1% |
| KuCoin | ✅ | ✅ | 0.1% / 0.1% |
| OKX | ✅ | — | 0.08% / 0.1% |
| Bybit | ✅ | — | 0.1% / 0.1% |

## Risk Management

Cấu hình trong `configs.py` → `RISK_CONFIG`:

| Tham số | Mặc định | Mô tả |
|---------|----------|--------|
| `max_drawdown_pct` | 5% | Drawdown tối đa trước khi dừng |
| `max_loss_per_trade_usd` | $10 | Lỗ tối đa mỗi giao dịch |
| `max_session_loss_pct` | 3% | Lỗ tối đa trong phiên |
| `max_consecutive_losses` | 5 | Lỗ liên tiếp tối đa |
| `max_slippage_pct` | 0.5% | Slippage cho phép |
| `cooldown_after_loss_sec` | 30s | Cooldown sau lỗ lớn |

## License

**BMLB Arbitrage Bot License v1.0** — Xem chi tiết tại [LICENSE](LICENSE).

| Đối tượng | Phí |
|-----------|-----|
| Cá nhân | Miễn phí |
| Tổ chức phi lợi nhuận / giáo dục | Miễn phí |
| Doanh nghiệp (doanh thu < $1M/năm) | Miễn phí |
| Doanh nghiệp (doanh thu $1M — $10M) | $5,000/năm |
| Doanh nghiệp (doanh thu $10M — $50M) | $15,000/năm |
| Doanh nghiệp (doanh thu > $50M) | $30,000/năm |

Copyright (c) 2026 Nguyễn Ngọc Bình. All Rights Reserved.

## Liên hệ

- GitHub: [nguyenngocbinhneu](https://github.com/nguyenngocbinhneu)
- Issues: [Mở issue](https://github.com/nguyenngocbinhneu/bmlb-arbitrage-bot/issues)
