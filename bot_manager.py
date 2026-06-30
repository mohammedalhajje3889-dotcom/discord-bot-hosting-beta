"""
🤖 bot_manager.py - مدير عمليات البوتات
يقوم بتشغيل، إيقاف، ومراقبة بوتات الديسكورد كعمليات منفصلة
"""
import os
import sys
import signal
import subprocess
import threading
import time
import json
import shutil
import zipfile
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime

import database as db

BOTS_DIR = os.path.join(os.path.dirname(__file__), "bots")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# قاموس لتخزين العمليات النشطة
active_processes: Dict[int, subprocess.Popen] = {}
process_lock = threading.Lock()

DATA_HELPER_SOURCE = os.path.join(os.path.dirname(__file__), "data_helper.py")

def ensure_dirs(bot_id: int):
    """إنشاء المجلدات الخاصة ببوت معين"""
    bot_dir = os.path.join(BOTS_DIR, str(bot_id))
    os.makedirs(bot_dir, exist_ok=True)
    os.makedirs(os.path.join(bot_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(bot_dir, "logs"), exist_ok=True)
    
    # حقن data_helper.py في مجلد البوت
    _inject_data_helper(bot_dir)
    
    return bot_dir

def _inject_data_helper(bot_dir: str):
    """حقن ملف data_helper.py في مجلد البوت وإنشاء قاعدة البيانات
    
    ينسخ الملف المساعد إلى مجلد البوت (وجميع المجلدات الفرعية)
    وينشئ ملف قاعدة بيانات فارغ في مجلد data/
    """
    # 1. نسخ data_helper.py إلى مجلد البوت
    dest = os.path.join(bot_dir, "data_helper.py")
    if not os.path.exists(dest):
        try:
            if os.path.exists(DATA_HELPER_SOURCE):
                shutil.copy2(DATA_HELPER_SOURCE, dest)
                print(f"   📦 تم حقن data_helper.py في البوت")
            else:
                print(f"   ⚠️ ملف data_helper.py غير موجود في المصدر")
        except Exception as e:
            print(f"   ⚠️ فشل حقن data_helper.py: {e}")
    
    # 2. أيضاً ننسخه في مجلد code/ إذا موجود (للبوتات المرفوعة ZIP)
    code_dir = os.path.join(bot_dir, "code")
    if os.path.exists(code_dir):
        dest_code = os.path.join(code_dir, "data_helper.py")
        if not os.path.exists(dest_code) and os.path.exists(DATA_HELPER_SOURCE):
            try:
                shutil.copy2(DATA_HELPER_SOURCE, dest_code)
                print(f"   📦 تم حقن data_helper.py في مجلد الكود")
            except Exception as e:
                print(f"   ⚠️ فشل حقن data_helper.py في الكود: {e}")
    
    # 3. إنشاء قاعدة بيانات فارغة للبوت
    data_dir = os.path.join(bot_dir, "data")
    db_path = os.path.join(data_dir, "bot_data.db")
    if not os.path.exists(db_path):
        try:
            # إنشاء قاعدة بيانات فارغة بواسطة Python
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
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
            conn.close()
            print(f"   🗄️ تم إنشاء قاعدة بيانات البوت: bot_data.db")
        except Exception as e:
            print(f"   ⚠️ فشل إنشاء قاعدة البيانات: {e}")

def generate_minimal_bot_script(token: str, bot_name: str) -> str:
    """
    إنشاء سكربت بوت بسيط يعمل بالتوكن فقط
    هذا يستخدم discord.py للحفاظ على اتصال البوت
    التوكن يمرر عبر متغير البيئة DISCORD_TOKEN للأمان
    """
    import json as _json
    safe_name = _json.dumps(bot_name, ensure_ascii=False)
    return f'''"""
🤖 {bot_name} - بوت مستضاف على المنصة
تم إنشاؤه تلقائياً بواسطة Discord Bot Hosting Panel
"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import json
import signal

# ========== قاعدة البيانات المدمجة ==========
# استيراد نظام التخزين المدمج لكل بوت
# يوفر:
#   from data_helper import db
#   db.set(key, value) / db.get(key, default)
#   db.table(name).add(data) / db.table(name).all()
#   db.save(key, data) / db.load(key)
try:
    from data_helper import db
    HAS_DB = True
except ImportError:
    HAS_DB = False

# ========== إعدادات البوت ==========
# التوكن يقرأ من متغير البيئة للأمان
TOKEN = os.environ.get("DISCORD_TOKEN", "")
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين DISCORD_TOKEN")
    sys.exit(1)

PREFIX = os.environ.get("PREFIX", "!")
BOT_NAME = os.environ.get("BOT_NAME", {safe_name})
DATA_DIR = os.environ.get("BOT_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ========== الأحداث الأساسية ==========
@bot.event
async def on_ready():
    print(f"✅ {{bot.user}} متصل! (ID: {{bot.user.id}})")
    print(f"🌐 شغال في {{len(bot.guilds)}} server(s)")
    if HAS_DB:
        db.set("bot_ready", True)
        db.set("bot_start_time", str(__import__('datetime').datetime.now()))
        print(f"🗄️ قاعدة البيانات البوت جاهزة")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name=f"استضافة {{BOT_NAME}}"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# ========== أوامر بسيطة ==========
@bot.command(name="ping")
async def ping(ctx):
    """اختبار اتصال البوت"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {{latency}}ms")

@bot.command(name="info")
async def info(ctx):
    """معلومات عن البوت"""
    embed = discord.Embed(
        title="🤖 معلومات البوت",
        color=discord.Color.blue()
    )
    embed.add_field(name="الاسم", value={{BOT_NAME}}, inline=True)
    embed.add_field(name="السيرفرات", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="المستخدمين", value=str(len(set(bot.get_all_members()))), inline=True)
    embed.add_field(name="Ping", value=f"{{round(bot.latency * 1000)}}ms", inline=True)
    await ctx.send(embed=embed)

# ========== أوامر قاعدة البيانات (مثال) ==========
if HAS_DB:
    @bot.command(name="stats")
    async def stats(ctx):
        """إحصائيات البوت"""
        cmd_count = db.get("command_count", 0)
        start_time = db.get("bot_start_time", "غير معروف")
        await ctx.send(f"📊 إحصائيات البوت:\n⚡ أوامر منفذة: {{cmd_count}}\n🕐 آخر تشغيل: {{start_time}}")

    @bot.command(name="save")
    async def save_data(ctx, key: str, *, value: str):
        """حفظ بيانات: !save key value"""
        db.set(f"user_{{ctx.author.id}}_{{key}}", value)
        await ctx.send(f"✅ تم حفظ `{{key}}` = `{{value}}`")

    @bot.command(name="load")
    async def load_data(ctx, key: str):
        """استرجاع بيانات: !load key"""
        value = db.get(f"user_{{ctx.author.id}}_{{key}}", "لا توجد بيانات")
        await ctx.send(f"📂 `{{key}}` = {{value}}")

# ========== تشغيل البوت ==========
def shutdown_handler(signum, frame):
    print("🛑 جاري إيقاف البوت...")
    if HAS_DB:
        db.close()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

if __name__ == "__main__":
    print(f"🚀 بدء تشغيل {{BOT_NAME}}...")
    if HAS_DB:
        print(f"🗄️ قاعدة البيانات: {{db.db_path}}")
    try:
        bot.run(TOKEN, reconnect=True)
    except discord.LoginFailure:
        print("❌ فشل تسجيل الدخول! التوكن غير صالح.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ خطأ: {{e}}")
        sys.exit(1)
'''

def _inject_credentials(code_dir: str, token: str, prefix: str = ""):
    """
    يحقن التوكن والبادئة في ملفات إعدادات البوت
    عشان البوت يشتغل مباشرة بدون الحاجة لمتغيرات بيئة
    """
    if not token:
        return
    
    print(f"🔑 ربط التوكن بملفات البوت...")
    
    # 1. config.json
    config_path = os.path.join(code_dir, 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            changed = False
            if 'token' in config:
                config['token'] = token
                changed = True
            if prefix and 'prefix' in config:
                config['prefix'] = prefix
                changed = True
            
            if changed:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                print(f"   ✅ config.json - تم حقن التوكن")
        except Exception as e:
            print(f"   ⚠️ config.json: {e}")
    
    # 2. config.example.json
    example_path = os.path.join(code_dir, 'config.example.json')
    if os.path.exists(example_path):
        try:
            with open(example_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            changed = False
            if 'token' in config:
                config['token'] = token
                changed = True
            if prefix and 'prefix' in config:
                config['prefix'] = prefix
                changed = True
            
            if changed:
                with open(example_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                print(f"   ✅ config.example.json - تم حقن التوكن")
        except Exception as e:
            print(f"   ⚠️ config.example.json: {e}")
    
    # 3. .env file
    env_path = os.path.join(code_dir, '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            has_token = False
            has_prefix = False
            for line in lines:
                if line.startswith('DISCORD_TOKEN=') or line.startswith('TOKEN='):
                    new_lines.append(f'DISCORD_TOKEN={token}\n')
                    has_token = True
                elif prefix and (line.startswith('PREFIX=')):
                    new_lines.append(f'PREFIX={prefix}\n')
                    has_prefix = True
                else:
                    new_lines.append(line)
            
            if not has_token:
                new_lines.append(f'\n# تمت الإضافة بواسطة Bot Hosting Panel\n')
                new_lines.append(f'DISCORD_TOKEN={token}\n')
            if prefix and not has_prefix:
                new_lines.append(f'PREFIX={prefix}\n')
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"   ✅ .env - تم حقن التوكن")
        except Exception as e:
            print(f"   ⚠️ .env: {e}")
    
    # 4. settings.json (للبوتات الأخرى)
    for root, dirs, files in os.walk(code_dir):
        for fname in files:
            if fname in ('settings.json', 'config.py', 'settings.py', 'bot_config.json'):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    replaced = False
                    # استبدال التوكن في ملفات Python
                    if fname.endswith('.py'):
                        # استبدال المتغيرات الشائعة
                        for var in ['TOKEN', 'token', 'DISCORD_TOKEN', 'discord_token', 'BOT_TOKEN']:
                            old = f'{var} = "' if var in ('TOKEN', 'token', 'BOT_TOKEN') else f'{var} = os.environ'
                            if old in content:
                                # فقط نضيف تعليق
                                pass
                    else:
                        # JSON files
                        data = json.loads(content)
                        if 'token' in data:
                            data['token'] = token
                            replaced = True
                        if prefix and 'prefix' in data:
                            data['prefix'] = prefix
                            replaced = True
                        if replaced:
                            with open(fpath, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            print(f"   ✅ {fname} - تم حقن التوكن")
                except Exception as e:
                    print(f"   ⚠️ {fname}: {e}")


def extract_zip_bot(zip_path: str, bot_id: int) -> Optional[str]:
    """
    استخراج ملف zip لبوت معين
    يحاول تحديد نقطة الدخول (main.py, bot.py, index.py, إلخ)
    يدعم ZIP للمجلدات والمحتويات المفردة
    """
    bot_dir = ensure_dirs(bot_id)
    code_dir = os.path.join(bot_dir, "code")
    
    # حذف المحتوى السابق إذا موجود
    if os.path.exists(code_dir):
        shutil.rmtree(code_dir)
    os.makedirs(code_dir, exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(code_dir)
        
        # ===== كشف إذا المستخدم ضغط مجلد بدل المحتويات =====
        # لو في مجلد واحد فقط في الجذر، والمجلد ما فيه ملفات py،
        # معناته المستخدم ضغط مجلد -> نرفع المحتويات لمستوى أعلى
        contents = [f for f in os.listdir(code_dir) 
                    if not f.startswith('.') and not f.startswith('__')]
        
        if len(contents) == 1:
            single_item = os.path.join(code_dir, contents[0])
            if os.path.isdir(single_item):
                # المستخدم ضغط مجلد! ننقل محتوياته للجذر
                inner_dir = single_item
                for item in os.listdir(inner_dir):
                    shutil.move(os.path.join(inner_dir, item), 
                               os.path.join(code_dir, item))
                os.rmdir(inner_dir)
                print(f"📦 تم كشف مجلد {contents[0]} ونقل محتوياته")
        
        # ===== البحث عن ملف الدخول الرئيسي =====
        # 1. نبحث في الجذر أولاً
        possible_entries = ['main.py', 'bot.py', 'index.py', 'run.py', 'start.py', 'app.py']
        found_entry = None
        
        for entry in possible_entries:
            entry_path = os.path.join(code_dir, entry)
            if os.path.exists(entry_path):
                found_entry = entry
                break
        
        # 2. إذا ما لقينا، نبحث في مجلد فرعي واحد (زي src/ أو bot/)
        if not found_entry:
            for root, dirs, files in os.walk(code_dir):
                if root == code_dir:
                    continue  # skip الجذر
                depth = root.replace(code_dir, '').count(os.sep)
                if depth > 2:
                    continue  # ما نتعمق كثير
                for entry in possible_entries:
                    if entry in files:
                        # نأخذ المسار النسبي من code_dir
                        rel_path = os.path.relpath(os.path.join(root, entry), code_dir)
                        found_entry = rel_path
                        break
                if found_entry:
                    break
        
        # 3. إذا لسا ما لقينا، نبحث عن أي ملف .py
        if not found_entry:
            for root, dirs, files in os.walk(code_dir):
                py_files = [f for f in files if f.endswith('.py') and not f.startswith('__')]
                if py_files:
                    rel_path = os.path.relpath(os.path.join(root, py_files[0]), code_dir)
                    found_entry = rel_path
                    break
        
        if not found_entry:
            print("❌ ما لقينا أي ملف Python في الـ ZIP")
            return None
        
        print(f"📄 تم العثور على نقطة الدخول: {found_entry}")
        
        # ===== ربط التوكن بملفات البوت =====
        # يبحث عن config.json, .env, settings.json ويحقن التوكن
        # نقرأ التوكن من قاعدة البيانات
        bot_data = db.get_bot(bot_id)
        if bot_data:
            bot_prefix = db.get_setting(bot_id, 'PREFIX', '')
            _inject_credentials(code_dir, bot_data['token'], bot_prefix)
        
        # ===== حقن data_helper.py في مجلد البوت =====
        _inject_data_helper(bot_dir)
        # أيضاً ننسخها داخل مجلد الكود
        code_helper = os.path.join(code_dir, "data_helper.py")
        if not os.path.exists(code_helper) and os.path.exists(DATA_HELPER_SOURCE):
            try:
                shutil.copy2(DATA_HELPER_SOURCE, code_helper)
                print(f"   📦 تم حقن data_helper.py في مجلد الكود")
            except Exception as e:
                print(f"   ⚠️ فشل حقن data_helper.py: {e}")
        
        # ===== تثبيت المتطلبات إذا وجدت =====
        # نبحث عن requirements.txt في الجذر والمجلدات الفرعية
        requirements_paths = []
        for root, dirs, files in os.walk(code_dir):
            if 'requirements.txt' in files:
                requirements_paths.append(os.path.join(root, 'requirements.txt'))
        
        for req_path in requirements_paths:
            try:
                print(f"📦 تثبيت المتطلبات من {req_path}...")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_path],
                    cwd=os.path.dirname(req_path),
                    capture_output=True,
                    timeout=120
                )
            except Exception as e:
                print(f"⚠️ فشل تثبيت المتطلبات: {e}")
        
        return found_entry
        
    except zipfile.BadZipFile:
        print("❌ ملف ZIP تالف")
        return None
    except Exception as e:
        print(f"❌ خطأ في استخراج الملف: {e}")
        return None

def create_bot_runner_script(bot_id: int, bot_info: Dict[str, Any]) -> str:
    """
    إنشاء سكربت التشغيل للبوت
    للسكربتات المرفوعة (zip)، نستخدم الكود المرفوع
    للتوكن فقط، نستخدم السكربت المصغر
    """
    bot_dir = ensure_dirs(bot_id)
    runner_path = os.path.join(bot_dir, "runner.py")
    
    if bot_info['bot_type'] == 'zip':
        # لبوت zip، ننشئ سكربت يشغل الملف الأصلي
        code_dir = os.path.join(bot_dir, "code")
        entry_point = bot_info.get('entry_point', 'main.py')
        entry_path = os.path.join(code_dir, entry_point)
        
        if not os.path.exists(entry_path):
            # البحث في مجلدات فرعية (إذا كان entry_point مسار نسبي)
            for root, dirs, files in os.walk(code_dir):
                basename = os.path.basename(entry_point)
                if basename in files:
                    entry_path = os.path.join(root, basename)
                    break
        
        # المسار النسبي من code_dir للـ runner
        try:
            rel_entry = os.path.relpath(entry_path, code_dir)
        except ValueError:
            rel_entry = entry_point
        
        runner_content = f'''"""
🤖 {bot_info['name']} - بوت مستضاف
تشغيل: {rel_entry}
"""
import os
import sys
import signal

# إضافة مسار الكود (المجلد الرئيسي)
sys.path.insert(0, r"{code_dir}")

# تغيير مسار العمل لمجلد الكود
os.chdir(r"{code_dir}")

# إعداد مسار البيانات
data_dir = r"{os.path.join(bot_dir, 'data')}"
os.makedirs(data_dir, exist_ok=True)
os.environ['BOT_DATA_DIR'] = data_dir

# التوكن يمرر عبر متغير البيئة (مضبوط مسبقاً من bot_manager)
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
if not DISCORD_TOKEN:
    print("❌ خطأ: لم يتم تعيين DISCORD_TOKEN")
    sys.exit(1)

def shutdown_handler(signum, frame):
    print("🛑 جاري إيقاف البوت...")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

# المسار الكامل لملف الدخول
entry_file = r"{entry_path}"
if not os.path.exists(entry_file):
    # بحث أعمى عن الملف
    import glob
    matches = glob.glob(os.path.join(r"{code_dir}", '**', os.path.basename(r"{rel_entry}")), recursive=True)
    if matches:
        entry_file = matches[0]
    else:
        print(f"❌ ملف الدخول غير موجود: {{entry_file}}")
        sys.exit(1)

print(f"🚀 تشغيل: {{entry_file}}")

# تشغيل ملف البوت
with open(entry_file, 'r', encoding='utf-8') as f:
    code = f.read()
exec(code)
'''
    else:
        # لبوت التوكن، نستخدم السكربت المصغر
        runner_content = generate_minimal_bot_script(bot_info['token'], bot_info['name'])
    
    with open(runner_path, 'w', encoding='utf-8') as f:
        f.write(runner_content)
    
    # إعداد ملف env للبوت
    env_path = os.path.join(bot_dir, ".env")
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f'DISCORD_TOKEN={bot_info["token"]}\n')
        f.write(f'BOT_NAME={bot_info["name"]}\n')
        f.write(f'DATA_DIR={os.path.join(bot_dir, "data")}\n')
    
    return runner_path

def start_bot(bot_id: int) -> bool:
    """تشغيل بوت"""
    bot_info = db.get_bot(bot_id)
    if not bot_info:
        return False
    
    # التحقق من عدم تشغيله مسبقاً
    with process_lock:
        if bot_id in active_processes and active_processes[bot_id].poll() is None:
            return True  # البوت شغال بالفعل
    
    try:
        bot_dir = ensure_dirs(bot_id)
        
        # إعداد متغيرات البيئة
        env = os.environ.copy()
        env['DISCORD_TOKEN'] = bot_info['token']
        env['BOT_NAME'] = bot_info['name']
        env['BOT_DATA_DIR'] = os.path.join(bot_dir, "data")
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONPATH'] = bot_dir
        
        # جلب الإعدادات المخصصة للبوت
        bot_prefix = db.get_setting(bot_id, 'PREFIX', '')
        if bot_prefix:
            env['PREFIX'] = bot_prefix
        
        if bot_info['bot_type'] == 'zip':
            # لبوت ZIP -> نشغل main.py مباشرة
            code_dir = os.path.join(bot_dir, "code")
            
            # إنشاء مجلد البيانات
            data_dir = os.path.join(bot_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            env['BOT_DATA_DIR'] = data_dir
            
            entry_point = bot_info.get('entry_point', 'main.py')
            entry_path = os.path.join(code_dir, entry_point)
            
            if not os.path.exists(entry_path):
                # بحث في مجلدات فرعية
                import glob
                matches = glob.glob(os.path.join(code_dir, '**', entry_point), recursive=True)
                if matches:
                    entry_path = matches[0]
                else:
                    # بحث عن أي ملف .py
                    py_matches = glob.glob(os.path.join(code_dir, '**', '*.py'), recursive=True)
                    if py_matches:
                        entry_path = py_matches[0]
                    else:
                        db.add_log(bot_id, f"❌ ملف الدخول غير موجود: {entry_point}", "error")
                        return False
            
            db.add_log(bot_id, f"🚀 تشغيل {os.path.relpath(entry_path, code_dir)}...", "info")
            
            process = subprocess.Popen(
                [sys.executable, entry_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=code_dir,
                env=env,
                text=True,
                bufsize=1
            )
        else:
            # لبوت التوكن -> نستخدم runner script
            runner_path = create_bot_runner_script(bot_id, bot_info)
            process = subprocess.Popen(
                [sys.executable, runner_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=bot_dir,
                env=env,
                text=True,
                bufsize=1
            )
        
        with process_lock:
            active_processes[bot_id] = process
        
        # تحديث الحالة في قاعدة البيانات
        db.update_bot(
            bot_id,
            status='running',
            pid=process.pid,
            last_started=datetime.now().isoformat()
        )
        
        db.add_log(bot_id, f"🚀 تم تشغيل البوت (PID: {process.pid})", "success")
        
        # بدء خيط لقراءة المخرجات
        threading.Thread(target=read_output, args=(bot_id, process), daemon=True).start()
        
        # بدء خيط لمراقبة العملية
        threading.Thread(target=monitor_process, args=(bot_id, process), daemon=True).start()
        
        return True
        
    except Exception as e:
        db.add_log(bot_id, f"❌ فشل التشغيل: {e}", "error")
        return False

def stop_bot(bot_id: int) -> bool:
    """إيقاف بوت"""
    with process_lock:
        process = active_processes.get(bot_id)
        if not process:
            db.update_bot(bot_id, status='stopped', pid=None)
            return True
        
        if process.poll() is not None:
            # العملية منتهية بالفعل
            del active_processes[bot_id]
            db.update_bot(bot_id, status='stopped', pid=None)
            return True
        
        try:
            # محاولة إيقاف نظيف
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except Exception:
            pass
        
        del active_processes[bot_id]
    
    db.update_bot(bot_id, status='stopped', pid=None)
    db.add_log(bot_id, "🛑 تم إيقاف البوت", "warning")
    return True

def restart_bot(bot_id: int) -> bool:
    """إعادة تشغيل بوت"""
    stop_bot(bot_id)
    time.sleep(2)
    return start_bot(bot_id)

def get_bot_status(bot_id: int) -> str:
    """الحصول على حالة البوت"""
    with process_lock:
        process = active_processes.get(bot_id)
        if not process:
            return 'stopped'
        if process.poll() is None:
            return 'running'
        return 'crashed'

def read_output(bot_id: int, process: subprocess.Popen):
    """قراءة مخرجات البوت بشكل مستمر"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.rstrip('\n\r')
                print(f"[Bot {bot_id}] {line}")
                # حفظ في قاعدة البيانات (آخر 5 سطور فقط للسرعة)
                db.add_log(bot_id, line[:500], "info")
    except Exception:
        pass

def monitor_process(bot_id: int, process: subprocess.Popen):
    """مراقبة العملية وإعادة التشغيل إذا لزم الأمر"""
    process.wait()
    
    with process_lock:
        if bot_id in active_processes:
            del active_processes[bot_id]
    
    exit_code = process.returncode
    db.update_bot(bot_id, status='crashed' if exit_code != 0 else 'stopped', pid=None)
    
    if exit_code != 0:
        db.add_log(bot_id, f"💥 البوت تعطل (رمز الخروج: {exit_code})", "error")
        
        # إعادة تشغيل تلقائي إذا كان مفعلاً
        bot_info = db.get_bot(bot_id)
        if bot_info and bot_info.get('auto_restart'):
            db.add_log(bot_id, "🔄 إعادة تشغيل تلقائي...", "warning")
            time.sleep(3)
            start_bot(bot_id)
    else:
        db.add_log(bot_id, "✅ البوت توقف بشكل طبيعي", "info")

def get_process_list() -> Dict[int, Dict]:
    """الحصول على قائمة بجميع العمليات النشطة وحالتها"""
    result = {}
    with process_lock:
        for bot_id, process in active_processes.items():
            status = 'running'
            if process.poll() is not None:
                status = 'crashed' if process.returncode != 0 else 'stopped'
            result[bot_id] = {
                'pid': process.pid,
                'status': status,
                'returncode': process.returncode
            }
    return result

def cleanup_all():
    """إيقاف جميع البوتات (للإغلاق النظيف)"""
    print("🧹 جاري إيقاف جميع البوتات...")
    bot_ids = list(active_processes.keys())
    for bot_id in bot_ids:
        stop_bot(bot_id)

def add_bot_from_token(name: str, token: str, description: str = "") -> Optional[int]:
    """إضافة بوت جديد باستخدام التوكن فقط"""
    # التحقق من صحة التوكن (فحص بسيط)
    if not token or len(token) < 10:
        return None
    
    bot_id = db.add_bot(
        name=name,
        token=token,
        bot_type='token',
        directory=f"bot_{name.lower().replace(' ', '_')[:20]}",
        description=description
    )
    
    # إنشاء مجلد البوت + حقن قاعدة البيانات
    ensure_dirs(bot_id)
    
    db.add_log(bot_id, f"✅ تم إضافة البوت {name} بنجاح", "success")
    db.add_log(bot_id, f"🗄️ تم إنشاء قاعدة بيانات مخصصة للبوت", "info")
    return bot_id

def add_bot_from_zip(name: str, token: str, zip_file_path: str, 
                     description: str = "") -> Optional[int]:
    """إضافة بوت جديد من ملف zip"""
    # التحقق من صحة التوكن
    if not token or len(token) < 10:
        return None
    
    # إضافة السجل أولاً للحصول على ID
    bot_id = db.add_bot(
        name=name,
        token=token,
        bot_type='zip',
        directory=f"bot_{name.lower().replace(' ', '_')[:20]}",
        description=description
    )
    
    # إنشاء مجلد البوت
    ensure_dirs(bot_id)
    
    # استخراج ملف zip
    entry_point = extract_zip_bot(zip_file_path, bot_id)
    if not entry_point:
        # فشل الاستخراج، نحذف البوت
        db.delete_bot(bot_id)
        return None
    
    # تحديث نقطة الدخول
    db.update_bot(bot_id, entry_point=entry_point)
    db.add_log(bot_id, f"✅ تم رفع واستخراج البوت (نقطة الدخول: {entry_point})", "success")
    
    return bot_id

# تسجيل إشارات الإيقاف النظيف
import atexit
atexit.register(cleanup_all)
