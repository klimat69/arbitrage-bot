# Utils

Các module tiện ích dùng chung trong toàn bộ dự án.

## Các file

| File | Mô tả |
|------|--------|
| `exceptions.py` | Custom exceptions: `ArbitrageError`, `ExchangeError`, `InsufficientBalanceError`, `OrderError`, `ConfigError`, `FuturesError` |
| `helpers.py` | Hàm tiện ích: format thời gian, đọc/ghi file, tính trung bình, trích xuất base asset |
| `logger.py` | Logging tập trung: console có màu (colorama) + ghi file, các hàm `log_info`, `log_error`, `log_warning`, `log_profit` |
| `env_loader.py` | Load biến môi trường từ `.env` cho quản lý credentials an toàn |

## Sử dụng

```python
# Logging
from utils.logger import log_info, log_error, log_profit
log_info("Bắt đầu phiên giao dịch")
log_profit("Lợi nhuận: +0.05 USD")

# Exceptions
from utils.exceptions import ExchangeError, InsufficientBalanceError
raise ExchangeError("binance", "Không thể kết nối")

# Helpers
from utils.helpers import show_time, extract_base_asset
show_time()  # "14:30:25"
extract_base_asset("BTC/USDT")  # "BTC"
```
