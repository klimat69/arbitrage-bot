# Services

Tầng business logic của bot. Mỗi service đảm nhiệm một trách nhiệm riêng biệt.

## Các file

| File | Mô tả |
|------|--------|
| `exchange_service.py` | Kết nối các sàn (Binance, KuCoin, OKX, Bybit) qua ccxt/ccxt.pro |
| `balance_service.py` | Quản lý số dư trên các sàn, khởi tạo và cập nhật balance files |
| `order_service.py` | Đặt lệnh đồng bộ với timeout và kiểm tra fill |
| `async_order_service.py` | Đặt lệnh bất đồng bộ — mua/bán song song nhiều sàn cùng lúc |
| `database_service.py` | Lưu trữ SQLite: sessions, trades, opportunities, balance snapshots |
| `notification_service.py` | Thông báo qua Telegram (cơ hội, giao dịch, lỗi) |
| `risk_manager.py` | Quản lý rủi ro: max drawdown, lỗ liên tiếp, cooldown, circuit breaker |
| `rate_limiter.py` | Giới hạn API calls bằng token bucket, cấu hình per exchange |
| `multi_pair_manager.py` | Chạy arbitrage đồng thời trên nhiều cặp giao dịch |

## Nguyên tắc

- Service **không import** service khác trực tiếp — nhận qua constructor (DI)
- Database connections dùng **context manager**: `with self._get_connection() as conn:`
- SQL dùng **parameterized queries** — không bao giờ dùng f-string
- Exchange I/O dùng **async/await** (ccxt.pro)
- Errors dùng custom exceptions từ `utils/exceptions.py`

## Sơ đồ quan hệ

```
Bot
├── ExchangeService     ← ccxt/ccxt.pro
├── BalanceService      ← balance.txt, start_balance.txt
├── OrderService        ← ExchangeService
├── AsyncOrderService   ← ExchangeService
├── DatabaseService     ← SQLite (data/arbitrage.db)
├── NotificationService ← Telegram API
├── RiskManager         ← configs.RISK_CONFIG
└── MultiPairManager    ← Bot factory + nhiều pairs
```
