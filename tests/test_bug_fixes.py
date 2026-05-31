"""
Unit tests for main.py - specifically testing bug fixes.
"""
import pytest
from unittest.mock import patch


class TestGetUserInput:
    """Test that user input correctly maps to distinct exchange keys."""

    @patch("builtins.input")
    @patch("builtins.print")
    def test_three_exchanges_are_distinct(self, mock_print, mock_input):
        """Regression test: ensure 3 exchanges get stored with distinct keys."""
        # Simulate user input: mode, renew, balance, exchange1, exchange2, exchange3, crypto
        mock_input.side_effect = [
            "fake-money",
            "5",
            "100",
            "binance",
            "kucoin",
            "okx",
            "BTC/USDT",
        ]

        from main import get_user_input

        inputs = get_user_input()

        # The critical fix: each exchange should have its own key
        assert inputs["exchange_1"] == "binance"
        assert inputs["exchange_2"] == "kucoin"
        assert inputs["exchange_3"] == "okx"

        # Other inputs should also be correct
        assert inputs["mode"] == "fake-money"
        assert inputs["renew"] == "5"
        assert inputs["balance"] == "100"
        assert inputs["crypto"] == "BTC/USDT"


class TestOrderServiceTimeout:
    """Test that the timeout calculation is correct."""

    def test_timeout_is_in_seconds(self):
        """Regression test: FIRST_ORDERS_FILL_TIMEOUT là giây, không phải phút."""
        from configs import FIRST_ORDERS_FILL_TIMEOUT

        timeout_seconds = FIRST_ORDERS_FILL_TIMEOUT
        assert timeout_seconds == 300
        # Phải đủ ngắn cho arbitrage (tối đa 10 phút = 600 giây)
        assert timeout_seconds < 600


class TestBaseBotZeroDivision:
    """Test that process_orderbook handles zero balance gracefully."""

    def test_process_orderbook_zero_balance(self):
        """Regression test: process_orderbook should not crash with zero total balance."""
        import asyncio
        from unittest.mock import MagicMock
        from bots.base_bot import BaseBot

        bot = BaseBot(
            exchange_service=MagicMock(),
            balance_service=MagicMock(),
            order_service=MagicMock(),
            notification_service=MagicMock(),
        )
        bot.symbol = "BTC/USDT"
        bot.exchanges = ["binance", "kucoin"]
        bot.usd = {"binance": 0, "kucoin": 0}  # Zero balance
        bot.crypto = {"binance": 0.01, "kucoin": 0.01}
        bot.crypto_per_transaction = 0.01
        bot.bid_prices = {"binance": 50000}
        bot.ask_prices = {"binance": 50100}

        orderbook = {
            "bids": [[50000, 1]],
            "asks": [[50100, 1]],
        }

        # Should not raise ZeroDivisionError
        result = asyncio.run(bot.process_orderbook("kucoin", orderbook))
        assert result is False
