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
    
    # Таблица пользователей
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
    
    # Таблица постов (добавлены type, visibility, likes_count, comments_count, reposts_count)
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT,
        type TEXT DEFAULT 'text',
        visibility TEXT DEFAULT 'public',
        likes_count INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        reposts_count INTEGER DEFAULT 0
    )''')
    
    # Таблица комментариев
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT
    )''')
    
    # Таблица лайков (на посты, с реакциями)
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        reaction TEXT DEFAULT '❤️',
        UNIQUE(post_id, user_id)
    )''')
    
    # Сохранённые посты
    c.execute('''CREATE TABLE IF NOT EXISTS saved_posts (
        user_id INTEGER,
        post_id INTEGER,
        created_at TEXT,
        PRIMARY KEY (user_id, post_id)
    )''')
    
    # Репосты
    c.execute('''CREATE TABLE IF NOT EXISTS reposts (
        user_id INTEGER,
        post_id INTEGER,
        created_at TEXT,
        PRIMARY KEY (user_id, post_id)
    )''')
    
    # Истории
    c.execute('''CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT,
        expires_at TEXT,
        visibility TEXT DEFAULT 'public'
    )''')
    
    # Просмотры историй
    c.execute('''CREATE TABLE IF NOT EXISTS story_views (
        user_id INTEGER,
        story_id INTEGER,
        viewed_at TEXT,
        PRIMARY KEY (user_id, story_id)
    )''')
    
    # Фильтры контента
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
    
    # Друзья (оставляем как было)
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user_id INTEGER,
        friend_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        PRIMARY KEY (user_id, friend_id)
    )''')
    
    # Чаты (1-1)
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        created_at TEXT
    )''')
    
    # Сообщения в чатах
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        sender_id INTEGER,
        text TEXT,
        image TEXT,
        timestamp TEXT,
        is_read INTEGER DEFAULT 0
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
    posts = c.execute('''SELECT p.*, u.username, u.avatar FROM posts p 
                         JOIN users u ON p.user_id = u.id 
                         ORDER BY p.created_at DESC''').fetchall()
    comments = {}
    for post in posts:
        comments[post[0]] = c.execute('''SELECT c.*, u.username FROM comments c 
                                         JOIN users u ON c.user_id = u.id 
                                         WHERE c.post_id = ? ORDER BY c.created_at''', (post[0],)).fetchall()
    db.close()
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
    # Обновляем счетчик комментариев в посте
    c.execute('UPDATE posts SET comments_count = comments_count + 1 WHERE id = ?', (post_id,))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

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
        c.execute('UPDATE posts SET likes_count = likes_count + 1 WHERE id = ?', (post_id,))
    except sqlite3.IntegrityError:
        c.execute('UPDATE likes SET reaction = ? WHERE post_id = ? AND user_id = ?',
                  (reaction, post_id, session['user_id']))
        # Если уже лайкал, не увеличиваем счетчик
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
    except sqlite3.IntegrityError:
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
        c.execute('UPDATE posts SET reposts_count = reposts_count + 1 WHERE id = ?', (post_id,))
        flash('Репостнут!', 'success')
    except sqlite3.IntegrityError:
        c.execute('DELETE FROM reposts WHERE user_id = ? AND post_id = ?',
                  (session['user_id'], post_id))
        c.execute('UPDATE posts SET reposts_count = reposts_count - 1 WHERE id = ?', (post_id,))
        flash('Репост отменён', 'info')
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

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

@app.route('/filter', methods=['POST'])
def update_filter():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    categories = ['politics', 'sports', 'news', 'humor', 'games', 'tech', 'business', 'music', 'movies', 'nsfw', 'ads']
    vals = {cat: int(request.form.get(cat, 0)) for cat in categories}
    c.execute('''INSERT OR REPLACE INTO filters (user_id, politics, sports, news, humor, games, tech, business, music, movies, nsfw, ads)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (session['user_id'], vals['politics'], vals['sports'], vals['news'], vals['humor'], vals['games'], vals['tech'], vals['business'], vals['music'], vals['movies'], vals['nsfw'], vals['ads']))
    db.commit()
    db.close()
    flash('Фильтры обновлены!', 'success')
    return redirect(url_for('index'))

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
        except sqlite3.IntegrityError:
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
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    friends_count = c.execute('SELECT COUNT(*) FROM friends WHERE (user_id=? OR friend_id=?) AND status="accepted"',
                             (session['user_id'], session['user_id'])).fetchone()[0]
    likes_count = c.execute('SELECT COUNT(*) FROM likes WHERE user_id=?', (session['user_id'],)).fetchone()[0]
    posts_count = c.execute('SELECT COUNT(*) FROM posts WHERE user_id=?', (session['user_id'],)).fetchone()[0]
    db.close()
    return render_template('profile.html', user=user, friends_count=friends_count,
                          likes_count=likes_count, posts_count=posts_count, username=session.get('username', ''))

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
    except sqlite3.IntegrityError:
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
