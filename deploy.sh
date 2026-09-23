#!/bin/bash
# ==============================================================================
# Script tự động cập nhật và khởi động lại BAWUI EX PRO trên VPS Linux
# ==============================================================================

set -e

echo "=========================================="
echo "🔄 CẬP NHẬT MÃ NGUỒN VÀ KHỞI ĐỘNG LẠI"
echo "=========================================="

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# 1. Kéo mã nguồn mới nhất
echo "📥 Đang git pull..."
git pull origin main

# 2. Cài đặt dependency (nếu có venv)
if [ -d "venv" ]; then
    echo "📦 Đang kích hoạt môi trường ảo venv..."
    source venv/bin/activate
    pip install -r requirements.txt --quiet
fi

# 3. Khởi động lại dịch vụ
if command -v systemctl &> /dev/null && systemctl list-unit-files | grep -q autopostfb.service; then
    echo "⚙️ Khởi động lại dịch vụ Systemd (autopostfb)..."
    sudo systemctl restart autopostfb
    sudo systemctl status autopostfb --no-pager -l
elif command -v pm2 &> /dev/null && pm2 list | grep -q autopostfb; then
    echo "⚙️ Khởi động lại dịch vụ PM2 (autopostfb)..."
    pm2 restart autopostfb
elif command -v docker &> /dev/null && [ -f "docker-compose.yml" ]; then
    echo "🐳 Rebuild và khởi động Docker container..."
    docker compose up -d --build
else
    echo "⚠️ Khởi động tiến trình chạy nền mới bằng nohup..."
    pkill -f "python3 server.py" || true
    nohup python3 server.py > server.log 2>&1 &
fi

echo "=========================================="
echo "✅ DEPLOY THÀNH CÔNG!"
echo "=========================================="
