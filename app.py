"""
🌐 app.py - تطبيق Flask الرئيسي
لوحة تحكم لاستضافة بوتات الديسكورد مع نظام مستخدمين
"""
import os
import sys
import json
import uuid
import shutil
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory

import database as db
import bot_manager as bm

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'discord-bot-hosting-secret-key-change-me')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB حد أقصى لرفع الملفات

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ========== سياق القوالب ==========
@app.context_processor
def inject_globals():
    return dict(now=datetime.now, session=session)

# ========== Middleware التحقق من الدخول ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('الرجاء تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or session.get('role') != 'admin':
            flash('❌ هذه الصفحة للمشرفين فقط', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ========== مساعدة ==========
def user_owns_bot(bot_id: int) -> bool:
    """التحقق من أن المستخدم يملك البوت أو هو مشرف"""
    if session.get('role') == 'admin':
        return True
    bot = db.get_bot(bot_id)
    if bot and bot['user_id'] == session.get('user_id'):
        return True
    return False

# ========== الصفحات الرئيسية ==========

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # التحقق من حساب المدير المدمج
        admin_pass = os.environ.get('ADMIN_PASSWORD', '61174271082')
        if username == 'admin' and password == admin_pass:
            # إنشاء حساب admin إذا ما موجود
            existing = db.get_user_by_username('admin')
            if not existing:
                db.add_user('admin', admin_pass, role='admin')
                user = db.get_user_by_username('admin')
            else:
                user = existing
                # تحديث كلمة المرور
                if user['password'] != admin_pass:
                    db.update_user(user['id'], password=admin_pass)
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('✅ مرحباً بك!', 'success')
            return redirect(url_for('dashboard'))
        
        # التحقق من المستخدمين العاديين
        user = db.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'✅ مرحباً {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """صفحة تسجيل مستخدم جديد"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()
        
        if not username or len(username) < 3:
            flash('❌ اسم المستخدم يجب أن يكون 3 أحرف على الأقل', 'error')
            return render_template('register.html')
        
        if not password or len(password) < 4:
            flash('❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل', 'error')
            return render_template('register.html', username=username)
        
        if password != confirm:
            flash('❌ كلمة المرور غير متطابقة', 'error')
            return render_template('register.html', username=username)
        
        user_id = db.add_user(username, password, role='user')
        if user_id:
            flash(f'✅ تم إنشاء الحساب بنجاح! مرحباً {username}', 'success')
            return redirect(url_for('login'))
        else:
            flash('❌ اسم المستخدم موجود مسبقاً', 'error')
            return render_template('register.html', username=username)
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    session.clear()
    flash('✅ تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

# ========== لوحة التحكم ==========

@app.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الرئيسية"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    if role == 'admin':
        bots = db.get_all_bots()  # كل البوتات
    else:
        bots = db.get_bots_by_user(user_id)  # بوتات المستخدم فقط
    
    # تحديث حالة البوتات
    process_statuses = bm.get_process_list()
    for bot in bots:
        if bot['id'] in process_statuses:
            bot['current_status'] = process_statuses[bot['id']]['status']
        else:
            bot['current_status'] = bot.get('status', 'stopped')
        # جلب اسم صاحب البوت
        if bot['user_id']:
            owner = db.get_user(bot['user_id'])
            bot['owner_name'] = owner['username'] if owner else 'مجهول'
        else:
            bot['owner_name'] = 'غير معروف'
    
    stats = {
        'total': len(bots),
        'running': sum(1 for b in bots if b.get('current_status') == 'running'),
        'stopped': sum(1 for b in bots if b.get('current_status') == 'stopped'),
        'crashed': sum(1 for b in bots if b.get('current_status') == 'crashed'),
    }
    
    users_count = db.count_users() if role == 'admin' else None
    
    return render_template('dashboard.html', bots=bots, stats=stats, 
                         users_count=users_count, role=role)

@app.route('/bot/<int:bot_id>')
@login_required
def bot_detail(bot_id):
    """صفحة تفاصيل البوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية الوصول لهذا البوت', 'error')
        return redirect(url_for('dashboard'))
    
    bot = db.get_bot(bot_id)
    if not bot:
        flash('❌ البوت غير موجود', 'error')
        return redirect(url_for('dashboard'))
    
    logs = db.get_logs(bot_id, limit=200)
    
    settings = {
        'PREFIX': db.get_setting(bot_id, 'PREFIX', '')
    }
    
    bot['current_status'] = bm.get_bot_status(bot_id)
    
    return render_template('bot_detail.html', bot=bot, logs=logs, settings=settings, db=db)

# ========== إدارة المستخدمين (للمشرف) ==========

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """صفحة إدارة المستخدمين"""
    users = db.get_all_users()
    users_with_bots = []
    for user in users:
        # إخفاء حساب الأدمن من القائمة
        if user['username'] == 'admin':
            continue
        bot_count = db.count_bots(user['id'])
        users_with_bots.append({**user, 'bot_count': bot_count})
    return render_template('admin_users.html', users=users_with_bots)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """حذف مستخدم"""
    if user_id == session.get('user_id'):
        flash('❌ لا يمكنك حذف حسابك', 'error')
        return redirect(url_for('admin_users'))
    
    user = db.get_user(user_id)
    if not user:
        flash('❌ المستخدم غير موجود', 'error')
        return redirect(url_for('admin_users'))
    
    # حذف جميع بوتات المستخدم
    bots = db.get_bots_by_user(user_id)
    for bot in bots:
        bm.stop_bot(bot['id'])
        bot_dir = os.path.join(bm.BOTS_DIR, str(bot['id']))
        if os.path.exists(bot_dir):
            shutil.rmtree(bot_dir)
        db.delete_bot(bot['id'])
    
    # حذف المستخدم
    conn = db.get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash(f'🗑️ تم حذف المستخدم {user["username"]} وجميع بوتاته', 'info')
    return redirect(url_for('admin_users'))

# ========== إدارة البوتات ==========

@app.route('/bot/add/token', methods=['GET', 'POST'])
@login_required
def add_bot_token():
    """إضافة بوت جديد باستخدام التوكن"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        token = request.form.get('token', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('❌ الرجاء إدخال اسم البوت', 'error')
            return render_template('add_bot_token.html', name=name, token=token)
        
        if not token:
            flash('❌ الرجاء إدخال توكن البوت', 'error')
            return render_template('add_bot_token.html', name=name, token=token)
        
        bot_id = bm.add_bot_from_token(name, token, description, user_id=session.get('user_id'))
        if bot_id:
            flash(f'✅ تم إضافة البوت {name} بنجاح', 'success')
            return redirect(url_for('bot_detail', bot_id=bot_id))
        else:
            flash('❌ فشل إضافة البوت. تأكد من صحة التوكن', 'error')
    
    return render_template('add_bot_token.html')

@app.route('/bot/add/zip', methods=['GET', 'POST'])
@login_required
def add_bot_zip():
    """إضافة بوت جديد من ملف zip"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        token = request.form.get('token', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('❌ الرجاء إدخال اسم البوت', 'error')
            return render_template('add_bot_zip.html')
        
        if not token:
            flash('❌ الرجاء إدخال توكن البوت', 'error')
            return render_template('add_bot_zip.html', name=name)
        
        if 'zip_file' not in request.files:
            flash('❌ الرجاء رفع ملف zip', 'error')
            return render_template('add_bot_zip.html', name=name, token=token)
        
        zip_file = request.files['zip_file']
        if zip_file.filename == '':
            flash('❌ لم يتم اختيار ملف', 'error')
            return render_template('add_bot_zip.html', name=name, token=token)
        
        if not zip_file.filename.endswith('.zip'):
            flash('❌ الرجاء رفع ملف بصيغة zip فقط', 'error')
            return render_template('add_bot_zip.html', name=name, token=token)
        
        # حفظ الملف بطريقة آمنة (بدون ERR_UPLOAD_FILE_CHANGED)
        temp_filename = f"{uuid.uuid4()}.zip"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        try:
            with open(temp_path, 'wb') as f:
                shutil.copyfileobj(zip_file, f)
        except Exception as e:
            flash(f'❌ فشل حفظ الملف: {e}', 'error')
            return render_template('add_bot_zip.html', name=name, token=token)
        
        bot_id = bm.add_bot_from_zip(name, token, temp_path, description, user_id=session.get('user_id'))
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        if bot_id:
            flash(f'✅ تم رفع وتثبيت البوت {name} بنجاح', 'success')
            return redirect(url_for('bot_detail', bot_id=bot_id))
        else:
            flash('❌ فشل رفع البوت. تأكد من وجود main.py في ملف zip', 'error')
    
    return render_template('add_bot_zip.html')

@app.route('/bot/<int:bot_id>/update', methods=['GET', 'POST'])
@login_required
def update_bot(bot_id):
    """تحديث بوت من ملف ZIP جديد (يحتفظ بالبيانات)"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    
    bot = db.get_bot(bot_id)
    if not bot:
        flash('❌ البوت غير موجود', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'zip_file' not in request.files:
            flash('❌ الرجاء رفع ملف zip', 'error')
            return render_template('bot_update.html', bot=bot)
        
        zip_file = request.files['zip_file']
        if zip_file.filename == '':
            flash('❌ لم يتم اختيار ملف', 'error')
            return render_template('bot_update.html', bot=bot)
        
        if not zip_file.filename.endswith('.zip'):
            flash('❌ الرجاء رفع ملف بصيغة zip فقط', 'error')
            return render_template('bot_update.html', bot=bot)
        
        # حفظ الملف بطريقة آمنة (بدون ERR_UPLOAD_FILE_CHANGED)
        temp_filename = f"update_{bot_id}_{uuid.uuid4()}.zip"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        try:
            with open(temp_path, 'wb') as f:
                shutil.copyfileobj(zip_file, f)
        except Exception as e:
            flash(f'❌ فشل حفظ الملف: {e}', 'error')
            return render_template('bot_update.html', bot=bot)
        
        success = bm.update_bot_from_zip(bot_id, temp_path)
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        if success:
            flash(f'✅ تم تحديث البوت {bot["name"]} بنجاح مع الاحتفاظ بالبيانات 📦', 'success')
            return redirect(url_for('bot_detail', bot_id=bot_id))
        else:
            flash('❌ فشل تحديث البوت', 'error')
    
    return render_template('bot_update.html', bot=bot)

@app.route('/bot/<int:bot_id>/start', methods=['POST'])
@login_required
def start_bot(bot_id):
    """تشغيل بوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    success = bm.start_bot(bot_id)
    if success:
        flash('✅ تم تشغيل البوت بنجاح', 'success')
    else:
        flash('❌ فشل تشغيل البوت', 'error')
    return redirect(url_for('bot_detail', bot_id=bot_id))

@app.route('/bot/<int:bot_id>/stop', methods=['POST'])
@login_required
def stop_bot(bot_id):
    """إيقاف بوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    success = bm.stop_bot(bot_id)
    if success:
        flash('✅ تم إيقاف البوت بنجاح', 'info')
    else:
        flash('❌ فشل إيقاف البوت', 'error')
    return redirect(url_for('bot_detail', bot_id=bot_id))

@app.route('/bot/<int:bot_id>/restart', methods=['POST'])
@login_required
def restart_bot(bot_id):
    """إعادة تشغيل بوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    success = bm.restart_bot(bot_id)
    if success:
        flash('✅ تم إعادة تشغيل البوت بنجاح', 'success')
    else:
        flash('❌ فشل إعادة تشغيل البوت', 'error')
    return redirect(url_for('bot_detail', bot_id=bot_id))

@app.route('/bot/<int:bot_id>/delete', methods=['POST'])
@login_required
def delete_bot(bot_id):
    """حذف بوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    
    bm.stop_bot(bot_id)
    
    bot_dir = os.path.join(bm.BOTS_DIR, str(bot_id))
    if os.path.exists(bot_dir):
        shutil.rmtree(bot_dir)
    
    db.delete_bot(bot_id)
    
    flash('🗑️ تم حذف البوت وجميع بياناته', 'info')
    return redirect(url_for('dashboard'))

@app.route('/bot/<int:bot_id>/settings', methods=['POST'])
@login_required
def update_bot_settings(bot_id):
    """تحديث إعدادات البوت"""
    if not user_owns_bot(bot_id):
        flash('❌ ليس لديك صلاحية', 'error')
        return redirect(url_for('dashboard'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    auto_restart = 1 if request.form.get('auto_restart') else 0
    prefix = request.form.get('prefix', '').strip()
    
    updates = {}
    if name:
        updates['name'] = name
    updates['description'] = description
    updates['auto_restart'] = auto_restart
    
    db.update_bot(bot_id, **updates)
    
    if prefix:
        db.set_setting(bot_id, 'PREFIX', prefix)
    else:
        db.set_setting(bot_id, 'PREFIX', '')
    
    flash('✅ تم تحديث الإعدادات', 'success')
    return redirect(url_for('bot_detail', bot_id=bot_id))

# ========== الإعدادات ==========

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """صفحة الإعدادات"""
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if new_password and new_password == confirm_password:
            user_id = session.get('user_id')
            db.update_user(user_id, password=new_password)
            flash('✅ تم تغيير كلمة المرور بنجاح', 'success')
        elif new_password != confirm_password:
            flash('❌ كلمة المرور غير متطابقة', 'error')
        else:
            flash('❌ الرجاء إدخال كلمة مرور جديدة', 'error')
        
        return redirect(url_for('settings'))
    
    try:
        import discord as discord_module
        discord_ver = discord_module.__version__
    except:
        discord_ver = 'غير مثبت'
    
    try:
        import flask as flask_module
        flask_ver = flask_module.__version__
    except:
        flask_ver = 'غير معروف'
    
    return render_template('settings.html', 
                         sys=sys,
                         flask_version=flask_ver,
                         discord_version=discord_ver)

# ========== API ==========

@app.route('/api/bot/<int:bot_id>/status')
def api_bot_status(bot_id):
    """API للحصول على حالة البوت"""
    bot = db.get_bot(bot_id)
    if not bot:
        return jsonify({'error': 'Bot not found'}), 404
    
    status = bm.get_bot_status(bot_id)
    logs = db.get_logs(bot_id, limit=10)
    
    return jsonify({
        'id': bot_id,
        'name': bot['name'],
        'status': status,
        'logs': [{'message': l['message'], 'level': l['level'], 'timestamp': l['timestamp']} for l in logs]
    })

@app.route('/api/bot/<int:bot_id>/logs/<int:count>')
def api_bot_logs(bot_id, count=50):
    """API للحصول على آخر اللوجات"""
    logs = db.get_logs(bot_id, limit=min(count, 500))
    return jsonify({
        'logs': [{'message': l['message'], 'level': l['level'], 'timestamp': l['timestamp']} for l in logs]
    })

@app.route('/api/stats')
def api_stats():
    """API للحصول على إحصائيات"""
    bots = db.get_all_bots()
    process_statuses = bm.get_process_list()
    
    running = stopped = crashed = 0
    for bot in bots:
        status = process_statuses.get(bot['id'], {}).get('status', bot.get('status', 'stopped'))
        if status == 'running':
            running += 1
        elif status == 'crashed':
            crashed += 1
        else:
            stopped += 1
    
    return jsonify({
        'total': len(bots),
        'running': running,
        'stopped': stopped,
        'crashed': crashed
    })

# ========== التشغيل ==========

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print(f"""
╔══════════════════════════════════════════╗
║   🚀 Discord Bot Hosting Panel          ║
║   {'='*37}  ║
║   الرابط: http://localhost:{port}          ║
║   {'='*37}  ║
║   📊 لوحة التحكم: /dashboard            ║
║   👥 تسجيل حساب: /register              ║
╚══════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
