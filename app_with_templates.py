from flask import Flask, render_template, request, redirect, url_for, flash, session
import hashlib
import os
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)

def init_db():
    conn = sqlite3.connect('komits.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        avatar TEXT DEFAULT 'default.jpg',
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
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('komits.db')

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    posts = c.execute('''SELECT p.*, u.username FROM posts p 
                         JOIN users u ON p.user_id = u.id 
                         ORDER BY p.created_at DESC''').fetchall()
    
    # Получаем комментарии и лайки для каждого поста
    comments = []
    for post in posts:
        post_comments = c.execute('''SELECT c.*, u.username, 
                                     (SELECT COUNT(*) FROM likes WHERE comment_id = c.id) as likes_count 
                                     FROM comments c 
                                     JOIN users u ON c.user_id = u.id 
                                     WHERE c.post_id = ? 
                                     ORDER BY c.created_at''', (post[0],)).fetchall()
        comments.extend([(c[0], c[1], c[5], c[3], c[6]) for c in post_comments])
    
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
    
    return redirect(url_for('index'))

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    text = request.form.get('text', '')
    
    db = get_db()
    c = db.cursor()
    c.execute('INSERT INTO comments (post_id, user_id, text, created_at) VALUES (?, ?, ?, ?)',
              (post_id, session['user_id'], text, datetime.now().isoformat()))
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
    data = c.execute('''SELECT u.username, COUNT(l.id) as likes 
                        FROM users u
                        LEFT JOIN comments c ON c.user_id = u.id
                        LEFT JOIN likes l ON l.comment_id = c.id
                        GROUP BY u.id
                        ORDER BY likes DESC
                        LIMIT 10''').fetchall()
    db.close()
    return render_template('leaderboard.html', leaderboard=data)

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
    db.close()
    
    return render_template('profile.html', username=session.get('username', ''), created_at=user[4] if user else None)

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename:
            filename = f"avatar_{session['user_id']}.jpg"
            file.save(os.path.join('static/avatars', filename))
    
    return redirect(url_for('profile'))

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chats.html')

if __name__ == '__main__':
    print("🚀 Запуск Komits...")
    print("📱 Открой в браузере: http://localhost:5000")
    print("👤 Сначала зарегистрируйся!")
    app.run(host='0.0.0.0', port=5000, debug=True)
