"""
Module quản lý ghi log của ứng dụng.
"""
import os
import sys
import logging
from datetime import datetime
from typing import Any, Optional
from colorama import Fore, Style
from utils.helpers import show_time


def configure_console_encoding() -> None:
    """Cấu hình UTF-8 cho console khi môi trường hỗ trợ."""
    for stream_name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, OSError, ValueError):
                continue


def safe_print(message: str) -> None:
    """In ra console mà không làm crash khi terminal không hỗ trợ Unicode đầy đủ."""
    stream = sys.stdout
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        sanitized = message.encode(encoding, errors='replace').decode(encoding, errors='replace')
        stream.write(sanitized + '\n')
        stream.flush()


configure_console_encoding()

# Tạo thư mục logs nếu chưa tồn tại
os.makedirs('logs', exist_ok=True)

# Cấu hình logging
today = datetime.now().strftime('%Y-%m-%d')
log_file = f'logs/arbitrage_bot_{today}.log'

# Tạo logger
logger = logging.getLogger('arbitrage_bot')
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Tạo file handler để lưu log vào tệp tin
if not logger.handlers:
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Định dạng log
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Thêm handler vào logger
    logger.addHandler(file_handler)


def log_and_print(message: str, level: str = 'info', print_to_console: bool = True, telegram: Any = None) -> None:
    """
    Ghi log và hiển thị thông báo ra màn hình console.
    
    Args:
        message (str): Nội dung cần ghi log
        level (str): Cấp độ log (debug, info, warning, error, critical)
        print_to_console (bool): Có hiển thị ra màn hình không
        telegram (NotiticationService, optional): Dịch vụ gửi thông báo Telegram
    """
    # Ghi log vào tệp
    getattr(logger, level.lower())(message)
    
    # Hiển thị ra màn hình nếu được yêu cầu
    if print_to_console:
        console_message = f"{Style.DIM}[{show_time()}]{Style.RESET_ALL} {message}"
        safe_print(console_message)
    
    # Gửi thông báo qua Telegram nếu có
    if telegram:
        telegram.send_message(message)


def log_debug(message: str, print_to_console: bool = False, telegram: Any = None) -> None:
    """Log và in thông báo debug."""
    log_and_print(message, 'debug', print_to_console, telegram)


def log_info(message: str, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo thông tin."""
    log_and_print(message, 'info', print_to_console, telegram)


def log_warning(message: str, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo cảnh báo."""
    log_and_print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}", 'warning', print_to_console, telegram)


def log_error(message: str, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo lỗi."""
    log_and_print(f"{Fore.RED}{message}{Style.RESET_ALL}", 'error', print_to_console, telegram)


def log_critical(message: str, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo lỗi nghiêm trọng."""
    log_and_print(f"{Fore.RED}{Style.BRIGHT}{message}{Style.RESET_ALL}", 'critical', print_to_console, telegram)


def log_profit(message: str, profit_pct: float, profit_usd: float, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo về lợi nhuận."""
    color = Fore.GREEN if profit_usd > 0 else (Fore.RED if profit_usd < 0 else Fore.WHITE)
    formatted_message = f"{message}: {color}+{round(profit_pct, 4)}% (+{round(profit_usd, 4)} USD){Style.RESET_ALL}"
    log_and_print(formatted_message, 'info', print_to_console, telegram)


def log_opportunity(index: int, min_ask_ex: str, min_ask_price: float, max_bid_ex: str, max_bid_price: float, profit_with_fees_pct: float, profit_with_fees_usd: float, print_to_console: bool = True, telegram: Any = None) -> None:
    """Log và in thông báo về cơ hội giao dịch."""
    message = (
        f"Opportunity #{index} detected! "
        f"({min_ask_ex} {min_ask_price} -> {max_bid_price} {max_bid_ex}) "
        f"Profit: +{round(profit_with_fees_pct, 4)}% (+{round(profit_with_fees_usd, 4)} USD)"
    )
    log_and_print(message, 'info', print_to_console, telegram)