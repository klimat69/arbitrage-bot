"""Tests for Binance futures public WebSocket parser."""
from strategies.binance_futures_ws import parse_depth_message


class TestParseDepthMessage:
    def test_parses_b_a_fields(self):
        raw = {
            'b': [['50000.0', '1.5'], ['49999.0', '0']],
            'a': [['50001.0', '2.0']],
        }
        book = parse_depth_message(raw)
        assert book is not None
        assert book['bids'][0] == [50000.0, 1.5]
        assert book['asks'][0] == [50001.0, 2.0]

    def test_empty_returns_none(self):
        assert parse_depth_message({}) is None
