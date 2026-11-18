#!/usr/bin/env bash
# =============================================================================
#  Cài đặt TỪ ĐẦU ứng dụng Quản lý container trên Ubuntu Server 24.04 LTS
#  Lê Hữu Anh Tài - MSSV 2424802010066
#
#  Cách dùng (trên VPS, trong thư mục repo đã clone):
#     sudo bash deploy/install.sh
#  Biến tùy chọn:
#     LAN_CIDR=192.168.240.0/24   dải mạng ảo được phép SSH (ufw)
#     ENABLE_UFW=1                bật tường lửa (mặc định 1)
#  Chạy lại nhiều lần được (idempotent): bước nào đã xong thì bỏ qua / cập nhật.
# =============================================================================
set -euo pipefail

APP_USER=qlcontainer
APP_DIR=/opt/qlcontainer
WEB_DIR=/var/www/qlcontainer
DB_NAME=qlcontainer
DB_USER=qlcontainer_app
LAN_CIDR="${LAN_CIDR:-192.168.240.0/24}"
ENABLE_UFW="${ENABLE_UFW:-1}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

buoc() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" -eq 0 ] || { echo "Hãy chạy bằng sudo"; exit 1; }

buoc "1/9 Cài gói hệ thống: nginx, postgresql, python3-venv, ufw"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx postgresql python3-venv python3-pip ufw rsync curl >/dev/null

buoc "2/9 Tạo tài khoản hệ thống riêng cho ứng dụng: $APP_USER (không đăng nhập được)"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o root -g "$APP_USER" -m 0750 "$APP_DIR"

buoc "3/9 Chép mã nguồn backend -> $APP_DIR, frontend -> $WEB_DIR"
rsync -a --delete --exclude '__pycache__' --exclude 'tests' "$REPO_DIR/backend/" "$APP_DIR/backend/"
rsync -a --delete "$REPO_DIR/frontend/" "$WEB_DIR/"
chown -R root:"$APP_USER" "$APP_DIR/backend"; chmod -R u=rwX,g=rX,o= "$APP_DIR/backend"
chown -R root:root "$WEB_DIR"; chmod -R u=rwX,go=rX "$WEB_DIR"

buoc "4/9 Tạo file bí mật $APP_DIR/.env (chỉ root và $APP_USER đọc được)"
if [ ! -f "$APP_DIR/.env" ]; then
    DB_PASS="$(openssl rand -hex 24)"
    SECRET_KEY="$(openssl rand -hex 32)"
    umask 077
    cat > "$APP_DIR/.env" <<EOF
# Sinh tự động bởi deploy/install.sh - KHÔNG đưa lên GitHub
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME
SECRET_KEY=$SECRET_KEY
SESSION_HOURS=8
COOKIE_SECURE=false
DOCS_ENABLED=false
EOF
    umask 022
fi
chown root:"$APP_USER" "$APP_DIR/.env"; chmod 0640 "$APP_DIR/.env"
DB_PASS="$(sed -n 's#^DATABASE_URL=postgresql+psycopg://[^:]*:\([^@]*\)@.*#\1#p' "$APP_DIR/.env")"

buoc "5/9 PostgreSQL: user riêng $DB_USER (không phải superuser), CSDL $DB_NAME, chỉ nghe localhost"
sudo -u postgres psql -v ON_ERROR_STOP=1 -q -v dbuser="$DB_USER" -v dbname="$DB_NAME" <<SQL
\set dbpass '$DB_PASS'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'dbuser')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'dbuser') \gexec
ALTER ROLE :"dbuser" WITH LOGIN PASSWORD :'dbpass' CONNECTION LIMIT 20;
SELECT format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0', :'dbname', :'dbuser')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname') \gexec
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"dbname" TO :"dbuser";
SQL
sudo -u postgres psql -v ON_ERROR_STOP=1 -q -d "$DB_NAME" -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC; ALTER SCHEMA public OWNER TO $DB_USER;"
PG_CONF="$(sudo -u postgres psql -tAc 'SHOW config_file')"
grep -qE "^listen_addresses\s*=\s*'localhost'" "$PG_CONF" || echo "listen_addresses = 'localhost'" >> "$PG_CONF"
systemctl enable --now postgresql >/dev/null
systemctl restart postgresql

buoc "6/9 Môi trường Python ảo (venv) + thư viện ghim phiên bản"
[ -x "$APP_DIR/venv/bin/python" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"
chown -R root:"$APP_USER" "$APP_DIR/venv"; chmod -R g+rX,o= "$APP_DIR/venv"

buoc "7/9 Tạo bảng CSDL"
( cd "$APP_DIR/backend" && set -a && . "$APP_DIR/.env" && set +a && \
  runuser -u "$APP_USER" -- "$APP_DIR/venv/bin/python" -m app.init_db )

buoc "8/9 Dịch vụ systemd + Nginx reverse proxy"
install -m 0644 "$REPO_DIR/deploy/systemd/qlcontainer.service" /etc/systemd/system/qlcontainer.service
systemctl daemon-reload
systemctl enable qlcontainer >/dev/null
systemctl restart qlcontainer
install -m 0644 "$REPO_DIR/deploy/nginx/qlcontainer.conf" /etc/nginx/sites-available/qlcontainer
ln -sf /etc/nginx/sites-available/qlcontainer /etc/nginx/sites-enabled/qlcontainer
rm -f /etc/nginx/sites-enabled/default
nginx -t -q
systemctl enable nginx >/dev/null
systemctl reload nginx

buoc "9/9 Tường lửa ufw (SSH chỉ từ $LAN_CIDR, HTTP 80)"
if [ "$ENABLE_UFW" = "1" ]; then LAN_CIDR="$LAN_CIDR" bash "$REPO_DIR/deploy/ufw.sh"; fi

buoc "Kiểm tra"
for i in $(seq 1 20); do curl -fsS http://127.0.0.1/api/health && break; sleep 1; done
echo
ss -tlnp | grep -E ':(80|8000|5432)\b' || true
echo -e "\n\033[1;32mXONG.\033[0m Mở trình duyệt: http://$(hostname -I | awk '{print $1}')/"
