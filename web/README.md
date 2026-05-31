# Web Dashboard

Dashboard theo dõi giao dịch arbitrage, xây dựng bằng FastAPI + Jinja2.

## Cấu trúc

```
web/
├── app.py              # FastAPI app: routes + API endpoints
└── templates/
    └── dashboard.html  # Giao diện HTML (dark theme)
```

## Endpoints

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/` | Trang dashboard chính (HTML) |
| GET | `/docs` | Swagger API documentation |
| GET | `/api/sessions` | Danh sách phiên giao dịch |
| GET | `/api/sessions/{id}` | Chi tiết một phiên |
| GET | `/api/trades` | Danh sách giao dịch (filter by symbol, exchange, date) |
| GET | `/api/sessions/{id}/trades` | Giao dịch của một phiên |
| GET | `/api/stats/overview` | Thống kê tổng quan |
| GET | `/api/stats/profit/daily` | Lợi nhuận theo ngày |
| GET | `/api/stats/profit/hourly` | Lợi nhuận theo giờ |
| GET | `/api/stats/profit/by-symbol` | Lợi nhuận theo cặp giao dịch |
| GET | `/api/stats/profit/by-exchange-pair` | Lợi nhuận theo cặp sàn |
| GET | `/api/stats/slippage` | Thống kê slippage |
| GET | `/api/health` | Health check |

## Chạy

```bash
# Chạy trực tiếp
python -m uvicorn web.app:app --reload --port 8000

# Truy cập
# Dashboard: http://localhost:8000
# API docs:  http://localhost:8000/docs
```

## Lưu ý

- Starlette 1.0.0: dùng `TemplateResponse(request, "name.html", context={...})`
- Database: đọc từ `data/arbitrage.db` (SQLite)
