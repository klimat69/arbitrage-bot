"""Tests for advanced risk manager can_open / record_trade."""
import pytest

from risk.risk_manager import RiskManager


class TestAdvancedRiskManager:
    def test_can_open_blocks_oversized_position(self):
        rm = RiskManager({'max_position_usdt': 100})
        allowed, reason = rm.can_open('BTC/USDT', 150)
        assert allowed is False
        assert 'exceeds limit' in reason

    def test_record_trade_trips_circuit_breaker(self):
        rm = RiskManager({'circuit_breaker_losses': 2, 'max_consecutive_losses': 10})
        rm.record_trade(-5, 'BTC/USDT')
        rm.record_trade(-5, 'BTC/USDT')
        allowed, reason = rm.can_open('BTC/USDT', 10)
        assert allowed is False
        assert 'liên tiếp' in reason.lower() or 'circuit' in reason.lower()

    def test_daily_loss_limit(self):
        rm = RiskManager({'max_daily_loss_usdt': 50})
        rm.record_trade(-60)
        allowed, _ = rm.can_open('BTC/USDT', 10)
        assert allowed is False
