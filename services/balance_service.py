"""
Service quản lý số dư trên các sàn giao dịch.
"""
import os
import time
from typing import Any, Optional
from utils.logger import log_info, log_error, log_warning
from utils.exceptions import InsufficientBalanceError
from utils.helpers import read_file_content, update_balance_file, extract_base_asset
from configs import START_BALANCE_FILE, BALANCE_FILE


class BalanceService:
    """
    Lớp dịch vụ quản lý số dư trên các sàn giao dịch.
    """
    
    def __init__(self, exchange_service: Any) -> None:
        """
        Khởi tạo dịch vụ quản lý số dư.
        
        Args:
            exchange_service (ExchangeService): Dịch vụ sàn giao dịch
        """
        self.exchange_service = exchange_service
        self.cache = {}  # Cache số dư để giảm số lượng request
        self.cache_time = {}  # Thời gian cache
        self.cache_timeout = 10  # Thời gian hết hạn cache (giây)
    
    async def check_balances(self, exchanges: list[str], symbol: str, total_amount: float,
                             notification_service: Any = None) -> bool:
        """
        Kiểm tra số dư trên các sàn giao dịch.
        
        Args:
            exchanges (list): Danh sách tên các sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            total_amount (float): Tổng số lượng USDT cần cho giao dịch
            notification_service (NotificationService, optional): Dịch vụ thông báo
            
        Returns:
            bool: True nếu tất cả các sàn có đủ số dư, ngược lại False
            
        Raises:
            InsufficientBalanceError: Nếu một sàn không có đủ số dư
        """
        amount_per_exchange = total_amount / len(exchanges)
        insufficient = False
        insufficient_exchange = None
        insufficient_amount = 0
        available_amount = 0
        
        for exchange_id in exchanges:
            balance = await self.get_balance(exchange_id, 'USDT')
            
            if balance < amount_per_exchange:
                message = (
                    f"Không đủ số dư trên {exchange_id}. "
                    f"Cần thêm {round(amount_per_exchange - balance, 3)} USDT nữa. "
                    f"Số dư hiện tại trên {exchange_id}: {round(balance, 3)} USDT"
                )
                log_error(message)
                
                if notification_service:
                    notification_service.send_message(message)
                
                insufficient = True
                insufficient_exchange = exchange_id
                insufficient_amount = amount_per_exchange
                available_amount = balance
            else:
                log_info(f"Số dư trên {exchange_id} đã đủ")
        
        if insufficient:
            raise InsufficientBalanceError(insufficient_exchange, 'USDT', insufficient_amount, available_amount)
        
        return True
    
    async def get_balance(self, exchange_id: str, asset: str) -> float:
        """
        Lấy số dư của một tài sản trên sàn giao dịch với caching.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            asset (str): Ký hiệu của tài sản
        
        Returns:
            float: Số dư của tài sản
        """
        cache_key = f"{exchange_id}_{asset}"
        
        # Sử dụng cache nếu chưa hết hạn
        current_time = time.time()
        if cache_key in self.cache and current_time - self.cache_time.get(cache_key, 0) < self.cache_timeout:
            return self.cache[cache_key]
        
        # Nếu không có cache hoặc đã hết hạn, lấy số dư mới
        balance = await self.exchange_service.async_get_balance(exchange_id, asset)
        
        # Cập nhật cache
        self.cache[cache_key] = balance
        self.cache_time[cache_key] = current_time
        
        return balance
    
    def initialize_balances(self, exchanges: list[str], symbol: str, total_usd_amount: float) -> dict[str, float]:
        """
        Khởi tạo số dư ảo cho các sàn giao dịch.
        
        Args:
            exchanges (list): Danh sách tên các sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            total_usd_amount (float): Tổng số lượng USDT
            
        Returns:
            dict: Số dư ảo trên các sàn giao dịch
        """
        # Phân chia số dư USDT đều cho các sàn
        usd_per_exchange = total_usd_amount / 2 / len(exchanges)
        
        # Khởi tạo từ điển số dư
        usd = {exchange: usd_per_exchange for exchange in exchanges}
        
        return usd
    
    def initialize_crypto_balances(self, exchanges: list[str], symbol: str, average_price: float,
                                    total_usd_amount: float) -> dict[str, float]:
        """
        Khởi tạo số dư tiền mã hóa ảo cho các sàn giao dịch.
        
        Args:
            exchanges (list): Danh sách tên các sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            average_price (float): Giá trung bình của cặp giao dịch
            total_usd_amount (float): Tổng số lượng USDT
            
        Returns:
            dict: Số dư tiền mã hóa ảo trên các sàn giao dịch
        """
        # Tính tổng số lượng tiền mã hóa có thể mua
        total_crypto = (total_usd_amount / 2) / average_price
        
        # Phân chia đều cho các sàn
        crypto_per_exchange = total_crypto / len(exchanges)
        
        # Khởi tạo từ điển số dư
        crypto = {exchange: crypto_per_exchange for exchange in exchanges}
        
        return crypto
    
    def initialize_balance_files(self, amount: float) -> float:
        """
        Khởi tạo các tệp tin lưu trữ số dư.
        
        Args:
            amount (float): Số dư ban đầu
        """
        # Ghi số dư ban đầu vào tệp
        with open(START_BALANCE_FILE, 'w') as f:
            f.write(str(amount))
        
        with open(BALANCE_FILE, 'w') as f:
            f.write(str(amount))
    
    def update_balance_with_profit(self, profit_pct: float) -> float:
        """
        Cập nhật số dư với lợi nhuận.
        
        Args:
            profit_pct (float): Phần trăm lợi nhuận
            
        Returns:
            float: Số dư mới
        """
        try:
            # Đọc số dư hiện tại từ tệp
            with open(BALANCE_FILE, 'r+') as f:
                balance = float(f.read().strip())
                
                # Tính số dư mới
                new_balance = round(balance * (1 + (profit_pct / 100)), 3)
                
                # Ghi số dư mới vào tệp
                f.seek(0)
                f.write(str(new_balance))
                f.truncate()
                
                return new_balance
                
        except Exception as e:
            log_error(f"Lỗi khi cập nhật số dư với lợi nhuận: {str(e)}")
            return 0
    
    def emergency_convert_all(self, symbol: str, exchanges: list[str]) -> None:
        """
        Chuyển đổi khẩn cấp tất cả tiền mã hóa sang USDT trên tất cả sàn.
        
        Args:
            symbol (str): Ký hiệu của cặp giao dịch
            exchanges (list): Danh sách tên các sàn giao dịch
            
        Returns:
            bool: True nếu thành công, ngược lại False
        """
        log_info(f"Bán tất cả {extract_base_asset(symbol)} trên {', '.join(exchanges)}")
        
        for exchange_id in exchanges:
            try:
                self.exchange_service.emergency_convert(exchange_id, symbol)
                log_info(f"Đã bán thành công trên {exchange_id}")
            except Exception as e:
                log_error(f"Lỗi khi bán khẩn cấp trên {exchange_id}: {str(e)}")
        
        return True
    
    def transfer_between_accounts(self, exchange_id: str, asset: str, amount: float,
                                    from_account: str, to_account: str) -> bool:
        """
        Chuyển tiền giữa các tài khoản trên cùng một sàn giao dịch.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            asset (str): Ký hiệu của tài sản
            amount (float): Số lượng cần chuyển
            from_account (str): Tài khoản nguồn
            to_account (str): Tài khoản đích
            
        Returns:
            dict: Thông tin về giao dịch chuyển
        """
        try:
            result = self.exchange_service.transfer_between_accounts(exchange_id, asset, amount, from_account, to_account)
            log_info(f"Đã chuyển {amount} {asset} từ {from_account} sang {to_account} trên {exchange_id}")
            return result
        except Exception as e:
            log_error(f"Lỗi khi chuyển tiền trên {exchange_id}: {str(e)}")
            raise