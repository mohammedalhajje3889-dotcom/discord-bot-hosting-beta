"""
📦 database.py - نظام إدارة قواعد البيانات
يدير المستخدمين، البوتات، والسجلات
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bots.db")

def get_db() -> sqlite3.Connection:
    """الحصول على اتصال بقاعدة البيانات"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    """إنشاء الجداول إذا لم تكن موجودة"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT NULL,
            name TEXT NOT NULL,
            token TEXT NOT NULL,
            bot_type TEXT NOT NULL DEFAULT 'token',
            entry_point TEXT DEFAULT 'main.py',
            status TEXT DEFAULT 'stopped',
            pid INTEGER DEFAULT NULL,
            port INTEGER DEFAULT NULL,
            directory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_started TIMESTAMP,
            auto_restart INTEGER DEFAULT 1,
            description TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        
        CREATE TABLE IF NOT EXISTS bot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            level TEXT DEFAULT 'info',
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS bot_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT DEFAULT '',
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE,
            UNIQUE(bot_id, key)
        );
    """)
    
    # التحقق من وجود عمود user_id في bots (للترقية)
    try:
        conn.execute("SELECT user_id FROM bots LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE bots ADD COLUMN user_id INTEGER DEFAULT NULL REFERENCES users(id) ON DELETE SET NULL")
    
    conn.commit()
    conn.close()

# ==================== إدارة المستخدمين ====================

def add_user(username: str, password: str, role: str = "user") -> Optional[int]:
    """إضافة مستخدم جديد"""
    try:
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        return None  # المستخدم موجود مسبقاً

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """الحصول على معلومات مستخدم"""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """الحصول على مستخدم باسم المستخدم"""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """التحقق من بيانات تسجيل الدخول"""
    user = get_user_by_username(username)
    if user and user['password'] == password:
        # تحديث آخر تسجيل دخول
        conn = get_db()
        conn.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user['id'],))
        conn.commit()
        conn.close()
        return user
    return None

def update_user(user_id: int, **kwargs) -> bool:
    """تحديث معلومات مستخدم"""
    if not kwargs:
        return False
    sets = ', '.join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values())
    values.append(user_id)
    conn = get_db()
    conn.execute(f"UPDATE users SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True

def get_all_users() -> List[Dict[str, Any]]:
    """الحصول على جميع المستخدمين"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def count_users() -> int:
    """عدد المستخدمين"""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row['cnt'] if row else 0

# ==================== إدارة البوتات ====================

def add_bot(name: str, token: str, bot_type: str = "token", 
            entry_point: str = "main.py", directory: str = "",
            description: str = "", user_id: Optional[int] = None) -> int:
    """إضافة بوت جديد إلى قاعدة البيانات"""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO bots (name, token, bot_type, entry_point, directory, description, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, token, bot_type, entry_point, directory, description, user_id)
    )
    bot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return bot_id

def get_bot(bot_id: int) -> Optional[Dict[str, Any]]:
    """الحصول على معلومات بوت محدد"""
    conn = get_db()
    row = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_bots(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """الحصول على قائمة بجميع البوتات (للمستخدم أو الكل)"""
    conn = get_db()
    if user_id is not None:
        rows = conn.execute("SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM bots ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_bots_by_user(user_id: int) -> List[Dict[str, Any]]:
    """الحصول على بوتات مستخدم معين"""
    return get_all_bots(user_id)

def update_bot(bot_id: int, **kwargs) -> bool:
    """تحديث معلومات بوت"""
    if not kwargs:
        return False
    kwargs['updated_at'] = datetime.now().isoformat()
    sets = ', '.join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values())
    values.append(bot_id)
    conn = get_db()
    conn.execute(f"UPDATE bots SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True

def delete_bot(bot_id: int) -> bool:
    """حذف بوت وجميع بياناته"""
    conn = get_db()
    conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    conn.execute("DELETE FROM bot_logs WHERE bot_id = ?", (bot_id,))
    conn.execute("DELETE FROM bot_settings WHERE bot_id = ?", (bot_id,))
    conn.commit()
    conn.close()
    return True

def count_bots(user_id: Optional[int] = None) -> int:
    """عدد البوتات"""
    conn = get_db()
    if user_id is not None:
        row = conn.execute("SELECT COUNT(*) as cnt FROM bots WHERE user_id = ?", (user_id,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) as cnt FROM bots").fetchone()
    conn.close()
    return row['cnt'] if row else 0

# ==================== السجلات ====================

def add_log(bot_id: int, message: str, level: str = "info"):
    """إضافة سجل لبوت معين"""
    conn = get_db()
    conn.execute(
        "INSERT INTO bot_logs (bot_id, level, message) VALUES (?, ?, ?)",
        (bot_id, level, message)
    )
    conn.commit()
    conn.close()

def get_logs(bot_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """الحصول على آخر السجلات لبوت"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bot_logs WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?",
        (bot_id, limit)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def clear_logs(bot_id: int):
    """مسح سجلات بوت"""
    conn = get_db()
    conn.execute("DELETE FROM bot_logs WHERE bot_id = ?", (bot_id,))
    conn.commit()
    conn.close()

# ==================== الإعدادات ====================

def get_setting(bot_id: int, key: str, default: str = "") -> str:
    """الحصول على إعدادات بوت"""
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM bot_settings WHERE bot_id = ? AND key = ?",
        (bot_id, key)
    ).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(bot_id: int, key: str, value: str):
    """تعيين إعدادات بوت"""
    conn = get_db()
    conn.execute(
        """INSERT INTO bot_settings (bot_id, key, value) VALUES (?, ?, ?)
           ON CONFLICT(bot_id, key) DO UPDATE SET value = excluded.value""",
        (bot_id, key, value)
    )
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات عند الاستيراد
init_db()
