"""
Tests cho RiskManager - quản lý rủi ro giao dịch.
"""
import time
import pytest
from services.risk_manager import RiskManager


class TestRiskManagerInit:
    """Test khởi tạo RiskManager."""

    def test_default_config(self):
        """Giá trị mặc định khi không truyền config."""
        rm = RiskManager()
        assert rm.enabled is True
        assert rm.max_drawdown_pct == 5.0
        assert rm.max_loss_per_trade_usd == 10.0
        assert rm.max_session_loss_pct == 3.0
        assert rm.max_consecutive_losses == 5
        assert rm.max_slippage_pct == 0.5

    def test_custom_config(self):
        """Config tùy chỉnh."""
        rm = RiskManager({
            'max_drawdown_pct': 10.0,
            'max_consecutive_losses': 3,
            'enabled': False,
        })
        assert rm.max_drawdown_pct == 10.0
        assert rm.max_consecutive_losses == 3
        assert rm.enabled is False

    def test_initial_state(self):
        """Trạng thái ban đầu."""
        rm = RiskManager()
        assert rm.is_stopped is False
        assert rm.stop_reason is None
        assert rm.consecutive_losses == 0
        assert rm.peak_profit_pct == 0.0
        assert rm.current_drawdown_pct == 0.0


class TestPreTradeCheck:
    """Test kiểm tra trước giao dịch."""

    def test_allowed_when_normal(self):
        """Cho phép giao dịch trong điều kiện bình thường."""
        rm = RiskManager()
        allowed, reason = rm.check_pre_trade(1.0)
        assert allowed is True
        assert reason is None

    def test_blocked_when_stopped(self):
        """Chặn khi bot đã bị dừng."""
        rm = RiskManager()
        rm._stopped = True
        rm._stop_reason = "Test stop"
        allowed, reason = rm.check_pre_trade(1.0)
        assert allowed is False
        assert "Test stop" in reason

    def test_blocked_when_disabled(self):
        """Luôn cho phép khi disabled."""
        rm = RiskManager({'enabled': False})
        rm._stopped = True  # Ngay cả khi stopped
        allowed, reason = rm.check_pre_trade(1.0)
        assert allowed is True

    def test_blocked_by_drawdown(self):
        """Chặn khi drawdown vượt giới hạn."""
        rm = RiskManager({'max_drawdown_pct': 2.0})
        rm._peak_profit_pct = 5.0
        rm._total_profit_pct = 2.5  # Drawdown = 5.0 - 2.5 = 2.5%
        allowed, reason = rm.check_pre_trade(1.0)
        assert allowed is False
        assert "Drawdown" in reason

    def test_blocked_by_consecutive_losses(self):
        """Chặn khi lỗ liên tiếp quá nhiều."""
        rm = RiskManager({'max_consecutive_losses': 3})
        rm._consecutive_losses = 3
        allowed, reason = rm.check_pre_trade(1.0)
        assert allowed is False
        assert "liên tiếp" in reason

    def test_blocked_by_cooldown(self):
        """Chặn khi đang trong cooldown."""
        rm = RiskManager()
        rm._cooldown_until = time.time() + 60
        allowed, reason = rm.check_pre_trade(1.0, current_time=time.time())
        assert allowed is False
        assert "cooldown" in reason

    def test_allowed_after_cooldown(self):
        """Cho phép sau khi hết cooldown."""
        rm = RiskManager()
        rm._cooldown_until = time.time() - 10  # Đã hết cooldown
        allowed, reason = rm.check_pre_trade(1.0, current_time=time.time())
        assert allowed is True


class TestPostTradeCheck:
    """Test kiểm tra sau giao dịch."""

    def test_continue_on_profit(self):
        """Tiếp tục khi có lợi nhuận."""
        rm = RiskManager()
        should_continue, reason = rm.check_post_trade(1.0, 0.1)
        assert should_continue is True
        assert reason is None

    def test_profit_updates_peak(self):
        """Cập nhật đỉnh lợi nhuận."""
        rm = RiskManager()
        rm.check_post_trade(1.0, 0.1, total_profit_pct=0.5)
        assert rm.peak_profit_pct == 0.5

    def test_consecutive_losses_tracked(self):
        """Theo dõi lỗ liên tiếp."""
        rm = RiskManager()
        rm.check_post_trade(-1.0, -0.1)
        assert rm.consecutive_losses == 1
        rm.check_post_trade(-0.5, -0.05)
        assert rm.consecutive_losses == 2
        rm.check_post_trade(1.0, 0.1)  # Lãi
        assert rm.consecutive_losses == 0

    def test_stop_on_session_loss(self):
        """Dừng khi lỗ phiên vượt giới hạn."""
        rm = RiskManager({'max_session_loss_pct': 2.0})
        should_continue, reason = rm.check_post_trade(
            -50.0, -2.5, total_profit_pct=-2.5
        )
        assert should_continue is False
        assert "Lỗ phiên" in reason

    def test_stop_on_drawdown(self):
        """Dừng khi drawdown vượt giới hạn."""
        rm = RiskManager({'max_drawdown_pct': 1.0})
        # Tạo đỉnh profit
        rm.check_post_trade(10.0, 2.0, total_profit_pct=2.0)
        assert rm.peak_profit_pct == 2.0
        # Giảm xuống -> drawdown
        should_continue, reason = rm.check_post_trade(
            -15.0, -1.5, total_profit_pct=0.5
        )
        # Drawdown = 2.0 - 0.5 = 1.5% > 1.0%
        assert should_continue is False
        assert "Drawdown" in reason

    def test_stop_on_consecutive_losses(self):
        """Dừng khi lỗ liên tiếp quá nhiều."""
        rm = RiskManager({'max_consecutive_losses': 3})
        rm.check_post_trade(-1.0, -0.1, total_profit_pct=-0.1)
        rm.check_post_trade(-1.0, -0.1, total_profit_pct=-0.2)
        should_continue, reason = rm.check_post_trade(
            -1.0, -0.1, total_profit_pct=-0.3
        )
        assert should_continue is False
        assert "liên tiếp" in reason

    def test_cooldown_on_large_loss(self):
        """Kích hoạt cooldown khi lỗ lớn."""
        rm = RiskManager({
            'max_loss_per_trade_usd': 5.0,
            'cooldown_after_loss_sec': 30,
            'max_session_loss_pct': 50.0  # Đặt cao để không trigger stop
        })
        now = time.time()
        rm.check_post_trade(-6.0, -0.3, total_profit_pct=-0.3, current_time=now)
        assert rm._cooldown_until > now

    def test_disabled_always_continue(self):
        """Luôn tiếp tục khi disabled."""
        rm = RiskManager({'enabled': False})
        should_continue, reason = rm.check_post_trade(
            -100.0, -50.0, total_profit_pct=-50.0
        )
        assert should_continue is True


class TestRiskManagerReset:
    """Test reset trạng thái."""

    def test_reset_clears_state(self):
        """Reset xóa toàn bộ state."""
        rm = RiskManager()
        rm._consecutive_losses = 5
        rm._peak_profit_pct = 10.0
        rm._total_profit_pct = -5.0
        rm._stopped = True
        rm._stop_reason = "test"
        rm._trade_count = 100

        rm.reset()
        assert rm.consecutive_losses == 0
        assert rm.peak_profit_pct == 0.0
        assert rm.is_stopped is False
        assert rm.stop_reason is None


class TestRiskManagerStatus:
    """Test lấy trạng thái."""

    def test_status_contains_all_fields(self):
        """Status chứa tất cả trường cần thiết."""
        rm = RiskManager()
        status = rm.get_status()
        assert 'enabled' in status
        assert 'stopped' in status
        assert 'stop_reason' in status
        assert 'trade_count' in status
        assert 'consecutive_losses' in status
        assert 'total_profit_pct' in status
        assert 'peak_profit_pct' in status
        assert 'current_drawdown_pct' in status
        assert 'limits' in status
        assert 'max_drawdown_pct' in status['limits']

    def test_status_reflects_state(self):
        """Status phản ánh state hiện tại."""
        rm = RiskManager()
        rm.check_post_trade(5.0, 1.0, total_profit_pct=1.0)
        rm.check_post_trade(-2.0, -0.5, total_profit_pct=0.5)

        status = rm.get_status()
        assert status['trade_count'] == 2
        assert status['peak_profit_pct'] == 1.0
        assert status['total_profit_pct'] == 0.5
        assert status['current_drawdown_pct'] == pytest.approx(0.5)


class TestDrawdownCalculation:
    """Test tính drawdown."""

    def test_no_drawdown_at_start(self):
        """Không có drawdown khi mới bắt đầu."""
        rm = RiskManager()
        assert rm.current_drawdown_pct == 0.0

    def test_drawdown_from_peak(self):
        """Drawdown tính từ đỉnh."""
        rm = RiskManager()
        rm._peak_profit_pct = 3.0
        rm._total_profit_pct = 1.0
        assert rm.current_drawdown_pct == 2.0

    def test_negative_profit_drawdown(self):
        """Drawdown khi lỗ (peak = 0)."""
        rm = RiskManager()
        rm._total_profit_pct = -1.5
        assert rm.current_drawdown_pct == 1.5

    def test_no_drawdown_at_peak(self):
        """Drawdown = 0 khi đang ở đỉnh."""
        rm = RiskManager()
        rm._peak_profit_pct = 5.0
        rm._total_profit_pct = 5.0
        assert rm.current_drawdown_pct == 0.0
