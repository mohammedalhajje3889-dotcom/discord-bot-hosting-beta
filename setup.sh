#!/usr/bin/env bash
# 🔧 إعداد منصة استضافة البوتات (نسخة كاملة)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "╔══════════════════════════════════════════╗"
echo "║   🔧 إعداد منصة استضافة البوتات         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. مجلدات
echo "📂 إنشاء المجلدات..."
mkdir -p data bots uploads logs
echo "   ✅ تم"

# 2. متطلبات Python
echo "📦 تثبيت متطلبات Python..."
pip install -r requirements.txt -q
echo "   ✅ تم"

# 3. PM2
echo "📦 التحقق من PM2..."
if ! command -v pm2 &>/dev/null; then
    npm install -g pm2 2>&1 | tail -1
fi
echo "   ✅ PM2: $(pm2 --version 2>/dev/null || echo 'مثبت')"

# 4. Wake Lock
echo "🔋 تفعيل Wake Lock..."
termux-wake-lock 2>/dev/null && echo "   ✅ مفعل" || echo "   ⚠️  غير متاح"

# 5. تشغيل الخدمة
echo "🚀 تشغيل الخدمة عبر PM2..."
pm2 delete discord-bot-hosting 2>/dev/null || true
pm2 start ecosystem.config.json
pm2 save
echo "   ✅ الخدمة شغالة"

# 6. تشغيل النفق الخارجي
echo "🌐 تشغيل النفق الخارجي (Serveo.net)..."
chmod +x tunnel.sh
./tunnel.sh stop 2>/dev/null
./tunnel.sh start

# 7. معلومات الوصول
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   🎉 تم التشغيل بنجاح!                   ║"
echo "╠══════════════════════════════════════════╣"
echo "║  📍 محلي: http://localhost:5000           ║"

URL=$(./tunnel.sh url)
if [ -n "$URL" ]; then
    echo "║  🌐 خارجي: $URL  ║"
fi

echo "║                                          ║"
echo "║  🔑 كلمة المرور: ${ADMIN_PASSWORD:-admin123}              ║"
echo "║                                          ║"
echo "║  📊 أوامر التحكم:                        ║"
echo "║     pm2 status                           ║"
echo "║     pm2 logs discord-bot-hosting          ║"
echo "║     ./tunnel.sh status                    ║"
echo "║     ./tunnel.sh url                       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

pm2 status 2>/dev/null | head -5
