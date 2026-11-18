"""Kiểm thử API end-to-end trên PostgreSQL thật."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

from .conftest import dang_nhap, so_cont

CONT = {
    "chu_hang": "Công ty TNHH Thủy sản Minh Phú",
    "loai": "40RF",
    "trang_thai": "TRONG_BAI",
    "vi_tri_bai": "a-01-02-3",
    "trong_luong_kg": 28500,
    "ngay_nhap": "2026-11-10",
    "ghi_chu": "Hàng đông lạnh -18°C",
}


# ------------------------------------------------------------------ tài khoản
def test_dang_ky_luu_mat_khau_dang_bam(client):
    r = client.post("/api/auth/register", json={"username": " AnhTai ", "full_name": "Lê Hữu Anh Tài",
                                                "password": "MatKhau123"})
    assert r.status_code == 201 and r.json()["username"] == "anhtai"
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.username == "anhtai"))
        assert u.password_hash.startswith("$2b$12$") and "MatKhau123" not in u.password_hash
    r = client.post("/api/auth/register", json={"username": "anhtai", "full_name": "Ai đó", "password": "Khac12345"})
    assert r.status_code == 409


def test_dang_ky_kiem_tra_dau_vao(client):
    r = client.post("/api/auth/register", json={"username": "a b", "full_name": "X", "password": "123"})
    assert r.status_code == 422
    assert {"username", "full_name", "password"} <= set(r.json()["errors"])
    r = client.post("/api/auth/register", json={"username": "abc", "full_name": "Tên", "password": "chiCoChu"})
    assert r.status_code == 422 and "chữ và số" in r.json()["errors"]["password"]


def test_dang_nhap_cookie_an_toan_va_me(client):
    dang_nhap(client)
    r = client.post("/api/auth/login", json={"username": "anhtai", "password": "MatKhau123"})
    sc = r.headers["set-cookie"].lower()
    assert "qlc_sid=" in sc and "httponly" in sc and "samesite=strict" in sc
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"]["full_name"] == "Lê Hữu Anh Tài"


def test_sai_mat_khau_bi_gioi_han(client):
    dang_nhap(client)
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "anhtai", "password": "Sai123456"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "anhtai", "password": "MatKhau123"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_dang_xuat_vo_hieu_phien_phia_may_chu(client):
    h = dang_nhap(client)
    cu = client.cookies.get("qlc_sid")
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    client.cookies.set("qlc_sid", cu)  # gửi lại cookie cũ (giả sử bị lộ)
    assert client.get("/api/auth/me").status_code == 401


# ------------------------------------------------------------------ container
def test_chua_dang_nhap_bi_chan(client):
    assert client.get("/api/containers").status_code == 401


def test_thieu_csrf_bi_chan(client):
    h = dang_nhap(client)
    body = {**CONT, "so_container": "CSQU3054383"}
    assert client.post("/api/containers", json=body).status_code == 403
    assert client.post("/api/containers", json=body, headers={"X-CSRF-Token": "sai"}).status_code == 403
    assert client.post("/api/containers", json=body, headers=h).status_code == 201


def test_crud_container(client):
    h = dang_nhap(client)
    r = client.post("/api/containers", json={**CONT, "so_container": "csqu 305438 3"}, headers=h)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["so_container"] == "CSQU3054383" and c["vi_tri_bai"] == "A-01-02-3"
    assert c["nguoi_tao"] == "Lê Hữu Anh Tài"
    # trùng số container
    assert client.post("/api/containers", json={**CONT, "so_container": "CSQU3054383"}, headers=h).status_code == 409
    # xem
    assert client.get(f"/api/containers/{c['id']}").json()["chu_hang"] == CONT["chu_hang"]
    # sửa
    r = client.put(f"/api/containers/{c['id']}", headers=h,
                   json={**CONT, "so_container": "CSQU3054383", "trang_thai": "DA_XUAT", "vi_tri_bai": ""})
    assert r.status_code == 200 and r.json()["trang_thai"] == "DA_XUAT" and r.json()["vi_tri_bai"] is None
    # xóa
    assert client.delete(f"/api/containers/{c['id']}", headers=h).status_code == 204
    assert client.get(f"/api/containers/{c['id']}").status_code == 404


def test_kiem_tra_iso6346_va_rang_buoc(client):
    h = dang_nhap(client)
    r = client.post("/api/containers", json={**CONT, "so_container": "CSQU3054384"}, headers=h)
    assert r.status_code == 422 and "chữ số kiểm tra" in r.json()["errors"]["so_container"]
    r = client.post("/api/containers", json={**CONT, "so_container": "CSQ13054383"}, headers=h)
    assert r.status_code == 422
    r = client.post("/api/containers", json={**CONT, "so_container": "CSQU3054383", "vi_tri_bai": None}, headers=h)
    assert r.status_code == 422 and "vị trí" in r.json()["detail"]
    r = client.post("/api/containers", json={**CONT, "so_container": "CSQU3054383", "trong_luong_kg": 99999},
                    headers=h)
    assert r.status_code == 422 and "trong_luong_kg" in r.json()["errors"]
    r = client.post("/api/containers", json={**CONT, "so_container": "CSQU3054383", "loai": "99XX"}, headers=h)
    assert r.status_code == 422 and "loai" in r.json()["errors"]


def test_tim_kiem_loc_phan_trang(client):
    h = dang_nhap(client)
    for i in range(12):
        body = {**CONT, "so_container": so_cont("MSKU", f"{100000 + i:06d}"),
                "chu_hang": "Vinamilk" if i % 3 == 0 else "Hòa Phát", "trang_thai": "TRONG_BAI" if i % 2 else "CHO_NHAP"}
        assert client.post("/api/containers", json=body, headers=h).status_code == 201
    p = client.get("/api/containers", params={"page_size": 5, "page": 3}).json()
    assert p["total"] == 12 and p["pages"] == 3 and len(p["items"]) == 2
    assert client.get("/api/containers", params={"q": "vinamilk"}).json()["total"] == 4
    assert client.get("/api/containers", params={"trang_thai": "CHO_NHAP"}).json()["total"] == 6
    # ký tự đại diện của LIKE được thoát: '%' không khớp mọi dòng
    assert client.get("/api/containers", params={"q": "%"}).json()["total"] == 0
    tk = client.get("/api/containers/thong-ke").json()
    assert tk["tong"] == 12 and tk["theo_trang_thai"]["TRONG_BAI"] == 6


def test_chen_sql_khong_tac_dung(client):
    dang_nhap(client)
    r = client.get("/api/containers", params={"q": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    r = client.post("/api/auth/login", json={"username": "anhtai' --", "password": "x"})
    assert r.status_code == 401


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"
