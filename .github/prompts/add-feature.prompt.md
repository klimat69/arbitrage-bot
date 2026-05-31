---
description: "Thêm tính năng mới vào arbitrage bot theo đúng architecture"
---

# Thêm Tính Năng Mới

## Yêu cầu

Tính năng cần thêm: {{ feature_description }}

## Quy trình

1. **Phân tích**: Xác định tính năng thuộc layer nào (bot, service, util, backtest, web)
2. **Thiết kế**: Tạo class/function mới theo pattern có sẵn trong codebase
3. **Implement**: Code với type hints đầy đủ, docstrings tiếng Việt, tên biến tiếng Anh
4. **Tests**: Tạo test file trong `tests/` với coverage đầy đủ
5. **Verify**: Chạy `pytest tests/ -v` đảm bảo tất cả tests pass

## Checklist

- [ ] Type hints cho tất cả function signatures
- [ ] Docstrings tiếng Việt
- [ ] Error handling bằng custom exceptions (`utils/exceptions.py`)
- [ ] Logging qua `utils/logger.py`
- [ ] Test file với ít nhất 5 test cases
- [ ] Không hardcode secrets
- [ ] Parameterized queries cho SQL
