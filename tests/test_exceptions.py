"""
Unit tests for utils/exceptions.py
"""
import pytest
from utils.exceptions import (
    ArbitrageError,
    ExchangeError,
    InsufficientBalanceError,
    OrderError,
    OrderFillTimeoutError,
    ConfigError,
    NotificationError,
    DeltaNeutralError,
    FuturesError,
)


class TestExchangeError:
    def test_message_format(self):
        err = ExchangeError("binance", "connection failed")
        assert "binance" in str(err)
        assert "connection failed" in str(err)

    def test_attributes(self):
        err = ExchangeError("kucoin", "timeout")
        assert err.exchange == "kucoin"
        assert err.message == "timeout"

    def test_is_arbitrage_error(self):
        err = ExchangeError("binance", "test")
        assert isinstance(err, ArbitrageError)


class TestInsufficientBalanceError:
    def test_message_format(self):
        err = InsufficientBalanceError("binance", "USDT", 100.0, 50.0)
        msg = str(err)
        assert "binance" in msg
        assert "USDT" in msg

    def test_attributes(self):
        err = InsufficientBalanceError("okx", "BTC", 1.0, 0.5)
        assert err.exchange == "okx"
        assert err.asset == "BTC"
        assert err.required == 1.0
        assert err.available == 0.5


class TestOrderError:
    def test_message_format(self):
        err = OrderError("binance", "limit buy", "insufficient funds")
        msg = str(err)
        assert "binance" in msg
        assert "limit buy" in msg
        assert "insufficient funds" in msg


class TestOrderFillTimeoutError:
    def test_message_format(self):
        err = OrderFillTimeoutError("binance", "order123", 120)
        msg = str(err)
        assert "order123" in msg
        assert "120" in msg


class TestConfigError:
    def test_message_format(self):
        err = ConfigError("missing API key")
        assert "missing API key" in str(err)


class TestNotificationError:
    def test_message_format(self):
        err = NotificationError("Telegram", "rate limit")
        msg = str(err)
        assert "Telegram" in msg
        assert "rate limit" in msg


class TestFuturesError:
    def test_message_format(self):
        err = FuturesError("kucoinfutures", "leverage error")
        msg = str(err)
        assert "kucoinfutures" in msg
        assert "leverage error" in msg

    def test_is_arbitrage_error(self):
        err = FuturesError("kucoinfutures", "test")
        assert isinstance(err, ArbitrageError)


class TestDeltaNeutralError:
    def test_message_format(self):
        err = DeltaNeutralError("hedge failed")
        assert "hedge failed" in str(err)
