"""
Các lớp ngoại lệ tùy chỉnh cho ứng dụng.
"""


class ArbitrageError(Exception):
    """Lỗi cơ sở cho tất cả các ngoại lệ trong ứng dụng."""
    pass


class ExchangeError(ArbitrageError):
    """Lỗi liên quan đến giao tiếp với sàn giao dịch."""
    
    def __init__(self, exchange: str, message: str) -> None:
        self.exchange = exchange
        self.message = message
        super().__init__(f"Lỗi trên sàn {exchange}: {message}")


class InsufficientBalanceError(ArbitrageError):
    """Lỗi số dư không đủ để thực hiện giao dịch."""
    
    def __init__(self, exchange: str, asset: str, required: float, available: float) -> None:
        self.exchange = exchange
        self.asset = asset
        self.required = required
        self.available = available
        message = f"Số dư không đủ trên {exchange}. Cần {round(required, 3)} {asset}, hiện có {round(available, 3)} {asset}."
        super().__init__(message)


class OrderError(ArbitrageError):
    """Lỗi liên quan đến đặt lệnh."""
    
    def __init__(self, exchange: str, order_type: str, message: str) -> None:
        self.exchange = exchange
        self.order_type = order_type
        self.message = message
        super().__init__(f"Lỗi khi đặt lệnh {order_type} trên {exchange}: {message}")


class OrderFillTimeoutError(ArbitrageError):
    """Lỗi khi đơn hàng không được điền trong thời gian quy định."""
    
    def __init__(self, exchange: str, order_id: str, timeout: int) -> None:
        self.exchange = exchange
        self.order_id = order_id
        self.timeout = timeout
        super().__init__(f"Lệnh {order_id} trên {exchange} không được điền trong {timeout} giây.")


class ConfigError(ArbitrageError):
    """Lỗi liên quan đến cấu hình."""
    
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Lỗi cấu hình: {message}")


class NotificationError(ArbitrageError):
    """Lỗi liên quan đến gửi thông báo."""
    
    def __init__(self, service: str, message: str) -> None:
        self.service = service
        self.message = message
        super().__init__(f"Lỗi khi gửi thông báo qua {service}: {message}")


class DeltaNeutralError(ArbitrageError):
    """Lỗi liên quan đến chiến lược Delta-Neutral."""
    
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Lỗi Delta-Neutral: {message}")


class FuturesError(ArbitrageError):
    """Lỗi liên quan đến giao dịch futures."""
    
    def __init__(self, exchange: str, message: str) -> None:
        self.exchange = exchange
        self.message = message
        super().__init__(f"Lỗi Futures trên {exchange}: {message}")