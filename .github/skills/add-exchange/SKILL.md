# Skill: Add Exchange

Thêm sàn giao dịch mới vào hệ thống arbitrage bot.

## Khi nào sử dụng

- User muốn thêm sàn giao dịch mới (ví dụ: Gate.io, MEXC, Bitget)
- Cần cấu hình phí giao dịch cho sàn mới
- Cần tích hợp sàn mới vào bot

## Cách thực hiện

### Bước 1: Cập nhật configs.py

Thêm sàn vào `SUPPORTED_EXCHANGES` và `EXCHANGE_FEES`:

```python
# configs.py
SUPPORTED_EXCHANGES = ['kucoin', 'binance', 'bybit', 'okx', 'kucoinfutures', '<new_exchange>']

EXCHANGE_FEES = {
    # ... existing ...
    '<new_exchange>': {'give': 0.001, 'receive': 0.001},
}
```

### Bước 2: Kiểm tra ccxt support

```python
import ccxt
print('<new_exchange>' in ccxt.exchanges)  # Phải True
```

### Bước 3: Cập nhật ExchangeService (nếu cần)

Nếu sàn mới có API đặc biệt, thêm logic trong `services/exchange_service.py`:

```python
# Chỉ cần nếu sàn có quirks riêng
if exchange_id == '<new_exchange>':
    # Custom configuration
    pass
```

### Bước 4: Thêm tests

Thêm test cases trong `tests/test_configs.py`:

```python
def test_new_exchange_in_supported():
    assert '<new_exchange>' in SUPPORTED_EXCHANGES

def test_new_exchange_fees():
    assert '<new_exchange>' in EXCHANGE_FEES
```

### Bước 5: Cập nhật rate limiter

Thêm rate limit config cho sàn mới trong `services/rate_limiter.py` nếu cần limits khác default.

## Validation

```bash
pytest tests/test_configs.py -v
pytest tests/test_integration.py -v
```

## Lưu ý

- Kiểm tra ccxt có hỗ trợ `fetchOrderBook` và `createOrder` cho sàn mới
- Phí giao dịch phải chính xác (kiểm tra trên website sàn)
- API keys cho sàn mới thêm vào `.env`, KHÔNG hardcode
