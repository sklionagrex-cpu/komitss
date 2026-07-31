from flask import Flask, request, redirect, url_for, flash, session
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'

def get_db():
    return sqlite3.connect('komits.db')

def init_db():
    conn = sqlite3.connect('komits.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return '''
    <h1>Komits</h1>
    <p>Вы вошли как {}</p>
    <a href="/logout">Выйти</a>
    '''.format(session.get('username', ''))

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
    return '''
    <h1>Регистрация</h1>
    <form method="post">
        <input type="text" name="username" placeholder="Юзернейм" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Зарегистрироваться</button>
    </form>
    <a href="/login">Войти</a>
    '''

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
    return '''
    <h1>Вход</h1>
    <form method="post">
        <input type="text" name="username" placeholder="Юзернейм" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Войти</button>
    </form>
    <a href="/register">Зарегистрироваться</a>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
