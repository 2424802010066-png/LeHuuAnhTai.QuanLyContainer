"""Kết nối PostgreSQL qua SQLAlchemy 2 (driver psycopg 3).

Mọi truy vấn đi qua ORM/Core với tham số ràng buộc (bind parameters) nên dữ liệu người dùng
không bao giờ bị ghép thẳng vào câu SQL -> chống SQL injection.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # kiểm tra kết nối trước khi dùng (PostgreSQL khởi động lại vẫn không lỗi)
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
