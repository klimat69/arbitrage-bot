"""
Service quản lý việc gửi thông báo qua Telegram.
"""
import os
import requests
from dotenv import load_dotenv
from utils.helpers import format_message, extract_base_asset
from utils.exceptions import NotificationError

# Tải biến môi trường
load_dotenv()


class NotificationService:
    """
    Lớp dịch vụ gửi thông báo qua các kênh khác nhau.
    Hiện tại chỉ hỗ trợ Telegram.
    """
    
    def __init__(self, enabled: bool = False) -> None:
        """
        Khởi tạo dịch vụ thông báo.
        
        Args:
            enabled (bool): Có kích hoạt gửi thông báo hay không
        """
        self.enabled = enabled
        self.telegram_token = os.getenv('TELEGRAM_API_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    def send_message(self, message: str) -> bool:
        """
        Gửi thông báo đến các kênh đã cấu hình.
        
        Args:
            message (str): Nội dung thông báo
        
        Returns:
            bool: True nếu gửi thành công, ngược lại False
        """
        if not self.enabled:
            return False
        
        success = False
        
        # Gửi qua Telegram nếu đã cấu hình
        if self.telegram_token and self.telegram_chat_id:
            success = self.send_telegram(message)
        
        return success
    
    def send_telegram(self, message: str) -> bool:
        """
        Gửi thông báo qua Telegram.
        
        Args:
            message (str): Nội dung thông báo
        
        Returns:
            bool: True nếu gửi thành công, ngược lại False
        
        Raises:
            NotificationError: Nếu có lỗi khi gửi thông báo
        """
        if not self.enabled:
            return False
        
        # Format lại tin nhắn để loại bỏ các ký tự đặc biệt
        message = format_message(message)
        
        api_url = f'https://api.telegram.org/bot{self.telegram_token}/sendMessage'
        
        try:
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(api_url, json=payload)
            response.raise_for_status()  # Phát sinh ngoại lệ nếu HTTP response không thành công
            return True
        
        except requests.exceptions.RequestException as e:
            raise NotificationError('Telegram', str(e))
    
    def send_opportunity(self, trade_number: int, min_ask_ex: str, min_ask_price: float,
                         max_bid_ex: str, max_bid_price: float, 
                         profit_pct: float, profit_usd: float, total_profit_pct: float,
                         total_profit_usd: float, 
                         fees_usd: float, fees_crypto: float, crypto_pair: str,
                         elapsed_time: str, balances: dict, current_worth: float) -> bool:
        """
        Gửi thông báo về cơ hội giao dịch qua Telegram.
        
        Args:
            trade_number (int): Số thứ tự giao dịch
            min_ask_ex (str): Tên sàn có giá mua thấp nhất
            min_ask_price (float): Giá mua thấp nhất
            max_bid_ex (str): Tên sàn có giá bán cao nhất
            max_bid_price (float): Giá bán cao nhất
            profit_pct (float): Phần trăm lợi nhuận
            profit_usd (float): Lợi nhuận tính theo USD
            total_profit_pct (float): Tổng phần trăm lợi nhuận của phiên
            total_profit_usd (float): Tổng lợi nhuận tính theo USD của phiên
            fees_usd (float): Phí tính theo USD
            fees_crypto (float): Phí tính theo crypto
            crypto_pair (str): Cặp giao dịch
            elapsed_time (str): Thời gian đã trôi qua
            balances (dict): Số dư trên các sàn
            current_worth (float): Giá trị hiện tại của tài sản
        
        Returns:
            bool: True nếu gửi thành công, ngược lại False
        """
        if not self.enabled:
            return False
        
        base_asset = extract_base_asset(crypto_pair)
        
        message = (
            f"[Trade #{trade_number}]\n\n"
            f"Opportunity detected!\n\n"
            f"Profit: {round(profit_pct, 4)}% ({round(profit_usd, 4)} USD)\n\n"
            f"{min_ask_ex} {min_ask_price} -> {max_bid_price} {max_bid_ex}\n"
            f"Time elapsed: {elapsed_time}\n"
            f"Session total profit: {round(total_profit_pct, 4)}% ({round(total_profit_usd, 4)} USDT)\n"
            f"Total fees paid: {round(fees_usd, 4)} USD, {round(fees_crypto, 4)} {base_asset}\n\n"
            f"--------BALANCES---------\n\n"
            f"Current worth: {round(current_worth, 3)} USD\n"
        )
        
        # Thêm thông tin số dư
        for exchange, balance in balances.items():
            message += f"➝ {exchange}: {round(balance['crypto'], 3)} {base_asset} / {round(balance['usd'], 2)} USDT\n"
        
        return self.send_telegram(message)