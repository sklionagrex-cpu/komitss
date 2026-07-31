import os
import hashlib
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)
os.makedirs('static/stories', exist_ok=True)

def get_db():
    return sqlite3.connect('komits.db')

def init_db():
    conn = sqlite3.connect('komits.db')
    c = conn.cursor()
    
    # ... (все старые таблицы) ...
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        avatar TEXT DEFAULT 'default.jpg',
        bio TEXT DEFAULT '',
        status TEXT DEFAULT 'online',
        custom_status TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        email TEXT DEFAULT '',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT,
        type TEXT DEFAULT 'text',
        visibility TEXT DEFAULT 'public'
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
        post_id INTEGER,
        user_id INTEGER,
        reaction TEXT DEFAULT '❤️',
        UNIQUE(post_id, user_id)
    )''')  # теперь лайки на постах, а не на комментариях
    c.execute('''CREATE TABLE IF NOT EXISTS saved_posts (
        user_id INTEGER,
        post_id INTEGER,
        created_at TEXT,
        PRIMARY KEY (user_id, post_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reposts (
        user_id INTEGER,
        post_id INTEGER,
        created_at TEXT,
        PRIMARY KEY (user_id, post_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT,
        expires_at TEXT,
        visibility TEXT DEFAULT 'public'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS story_views (
        user_id INTEGER,
        story_id INTEGER,
        viewed_at TEXT,
        PRIMARY KEY (user_id, story_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS filters (
        user_id INTEGER PRIMARY KEY,
        politics INTEGER DEFAULT 1,
        sports INTEGER DEFAULT 1,
        news INTEGER DEFAULT 1,
        humor INTEGER DEFAULT 1,
        games INTEGER DEFAULT 1,
        tech INTEGER DEFAULT 1,
        business INTEGER DEFAULT 1,
        music INTEGER DEFAULT 1,
        movies INTEGER DEFAULT 1,
        nsfw INTEGER DEFAULT 0,
        ads INTEGER DEFAULT 1
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

def get_stories(user_id):
    db = get_db()
    c = db.cursor()
    now = datetime.now().isoformat()
    # Истории друзей + свои за последние 24 часа
    stories = c.execute('''SELECT s.*, u.username, u.avatar FROM stories s
                           JOIN users u ON u.id = s.user_id
                           WHERE s.expires_at > ? AND (s.user_id IN (
                               SELECT friend_id FROM friends WHERE user_id = ? AND status = 'accepted'
                               UNION
                               SELECT user_id FROM friends WHERE friend_id = ? AND status = 'accepted'
                           ) OR s.user_id = ?)
                           ORDER BY s.created_at DESC''', (now, user_id, user_id, user_id)).fetchall()
    db.close()
    return stories

# ---- МАРШРУТЫ ----
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    # Посты для ленты (пока все, позже добавим алгоритмы)
    posts = c.execute('''SELECT p.*, u.username, u.avatar FROM posts p 
                         JOIN users u ON p.user_id = u.id 
                         ORDER BY p.created_at DESC''').fetchall()
    # Комментарии для каждого поста
    comments = {}
    for post in posts:
        comments[post[0]] = c.execute('''SELECT c.*, u.username, 
                               (SELECT COUNT(*) FROM likes WHERE post_id = ?) as likes_count 
                               FROM comments c JOIN users u ON c.user_id = u.id 
                               WHERE c.post_id = ? ORDER BY c.created_at''', (post[0], post[0])).fetchall()
    db.close()
    # Получаем истории
    stories = get_stories(session['user_id'])
    return render_template('index.html', 
                          posts=posts, 
                          comments=comments, 
                          stories=stories,
                          username=session.get('username', ''))

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    post_type = request.form.get('post_type', 'text')
    text = request.form.get('text', '')
    image = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
            image = filename
    visibility = request.form.get('visibility', 'public')
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO posts (user_id, text, image, created_at, type, visibility) VALUES (?, ?, ?, ?, ?, ?)',
              (session['user_id'], text, image, datetime.now().isoformat(), post_type, visibility))
    db.commit()
    db.close()
    flash('Пост опубликован!', 'success')
    return redirect(url_for('index'))

@app.route('/create_story', methods=['POST'])
def create_story():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    text = request.form.get('text', '')
    image = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/stories', filename))
            image = filename
    visibility = request.form.get('visibility', 'public')
    expires = datetime.now() + timedelta(hours=24)
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO stories (user_id, text, image, created_at, expires_at, visibility) VALUES (?, ?, ?, ?, ?, ?)',
              (session['user_id'], text, image, datetime.now().isoformat(), expires.isoformat(), visibility))
    db.commit()
    db.close()
    flash('История опубликована!', 'success')
    return redirect(url_for('index'))

@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    reaction = request.form.get('reaction', '❤️')
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO likes (post_id, user_id, reaction) VALUES (?, ?, ?)',
                  (post_id, session['user_id'], reaction))
    except:
        c.execute('UPDATE likes SET reaction = ? WHERE post_id = ? AND user_id = ?',
                  (reaction, post_id, session['user_id']))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/save_post/<int:post_id>', methods=['POST'])
def save_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO saved_posts (user_id, post_id, created_at) VALUES (?, ?, ?)',
                  (session['user_id'], post_id, datetime.now().isoformat()))
        flash('Сохранено!', 'success')
    except:
        c.execute('DELETE FROM saved_posts WHERE user_id = ? AND post_id = ?',
                  (session['user_id'], post_id))
        flash('Удалено из сохранённых', 'info')
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/repost_post/<int:post_id>', methods=['POST'])
def repost_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    try:
        c.execute('INSERT INTO reposts (user_id, post_id, created_at) VALUES (?, ?, ?)',
                  (session['user_id'], post_id, datetime.now().isoformat()))
        flash('Репостнут!', 'success')
    except:
        c.execute('DELETE FROM reposts WHERE user_id = ? AND post_id = ?',
                  (session['user_id'], post_id))
        flash('Репост отменён', 'info')
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/filter', methods=['POST'])
def update_filter():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    filters = ['politics', 'sports', 'news', 'humor', 'games', 'tech', 'business', 'music', 'movies', 'nsfw', 'ads']
    vals = {f: int(request.form.get(f, 0)) for f in filters}
    c.execute('''INSERT OR REPLACE INTO filters (user_id, politics, sports, news, humor, games, tech, business, music, movies, nsfw, ads)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (session['user_id'], vals['politics'], vals['sports'], vals['news'], vals['humor'], vals['games'], vals['tech'], vals['business'], vals['music'], vals['movies'], vals['nsfw'], vals['ads']))
    db.commit()
    db.close()
    flash('Фильтры обновлены!', 'success')
    return redirect(url_for('index'))

# Остальные маршруты (регистрация, логин, профиль и т.д.) остаются без изменений, но для краткости я их опускаю. В реальном проекте добавьте их сюда.
