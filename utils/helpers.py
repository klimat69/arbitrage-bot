"""
Các hàm tiện ích dùng chung cho toàn bộ ứng dụng.
"""
import time
from datetime import datetime
from colorama import Style


def show_time() -> str:
    """Trả về thời gian hiện tại định dạng HH:MM:SS."""
    return time.strftime('%H:%M:%S', time.gmtime(time.time()))


def format_message(message: str) -> str:
    """
    Format thông báo để hiển thị đúng định dạng và
    loại bỏ các ký tự đặc biệt của colorama.
    """
    message = message.replace("[2m", "")
    message = message.replace("[0m", "")
    return message


def format_log_message(message: str) -> str:
    """Format thông báo log với thời gian."""
    return f"{Style.DIM}[{show_time()}]{Style.RESET_ALL} {message}"


def calculate_average(values: list[float]) -> float:
    """Tính giá trị trung bình của một danh sách số."""
    if not values:
        return 0
    return sum(values) / len(values)


def append_to_file(file_path: str, content: str, add_newline: bool = True) -> bool:
    """Thêm nội dung vào cuối tệp tin."""
    try:
        with open(file_path, 'a+') as file:
            file.seek(0)
            data = file.read(100)
            if len(data) > 0 and add_newline:
                file.write('\n')
            file.write(content)
        return True
    except Exception as e:
        print(f"Lỗi khi ghi vào tệp tin {file_path}: {e}")
        return False


def read_file_content(file_path: str, default: str = "") -> str:
    """Đọc nội dung của tệp tin."""
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        print(f"Lỗi khi đọc tệp tin {file_path}: {e}")
        return default


def update_balance_file(file_path: str, profit_pct: float, original_balance: float) -> float:
    """Cập nhật tệp tin số dư với lợi nhuận mới."""
    try:
        new_balance = round(original_balance * (1 + (profit_pct / 100)), 3)
        with open(file_path, 'w') as file:
            file.write(str(new_balance))
        return new_balance
    except Exception as e:
        print(f"Lỗi khi cập nhật tệp tin số dư {file_path}: {e}")
        return original_balance


def extract_base_asset(symbol: str) -> str:
    """Trích xuất tên tài sản cơ sở từ một cặp giao dịch."""
    if '/' in symbol:
        return symbol.split('/')[0]
    elif ':' in symbol:
        return symbol.split(':')[0]
    return symbol


def get_precision_min(orderbook, exchange_id):
    """
    Xác định độ chính xác tối thiểu cho giá dựa trên sách lệnh.
    
    Args:
        orderbook (dict): Dữ liệu sách lệnh
        exchange_id (str): ID của sàn giao dịch
        
    Returns:
        float: Giá trị độ chính xác tối thiểu
    """
    try:
        # Tính toán độ chính xác dựa trên sự chênh lệch giữa các giá
        bids = orderbook['bids']
        asks = orderbook['asks']
        
        price_diffs = []
        
        # Lấy độ chênh lệch giữa các giá mua
        for i in range(1, min(5, len(bids))):
            diff = abs(bids[i][0] - bids[i-1][0])
            if diff > 0:
                price_diffs.append(diff)
        
        # Lấy độ chênh lệch giữa các giá bán
        for i in range(1, min(5, len(asks))):
            diff = abs(asks[i][0] - asks[i-1][0])
            if diff > 0:
                price_diffs.append(diff)
        
        if price_diffs:
            # Lấy giá trị tối thiểu
            min_diff = min(price_diffs)
            return min_diff
        
        # Nếu không thể tính toán, trả về giá trị mặc định theo sàn
        default_precisions = {
            'binance': 0.01,
            'kucoin': 0.01,
            'okx': 0.01,
            'bybit': 0.01,
            'kucoinfutures': 0.1,
        }
        
        return default_precisions.get(exchange_id, 0.01)
    
    except Exception as e:
        # Nếu có lỗi, trả về giá trị mặc định
        print(f"Lỗi khi tính toán độ chính xác: {e}")
        return 0.01


def printandtelegram(message, notification_service=None):
    """
    In thông báo ra màn hình và gửi qua Telegram nếu có thể.
    
    Args:
        message (str): Thông báo cần hiển thị và gửi
        notification_service (NotificationService, optional): Dịch vụ thông báo
    """
    print(message)
    
    if notification_service:
        notification_service.send_message(message)