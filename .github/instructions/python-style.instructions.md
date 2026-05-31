---
description: "Use when editing Python files in this project."
applyTo: "**/*.py"
---

# Python Code Style Instructions

## Conventions

- Type hints bắt buộc cho tất cả function signatures
- Import typing: `from typing import Any, Optional, Union, Generator, Callable`
- Docstrings tiếng Việt cho tất cả public classes và methods
- Tên biến, hàm, class bằng tiếng Anh

## Error Handling

- Dùng custom exceptions từ `utils/exceptions.py`: ArbitrageError, ExchangeError, InsufficientBalanceError, OrderError, ConfigError
- KHÔNG dùng bare `except:` — luôn bắt exception cụ thể
- Log errors qua `utils/logger.py`: log_info, log_error, log_warning, log_profit

## Database

- SQLite qua `services/database_service.py`
- Context manager: `with self._get_connection() as conn:`
- Parameterized queries only: `cursor.execute("SELECT * FROM t WHERE id = ?", (id,))`
- KHÔNG BAO GIỜ dùng f-string cho SQL

## Async

- Dùng `async/await` cho tất cả exchange I/O (ccxt.pro)
- Dùng `asyncio.gather()` cho parallel operations
- Exchange connections phải được close trong `finally` block

## Testing

- Mỗi module mới phải có test file tương ứng trong `tests/`
- Chạy: `pytest tests/ -v`
- Mock ccxt exchanges, KHÔNG gọi API thật trong tests
