"""
Unit tests for utils/helpers.py
"""
import pytest
from utils.helpers import (
    extract_base_asset,
    calculate_average,
    format_message,
    show_time,
    get_precision_min,
)


class TestExtractBaseAsset:
    def test_slash_separator(self):
        assert extract_base_asset("BTC/USDT") == "BTC"

    def test_colon_separator(self):
        assert extract_base_asset("BTC:USDT") == "BTC"

    def test_no_separator(self):
        assert extract_base_asset("BTC") == "BTC"

    def test_eth_pair(self):
        assert extract_base_asset("ETH/USDT") == "ETH"


class TestCalculateAverage:
    def test_normal_list(self):
        assert calculate_average([10, 20, 30]) == 20.0

    def test_single_value(self):
        assert calculate_average([5]) == 5.0

    def test_empty_list(self):
        assert calculate_average([]) == 0

    def test_float_values(self):
        assert calculate_average([1.5, 2.5]) == 2.0


class TestFormatMessage:
    def test_removes_ansi_codes(self):
        msg = "hello [2m world [0m"
        result = format_message(msg)
        assert "[2m" not in result
        assert "[0m" not in result
        assert "hello" in result

    def test_plain_message_unchanged(self):
        msg = "simple message"
        assert format_message(msg) == "simple message"


class TestShowTime:
    def test_returns_string(self):
        result = show_time()
        assert isinstance(result, str)
        # Should be in HH:MM:SS format
        parts = result.split(":")
        assert len(parts) == 3


class TestGetPrecisionMin:
    def test_with_valid_orderbook(self):
        orderbook = {
            "bids": [[100.0, 1], [99.5, 2], [99.0, 3], [98.5, 4], [98.0, 5]],
            "asks": [[101.0, 1], [101.5, 2], [102.0, 3], [102.5, 4], [103.0, 5]],
        }
        result = get_precision_min(orderbook, "binance")
        assert result == 0.5

    def test_with_empty_orderbook(self):
        orderbook = {"bids": [[100.0, 1]], "asks": [[101.0, 1]]}
        result = get_precision_min(orderbook, "binance")
        # Only one entry per side, so no diffs -> returns default
        assert result == 0.01

    def test_default_for_unknown_exchange(self):
        orderbook = {"bids": [[100.0, 1]], "asks": [[101.0, 1]]}
        result = get_precision_min(orderbook, "unknown_exchange")
        assert result == 0.01
