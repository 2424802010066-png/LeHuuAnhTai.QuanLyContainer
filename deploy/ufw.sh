#!/usr/bin/env bash
# Tường lửa ufw trên VPS: mặc định CHẶN mọi kết nối vào, chỉ mở:
#   - 22/tcp (SSH) cho MẠNG ẢO quản trị (mặc định 192.168.240.0/24 - mạng VPS-Net)
#   - 80/tcp (HTTP, Nginx) cho mọi nơi
# Chạy: sudo LAN_CIDR=192.168.240.0/24 bash deploy/ufw.sh
set -euo pipefail
LAN_CIDR="${LAN_CIDR:-192.168.240.0/24}"

ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$LAN_CIDR" to any port 22 proto tcp comment 'SSH chi tu mang ao VPS-Net'
ufw allow 80/tcp comment 'HTTP - Nginx reverse proxy'
ufw logging low
ufw --force enable
ufw status verbose
