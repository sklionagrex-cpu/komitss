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
    
    # ---- Существующие таблицы (сокращено для читаемости) ----
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
        visibility TEXT DEFAULT 'public',
        likes_count INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        reposts_count INTEGER DEFAULT 0
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
    )''')
    
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user_id INTEGER,
        friend_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        PRIMARY KEY (user_id, friend_id)
    )''')
    
    # ---- НОВЫЕ ТАБЛИЦЫ ДЛЯ ЧАТОВ ----
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1_id INTEGER,
        user2_id INTEGER,
        is_group INTEGER DEFAULT 0,
        name TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_members (
        chat_id INTEGER,
        user_id INTEGER,
        role TEXT DEFAULT 'member',
        joined_at TEXT,
        PRIMARY KEY (chat_id, user_id)
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_preferences (
        user_id INTEGER,
        chat_id INTEGER,
        pinned INTEGER DEFAULT 0,
        muted INTEGER DEFAULT 0,
        archived INTEGER DEFAULT 0,
        last_read_message_id INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, chat_id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ---- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЧАТОВ ----
def get_user(user_id):
    db = get_db()
    c = db.cursor()
    user = c.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    return user

def get_chat_preference(user_id, chat_id):
    db = get_db()
    c = db.cursor()
    pref = c.execute('SELECT * FROM chat_preferences WHERE user_id=? AND chat_id=?', (user_id, chat_id)).fetchone()
    db.close()
    if not pref:
        # Создаём настройки по умолчанию
        db = get_db()
        c = db.cursor()
        c.execute('INSERT INTO chat_preferences (user_id, chat_id) VALUES (?, ?)', (user_id, chat_id))
        db.commit()
        db.close()
        return (user_id, chat_id, 0, 0, 0, 0)
    return pref

def get_chat_list(user_id):
    db = get_db()
    c = db.cursor()
    # Получаем чаты пользователя (личные + группы)
    chats = c.execute('''SELECT c.*, 
                           (SELECT COUNT(*) FROM messages WHERE chat_id = c.id AND is_read = 0 AND sender_id != ?) as unread,
                           (SELECT MAX(timestamp) FROM messages WHERE chat_id = c.id) as last_msg_time,
                           (SELECT text FROM messages WHERE chat_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_msg_text,
                           (SELECT image FROM messages WHERE chat_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_msg_image,
                           cp.pinned, cp.muted, cp.archived
                        FROM chats c
                        LEFT JOIN chat_preferences cp ON cp.chat_id = c.id AND cp.user_id = ?
                        WHERE (c.user1_id = ? OR c.user2_id = ? OR c.id IN (SELECT chat_id FROM chat_members WHERE user_id = ?))
                        AND (cp.archived = 0 OR cp.archived IS NULL)
                        ORDER BY cp.pinned DESC, last_msg_time DESC''',
                     (user_id, user_id, user_id, user_id, user_id)).fetchall()
    db.close()
    return chats

# ---- МАРШРУТЫ ----
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # ... (как было) ...
    return render_template('index.html', posts=[], comments={}, stories=[], username=session.get('username', ''))

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    chat_list = get_chat_list(session['user_id'])
    return render_template('chats.html', chats=chat_list, username=session.get('username', ''))

@app.route('/chat/<int:chat_id>')
def chat_view(chat_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    c = db.cursor()
    # Проверка доступа
    member = c.execute('SELECT * FROM chat_members WHERE chat_id=? AND user_id=?', (chat_id, session['user_id'])).fetchone()
    if not member:
        chat = c.execute('SELECT * FROM chats WHERE id=? AND (user1_id=? OR user2_id=?)', (chat_id, session['user_id'], session['user_id'])).fetchone()
        if not chat:
            flash('Нет доступа к чату', 'error')
            return redirect(url_for('chats'))
    messages = c.execute('''SELECT m.*, u.username, u.avatar FROM messages m
                            JOIN users u ON m.sender_id = u.id
                            WHERE m.chat_id = ? ORDER BY m.timestamp ASC''', (chat_id,)).fetchall()
    # Отметить все как прочитанные
    c.execute('UPDATE messages SET is_read = 1 WHERE chat_id = ? AND sender_id != ?', (chat_id, session['user_id']))
    # Обновить last_read_message_id в настройках
    last_msg = c.execute('SELECT MAX(id) FROM messages WHERE chat_id = ?', (chat_id,)).fetchone()[0]
    if last_msg:
        c.execute('UPDATE chat_preferences SET last_read_message_id = ? WHERE user_id = ? AND chat_id = ?',
                  (last_msg, session['user_id'], chat_id))
    db.commit()
    db.close()
    return render_template('chat_view.html', messages=messages, chat_id=chat_id, username=session.get('username', ''))

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
    # Добавляем участников в chat_members
    c.execute('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (?, ?, ?)',
              (chat_id, session['user_id'], datetime.now().isoformat()))
    c.execute('INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (?, ?, ?)',
              (chat_id, friend_id, datetime.now().isoformat()))
    db.commit()
    db.close()
    return redirect(url_for('chat_view', chat_id=chat_id))

# ---- API ДЛЯ ЖЕСТОВ И КОНТЕКСТНОГО МЕНЮ ----
@app.route('/chat/pin', methods=['POST'])
def chat_pin():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    chat_id = request.form.get('chat_id')
    db = get_db()
    c = db.cursor()
    # Получаем текущее значение
    pref = c.execute('SELECT pinned FROM chat_preferences WHERE user_id=? AND chat_id=?', (session['user_id'], chat_id)).fetchone()
    if pref:
        new_pin = 0 if pref[0] else 1
        c.execute('UPDATE chat_preferences SET pinned=? WHERE user_id=? AND chat_id=?', (new_pin, session['user_id'], chat_id))
    else:
        new_pin = 1
        c.execute('INSERT INTO chat_preferences (user_id, chat_id, pinned) VALUES (?, ?, ?)', (session['user_id'], chat_id, new_pin))
    db.commit()
    db.close()
    return jsonify({'pinned': new_pin})

@app.route('/chat/mute', methods=['POST'])
def chat_mute():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    chat_id = request.form.get('chat_id')
    db = get_db()
    c = db.cursor()
    pref = c.execute('SELECT muted FROM chat_preferences WHERE user_id=? AND chat_id=?', (session['user_id'], chat_id)).fetchone()
    if pref:
        new_mute = 0 if pref[0] else 1
        c.execute('UPDATE chat_preferences SET muted=? WHERE user_id=? AND chat_id=?', (new_mute, session['user_id'], chat_id))
    else:
        new_mute = 1
        c.execute('INSERT INTO chat_preferences (user_id, chat_id, muted) VALUES (?, ?, ?)', (session['user_id'], chat_id, new_mute))
    db.commit()
    db.close()
    return jsonify({'muted': new_mute})

@app.route('/chat/archive', methods=['POST'])
def chat_archive():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    chat_id = request.form.get('chat_id')
    db = get_db()
    c = db.cursor()
    pref = c.execute('SELECT archived FROM chat_preferences WHERE user_id=? AND chat_id=?', (session['user_id'], chat_id)).fetchone()
    if pref:
        new_archive = 0 if pref[0] else 1
        c.execute('UPDATE chat_preferences SET archived=? WHERE user_id=? AND chat_id=?', (new_archive, session['user_id'], chat_id))
    else:
        new_archive = 1
        c.execute('INSERT INTO chat_preferences (user_id, chat_id, archived) VALUES (?, ?, ?)', (session['user_id'], chat_id, new_archive))
    db.commit()
    db.close()
    return jsonify({'archived': new_archive})

@app.route('/chat/unread', methods=['POST'])
def chat_unread():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    chat_id = request.form.get('chat_id')
    db = get_db()
    c = db.cursor()
    # Помечаем как непрочитанное: сбрасываем last_read_message_id на предыдущее сообщение
    # Получаем последнее сообщение
    last_msg = c.execute('SELECT id FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1', (chat_id,)).fetchone()
    if last_msg:
        prev_msg = c.execute('SELECT id FROM messages WHERE chat_id = ? AND id < ? ORDER BY id DESC LIMIT 1', (chat_id, last_msg[0])).fetchone()
        new_last_read = prev_msg[0] if prev_msg else 0
        c.execute('UPDATE chat_preferences SET last_read_message_id = ? WHERE user_id = ? AND chat_id = ?',
                  (new_last_read, session['user_id'], chat_id))
        db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/chat/delete', methods=['POST'])
def chat_delete():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    chat_id = request.form.get('chat_id')
    db = get_db()
    c = db.cursor()
    # Удаляем чат только для пользователя (скрываем), можно архивировать или удалить полностью если он создатель.
    # Поскольку у нас нет прав, просто архивируем.
    c.execute('UPDATE chat_preferences SET archived = 1 WHERE user_id = ? AND chat_id = ?', (session['user_id'], chat_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ---- ОСТАЛЬНЫЕ МАРШРУТЫ (регистрация, логин, профиль, друзья) ----
# ... (они уже есть в предыдущих версиях, здесь я пропущу для краткости) ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
