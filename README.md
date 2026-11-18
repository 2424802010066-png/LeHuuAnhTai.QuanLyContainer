# Quản lý container – ứng dụng web trên VPS

Bài cá nhân 2 môn **Thực hành điện toán đám mây** – Lê Hữu Anh Tài – MSSV **2424802010066** – TDMU.

Ứng dụng quản lý container trong bãi cảng: đăng ký, đăng nhập, thêm – xem – sửa – xóa container
(số container chuẩn ISO 6346, chủ hàng, loại, trạng thái, vị trí bãi, trọng lượng, ngày nhập), tìm kiếm, lọc, phân trang.
Chạy trên VPS `vps-2424802010066` (Ubuntu Server 24.04 LTS, IP tĩnh `192.168.240.10`) dựng ở Bài 1 trên VMware ESXi 8.

| Thành phần | Công nghệ |
|---|---|
| Frontend | HTML + CSS + JavaScript thuần, gọi REST API bằng `fetch` |
| Backend | Python 3.12, FastAPI 0.163, SQLAlchemy 2.1, Pydantic 2 |
| Cơ sở dữ liệu | PostgreSQL 16, người dùng riêng `qlcontainer_app` (không phải superuser) |
| Chạy dịch vụ | Uvicorn + systemd (`qlcontainer.service`), chỉ lắng nghe `127.0.0.1:8000` |
| Reverse proxy | Nginx cổng 80 |
| Tường lửa | ufw: mặc định chặn kết nối vào, chỉ mở 22/tcp cho mạng ảo và 80/tcp |

## Kiến trúc

```mermaid
flowchart LR
    L["Laptop 192.168.240.1<br/>trình duyệt"] -- "HTTP :80" --> W
    A["Laptop<br/>ssh -i khóa"] -- "SSH :22" --> W
    subgraph VPS["vps-2424802010066 · 192.168.240.10 · Ubuntu 24.04"]
        W{{"ufw<br/>chặn mặc định<br/>mở 22 từ 192.168.240.0/24, mở 80"}}
        W --> N["Nginx :80"]
        N -- "/" --> F["/var/www/qlcontainer<br/>HTML/CSS/JS"]
        N -- "/api/" --> B["Uvicorn + FastAPI<br/>127.0.0.1:8000<br/>systemd: qlcontainer"]
        B -- "psycopg" --> P[("PostgreSQL 16<br/>127.0.0.1:5432<br/>DB qlcontainer")]
    end
```

- Trình duyệt chỉ nói chuyện với **Nginx**. Backend và PostgreSQL chỉ nghe ở `127.0.0.1` nên từ ngoài VPS không
  kết nối thẳng vào được, kể cả khi tắt tường lửa.
- Nginx trả file tĩnh cho `/` và chuyển tiếp `/api/` vào Uvicorn. Frontend và API cùng một gốc (same-origin)
  nên không cần mở CORS.

## Chức năng và bảo mật

| Yêu cầu của đề | Cách làm trong mã |
|---|---|
| Đăng ký, đăng nhập, mật khẩu lưu dạng băm | `bcrypt` cost 12 (`backend/app/security.py`); CSDL chỉ có cột `password_hash` |
| Thêm – xem – sửa – xóa một đối tượng | `backend/app/routers/containers.py`: `GET/POST /api/containers`, `GET/PUT/DELETE /api/containers/{id}` |
| CSDL chạy trên VPS, người dùng riêng | `deploy/install.sh` bước 5: tạo role `qlcontainer_app` NOSUPERUSER, chỉ có quyền trên DB `qlcontainer` |
| Backend là dịch vụ, tự khởi động, chỉ nghe 127.0.0.1 | `deploy/systemd/qlcontainer.service`: `--host 127.0.0.1`, `WantedBy=multi-user.target`, `Restart=on-failure` |
| Nginx reverse proxy cổng 80 | `deploy/nginx/qlcontainer.conf` |
| ufw: chặn vào, mở 22 cho mạng ảo và 80 | `deploy/ufw.sh` |
| Bí mật trong `.env`, có `.env.example` | `.env` bị `.gitignore` chặn; `install.sh` tự sinh mật khẩu CSDL và `SECRET_KEY` ngẫu nhiên trên VPS |

Thêm ngoài yêu cầu:

- Phiên đăng nhập lưu phía máy chủ: cookie `HttpOnly`, `SameSite=Strict` chỉ chứa token ngẫu nhiên; CSDL lưu HMAC của token.
- Chống CSRF: mọi thao tác ghi phải gửi header `X-CSRF-Token` khớp với phiên.
- Chặn dò mật khẩu: sai 5 lần trong 5 phút thì khóa tạm (backend) + Nginx giới hạn 10 lần/phút cho `/api/auth/login`.
- Kiểm tra dữ liệu ở **cả frontend và backend** (Pydantic): số container đúng chữ số kiểm tra ISO 6346, vị trí bãi
  dạng `A-01-02-3`, trọng lượng 0–45 000 kg. CSDL có thêm ràng buộc `CHECK`.
- SQLAlchemy dùng tham số hóa câu lệnh (chống SQL injection); frontend chèn dữ liệu bằng `textContent` (chống XSS);
  Nginx gửi header `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`.
- Dịch vụ chạy bằng tài khoản hệ thống `qlcontainer` (không đăng nhập được), có sandbox systemd (`ProtectSystem=strict`, `NoNewPrivileges`...).

## Cài lại từ đầu trên VPS

### 0. Điều kiện

- Một VPS **Ubuntu Server 24.04 LTS** có Internet (để `apt` và `pip` tải gói), đăng nhập SSH được bằng một người dùng có `sudo`.
  Ở bài này: `ssh -i ~/.ssh/id_ed25519_vps anhtai@192.168.240.10`.
- Biết dải IP của mạng ảo dùng để quản trị (được phép SSH). Ở bài này là `192.168.240.0/24`.

> Nếu đang SSH từ một dải khác dải trong `LAN_CIDR`, bước bật ufw sẽ cắt SSH của chính bạn. Hãy đặt `LAN_CIDR` đúng dải đang dùng.

### 1. Lấy mã nguồn

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/2424802010066-png/LeHuuAnhTai.QuanLyContainer.git
cd LeHuuAnhTai.QuanLyContainer
```

### 2. Chạy script cài đặt

```bash
sudo LAN_CIDR=192.168.240.0/24 bash deploy/install.sh
```

Script làm 9 bước, chạy lại nhiều lần không hỏng (bước nào xong rồi thì bỏ qua hoặc cập nhật):

1. Cài `nginx`, `postgresql`, `python3-venv`, `ufw`.
2. Tạo tài khoản hệ thống `qlcontainer` (shell `nologin`).
3. Chép backend vào `/opt/qlcontainer/backend`, frontend vào `/var/www/qlcontainer`.
4. Sinh `/opt/qlcontainer/.env` với mật khẩu CSDL và `SECRET_KEY` ngẫu nhiên (`openssl rand`), quyền `0640 root:qlcontainer`.
5. Tạo role PostgreSQL `qlcontainer_app` + database `qlcontainer`, thu hồi quyền của `PUBLIC`, giữ `listen_addresses = 'localhost'`.
6. Tạo venv `/opt/qlcontainer/venv`, cài thư viện theo `backend/requirements.txt` (đã ghim phiên bản).
7. Tạo bảng (`python -m app.init_db`).
8. Cài và bật dịch vụ `qlcontainer` (systemd) + site Nginx, xóa site mặc định.
9. Bật ufw theo `deploy/ufw.sh`.

Cuối script in kết quả `/api/health` và các cổng đang nghe.

### 3. Kiểm tra

```bash
systemctl status qlcontainer --no-pager      # active (running), enabled
curl -s http://127.0.0.1/api/health          # {"status":"ok","database":"ok","host":"vps-2424802010066",...}
sudo ufw status verbose                      # deny (incoming); 22/tcp từ 192.168.240.0/24; 80/tcp
sudo ss -tlnp                                # 0.0.0.0:80 nginx; 127.0.0.1:8000 uvicorn; 127.0.0.1:5432 postgres
```

Trên laptop mở `http://192.168.240.10/`, bấm **Đăng ký** để tạo tài khoản rồi đăng nhập.

### Cập nhật phiên bản mới

```bash
cd ~/LeHuuAnhTai.QuanLyContainer && git pull
sudo LAN_CIDR=192.168.240.0/24 bash deploy/install.sh   # giữ nguyên .env và dữ liệu cũ
```

### Gỡ cài đặt

```bash
sudo systemctl disable --now qlcontainer
sudo rm -f /etc/systemd/system/qlcontainer.service /etc/nginx/sites-enabled/qlcontainer /etc/nginx/sites-available/qlcontainer
sudo systemctl daemon-reload && sudo systemctl reload nginx
sudo -u postgres psql -c "DROP DATABASE qlcontainer" -c "DROP ROLE qlcontainer_app"   # XÓA HẲN dữ liệu
sudo rm -rf /opt/qlcontainer /var/www/qlcontainer && sudo userdel qlcontainer
```

## Chạy thử trên máy cá nhân

Cần Python 3.12 và một PostgreSQL bất kỳ (ví dụ Docker):

```bash
docker run -d --name pg-qlc -e POSTGRES_USER=qlc -e POSTGRES_PASSWORD=matkhau_thu -e POSTGRES_DB=qlcontainer -p 127.0.0.1:5432:5432 postgres:16
cp .env.example .env    # sửa DATABASE_URL, SECRET_KEY; đặt SERVE_FRONTEND=true để FastAPI phục vụ luôn frontend
cd backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m app.init_db
uvicorn app.main:app --reload                        # mở http://127.0.0.1:8000/
```

Kiểm thử tự động (12 ca: đăng ký lưu mật khẩu dạng băm, kiểm tra đầu vào, cookie an toàn, khóa đăng nhập sai,
đăng xuất vô hiệu phiên, chặn khi chưa đăng nhập, thiếu CSRF bị chặn, CRUD, ISO 6346, tìm kiếm – lọc – phân trang,
chuỗi chèn SQL không có tác dụng, health).
Test **xóa và tạo lại bảng**, nên phải trỏ tới một database riêng:

```bash
export TEST_DATABASE_URL=postgresql+psycopg://qlc:matkhau_thu@127.0.0.1:5432/qlcontainer_test
python -m pytest -q
```

## REST API

Mọi API container cần đăng nhập (cookie phiên). `POST`, `PUT`, `DELETE` cần thêm header `X-CSRF-Token`.

| Phương thức | Đường dẫn | Việc |
|---|---|---|
| POST | `/api/auth/register` | Đăng ký |
| POST | `/api/auth/login` | Đăng nhập, trả về `csrf_token` và đặt cookie phiên |
| POST | `/api/auth/logout` | Đăng xuất |
| GET | `/api/auth/me` | Người đang đăng nhập |
| GET | `/api/containers?q=&trang_thai=&loai=&page=&page_size=` | Danh sách, tìm kiếm, lọc, phân trang |
| GET | `/api/containers/thong-ke` | Đếm theo trạng thái |
| GET | `/api/containers/{id}` | Xem một container |
| POST | `/api/containers` | Thêm |
| PUT | `/api/containers/{id}` | Sửa |
| DELETE | `/api/containers/{id}` | Xóa |
| GET | `/api/health` | Kiểm tra sống (kèm tên máy chủ) |

Đặt `DOCS_ENABLED=true` trong `.env` rồi `sudo systemctl restart qlcontainer` để xem Swagger ở `/api/docs`.

## Cấu trúc thư mục

```
.
├── .env.example                 # mẫu biến môi trường (KHÔNG có bí mật thật)
├── backend/
│   ├── app/
│   │   ├── main.py              # tạo FastAPI app, /api/health, /api/meta
│   │   ├── config.py            # đọc cấu hình từ biến môi trường
│   │   ├── db.py                # engine + phiên SQLAlchemy
│   │   ├── models.py            # bảng users, sessions, containers
│   │   ├── schemas.py           # kiểm tra dữ liệu vào (Pydantic), ISO 6346
│   │   ├── security.py          # bcrypt, token phiên, giới hạn đăng nhập sai
│   │   ├── deps.py              # lấy người dùng hiện tại, kiểm tra CSRF
│   │   ├── init_db.py           # tạo bảng
│   │   └── routers/             # auth.py, containers.py
│   ├── tests/                   # pytest
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/                    # index.html (đăng nhập/đăng ký), containers.html, css/, js/, img/
└── deploy/
    ├── install.sh               # cài từ đầu trên Ubuntu 24.04
    ├── ufw.sh                   # luật tường lửa
    ├── nginx/qlcontainer.conf
    └── systemd/qlcontainer.service
```

## Tài liệu tham khảo

- FastAPI – https://fastapi.tiangolo.com/
- SQLAlchemy 2.x – https://docs.sqlalchemy.org/en/20/
- Uvicorn deployment – https://www.uvicorn.org/deployment/
- Nginx reverse proxy – https://nginx.org/en/docs/http/ngx_http_proxy_module.html
- PostgreSQL 16 `CREATE ROLE` / `GRANT` – https://www.postgresql.org/docs/16/
- Ubuntu ufw – https://help.ubuntu.com/community/UFW
- systemd sandboxing – https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
- ISO 6346 check digit – https://en.wikipedia.org/wiki/ISO_6346
- OWASP Cheat Sheet (Session Management, CSRF, Password Storage) – https://cheatsheetseries.owasp.org/

Có dùng trợ lý AI (Claude) để gợi ý cấu trúc mã, script triển khai và soạn tài liệu; mọi cấu hình đã được chạy thử
trên VPS và tác giả tự giải thích được.
