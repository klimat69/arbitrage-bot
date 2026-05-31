---
description: "Tối ưu hiệu suất bot: giảm latency, tăng throughput, cải thiện profit"
---

# Tối Ưu Hiệu Suất

## Mục tiêu

{{ optimization_goal }}

## Các hướng tối ưu

### 1. Giảm latency giao dịch
- Kiểm tra `services/async_order_service.py` — đặt lệnh song song
- Kiểm tra `services/rate_limiter.py` — rate limit có quá chặt?
- Dùng WebSocket (`ccxt.pro`) thay REST API cho orderbook

### 2. Tăng profit
- Phân tích fee structure trong `configs.py` EXCHANGE_FEES
- Kiểm tra `min_spread_pct` trong backtest — có quá cao?
- Review slippage tracking trong `services/order_service.py`

### 3. Giảm risk
- Review `services/risk_manager.py` RISK_CONFIG
- Kiểm tra max_drawdown_pct, max_consecutive_losses
- Backtest với parameter sweep để tìm optimal risk params

## Validate

```bash
# Chạy backtest trước/sau để so sánh
pytest tests/test_backtest.py -v

# Chạy tất cả tests
pytest tests/ -v
```
