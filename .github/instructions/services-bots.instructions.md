---
description: "Use when editing bot implementations or service layer."
applyTo: "{bots,services}/**/*.py"
---

# Services & Bots Instructions

## Bot Architecture

- `BaseBot` → `ClassicBot`, `DeltaNeutralBot`, `FakeMoneyBot`
- Bot nhận services qua constructor (dependency injection)
- Mỗi bot có `run()` method chính và các helper methods

## Service Layer

| Service | Trách nhiệm |
|---------|-------------|
| `ExchangeService` | Kết nối ccxt.pro, fetch orderbook |
| `BalanceService` | Đọc/ghi balance files |
| `OrderService` | Đặt lệnh đồng bộ |
| `AsyncOrderService` | Đặt lệnh song song nhiều sàn |
| `DatabaseService` | SQLite CRUD (sessions, trades) |
| `NotificationService` | Telegram alerts |
| `RiskManager` | Stop-loss, drawdown, cooldown |
| `RateLimiter` | Token bucket per exchange |
| `MultiPairManager` | Nhiều trading pairs đồng thời |

## Quy tắc

- Service KHÔNG import service khác trực tiếp — nhận qua constructor
- Bot quản lý lifecycle: start session → trade → end session
- RiskManager.check_risk() phải được gọi TRƯỚC mỗi giao dịch
- DatabaseService.record_trade() phải được gọi SAU mỗi giao dịch
- Luôn close exchange connections trong bot.cleanup()
- Các hàm đọc số dư/giá từ sàn phải dùng async end-to-end (`await` ở bot level)
- `BalanceService.check_balances()` và `BalanceService.get_balance()` là async, không gọi kiểu sync
- Khi bật sandbox (`USE_SANDBOX=true`), bot vẫn giữ nguyên flow, chỉ đổi credential sang `*_TESTNET_*`
