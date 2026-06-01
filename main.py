#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Điểm chạy chính của ứng dụng BMLB Arbitrage Bot.
"""
import os
import sys
import time
import asyncio
import argparse
import logging
import concurrent.futures
import aiohttp
from colorama import Style, Fore, init
from dotenv import load_dotenv

# Khởi tạo colorama
init()

# Import các dịch vụ
from services.exchange_service import ExchangeService
from services.balance_service import BalanceService
from services.order_service import OrderService
from services.notification_service import NotificationService
from services.database_service import DatabaseService

# Import multi-pair
from services.multi_pair_manager import MultiPairManager

# Import các bot
from bots.classic_bot import ClassicBot
from bots.delta_neutral_bot import DeltaNeutralBot
from bots.fake_money_bot import FakeMoneyBot

# Import các module tiện ích
from utils.logger import log_info, log_error, log_warning, logger, safe_print, configure_console_encoding
from utils.helpers import show_time
from utils.session_recovery import SessionRecovery
from utils.telegram import TelegramNotifier
from utils.keys_store import ensure_keys_interactive, keys_for_exchange_service, load_keys
from configs import PYTHON_COMMAND, ENABLE_TELEGRAM, BOT_MODES, FUTURES_SYMBOL

configure_console_encoding()


def configure_async_dns_resolver() -> None:
    """Chuyển aiohttp sang threaded resolver trên Windows để tránh lỗi DNS của aiodns."""
    if sys.platform != 'win32':
        return

    aiohttp.connector.DefaultResolver = aiohttp.ThreadedResolver
    aiohttp.resolver.DefaultResolver = aiohttp.ThreadedResolver


configure_async_dns_resolver()


def setup_logging(level=logging.INFO):
    """
    Thiết lập cấu hình logging nâng cao.
    
    Args:
        level: Cấp độ logging (mặc định là INFO)
    """
    # Tạo thư mục logs nếu chưa tồn tại
    os.makedirs('logs', exist_ok=True)
    
    # Định dạng thời gian cho tên file log
    log_filename = f"logs/arbitrage_bot_{time.strftime('%Y-%m-%d')}.log"
    
    # Định dạng cho các message log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Cấu hình logging
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )


def display_banner():
    """Hiển thị banner khi khởi động ứng dụng."""
    safe_print("""
                ╔═╗─╔╗────────────────╔═╗─╔╗─────────╔══╗───╔╗
                ║║╚╗║║────────────────║║╚╗║║─────────║╔╗║───║║
                ║╔╗╚╝╠══╦╗╔╦╗─╔╦══╦═╗─║╔╗╚╝╠══╦══╦══╗║╚╝╚╦═╗║╚═╗
                ║║╚╗║║╔╗║║║║║─║║║═╣╔╗╗║║╚╗║║╔╗║╔╗║╔═╝║╔═╗║╔╗╣╔╗║
                ║║─║║║╚╝║╚╝║╚═╝║║═╣║║║║║─║║║╚╝║╚╝║╚═╗║╚═╝║║║║║║║
                ╚╝─╚═╩═╗╠══╩═╗╔╩══╩╝╚╝╚╝─╚═╩═╗╠══╩══╝╚═══╩╝╚╩╝╚╝
                ─────╔═╝║──╔═╝║────────────╔═╝║
                ─────╚══╝──╚══╝────────────╚══╝
    """)
    safe_print(f"\n{Fore.CYAN}BMLB Arbitrage Bot{Style.RESET_ALL} - Giao dịch chênh lệch giá crypto tự động")
    safe_print("\nGithub: nguyenngocbinh\nTwitter: @nanabi88\n")


def parse_arguments():
    """
    Phân tích tham số dòng lệnh.
    
    Returns:
        argparse.Namespace: Đối tượng chứa tham số dòng lệnh
    """
    parser = argparse.ArgumentParser(description='BMLB Arbitrage Bot - Giao dịch chênh lệch giá crypto')
    
    # Tham số bắt buộc
    parser.add_argument('mode', choices=BOT_MODES, help='Chế độ bot (fake-money, classic, delta-neutral)')
    parser.add_argument('renew_time', type=int, help='Thời gian làm mới (phút)')
    parser.add_argument('usdt_amount', type=float, help='Số lượng USDT để giao dịch')
    
    # Các sàn giao dịch
    parser.add_argument('exchange1', help='Sàn giao dịch 1')
    parser.add_argument('exchange2', help='Sàn giao dịch 2')
    parser.add_argument('exchange3', help='Sàn giao dịch 3')
    
    # Tham số tùy chọn
    parser.add_argument('symbol', nargs='?', help='Cặp giao dịch (nếu bỏ trống sẽ tìm tự động)')
    
    # Thêm các tùy chọn mới
    parser.add_argument('--debug', action='store_true', help='Kích hoạt chế độ debug')
    parser.add_argument('--no-banner', action='store_true', help='Không hiển thị banner')
    parser.add_argument('--dry-run', action='store_true', help='Chạy mà không thực hiện giao dịch thực tế')
    parser.add_argument('--no-recovery', action='store_true', help='Bỏ qua khôi phục phiên bị dừng')
    parser.add_argument('--symbols', nargs='+', help='Nhiều cặp giao dịch (vd: --symbols BTC/USDT ETH/USDT)')
    
    return parser.parse_args()


def get_user_input():
    """
    Lấy thông tin từ người dùng qua giao diện dòng lệnh.
    
    Returns:
        dict: Thông tin nhập từ người dùng
    """
    inputs = {}
    
    # Danh sách các thông tin cần nhập
    input_list = [
        ("mode", "mode (fake-money, classic, delta-neutral)"),
        ("renew", "renew time (in minutes)"),
        ("balance", "balance to use (USDT)"),
        ("exchange_1", "exchange 1"),
        ("exchange_2", "exchange 2"),
        ("exchange_3", "exchange 3"),
        ("crypto", "crypto pair (để trống để tìm tự động)")
    ]
    
    print(f"{Fore.YELLOW}Nhập thông tin cấu hình:{Style.RESET_ALL}")
    # Lấy thông tin từ người dùng
    for key, prompt in input_list:
        user_input = input(f"{Fore.CYAN}{prompt}{Style.RESET_ALL} >>> ")
        inputs[key] = user_input
    
    print()  # Dòng trống cho đẹp
    return inputs


async def find_best_symbol(exchange_service, exchanges):
    """
    Tìm cặp giao dịch tốt nhất cho arbitrage.
    
    Args:
        exchange_service (ExchangeService): Dịch vụ sàn giao dịch
        exchanges (list): Danh sách tên các sàn giao dịch
    
    Returns:
        str: Ký hiệu của cặp giao dịch tốt nhất
    """
    log_info("Đang tìm cặp giao dịch tốt nhất... (có thể mất vài phút)")
    
    try:
        # Danh sách các cặp giao dịch phổ biến để kiểm tra
        common_pairs = [
            "BTC/USDT", "ETH/USDT", "XRP/USDT", "LTC/USDT", "ADA/USDT",
            "DOT/USDT", "DOGE/USDT", "SOL/USDT", "AVAX/USDT", "MATIC/USDT"
        ]
        
        # Danh sách để lưu chênh lệch giá của các cặp giao dịch
        pair_spreads = []
        
        # Kiểm tra từng cặp giao dịch
        for pair in common_pairs:
            try:
                # Lấy giá bid và ask trên mỗi sàn
                bid_prices = {}
                ask_prices = {}
                
                # Thu thập giá từ các sàn
                for exchange_id in exchanges:
                    ticker = await exchange_service.get_ticker(exchange_id, pair)
                    bid_prices[exchange_id] = ticker['bid']
                    ask_prices[exchange_id] = ticker['ask']
                
                # Tìm giá bán thấp nhất và giá mua cao nhất
                min_ask = min(ask_prices.values())
                max_bid = max(bid_prices.values())
                
                # Tính chênh lệch giá
                spread = (max_bid - min_ask) / min_ask * 100
                
                # Thêm vào danh sách
                pair_spreads.append((pair, spread))
                
                log_info(f"Cặp {pair}: Chênh lệch giá {spread:.4f}%")
                
            except Exception as e:
                log_warning(f"Không thể lấy thông tin cho cặp {pair}: {str(e)}")
        
        # Sắp xếp các cặp theo chênh lệch giá giảm dần
        pair_spreads.sort(key=lambda x: x[1], reverse=True)
        
        if pair_spreads:
            # Lấy cặp có chênh lệch giá cao nhất
            best_pair = pair_spreads[0][0]
            log_info(f"Đã tìm thấy cặp giao dịch tốt nhất: {best_pair} với chênh lệch giá {pair_spreads[0][1]:.4f}%")
            
            # Lưu cặp giao dịch vào tệp
            with open('symbol.txt', 'w') as f:
                f.write(best_pair)
            
            return best_pair
        else:
            # Nếu không tìm thấy cặp nào, sử dụng BTC/USDT làm mặc định
            default_pair = "BTC/USDT"
            log_warning(f"Không tìm thấy cặp giao dịch phù hợp. Sử dụng mặc định: {default_pair}")
            
            with open('symbol.txt', 'w') as f:
                f.write(default_pair)
            
            return default_pair
            
    except Exception as e:
        log_error(f"Lỗi khi tìm cặp giao dịch tốt nhất: {str(e)}")
        
        # Sử dụng cặp mặc định trong trường hợp lỗi
        default_pair = "BTC/USDT"
        log_warning(f"Sử dụng cặp giao dịch mặc định: {default_pair}")
        
        with open('symbol.txt', 'w') as f:
            f.write(default_pair)
        
        return default_pair


async def run_bot(
    mode,
    symbol,
    usdt_amount,
    renew_time,
    exchanges,
    dry_run=False,
    symbols=None,
    credentials=None,
):
    """
    Chạy bot giao dịch với các tham số đã cho.
    
    Args:
        mode (str): Chế độ bot (fake-money, classic, delta-neutral)
        symbol (str): Ký hiệu của cặp giao dịch (single pair)
        usdt_amount (float): Số lượng USDT để giao dịch
        renew_time (int): Thời gian làm mới (phút)
        exchanges (list): Danh sách tên các sàn giao dịch
        dry_run (bool): Nếu True, bot sẽ không thực hiện giao dịch thực tế
        symbols (list, optional): Danh sách cặp giao dịch cho multi-pair
        
    Returns:
        float: Tổng lợi nhuận (phần trăm)
    """
    bot = None
    db_service = None
    recovery = None
    exchange_service = None
    
    try:
        creds = credentials or keys_for_exchange_service(load_keys())
        exchange_service = ExchangeService(credentials=creds)
        balance_service = BalanceService(exchange_service)
        order_service = OrderService(exchange_service)
        notification_service = NotificationService(ENABLE_TELEGRAM)
        telegram_notifier = TelegramNotifier(enabled=ENABLE_TELEGRAM)
        db_service = DatabaseService()
        recovery = SessionRecovery(db_service)
        
        # Log thông tin khởi động
        log_info(f"Khởi động bot với chế độ: {mode}, số tiền: {usdt_amount} USDT, thời gian làm mới: {renew_time} phút")
        if dry_run:
            log_info("Chế độ dry-run được kích hoạt - không thực hiện giao dịch thực tế")
        
        # Khởi tạo balance files
        balance_service.initialize_balance_files(usdt_amount)
        
        # Multi-pair mode
        if symbols and len(symbols) > 1:
            log_info(f"Multi-pair mode: {len(symbols)} cặp")

            def _bot_factory():
                if mode == "fake-money" or dry_run:
                    return FakeMoneyBot(exchange_service, balance_service, order_service, notification_service, db_service)
                elif mode == "classic":
                    return ClassicBot(exchange_service, balance_service, order_service, notification_service, db_service)
                elif mode == "delta-neutral":
                    return DeltaNeutralBot(exchange_service, balance_service, order_service, notification_service, db_service)
                else:
                    return FakeMoneyBot(exchange_service, balance_service, order_service, notification_service, db_service)

            manager = MultiPairManager(
                _bot_factory, symbols, exchanges,
                usdt_amount, renew_time, notification_service
            )
            results = await manager.start()
            return manager.total_profit_pct

        # Single pair mode
        # Tìm cặp giao dịch nếu không được chỉ định
        if mode == 'classic':
            symbol = FUTURES_SYMBOL
            log_info(f'Classic futures mode: {symbol}')
        elif not symbol:
            symbol = await find_best_symbol(exchange_service, exchanges)
        else:
            log_info(f"Sử dụng cặp giao dịch đã chỉ định: {symbol}")
        
        # Khởi tạo bot dựa trên chế độ
        if mode == "fake-money" or dry_run:
            bot = FakeMoneyBot(exchange_service, balance_service, order_service, notification_service, db_service)
            log_info("Sử dụng bot mô phỏng (không thực hiện giao dịch thực tế)")
        elif mode == "classic":
            bot = ClassicBot(exchange_service, balance_service, order_service, notification_service, db_service)
            log_info("Sử dụng bot arbitrage cổ điển")
        elif mode == "delta-neutral":
            bot = DeltaNeutralBot(exchange_service, balance_service, order_service, notification_service, db_service)
            log_info("Sử dụng bot delta-neutral")
        else:
            log_error(f"Chế độ không hợp lệ: {mode}")
            return 0
        
        # Cấu hình bot
        timeout = renew_time * 60  # Chuyển đổi phút sang giây
        bot.configure(symbol, exchanges, timeout, usdt_amount, symbol)
        bot.telegram_notifier = telegram_notifier
        
        # Chạy bot
        start_time = time.time()
        try:
            profit_pct = await bot.start()
            end_time = time.time()
            
            # Log thông tin kết thúc
            elapsed_time = time.strftime('%H:%M:%S', time.gmtime(end_time - start_time))
            log_info(f"Bot đã kết thúc sau {elapsed_time}. Tổng lợi nhuận: {profit_pct:.4f}%")
            
            return profit_pct
            
        except KeyboardInterrupt:
            # Khi Ctrl+C, phiên sẽ được xử lý bởi bot.stop() trong signal handler
            raise
        except Exception as e:
            # Nếu xảy ra lỗi trong bot, đánh dấu session là interrupted
            error_msg = f"Lỗi trong khi chạy bot: {str(e)}"
            log_error(error_msg)
            
            if bot and bot.session_id and db_service:
                try:
                    log_warning(f"Đánh dấu phiên #{bot.session_id} là interrupted")
                    recovery.mark_interrupted(bot.session_id, error_msg)
                except Exception as recovery_error:
                    log_error(f"Lỗi khi đánh dấu phiên interrupted: {str(recovery_error)}")

            if telegram_notifier.enabled:
                await telegram_notifier.notify_critical_error('run_bot', error_msg)
            
            raise
        
    except Exception as e:
        log_error(f"Lỗi khi chạy bot: {str(e)}")
        return 0
    finally:
        if exchange_service:
            try:
                await exchange_service.close_all_pro_exchanges()
            except Exception as close_error:
                log_warning(f"Không thể đóng toàn bộ kết nối pro: {str(close_error)}")


async def main(credentials=None):
    """Hàm chính của ứng dụng."""
    try:
        # Thiết lập logging
        setup_logging()
        
        # Khởi tạo database service để kiểm tra phiên bị dừng
        db_service = DatabaseService()
        recovery = SessionRecovery(db_service)
        
        # Nếu có tham số dòng lệnh
        if len(sys.argv) > 1:
            args = parse_arguments()
            
            # Thiết lập cấp độ logging dựa trên tham số --debug
            if args.debug:
                setup_logging(logging.DEBUG)
                log_info("Chế độ debug được kích hoạt")
            
            # Hiển thị banner nếu không có tham số --no-banner
            if not args.no_banner:
                display_banner()
            
            mode = args.mode
            renew_time = args.renew_time
            usdt_amount = args.usdt_amount
            exchanges = [args.exchange1, args.exchange2, args.exchange3]
            symbol = args.symbol
            dry_run = args.dry_run
            no_recovery = args.no_recovery
            symbols = args.symbols  # Multi-pair
            recovered_session_id = None
            
        # Nếu không có tham số dòng lệnh, lấy thông tin từ người dùng
        else:
            # Hiển thị banner
            display_banner()
            
            inputs = get_user_input()
            
            mode = inputs["mode"]
            renew_time = int(inputs["renew"])
            usdt_amount = float(inputs["balance"])
            exchanges = [inputs["exchange_1"], inputs["exchange_2"], inputs["exchange_3"]]
            symbol = inputs["crypto"] if inputs["crypto"] else None
            dry_run = False  # Mặc định không phải dry run khi nhập thủ công
            no_recovery = False
            symbols = None  # Manual mode không hỗ trợ multi-pair
            recovered_session_id = None
        
        # ─── PHÁT HIỆN & KHÔI PHỤC PHIÊN BỊ DỪNG ─────────────────────────
        # Kiểm tra xem có phiên bị dừng chưa được khôi phục
        interrupted_sessions = recovery.get_interrupted_sessions()
        if interrupted_sessions and not no_recovery:
            safe_print('')
            recovered_session_id = recovery.show_interrupted_sessions()
            
            if recovered_session_id:
                # Lấy thông tin khôi phục
                recovery_info = recovery.get_recovery_info(recovered_session_id)
                
                if recovery_info:
                    # Sử dụng thông tin từ phiên cũ để khôi phục
                    mode = recovery_info['mode']
                    symbol = recovery_info['symbol']
                    usdt_amount = recovery_info['usdt_amount']
                    renew_time = recovery_info['renew_time_minutes']
                    exchanges = recovery_info['exchanges']
                    
                    log_info(f"Khôi phục phiên #{recovered_session_id}")
                    log_info(f"Lợi nhuận trước đó: {recovery_info['cumulative_profit_pct']:.4f}%")
                    
                    # Tạo vốn mới từ balance file (hoặc sử dụng số dư cuối từ phiên cũ)
                    try:
                        with open('balance.txt', 'r') as f:
                            usdt_amount = float(f.read().strip())
                            log_info(f"Sử dụng balance từ balance.txt: {usdt_amount} USDT")
                    except Exception as e:
                        log_warning(f"Không thể đọc balance.txt, sử dụng vốn từ phiên cũ: {str(e)}")
            else:
                safe_print('')
        
        # ─── KẾT THÚC PHÁT HIỆN PHIÊN ─────────────────────────────────────
        
        # Kiểm tra chế độ
        if mode not in BOT_MODES:
            log_error(f"Chế độ không hợp lệ: {mode}. Các chế độ hợp lệ: {', '.join(BOT_MODES)}")
            sys.exit(1)
            
        # Chạy bot
        i = 0
        while True:
            # Chạy bot với các tham số đã cho
            profit_pct = await run_bot(
                mode, symbol, usdt_amount, renew_time, exchanges, dry_run, symbols,
                credentials=credentials,
            )
            
            # Đọc số dư mới từ tệp
            with open('balance.txt', 'r') as f:
                usdt_amount = float(f.read().strip())
            
            # Tăng số lần chạy
            i += 1
            
            # Nếu là lần chạy đầu tiên mà có lỗi, thoát khỏi vòng lặp
            if i == 1 and profit_pct == 0:
                log_error("Chạy bot lần đầu không thành công. Thoát chương trình.")
                break
            
    except KeyboardInterrupt:
        log_info("Đã nhận tín hiệu ngắt. Thoát chương trình.")
    except Exception as e:
        log_error(f"Lỗi không xác định: {str(e)}")
    finally:
        log_info("Chương trình kết thúc.")


def _bootstrap_frozen_argv() -> None:
    """Packaged app: default classic futures session without manual CLI args."""
    if getattr(sys, 'frozen', False) and len(sys.argv) <= 1:
        sys.argv.extend(['classic', '60', '100', 'binance', 'mexc', 'mexc'])


if __name__ == "__main__":
    load_dotenv()
    _bootstrap_frozen_argv()

    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    api_keys = ensure_keys_interactive()
    asyncio.run(main(credentials=keys_for_exchange_service(api_keys)))