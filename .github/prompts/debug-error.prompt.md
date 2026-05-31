---
description: "Debug lỗi giao dịch hoặc bot crash theo quy trình có hệ thống"
---

# Debug Lỗi

## Mô tả lỗi

{{ error_description }}

## Quy trình debug

1. **Thu thập thông tin**: Đọc logs trong `logs/`, kiểm tra traceback
2. **Tái tạo lỗi**: Viết test case tái tạo lỗi trong `tests/`
3. **Phân tích**: Tìm root cause trong code
4. **Fix**: Sửa lỗi, đảm bảo không break code khác
5. **Verify**: Chạy `pytest tests/ -v` — tất cả tests phải pass
6. **Regression test**: Thêm test case cho lỗi vào `tests/test_bug_fixes.py`

## Nơi kiểm tra theo loại lỗi

| Loại lỗi | File kiểm tra |
|-----------|--------------|
| Exchange connection | `services/exchange_service.py` |
| Order fails | `services/order_service.py`, `services/async_order_service.py` |
| Balance sai | `services/balance_service.py` |
| Risk trigger | `services/risk_manager.py` |
| Database error | `services/database_service.py` |
| Backtest crash | `backtest/engine.py` |
| Web dashboard | `web/app.py` |
| Config error | `configs.py`, `utils/env_loader.py` |
