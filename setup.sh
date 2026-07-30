#!/bin/bash
echo "Установка зависимостей для Komits..."

# Обновление пакетов Termux
pkg update -y
pkg upgrade -y

# Установка Python и pip
pkg install python python-pip -y

# Обновление pip
python -m pip install --upgrade pip

# Установка библиотек
pip install --default-timeout=100 --no-cache-dir \
  Flask==2.0.3 \
  Werkzeug==2.0.3 \
  Jinja2==3.0.3 \
  MarkupSafe==2.0.1 \
  Flask-SQLAlchemy==2.5.1 \
  Flask-Login==0.5.0 \
  SQLAlchemy==1.4.46 \
  Pillow==9.0.0

echo "✅ Все библиотеки установлены!"
