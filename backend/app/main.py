"""Điểm vào ứng dụng FastAPI.

Trên VPS: Uvicorn chạy `app.main:app`, CHỈ lắng nghe 127.0.0.1:8000; Nginx (cổng 80) phục vụ frontend tĩnh
và chuyển tiếp (reverse proxy) mọi request /api/ vào đây.
"""
import socket
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import __version__
from .config import settings
from .db import get_db
from .models import LOAI, TRANG_THAI
from .routers import auth, containers

app = FastAPI(
    title="Quản lý container – REST API",
    description="Bài cá nhân 2 – Lê Hữu Anh Tài – MSSV 2424802010066",
    version=__version__,
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.docs_enabled else None,
)

TEN_TRUONG = {
    "username": "Tên đăng nhập", "full_name": "Họ tên", "password": "Mật khẩu",
    "so_container": "Số container", "chu_hang": "Chủ hàng", "loai": "Loại", "trang_thai": "Trạng thái",
    "vi_tri_bai": "Vị trí bãi", "trong_luong_kg": "Trọng lượng", "ngay_nhap": "Ngày nhập", "ghi_chu": "Ghi chú",
}


def _thong_bao(e: dict) -> str:
    ctx, t = e.get("ctx") or {}, e.get("type", "")
    mau = {
        "missing": "bắt buộc nhập",
        "string_too_short": f"phải có ít nhất {ctx.get('min_length')} ký tự",
        "string_too_long": f"tối đa {ctx.get('max_length')} ký tự",
        "string_pattern_mismatch": "sai định dạng",
        "literal_error": "giá trị không hợp lệ",
        "int_parsing": "phải là số nguyên",
        "int_from_float": "phải là số nguyên",
        "greater_than_equal": f"phải ≥ {ctx.get('ge')}",
        "less_than_equal": f"phải ≤ {ctx.get('le')}",
        "date_from_datetime_parsing": "ngày không hợp lệ",
        "date_parsing": "ngày không hợp lệ",
        "string_type": "phải là chuỗi",
        "json_invalid": "dữ liệu JSON không hợp lệ",
    }
    return mau.get(t) or str(e.get("msg", "không hợp lệ")).removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def loi_du_lieu(_request: Request, exc: RequestValidationError):
    """Trả lỗi kiểm tra dữ liệu dạng dễ đọc: {"detail": "...", "errors": {"tên_trường": "thông báo"}}."""
    errors: dict[str, str] = {}
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path")]
        errors.setdefault(loc[0] if loc else "_", _thong_bao(e))
    detail = "; ".join(v if k == "_" else f"{TEN_TRUONG.get(k, k)}: {v}" for k, v in errors.items())
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


app.include_router(auth.router, prefix="/api/auth")
app.include_router(containers.router, prefix="/api/containers")


@app.get("/api/health", tags=["Hệ thống"])
def health(db: Session = Depends(get_db)):
    """Kiểm tra sống: dùng cho giám sát và để thấy tên máy chủ (MSSV) trên giao diện."""
    try:
        db.execute(text("SELECT 1"))
        ok = True
    except Exception:  # CSDL tắt -> báo degraded thay vì lỗi 500
        ok = False
    body = {"status": "ok" if ok else "degraded", "database": "ok" if ok else "error",
            "host": socket.gethostname(), "version": __version__}
    return JSONResponse(body, status_code=200 if ok else 503)


@app.get("/api/meta", tags=["Hệ thống"])
def meta():
    return {"loai": LOAI, "trang_thai": TRANG_THAI, "host": socket.gethostname()}


if settings.serve_frontend:  # chỉ khi chạy thử trên máy cá nhân (trên VPS Nginx làm việc này)
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend", html=True), name="web")
