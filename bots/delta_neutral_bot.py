"""
Bot giao dịch chênh lệch giá kết hợp với chiến lược delta-neutral.
"""
import time
import asyncio
from asyncio import gather
import sys
import traceback

from typing import Any, Optional
from utils.logger import log_info, log_error, log_warning, log_debug
from utils.exceptions import ArbitrageError, ExchangeError, InsufficientBalanceError, OrderError
from utils.helpers import calculate_average, extract_base_asset
from bots.base_bot import BaseBot
from configs import EXCHANGE_FEES, RISK_CONFIG


class DeltaNeutralBot(BaseBot):
    """
    Bot giao dịch kết hợp chênh lệch giá và vị thế delta-neutral.
    Mua vào tiền điện tử trên các sàn spot và mở vị thế short trên futures.
    """
    
    def __init__(self, exchange_service: Any, balance_service: Any, order_service: Any,
                 notification_service: Any, db_service: Any = None,
                 risk_config: Optional[dict[str, Any]] = None) -> None:
        """
        Khởi tạo bot giao dịch delta-neutral.
        
        Args:
            exchange_service (ExchangeService): Dịch vụ sàn giao dịch
            balance_service (BalanceService): Dịch vụ quản lý số dư
            order_service (OrderService): Dịch vụ quản lý lệnh
            notification_service (NotificationService): Dịch vụ thông báo
            db_service (DatabaseService, optional): Dịch vụ cơ sở dữ liệu
            risk_config (dict, optional): Cấu hình quản lý rủi ro
        """
        super().__init__(
            exchange_service,
            balance_service,
            order_service,
            notification_service,
            {'fees': EXCHANGE_FEES},
            db_service,
            risk_config or RISK_CONFIG
        )
        
        # Biến cho chiến lược delta-neutral
        self.futures_exchange = 'kucoinfutures'  # Sàn futures mặc định
        self.futures_amount = 0  # Số lượng tiền điện tử đã short
        self.leverage = 1  # Đòn bẩy
        self.short_amount_ratio = 1/3  # Tỷ lệ số tiền để mở vị thế short (1/3 tổng số tiền)
        
        # Thêm biến thống kê
        self.stats = {
            'opportunities_found': 0,
            'trades_executed': 0,
            'failed_trades': 0,
            'total_volume': 0
        }
    
    async def start(self) -> float:
        """
        Bắt đầu chạy bot giao dịch delta-neutral.
        
        Returns:
            float: Tổng lợi nhuận (phần trăm)
        """
        try:
            log_info(f"Bắt đầu phiên giao dịch delta-neutral với tham số: {self.symbol}, {self.exchanges}, {self.howmuchusd} USDT")
            self.start_time = time.time()
            
            # Tạo phiên giao dịch trong database
            try:
                self.session_id = self.db.create_session(
                    'delta-neutral', self.symbol, self.exchanges,
                    self.howmuchusd, int(self.timeout - time.time()) // 60
                )
            except Exception as e:
                log_error(f"Lỗi khi tạo phiên trong database: {str(e)}")
            
            # Tính toán số tiền để mở vị thế delta-neutral
            spot_investment = self.howmuchusd * (2/3)  # 2/3 số tiền cho giao dịch spot
            futures_investment = self.howmuchusd * (1/3)  # 1/3 số tiền cho vị thế short
            
            # Kiểm tra số dư trên các sàn spot
            try:
                await self.balance_service.check_balances(
                    self.exchanges, 
                    'USDT', 
                    spot_investment, 
                    self.notification_service
                )
            except InsufficientBalanceError as e:
                log_error(f"Không đủ số dư: {str(e)}")
                return 0
            
            # Kiểm tra số dư trên sàn futures
            try:
                futures_balance = await self.balance_service.get_balance(self.futures_exchange, 'USDT')
                
                # Nếu số dư trên sàn futures không đủ, chuyển tiền từ spot sang futures
                if futures_balance < futures_investment:
                    log_info(f"Số dư trên {self.futures_exchange} không đủ. Cần chuyển thêm {round(futures_investment - futures_balance, 3)} USDT.")
                    
                    # Chuyển tiền từ sàn spot (sàn đầu tiên trong danh sách) sang futures
                    if 'kucoin' in self.exchanges and self.futures_exchange == 'kucoinfutures':
                        transfer_amount = round(futures_investment - futures_balance, 3)
                        
                        if transfer_amount > 1:  # Đảm bảo số tiền chuyển > 1 USDT
                            self.balance_service.transfer_between_accounts(
                                'kucoin', 
                                'USDT', 
                                transfer_amount, 
                                'spot', 
                                'future'
                            )
                            
                            log_info(f"{transfer_amount} USDT đã được chuyển từ KuCoin Spot sang KuCoin Futures thành công.")
                            
                            if self.notification_service:
                                self.notification_service.send_message(
                                    f"{transfer_amount} USDT đã được chuyển từ KuCoin Spot sang KuCoin Futures thành công."
                                )
            except Exception as e:
                log_error(f"Lỗi khi kiểm tra số dư futures: {str(e)}")
                return 0
            
            # Lấy giá trung bình toàn cầu
            try:
                average_price = await self.exchange_service.get_global_average_price(self.exchanges, self.symbol)
                log_info(f"Giá trung bình toàn cầu cho {self.symbol}: {average_price}")
            except Exception as e:
                log_error(f"Không thể lấy giá trung bình toàn cầu: {str(e)}")
                return 0
            
            # Khởi tạo số dư ảo
            self.usd = self.balance_service.initialize_balances(self.exchanges, self.symbol, spot_investment)
            self.crypto = {exchange: 0 for exchange in self.exchanges}  # Khởi tạo số dư crypto bằng 0
            
            # Đặt lệnh mua ban đầu trên các sàn spot (async - đồng thời)
            success = await self.async_order_service.place_initial_orders(
                self.exchanges, 
                self.symbol, 
                (spot_investment / 2) / (len(self.exchanges) * average_price), 
                average_price, 
                self.notification_service
            )
            
            if not success:
                log_warning("Không thể đặt lệnh mua ban đầu. Dừng bot.")
                return 0
            
            # Cập nhật số dư crypto sau khi đặt lệnh mua ban đầu
            self.crypto = self.balance_service.initialize_crypto_balances(
                self.exchanges, 
                self.symbol, 
                average_price, 
                spot_investment
            )
            
            # Tính tổng số lượng crypto đã mua
            total_crypto = sum(self.crypto.values())
            
            # Cập nhật số lượng crypto mỗi giao dịch
            self.crypto_per_transaction = total_crypto / len(self.exchanges) * 0.99  # Giảm 1% để đảm bảo đủ số dư
            
            # Mở vị thế short trên sàn futures
            try:
                # Tính số lượng cần short
                min_futures_quantity = 1  # Số lượng tối thiểu
                futures_symbol = f"{extract_base_asset(self.symbol)}:USDT"  # Đảm bảo đúng định dạng của futures
                
                # Lấy cặp giao dịch futures
                futures_symbol = self.symbol.replace('/', ':') if '/' in self.symbol else self.symbol
                if not futures_symbol.endswith(':USDT'):
                    futures_symbol = f"{extract_base_asset(self.symbol)}:USDT"
                
                # Tính số lượng cần short dựa trên giá trung bình và số tiền đầu tư
                quantity_to_short = max(min_futures_quantity, round(futures_investment / average_price, 3))
                
                # Đặt lệnh short (async)
                await self.async_order_service.place_futures_short_order(
                    self.futures_exchange, 
                    futures_symbol, 
                    quantity_to_short, 
                    self.leverage
                )
                
                # Lưu số lượng đã short
                self.futures_amount = quantity_to_short
                
                # Gửi thông báo
                message = f"Đã đặt lệnh Delta-neutral Short cho {round(futures_investment, 3)} USDT ({quantity_to_short} {extract_base_asset(self.symbol)}) trên {self.futures_exchange}."
                log_info(message)
                
                if self.notification_service:
                    self.notification_service.send_message(message)
                
                # Đợi lệnh được thực hiện
                log_info("Đang đợi 120 giây để lệnh short được thực hiện...")
                
                # Kiểm tra trạng thái lệnh short (async)
                short_filled = await self.async_order_service.wait_for_futures_order_fill(
                    self.futures_exchange, 
                    futures_symbol, 
                    120
                )
                
                if not short_filled:
                    log_error("Lệnh Delta-neutral Short không được thực hiện thành công. Thoát chương trình.")
                    return 0
                    
            except Exception as e:
                log_error(f"Lỗi khi mở vị thế short: {str(e)}")
                log_debug(f"Chi tiết lỗi: {traceback.format_exc()}")
                return 0
            
            # Bắt đầu vòng lặp theo dõi sách lệnh
            await self._start_orderbook_loop()
            
            # Hiển thị thống kê
            self._display_stats()
            
            # Dừng bot và đóng vị thế
            return await self.stop()
            
        except Exception as e:
            log_error(f"Lỗi khi chạy bot: {str(e)}")
            log_debug(f"Chi tiết lỗi: {traceback.format_exc()}")
            
            # Ghi lỗi vào database
            if self.session_id:
                try:
                    self.db.record_error('bot_crash', str(e), session_id=self.session_id, details=traceback.format_exc())
                    self.db.update_session(self.session_id, status='error', error_message=str(e))
                except Exception:
                    pass
            
            # Thực hiện bán khẩn cấp và đóng vị thế nếu có lỗi
            try:
                await self._emergency_stop()
            except Exception as cleanup_error:
                log_error(f"Lỗi khi dừng khẩn cấp: {str(cleanup_error)}")
                
            return 0
    
    async def stop(self) -> float:
        """
        Dừng bot giao dịch và thực hiện các thao tác dọn dẹp.
        
        Returns:
            float: Tổng lợi nhuận (phần trăm)
        """
        # Bán tất cả crypto trên tất cả sàn (async - đồng thời)
        try:
            log_info(f"Bán tất cả {self.symbol} trên {self.exchanges} (async)")
            await self.async_order_service.async_emergency_sell(self.symbol, self.exchanges)
            log_info("Đã bán tất cả crypto thành công")
        except Exception as e:
            log_error(f"Lỗi khi bán crypto: {str(e)}")
        
        # Đóng vị thế short (async)
        try:
            if self.futures_amount > 0:
                # Lấy cặp giao dịch futures
                futures_symbol = self.symbol.replace('/', ':') if '/' in self.symbol else self.symbol
                if not futures_symbol.endswith(':USDT'):
                    futures_symbol = f"{extract_base_asset(self.symbol)}:USDT"
                
                # Đóng vị thế short (async)
                await self.async_order_service.close_futures_short_order(
                    self.futures_exchange, 
                    futures_symbol, 
                    self.futures_amount, 
                    self.leverage
                )
                
                log_info(f"Đã đóng vị thế Delta-neutral Short trên {self.futures_exchange}")
                
                if self.notification_service:
                    self.notification_service.send_message(
                        f"Đã đóng vị thế Delta-neutral Short trên {self.futures_exchange}"
                    )
        except Exception as e:
            log_error(f"Lỗi khi đóng vị thế short: {str(e)}")
        
        # Gọi phương thức dừng của lớp cha
        return await super().stop()
    
    async def _emergency_stop(self) -> None:
        """
        Dừng khẩn cấp bot, bán tất cả crypto và đóng vị thế short.
        
        Returns:
            float: Tổng lợi nhuận (phần trăm)
        """
        # Bán tất cả crypto trên các sàn spot (async - đồng thời)
        try:
            await self.async_order_service.async_emergency_sell(self.symbol, self.exchanges)
        except Exception as e:
            log_error(f"Lỗi khi bán khẩn cấp crypto: {str(e)}")
        
        # Đóng vị thế short nếu đã mở (async)
        try:
            if self.futures_amount > 0:
                # Lấy cặp giao dịch futures
                futures_symbol = self.symbol.replace('/', ':') if '/' in self.symbol else self.symbol
                if not futures_symbol.endswith(':USDT'):
                    futures_symbol = f"{extract_base_asset(self.symbol)}:USDT"
                
                # Đóng vị thế short (async)
                await self.async_order_service.close_futures_short_order(
                    self.futures_exchange, 
                    futures_symbol, 
                    self.futures_amount, 
                    self.leverage
                )
        except Exception as e:
            log_error(f"Lỗi khi đóng khẩn cấp vị thế short: {str(e)}")
        
        return 0
    
    def _display_stats(self) -> None:
        """Hiển thị thống kê về phiên giao dịch."""
        elapsed_time = time.strftime('%H:%M:%S', time.gmtime(time.time() - self.start_time))
        
        log_info("\n" + "="*50)
        log_info(f"THỐNG KÊ PHIÊN GIAO DỊCH DELTA-NEUTRAL - {self.symbol}")
        log_info("="*50)
        log_info(f"Thời gian chạy: {elapsed_time}")
        log_info(f"Tổng lợi nhuận: {self.total_absolute_profit_pct:.4f}% ({(self.total_absolute_profit_pct/100)*self.howmuchusd:.4f} USDT)")
        log_info(f"Số cơ hội phát hiện: {self.stats['opportunities_found']}")
        log_info(f"Số giao dịch thành công: {self.stats['trades_executed']}")
        log_info(f"Số giao dịch thất bại: {self.stats['failed_trades']}")
        log_info(f"Tổng khối lượng giao dịch: {self.stats['total_volume']:.4f} USDT")
        log_info(f"Vị thế Short trên {self.futures_exchange}: {self.futures_amount} {extract_base_asset(self.symbol)}")
        
        if self.stats['trades_executed'] > 0:
            avg_profit = self.total_absolute_profit_pct / self.stats['trades_executed']
            log_info(f"Lợi nhuận trung bình mỗi giao dịch: {avg_profit:.4f}%")
        
        log_info("="*50 + "\n")
        
        # Gửi thông báo tổng kết qua Telegram
        if self.notification_service:
            stats_message = (
                f"📊 THỐNG KÊ PHIÊN GIAO DỊCH DELTA-NEUTRAL - {self.symbol}\n\n"
                f"⏱️ Thời gian chạy: {elapsed_time}\n"
                f"💰 Tổng lợi nhuận: {self.total_absolute_profit_pct:.4f}% ({(self.total_absolute_profit_pct/100)*self.howmuchusd:.4f} USDT)\n"
                f"🔍 Số cơ hội phát hiện: {self.stats['opportunities_found']}\n"
                f"✅ Số giao dịch thành công: {self.stats['trades_executed']}\n"
                f"❌ Số giao dịch thất bại: {self.stats['failed_trades']}\n"
                f"📈 Tổng khối lượng: {self.stats['total_volume']:.4f} USDT\n"
                f"📉 Vị thế Short: {self.futures_amount} {extract_base_asset(self.symbol)}"
            )
            self.notification_service.send_message(stats_message)