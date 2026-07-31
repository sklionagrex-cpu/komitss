import os
import hashlib
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)

# Получаем URL базы данных из переменных окружения Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Подключение к PostgreSQL"""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        # Если нет переменной, используем SQLite для локальной разработки
        import sqlite3
        return sqlite3.connect('komits.db')

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Проверяем, PostgreSQL или SQLite
    is_postgres = DATABASE_URL is not None
    
    if is_postgres:
        # PostgreSQL
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            avatar TEXT DEFAULT 'default.jpg',
            bio TEXT DEFAULT '',
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            text TEXT,
            image TEXT,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            post_id INTEGER,
            user_id INTEGER,
            text TEXT,
            image TEXT,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS likes (
            id SERIAL PRIMARY KEY,
            comment_id INTEGER,
            user_id INTEGER,
            UNIQUE(comment_id, user_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            name TEXT,
            is_group INTEGER DEFAULT 0,
            is_community INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_by INTEGER DEFAULT 0,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS chat_members (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member',
            joined_at TEXT,
            UNIQUE(chat_id, user_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER,
            sender_id INTEGER,
            text TEXT,
            image TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS friends (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            UNIQUE(user_id, friend_id)
        )''')
    else:
        # SQLite
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            avatar TEXT DEFAULT 'default.jpg',
            bio TEXT DEFAULT '',
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
            name TEXT,
            is_group INTEGER DEFAULT 0,
            is_community INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_by INTEGER DEFAULT 0,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS chat_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member',
            joined_at TEXT,
            UNIQUE(chat_id, user_id)
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            UNIQUE(user_id, friend_id)
        )''')
    
    conn.commit()
    conn.close()

# Инициализация базы данных при запуске
init_db()

def execute_query(query, params=None, fetch=False):
    """Выполнение запроса с автоматическим закрытием соединения"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        if fetch:
            result = c.fetchall()
        else:
            conn.commit()
            result = True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
    return result

def fetch_all(query, params=None):
    """Получение всех строк"""
    conn = get_db_connection()
    c = conn.cursor()
    if params:
        c.execute(query, params)
    else:
        c.execute(query)
    result = c.fetchall()
    conn.close()
    return result

def fetch_one(query, params=None):
    """Получение одной строки"""
    conn = get_db_connection()
    c = conn.cursor()
    if params:
        c.execute(query, params)
    else:
        c.execute(query)
    result = c.fetchone()
    conn.close()
    return result

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    posts = fetch_all('''SELECT p.*, u.username, u.avatar FROM posts p 
                         JOIN users u ON p.user_id = u.id 
                         ORDER BY p.created_at DESC''')
    
    comments_dict = {}
    for post in posts:
        comments = fetch_all('''SELECT c.*, u.username, 
                               (SELECT COUNT(*) FROM likes WHERE comment_id = c.id) as likes_count 
                               FROM comments c 
                               JOIN users u ON c.user_id = u.id 
                               WHERE c.post_id = %s''', (post[0],))
        comments_dict[post[0]] = comments if comments else []
    
    return render_template('index.html', posts=posts, comments_dict=comments_dict, 
                          username=session.get('username', ''))

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
    
    execute_query('INSERT INTO posts (user_id, text, image, created_at) VALUES (%s, %s, %s, %s)',
                  (session['user_id'], text, image, datetime.now().isoformat()))
    
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
    
    execute_query('INSERT INTO comments (post_id, user_id, text, image, created_at) VALUES (%s, %s, %s, %s, %s)',
                  (post_id, session['user_id'], text, image, datetime.now().isoformat()))
    
    return redirect(url_for('index'))

@app.route('/like_comment/<int:comment_id>')
def like_comment(comment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        execute_query('INSERT INTO likes (comment_id, user_id) VALUES (%s, %s)', 
                      (comment_id, session['user_id']))
    except:
        execute_query('DELETE FROM likes WHERE comment_id=%s AND user_id=%s', 
                      (comment_id, session['user_id']))
    
    return redirect(request.referrer or url_for('index'))

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    data = fetch_all('''SELECT u.username, u.avatar, COUNT(l.id) as likes 
                        FROM users u
                        LEFT JOIN comments c ON c.user_id = u.id
                        LEFT JOIN likes l ON l.comment_id = c.id
                        GROUP BY u.id
                        ORDER BY likes DESC LIMIT 10''')
    
    return render_template('leaderboard.html', leaderboard=data)

@app.route('/friends')
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friends_list = fetch_all('''SELECT u.id, u.username, u.avatar, u.bio 
                               FROM friends f JOIN users u ON u.id = f.friend_id
                               WHERE f.user_id = %s AND f.status = 'accepted'
                               UNION
                               SELECT u.id, u.username, u.avatar, u.bio 
                               FROM friends f JOIN users u ON u.id = f.user_id
                               WHERE f.friend_id = %s AND f.status = 'accepted'
                               ''', (session['user_id'], session['user_id']))
    
    requests = fetch_all('''SELECT u.id, u.username, u.avatar 
                            FROM friends f JOIN users u ON u.id = f.user_id
                            WHERE f.friend_id = %s AND f.status = 'pending'
                            ''', (session['user_id'],))
    
    return render_template('friends.html', friends=friends_list, requests=requests, 
                          username=session.get('username', ''))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_id = request.form.get('friend_id')
    action = request.form.get('action', 'add')
    
    if action == 'add':
        try:
            execute_query('INSERT INTO friends (user_id, friend_id, status, created_at) VALUES (%s, %s, %s, %s)',
                          (session['user_id'], friend_id, 'pending', datetime.now().isoformat()))
            flash('Запрос в друзья отправлен!', 'success')
        except:
            flash('Запрос уже отправлен', 'error')
    elif action == 'accept':
        execute_query('UPDATE friends SET status = "accepted" WHERE user_id=%s AND friend_id=%s',
                      (friend_id, session['user_id']))
        flash('Вы теперь друзья!', 'success')
    
    return redirect(request.referrer or url_for('friends'))

@app.route('/search_users')
def search_users():
    if 'user_id' not in session:
        return jsonify([])
    
    query = request.args.get('q', '')
    users = fetch_all('''SELECT id, username, avatar FROM users 
                         WHERE username LIKE %s AND id != %s LIMIT 10''', 
                      (f'%{query}%', session['user_id']))
    
    return jsonify([{'id': u[0], 'username': u[1], 'avatar': u[2]} for u in users])

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_chats = fetch_all('''SELECT c.*, 
                              (SELECT COUNT(*) FROM messages WHERE chat_id = c.id AND is_read = 0 AND sender_id != %s) as unread,
                              (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) as members_count
                              FROM chats c JOIN chat_members cm ON cm.chat_id = c.id
                              WHERE cm.user_id = %s AND c.is_community = 0
                              ORDER BY c.created_at DESC''', 
                           (session['user_id'], session['user_id']))
    
    return render_template('chats.html', chats=user_chats, username=session.get('username', ''))

@app.route('/chat/<int:chat_id>')
def chat_view(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    member = fetch_one('SELECT * FROM chat_members WHERE chat_id=%s AND user_id=%s', 
                       (chat_id, session['user_id']))
    if not member:
        flash('Нет доступа к чату', 'error')
        return redirect(url_for('chats'))
    
    messages = fetch_all('''SELECT m.*, u.username, u.avatar FROM messages m
                            JOIN users u ON m.sender_id = u.id
                            WHERE m.chat_id = %s ORDER BY m.timestamp ASC''', (chat_id,))
    
    execute_query('UPDATE messages SET is_read = 1 WHERE chat_id=%s AND sender_id != %s', 
                  (chat_id, session['user_id']))
    
    chat = fetch_one('SELECT * FROM chats WHERE id = %s', (chat_id,))
    members = fetch_all('''SELECT u.id, u.username, u.avatar, cm.role FROM users u
                           JOIN chat_members cm ON cm.user_id = u.id WHERE cm.chat_id = %s''', (chat_id,))
    
    return render_template('chat_view.html', messages=messages, chat=chat, members=members, 
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
    
    execute_query('INSERT INTO messages (chat_id, sender_id, text, image, timestamp) VALUES (%s, %s, %s, %s, %s)',
                  (chat_id, session['user_id'], text, image, datetime.now().isoformat()))
    
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/create_group', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name', '')
    
    execute_query('INSERT INTO chats (name, is_group, created_by, created_at) VALUES (%s, %s, %s, %s)',
                  (name, 1, session['user_id'], datetime.now().isoformat()))
    
    # Получаем ID последнего чата
    chat_id = fetch_one('SELECT lastval()' if DATABASE_URL else 'SELECT last_insert_rowid()')[0]
    
    execute_query('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)',
                  (chat_id, session['user_id'], 'admin', datetime.now().isoformat()))
    
    flash('Группа создана!', 'success')
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/communities')
def communities():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    communities_list = fetch_all('''SELECT c.*, 
                                   (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) as members_count,
                                   (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id AND user_id = %s) as is_member
                                   FROM chats c WHERE c.is_community = 1
                                   ORDER BY members_count DESC''', (session['user_id'],))
    
    return render_template('communities.html', communities=communities_list, 
                          username=session.get('username', ''))

@app.route('/community/<int:community_id>')
def view_community(community_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    community = fetch_one('SELECT * FROM chats WHERE id=%s AND is_community=1', (community_id,))
    if not community:
        flash('Сообщество не найдено', 'error')
        return redirect(url_for('communities'))
    
    posts = fetch_all('''SELECT p.*, u.username, u.avatar FROM posts p
                         JOIN users u ON p.user_id = u.id
                         WHERE p.community_id = %s ORDER BY p.created_at DESC''', (community_id,))
    
    members_count = fetch_one('SELECT COUNT(*) FROM chat_members WHERE chat_id=%s', (community_id,))[0]
    is_member = fetch_one('SELECT * FROM chat_members WHERE chat_id=%s AND user_id=%s',
                         (community_id, session['user_id'])) is not None
    
    return render_template('view_community.html', community=community, posts=posts, 
                          members_count=members_count, is_member=is_member, 
                          username=session.get('username', ''))

@app.route('/create_community', methods=['POST'])
def create_community():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    if not name:
        flash('Введите название!', 'error')
        return redirect(url_for('communities'))
    
    execute_query('''INSERT INTO chats (name, description, is_group, is_community, created_by, created_at) 
                     VALUES (%s, %s, %s, %s, %s, %s)''',
                  (name, description, 0, 1, session['user_id'], datetime.now().isoformat()))
    
    chat_id = fetch_one('SELECT lastval()' if DATABASE_URL else 'SELECT last_insert_rowid()')[0]
    
    execute_query('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)',
                  (chat_id, session['user_id'], 'admin', datetime.now().isoformat()))
    
    flash('Сообщество создано!', 'success')
    return redirect(url_for('view_community', community_id=chat_id))

@app.route('/create_community_post/<int:community_id>', methods=['POST'])
def create_community_post(community_id):
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
    
    execute_query('INSERT INTO posts (user_id, text, image, created_at, community_id) VALUES (%s, %s, %s, %s, %s)',
                  (session['user_id'], text, image, datetime.now().isoformat(), community_id))
    
    flash('Пост опубликован в сообществе!', 'success')
    return redirect(url_for('view_community', community_id=community_id))

@app.route('/join_community/<int:chat_id>')
def join_community(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    existing = fetch_one('SELECT * FROM chat_members WHERE chat_id=%s AND user_id=%s', 
                        (chat_id, session['user_id']))
    if existing:
        return redirect(url_for('view_community', community_id=chat_id))
    
    execute_query('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)',
                  (chat_id, session['user_id'], 'member', datetime.now().isoformat()))
    
    flash('Вы вступили в сообщество!', 'success')
    return redirect(url_for('view_community', community_id=chat_id))

@app.route('/leave_community/<int:chat_id>')
def leave_community(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    execute_query('DELETE FROM chat_members WHERE chat_id=%s AND user_id=%s', 
                  (chat_id, session['user_id']))
    
    flash('Вы покинули сообщество', 'success')
    return redirect(url_for('communities'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        try:
            execute_query('INSERT INTO users (username, password, created_at) VALUES (%s, %s, %s)',
                          (username, password, datetime.now().isoformat()))
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except:
            flash('Пользователь уже существует!', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        user = fetch_one('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
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
    
    user = fetch_one('SELECT * FROM users WHERE id=%s', (session['user_id'],))
    friends_count = fetch_one('''SELECT COUNT(*) FROM friends 
                                 WHERE (user_id = %s OR friend_id = %s) AND status = 'accepted'
                                 ''', (session['user_id'], session['user_id']))[0]
    likes_count = fetch_one('''SELECT COUNT(*) FROM likes l
                               JOIN comments c ON c.id = l.comment_id
                               WHERE c.user_id = %s''', (session['user_id'],))[0]
    posts_count = fetch_one('SELECT COUNT(*) FROM posts WHERE user_id = %s', (session['user_id'],))[0]
    
    return render_template('profile.html', user=user, friends_count=friends_count, 
                          likes_count=likes_count, posts_count=posts_count, 
                          username=session.get('username', ''))

@app.route('/profile/<username>')
def view_profile(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = fetch_one('SELECT * FROM users WHERE username=%s', (username,))
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))
    
    posts = fetch_all('SELECT * FROM posts WHERE user_id=%s ORDER BY created_at DESC', (user[0],))
    
    return render_template('view_profile.html', user=user, posts=posts, 
                          username=session.get('username', ''))

@app.route('/create_chat_with_user', methods=['POST'])
def create_chat_with_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_id = request.form.get('friend_id')
    
    existing = fetch_one('''SELECT c.id FROM chats c
                            JOIN chat_members cm1 ON cm1.chat_id = c.id
                            JOIN chat_members cm2 ON cm2.chat_id = c.id
                            WHERE cm1.user_id = %s AND cm2.user_id = %s 
                            AND c.is_group = 0 AND c.is_community = 0
                            AND (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) = 2''',
                         (session['user_id'], friend_id))
    
    if existing:
        return redirect(url_for('chat_view', chat_id=existing[0]))
    
    execute_query('INSERT INTO chats (name, is_group, is_community, created_at) VALUES (%s, %s, %s, %s)',
                  ('', 0, 0, datetime.now().isoformat()))
    
    chat_id = fetch_one('SELECT lastval()' if DATABASE_URL else 'SELECT last_insert_rowid()')[0]
    
    execute_query('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (%s, %s, %s)',
                  (chat_id, session['user_id'], datetime.now().isoformat()))
    execute_query('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (%s, %s, %s)',
                  (chat_id, friend_id, datetime.now().isoformat()))
    
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
            execute_query('UPDATE users SET avatar = %s WHERE id = %s', (filename, session['user_id']))
            flash('Аватарка обновлена!', 'success')
    
    return redirect(url_for('profile'))

@app.route('/update_bio', methods=['POST'])
def update_bio():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bio = request.form.get('bio', '')
    execute_query('UPDATE users SET bio = %s WHERE id = %s', (bio, session['user_id']))
    flash('Статус обновлён!', 'success')
    
    return redirect(url_for('profile'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
