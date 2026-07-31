import os
import hashlib
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)

def get_db():
    return sqlite3.connect('komits.db')

def init_db():
    conn = sqlite3.connect('komits.db')
    c = conn.cursor()
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
    conn.commit()
    conn.close()

init_db()

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
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    friends_count = c.execute('SELECT COUNT(*) FROM friends WHERE (user_id=? OR friend_id=?) AND status="accepted"', 
                             (session['user_id'], session['user_id'])).fetchone()[0]
    likes_count = c.execute('SELECT COUNT(*) FROM likes l JOIN comments c ON c.id=l.comment_id WHERE c.user_id=?', 
                           (session['user_id'],)).fetchone()[0]
    posts_count = c.execute('SELECT COUNT(*) FROM posts WHERE user_id=?', (session['user_id'],)).fetchone()[0]
    db.close()
    return render_template('profile.html', user=user, friends_count=friends_count, 
                          likes_count=likes_count, posts_count=posts_count, username=session.get('username', ''))

@app.route('/profile/<username>')
def view_profile(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))
    posts = c.execute('SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC', (user[0],)).fetchall()
    db.close()
    return render_template('view_profile.html', user=user, posts=posts, username=session.get('username', ''))

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

@app.route('/update_bio', methods=['POST'])
def update_bio():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    bio = request.form.get('bio', '')
    db = get_db()
    c = db.cursor()
    c.execute('UPDATE users SET bio=? WHERE id=?', (bio, session['user_id']))
    db.commit()
    db.close()
    flash('Статус обновлён!', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
