"""Kiểm tra dữ liệu đầu vào ở BACKEND bằng Pydantic (frontend cũng kiểm tra, nhưng không bao giờ tin frontend)."""
import re
import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import LOAI, TRANG_THAI

LoaiT = Literal["20GP", "40GP", "40HC", "20RF", "40RF", "20OT", "20TK"]
TrangThaiT = Literal["CHO_NHAP", "TRONG_BAI", "CHO_KIEM_HOA", "DA_XUAT"]
assert set(LoaiT.__args__) == set(LOAI) and set(TrangThaiT.__args__) == set(TRANG_THAI)

# Bảng giá trị chữ cái theo ISO 6346 (bỏ qua 11, 22, 33 vì là bội số của 11)
_ISO_GIA_TRI = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                        [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34,
                         35, 36, 37, 38]))
_RE_CONT = re.compile(r"^[A-Z]{3}[UJZ][0-9]{7}$")
_RE_VI_TRI = re.compile(r"^[A-Z]-[0-9]{2}-[0-9]{2}-[0-9]$")


def chu_so_kiem_tra(so: str) -> int:
    """Chữ số kiểm tra (check digit) của số container ISO 6346: tổng giá trị * 2^vị trí, mod 11, mod 10."""
    tong = sum((_ISO_GIA_TRI[c] if c.isalpha() else int(c)) * (2 ** i) for i, c in enumerate(so[:10]))
    return tong % 11 % 10


def _sach(text: str) -> str:
    """Chuẩn hóa Unicode (NFC), bỏ ký tự điều khiển, gộp khoảng trắng."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


# ---------------------------------------------------------------- tài khoản
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_.]+$")
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username", mode="before")
    @classmethod
    def _username(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("full_name")
    @classmethod
    def _full_name(cls, v: str) -> str:
        v = _sach(v)
        if len(v) < 2:
            raise ValueError("Họ tên quá ngắn")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:  # bcrypt chỉ dùng 72 byte đầu -> chặn hẳn thay vì cắt ngầm
            raise ValueError("Mật khẩu tối đa 72 byte")
        if not (re.search(r"[A-Za-z]", v) and re.search(r"[0-9]", v)):
            raise ValueError("Mật khẩu phải có cả chữ và số")
        return v


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username", mode="before")
    @classmethod
    def _username(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


# ---------------------------------------------------------------- container
class ContainerIn(BaseModel):
    so_container: str = Field(min_length=11, max_length=11)
    chu_hang: str = Field(min_length=2, max_length=120)
    loai: LoaiT
    trang_thai: TrangThaiT
    vi_tri_bai: str | None = Field(default=None, max_length=12)
    trong_luong_kg: int | None = Field(default=None, ge=0, le=45000)
    ngay_nhap: date | None = None
    ghi_chu: str | None = Field(default=None, max_length=500)

    @field_validator("so_container", mode="before")
    @classmethod
    def _so_upper(cls, v):
        return re.sub(r"\s+", "", v).upper() if isinstance(v, str) else v

    @field_validator("so_container")
    @classmethod
    def _so_iso6346(cls, v: str) -> str:
        if not _RE_CONT.match(v):
            raise ValueError("Số container phải theo ISO 6346: 3 chữ chủ sở hữu + U/J/Z + 7 chữ số, vd CSQU3054383")
        if chu_so_kiem_tra(v) != int(v[10]):
            raise ValueError(f"Sai chữ số kiểm tra ISO 6346 (chữ số cuối đúng phải là {chu_so_kiem_tra(v)})")
        return v

    @field_validator("chu_hang")
    @classmethod
    def _chu_hang(cls, v: str) -> str:
        v = _sach(v)
        if len(v) < 2:
            raise ValueError("Tên chủ hàng quá ngắn")
        return v

    @field_validator("vi_tri_bai", mode="before")
    @classmethod
    def _vi_tri(cls, v):
        if isinstance(v, str):
            v = v.strip().upper()
            if not v:
                return None
            if not _RE_VI_TRI.match(v):
                raise ValueError("Vị trí bãi dạng Khối-Bay-Hàng-Tầng, vd A-01-02-3")
        return v

    @field_validator("ghi_chu", mode="before")
    @classmethod
    def _ghi_chu(cls, v):
        if isinstance(v, str):
            v = _sach(v)
            return v or None
        return v

    @field_validator("ngay_nhap")
    @classmethod
    def _ngay(cls, v: date | None) -> date | None:
        if v and v > date.today():
            raise ValueError("Ngày nhập bãi không được ở tương lai")
        return v

    @model_validator(mode="after")
    def _rang_buoc(self):
        if self.trang_thai == "TRONG_BAI" and not self.vi_tri_bai:
            raise ValueError("Container đang trong bãi phải có vị trí bãi")
        return self


class ContainerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    so_container: str
    chu_hang: str
    loai: str
    trang_thai: str
    vi_tri_bai: str | None
    trong_luong_kg: int | None
    ngay_nhap: date | None
    ghi_chu: str | None
    nguoi_tao: str | None
    nguoi_sua: str | None
    created_at: datetime
    updated_at: datetime


class ContainerPage(BaseModel):
    items: list[ContainerOut]
    total: int
    page: int
    page_size: int
    pages: int


class ThongKe(BaseModel):
    tong: int
    theo_trang_thai: dict[str, int]
