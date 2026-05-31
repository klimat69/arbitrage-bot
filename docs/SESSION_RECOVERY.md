# Hướng dẫn khôi phục phiên giao dịch

## Tính năng mới: Session Recovery (Khôi phục Phiên)

Bot hiện nay hỗ trợ khôi phục tự động các phiên bị dừng do lỗi hoặc ngắt kết nối. Điều này giúp bạn tiếp tục giao dịch từ điểm dừng mà không mất dữ liệu.

## Cách hoạt động

### 1. **Phát hiện phiên bị dừng**
- Khi bot bắt đầu chạy, nó sẽ kiểm tra database để tìm các phiên có `status = 'running'` (chưa hoàn thành)
- Nếu tìm thấy, bot sẽ hiển thị danh sách các phiên bị dừng

### 2. **Hỏi người dùng**
Bạn sẽ thấy menu như sau:
```
================================================================================
Phát hiện 1 phiên bị dừng:
================================================================================

[1] Phiên #5:
    Chế độ: fake-money
    Cặp tiền: BTC/USDT
    Sàn: binance,kucoin,okx
    Vốn: 1000 USDT
    Thời gian bắt đầu: 2026-05-12T10:30:45.123456+00:00
    Giao dịch đã thực hiện: 12
    Lợi nhuận: 0.5234% (5.2340 USDT)

================================================================================
Tùy chọn:
  [1] - Khôi phục phiên
  [0 hoặc Enter] - Chạy phiên mới

Lựa chọn của bạn: 
```

### 3. **Khôi phục**
Nếu bạn chọn khôi phục (nhập `1`):
- Bot sẽ tải lại cấu hình phiên cũ (chế độ, cặp tiền, sàn, vốn, v.v.)
- Khôi phục balance từ file `balance.txt`
- Đánh dấu phiên cũ là `resumed`
- Tiếp tục giao dịch với cấu hình đó

## Các tình huống sử dụng

### 1. **Mất kết nối mạng**
```bash
# Bot đang chạy khi mất internet
# Sau khi kết nối lại, khởi động bot bình thường:
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Bot sẽ phát hiện phiên bị dừng và hỏi có muốn khôi phục không
```

### 2. **Bot crash**
```bash
# Bot bị crash do lỗi (ví dụ: exchange API error)
# Kiểm tra logs để debug
tail -f logs/arbitrage_bot_*.log

# Sau khi fix lỗi, khởi động lại:
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Chọn khôi phục phiên để tiếp tục
```

### 3. **Người dùng thoát chương trình**
```bash
# Nhấn Ctrl+C khi bot đang chạy
# Bot sẽ hỏi có muốn bán tất cả crypto không

# Nếu thoát mà không bán (nhấn N):
# Phiên sẽ được lưu với status = 'running'

# Lần khởi động tiếp theo:
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Chọn khôi phục phiên để tiếp tục
```

## Tình trạng phiên (Session Status)

| Status | Ý nghĩa |
|--------|---------|
| `running` | Phiên đang chạy hoặc bị dừng (chưa hoàn thành) |
| `completed` | Phiên hoàn thành bình thường |
| `interrupted` | Phiên bị dừng bất thường (lỗi) |
| `resumed` | Phiên đã được khôi phục lần trước |
| `error` | Phiên kết thúc do lỗi |

## Dữ liệu được lưu trữ cho recovery

Khi phiên bị dừng, bot lưu trữ:
- **Cấu hình phiên**: chế độ, cặp tiền, sàn, vốn, thời gian làm mới
- **Dữ liệu giao dịch**: tất cả giao dịch đã thực hiện
- **Balance snapshots**: số dư cuối của mỗi sàn
- **Lợi nhuận tích lũy**: tổng lợi nhuận từ các giao dịch trước
- **Thông tin lỗi**: nếu có exception

## Cách tắt tính năng recovery

Nếu bạn muốn chạy phiên mới mà không khôi phục:

```bash
# Cách 1: Chọn "0" hoặc nhấn Enter khi menu hỏi
Lựa chọn của bạn: 0

# Cách 2: Sử dụng flag --no-recovery (tuỳ chọn)
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT --no-recovery
```

## Xem lịch sử phiên trên Dashboard

Để xem danh sách tất cả phiên (kể cả những phiên bị dừng):

```bash
# Chạy web dashboard
python -m uvicorn web.app:app --reload --port 8000

# Mở trình duyệt: http://localhost:8000/dashboard
```

Dashboard sẽ hiển thị:
- Tất cả phiên (running, completed, interrupted, resumed)
- Chi tiết giao dịch của mỗi phiên
- Lợi nhuận/lỗ
- Balance snapshots

## API Query để kiểm tra phiên bị dừng

Nếu bạn muốn kiểm tra trực tiếp database:

```python
from services.database_service import DatabaseService

db = DatabaseService()

# Lấy danh sách phiên bị dừng
interrupted = db.get_interrupted_sessions()
for session in interrupted:
    print(f"Phiên #{session['id']}: {session['mode']} - {session['symbol']}")
    print(f"  Status: {session['status']}")
    print(f"  Giao dịch: {session['trades_executed']}")
    print(f"  Lợi nhuận: {session['total_profit_pct']:.4f}%\n")

# Lấy thông tin chi tiết phiên
recovery_info = db.get_session_recovery_info(session_id=5)
print(f"Khôi phục: {recovery_info}")

# Xem giao dịch cuối cùng
last_trade = db.get_last_trade(session_id=5)
print(f"Giao dịch cuối: {last_trade}")
```

## Ghi chú quan trọng

### ⚠️ Dữ liệu Balance
- **Đọc từ `balance.txt`**: Vốn sẽ được lấy từ file `balance.txt` (được cập nhật sau mỗi phiên)
- **Nếu bạn đã rút tiền**: Cập nhật số dư trong `balance.txt` trước khi khôi phục

### ⚠️ Timeout vẫn được tính từ lúc khôi phục
- Nếu phiên cũ timeout là 15 phút từ 10:00 -> 10:15
- Sau khi khôi phục lúc 14:00, timeout sẽ là 15 phút từ 14:00 -> 14:15
- Bạn có thể muốn điều chỉnh lại timeout khi khôi phục

### ✅ Best Practices

1. **Kiểm tra logs**: Xem logs để debug lý do tại sao phiên bị dừng
2. **Cập nhật balance**: Cập nhật `balance.txt` nếu bạn đã rút/gửi tiền
3. **Xem dashboard**: Kiểm tra kết quả phiên cũ trước khi khôi phục
4. **Test dry-run trước**: Nếu không chắc chắn, dùng `--dry-run` để test

## Troubleshooting

### Q: Bot không nhận ra phiên bị dừng?
**A**: 
- Kiểm tra database tại `data/arbitrage.db`
- Xem logs để kiểm tra lỗi
- Kiểm tra database connection: `sqlite3 data/arbitrage.db "SELECT * FROM sessions WHERE status='running'"`

### Q: Phiên khôi phục nhưng không tiếp tục từ điểm cũ?
**A**: 
- Bot sẽ bắt đầu với cấu hình cũ nhưng sẽ tạo một số hiệu giao dịch mới
- Lợi nhuận trước đó sẽ được hiển thị và tích lũy

### Q: Tôi muốn xóa phiên bị dừng?
**A**: 
- Hiện tại, chọn "0" khi hỏi sẽ bắt đầu phiên mới (phiên cũ sẽ vẫn được lưu)
- Để xóa từ database: `sqlite3 data/arbitrage.db "DELETE FROM sessions WHERE id=5"`
- Hoặc chỉnh sửa status thành `'completed'`: `sqlite3 data/arbitrage.db "UPDATE sessions SET status='completed' WHERE id=5"`

### Q: Recovery không hoạt động khi chạy multi-pair?
**A**: 
- Multi-pair mode hiện chưa hỗ trợ recovery đầy đủ
- Phiên bị dừng sẽ được phát hiện, nhưng bạn cần chạy lại từ đầu
- Recovery tốt nhất dành cho single-pair mode

## Giới hạn hiện tại

- ❌ Không thể resume pending orders (chưa hoàn thành)
- ❌ Multi-pair recovery không đầy đủ
- ⚠️ Timeout được tính từ khi khôi phục (không tiếp tục từ timeout cũ)
- ⚠️ Không tự động retry nếu khôi phục lỗi

## Phát triển tiếp theo

Những cải tiến dự kiến:
- [ ] Tự động khôi phục nếu phiên bị dừng > X phút
- [ ] Quản lý pending orders khi khôi phục
- [ ] Heartbeat checkpoint (lưu trạng thái mỗi phút)
- [ ] Recovery support cho multi-pair mode
- [ ] Tính lại timeout từ điểm gốc

---

**Câu hỏi hay đóng góp?** Vui lòng mở issue trên GitHub: https://github.com/nguyenngocbinhneu/bmlb-arbitrage-bot/issues
