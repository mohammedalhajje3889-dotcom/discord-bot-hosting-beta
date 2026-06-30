"""
📦 data_helper.py - نظام قاعدة بيانات لكل بوت
يتم حقن هذا الملف تلقائياً في مجلد كل بوت عند إنشائه

الاستخدام في البوت:
    from data_helper import db
    
    # حفظ واسترجاع بيانات بسيطة (key-value)
    db.set('user_count', 100)
    count = db.get('user_count', 0)
    
    # جداول مخصصة
    db.table('users').add({'id': 123, 'name': 'user', 'coins': 50})
    user = db.table('users').get('id', 123)
    all_users = db.table('users').all()
    
    # JSON كامل
    db.save('my_data', {'key': 'value'})
    data = db.load('my_data', {})
"""
import sqlite3
import os
import json
from typing import Any, Optional, Dict, List, Union

class BotDatabase:
    """
    قاعدة بيانات SQLite مبسطة لكل بوت.
    تنشأ تلقائياً في مجلد data/ الخاص بالبوت.
    """
    
    def __init__(self, data_dir: str = None):
        # تحديد مسار قاعدة البيانات
        if data_dir is None:
            data_dir = os.environ.get('BOT_DATA_DIR', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        self.db_path = os.path.join(data_dir, 'bot_data.db')
        self._conn = None
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """الحصول على اتصال بقاعدة البيانات"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn
    
    def _init_db(self):
        """إنشاء الجداول الأساسية"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS json_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    
    # ==================== Key-Value Storage ====================
    
    def set(self, key: str, value: Any):
        """حفظ قيمة (أي نوع)"""
        conn = self._get_conn()
        json_value = json.dumps(value, ensure_ascii=False)
        conn.execute(
            """INSERT INTO kv_store (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, json_value)
        )
        conn.commit()
    
    def get(self, key: str, default: Any = None) -> Any:
        """استرجاع قيمة"""
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except:
                return row['value']
        return default
    
    def delete(self, key: str):
        """حذف قيمة"""
        conn = self._get_conn()
        conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
        conn.commit()
    
    def keys(self, pattern: str = None) -> List[str]:
        """الحصول على جميع المفاتيح (مع فلتر اختياري)"""
        conn = self._get_conn()
        if pattern:
            rows = conn.execute("SELECT key FROM kv_store WHERE key LIKE ?", (pattern,)).fetchall()
        else:
            rows = conn.execute("SELECT key FROM kv_store").fetchall()
        return [row['key'] for row in rows]
    
    def all(self) -> Dict[str, Any]:
        """الحصول على جميع القيم"""
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM kv_store").fetchall()
        result = {}
        for row in rows:
            try:
                result[row['key']] = json.loads(row['value'])
            except:
                result[row['key']] = row['value']
        return result
    
    # ==================== JSON Document Storage ====================
    
    def save(self, key: str, data: Any):
        """حفظ مستند JSON كامل"""
        conn = self._get_conn()
        json_value = json.dumps(data, ensure_ascii=False)
        conn.execute(
            """INSERT INTO json_store (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, json_value)
        )
        conn.commit()
    
    def load(self, key: str, default: Any = None) -> Any:
        """استرجاع مستند JSON"""
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM json_store WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except:
                return row['value']
        return default
    
    # ==================== Table Management ====================
    
    def table(self, table_name: str) -> 'Table':
        """الوصول إلى جدول مخصص (يتم إنشاؤه تلقائياً)"""
        return Table(self, table_name)
    
    def create_table(self, table_name: str, schema: Dict[str, str]):
        """إنشاء جدول مخصص مع مخطط (schema)
        
        مثال:
            db.create_table('users', {
                'id': 'INTEGER PRIMARY KEY',
                'name': 'TEXT NOT NULL',
                'coins': 'INTEGER DEFAULT 0'
            })
        """
        conn = self._get_conn()
        columns = ', '.join(f"{col} {dtype}" for col, dtype in schema.items())
        conn.execute(f"CREATE TABLE IF NOT EXISTS [{table_name}] ({columns})")
        conn.commit()
    
    def custom_query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """استعلام SQL مخصص"""
        conn = self._get_conn()
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    
    def custom_execute(self, sql: str, params: tuple = ()):
        """تنفيذ SQL مخصص (إدراج/تحديث/حذف)"""
        conn = self._get_conn()
        conn.execute(sql, params)
        conn.commit()
    
    def close(self):
        """إغلاق الاتصال"""
        if self._conn:
            self._conn.close()
            self._conn = None


class Table:
    """إدارة جدول مخصص"""
    
    def __init__(self, db: BotDatabase, table_name: str):
        self.db = db
        self.table_name = table_name
        self._ensure_exists()
    
    def _ensure_exists(self):
        """إنشاء الجدول إذا لم يكن موجوداً (بمخطط ديناميكي)"""
        conn = self.db._get_conn()
        # نتحقق من وجود الجدول
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.table_name,)
        ).fetchone()
        if not row:
            # إنشاء جدول بمخطط عام (id + data JSON)
            conn.execute(f"""
                CREATE TABLE [{self.table_name}] (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL DEFAULT '{{}}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def add(self, data: Dict) -> int:
        """إضافة سجل جديد"""
        conn = self.db._get_conn()
        json_data = json.dumps(data, ensure_ascii=False)
        cursor = conn.execute(
            f"INSERT INTO [{self.table_name}] (data) VALUES (?)",
            (json_data,)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get(self, column: str, value: Any) -> Optional[Dict]:
        """البحث عن سجل"""
        conn = self.db._get_conn()
        # إذا كان column = 'id' نستخدم المقارنة المباشرة
        if column == 'id':
            row = conn.execute(
                f"SELECT * FROM [{self.table_name}] WHERE id = ?",
                (value,)
            ).fetchone()
        else:
            # بحث في حقل JSON
            rows = conn.execute(f"SELECT * FROM [{self.table_name}]").fetchall()
            for r in rows:
                r = dict(r)
                try:
                    data = json.loads(r['data'])
                    if str(data.get(column)) == str(value):
                        r['_data'] = data
                        return r
                except:
                    pass
            return None
        
        if row:
            row = dict(row)
            try:
                row['_data'] = json.loads(row['data'])
            except:
                row['_data'] = {}
            return row
        return None
    
    def update(self, record_id: int, data: Dict) -> bool:
        """تحديث سجل"""
        conn = self.db._get_conn()
        # دمج البيانات القديمة مع الجديدة
        row = conn.execute(
            f"SELECT data FROM [{self.table_name}] WHERE id = ?",
            (record_id,)
        ).fetchone()
        if not row:
            return False
        
        try:
            existing = json.loads(row['data'])
        except:
            existing = {}
        existing.update(data)
        
        conn.execute(
            f"UPDATE [{self.table_name}] SET data = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(existing, ensure_ascii=False), record_id)
        )
        conn.commit()
        return True
    
    def delete(self, record_id: int) -> bool:
        """حذف سجل"""
        conn = self.db._get_conn()
        conn.execute(f"DELETE FROM [{self.table_name}] WHERE id = ?", (record_id,))
        conn.commit()
        return True
    
    def all(self) -> List[Dict]:
        """الحصول على جميع السجلات"""
        conn = self.db._get_conn()
        rows = conn.execute(f"SELECT * FROM [{self.table_name}] ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            row = dict(row)
            try:
                row['_data'] = json.loads(row['data'])
            except:
                row['_data'] = {}
            result.append(row)
        return result
    
    def count(self) -> int:
        """عدد السجلات"""
        conn = self.db._get_conn()
        row = conn.execute(f"SELECT COUNT(*) as cnt FROM [{self.table_name}]").fetchone()
        return row['cnt'] if row else 0
    
    def filter(self, **conditions) -> List[Dict]:
        """تصفية السجلات حسب الشروط
        
        مثال:
            users = db.table('users').filter(coins=100, level='gold')
        """
        conn = self.db._get_conn()
        rows = conn.execute(f"SELECT * FROM [{self.table_name}] ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            row = dict(row)
            try:
                data = json.loads(row['data'])
            except:
                data = {}
            row['_data'] = data
            
            # التحقق من جميع الشروط
            match = True
            for key, value in conditions.items():
                if str(data.get(key)) != str(value):
                    match = False
                    break
            
            if match:
                result.append(row)
        
        return result
    
    def drop(self):
        """حذف الجدول بالكامل"""
        conn = self.db._get_conn()
        conn.execute(f"DROP TABLE IF EXISTS [{self.table_name}]")
        conn.commit()


# ==================== إنشاء كائن قاعدة البيانات الافتراضي ====================
# يتم استيراده في البوت مباشرة: from data_helper import db

data_dir = os.environ.get('BOT_DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
db = BotDatabase(data_dir)
