"""
Unit tests for configs.py
"""
import pytest
from configs import (
    SUPPORTED_EXCHANGES,
    EXCHANGE_FEES,
    BOT_MODES,
    FIRST_ORDERS_FILL_TIMEOUT,
    BALANCE_FILE,
    START_BALANCE_FILE,
    SYMBOL_FILE,
)


class TestConfigs:
    def test_supported_exchanges_not_empty(self):
        assert len(SUPPORTED_EXCHANGES) > 0

    def test_supported_exchanges_contains_known(self):
        assert "binance" in SUPPORTED_EXCHANGES
        assert "kucoin" in SUPPORTED_EXCHANGES

    def test_exchange_fees_has_all_exchanges(self):
        for exchange in SUPPORTED_EXCHANGES:
            assert exchange in EXCHANGE_FEES, f"Missing fee config for {exchange}"

    def test_exchange_fees_have_give_and_receive(self):
        for exchange, fees in EXCHANGE_FEES.items():
            assert "give" in fees, f"Missing 'give' fee for {exchange}"
            assert "receive" in fees, f"Missing 'receive' fee for {exchange}"
            assert 0 <= fees["give"] <= 1, f"Invalid 'give' fee for {exchange}"
            assert 0 <= fees["receive"] <= 1, f"Invalid 'receive' fee for {exchange}"

    def test_bot_modes(self):
        assert "fake-money" in BOT_MODES
        assert "classic" in BOT_MODES
        assert "delta-neutral" in BOT_MODES

    def test_first_orders_fill_timeout_is_seconds(self):
        # FIRST_ORDERS_FILL_TIMEOUT should be in seconds (300 = 5 phút — đủ cho arbitrage)
        assert FIRST_ORDERS_FILL_TIMEOUT == 300

    def test_file_paths(self):
        assert BALANCE_FILE == "balance.txt"
        assert START_BALANCE_FILE == "start_balance.txt"
        assert SYMBOL_FILE == "symbol.txt"
