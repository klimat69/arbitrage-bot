"""
Tests cho FastAPI Web Dashboard.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from services.database_service import DatabaseService
from web.app import create_app


@pytest.fixture
def db():
    """Database tạm cho tests."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db_service = DatabaseService(db_path=path)
    yield db_service
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(db):
    """FastAPI test client."""
    app = create_app(db_service=db)
    return TestClient(app)


@pytest.fixture
def seeded_db(db):
    """Database với dữ liệu mẫu."""
    s_id = db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 60)
    db.record_trade(
        s_id, 1, 'BTC/USDT', 'binance', 'kucoin',
        50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
        0.1, 1.0,
        actual_buy_price=50010.0, actual_sell_price=50090.0,
        buy_slippage_pct=0.02, sell_slippage_pct=-0.02,
        total_slippage_usd=0.2
    )
    db.end_session(s_id, 0.1, 1.0, 0.05, 1, 1, 0, 500.0, 1001.0)
    return db


@pytest.fixture
def seeded_client(seeded_db):
    """Client với dữ liệu mẫu."""
    app = create_app(db_service=seeded_db)
    return TestClient(app)


class TestHealthCheck:
    """Test health endpoint."""

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestDashboard:
    """Test trang dashboard."""

    def test_dashboard_empty(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Dashboard" in r.text

    def test_dashboard_with_data(self, seeded_client):
        r = seeded_client.get("/")
        assert r.status_code == 200
        assert "BTC/USDT" in r.text


class TestSessionsAPI:
    """Test sessions API."""

    def test_get_sessions_empty(self, client):
        r = client.get("/api/sessions")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["count"] == 0

    def test_get_sessions_with_data(self, seeded_client):
        r = seeded_client.get("/api/sessions")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1

    def test_get_session_by_id(self, seeded_client):
        r = seeded_client.get("/api/sessions/1")
        assert r.status_code == 200
        assert r.json()["data"]["symbol"] == "BTC/USDT"

    def test_get_session_not_found(self, client):
        r = client.get("/api/sessions/999")
        assert r.status_code == 404

    def test_sessions_filter_status(self, seeded_client):
        r = seeded_client.get("/api/sessions?status=completed")
        assert r.status_code == 200
        for s in r.json()["data"]:
            assert s["status"] == "completed"


class TestTradesAPI:
    """Test trades API."""

    def test_get_trades_empty(self, client):
        r = client.get("/api/trades")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_get_trades_with_data(self, seeded_client):
        r = seeded_client.get("/api/trades")
        data = r.json()
        assert data["count"] >= 1
        trade = data["data"][0]
        assert "buy_exchange" in trade
        assert "sell_exchange" in trade

    def test_get_session_trades(self, seeded_client):
        r = seeded_client.get("/api/sessions/1/trades")
        assert r.status_code == 200
        assert r.json()["count"] >= 1


class TestStatsAPI:
    """Test statistics API."""

    def test_overview_stats(self, seeded_client):
        r = seeded_client.get("/api/stats/overview")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "total_sessions" in data
        assert "total_trades" in data

    def test_daily_profit(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/daily")
        assert r.status_code == 200

    def test_hourly_profit(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/hourly")
        assert r.status_code == 200

    def test_profit_by_symbol(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/by-symbol")
        assert r.status_code == 200

    def test_profit_by_exchange(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/by-exchange-pair")
        assert r.status_code == 200

    def test_exchange_performance(self, seeded_client):
        r = seeded_client.get("/api/stats/exchange-performance")
        assert r.status_code == 200

    def test_slippage_stats(self, seeded_client):
        r = seeded_client.get("/api/stats/slippage")
        assert r.status_code == 200
        assert "total_slippage_usd" in r.json()["data"]

    def test_slippage_by_exchange(self, seeded_client):
        r = seeded_client.get("/api/stats/slippage/by-exchange")
        assert r.status_code == 200


class TestErrorsAPI:
    """Test errors API."""

    def test_get_errors_empty(self, client):
        r = client.get("/api/errors")
        assert r.status_code == 200
        assert r.json()["count"] == 0
