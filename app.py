import os
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)
os.makedirs('static/banners', exist_ok=True)

def get_db():
    return sqlite3.connect('komits.db')

def init_db():
    conn = sqlite3.connect('komits.db')
    c = conn.cursor()
    
    # Основные таблицы (уже были)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        avatar TEXT DEFAULT 'default.jpg',
        banner TEXT DEFAULT '',
        bio TEXT DEFAULT '',
        status TEXT DEFAULT 'online',
        custom_status TEXT DEFAULT '',
        status_expires TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        birth_date TEXT DEFAULT '',
        country TEXT DEFAULT '',
        city TEXT DEFAULT '',
        timezone TEXT DEFAULT 'UTC',
        language TEXT DEFAULT 'ru',
        premium INTEGER DEFAULT 0,
        verified INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        comment_id INTEGER,
        user_id INTEGER,
        UNIQUE(comment_id, user_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        sender_id INTEGER,
        text TEXT,
        image TEXT,
        timestamp TEXT,
        is_read INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user_id INTEGER,
        friend_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        PRIMARY KEY (user_id, friend_id)
    )''')
    
    # НОВЫЕ ТАБЛИЦЫ ДЛЯ ПРОФИЛЯ
    c.execute('''CREATE TABLE IF NOT EXISTS social_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        platform TEXT,
        url TEXT,
        UNIQUE(user_id, platform)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        icon TEXT,
        unlocked_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        ip TEXT,
        last_seen TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS privacy_settings (
        user_id INTEGER PRIMARY KEY,
        show_phone INTEGER DEFAULT 0,
        show_email INTEGER DEFAULT 0,
        show_bio INTEGER DEFAULT 1,
        show_online INTEGER DEFAULT 1,
        show_last_seen INTEGER DEFAULT 1,
        show_birthday INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS notification_settings (
        user_id INTEGER PRIMARY KEY,
        sound INTEGER DEFAULT 1,
        vibration INTEGER DEFAULT 1,
        push INTEGER DEFAULT 1,
        email INTEGER DEFAULT 1,
        sms INTEGER DEFAULT 0,
        mentions INTEGER DEFAULT 1,
        reactions INTEGER DEFAULT 1,
        replies INTEGER DEFAULT 1,
        pms INTEGER DEFAULT 1,
        groups INTEGER DEFAULT 1,
        channels INTEGER DEFAULT 1
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS theme_settings (
        user_id INTEGER PRIMARY KEY,
        theme TEXT DEFAULT 'dark',
        accent_color TEXT DEFAULT '#7c5cbf',
        font_size INTEGER DEFAULT 16,
        compact_mode INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS blocked_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        blocked_id INTEGER,
        reason TEXT,
        created_at TEXT,
        UNIQUE(user_id, blocked_id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ---- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----
def get_user(user_id):
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    return user

def get_privacy(user_id):
    db = get_db()
    c = db.cursor()
    privacy = c.execute('SELECT * FROM privacy_settings WHERE user_id = ?', (user_id,)).fetchone()
    db.close()
    if not privacy:
        # Создаём настройки по умолчанию
        db = get_db()
        c = db.cursor()
        c.execute('''INSERT INTO privacy_settings (user_id, show_phone, show_email, show_bio, show_online, show_last_seen, show_birthday)
                     VALUES (?, 0, 0, 1, 1, 1, 0)''', (user_id,))
        db.commit()
        db.close()
        return (user_id, 0, 0, 1, 1, 1, 0)
    return privacy

def get_notifications(user_id):
    db = get_db()
    c = db.cursor()
    notif = c.execute('SELECT * FROM notification_settings WHERE user_id = ?', (user_id,)).fetchone()
    db.close()
    if not notif:
        db = get_db()
        c = db.cursor()
        c.execute('''INSERT INTO notification_settings (user_id) VALUES (?)''', (user_id,))
        db.commit()
        db.close()
        return (user_id, 1,1,1,1,0,1,1,1,1,1,1)
    return notif

def get_theme(user_id):
    db = get_db()
    c = db.cursor()
    theme = c.execute('SELECT * FROM theme_settings WHERE user_id = ?', (user_id,)).fetchone()
    db.close()
    if not theme:
        db = get_db()
        c = db.cursor()
        c.execute('''INSERT INTO theme_settings (user_id, theme, accent_color, font_size, compact_mode)
                     VALUES (?, 'dark', '#7c5cbf', 16, 0)''', (user_id,))
        db.commit()
        db.close()
        return (user_id, 'dark', '#7c5cbf', 16, 0)
    return theme

# ---- МАРШРУТЫ ----
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    posts = c.execute('''SELECT p.*, u.username, u.avatar FROM posts p 
                         JOIN users u ON p.user_id = u.id 
                         ORDER BY p.created_at DESC''').fetchall()
    comments = {}
    for post in posts:
        comments[post[0]] = c.execute('''SELECT c.*, u.username, 
                               (SELECT COUNT(*) FROM likes WHERE comment_id = c.id) as likes_count 
                               FROM comments c JOIN users u ON c.user_id = u.id 
                               WHERE c.post_id = ?''', (post[0],)).fetchall()
    db.close()
    return render_template('index.html', posts=posts, comments=comments, username=session.get('username', ''))

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    text = request.form.get('text', '')
    image = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
            image = filename
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO posts (user_id, text, image, created_at) VALUES (?, ?, ?, ?)',
              (session['user_id'], text, image, datetime.now().isoformat()))
    db.commit()
    db.close()
    flash('Пост опубликован!', 'success')
    return redirect(url_for('index'))

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    text = request.form.get('text', '')
    image = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
            image = filename
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO comments (post_id, user_id, text, image, created_at) VALUES (?, ?, ?, ?, ?)',
              (post_id, session['user_id'], text, image, datetime.now().isoformat()))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/like_comment/<int:comment_id>')
def like_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO likes (comment_id, user_id) VALUES (?, ?)', (comment_id, session['user_id']))
        db.commit()
    except:
        c.execute('DELETE FROM likes WHERE comment_id=? AND user_id=?', (comment_id, session['user_id']))
        db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/best_commentator')
def best_commentator():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    data = c.execute('''SELECT u.username, u.avatar, COUNT(c.id) as comments_count,
                               (SELECT COUNT(*) FROM likes WHERE comment_id = c.id) as total_likes
                        FROM users u
                        JOIN comments c ON c.user_id = u.id
                        GROUP BY u.id
                        ORDER BY comments_count DESC LIMIT 10''').fetchall()
    db.close()
    return render_template('best_commentator.html', commentator=data)

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    chat_list = c.execute('''SELECT c.*, 
                              (SELECT COUNT(*) FROM messages WHERE chat_id = c.id AND is_read = 0 AND sender_id != ?) as unread
                              FROM chats c
                              WHERE c.user1_id = ? OR c.user2_id = ?
                              ORDER BY c.created_at DESC''', 
                         (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    db.close()
    return render_template('chats.html', chats=chat_list, username=session.get('username', ''))

@app.route('/chat/<int:chat_id>')
def chat_view(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    messages = c.execute('''SELECT m.*, u.username, u.avatar FROM messages m
                            JOIN users u ON m.sender_id = u.id
                            WHERE m.chat_id = ? ORDER BY m.timestamp ASC''', (chat_id,)).fetchall()
    c.execute('UPDATE messages SET is_read = 1 WHERE chat_id = ? AND sender_id != ?', 
              (chat_id, session['user_id']))
    db.commit()
    chat = c.execute('SELECT * FROM chats WHERE id = ?', (chat_id,)).fetchone()
    other_user_id = chat[1] if chat[1] != session['user_id'] else chat[2]
    other_user = c.execute('SELECT username, avatar FROM users WHERE id = ?', (other_user_id,)).fetchone()
    db.close()
    return render_template('chat_view.html', messages=messages, chat=chat, other_user=other_user,
                          chat_id=chat_id, username=session.get('username', ''))

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    chat_id = request.form.get('chat_id')
    text = request.form.get('text', '')
    image = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
            image = filename
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO messages (chat_id, sender_id, text, image, timestamp) VALUES (?, ?, ?, ?, ?)',
              (chat_id, session['user_id'], text, image, datetime.now().isoformat()))
    db.commit()
    db.close()
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/create_chat', methods=['POST'])
def create_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    friend_id = request.form.get('friend_id')
    if not friend_id:
        flash('Выберите пользователя', 'error')
        return redirect(url_for('friends'))
    
    db = get_db()
    c = db.cursor()
    existing = c.execute('''SELECT id FROM chats 
                            WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)''',
                         (session['user_id'], friend_id, friend_id, session['user_id'])).fetchone()
    if existing:
        db.close()
        return redirect(url_for('chat_view', chat_id=existing[0]))
    
    c.execute('INSERT INTO chats (user1_id, user2_id, created_at) VALUES (?, ?, ?)',
              (session['user_id'], friend_id, datetime.now().isoformat()))
    chat_id = c.lastrowid
    db.commit()
    db.close()
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/friends')
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    friends_list = c.execute('''SELECT u.id, u.username, u.avatar, u.bio FROM friends f 
                               JOIN users u ON u.id = f.friend_id 
                               WHERE f.user_id=? AND f.status="accepted" 
                               UNION 
                               SELECT u.id, u.username, u.avatar, u.bio FROM friends f 
                               JOIN users u ON u.id = f.user_id 
                               WHERE f.friend_id=? AND f.status="accepted"''', 
                            (session['user_id'], session['user_id'])).fetchall()
    db.close()
    return render_template('friends.html', friends=friends_list, username=session.get('username', ''))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    friend_id = request.form.get('friend_id')
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO friends (user_id, friend_id, status, created_at) VALUES (?, ?, ?, ?)',
                  (session['user_id'], friend_id, 'pending', datetime.now().isoformat()))
        flash('Запрос отправлен!', 'success')
    except:
        flash('Уже в друзьях', 'error')
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('friends'))

@app.route('/search_users')
def search_users():
    if 'user_id' not in session:
        return jsonify([])
    query = request.args.get('q', '')
    db = get_db()
    c = db.cursor()
    users = c.execute('SELECT id, username, avatar FROM users WHERE username LIKE ? LIMIT 10', (f'%{query}%',)).fetchall()
    db.close()
    return jsonify([{'id': u[0], 'username': u[1], 'avatar': u[2]} for u in users])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        db = get_db()
        c = db.cursor()
        try:
            c.execute('INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)',
                      (username, password, datetime.now().isoformat()))
            db.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except:
            flash('Пользователь уже существует!', 'error')
        db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        db = get_db()
        c = db.cursor()
        user = c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password)).fetchone()
        db.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        flash('Неверный логин или пароль!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = get_user(session['user_id'])
    privacy = get_privacy(session['user_id'])
    notif = get_notifications(session['user_id'])
    theme = get_theme(session['user_id'])
    
    db = get_db()
    c = db.cursor()
    friends_count = c.execute('SELECT COUNT(*) FROM friends WHERE (user_id=? OR friend_id=?) AND status="accepted"', 
                             (session['user_id'], session['user_id'])).fetchone()[0]
    likes_count = c.execute('SELECT COUNT(*) FROM likes l JOIN comments c ON c.id=l.comment_id WHERE c.user_id=?', 
                           (session['user_id'],)).fetchone()[0]
    posts_count = c.execute('SELECT COUNT(*) FROM posts WHERE user_id=?', (session['user_id'],)).fetchone()[0]
    social_links = c.execute('SELECT * FROM social_links WHERE user_id=?', (session['user_id'],)).fetchall()
    achievements = c.execute('SELECT * FROM achievements WHERE user_id=? ORDER BY unlocked_at DESC', (session['user_id'],)).fetchall()
    devices = c.execute('SELECT * FROM devices WHERE user_id=? ORDER BY last_seen DESC', (session['user_id'],)).fetchall()
    blocked = c.execute('SELECT u.username FROM blocked_users b JOIN users u ON u.id = b.blocked_id WHERE b.user_id=?', (session['user_id'],)).fetchall()
    db.close()
    
    return render_template('profile.html', 
                          user=user, 
                          privacy=privacy, 
                          notif=notif, 
                          theme=theme,
                          friends_count=friends_count,
                          likes_count=likes_count,
                          posts_count=posts_count,
                          social_links=social_links,
                          achievements=achievements,
                          devices=devices,
                          blocked=blocked,
                          username=session.get('username', ''))

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename:
            filename = f"avatar_{session['user_id']}.jpg"
            file.save(os.path.join('static/avatars', filename))
            db = get_db()
            c = db.cursor()
            c.execute('UPDATE users SET avatar=? WHERE id=?', (filename, session['user_id']))
            db.commit()
            db.close()
            flash('Аватар обновлён!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_banner', methods=['POST'])
def update_banner():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'banner' in request.files:
        file = request.files['banner']
        if file.filename:
            filename = f"banner_{session['user_id']}.jpg"
            file.save(os.path.join('static/banners', filename))
            db = get_db()
            c = db.cursor()
            c.execute('UPDATE users SET banner=? WHERE id=?', (filename, session['user_id']))
            db.commit()
            db.close()
            flash('Обложка обновлена!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    bio = request.form.get('bio', '')
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    birth_date = request.form.get('birth_date', '')
    country = request.form.get('country', '')
    city = request.form.get('city', '')
    timezone = request.form.get('timezone', 'UTC')
    language = request.form.get('language', 'ru')
    db = get_db()
    c = db.cursor()
    c.execute('''UPDATE users SET bio=?, phone=?, email=?, birth_date=?, country=?, city=?, timezone=?, language=?
                 WHERE id=?''', (bio, phone, email, birth_date, country, city, timezone, language, session['user_id']))
    db.commit()
    db.close()
    flash('Профиль обновлён!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    status = request.form.get('status', 'online')
    custom_status = request.form.get('custom_status', '')
    expires = request.form.get('expires', '')
    db = get_db()
    c = db.cursor()
    c.execute('UPDATE users SET status=?, custom_status=?, status_expires=? WHERE id=?',
              (status, custom_status, expires, session['user_id']))
    db.commit()
    db.close()
    flash('Статус обновлён!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_privacy', methods=['POST'])
def update_privacy():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    show_phone = int(request.form.get('show_phone', 0))
    show_email = int(request.form.get('show_email', 0))
    show_bio = int(request.form.get('show_bio', 1))
    show_online = int(request.form.get('show_online', 1))
    show_last_seen = int(request.form.get('show_last_seen', 1))
    show_birthday = int(request.form.get('show_birthday', 0))
    db = get_db()
    c = db.cursor()
    c.execute('''UPDATE privacy_settings SET show_phone=?, show_email=?, show_bio=?, show_online=?, show_last_seen=?, show_birthday=?
                 WHERE user_id=?''', (show_phone, show_email, show_bio, show_online, show_last_seen, show_birthday, session['user_id']))
    db.commit()
    db.close()
    flash('Настройки приватности сохранены!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_notifications', methods=['POST'])
def update_notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    sound = int(request.form.get('sound', 1))
    vibration = int(request.form.get('vibration', 1))
    push = int(request.form.get('push', 1))
    email = int(request.form.get('email', 1))
    sms = int(request.form.get('sms', 0))
    mentions = int(request.form.get('mentions', 1))
    reactions = int(request.form.get('reactions', 1))
    replies = int(request.form.get('replies', 1))
    pms = int(request.form.get('pms', 1))
    groups = int(request.form.get('groups', 1))
    channels = int(request.form.get('channels', 1))
    db = get_db()
    c = db.cursor()
    c.execute('''UPDATE notification_settings SET sound=?, vibration=?, push=?, email=?, sms=?, mentions=?, reactions=?, replies=?, pms=?, groups=?, channels=?
                 WHERE user_id=?''', (sound, vibration, push, email, sms, mentions, reactions, replies, pms, groups, channels, session['user_id']))
    db.commit()
    db.close()
    flash('Настройки уведомлений сохранены!', 'success')
    return redirect(url_for('profile'))

@app.route('/update_theme', methods=['POST'])
def update_theme():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = request.form.get('theme', 'dark')
    accent = request.form.get('accent_color', '#7c5cbf')
    font_size = int(request.form.get('font_size', 16))
    compact = int(request.form.get('compact_mode', 0))
    db = get_db()
    c = db.cursor()
    c.execute('''UPDATE theme_settings SET theme=?, accent_color=?, font_size=?, compact_mode=? WHERE user_id=?''',
              (theme, accent, font_size, compact, session['user_id']))
    db.commit()
    db.close()
    flash('Настройки темы сохранены!', 'success')
    return redirect(url_for('profile'))

@app.route('/add_social_link', methods=['POST'])
def add_social_link():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = request.form.get('platform')
    url = request.form.get('url')
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO social_links (user_id, platform, url) VALUES (?, ?, ?)',
                  (session['user_id'], platform, url))
        db.commit()
        flash('Социальная сеть добавлена!', 'success')
    except:
        flash('Такая социальная сеть уже добавлена', 'error')
    db.close()
    return redirect(url_for('profile'))

@app.route('/remove_social_link/<int:link_id>', methods=['POST'])
def remove_social_link(link_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    c.execute('DELETE FROM social_links WHERE id=? AND user_id=?', (link_id, session['user_id']))
    db.commit()
    db.close()
    flash('Ссылка удалена', 'success')
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    old = request.form.get('old_password')
    new = request.form.get('new_password')
    confirm = request.form.get('confirm_password')
    if new != confirm:
        flash('Пароли не совпадают', 'error')
        return redirect(url_for('profile'))
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT password FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if hashlib.sha256(old.encode()).hexdigest() != user[0]:
        flash('Неверный старый пароль', 'error')
        db.close()
        return redirect(url_for('profile'))
    c.execute('UPDATE users SET password=? WHERE id=?', (hashlib.sha256(new.encode()).hexdigest(), session['user_id']))
    db.commit()
    db.close()
    flash('Пароль изменён!', 'success')
    return redirect(url_for('profile'))

@app.route('/block_user', methods=['POST'])
def block_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    blocked_id = request.form.get('blocked_id')
    reason = request.form.get('reason', '')
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO blocked_users (user_id, blocked_id, reason, created_at) VALUES (?, ?, ?, ?)',
                  (session['user_id'], blocked_id, reason, datetime.now().isoformat()))
        db.commit()
        flash('Пользователь заблокирован', 'success')
    except:
        flash('Уже заблокирован', 'error')
    db.close()
    return redirect(url_for('profile'))

@app.route('/unblock_user/<int:blocked_id>', methods=['POST'])
def unblock_user(blocked_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    c.execute('DELETE FROM blocked_users WHERE user_id=? AND blocked_id=?', (session['user_id'], blocked_id))
    db.commit()
    db.close()
    flash('Пользователь разблокирован', 'success')
    return redirect(url_for('profile'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # В реальном проекте нужно подтверждение
    db = get_db()
    c = db.cursor()
    # Удаляем все данные пользователя
    c.execute('DELETE FROM users WHERE id=?', (session['user_id'],))
    c.execute('DELETE FROM posts WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM comments WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM likes WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM friends WHERE user_id=? OR friend_id=?', (session['user_id'], session['user_id']))
    c.execute('DELETE FROM chats WHERE user1_id=? OR user2_id=?', (session['user_id'], session['user_id']))
    c.execute('DELETE FROM messages WHERE sender_id=?', (session['user_id'],))
    c.execute('DELETE FROM social_links WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM achievements WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM devices WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM privacy_settings WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM notification_settings WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM theme_settings WHERE user_id=?', (session['user_id'],))
    c.execute('DELETE FROM blocked_users WHERE user_id=?', (session['user_id'],))
    db.commit()
    db.close()
    session.clear()
    flash('Аккаунт удалён', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
