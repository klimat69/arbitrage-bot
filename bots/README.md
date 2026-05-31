# Bots

Các bot giao dịch arbitrage crypto. Tất cả kế thừa từ `BaseBot`.

## Kiến trúc

```
BaseBot (base_bot.py)
├── ClassicBot (classic_bot.py)        # Arbitrage cổ điển
├── DeltaNeutralBot (delta_neutral_bot.py)  # Delta-neutral hedging
└── FakeMoneyBot (fake_money_bot.py)   # Mô phỏng (tiền ảo)
```

## Các file

| File | Mô tả |
|------|--------|
| `base_bot.py` | Lớp cơ sở — khởi tạo services, vòng lặp orderbook, quản lý session |
| `classic_bot.py` | Mua sàn giá thấp, bán sàn giá cao |
| `delta_neutral_bot.py` | Kết hợp spot arbitrage + short futures để hedge rủi ro giá |
| `fake_money_bot.py` | Mô phỏng giao dịch với tiền ảo, không đặt lệnh thật |
| `demo_fake_bot.py` | Script demo chạy standalone — dữ liệu thực, không cần API key |

## Cách chạy

```bash
# Qua main.py (đầy đủ)
python main.py fake-money 5 1000 binance okx bybit BTC/USDT

# Demo nhanh (không cần .env)
python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit
```

## Luồng hoạt động

1. Bot nhận services qua constructor (dependency injection)
2. `configure()` — thiết lập symbol, exchanges, timeout, vốn
3. `start()` — tạo session DB → khởi tạo balance → chạy orderbook loop
4. `process_orderbook()` — so sánh giá giữa các sàn → phát hiện cơ hội
5. `execute_trade()` — đặt lệnh mua/bán (hoặc mô phỏng với FakeMoneyBot)
6. `stop()` — kết thúc session, ghi kết quả vào DB
