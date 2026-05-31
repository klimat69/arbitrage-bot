"""
Công cụ khôi phục phiên giao dịch.
Xử lý phát hiện, hỏi người dùng, và khôi phục phiên bị dừng.
"""
import time
from typing import Optional, Any
from datetime import datetime, timezone
from colorama import Fore, Style

from utils.logger import log_info, log_warning, log_error, safe_print
from services.database_service import DatabaseService


class SessionRecovery:
    """
    Lớp quản lý khôi phục phiên giao dịch bị dừng.
    """
    
    def __init__(self, db_service: DatabaseService) -> None:
        """
        Khởi tạo công cụ khôi phục.
        
        Args:
            db_service (DatabaseService): Dịch vụ database
        """
        self.db = db_service
    
    def get_interrupted_sessions(self) -> list[dict[str, Any]]:
        """
        Lấy danh sách phiên bị dừng.
        
        Returns:
            list[dict]: Danh sách phiên
        """
        return self.db.get_interrupted_sessions()
    
    def show_interrupted_sessions(self) -> Optional[int]:
        """
        Hiển thị danh sách phiên bị dừng và hỏi người dùng có muốn khôi phục không.
        
        Returns:
            int: ID phiên được chọn, hoặc None nếu người dùng không muốn khôi phục
        """
        interrupted_sessions = self.get_interrupted_sessions()
        
        if not interrupted_sessions:
            log_info("Không có phiên nào bị dừng")
            return None
        
        safe_print("\n" + "="*80)
        safe_print(f"{Fore.YELLOW}Phát hiện {len(interrupted_sessions)} phiên bị dừng:{Style.RESET_ALL}")
        safe_print("="*80)
        
        for idx, session in enumerate(interrupted_sessions, 1):
            session_id = session['id']
            mode = session['mode']
            symbol = session['symbol']
            exchanges = session['exchanges']
            start_time = session['start_time']
            usdt_amount = session['usdt_amount']
            trades_executed = session['trades_executed']
            profit_pct = session['total_profit_pct'] if session['total_profit_pct'] else 0
            profit_usd = session['total_profit_usd'] if session['total_profit_usd'] else 0
            
            safe_print(f"\n[{idx}] Phiên #{session_id}:")
            safe_print(f"    Chế độ: {mode}")
            safe_print(f"    Cặp tiền: {symbol}")
            safe_print(f"    Sàn: {exchanges}")
            safe_print(f"    Vốn: {usdt_amount} USDT")
            safe_print(f"    Thời gian bắt đầu: {start_time}")
            safe_print(f"    Giao dịch đã thực hiện: {trades_executed}")
            safe_print(f"    Lợi nhuận: {profit_pct:.4f}% ({profit_usd:.4f} USDT)")
        
        safe_print("\n" + "="*80)
        safe_print(f"{Fore.CYAN}Tùy chọn:{Style.RESET_ALL}")
        safe_print(f"  [1-{len(interrupted_sessions)}] - Khôi phục phiên")
        safe_print(f"  [0 hoặc Enter] - Chạy phiên mới")
        
        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Lựa chọn của bạn:{Style.RESET_ALL} ").strip()
                
                if choice == '' or choice == '0':
                    log_info("Bắt đầu phiên mới (không khôi phục)")
                    return None
                
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(interrupted_sessions):
                    selected_session = interrupted_sessions[choice_idx]
                    log_info(f"Khôi phục phiên #{selected_session['id']}")
                    return selected_session['id']
                else:
                    safe_print(f"{Fore.RED}Lựa chọn không hợp lệ. Vui lòng thử lại.{Style.RESET_ALL}")
                    
            except ValueError:
                safe_print(f"{Fore.RED}Vui lòng nhập số hợp lệ.{Style.RESET_ALL}")
            except KeyboardInterrupt:
                safe_print('')
                log_info("Hủy khôi phục. Chạy phiên mới.")
                return None
    
    def get_recovery_info(self, session_id: int) -> Optional[dict[str, Any]]:
        """
        Lấy thông tin để khôi phục phiên.
        
        Args:
            session_id (int): ID phiên cần khôi phục
        
        Returns:
            dict: Thông tin khôi phục
        """
        recovery_info = self.db.get_session_recovery_info(session_id)
        
        if recovery_info:
            safe_print(f"\n{Fore.CYAN}Thông tin khôi phục:{Style.RESET_ALL}")
            safe_print(f"  Phiên ID: {recovery_info['session_id']}")
            safe_print(f"  Chế độ: {recovery_info['mode']}")
            safe_print(f"  Cặp tiền: {recovery_info['symbol']}")
            safe_print(f"  Sàn: {', '.join(recovery_info['exchanges'])}")
            safe_print(f"  Vốn: {recovery_info['usdt_amount']} USDT")
            safe_print(f"  Giao dịch đã thực hiện: {recovery_info['trades_executed']}")
            safe_print(f"  Lợi nhuận tích lũy: {recovery_info['cumulative_profit_pct']:.4f}%")
            safe_print(f"  Thời gian bắt đầu: {recovery_info['start_time']}")
        
        return recovery_info
    
    def mark_interrupted(self, session_id: int, error_message: str = None) -> None:
        """
        Đánh dấu phiên là bị interrupt.
        
        Args:
            session_id (int): ID phiên
            error_message (str, optional): Thông báo lỗi
        """
        self.db.mark_session_interrupted(session_id, error_message)
    
    def mark_resumed(self, session_id: int) -> None:
        """
        Đánh dấu phiên đã được khôi phục.
        
        Args:
            session_id (int): ID phiên
        """
        self.db.mark_session_resumed(session_id)
    
    @staticmethod
    def extract_recovery_params(recovery_info: dict[str, Any]) -> dict[str, Any]:
        """
        Trích xuất các tham số để chạy bot từ thông tin khôi phục.
        
        Args:
            recovery_info (dict): Thông tin khôi phục
        
        Returns:
            dict: Tham số cho bot
        """
        return {
            'mode': recovery_info['mode'],
            'symbol': recovery_info['symbol'],
            'usdt_amount': recovery_info['usdt_amount'],
            'renew_time': recovery_info['renew_time_minutes'],
            'exchanges': recovery_info['exchanges'],
            'recovered_session_id': recovery_info['session_id'],
            'last_trade_number': recovery_info['last_trade_number'],
            'cumulative_profit_pct': recovery_info['cumulative_profit_pct'],
            'cumulative_profit_usd': recovery_info['cumulative_profit_usd']
        }
