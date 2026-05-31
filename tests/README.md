# Tests

Test suite cho dự án arbitrage bot. Sử dụng pytest + pytest-asyncio.

## Tổng quan

- **12 test files**, **221+ test cases**
- Mock ccxt exchanges — không gọi API thật
- SQLite in-memory cho database tests

## Các file

| File | Module | Tests |
|------|--------|-------|
| `test_backtest.py` | Backtest engine, data recorder, analyzer | 30 |
| `test_bug_fixes.py` | Regression tests cho các bug đã fix | — |
| `test_configs.py` | Cấu hình, exchanges, fees | — |
| `test_database_service.py` | SQLite CRUD, sessions, trades | — |
| `test_exceptions.py` | Custom exception classes | — |
| `test_helpers.py` | Utility functions | — |
| `test_integration.py` | Tích hợp nhiều services + bot | — |
| `test_multi_pair.py` | Multi-pair trading manager | — |
| `test_rate_limiter.py` | Token bucket rate limiting | — |
| `test_risk_manager.py` | Risk management rules | — |
| `test_slippage.py` | Slippage tracking & calculation | — |
| `test_web_dashboard.py` | FastAPI endpoints, dashboard | 20 |

## Chạy

```bash
# Tất cả tests
pytest tests/ -v

# Một file cụ thể
pytest tests/test_backtest.py -v

# Dừng khi gặp lỗi đầu tiên
pytest tests/ -v -x

# Filter theo tên
pytest tests/ -v -k "test_risk"

# Với coverage
pytest tests/ -v --cov=.
```
