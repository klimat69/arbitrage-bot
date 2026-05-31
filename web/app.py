"""
FastAPI Web Dashboard cho BMLB Arbitrage Bot.
Cung cấp API REST và giao diện web để theo dõi giao dịch.
"""
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os
from typing import Optional

from services.database_service import DatabaseService


def create_app(db_service: Optional[DatabaseService] = None) -> FastAPI:
    """
    Tạo FastAPI app.

    Args:
        db_service (DatabaseService, optional): Dịch vụ database.
            Nếu không truyền, sẽ tạo mới.

    Returns:
        FastAPI: App instance
    """
    app = FastAPI(
        title="BMLB Arbitrage Bot Dashboard",
        description="Dashboard theo dõi giao dịch arbitrage crypto",
        version="1.0.0"
    )

    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    templates = Jinja2Templates(directory=templates_dir)

    db = db_service or DatabaseService()

    # ─── Dashboard HTML ───────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request):
        """Landing page for product positioning, demo, pricing, and risk notes."""
        return templates.TemplateResponse(request, "landing.html", context={})

    @app.get("/getting-started", response_class=HTMLResponse)
    async def getting_started(request: Request):
        """Beginner guide with safe paper trading and dry-run workflow."""
        return templates.TemplateResponse(request, "getting_started.html", context={})

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Trang dashboard chính."""
        stats = db.get_overall_stats()
        sessions = db.get_all_sessions(limit=10)
        return templates.TemplateResponse(request, "dashboard.html", context={
            "stats": stats,
            "sessions": sessions,
        })

    # ─── API: Sessions ────────────────────────────────────────────

    @app.get("/api/sessions")
    async def get_sessions(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        status: str = Query(None),
        symbol: str = Query(None)
    ):
        """Lấy danh sách phiên giao dịch."""
        sessions = db.get_all_sessions(limit, offset, status, symbol)
        return {"success": True, "data": sessions, "count": len(sessions)}

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: int):
        """Lấy chi tiết phiên giao dịch."""
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Phiên không tồn tại")
        return {"success": True, "data": session}

    # ─── API: Trades ──────────────────────────────────────────────

    @app.get("/api/trades")
    async def get_trades(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        symbol: str = Query(None),
        buy_exchange: str = Query(None),
        sell_exchange: str = Query(None),
        start_date: str = Query(None),
        end_date: str = Query(None)
    ):
        """Lấy danh sách giao dịch."""
        trades = db.get_all_trades(
            limit, offset, symbol, buy_exchange, sell_exchange,
            start_date, end_date
        )
        return {"success": True, "data": trades, "count": len(trades)}

    @app.get("/api/sessions/{session_id}/trades")
    async def get_session_trades(
        session_id: int,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0)
    ):
        """Lấy giao dịch của một phiên."""
        trades = db.get_trades_by_session(session_id, limit, offset)
        return {"success": True, "data": trades, "count": len(trades)}

    # ─── API: Statistics ──────────────────────────────────────────

    @app.get("/api/stats/overview")
    async def get_overview_stats():
        """Thống kê tổng quan."""
        stats = db.get_overall_stats()
        return {"success": True, "data": stats}

    @app.get("/api/stats/profit/daily")
    async def get_daily_profit(days: int = Query(30, ge=1, le=365)):
        """Lợi nhuận theo ngày."""
        data = db.get_daily_profit(days)
        return {"success": True, "data": data}

    @app.get("/api/stats/profit/hourly")
    async def get_hourly_profit(
        session_id: int = Query(None),
        days: int = Query(7, ge=1, le=90)
    ):
        """Lợi nhuận theo giờ."""
        data = db.get_hourly_profit(session_id, days)
        return {"success": True, "data": data}

    @app.get("/api/stats/profit/by-symbol")
    async def get_profit_by_symbol():
        """Lợi nhuận theo cặp giao dịch."""
        data = db.get_profit_by_symbol()
        return {"success": True, "data": data}

    @app.get("/api/stats/profit/by-exchange-pair")
    async def get_profit_by_exchange():
        """Lợi nhuận theo cặp sàn."""
        data = db.get_profit_by_exchange_pair()
        return {"success": True, "data": data}

    @app.get("/api/stats/exchange-performance")
    async def get_exchange_performance():
        """Hiệu suất từng sàn."""
        data = db.get_exchange_performance()
        return {"success": True, "data": data}

    @app.get("/api/stats/slippage")
    async def get_slippage_stats(session_id: int = Query(None)):
        """Thống kê slippage."""
        data = db.get_slippage_stats(session_id)
        return {"success": True, "data": data}

    @app.get("/api/stats/slippage/by-exchange")
    async def get_slippage_by_exchange(session_id: int = Query(None)):
        """Slippage theo sàn."""
        data = db.get_slippage_by_exchange(session_id)
        return {"success": True, "data": data}

    # ─── API: Errors ──────────────────────────────────────────────

    @app.get("/api/errors")
    async def get_errors(
        session_id: int = Query(None),
        error_type: str = Query(None),
        limit: int = Query(100, ge=1, le=500)
    ):
        """Lấy danh sách lỗi."""
        errors = db.get_errors(session_id, error_type, limit)
        return {"success": True, "data": errors, "count": len(errors)}

    # ─── API: Health ──────────────────────────────────────────────

    @app.get("/api/health")
    async def health_check():
        """Kiểm tra trạng thái server."""
        return {"status": "ok", "service": "arbitrage-bot-dashboard"}

    return app


# Default app instance
app = create_app()
