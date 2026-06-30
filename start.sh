#!/usr/bin/env bash
# 🚀 Discord Bot Hosting - سكريبت التشغيل
# يدعم Railway و التشغيل المحلي

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   🤖 Discord Bot Hosting Panel          ║"
echo "║   جاري التشغيل...                       ║"
echo "╚══════════════════════════════════════════╝"

# إنشاء المجلدات الضرورية
mkdir -p data bots uploads

# التحقق من وجود Railway CLI (للاستضافة السحابية)
if [ -n "$RAILWAY_SERVICE_ID" ]; then
    echo "☁️  بيئة Railway detected"
    echo "📦 تثبيت المتطلبات..."
    pip install -r requirements.txt -q
    
    echo "🌐 تشغيل الخادم على Railway..."
    export PYTHONUNBUFFERED=1
    exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -
else
    # تشغيل محلي
    echo "💻 بيئة محلية detected"
    
    # تثبيت المتطلبات إذا لزم الأمر
    if [ ! -f "requirements.installed" ]; then
        echo "📦 تثبيت المتطلبات..."
        pip install -r requirements.txt -q
        touch requirements.installed
        echo "✅ تم التثبيت"
    fi
    
    PORT="${PORT:-5000}"
    echo "🌐 التشغيل على http://localhost:$PORT"
    echo "🔑 كلمة المرور: ${ADMIN_PASSWORD:-admin123}"
    echo ""
    echo "⚠️  للوصول الخارجي: استخدم ngrok أو Cloudflare Tunnel"
    echo "   مثال: npx ngrok http $PORT"
    echo ""
    
    export PYTHONUNBUFFERED=1
    exec python app.py
fi
