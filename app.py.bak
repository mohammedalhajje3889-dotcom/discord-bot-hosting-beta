"""
🌐 app.py - تطبيق Flask الرئيسي
لوحة تحكم لاستضافة بوتات الديسكورد
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
    return dict(now=datetime.now)

# ========== إعدادات بسيطة ==========
# كلمة مرور بسيطة للوحة التحكم (يمكن تغييرها)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# ========== Middleware التحقق من الدخول ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('الرجاء تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== الصفحات الرئيسية ==========

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('✅ تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    session.pop('logged_in', None)
    flash('✅ تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

# ========== لوحة التحكم ==========

@app.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الرئيسية"""
    bots = db.get_all_bots()
    
    # تحديث حالة البوتات من المدير
    process_statuses = bm.get_process_list()
    for bot in bots:
        if bot['id'] in process_statuses:
            bot['current_status'] = process_statuses[bot['id']]['status']
        else:
            bot['current_status'] = bot.get('status', 'stopped')
    
    stats = {
        'total': len(bots),
        'running': sum(1 for b in bots if b.get('current_status') == 'running'),
        'stopped': sum(1 for b in bots if b.get('current_status') == 'stopped'),
        'crashed': sum(1 for b in bots if b.get('current_status') == 'crashed'),
    }
    
    return render_template('dashboard.html', bots=bots, stats=stats)

@app.route('/bot/<int:bot_id>')
@login_required
def bot_detail(bot_id):
    """صفحة تفاصيل البوت"""
    bot = db.get_bot(bot_id)
    if not bot:
        flash('❌ البوت غير موجود', 'error')
        return redirect(url_for('dashboard'))
    
    logs = db.get_logs(bot_id, limit=200)
    
    # جلب الإعدادات المخصصة
    settings = {
        'PREFIX': db.get_setting(bot_id, 'PREFIX', '')
    }
    
    # الحصول على الحالة الفعلية
    bot['current_status'] = bm.get_bot_status(bot_id)
    
    return render_template('bot_detail.html', bot=bot, logs=logs, settings=settings, db=db)

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
        
        # إضافة البوت
        bot_id = bm.add_bot_from_token(name, token, description)
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
        
        # حفظ الملف مؤقتاً
        temp_filename = f"{uuid.uuid4()}.zip"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        zip_file.save(temp_path)
        
        # إضافة البوت من zip
        bot_id = bm.add_bot_from_zip(name, token, temp_path, description)
        
        # حذف الملف المؤقت
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

@app.route('/bot/<int:bot_id>/start', methods=['POST'])
@login_required
def start_bot(bot_id):
    """تشغيل بوت"""
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
    # إيقاف البوت أولاً
    bm.stop_bot(bot_id)
    
    # حذف مجلد البوت
    bot_dir = os.path.join(bm.BOTS_DIR, str(bot_id))
    if os.path.exists(bot_dir):
        shutil.rmtree(bot_dir)
    
    # حذف من قاعدة البيانات
    db.delete_bot(bot_id)
    
    flash('🗑️ تم حذف البوت وجميع بياناته', 'info')
    return redirect(url_for('dashboard'))

@app.route('/bot/<int:bot_id>/settings', methods=['POST'])
@login_required
def update_bot_settings(bot_id):
    """تحديث إعدادات البوت"""
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
    
    # حفظ الإعدادات المخصصة
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
            # حفظ كلمة المرور الجديدة في متغير البيئة
            # ملاحظة: هذا مؤقت، للتخزين الدائم استخدم ملف .env
            global ADMIN_PASSWORD
            ADMIN_PASSWORD = new_password
            os.environ['ADMIN_PASSWORD'] = new_password
            flash('✅ تم تغيير كلمة المرور بنجاح (للمدة الحالية)', 'success')
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

# ========== API (للحصول على البيانات بشكل حي) ==========

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
    
    running = 0
    stopped = 0
    crashed = 0
    
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
║   البورت: {port}                                ║
║   {'='*37}  ║
║   📊 لوحة التحكم: /dashboard            ║
║   🔑 كلمة المرور: {ADMIN_PASSWORD}               ║
╚══════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
