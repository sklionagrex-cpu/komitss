import os
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename

# Пытаемся импортировать psycopg2, если он установлен
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    # Если psycopg2 не найден, используем sqlite3
    import sqlite3

app = Flask(__name__)
app.secret_key = 'komits_secret_2026'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)

# Определяем функцию подключения к БД
def get_db_connection():
    """Подключение к PostgreSQL или SQLite"""
    if POSTGRES_AVAILABLE:
        # Используем PostgreSQL, если psycopg2 установлен
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL:
            return psycopg2.connect(DATABASE_URL)
    
    # Запасной вариант: SQLite (для локальной разработки или если PostgreSQL недоступен)
    import sqlite3
    return sqlite3.connect('komits.db')

# --- ВСЁ ОСТАЛЬНОЕ: все ваши маршруты (routes) и функции ---
# (Оставьте остальную часть вашего app.py без изменений)
# ...
