"""Tests for LargeOrderDetector anti-spoofing logic."""
import asyncio
import time

import pytest

from strategies.large_order_detector import LargeOrderDetector


@pytest.fixture
def signals():
    return []


@pytest.fixture
def detector(signals):
    async def callback(signal):
        signals.append(signal)

    return LargeOrderDetector(
        symbol='BTC/USDT',
        threshold_btc=1.0,
        order_ttl_seconds=0.2,
        on_valid_signal=callback,
    )


class TestLargeOrderDetector:
    def test_ignores_small_orders(self, detector, signals):
        orderbook = {'bids': [[50000.0, 0.01]], 'asks': []}
        emitted = asyncio.run(detector.process_orderbook(orderbook))
        assert emitted == []
        assert signals == []

    def test_emits_after_ttl(self, detector, signals):
        orderbook = {'bids': [[50000.0, 2.0]], 'asks': []}
        asyncio.run(detector.process_orderbook(orderbook))
        time.sleep(0.25)
        orderbook2 = {'bids': [[50000.0, 2.0]], 'asks': []}
        emitted = asyncio.run(detector.process_orderbook(orderbook2))
        assert len(emitted) == 1
        assert emitted[0]['side'] == 'bid'
        assert emitted[0]['btc_volume'] >= 1.0

    def test_spoofing_filtered(self, detector, signals):
        orderbook = {'bids': [[50000.0, 2.0]], 'asks': []}
        asyncio.run(detector.process_orderbook(orderbook))
        removed = {'bids': [], 'asks': []}
        asyncio.run(detector.process_orderbook(removed))
        assert signals == []
