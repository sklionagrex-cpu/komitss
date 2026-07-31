import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import hashlib
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)
os.makedirs('uploads/group_avatars', exist_ok=True)

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
        created_at TEXT,
        last_seen TEXT,
        online INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        image TEXT,
        created_at TEXT,
        community_id INTEGER DEFAULT 0
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

init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    posts = c.execute('''SELECT p.*, u.username, u.avatar, 
                         (SELECT name FROM chats WHERE id = p.community_id) as community_name
                         FROM posts p
                         JOIN users u ON p.user_id = u.id
                         ORDER BY p.created_at DESC''').fetchall()
    
    comments_dict = {}
    for post in posts:
        comments = c.execute('''SELECT c.*, u.username, 
                               (SELECT COUNT(*) FROM likes WHERE comment_id = c.id) as likes_count 
                               FROM comments c 
                               JOIN users u ON c.user_id = u.id 
                               WHERE c.post_id = ? 
                               ORDER BY c.created_at''', (post[0],)).fetchall()
        comments_dict[post[0]] = comments
    
    db.close()
    return render_template('index.html', posts=posts, comments_dict=comments_dict, username=session.get('username', ''))

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    text = request.form.get('text', '')
    image = None
    community_id = request.form.get('community_id', 0)
    
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
            image = filename
    
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO posts (user_id, text, image, created_at, community_id) VALUES (?, ?, ?, ?, ?)',
              (session['user_id'], text, image, datetime.now().isoformat(), community_id))
    db.commit()
    db.close()
    
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

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    data = c.execute('''SELECT u.username, u.avatar, COUNT(l.id) as likes 
                        FROM users u
                        LEFT JOIN comments c ON c.user_id = u.id
                        LEFT JOIN likes l ON l.comment_id = c.id
                        GROUP BY u.id
                        ORDER BY likes DESC
                        LIMIT 10''').fetchall()
    db.close()
    return render_template('leaderboard.html', leaderboard=data)

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    user_chats = c.execute('''SELECT c.*, 
                              (SELECT COUNT(*) FROM messages WHERE chat_id = c.id AND is_read = 0 AND sender_id != ?) as unread,
                              (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) as members_count,
                              (SELECT m.text FROM messages m WHERE m.chat_id = c.id ORDER BY m.timestamp DESC LIMIT 1) as last_msg
                              FROM chats c
                              JOIN chat_members cm ON cm.chat_id = c.id
                              WHERE cm.user_id = ? AND c.is_community = 0
                              ORDER BY c.created_at DESC''', (session['user_id'], session['user_id'])).fetchall()
    db.close()
    return render_template('chats.html', chats=user_chats, username=session.get('username', ''))

@app.route('/chat/<int:chat_id>')
def chat_view(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    member = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=?', 
                       (chat_id, session['user_id'])).fetchone()
    if not member:
        return redirect(url_for('chats'))
    
    messages = c.execute('''SELECT m.*, u.username, u.avatar FROM messages m
                            JOIN users u ON m.sender_id = u.id
                            WHERE m.chat_id = ?
                            ORDER BY m.timestamp ASC''', (chat_id,)).fetchall()
    
    c.execute('UPDATE messages SET is_read = 1 WHERE chat_id = ? AND sender_id != ?', 
              (chat_id, session['user_id']))
    db.commit()
    chat = c.execute('SELECT * FROM chats WHERE id = ?', (chat_id,)).fetchone()
    members = c.execute('''SELECT u.id, u.username, u.avatar, cm.role FROM users u
                           JOIN chat_members cm ON cm.user_id = u.id
                           WHERE cm.chat_id = ?''', (chat_id,)).fetchall()
    is_admin = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=? AND role="admin"',
                        (chat_id, session['user_id'])).fetchone() is not None
    db.close()
    return render_template('chat_view.html', messages=messages, chat=chat, members=members, 
                          chat_id=chat_id, username=session.get('username', ''), is_admin=is_admin)

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

@app.route('/create_group', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name', '')
    avatar = None
    
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads/group_avatars', filename))
            avatar = filename
    
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO chats (name, is_group, is_community, created_by, created_at, avatar) VALUES (?, ?, ?, ?, ?, ?)',
              (name, 1, 0, session['user_id'], datetime.now().isoformat(), avatar))
    chat_id = c.lastrowid
    c.execute('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)',
              (chat_id, session['user_id'], 'admin', datetime.now().isoformat()))
    db.commit()
    db.close()
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/friends_list')
def friends_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    friends = c.execute('''SELECT u.id, u.username, u.avatar, u.bio 
                           FROM friends f
                           JOIN users u ON (u.id = f.friend_id OR u.id = f.user_id)
                           WHERE (f.user_id = ? OR f.friend_id = ?) 
                           AND f.status = 'accepted'
                           AND u.id != ?''', 
                        (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    requests = c.execute('''SELECT u.id, u.username, u.avatar 
                            FROM friends f
                            JOIN users u ON u.id = f.user_id
                            WHERE f.friend_id = ? AND f.status = 'pending' ''', 
                         (session['user_id'],)).fetchall()
    db.close()
    return render_template('friends_list.html', friends=friends, requests=requests, username=session.get('username', ''))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_username = request.form.get('friend_username')
    action = request.form.get('action', 'add')
    
    db = get_db()
    c = db.cursor()
    friend = c.execute('SELECT id FROM users WHERE username = ?', (friend_username,)).fetchone()
    if not friend:
        flash('Пользователь не найден')
        return redirect(request.referrer or url_for('index'))
    
    friend_id = friend[0]
    
    if action == 'add':
        try:
            c.execute('INSERT INTO friends (user_id, friend_id, status, created_at) VALUES (?, ?, ?, ?)',
                      (session['user_id'], friend_id, 'pending', datetime.now().isoformat()))
            flash('Запрос в друзья отправлен!')
        except:
            flash('Вы уже отправили запрос этому пользователю')
    elif action == 'accept':
        c.execute('UPDATE friends SET status = "accepted" WHERE user_id=? AND friend_id=?',
                  (friend_id, session['user_id']))
        flash('Вы теперь друзья!')
    
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('friends_list'))

@app.route('/search_users')
def search_users():
    if 'user_id' not in session:
        return jsonify([])
    
    query = request.args.get('q', '')
    db = get_db()
    c = db.cursor()
    users = c.execute('''SELECT id, username, avatar 
                         FROM users 
                         WHERE username LIKE ? AND id != ? 
                         LIMIT 10''', (f'%{query}%', session['user_id'])).fetchall()
    db.close()
    return jsonify([{'id': u[0], 'username': u[1], 'avatar': u[2]} for u in users])

@app.route('/profile/<username>')
def view_profile(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('index'))
    
    posts = c.execute('SELECT * FROM posts WHERE user_id=? AND community_id=0 ORDER BY created_at DESC', (user[0],)).fetchall()
    chat = c.execute('''SELECT c.id FROM chats c
                        JOIN chat_members cm1 ON cm1.chat_id = c.id
                        JOIN chat_members cm2 ON cm2.chat_id = c.id
                        WHERE cm1.user_id = ? AND cm2.user_id = ? 
                        AND c.is_group = 0 AND c.is_community = 0
                        AND (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) = 2''',
                     (session['user_id'], user[0])).fetchone()
    friend_status = c.execute('SELECT status FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)',
                             (session['user_id'], user[0], user[0], session['user_id'])).fetchone()
    db.close()
    return render_template('view_profile.html', user=user, posts=posts, chat=chat, 
                          friend_status=friend_status, username=session.get('username', ''))

@app.route('/create_chat_with_user', methods=['POST'])
def create_chat_with_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_id = request.form.get('friend_id')
    
    db = get_db()
    c = db.cursor()
    existing = c.execute('''SELECT c.id FROM chats c
                            JOIN chat_members cm1 ON cm1.chat_id = c.id
                            JOIN chat_members cm2 ON cm2.chat_id = c.id
                            WHERE cm1.user_id = ? AND cm2.user_id = ? 
                            AND c.is_group = 0 AND c.is_community = 0
                            AND (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) = 2''',
                         (session['user_id'], friend_id)).fetchone()
    if existing:
        return redirect(url_for('chat_view', chat_id=existing[0]))
    
    c.execute('INSERT INTO chats (name, is_group, is_community, created_at) VALUES (?, ?, ?, ?)',
              ('', 0, 0, datetime.now().isoformat()))
    chat_id = c.lastrowid
    c.execute('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (?, ?, ?)',
              (chat_id, session['user_id'], datetime.now().isoformat()))
    c.execute('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (?, ?, ?)',
              (chat_id, friend_id, datetime.now().isoformat()))
    db.commit()
    db.close()
    return redirect(url_for('chat_view', chat_id=chat_id))

@app.route('/communities')
def communities():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    communities = c.execute('''SELECT c.*, 
                               (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id) as members_count,
                               (SELECT COUNT(*) FROM chat_members WHERE chat_id = c.id AND user_id = ?) as is_member
                               FROM chats c
                               WHERE c.is_community = 1
                               ORDER BY members_count DESC''', (session['user_id'],)).fetchall()
    db.close()
    return render_template('communities.html', communities=communities, username=session.get('username', ''))

@app.route('/community/<int:community_id>')
def view_community(community_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    community = c.execute('SELECT * FROM chats WHERE id=? AND is_community=1', (community_id,)).fetchone()
    if not community:
        flash('Сообщество не найдено')
        return redirect(url_for('communities'))
    
    posts = c.execute('''SELECT p.*, u.username, u.avatar FROM posts p
                         JOIN users u ON p.user_id = u.id
                         WHERE p.community_id = ?
                         ORDER BY p.created_at DESC''', (community_id,)).fetchall()
    
    is_admin = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=? AND role="admin"',
                        (community_id, session['user_id'])).fetchone() is not None
    is_member = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=?',
                         (community_id, session['user_id'])).fetchone() is not None
    db.close()
    return render_template('view_community.html', community=community, posts=posts, 
                          is_admin=is_admin, is_member=is_member, username=session.get('username', ''))

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
    
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO posts (user_id, text, image, created_at, community_id) VALUES (?, ?, ?, ?, ?)',
              (session['user_id'], text, image, datetime.now().isoformat(), community_id))
    db.commit()
    db.close()
    return redirect(url_for('view_community', community_id=community_id))

@app.route('/create_community', methods=['POST'])
def create_community():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    if not name:
        flash('Введите название сообщества!')
        return redirect(url_for('communities'))
    
    db = get_db()
    c = db.cursor()
    existing = c.execute('SELECT id FROM chats WHERE name = ? AND is_community = 1', (name,)).fetchone()
    if existing:
        flash('Сообщество с таким названием уже существует!')
        return redirect(url_for('communities'))
    
    c.execute('''INSERT INTO chats (name, description, is_group, is_community, created_by, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (name, description, 0, 1, session['user_id'], datetime.now().isoformat()))
    chat_id = c.lastrowid
    c.execute('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)',
              (chat_id, session['user_id'], 'admin', datetime.now().isoformat()))
    db.commit()
    db.close()
    flash('Сообщество создано!')
    return redirect(url_for('view_community', community_id=chat_id))

@app.route('/join_community/<int:chat_id>')
def join_community(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    chat = c.execute('SELECT * FROM chats WHERE id=? AND is_community=1', (chat_id,)).fetchone()
    if not chat:
        flash('Сообщество не найдено')
        return redirect(url_for('communities'))
    
    existing = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=?', 
                        (chat_id, session['user_id'])).fetchone()
    if existing:
        return redirect(url_for('view_community', community_id=chat_id))
    
    c.execute('INSERT INTO chat_members (chat_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)',
              (chat_id, session['user_id'], 'member', datetime.now().isoformat()))
    db.commit()
    db.close()
    flash('Вы вступили в сообщество!')
    return redirect(url_for('view_community', community_id=chat_id))

@app.route('/leave_community/<int:chat_id>')
def leave_community(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    c.execute('DELETE FROM chat_members WHERE chat_id=? AND user_id=?', (chat_id, session['user_id']))
    db.commit()
    db.close()
    flash('Вы покинули сообщество')
    return redirect(url_for('communities'))

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
            flash('Регистрация успешна!')
            return redirect(url_for('login'))
        except:
            flash('Пользователь уже существует!')
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
        
        flash('Неверный логин или пароль!')
    
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
    
    friends_count = c.execute('''SELECT COUNT(*) FROM friends 
                                 WHERE (user_id = ? OR friend_id = ?) AND status = 'accepted'
                                 ''', (session['user_id'], session['user_id'])).fetchone()[0]
    likes_count = c.execute('''SELECT COUNT(*) FROM likes l
                               JOIN comments c ON c.id = l.comment_id
                               WHERE c.user_id = ?''', (session['user_id'],)).fetchone()[0]
    posts_count = c.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND community_id=0', (session['user_id'],)).fetchone()[0]
    db.close()
    
    return render_template('profile.html', user=user, friends_count=friends_count, 
                          likes_count=likes_count, posts_count=posts_count, 
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
            c.execute('UPDATE users SET avatar = ? WHERE id = ?', (filename, session['user_id']))
            db.commit()
            db.close()
            flash('Аватарка обновлена!')
    
    return redirect(url_for('profile'))

@app.route('/update_bio', methods=['POST'])
def update_bio():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bio = request.form.get('bio', '')
    db = get_db()
    c = db.cursor()
    c.execute('UPDATE users SET bio = ? WHERE id = ?', (bio, session['user_id']))
    db.commit()
    db.close()
    return redirect(url_for('profile'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
