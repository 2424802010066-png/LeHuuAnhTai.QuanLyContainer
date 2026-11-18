"""Cấu hình ứng dụng: đọc TẤT CẢ từ biến môi trường.

Trên VPS, systemd nạp file /opt/qlcontainer/.env (EnvironmentFile=) vào môi trường của tiến trình.
Khi chạy thử trên máy cá nhân, python-dotenv đọc file .env ở thư mục gốc repo (nếu có).
Mã nguồn không chứa mật khẩu hay khóa bí mật nào - file .env bị .gitignore chặn, chỉ có .env.example.
"""
import os
from dataclasses import dataclass
from pathlib import Path

try:  # chỉ cần khi chạy local; trên VPS biến đã có sẵn từ systemd
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    session_hours: int
    cookie_secure: bool
    docs_enabled: bool
    serve_frontend: bool


def load_settings() -> Settings:
    db = os.getenv("DATABASE_URL", "").strip()
    key = os.getenv("SECRET_KEY", "").strip()
    if not db:
        raise RuntimeError("Thiếu DATABASE_URL (xem .env.example)")
    if len(key) < 32:
        raise RuntimeError("SECRET_KEY phải dài ít nhất 32 ký tự (xem .env.example)")
    return Settings(
        database_url=db,
        secret_key=key,
        session_hours=int(os.getenv("SESSION_HOURS", "8")),
        cookie_secure=_bool("COOKIE_SECURE", False),   # true khi chạy sau HTTPS
        docs_enabled=_bool("DOCS_ENABLED", False),     # /api/docs (Swagger) chỉ bật khi cần demo
        serve_frontend=_bool("SERVE_FRONTEND", False),  # chỉ dùng khi chạy local, trên VPS Nginx phục vụ frontend
    )


settings = load_settings()
