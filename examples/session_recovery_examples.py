"""
Ví dụ: Sử dụng Session Recovery trong Bot

Tệp này minh họa cách khôi phục phiên bị dừng bằng SessionRecovery utility.
"""
import sys
import os

# Thêm thư mục gốc vào path để import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database_service import DatabaseService
from utils.session_recovery import SessionRecovery
from utils.logger import safe_print


# ============================================================================
# EXAMPLE 1: Kiểm tra phiên bị dừng (interrupt)
# ============================================================================

def example_check_interrupted():
    """Kiểm tra xem có phiên nào bị dừng không."""
    db = DatabaseService()
    recovery = SessionRecovery(db)
    
    interrupted = recovery.get_interrupted_sessions()
    
    if not interrupted:
        safe_print("No interrupted sessions found")
    else:
        safe_print(f"Found {len(interrupted)} interrupted sessions:")
        for session in interrupted:
            safe_print(f"  - Session #{session['id']}: {session['symbol']} ({session['mode']})")


# ============================================================================
# EXAMPLE 2: Lấy thông tin khôi phục phiên
# ============================================================================

def example_get_recovery_info(session_id):
    """Lấy thông tin chi tiết để khôi phục phiên."""
    db = DatabaseService()
    recovery = SessionRecovery(db)
    
    recovery_info = recovery.get_recovery_info(session_id)
    
    if recovery_info:
        safe_print(f"Recovery info for session #{session_id}:")
        safe_print(f"  Mode: {recovery_info['mode']}")
        safe_print(f"  Symbol: {recovery_info['symbol']}")
        safe_print(f"  Exchanges: {', '.join(recovery_info['exchanges'])}")
        safe_print(f"  USDT Amount: {recovery_info['usdt_amount']}")
        safe_print(f"  Trades Executed: {recovery_info['trades_executed']}")
        safe_print(f"  Cumulative Profit: {recovery_info['cumulative_profit_pct']:.4f}%")
        safe_print(f"  Cumulative Profit USD: {recovery_info['cumulative_profit_usd']:.4f}")
        safe_print(f"  Start Time: {recovery_info['start_time']}")
        
        # Lấy tham số để chạy bot
        params = SessionRecovery.extract_recovery_params(recovery_info)
        safe_print("\n  Bot parameters:")
        safe_print(
            f"    python main.py {params['mode']} {params['renew_time']} {params['usdt_amount']} "
            f"{' '.join(params['exchanges'])} {params['symbol']}"
        )


# ============================================================================
# EXAMPLE 3: Đánh dấu phiên là interrupted (khi có lỗi)
# ============================================================================

def example_mark_interrupted(session_id, error_message):
    """Đánh dấu phiên là bị interrupt do lỗi."""
    db = DatabaseService()
    recovery = SessionRecovery(db)
    
    recovery.mark_interrupted(session_id, error_message)
    safe_print(f"Session #{session_id} was marked as interrupted")


# ============================================================================
# EXAMPLE 4: Đánh dấu phiên là resumed (khi khôi phục thành công)
# ============================================================================

def example_mark_resumed(session_id):
    """Đánh dấu phiên đã được khôi phục."""
    db = DatabaseService()
    recovery = SessionRecovery(db)
    
    recovery.mark_resumed(session_id)
    safe_print(f"Session #{session_id} was marked as resumed")


# ============================================================================
# EXAMPLE 5: Luồng khôi phục phiên hoàn chỉnh
# ============================================================================

def example_full_recovery_flow():
    """Luồng khôi phục phiên hoàn chỉnh."""
    db = DatabaseService()
    recovery = SessionRecovery(db)
    
    safe_print("SESSION RECOVERY FLOW\n")
    
    # Step 1: Kiểm tra phiên bị dừng
    safe_print("Step 1: Check interrupted sessions...")
    interrupted = recovery.get_interrupted_sessions()
    
    if not interrupted:
        safe_print("  -> No interrupted sessions found")
        return
    
    safe_print(f"  -> Found {len(interrupted)} interrupted sessions")
    
    # Step 2: Hỏi người dùng (thường thấy trong main.py)
    safe_print("\nStep 2: Show the prompt menu...")
    safe_print("  (In main.py, this is the interactive recovery menu)")
    
    # Step 3: Lấy thông tin phiên được chọn
    session_id = interrupted[0]['id']
    safe_print(f"\nStep 3: Load recovery info for session #{session_id}...")
    recovery_info = recovery.get_recovery_info(session_id)
    
    if recovery_info:
        safe_print(f"  -> Mode: {recovery_info['mode']}")
        safe_print(f"  -> Symbol: {recovery_info['symbol']}")
        safe_print(f"  -> Previous trades: {recovery_info['trades_executed']}")
        safe_print(f"  -> Cumulative profit: {recovery_info['cumulative_profit_pct']:.4f}%")
    
    # Step 4: Trích xuất tham số
    safe_print("\nStep 4: Extract bot parameters...")
    params = SessionRecovery.extract_recovery_params(recovery_info)
    safe_print(f"  -> Mode: {params['mode']}")
    safe_print(f"  -> Symbol: {params['symbol']}")
    safe_print(f"  -> Exchanges: {params['exchanges']}")
    
    # Step 5: Khôi phục (trong main.py, bot sẽ chạy lại với tham số này)
    safe_print("\nStep 5: Restart the bot with the recovered configuration")
    safe_print("  -> The session continues from the interruption point")
    safe_print("  -> Previous profit is carried forward")
    
    # Step 6: Đánh dấu resumed khi khôi phục thành công
    safe_print("\nStep 6: After the bot finishes, the session is marked as 'resumed'")
    # recovery.mark_resumed(session_id)  # Không chạy trong ví dụ này


# ============================================================================
# EXAMPLE 6: Xem lịch sử tất cả phiên (bao gồm interrupted)
# ============================================================================

def example_view_all_sessions():
    """Xem tất cả phiên, bao gồm những phiên bị dừng."""
    db = DatabaseService()
    
    # Xem tất cả phiên
    all_sessions = db.get_all_sessions(limit=100)
    
    safe_print("ALL SESSIONS:")
    safe_print("=" * 80)
    
    for session in all_sessions:
        status_symbol = {
            'running': '[RUNNING]',
            'completed': '[DONE]',
            'interrupted': '[INTERRUPTED]',
            'resumed': '[RESUMED]',
            'error': '[ERROR]'
        }.get(session['status'], '[UNKNOWN]')
        
        safe_print(f"{status_symbol} Session #{session['id']}")
        safe_print(f"   Mode: {session['mode']} | Symbol: {session['symbol']}")
        safe_print(f"   Status: {session['status']} | Time: {session['renew_time_minutes']} min")
        safe_print(f"   Profit: {session['total_profit_pct']:.4f}% ({session['total_profit_usd']:.4f} USD)")
        safe_print(f"   Trades: {session['trades_executed']} | Opportunities: {session['opportunities_found']}")
        safe_print('')


# ============================================================================
# MAIN: Chạy ví dụ
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        safe_print("Usage:")
        safe_print("  python examples/session_recovery_examples.py check     # List interrupted sessions")
        safe_print("  python examples/session_recovery_examples.py info <id> # Show recovery info")
        safe_print("  python examples/session_recovery_examples.py flow      # Show recovery flow")
        safe_print("  python examples/session_recovery_examples.py all       # List all sessions")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        example_check_interrupted()
    elif command == "info" and len(sys.argv) > 2:
        try:
            session_id = int(sys.argv[2])
            example_get_recovery_info(session_id)
        except ValueError:
            safe_print("Error: Session ID must be a number")
    elif command == "flow":
        example_full_recovery_flow()
    elif command == "all":
        example_view_all_sessions()
    else:
        safe_print(f"Invalid command: {command}")
        safe_print("Valid commands: check, info, flow, all")
