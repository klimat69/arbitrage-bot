"""
Service quản lý các hoạt động đặt lệnh giao dịch.
"""
import time
import asyncio
from typing import Any, Optional
from utils.logger import log_info, log_error, log_warning
from utils.exceptions import OrderError, OrderFillTimeoutError, FuturesError
from configs import FIRST_ORDERS_FILL_TIMEOUT
from utils.helpers import extract_base_asset


class OrderService:
    """
    Lớp dịch vụ quản lý các lệnh giao dịch.
    """
    
    def __init__(self, exchange_service: Any) -> None:
        """
        Khởi tạo dịch vụ quản lý lệnh.
        
        Args:
            exchange_service (ExchangeService): Dịch vụ sàn giao dịch
        """
        self.exchange_service = exchange_service
    
    def place_initial_orders(self, exchanges: list[str], symbol: str, amount_per_exchange: float,
                             price: float, notification_service: Any = None) -> bool:
        """
        Đặt các lệnh mua ban đầu.
        
        Args:
            exchanges (list): Danh sách tên các sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount_per_exchange (float): Số lượng mỗi lệnh
            price (float): Giá mua
            notification_service (NotificationService, optional): Dịch vụ thông báo
            
        Returns:
            bool: True nếu tất cả các lệnh đã được điền, ngược lại False
            
        Raises:
            OrderError: Nếu có lỗi khi đặt lệnh
        """
        orders_filled = 0
        already_filled = []
        
        # Đặt lệnh mua giới hạn trên tất cả các sàn
        for exchange_id in exchanges:
            try:
                self.exchange_service.create_limit_buy_order(exchange_id, symbol, amount_per_exchange, price)
                log_info(f"Đặt lệnh giới hạn mua {round(amount_per_exchange, 3)} {extract_base_asset(symbol)} ở giá {price} gửi đến {exchange_id}.")
                
                if notification_service:
                    notification_service.send_message(f"Đặt lệnh giới hạn mua {round(amount_per_exchange, 3)} {extract_base_asset(symbol)} ở giá {price} gửi đến {exchange_id}.")
            except Exception as e:
                raise OrderError(exchange_id, "limit buy", str(e))
        
        log_info("Tất cả các lệnh đã được gửi.")
        
        # Đợi cho đến khi tất cả các lệnh được điền hoặc hết thời gian chờ
        timeout_seconds = FIRST_ORDERS_FILL_TIMEOUT  # Thời gian chờ tối đa (giây)
        start_time = time.time()
        
        while time.time() - start_time <= timeout_seconds and orders_filled != len(exchanges):
            for exchange_id in exchanges:
                if exchange_id in already_filled:
                    continue
                    
                try:
                    # Kiểm tra xem lệnh đã được điền chưa
                    open_orders = self.exchange_service.fetch_open_orders(exchange_id, symbol)
                    
                    if not open_orders:  # Nếu không có lệnh mở, lệnh đã được điền
                        log_info(f"Lệnh trên {exchange_id} đã được điền.")
                        
                        if notification_service:
                            notification_service.send_message(f"Lệnh trên {exchange_id} đã được điền.")
                            
                        orders_filled += 1
                        already_filled.append(exchange_id)
                except Exception as e:
                    log_error(f"Lỗi khi kiểm tra trạng thái lệnh trên {exchange_id}: {str(e)}")
                
            # Dừng 1.8 giây để giảm số lượng request
            time.sleep(1.8)
        
        # Kiểm tra nếu có lệnh nào chưa được điền sau khi hết thời gian chờ
        if time.time() - start_time >= timeout_seconds and orders_filled != len(exchanges):
            message = f"Một hoặc nhiều lệnh không được điền trong khoảng {FIRST_ORDERS_FILL_TIMEOUT // 60} phút. Hủy các lệnh và bán số lượng đã điền."
            log_warning(message)
            
            if notification_service:
                notification_service.send_message(message)
            
            # Bán số lượng đã mua trên các sàn đã điền lệnh
            if already_filled:
                self.emergency_sell(symbol, already_filled)
            
            # Hủy các lệnh chưa điền
            for exchange_id in exchanges:
                if exchange_id not in already_filled:
                    try:
                        open_orders = self.exchange_service.fetch_open_orders(exchange_id, symbol)
                        
                        if open_orders:
                            self.exchange_service.cancel_order(exchange_id, open_orders[-1]['id'], symbol)
                            log_info(f"Đã hủy lệnh trên {exchange_id}.")
                    except Exception as e:
                        log_error(f"Lỗi khi hủy lệnh trên {exchange_id}: {str(e)}")
            
            return False
        
        return True
    
    def place_arbitrage_orders(self, min_ask_ex: str, max_bid_ex: str, symbol: str,
                               amount: float, min_ask_price: float, max_bid_price: float,
                               notification_service: Any = None) -> bool:
        """
        Đặt các lệnh giao dịch chênh lệch giá.
        
        Args:
            min_ask_ex (str): Tên sàn có giá mua thấp nhất
            max_bid_ex (str): Tên sàn có giá bán cao nhất
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng giao dịch
            min_ask_price (float): Giá mua thấp nhất
            max_bid_price (float): Giá bán cao nhất
            notification_service (NotificationService, optional): Dịch vụ thông báo
            
        Returns:
            bool: True nếu các lệnh đã được điền, ngược lại False
            
        Raises:
            OrderError: Nếu có lỗi khi đặt lệnh
        """
        try:
            # Đặt lệnh bán giới hạn trên sàn có giá cao
            self.exchange_service.create_limit_sell_order(max_bid_ex, symbol, amount, max_bid_price)
            log_info(f"Lệnh bán giới hạn đã gửi đến {max_bid_ex} cho {amount} {extract_base_asset(symbol)} ở giá {max_bid_price}, đợi 3 phút để điền.")
            
            # Đặt lệnh mua giới hạn trên sàn có giá thấp
            self.exchange_service.create_limit_buy_order(min_ask_ex, symbol, amount, min_ask_price)
            log_info(f"Lệnh mua giới hạn đã gửi đến {min_ask_ex} cho {amount} {extract_base_asset(symbol)} ở giá {min_ask_price}, đợi 3 phút để điền.")
            
            if notification_service:
                notification_service.send_message(
                    f"Đặt lệnh chênh lệch giá:\n"
                    f"- Bán giới hạn: {max_bid_ex} {amount} {extract_base_asset(symbol)} @ {max_bid_price}\n"
                    f"- Mua giới hạn: {min_ask_ex} {amount} {extract_base_asset(symbol)} @ {min_ask_price}"
                )
            
            # Thiết lập thời gian chờ tối đa cho việc điền lệnh
            cancel_order_timeout = time.time() + 180  # 3 phút
            already_filled = []
            
            # Kiểm tra liên tục trạng thái lệnh
            while time.time() < cancel_order_timeout:
                time.sleep(2)
                
                # Kiểm tra lệnh mua
                buy_orders = self.exchange_service.fetch_open_orders(min_ask_ex, symbol)
                
                # Kiểm tra lệnh bán
                sell_orders = self.exchange_service.fetch_open_orders(max_bid_ex, symbol)
                
                # Cập nhật danh sách lệnh đã điền
                if not buy_orders and min_ask_ex not in already_filled:
                    already_filled.append(min_ask_ex)
                    log_info(f"Lệnh mua trên {min_ask_ex} đã được điền!")
                    
                    if notification_service:
                        notification_service.send_message(f"Lệnh mua trên {min_ask_ex} đã được điền!")
                
                if not sell_orders and max_bid_ex not in already_filled:
                    already_filled.append(max_bid_ex)
                    log_info(f"Lệnh bán trên {max_bid_ex} đã được điền!")
                    
                    if notification_service:
                        notification_service.send_message(f"Lệnh bán trên {max_bid_ex} đã được điền!")
                
                # Nếu cả hai lệnh đều đã điền thì thoát vòng lặp
                if not buy_orders and not sell_orders:
                    return True
            
            # Xử lý trường hợp lệnh chưa được điền sau thời gian chờ
            if buy_orders and not sell_orders:
                # Lệnh mua chưa điền nhưng lệnh bán đã điền
                log_warning(f"Lệnh mua trên {min_ask_ex} không được điền trong 3 phút.")
                
                # Hủy lệnh mua
                self.exchange_service.cancel_order(min_ask_ex, buy_orders[0]['id'], symbol)
                log_info(f"Đã hủy lệnh mua trên {min_ask_ex}.")
                
                # Tạo lệnh mua thị trường để cân bằng
                log_info("Tạo lệnh mua thị trường ngược lại...")
                last_orders = self.exchange_service.fetch_closed_orders(max_bid_ex, symbol)
                
                if last_orders:
                    amount_filled = last_orders[-1]["filled"]
                    self.exchange_service.create_market_buy_order(max_bid_ex, symbol, amount_filled)
                    log_info(f"Đã tạo lệnh mua thị trường trên {max_bid_ex} cho {amount_filled} {extract_base_asset(symbol)}.")
                
            elif sell_orders and not buy_orders:
                # Lệnh bán chưa điền nhưng lệnh mua đã điền
                log_warning(f"Lệnh bán trên {max_bid_ex} không được điền trong 3 phút.")
                
                # Hủy lệnh bán
                self.exchange_service.cancel_order(max_bid_ex, sell_orders[0]['id'], symbol)
                log_info(f"Đã hủy lệnh bán trên {max_bid_ex}.")
                
                # Tạo lệnh bán thị trường để cân bằng
                last_orders = self.exchange_service.fetch_closed_orders(min_ask_ex, symbol)
                
                if last_orders:
                    amount_filled = last_orders[-1]["filled"]
                    self.exchange_service.create_market_sell_order(min_ask_ex, symbol, amount_filled)
                    log_info(f"Lệnh bán thị trường đã được điền trên {min_ask_ex}. Có thể có tổn thất nhỏ.")
            
            elif buy_orders and sell_orders:
                # Cả hai lệnh đều chưa điền
                log_warning("2 lệnh không được điền trong 120 giây. Đang hủy...")
                
                # Hủy cả hai lệnh
                self.exchange_service.cancel_order(min_ask_ex, buy_orders[0]['id'], symbol)
                self.exchange_service.cancel_order(max_bid_ex, sell_orders[0]['id'], symbol)
                log_info("Đã hủy cả hai lệnh.")
            
            return False
            
        except Exception as e:
            raise OrderError(f"{min_ask_ex}/{max_bid_ex}", "arbitrage", str(e))
    
    def emergency_sell(self, symbol: str, exchanges: list[str]) -> bool:
        """
        Bán khẩn cấp tiền mã hóa trên các sàn.
        
        Args:
            symbol (str): Ký hiệu của cặp giao dịch
            exchanges (list): Danh sách tên các sàn giao dịch
            
        Returns:
            bool: True nếu thành công, ngược lại False
        """
        for exchange_id in exchanges:
            try:
                self.exchange_service.emergency_convert(exchange_id, symbol)
            except Exception as e:
                log_error(f"Lỗi khi bán khẩn cấp trên {exchange_id}: {str(e)}")
        
        return True
    
    def place_futures_short_order(self, exchange_id: str, symbol: str, amount: float,
                                   leverage: int = 1) -> dict[str, Any]:
        """
        Đặt lệnh Short trên thị trường Futures.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng
            leverage (int): Đòn bẩy
            
        Returns:
            dict: Thông tin lệnh
            
        Raises:
            FuturesError: Nếu có lỗi khi đặt lệnh
        """
        try:
            # Đảm bảo đây là một symbol Futures hợp lệ
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            # Đặt lệnh bán thị trường với đòn bẩy
            params = {'leverage': leverage}
            order = self.exchange_service.create_futures_order(exchange_id, symbol, 'market', 'sell', amount, params)
            log_info(f"Đã đặt lệnh short trên {exchange_id} cho {amount} {extract_base_asset(symbol)} với đòn bẩy {leverage}x")
            
            return order
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể đặt lệnh short: {str(e)}")
    
    def close_futures_short_order(self, exchange_id: str, symbol: str, amount: float,
                                    leverage: int = 1) -> dict[str, Any]:
        """
        Đóng lệnh Short trên thị trường Futures.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng
            leverage (int): Đòn bẩy
            
        Returns:
            dict: Thông tin lệnh
            
        Raises:
            FuturesError: Nếu có lỗi khi đặt lệnh
        """
        try:
            # Đảm bảo đây là một symbol Futures hợp lệ
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            # Đặt lệnh mua thị trường để đóng vị thế short
            params = {'leverage': leverage}
            order = self.exchange_service.create_futures_order(exchange_id, symbol, 'market', 'buy', amount, params)
            log_info(f"Đã đóng lệnh short trên {exchange_id} cho {amount} {extract_base_asset(symbol)} với đòn bẩy {leverage}x")
            
            return order
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể đóng lệnh short: {str(e)}")
    
    def wait_for_futures_order_fill(self, exchange_id: str, symbol: str, timeout: int = 120) -> bool:
        """
        Đợi cho đến khi lệnh Futures được điền.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            timeout (int): Thời gian chờ tối đa (giây)
            
        Returns:
            bool: True nếu lệnh đã được điền, ngược lại False
            
        Raises:
            OrderFillTimeoutError: Nếu lệnh không được điền trong thời gian quy định
        """
        try:
            # Đảm bảo đây là một symbol Futures hợp lệ
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Kiểm tra các lệnh đang mở
                open_orders = self.exchange_service.fetch_open_orders(exchange_id, symbol)
                
                if not open_orders:
                    # Không có lệnh đang mở, tức là lệnh đã được điền
                    log_info(f"Lệnh Futures trên {exchange_id} đã được điền.")
                    return True
                
                # Dừng 1 giây để giảm số lượng request
                time.sleep(1)
            
            # Nếu vẫn còn lệnh đang mở sau khi hết thời gian chờ
            open_orders = self.exchange_service.fetch_open_orders(exchange_id, symbol)
            
            if open_orders:
                # Hủy lệnh đầu tiên
                order_id = open_orders[0]['id']
                self.exchange_service.cancel_order(exchange_id, order_id, symbol)
                
                raise OrderFillTimeoutError(exchange_id, order_id, timeout)
            
            return True
            
        except Exception as e:
            if isinstance(e, OrderFillTimeoutError):
                raise
            
            raise FuturesError(exchange_id, f"Lỗi khi đợi lệnh futures được điền: {str(e)}")
    
    def set_futures_leverage(self, exchange_id: str, symbol: str, leverage: int) -> Optional[dict[str, Any]]:
        """
        Thiết lập đòn bẩy cho một cặp giao dịch trên thị trường Futures.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            leverage (int): Đòn bẩy
            
        Returns:
            dict: Thông tin về việc thiết lập đòn bẩy
            
        Raises:
            FuturesError: Nếu có lỗi khi thiết lập đòn bẩy
        """
        try:
            # Đảm bảo đây là một symbol Futures hợp lệ
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            exchange = self.exchange_service.get_exchange(exchange_id)
            
            if hasattr(exchange, 'set_leverage'):
                result = exchange.set_leverage(leverage, symbol)
                log_info(f"Đã thiết lập đòn bẩy {leverage}x cho {symbol} trên {exchange_id}")
                return result
            else:
                log_warning(f"Sàn {exchange_id} không hỗ trợ thiết lập đòn bẩy qua API")
                return None
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể thiết lập đòn bẩy: {str(e)}")
    
    def check_futures_position(self, exchange_id: str, symbol: str) -> Optional[dict[str, Any]]:
        """
        Kiểm tra vị thế Futures hiện tại.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            
        Returns:
            dict: Thông tin về vị thế
            
        Raises:
            FuturesError: Nếu có lỗi khi kiểm tra vị thế
        """
        try:
            # Đảm bảo đây là một symbol Futures hợp lệ
            if not symbol.endswith(':USDT'):
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            exchange = self.exchange_service.get_exchange(exchange_id)
            
            if hasattr(exchange, 'fetch_positions'):
                positions = exchange.fetch_positions([symbol])
                
                if positions and len(positions) > 0:
                    for position in positions:
                        if position['symbol'] == symbol:
                            log_info(f"Vị thế Futures {symbol} trên {exchange_id}: {position['side']} {position['contracts']}")
                            return position
                
                log_info(f"Không tìm thấy vị thế Futures {symbol} trên {exchange_id}")
                return None
            else:
                log_warning(f"Sàn {exchange_id} không hỗ trợ kiểm tra vị thế qua API")
                return None
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể kiểm tra vị thế: {str(e)}")
            
    def get_futures_balance(self, exchange_id: str, asset: str = 'USDT') -> float:
        """
        Lấy số dư trên tài khoản Futures.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            asset (str): Ký hiệu của tài sản (mặc định là USDT)
            
        Returns:
            float: Số dư của tài sản
            
        Raises:
            FuturesError: Nếu có lỗi khi lấy số dư
        """
        try:
            exchange = self.exchange_service.get_exchange(exchange_id)
            
            if hasattr(exchange, 'fetch_balance'):
                balance = exchange.fetch_balance()
                
                if asset in balance['free']:
                    log_info(f"Số dư Futures {asset} trên {exchange_id}: {balance['free'][asset]}")
                    return balance['free'][asset]
                
                log_info(f"Không tìm thấy số dư {asset} trên {exchange_id}")
                return 0
            else:
                log_warning(f"Sàn {exchange_id} không hỗ trợ kiểm tra số dư qua API")
                return 0
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể lấy số dư: {str(e)}")