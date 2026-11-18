"""Cấu hình pytest: chạy trên một CSDL PostgreSQL RIÊNG cho kiểm thử (mỗi test xóa và tạo lại bảng).

    export TEST_DATABASE_URL=postgresql+psycopg://user:pass@127.0.0.1:5432/qlcontainer_test
    cd backend && python -m pytest -q
"""
import os
import secrets

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.exit("Đặt biến TEST_DATABASE_URL trỏ tới CSDL kiểm thử (KHÔNG dùng CSDL thật vì test xóa bảng)", 2)
os.environ["DATABASE_URL"] = TEST_DB
os.environ["SECRET_KEY"] = secrets.token_hex(32)
os.environ["COOKIE_SECURE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import chu_so_kiem_tra  # noqa: E402
from app.security import login_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def csdl_sach():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    login_limiter._fails.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def so_cont(tien_to: str, so: str) -> str:
    """Sinh số container hợp lệ ISO 6346 (tự tính chữ số kiểm tra)."""
    goc = tien_to + so
    return goc + str(chu_so_kiem_tra(goc))


def dang_nhap(client, username="anhtai", password="MatKhau123", full_name="Lê Hữu Anh Tài"):
    r = client.post("/api/auth/register", json={"username": username, "full_name": full_name, "password": password})
    assert r.status_code in (201, 409), r.text
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}
