"""Mô hình dữ liệu (3 bảng): users, sessions, containers."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

LOAI = {
    "20GP": "20' thường (GP)",
    "40GP": "40' thường (GP)",
    "40HC": "40' cao (HC)",
    "20RF": "20' lạnh (RF)",
    "40RF": "40' lạnh (RF)",
    "20OT": "20' mở nóc (OT)",
    "20TK": "20' bồn (Tank)",
}
TRANG_THAI = {
    "CHO_NHAP": "Chờ nhập bãi",
    "TRONG_BAI": "Đang trong bãi",
    "CHO_KIEM_HOA": "Chờ kiểm hóa",
    "DA_XUAT": "Đã xuất bãi",
}


def _in(col: str, values) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    # Chỉ lưu bản băm bcrypt ($2b$12$...), không bao giờ lưu mật khẩu gốc
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    """Phiên đăng nhập phía máy chủ: cookie chỉ chứa token ngẫu nhiên, CSDL lưu HMAC của token."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(lazy="joined")


class Container(Base):
    __tablename__ = "containers"
    __table_args__ = (
        CheckConstraint(_in("loai", LOAI), name="ck_containers_loai"),
        CheckConstraint(_in("trang_thai", TRANG_THAI), name="ck_containers_trang_thai"),
        CheckConstraint("trong_luong_kg IS NULL OR trong_luong_kg BETWEEN 0 AND 45000",
                        name="ck_containers_trong_luong"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    so_container: Mapped[str] = mapped_column(String(11), unique=True, index=True)  # chuẩn ISO 6346
    chu_hang: Mapped[str] = mapped_column(String(120), index=True)
    loai: Mapped[str] = mapped_column(String(4))
    trang_thai: Mapped[str] = mapped_column(String(20), index=True)
    vi_tri_bai: Mapped[str | None] = mapped_column(String(12))  # Khối-Bay-Hàng-Tầng, vd A-01-02-3
    trong_luong_kg: Mapped[int | None] = mapped_column(Integer)
    ngay_nhap: Mapped[date | None] = mapped_column(Date)
    ghi_chu: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())

    creator: Mapped[User | None] = relationship(foreign_keys=[created_by], lazy="joined")
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by], lazy="joined")

    @property
    def nguoi_tao(self) -> str | None:
        return self.creator.full_name if self.creator else None

    @property
    def nguoi_sua(self) -> str | None:
        return self.updater.full_name if self.updater else None
