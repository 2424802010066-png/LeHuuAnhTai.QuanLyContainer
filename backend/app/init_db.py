"""Tạo bảng trong CSDL (chạy 1 lần khi cài đặt, trước khi khởi động dịch vụ).

    cd backend && python -m app.init_db

Tách riêng khỏi lúc khởi động để 2 tiến trình Uvicorn (--workers 2) không cùng lúc tạo bảng.
create_all chỉ tạo bảng chưa có, chạy lại nhiều lần không mất dữ liệu.
"""
from sqlalchemy import inspect

from . import models  # noqa: F401  (nạp model để Base biết các bảng)
from .db import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("Các bảng hiện có:", ", ".join(sorted(inspect(engine).get_table_names())))


if __name__ == "__main__":
    main()
