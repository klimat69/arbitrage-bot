"""
Service quản lý tương tác với các sàn giao dịch.
"""
import os
import ccxt
import ccxt.pro
import asyncio
from datetime import datetime
from typing import Any, Optional
from dotenv import load_dotenv
from utils.logger import log_info, log_error, log_debug
from utils.exceptions import ExchangeError, InsufficientBalanceError, FuturesError
from utils.helpers import calculate_average, extract_base_asset
from services.rate_limiter import get_rate_limiter
from configs import SUPPORTED_EXCHANGES
import time

# Tải biến môi trường
load_dotenv()

async def retry_with_backoff(func, *args, retries=3, backoff_in_seconds=1, **kwargs):
    """
    Thực hiện retry với backoff khi gọi hàm.

    Args:
        func (callable): Hàm cần gọi.
        retries (int): Số lần thử lại tối đa.
        backoff_in_seconds (int): Thời gian chờ ban đầu giữa các lần thử lại.
        *args: Tham số truyền vào hàm.
        **kwargs: Tham số keyword truyền vào hàm.

    Returns:
        Any: Kết quả trả về từ hàm.

    Raises:
        Exception: Nếu hết số lần thử lại mà vẫn thất bại.
    """
    for attempt in range(retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log_error(f"Lỗi khi gọi hàm {func.__name__}: {str(e)}. Thử lại ({attempt + 1}/{retries})...")
            if attempt < retries - 1:
                await asyncio.sleep(backoff_in_seconds * (2 ** attempt))
            else:
                raise

class ExchangeService:
    """
    Lớp dịch vụ tương tác với các sàn giao dịch cryptocurrency.
    """
    
    def __init__(self) -> None:
        """Khởi tạo dịch vụ sàn giao dịch."""
        self.exchanges = {}
        self.exchange_instances = {}
        self._use_sandbox = os.getenv('USE_SANDBOX', 'false').lower() == 'true'
        self._rate_limiter = get_rate_limiter()
        self._initialize_exchanges()

    def _apply_sandbox_mode(self, exchange: Any, exchange_id: str) -> None:
        """Bật sandbox mode nếu cấu hình môi trường yêu cầu."""
        if not self._use_sandbox:
            return

        if hasattr(exchange, 'set_sandbox_mode'):
            exchange.set_sandbox_mode(True)
            log_info(f"Đã bật sandbox mode cho {exchange_id}")

    def _get_env_value(self, prod_key: str, testnet_key: str) -> Optional[str]:
        """Lấy giá trị env, ưu tiên key testnet khi bật sandbox."""
        if self._use_sandbox:
            testnet_value = os.getenv(testnet_key)
            if testnet_value:
                return testnet_value
        return os.getenv(prod_key)
    
    def _initialize_exchanges(self) -> None:
        """Khởi tạo đối tượng sàn giao dịch với thông tin xác thực từ biến môi trường."""
        for exchange_id in SUPPORTED_EXCHANGES:
            self.exchanges[exchange_id] = {'enableRateLimit': True}

        binance_api_key = self._get_env_value('BINANCE_API_KEY', 'BINANCE_TESTNET_API_KEY')
        binance_secret = self._get_env_value('BINANCE_SECRET', 'BINANCE_TESTNET_SECRET')
        kucoin_api_key = self._get_env_value('KUCOIN_API_KEY', 'KUCOIN_TESTNET_API_KEY')
        kucoin_secret = self._get_env_value('KUCOIN_SECRET', 'KUCOIN_TESTNET_SECRET')
        kucoin_password = self._get_env_value('KUCOIN_PASSWORD', 'KUCOIN_TESTNET_PASSWORD')
        bybit_api_key = self._get_env_value('BYBIT_API_KEY', 'BYBIT_TESTNET_API_KEY')
        bybit_secret = self._get_env_value('BYBIT_SECRET', 'BYBIT_TESTNET_SECRET')
        okx_api_key = self._get_env_value('OKX_API_KEY', 'OKX_TESTNET_API_KEY')
        okx_secret = self._get_env_value('OKX_SECRET', 'OKX_TESTNET_SECRET')
        okx_password = self._get_env_value('OKX_PASSWORD', 'OKX_TESTNET_PASSWORD')

        # Khởi tạo Binance
        if binance_api_key and binance_secret:
            self.exchanges['binance'] = {
                'apiKey': binance_api_key,
                'secret': binance_secret,
                'options': {'createMarketBuyOrderRequiresPrice': False}
            }
        
        # Khởi tạo KuCoin
        if kucoin_api_key and kucoin_secret and kucoin_password:
            self.exchanges['kucoin'] = {
                'apiKey': kucoin_api_key,
                'secret': kucoin_secret,
                'password': kucoin_password,
                'options': {'createMarketBuyOrderRequiresPrice': False}
            }
            self.exchanges['kucoinfutures'] = {
                'apiKey': kucoin_api_key,
                'secret': kucoin_secret,
                'password': kucoin_password
            }
        
        # Khởi tạo Bybit
        if bybit_api_key and bybit_secret:
            self.exchanges['bybit'] = {
                'apiKey': bybit_api_key,
                'secret': bybit_secret,
                'options': {
                    'defaultType': 'spot',
                    'createMarketBuyOrderRequiresPrice': False
                }
            }
        
        # Khởi tạo OKX
        if okx_api_key and okx_secret and okx_password:
            self.exchanges['okx'] = {
                'apiKey': okx_api_key,
                'secret': okx_secret,
                'password': okx_password,
                'options': {'createMarketBuyOrderRequiresPrice': False}
            }
    
    def get_exchange(self, exchange_id: str) -> Any:
        """
        Lấy đối tượng sàn giao dịch theo id.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
        
        Returns:
            object: Đối tượng sàn giao dịch đã được khởi tạo
        
        Raises:
            ExchangeError: Nếu sàn giao dịch không tồn tại hoặc không được hỗ trợ
        """
        if exchange_id not in self.exchange_instances:
            if exchange_id not in self.exchanges:
                raise ExchangeError(exchange_id, "Sàn giao dịch không được hỗ trợ hoặc chưa được cấu hình")
            
            try:
                # Tạo đối tượng sàn giao dịch
                exchange_class = getattr(ccxt, exchange_id)
                self.exchange_instances[exchange_id] = exchange_class(self.exchanges[exchange_id])
                self._apply_sandbox_mode(self.exchange_instances[exchange_id], exchange_id)
                log_info(f"Đã khởi tạo sàn giao dịch {exchange_id}")
            except Exception as e:
                raise ExchangeError(exchange_id, f"Không thể khởi tạo sàn giao dịch: {str(e)}")
        
        return self.exchange_instances[exchange_id]

    async def get_pro_exchange(self, exchange_id: str, public_only: bool = False) -> Any:
        """
        Lấy đối tượng sàn giao dịch ccxt.pro theo id.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            public_only (bool): Chỉ dùng endpoint public, không gửi credential
        
        Returns:
            object: Đối tượng sàn giao dịch ccxt.pro đã được khởi tạo
        
        Raises:
            ExchangeError: Nếu sàn giao dịch không tồn tại hoặc không được hỗ trợ
        """
        try:
            return await self._get_or_create_pro_exchange(exchange_id, public_only=public_only)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể khởi tạo sàn giao dịch pro: {str(e)}")
    
    async def get_balance(self, exchange_id: str, symbol: str) -> dict[str, float]:
        """
        Lấy số dư của một tài sản trên sàn giao dịch.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của tài sản
        
        Returns:
            float: Số dư của tài sản
        
        Raises:
            ExchangeError: Nếu có lỗi khi lấy số dư
        """
        exchange = self.get_exchange(exchange_id)

        async def fetch():
            return exchange.fetch_balance()

        try:
            return await retry_with_backoff(fetch)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể lấy số dư của {symbol}: {str(e)}")
    
    async def get_ticker(self, exchange_id: str, symbol: str) -> dict[str, Any]:
        """
        Lấy thông tin ticker của một cặp giao dịch với retry.

        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch

        Returns:
            dict: Thông tin ticker

        Raises:
            ExchangeError: Nếu có lỗi khi lấy ticker
        """
        exchange = self.get_exchange(exchange_id)

        async def fetch_ticker():
            return exchange.fetch_ticker(symbol)

        try:
            log_info(f"Đang gọi API get_ticker cho {exchange_id} với cặp {symbol}...")
            return await retry_with_backoff(fetch_ticker)
        except Exception as e:
            log_error(f"Lỗi khi gọi API get_ticker cho {exchange_id} với cặp {symbol}: {str(e)}")
            raise ExchangeError(exchange_id, f"Không thể lấy ticker cho {symbol}: {str(e)}")
    
    def create_limit_buy_order(self, exchange_id: str, symbol: str, amount: float,
                                price: float) -> dict[str, Any]:
        """
        Tạo lệnh mua giới hạn.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần mua
            price (float): Giá mua
        
        Returns:
            dict: Thông tin lệnh đã tạo
        
        Raises:
            ExchangeError: Nếu có lỗi khi tạo lệnh
        """
        exchange = self.get_exchange(exchange_id)

        try:
            self._rate_limiter.acquire(exchange_id)
            return exchange.create_limit_buy_order(symbol, amount, price)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể tạo lệnh mua giới hạn cho {symbol}: {str(e)}")
    
    def create_limit_sell_order(self, exchange_id: str, symbol: str, amount: float,
                                 price: float) -> dict[str, Any]:
        """
        Tạo lệnh bán giới hạn.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần bán
            price (float): Giá bán
        
        Returns:
            dict: Thông tin lệnh đã tạo
        
        Raises:
            ExchangeError: Nếu có lỗi khi tạo lệnh
        """
        exchange = self.get_exchange(exchange_id)

        try:
            self._rate_limiter.acquire(exchange_id)
            return exchange.create_limit_sell_order(symbol, amount, price)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể tạo lệnh bán giới hạn cho {symbol}: {str(e)}")
    
    def create_market_buy_order(self, exchange_id: str, symbol: str, amount: float,
                                 params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Tạo lệnh mua thị trường.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần mua
            params (dict, optional): Tham số bổ sung
        
        Returns:
            dict: Thông tin lệnh đã tạo
        
        Raises:
            ExchangeError: Nếu có lỗi khi tạo lệnh
        """
        exchange = self.get_exchange(exchange_id)
        params = params or {}

        try:
            self._rate_limiter.acquire(exchange_id)
            return exchange.create_market_buy_order(symbol, amount, params)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể tạo lệnh mua thị trường cho {symbol}: {str(e)}")
    
    def create_market_sell_order(self, exchange_id: str, symbol: str, amount: float,
                                  params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Tạo lệnh bán thị trường.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần bán
            params (dict, optional): Tham số bổ sung
        
        Returns:
            dict: Thông tin lệnh đã tạo
        
        Raises:
            ExchangeError: Nếu có lỗi khi tạo lệnh
        """
        exchange = self.get_exchange(exchange_id)
        params = params or {}

        try:
            self._rate_limiter.acquire(exchange_id)
            return exchange.create_market_sell_order(symbol, amount, params)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể tạo lệnh bán thị trường cho {symbol}: {str(e)}")
    
    def fetch_open_orders(self, exchange_id: str, symbol: str) -> list[dict[str, Any]]:
        """
        Lấy danh sách lệnh đang mở.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            list: Danh sách các lệnh đang mở
        
        Raises:
            ExchangeError: Nếu có lỗi khi lấy danh sách lệnh
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            return exchange.fetch_open_orders(symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể lấy danh sách lệnh đang mở cho {symbol}: {str(e)}")
    
    def fetch_closed_orders(self, exchange_id: str, symbol: str) -> list[dict[str, Any]]:
        """
        Lấy danh sách lệnh đã đóng.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            list: Danh sách các lệnh đã đóng
        
        Raises:
            ExchangeError: Nếu có lỗi khi lấy danh sách lệnh
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            return exchange.fetch_closed_orders(symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể lấy danh sách lệnh đã đóng cho {symbol}: {str(e)}")
    
    def cancel_order(self, exchange_id: str, order_id: str, symbol: str) -> dict[str, Any]:
        """
        Hủy một lệnh.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            order_id (str): ID của lệnh cần hủy
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            dict: Thông tin lệnh đã hủy
        
        Raises:
            ExchangeError: Nếu có lỗi khi hủy lệnh
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            return exchange.cancel_order(order_id, symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể hủy lệnh {order_id} cho {symbol}: {str(e)}")
    
    def cancel_all_orders(self, exchange_id: str, symbol: str) -> None:
        """
        Hủy tất cả các lệnh đang mở.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            dict: Thông tin về việc hủy lệnh
        
        Raises:
            ExchangeError: Nếu có lỗi khi hủy lệnh
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            if hasattr(exchange, 'cancel_all_orders'):
                return exchange.cancel_all_orders(symbol)
            else:
                # Nếu sàn không hỗ trợ hủy tất cả, hủy từng lệnh một
                orders = self.fetch_open_orders(exchange_id, symbol)
                results = []
                for order in orders:
                    results.append(self.cancel_order(exchange_id, order['id'], symbol))
                return results
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể hủy tất cả lệnh cho {symbol}: {str(e)}")
    
    def get_precision_min(self, exchange_id: str, symbol: str) -> tuple[float, float, float]:
        """
        Lấy giá trị tối thiểu của giá cho một cặp giao dịch.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            float: Giá trị tối thiểu
        
        Raises:
            ExchangeError: Nếu có lỗi khi lấy giá trị tối thiểu
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            markets = exchange.load_markets()
            if symbol in markets:
                symbol_info = markets[symbol]
                if 'limits' in symbol_info and 'price' in symbol_info['limits'] and 'min' in symbol_info['limits']['price']:
                    return symbol_info['limits']['price']['min']
            return 0.001  # Giá trị mặc định
        except Exception as e:
            # Nếu không lấy được thông tin, trả về giá trị mặc định
            log_error(f"Không thể lấy giá trị tối thiểu cho {symbol} trên {exchange_id}: {str(e)}")
            return 0.001
    
    async def get_global_average_price(self, exchanges: list[str], symbol: str) -> float:
        """
        Lấy giá trung bình của một cặp giao dịch trên nhiều sàn.
        
        Args:
            exchanges (list): Danh sách ID của các sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            float: Giá trung bình
            
        Raises:
            ExchangeError: Nếu có lỗi khi lấy giá
        """
        all_tickers = []
        log_info(f"Đang lấy giá trung bình trên toàn cầu cho {symbol}...")
        
        try:
            for exchange_id in exchanges:
                ticker = await self.get_ticker(exchange_id, symbol)
                all_tickers.append(ticker['bid'])
                all_tickers.append(ticker['ask'])
            
            average_price = calculate_average(all_tickers)
            log_info(f"Giá trung bình {symbol} trong USDT: {average_price}")
            return average_price
        except Exception as e:
            raise ExchangeError("global", f"Không thể lấy giá trung bình: {str(e)}")
    
    async def watch_order_book(self, exchange_id: str, symbol: str) -> dict[str, Any]:
        """
        Theo dõi sách lệnh của một cặp giao dịch.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            dict: Thông tin sách lệnh
            
        Raises:
            ExchangeError: Nếu có lỗi khi theo dõi sách lệnh
        """
        try:
            pro_exchange = await self.get_pro_exchange(exchange_id)
            orderbook = await pro_exchange.watch_order_book(symbol)
            return orderbook
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể theo dõi sách lệnh cho {symbol}: {str(e)}")
    
    def emergency_convert(self, exchange_id: str, symbol: str, keep_percentage: float = 0.01) -> None:
        """
        Chuyển đổi khẩn cấp một tài sản sang USDT.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            keep_percentage (float): Phần trăm tài sản giữ lại (0.01 = 1%)
        
        Returns:
            dict: Thông tin lệnh bán
            
        Raises:
            ExchangeError: Nếu có lỗi khi chuyển đổi
        """
        try:
            # Hủy tất cả các lệnh đang mở
            self.cancel_all_orders(exchange_id, symbol)
            
            # Lấy số dư và tính số lượng cần bán
            base_asset = extract_base_asset(symbol)
            balance = self.get_balance(exchange_id, base_asset)
            balance_to_sell = balance - (balance * keep_percentage)
            
            # Kiểm tra số dư tối thiểu
            ticker = self.get_ticker(exchange_id, symbol)
            min_amount_in_base = 10 / ticker['last']  # Số lượng tối thiểu tương đương 10 USDT
            
            if balance_to_sell > min_amount_in_base:
                return self.create_market_sell_order(exchange_id, symbol, round(balance_to_sell, 4))
            else:
                log_info(f"Không đủ {base_asset} trên {exchange_id}.")
                return None
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể thực hiện chuyển đổi khẩn cấp cho {symbol}: {str(e)}")
    
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
            
        Raises:
            ExchangeError: Nếu có lỗi khi chuyển tiền
        """
        exchange = self.get_exchange(exchange_id)
        
        try:
            result = exchange.transfer(asset, amount, from_account, to_account)
            log_info(f"Đã chuyển {amount} {asset} từ {from_account} sang {to_account} trên {exchange_id}")
            return result
        except Exception as e:
            raise ExchangeError(exchange_id, f"Không thể chuyển tiền: {str(e)}")
    
    def create_futures_order(self, exchange_id: str, symbol: str, type: str, side: str,
                              amount: float, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Tạo lệnh trên thị trường futures.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            type (str): Loại lệnh (market, limit)
            side (str): Hướng đặt lệnh (buy, sell)
            amount (float): Số lượng
            params (dict, optional): Tham số bổ sung
            
        Returns:
            dict: Thông tin lệnh đã tạo
            
        Raises:
            FuturesError: Nếu có lỗi khi tạo lệnh
        """
        exchange = self.get_exchange(exchange_id)
        params = params or {}
        
        try:
            # Đảm bảo symbol đúng định dạng cho futures
            if not symbol.endswith(':USDT') and ':USDT' not in symbol:
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            # Tạo lệnh futures
            if type == 'market':
                if side == 'buy':
                    return exchange.create_market_buy_order(symbol, amount, params)
                elif side == 'sell':
                    return exchange.create_market_sell_order(symbol, amount, params)
            elif type == 'limit':
                price = params.pop('price', None)
                if not price:
                    raise FuturesError(exchange_id, "Giá bắt buộc phải có cho lệnh giới hạn")
                
                if side == 'buy':
                    return exchange.create_limit_buy_order(symbol, amount, price, params)
                elif side == 'sell':
                    return exchange.create_limit_sell_order(symbol, amount, price, params)
            
            raise FuturesError(exchange_id, f"Loại lệnh không hợp lệ: {type}")
            
        except Exception as e:
            raise FuturesError(exchange_id, f"Không thể tạo lệnh futures: {str(e)}")

    # ─── Async Methods ────────────────────────────────────────────────
    # Các phương thức async sử dụng ccxt.pro cho đặt lệnh đồng thời

    def _build_pro_exchange_config(self, exchange_id: str, public_only: bool = False) -> dict[str, Any]:
        """
        Tạo cấu hình cho ccxt.pro.

        Args:
            exchange_id (str): ID của sàn giao dịch
            public_only (bool): Chỉ giữ lại cấu hình cần thiết cho endpoint public

        Returns:
            dict: Cấu hình dùng để khởi tạo client ccxt.pro
        """
        config = dict(self.exchanges[exchange_id])
        if not public_only:
            return config

        public_config = {
            'enableRateLimit': config.get('enableRateLimit', True)
        }
        if 'options' in config:
            public_config['options'] = dict(config['options'])
        return public_config

    async def _get_or_create_pro_exchange(self, exchange_id: str, public_only: bool = False) -> Any:
        """
        Lấy hoặc tạo đối tượng sàn giao dịch ccxt.pro dùng lại được.
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            public_only (bool): Chỉ dùng endpoint public, không gửi credential
        
        Returns:
            object: Đối tượng sàn giao dịch ccxt.pro
        """
        if not hasattr(self, '_pro_instances'):
            self._pro_instances = {}

        instance_key = f"{exchange_id}:public" if public_only else exchange_id
        
        if instance_key not in self._pro_instances:
            if exchange_id not in self.exchanges:
                raise ExchangeError(exchange_id, "Sàn giao dịch không được hỗ trợ hoặc chưa được cấu hình")
            exchange_class = getattr(ccxt.pro, exchange_id)
            exchange_config = self._build_pro_exchange_config(exchange_id, public_only=public_only)
            self._pro_instances[instance_key] = exchange_class(exchange_config)
            self._apply_sandbox_mode(self._pro_instances[instance_key], exchange_id)
        
        return self._pro_instances[instance_key]

    async def close_all_pro_exchanges(self):
        """Đóng tất cả kết nối ccxt.pro."""
        if hasattr(self, '_pro_instances'):
            for exchange_id, exchange in self._pro_instances.items():
                try:
                    await exchange.close()
                except Exception:
                    pass
            self._pro_instances.clear()

    async def async_create_limit_buy_order(self, exchange_id, symbol, amount, price):
        """
        Tạo lệnh mua giới hạn (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần mua
            price (float): Giá mua
        
        Returns:
            dict: Thông tin lệnh đã tạo
        """
        try:
            await self._rate_limiter.async_acquire(exchange_id)
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.create_limit_buy_order(symbol, amount, price)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể tạo lệnh mua giới hạn cho {symbol}: {str(e)}")

    async def async_create_limit_sell_order(self, exchange_id, symbol, amount, price):
        """
        Tạo lệnh bán giới hạn (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần bán
            price (float): Giá bán
        
        Returns:
            dict: Thông tin lệnh đã tạo
        """
        try:
            await self._rate_limiter.async_acquire(exchange_id)
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.create_limit_sell_order(symbol, amount, price)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể tạo lệnh bán giới hạn cho {symbol}: {str(e)}")

    async def async_create_market_buy_order(self, exchange_id, symbol, amount, params=None):
        """
        Tạo lệnh mua thị trường (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần mua
            params (dict, optional): Tham số bổ sung
        
        Returns:
            dict: Thông tin lệnh đã tạo
        """
        params = params or {}
        try:
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.create_market_buy_order(symbol, amount, params)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể tạo lệnh mua thị trường cho {symbol}: {str(e)}")

    async def async_create_market_sell_order(self, exchange_id, symbol, amount, params=None):
        """
        Tạo lệnh bán thị trường (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            amount (float): Số lượng cần bán
            params (dict, optional): Tham số bổ sung
        
        Returns:
            dict: Thông tin lệnh đã tạo
        """
        params = params or {}
        try:
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.create_market_sell_order(symbol, amount, params)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể tạo lệnh bán thị trường cho {symbol}: {str(e)}")

    async def async_fetch_open_orders(self, exchange_id, symbol):
        """
        Lấy danh sách lệnh đang mở (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            list: Danh sách các lệnh đang mở
        """
        try:
            await self._rate_limiter.async_acquire(exchange_id)
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.fetch_open_orders(symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể lấy danh sách lệnh đang mở cho {symbol}: {str(e)}")

    async def async_fetch_closed_orders(self, exchange_id, symbol):
        """
        Lấy danh sách lệnh đã đóng (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            list: Danh sách các lệnh đã đóng
        """
        try:
            await self._rate_limiter.async_acquire(exchange_id)
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.fetch_closed_orders(symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể lấy danh sách lệnh đã đóng cho {symbol}: {str(e)}")

    async def async_cancel_order(self, exchange_id, order_id, symbol):
        """
        Hủy một lệnh (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            order_id (str): ID của lệnh cần hủy
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            dict: Thông tin lệnh đã hủy
        """
        try:
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.cancel_order(order_id, symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể hủy lệnh {order_id} cho {symbol}: {str(e)}")

    async def async_get_ticker(self, exchange_id, symbol):
        """
        Lấy thông tin ticker (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
        
        Returns:
            dict: Thông tin ticker
        """
        try:
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            return await pro_exchange.fetch_ticker(symbol)
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể lấy ticker cho {symbol}: {str(e)}")

    async def async_get_balance(self, exchange_id, symbol):
        """
        Lấy số dư tài sản (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của tài sản
        
        Returns:
            float: Số dư
        """
        try:
            clean_symbol = extract_base_asset(symbol) if symbol != 'USDT' else 'USDT'
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            balance = await pro_exchange.fetch_balance()
            if clean_symbol in balance['free'] and balance['free'][clean_symbol] != 0:
                return balance['free'][clean_symbol]
            return 0
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể lấy số dư của {symbol}: {str(e)}")

    async def async_emergency_convert(self, exchange_id, symbol, keep_percentage=0.01):
        """
        Chuyển đổi khẩn cấp tài sản sang USDT (async).
        
        Args:
            exchange_id (str): ID của sàn giao dịch
            symbol (str): Ký hiệu của cặp giao dịch
            keep_percentage (float): Phần trăm giữ lại
        
        Returns:
            dict: Thông tin lệnh bán
        """
        try:
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            
            # Hủy tất cả lệnh đang mở
            try:
                open_orders = await pro_exchange.fetch_open_orders(symbol)
                for order in open_orders:
                    await pro_exchange.cancel_order(order['id'], symbol)
            except Exception:
                pass
            
            # Lấy số dư
            base_asset = extract_base_asset(symbol)
            balance = await pro_exchange.fetch_balance()
            asset_balance = balance['free'].get(base_asset, 0)
            balance_to_sell = asset_balance - (asset_balance * keep_percentage)
            
            # Kiểm tra số dư tối thiểu
            ticker = await pro_exchange.fetch_ticker(symbol)
            min_amount_in_base = 10 / ticker['last']
            
            if balance_to_sell > min_amount_in_base:
                return await pro_exchange.create_market_sell_order(symbol, round(balance_to_sell, 4))
            else:
                log_info(f"Không đủ {base_asset} trên {exchange_id}.")
                return None
        except Exception as e:
            raise ExchangeError(exchange_id, f"Async: Không thể chuyển đổi khẩn cấp cho {symbol}: {str(e)}")

    async def async_create_futures_order(self, exchange_id, symbol, type, side, amount, params=None):
        """
        Tạo lệnh futures (async).
        
        Args:
            exchange_id (str): ID sàn giao dịch
            symbol (str): Ký hiệu cặp giao dịch
            type (str): Loại lệnh (market, limit)
            side (str): Hướng đặt lệnh (buy, sell)
            amount (float): Số lượng
            params (dict, optional): Tham số bổ sung
        
        Returns:
            dict: Thông tin lệnh
        """
        params = params or {}
        try:
            if not symbol.endswith(':USDT') and ':USDT' not in symbol:
                symbol = f"{extract_base_asset(symbol)}:USDT"
            
            pro_exchange = await self._get_or_create_pro_exchange(exchange_id)
            
            if type == 'market':
                if side == 'buy':
                    return await pro_exchange.create_market_buy_order(symbol, amount, params)
                elif side == 'sell':
                    return await pro_exchange.create_market_sell_order(symbol, amount, params)
            elif type == 'limit':
                price = params.pop('price', None)
                if not price:
                    raise FuturesError(exchange_id, "Giá bắt buộc phải có cho lệnh giới hạn")
                if side == 'buy':
                    return await pro_exchange.create_limit_buy_order(symbol, amount, price, params)
                elif side == 'sell':
                    return await pro_exchange.create_limit_sell_order(symbol, amount, price, params)
            
            raise FuturesError(exchange_id, f"Loại lệnh không hợp lệ: {type}")
        except Exception as e:
            raise FuturesError(exchange_id, f"Async: Không thể tạo lệnh futures: {str(e)}")
