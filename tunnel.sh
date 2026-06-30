#!/usr/bin/env bash
# 🌐 نفق Serveo.net للوصول الخارجي
# يرتبط مع PM2 عشان يشتغل دايم

TUNNEL_LOG="$HOME/serveo.log"
TUNNEL_PID_FILE="$HOME/.serveo.pid"

start() {
    # إيقاف النفق القديم إذا موجود
    stop
    
    echo "🚀 تشغيل النفق الخارجي..."
    nohup ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 \
        -o ExitOnForwardFailure=yes \
        -R 80:localhost:5000 serveo.net > "$TUNNEL_LOG" 2>&1 &
    echo $! > "$TUNNEL_PID_FILE"
    
    sleep 8
    URL=$(grep -o 'https://[^ ]*\.serveousercontent\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
    if [ -n "$URL" ]; then
        echo "✅ النفق شغال!"
        echo "🌐 الرابط: $URL"
    else
        echo "❌ فشل النفق"
    fi
}

stop() {
    if [ -f "$TUNNEL_PID_FILE" ]; then
        PID=$(cat "$TUNNEL_PID_FILE")
        kill $PID 2>/dev/null || true
        rm -f "$TUNNEL_PID_FILE"
        echo "🛑 تم إيقاف النفق"
    fi
}

status() {
    if [ -f "$TUNNEL_PID_FILE" ]; then
        PID=$(cat "$TUNNEL_PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            URL=$(grep -o 'https://[^ ]*\.serveousercontent\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
            echo "✅ النفق شغال (PID: $PID)"
            echo "🌐 $URL"
        else
            echo "❌ النفق متوقف"
        fi
    else
        echo "❌ النفق غير شغال"
    fi
}

url() {
    grep -o 'https://[^ ]*\.serveousercontent\.com' "$TUNNEL_LOG" 2>/dev/null | head -1
}

case "${1:-start}" in
    start)  start ;;
    stop)   stop ;;
    restart) stop; sleep 2; start ;;
    status) status ;;
    url)    url ;;
    *)
        echo "الاستخدام: $0 {start|stop|restart|status|url}"
        exit 1
        ;;
esac
