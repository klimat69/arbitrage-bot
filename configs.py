"""
Tệp cấu hình chứa các thông số cấu hình chung cho bot giao dịch.
"""
import os
from dotenv import load_dotenv

# Tải biến môi trường từ tệp .env
load_dotenv()

# Cấu hình chung
PYTHON_COMMAND = os.getenv('PYTHON_COMMAND', 'python')
ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', 'false').lower() == 'true'
ENABLE_CTRL_C_HANDLING = os.getenv('ENABLE_CTRL_C_HANDLING', 'false').lower() == 'true'

# Tiêu chí lợi nhuận
PROFIT_CRITERIA_PCT = 0.05  # % lợi nhuận tối thiểu (đủ bù phí ~0.1-0.2%)
PROFIT_CRITERIA_USD = 0.5   # Lợi nhuận USD tối thiểu

# Thông số giao dịch
BETTER_FILL_LESS_PROFITS = True  # Điều chỉnh fill để giảm lợi nhuận
FIRST_ORDERS_FILL_TIMEOUT = 300  # Thời gian chờ tối đa để fill đơn hàng đầu tiên (giây)

# Danh sách các sàn giao dịch hỗ trợ
SUPPORTED_EXCHANGES = ['kucoin', 'binance', 'bybit', 'okx', 'kucoinfutures', 'mexc']

# Binance → MEXC futures pipeline
FUTURES_SYMBOL = os.getenv('FUTURES_SYMBOL', 'BTC/USDT:USDT')
SIGNAL_EXCHANGE = os.getenv('SIGNAL_EXCHANGE', 'binance')
EXECUTION_EXCHANGE = os.getenv('EXECUTION_EXCHANGE', 'mexc')
LARGE_ORDER_THRESHOLD_BTC = float(os.getenv('LARGE_ORDER_THRESHOLD_BTC', '5.0'))
ORDER_TTL_SECONDS = float(os.getenv('ORDER_TTL_SECONDS', '3.0'))
BINANCE_WS_STREAM = os.getenv('BINANCE_WS_STREAM', 'btcusdt@depth20@100ms')
BINANCE_WS_URL = os.getenv(
    'BINANCE_WS_URL',
    f'wss://fstream.binance.com/ws/{BINANCE_WS_STREAM}',
)

# Phí giao dịch của từng sàn
EXCHANGE_FEES = {
    'binance': {'give': 0.001, 'receive': 0.001},
    'mexc': {'give': 0.0, 'receive': 0.0},
    'kucoin': {'give': 0.001, 'receive': 0.001},
    'okx': {'give': 0.0008, 'receive': 0.001},
    'bybit': {'give': 0.001, 'receive': 0.001},
    'kucoinfutures': {'give': 0.001, 'receive': 0.001},
    # Có thể thêm nhiều sàn khác nếu cần
}

# Cấu hình Delta-Neutral
DEFAULT_FUTURES_EXCHANGE = 'kucoinfutures'  # Sàn futures mặc định
DEFAULT_LEVERAGE = 1  # Đòn bẩy mặc định
SHORT_AMOUNT_RATIO = 1/3  # Tỷ lệ số tiền để mở vị thế short (1/3 tổng số tiền)
MIN_FUTURES_QUANTITY = 1  # Số lượng tối thiểu cho giao dịch futures

# Chế độ bot
BOT_MODES = ['fake-money', 'classic', 'delta-neutral']

# Đường dẫn tệp tin
BALANCE_FILE = 'balance.txt'
START_BALANCE_FILE = 'start_balance.txt'
SYMBOL_FILE = 'symbol.txt'

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'arbitrage.db')

# Risk Management
RISK_CONFIG = {
    'enabled': True,
    'max_drawdown_pct': 5.0,           # Drawdown tối đa: 5%
    'max_loss_per_trade_usd': 10.0,    # Lỗ tối đa mỗi giao dịch: 10 USD
    'max_session_loss_pct': 3.0,       # Lỗ tối đa trong phiên: 3%
    'max_consecutive_losses': 5,        # Lỗ liên tiếp tối đa: 5 lần
    'max_slippage_pct': 0.5,           # Slippage tối đa cho phép: 0.5%
    'cooldown_after_loss_sec': 30,     # Cooldown sau lỗ lớn: 30 giây
}