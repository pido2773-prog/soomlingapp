from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import hashlib
import json
import os
import random
import string
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "soomling_gram_secret_v4"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/avatars', exist_ok=True)
os.makedirs('static/voice', exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

def init_db():
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        password TEXT,
        avatar TEXT,
        coins INTEGER DEFAULT 100,
        online INTEGER DEFAULT 0,
        favorites TEXT DEFAULT '[]',
        blocked TEXT DEFAULT '[]',
        settings TEXT DEFAULT '{"sound":true,"notifications":true,"fontSize":16}'
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user TEXT,
        to_user TEXT,
        message TEXT,
        timestamp TEXT,
        is_file INTEGER DEFAULT 0,
        file_url TEXT,
        is_voice INTEGER DEFAULT 0,
        is_secret INTEGER DEFAULT 0,
        reply_to INTEGER DEFAULT NULL,
        deleted INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        creator TEXT,
        members TEXT DEFAULT '[]',
        blocked TEXT DEFAULT '[]'
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS group_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        from_user TEXT,
        from_name TEXT,
        message TEXT,
        timestamp TEXT,
        is_file INTEGER DEFAULT 0,
        file_url TEXT,
        deleted INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY,
        name TEXT,
        emoji TEXT,
        price INTEGER
    )''')
    
    c.execute("SELECT COUNT(*) FROM gifts")
    if c.fetchone()[0] == 0:
        gifts = [(1, 'Роза', '🌹', 50), (2, 'Торт', '🎂', 100), (3, 'Корона', '👑', 500), (4, 'Сердце', '❤️', 30), (5, 'Сакура', '🌸', 80), (6, 'Алмаз', '💎', 1000)]
        c.executemany("INSERT INTO gifts (id, name, emoji, price) VALUES (?, ?, ?, ?)", gifts)
    
    conn.commit()
    conn.close()

init_db()

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def send_sms(phone, code):
    print(f"\n📱 [SMS] На номер {phone} отправлен код: {code}\n")
    return True

# === HTML СТРАНИЦЫ ===
LOGIN_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <link rel="manifest" href="/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoomlingGram">
    <title>SoomlingGram</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        @keyframes sakuraFloat {
            0% { transform: translateY(0) rotate(0deg); opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { transform: translateY(-100vh) rotate(360deg); opacity: 0; }
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            position: relative;
            overflow: hidden;
            font-size: 18px;
        }
        .sakura {
            position: absolute;
            pointer-events: none;
            font-size: 24px;
            animation: sakuraFloat linear forwards;
        }
        .glass {
            background: rgba(255,255,255,0.12);
            backdrop-filter: blur(20px);
            border-radius: 50px;
            padding: 40px;
            width: 100%;
            max-width: 480px;
            border: 1px solid rgba(255,255,255,0.25);
            z-index: 1;
        }
        h1 { text-align: center; margin-bottom: 10px; font-size: 48px; }
        .soomling { color: #ff6b6b; }
        .gram { color: #4ecdc4; }
        .subtitle { text-align: center; color: rgba(255,255,255,0.7); margin-bottom: 30px; font-size: 16px; }
        input {
            width: 100%;
            padding: 18px;
            margin-bottom: 18px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 30px;
            color: white;
            font-size: 18px;
        }
        input:focus { outline: none; border-color: #ff6b6b; }
        button {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
        }
        .error { background: rgba(255,0,0,0.3); color: #ffaaaa; padding: 12px; border-radius: 20px; margin-bottom: 20px; text-align: center; }
        .features { display: flex; justify-content: center; gap: 15px; margin-top: 30px; flex-wrap: wrap; }
        .feature { background: rgba(255,255,255,0.1); padding: 8px 18px; border-radius: 30px; font-size: 14px; }
        .support { text-align: center; margin-top: 25px; font-size: 14px; color: rgba(255,255,255,0.4); }
        .support a { color: #ff6b6b; text-decoration: none; }
    </style>
</head>
<body>
    <div class="glass">
        <h1><span class="soomling">Soomling</span><span class="gram">Gram</span></h1>
        <div class="subtitle">Telegram 2.0 | Секретные чаты</div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST" action="/send_sms_code">
            <input type="tel" name="phone" placeholder="📱 Номер телефона" required>
            <button type="submit">🔐 Войти / Регистрация</button>
        </form>
        <div class="features">
            <span class="feature">🔒 Секретные чаты</span>
            <span class="feature">🎙️ Кружки</span>
            <span class="feature">📁 Файлы</span>
            <span class="feature">🌸 Сакура</span>
        </div>
        <div class="support">📞 Поддержка: <a href="tel:89996081231">8-999-608-12-31</a></div>
    </div>
    <script>
        for(let i=0;i<30;i++){
            let s=document.createElement('div');
            s.className='sakura';
            s.innerHTML='🌸';
            s.style.left=Math.random()*100+'%';
            s.style.animationDuration=5+Math.random()*10+'s';
            s.style.animationDelay=Math.random()*10+'s';
            s.style.fontSize=20+Math.random()*30+'px';
            document.body.appendChild(s);
        }
    </script>
</body>
</html>
'''

CODE_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <link rel="manifest" href="/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoomlingGram">
    <title>Подтверждение - SoomlingGram</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
        }
        .glass {
            background: rgba(255,255,255,0.12);
            backdrop-filter: blur(20px);
            border-radius: 50px;
            padding: 40px;
            width: 100%;
            max-width: 450px;
            border: 1px solid rgba(255,255,255,0.25);
        }
        h1 { text-align: center; margin-bottom: 30px; color: #ff6b6b; font-size: 32px; }
        input {
            width: 100%;
            padding: 18px;
            margin-bottom: 18px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 30px;
            color: white;
            font-size: 20px;
            text-align: center;
        }
        button {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
        }
        .error { background: rgba(255,0,0,0.3); color: #ffaaaa; padding: 12px; border-radius: 20px; margin-bottom: 20px; text-align: center; }
        .hint { text-align: center; margin-top: 20px; color: rgba(255,255,255,0.5); font-size: 14px; }
    </style>
</head>
<body>
    <div class="glass">
        <h1>🌸 Код подтверждения</h1>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST" action="/verify_sms_code">
            <input type="text" name="code" placeholder="Введите код из SMS" required autofocus>
            <button type="submit">✅ Подтвердить</button>
        </form>
        <div class="hint">Код отправлен в консоль сервера</div>
    </div>
</body>
</html>
'''

REGISTER_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <link rel="manifest" href="/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoomlingGram">
    <title>Регистрация - SoomlingGram</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
        }
        .glass {
            background: rgba(255,255,255,0.12);
            backdrop-filter: blur(20px);
            border-radius: 50px;
            padding: 40px;
            width: 100%;
            max-width: 480px;
            border: 1px solid rgba(255,255,255,0.25);
        }
        h1 { text-align: center; margin-bottom: 30px; color: #ff6b6b; font-size: 36px; }
        input {
            width: 100%;
            padding: 18px;
            margin-bottom: 18px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 30px;
            color: white;
            font-size: 18px;
        }
        button {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
        }
        .row { display: flex; gap: 15px; }
        .row input { flex: 1; }
        .error { background: rgba(255,0,0,0.3); color: #ffaaaa; padding: 12px; border-radius: 20px; margin-bottom: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="glass">
        <h1>🌸 Регистрация</h1>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST" action="/complete_register">
            <div class="row">
                <input type="text" name="first_name" placeholder="Имя" required>
                <input type="text" name="last_name" placeholder="Фамилия" required>
            </div>
            <input type="email" name="email" placeholder="Email (необязательно)">
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit">✨ Завершить регистрацию</button>
        </form>
    </div>
</body>
</html>
'''

CHAT_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no">
    <link rel="manifest" href="/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="SoomlingGram">
    <title>SoomlingGram</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        @keyframes sakuraFloat {
            0% { transform: translateY(0) rotate(0deg); opacity: 0; }
            10% { opacity: 0.8; }
            90% { opacity: 0.8; }
            100% { transform: translateY(-100vh) rotate(360deg); opacity: 0; }
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            100% { transform: scale(1.3); opacity: 0; }
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            overflow: hidden;
            height: 100vh;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            position: relative;
        }
        .sakura-bg {
            position: fixed;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        .sakura-leaf {
            position: absolute;
            pointer-events: none;
            font-size: 22px;
            animation: sakuraFloat linear forwards;
        }
        .container {
            display: flex;
            height: 100vh;
            position: relative;
            z-index: 1;
        }
        .sidebar {
            width: 340px;
            background: rgba(30, 40, 50, 0.45);
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255,255,255,0.1);
            display: flex;
            flex-direction: column;
            transition: transform 0.3s;
        }
        @media (max-width: 768px) {
            .sidebar {
                position: absolute;
                left: 0;
                top: 0;
                height: 100%;
                z-index: 100;
                transform: translateX(-100%);
                width: 85%;
            }
            .sidebar.open { transform: translateX(0); }
            .chat-area { width: 100%; }
        }
        .top-bar {
            padding: 18px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .top-bar h2 { color: #ff6b6b; font-size: 24px; }
        .top-icons { display: flex; gap: 18px; }
        .top-icons button {
            background: none;
            border: none;
            color: white;
            font-size: 22px;
            cursor: pointer;
        }
        .profile {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 18px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .avatar {
            width: 55px;
            height: 55px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 22px;
        }
        .search-box { padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .search-box input {
            width: 100%;
            padding: 14px 18px;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 16px;
        }
        .tabs { display: flex; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .tab {
            flex: 1;
            text-align: center;
            padding: 14px;
            cursor: pointer;
            color: rgba(255,255,255,0.6);
            font-size: 15px;
        }
        .tab.active { color: #ff6b6b; border-bottom: 2px solid #ff6b6b; }
        .users-list, .groups-list, .favorites-list, .secret-list {
            flex: 1;
            overflow-y: auto;
            display: none;
        }
        .users-list.active, .groups-list.active, .favorites-list.active, .secret-list.active { display: block; }
        .user-item, .group-item, .favorite-item, .secret-item {
            padding: 14px 16px;
            display: flex;
            align-items: center;
            gap: 14px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .user-item:hover, .group-item:hover { background: rgba(255,255,255,0.08); }
        .user-avatar, .group-avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .user-info { flex: 1; }
        .user-name { font-weight: 600; font-size: 17px; }
        .user-status { font-size: 12px; color: #4ecdc4; }
        .create-btn {
            background: rgba(255,107,107,0.3);
            margin: 12px;
            padding: 12px;
            text-align: center;
            border-radius: 30px;
            cursor: pointer;
        }
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: rgba(10, 20, 30, 0.4);
            backdrop-filter: blur(8px);
        }
        .chat-header {
            padding: 15px 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            background: rgba(30,40,50,0.3);
        }
        .back-btn {
            background: none;
            border: none;
            color: white;
            font-size: 28px;
            cursor: pointer;
            display: none;
        }
        @media (max-width: 768px) { .back-btn { display: block; } }
        .chat-user { flex: 1; }
        .chat-user-name { font-weight: 600; font-size: 20px; }
        .chat-actions { display: flex; gap: 15px; }
        .chat-actions button {
            background: none;
            border: none;
            color: white;
            font-size: 22px;
            cursor: pointer;
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message {
            display: flex;
            flex-direction: column;
            max-width: 75%;
            position: relative;
        }
        .message.sent { align-self: flex-end; }
        .message.received { align-self: flex-start; }
        .message-bubble {
            padding: 12px 18px;
            border-radius: 24px;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(5px);
            font-size: 16px;
            word-break: break-word;
        }
        .message.sent .message-bubble {
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
        }
        .message.secret .message-bubble {
            background: linear-gradient(135deg, #4ecdc4, #44a08d);
        }
        .message-time { font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 5px; margin-left: 12px; }
        .message-actions {
            position: absolute;
            top: -20px;
            right: 0;
            display: none;
            gap: 8px;
            background: rgba(0,0,0,0.6);
            padding: 5px 10px;
            border-radius: 20px;
        }
        .message:hover .message-actions { display: flex; }
        .message-actions button {
            background: none;
            border: none;
            color: white;
            font-size: 14px;
            cursor: pointer;
        }
        .reactions {
            display: flex;
            gap: 5px;
            margin-top: 5px;
        }
        .reaction {
            background: rgba(255,255,255,0.15);
            border-radius: 20px;
            padding: 2px 8px;
            font-size: 12px;
            cursor: pointer;
        }
        .message-input {
            padding: 15px 20px;
            display: flex;
            gap: 12px;
            border-top: 1px solid rgba(255,255,255,0.1);
            background: rgba(30,40,50,0.5);
        }
        .message-input input {
            flex: 1;
            padding: 14px 18px;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 16px;
        }
        .message-input button {
            padding: 14px 22px;
            background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
            border: none;
            border-radius: 30px;
            color: white;
            cursor: pointer;
            font-size: 18px;
        }
        .attach-menu { position: relative; }
        .attach-options {
            position: absolute;
            bottom: 60px;
            left: 0;
            background: rgba(30,40,50,0.95);
            backdrop-filter: blur(20px);
            border-radius: 30px;
            padding: 12px;
            display: none;
            gap: 12px;
        }
        .attach-options.active { display: flex; }
        .attach-options button {
            background: rgba(255,255,255,0.15);
            border: none;
            border-radius: 25px;
            padding: 12px 18px;
            color: white;
            cursor: pointer;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: rgba(30,40,50,0.96);
            backdrop-filter: blur(20px);
            border-radius: 40px;
            padding: 30px;
            width: 90%;
            max-width: 420px;
        }
        .modal-content h3 { color: #ff6b6b; margin-bottom: 25px; font-size: 24px; }
        .modal-content input, .modal-content select {
            width: 100%;
            padding: 16px;
            margin-bottom: 18px;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 30px;
            color: white;
            font-size: 16px;
        }
        .modal-buttons { display: flex; gap: 15px; margin-top: 20px; }
        .modal-buttons button {
            flex: 1;
            padding: 14px;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            font-size: 16px;
        }
        .save-btn { background: #ff6b6b; color: white; }
        .cancel-btn { background: rgba(255,255,255,0.15); color: white; }
        .danger-btn { background: #f44336; color: white; }
        .call-notification {
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: #ff6b6b;
            padding: 18px 30px;
            border-radius: 60px;
            display: none;
            z-index: 1000;
            text-align: center;
        }
        .recording {
            position: fixed;
            bottom: 120px;
            left: 50%;
            transform: translateX(-50%);
            background: #ff4444;
            padding: 15px 25px;
            border-radius: 50px;
            display: none;
            z-index: 1000;
            animation: pulse 1s infinite;
        }
        .gift-item {
            display: flex;
            align-items: center;
            gap: 18px;
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            cursor: pointer;
        }
        .support-footer {
            padding: 12px;
            text-align: center;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 12px;
            color: rgba(255,255,255,0.4);
        }
        .support-footer a { color: #ff6b6b; text-decoration: none; }
        .context-menu {
            position: fixed;
            background: rgba(30,40,50,0.95);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 10px;
            display: none;
            z-index: 1000;
        }
        .context-menu button {
            display: block;
            width: 100%;
            padding: 10px 20px;
            background: none;
            border: none;
            color: white;
            text-align: left;
            cursor: pointer;
            border-radius: 10px;
        }
        .context-menu button:hover { background: rgba(255,255,255,0.1); }
    </style>
</head>
<body>
    <div class="sakura-bg" id="sakuraBg"></div>
    <div class="container">
        <div class="sidebar" id="sidebar">
            <div class="top-bar">
                <h2>SoomlingGram</h2>
                <div class="top-icons">
                    <button id="favoritesTabBtn">⭐</button>
                    <button id="secretTabBtn">🔒</button>
                    <button id="settingsTopBtn">⚙️</button>
                </div>
            </div>
            <div class="profile" id="profileBtn">
                <div class="avatar">{{ my_name[0]|upper }}</div>
                <div><div style="font-weight:600; font-size:18px">{{ my_name }}</div><div style="font-size:13px">{{ my_phone }}</div></div>
            </div>
            <div class="search-box"><input type="text" id="searchInput" placeholder="🔍 Поиск по номеру..."></div>
            <div class="tabs">
                <div class="tab active" data-tab="users">💬 Чаты</div>
                <div class="tab" data-tab="groups">👥 Группы</div>
                <div class="tab" data-tab="favorites">⭐ Избранное</div>
                <div class="tab" data-tab="secret">🔒 Секретные</div>
            </div>
            <div class="users-list active" id="usersList">
                {% for user in users %}
                <div class="user-item" data-phone="{{ user[0] }}" data-name="{{ user[1] }} {{ user[2] }}">
                    <div class="user-avatar">{{ user[1][0]|upper }}</div>
                    <div class="user-info">
                        <div class="user-name">{{ user[1] }} {{ user[2] }}</div>
                        <div class="user-status">{% if user[3] %}🟢 Онлайн{% else %}⚫ Офлайн{% endif %}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="groups-list" id="groupsList">
                <div class="create-btn" id="createGroupBtn">➕ Создать группу</div>
                {% for group in groups %}
                <div class="group-item" data-group-id="{{ group[0] }}" data-group-name="{{ group[1] }}">
                    <div class="group-avatar">{{ group[1][0]|upper }}</div>
                    <div>{{ group[1] }}</div>
                </div>
                {% endfor %}
            </div>
            <div class="favorites-list" id="favoritesList">
                {% for fav in favorites %}
                <div class="favorite-item" data-phone="{{ fav[0] }}" data-name="{{ fav[1] }} {{ fav[2] }}">
                    <div class="user-avatar">{{ fav[1][0]|upper }}</div>
                    <div>{{ fav[1] }} {{ fav[2] }}</div>
                </div>
                {% endfor %}
            </div>
            <div class="secret-list" id="secretList">
                {% for secret in secret_chats %}
                <div class="secret-item" data-phone="{{ secret[0] }}" data-name="{{ secret[1] }} {{ secret[2] }}">
                    <div class="user-avatar">🔒</div>
                    <div>{{ secret[1] }} {{ secret[2] }}</div>
                </div>
                {% endfor %}
            </div>
            <div class="support-footer">📞 Поддержка: <a href="tel:89996081231">8-999-608-12-31</a></div>
        </div>
        <div class="chat-area">
            <div class="chat-header">
                <button class="back-btn" id="backBtn">←</button>
                <div class="chat-user"><div class="chat-user-name" id="chatUserName">Выберите чат</div></div>
                <div class="chat-actions">
                    <button id="callBtn" style="display:none;">📞</button>
                    <button id="giftBtn" style="display:none;">🎁</button>
                    <button id="infoBtn" style="display:none;">ℹ️</button>
                </div>
            </div>
            <div class="messages" id="messages"></div>
            <div class="recording" id="recordingIndicator">🎙️ Запись...</div>
            <div class="message-input">
                <div class="attach-menu">
                    <button id="attachBtn" style="background:rgba(255,255,255,0.1); padding:12px 18px; border-radius:30px;">📎</button>
                    <div class="attach-options" id="attachOptions">
                        <button id="fileBtn">📁 Файл</button>
                        <button id="voiceBtn">🎙️ Кружок</button>
                        <button id="photoBtn">📸 Фото</button>
                    </div>
                </div>
                <input type="text" id="messageInput" placeholder="Сообщение...">
                <button id="sendBtn">➤</button>
            </div>
        </div>
    </div>

    <div class="modal" id="settingsModal">
        <div class="modal-content">
            <h3>⚙️ Настройки</h3>
            <input type="text" id="firstNameInput" placeholder="Имя" value="{{ first_name }}">
            <input type="text" id="lastNameInput" placeholder="Фамилия" value="{{ last_name }}">
            <select id="fontSizeSelect">
                <option value="14">Маленький шрифт</option>
                <option value="16" selected>Средний шрифт</option>
                <option value="18">Большой шрифт</option>
                <option value="20">Очень большой</option>
            </select>
            <div style="margin: 15px 0;">
                <label><input type="checkbox" id="soundToggle"> 🔊 Звук уведомлений</label>
            </div>
            <div style="margin: 15px 0;">
                <label><input type="checkbox" id="notificationsToggle"> 🔔 Push-уведомления</label>
            </div>
            <div class="modal-buttons">
                <button id="saveSettingsBtn" class="save-btn">Сохранить</button>
                <button id="closeSettingsBtn" class="cancel-btn">Закрыть</button>
            </div>
        </div>
    </div>

    <div class="modal" id="chatInfoModal">
        <div class="modal-content">
            <h3>ℹ️ Информация</h3>
            <div id="chatInfoContent"></div>
            <button id="blockUserBtn" class="danger-btn" style="margin-top:15px">🚫 Заблокировать</button>
            <button id="clearChatBtn" class="danger-btn" style="margin-top:10px">🗑️ Очистить историю</button>
            <button id="closeInfoBtn" class="cancel-btn" style="margin-top:15px">Закрыть</button>
        </div>
    </div>

    <div class="modal" id="giftModal">
        <div class="modal-content">
            <h3>🎁 Магазин подарков</h3>
            <div style="text-align:center;margin-bottom:18px">💰 Монет: <span id="coinBalance">{{ coins }}</span></div>
            <div id="giftsList"></div>
            <button id="closeGiftBtn" class="cancel-btn" style="margin-top:18px">Закрыть</button>
        </div>
    </div>

    <div class="modal" id="groupModal">
        <div class="modal-content">
            <h3>👥 Создать группу</h3>
            <input type="text" id="groupNameInput" placeholder="Название группы">
            <div class="modal-buttons">
                <button id="confirmGroupBtn" class="save-btn">Создать</button>
                <button id="closeGroupBtn" class="cancel-btn">Отмена</button>
            </div>
        </div>
    </div>

    <div class="call-notification" id="callNotification">
        <div id="callerName">Звонит...</div>
        <div style="display:flex;gap:12px;margin-top:12px">
            <button id="acceptCall" style="background:#4caf50;padding:10px 25px;border:none;border-radius:30px">Ответить</button>
            <button id="rejectCall" style="background:#f44336;padding:10px 25px;border:none;border-radius:30px">Отклонить</button>
        </div>
    </div>

    <div class="context-menu" id="contextMenu">
        <button id="replyMsgBtn">↩️ Ответить</button>
        <button id="deleteMsgBtn">🗑️ Удалить</button>
        <button id="forwardMsgBtn">📤 Переслать</button>
    </div>

    <input type="file" id="fileInput" style="display:none">
    <input type="file" id="photoInput" style="display:none" accept="image/*">
    <audio id="audioPlayer" style="display:none"></audio>

    <script>
        const socket = io();
        let currentChat = null;
        let currentChatType = null;
        let currentChatName = null;
        let myPhone = "{{ my_phone }}";
        let myName = "{{ my_name }}";
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let replyToMsg = null;
        let contextMenuMsgId = null;
        let fontSize = 16;
        
        let settings = {{ settings_json|safe }};
        fontSize = settings.fontSize || 16;
        document.body.style.fontSize = fontSize + 'px';
        
        function createSakura() {
            let bg = document.getElementById('sakuraBg');
            for(let i=0;i<15;i++){
                let s=document.createElement('div');
                s.className='sakura-leaf';
                s.innerHTML='🌸';
                s.style.left=Math.random()*100+'%';
                s.style.animationDuration=6+Math.random()*12+'s';
                s.style.animationDelay=Math.random()*15+'s';
                s.style.fontSize=18+Math.random()*28+'px';
                bg.appendChild(s);
                setTimeout(()=>s.remove(), 20000);
            }
        }
        createSakura();
        setInterval(createSakura, 4000);
        
        function escapeHtml(t){ let d=document.createElement('div'); d.textContent=t; return d.innerHTML; }
        
        function addMessage(msgId, text, isSent, time, isFile=false, fileUrl=null, isVoice=false, isSecret=false, replyText=null){
            let container=document.getElementById('messages');
            let div=document.createElement('div');
            div.className=`message ${isSent ? 'sent' : 'received'} ${isSecret ? 'secret' : ''}`;
            div.dataset.msgId = msgId;
            let content='';
            if(replyText){
                content+=`<div style="font-size:12px;color:#aaa;margin-bottom:5px">↩️ Ответ: ${escapeHtml(replyText.substring(0,50))}</div>`;
            }
            if(isFile && fileUrl){
                content+=`<div class="file-message">📁 <a href="${fileUrl}" download style="color:white">${escapeHtml(text)}</a></div>`;
            } else if(isVoice && fileUrl){
                content+=`<div class="voice-message" onclick="document.getElementById('audioPlayer').src='${fileUrl}'; document.getElementById('audioPlayer').play()">
                    <div class="voice-play">🎙️</div>
                    <div>Голосовое сообщение</div>
                </div>`;
            } else {
                content+=`<div class="message-bubble">${escapeHtml(text)}</div>`;
            }
            content+=`<div class="message-time">${time} ${isSecret ? '🔒' : ''}</div>`;
            content+=`<div class="message-actions">
                <button onclick="replyToMessage(${msgId}, '${escapeHtml(text).replace(/'/g, "\\'")}')">↩️</button>
                <button onclick="deleteMessage(${msgId})">🗑️</button>
                <button onclick="forwardMessage(${msgId}, '${escapeHtml(text).replace(/'/g, "\\'")}')">📤</button>
            </div>`;
            div.innerHTML=content;
            container.appendChild(div);
            div.scrollIntoView();
        }
        
        function replyToMessage(msgId, text){
            replyToMsg = {id: msgId, text: text};
            document.getElementById('messageInput').placeholder = `↩️ Ответ: ${text.substring(0,30)}...`;
        }
        
        function deleteMessage(msgId){
            if(confirm('Удалить сообщение?')){
                fetch('/delete_message', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg_id:msgId, type:currentChatType})}).then(()=>{
                    let msgDiv = document.querySelector(`.message[data-msg-id="${msgId}"]`);
                    if(msgDiv) msgDiv.remove();
                });
            }
        }
        
        function forwardMessage(msgId, text){
            let toUser = prompt('Введите номер получателя:');
            if(toUser){
                fetch('/forward_message', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg_id:msgId, to:toUser, text:text})}).then(()=>{
                    alert('Сообщение переслано!');
                });
            }
        }
        
        function loadUserMessages(phone, name, isSecret=false){
            if(phone === myPhone){ alert("Нельзя писать самому себе"); return; }
            currentChat = phone;
            currentChatType = 'user';
            currentChatName = name;
            document.getElementById('chatUserName').innerHTML = name + (isSecret ? ' 🔒' : '');
            document.getElementById('callBtn').style.display = isSecret ? 'none' : 'block';
            document.getElementById('giftBtn').style.display = isSecret ? 'none' : 'block';
            document.getElementById('infoBtn').style.display = 'block';
            let url = isSecret ? `/get_secret_messages/${phone}` : `/get_messages/${phone}`;
            fetch(url).then(r=>r.json()).then(data=>{
                let c=document.getElementById('messages');
                c.innerHTML='';
                data.forEach(msg=>addMessage(msg[0], msg[1], msg[2]===myPhone, msg[3], msg[4], msg[5], msg[6], isSecret, msg[7]));
            });
            if(window.innerWidth<=768) closeSidebar();
        }
        
        function loadGroupMessages(id, name){
            currentChat = id;
            currentChatType = 'group';
            currentChatName = name;
            document.getElementById('chatUserName').innerHTML = name;
            document.getElementById('callBtn').style.display = 'none';
            document.getElementById('giftBtn').style.display = 'block';
            document.getElementById('infoBtn').style.display = 'block';
            fetch(`/get_group_messages/${id}`).then(r=>r.json()).then(data=>{
                let c=document.getElementById('messages');
                c.innerHTML='';
                data.forEach(msg=>addMessage(msg[0], `${msg[1]}: ${msg[2]}`, msg[3]===myPhone, msg[4], msg[5], msg[6]));
            });
            if(window.innerWidth<=768) closeSidebar();
        }
        
        function sendMessage(){
            let input=document.getElementById('messageInput');
            let text=input.value.trim();
            if(!text || !currentChat) return;
            if(currentChatType === 'user'){
                let isSecret = document.getElementById('chatUserName').innerHTML.includes('🔒');
                let replyId = replyToMsg ? replyToMsg.id : null;
                socket.emit('send_message', {to: currentChat, message: text, is_secret: isSecret, reply_to: replyId});
                addMessage(Date.now(), text, true, new Date().toLocaleTimeString(), false, null, false, isSecret);
            } else if(currentChatType === 'group'){
                socket.emit('send_group_message', {group_id: currentChat, message: text});
                addMessage(Date.now(), `${myName}: ${text}`, true, new Date().toLocaleTimeString());
            }
            input.value='';
            replyToMsg = null;
            document.getElementById('messageInput').placeholder = 'Сообщение...';
        }
        
        function sendFile(file, isVoice=false){
            if(!currentChat) return;
            let fd=new FormData();
            fd.append('file', file);
            fd.append('to', currentChat);
            fd.append('type', currentChatType);
            fd.append('is_voice', isVoice);
            fetch('/upload_file', {method:'POST', body:fd}).then(r=>r.json()).then(data=>{
                if(data.url){
                    if(currentChatType === 'user'){
                        socket.emit('send_message', {to: currentChat, message: file.name, is_file: true, file_url: data.url, is_voice: isVoice});
                    } else {
                        socket.emit('send_group_message', {group_id: currentChat, message: file.name, is_file: true, file_url: data.url});
                    }
                    addMessage(Date.now(), file.name, true, new Date().toLocaleTimeString(), true, data.url, isVoice);
                }
            });
        }
        
        document.getElementById('sendBtn').onclick = sendMessage;
        document.getElementById('messageInput').onkeypress = e => { if(e.key==='Enter') sendMessage(); };
        
        document.getElementById('attachBtn').onclick = ()=>{
            document.getElementById('attachOptions').classList.toggle('active');
        };
        document.getElementById('fileBtn').onclick = ()=>{
            document.getElementById('fileInput').click();
            document.getElementById('attachOptions').classList.remove('active');
        };
        document.getElementById('photoBtn').onclick = ()=>{
            document.getElementById('photoInput').click();
            document.getElementById('attachOptions').classList.remove('active');
        };
        document.getElementById('voiceBtn').onclick = ()=>{
            if(isRecording){
                mediaRecorder.stop();
                isRecording=false;
                document.getElementById('recordingIndicator').style.display='none';
            } else {
                navigator.mediaDevices.getUserMedia({ audio: true }).then(stream=>{
                    mediaRecorder=new MediaRecorder(stream);
                    audioChunks=[];
                    mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);
                    mediaRecorder.onstop=()=>{
                        let blob=new Blob(audioChunks, {type:'audio/webm'});
                        let file=new File([blob], `voice_${Date.now()}.webm`, {type:'audio/webm'});
                        sendFile(file, true);
                        stream.getTracks().forEach(t=>t.stop());
                    };
                    mediaRecorder.start();
                    isRecording=true;
                    document.getElementById('recordingIndicator').style.display='block';
                    setTimeout(()=>{
                        if(isRecording){
                            mediaRecorder.stop();
                            isRecording=false;
                            document.getElementById('recordingIndicator').style.display='none';
                        }
                    }, 30000);
                });
            }
            document.getElementById('attachOptions').classList.remove('active');
        };
        
        document.getElementById('fileInput').onchange = e => { if(e.target.files[0]) sendFile(e.target.files[0]); };
        document.getElementById('photoInput').onchange = e => { if(e.target.files[0]) sendFile(e.target.files[0]); };
        
        socket.on('receive_message', (data) => {
            if(currentChatType === 'user' && currentChat === data.from){
                addMessage(data.msg_id, data.message, false, data.timestamp, data.is_file, data.file_url, data.is_voice, data.is_secret, data.reply_text);
                if(settings.sound) new Audio('/static/ding.mp3').play().catch(e=>console.log);
            }
        });
        socket.on('receive_group_message', (data) => {
            if(currentChatType === 'group' && currentChat == data.group_id){
                addMessage(data.msg_id, `${data.from_name}: ${data.message}`, false, data.timestamp, data.is_file, data.file_url);
            }
        });
        
        function selectUser(phone, name){ loadUserMessages(phone, name); }
        function selectGroup(id, name){ loadGroupMessages(id, name); }
        
        document.querySelectorAll('.user-item').forEach(el=>{
            el.onclick=()=>selectUser(el.dataset.phone, el.dataset.name);
        });
        document.querySelectorAll('.group-item').forEach(el=>{
            el.onclick=()=>selectGroup(el.dataset.groupId, el.dataset.groupName);
        });
        document.querySelectorAll('.favorite-item, .secret-item').forEach(el=>{
            el.onclick=()=>selectUser(el.dataset.phone, el.dataset.name);
        });
        
        document.getElementById('searchInput').oninput = (e) => {
            let q=e.target.value;
            if(q.length<2) return;
            fetch(`/search_by_phone?q=${q}`).then(r=>r.json()).then(users=>{
                let list=document.getElementById('usersList');
                list.innerHTML='';
                users.forEach(u=>{
                    let div=document.createElement('div');
                    div.className='user-item';
                    div.dataset.phone=u[0];
                    div.dataset.name=`${u[1]} ${u[2]}`;
                    div.innerHTML=`<div class="user-avatar">${u[1][0].toUpperCase()}</div><div class="user-info"><div class="user-name">${escapeHtml(u[1])} ${escapeHtml(u[2])}</div><div class="user-status">📱 ${u[0]}</div></div>`;
                    div.onclick=()=>selectUser(u[0], `${u[1]} ${u[2]}`);
                    list.appendChild(div);
                });
            });
        };
        
        document.querySelectorAll('.tab').forEach(tab=>{
            tab.onclick=()=>{
                document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
                tab.classList.add('active');
                let target=tab.dataset.tab;
                document.querySelectorAll('.users-list, .groups-list, .favorites-list, .secret-list').forEach(l=>l.classList.remove('active'));
                document.getElementById(`${target}List`).classList.add('active');
            };
        });
        
        let settingsModal=document.getElementById('settingsModal');
        document.getElementById('settingsTopBtn').onclick = () => settingsModal.classList.add('active');
        document.getElementById('profileBtn').onclick = () => settingsModal.classList.add('active');
        document.getElementById('closeSettingsBtn').onclick = () => settingsModal.classList.remove('active');
        
        document.getElementById('saveSettingsBtn').onclick = () => {
            let fn=document.getElementById('firstNameInput').value.trim();
            let ln=document.getElementById('lastNameInput').value.trim();
            let fontSizeVal=document.getElementById('fontSizeSelect').value;
            let sound=document.getElementById('soundToggle').checked;
            let notifications=document.getElementById('notificationsToggle').checked;
            fetch('/update_profile', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({first_name:fn, last_name:ln, settings:{fontSize:parseInt(fontSizeVal), sound:sound, notifications:notifications}})}).then(()=>location.reload());
        };
        
        document.getElementById('infoBtn').onclick = () => {
            let modal=document.getElementById('chatInfoModal');
            document.getElementById('chatInfoContent').innerHTML = `
                <p><strong>Имя:</strong> ${currentChatName}</p>
                <p><strong>ID:</strong> ${currentChat}</p>
                <p><strong>Тип:</strong> ${currentChatType === 'user' ? 'Личный чат' : 'Группа'}</p>
            `;
            modal.classList.add('active');
        };
        
        document.getElementById('blockUserBtn').onclick = () => {
            if(currentChatType === 'user' && confirm('Заблокировать пользователя?')){
                fetch('/block_user', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:currentChat})}).then(()=>alert('Пользователь заблокирован'));
            }
            document.getElementById('chatInfoModal').classList.remove('active');
        };
        
        document.getElementById('clearChatBtn').onclick = () => {
            if(confirm('Очистить всю историю чата?')){
                fetch('/clear_chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({with_user:currentChat, type:currentChatType})}).then(()=>{
                    document.getElementById('messages').innerHTML='';
                });
            }
            document.getElementById('chatInfoModal').classList.remove('active');
        };
        
        document.getElementById('closeInfoBtn').onclick = () => document.getElementById('chatInfoModal').classList.remove('active');
        
        document.getElementById('giftBtn').onclick = () => {
            fetch('/get_gifts').then(r=>r.json()).then(data=>{
                let list=document.getElementById('giftsList');
                list.innerHTML='';
                data.gifts.forEach(g=>{
                    let div=document.createElement('div');
                    div.className='gift-item';
                    div.innerHTML=`<div style="font-size:36px">${g.emoji}</div><div><div>${g.name}</div><div>${g.price} монет</div></div>`;
                    div.onclick=()=>{
                        fetch('/send_gift', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:currentChat, gift_id:g.id, type:currentChatType})}).then(r=>r.json()).then(res=>{
                            if(res.success) alert('Подарок отправлен!');
                            else alert('Недостаточно монет');
                        });
                    };
                    list.appendChild(div);
                });
            });
            document.getElementById('giftModal').classList.add('active');
        };
        document.getElementById('closeGiftBtn').onclick = () => document.getElementById('giftModal').classList.remove('active');
        
        let groupModal=document.getElementById('groupModal');
        document.getElementById('createGroupBtn').onclick = () => groupModal.classList.add('active');
        document.getElementById('closeGroupBtn').onclick = () => groupModal.classList.remove('active');
        document.getElementById('confirmGroupBtn').onclick = () => {
            let name=document.getElementById('groupNameInput').value.trim();
            if(name) fetch('/create_group', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}).then(()=>location.reload());
        };
        
        document.getElementById('callBtn').onclick = () => {
            if(currentChat){ socket.emit('call_user', {to: currentChat}); alert('Звоним...'); }
        };
        socket.on('incoming_call', (data)=>{
            document.getElementById('callerName').innerHTML=`${data.from_name} звонит...`;
            document.getElementById('callNotification').style.display='block';
            window.callFrom=data.from;
        });
        document.getElementById('acceptCall').onclick = () => {
            document.getElementById('callNotification').style.display='none';
            socket.emit('accept_call', {to: window.callFrom});
            alert('Звонок начат');
        };
        document.getElementById('rejectCall').onclick = () => document.getElementById('callNotification').style.display='none';
        
        socket.emit('join');
        function closeSidebar(){ document.getElementById('sidebar').classList.remove('open'); }
        document.getElementById('backBtn').onclick = () => { if(window.innerWidth<=768) document.getElementById('sidebar').classList.add('open'); };
        
        socket.on('user_status', (data) => {
            let ui=document.querySelector(`.user-item[data-phone="${data.phone}"]`);
            if(ui){ let sd=ui.querySelector('.user-status'); sd.innerHTML=data.online ? '🟢 Онлайн' : '⚫ Офлайн'; }
        });
        
        document.getElementById('favoritesTabBtn').onclick = () => document.querySelector('.tab[data-tab="favorites"]').click();
        document.getElementById('secretTabBtn').onclick = () => document.querySelector('.tab[data-tab="secret"]').click();
    </script>
</body>
</html>
'''

# === РОУТЫ ===
@app.route('/')
def index():
    if 'phone' in session:
        return redirect(url_for('chat'))
    return render_template_string(LOGIN_PAGE)

@app.route('/send_sms_code', methods=['POST'])
def send_sms_code():
    phone = request.form['phone']
    code = str(random.randint(100000, 999999))
    session['reg_phone'] = phone
    session['reg_code'] = code
    send_sms(phone, code)
    return render_template_string(CODE_PAGE)

@app.route('/verify_sms_code', methods=['POST'])
def verify_sms_code():
    if request.form['code'] != session.get('reg_code'):
        return render_template_string(CODE_PAGE, error="Неверный код")
    phone = session.get('reg_phone')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT first_name, last_name FROM users WHERE phone=?", (phone,))
    user = c.fetchone()
    if user:
        session['phone'] = phone
        session['first_name'] = user[0]
        session['last_name'] = user[1]
        conn.close()
        return redirect(url_for('chat'))
    else:
        conn.close()
        return render_template_string(REGISTER_PAGE)

@app.route('/complete_register', methods=['POST'])
def complete_register():
    phone = session.get('reg_phone')
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form.get('email', '')
    password = hash_pass(request.form['password'])
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (phone, email, first_name, last_name, password) VALUES (?, ?, ?, ?, ?)", (phone, email, first_name, last_name, password))
        conn.commit()
        session['phone'] = phone
        session['first_name'] = first_name
        session['last_name'] = last_name
        conn.close()
        return redirect(url_for('chat'))
    except:
        conn.close()
        return render_template_string(REGISTER_PAGE, error="Ошибка регистрации")

@app.route('/chat')
def chat():
    if 'phone' not in session:
        return redirect(url_for('index'))
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT phone, first_name, last_name, online FROM users WHERE phone != ?", (session['phone'],))
    users = c.fetchall()
    c.execute("SELECT id, name FROM groups")
    groups = c.fetchall()
    c.execute("SELECT favorites FROM users WHERE phone=?", (session['phone'],))
    favs = json.loads(c.fetchone()[0] or '[]')
    fav_users = []
    for fav in favs:
        c.execute("SELECT phone, first_name, last_name FROM users WHERE phone=?", (fav,))
        u = c.fetchone()
        if u: fav_users.append(u)
    c.execute("SELECT coins, settings FROM users WHERE phone=?", (session['phone'],))
    row = c.fetchone()
    coins = row[0] if row else 100
    settings = json.loads(row[1]) if row and row[1] else {"sound": True, "notifications": True, "fontSize": 16}
    c.execute("SELECT phone, first_name, last_name FROM users WHERE phone != ?", (session['phone'],))
    secret_users = c.fetchall()
    conn.close()
    return render_template_string(CHAT_PAGE, users=users, groups=groups, favorites=fav_users, favorites_json=json.dumps(favs), secret_chats=secret_users, my_phone=session['phone'], my_name=f"{session['first_name']} {session['last_name']}", first_name=session['first_name'], last_name=session['last_name'], coins=coins, settings_json=json.dumps(settings))

@app.route('/get_messages/<to_phone>')
def get_messages(to_phone):
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT id, message, from_user, timestamp, is_file, file_url, is_voice, reply_to FROM messages WHERE ((from_user=? AND to_user=?) OR (from_user=? AND to_user=?)) AND is_secret=0 AND deleted=0 ORDER BY id", (session['phone'], to_phone, to_phone, session['phone']))
    msgs = c.fetchall()
    result = []
    for msg in msgs:
        reply_text = None
        if msg[7]:
            c.execute("SELECT message FROM messages WHERE id=?", (msg[7],))
            reply = c.fetchone()
            if reply: reply_text = reply[0]
        result.append([msg[0], msg[1], msg[2], msg[3], msg[4], msg[5], msg[6], reply_text])
    conn.close()
    return jsonify(result)

@app.route('/get_secret_messages/<to_phone>')
def get_secret_messages(to_phone):
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT id, message, from_user, timestamp, is_file, file_url, is_voice, reply_to FROM messages WHERE ((from_user=? AND to_user=?) OR (from_user=? AND to_user=?)) AND is_secret=1 AND deleted=0 ORDER BY id", (session['phone'], to_phone, to_phone, session['phone']))
    msgs = c.fetchall()
    result = []
    for msg in msgs:
        reply_text = None
        if msg[7]:
            c.execute("SELECT message FROM messages WHERE id=?", (msg[7],))
            reply = c.fetchone()
            if reply: reply_text = reply[0]
        result.append([msg[0], msg[1], msg[2], msg[3], msg[4], msg[5], msg[6], reply_text])
    conn.close()
    return jsonify(result)

@app.route('/get_group_messages/<group_id>')
def get_group_messages(group_id):
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT id, from_name, message, from_user, timestamp, is_file, file_url FROM group_messages WHERE group_id=? AND deleted=0 ORDER BY id", (group_id,))
    msgs = c.fetchall()
    result = [[m[0], m[1], m[2], m[3], m[4], m[5], m[6]] for m in msgs]
    conn.close()
    return jsonify(result)

@app.route('/search_by_phone')
def search_by_phone():
    q = request.args.get('q', '')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT phone, first_name, last_name FROM users WHERE phone LIKE ? AND phone != ? LIMIT 20", (f'%{q}%', session['phone']))
    users = c.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    fn = request.json.get('first_name')
    ln = request.json.get('last_name')
    settings = request.json.get('settings')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    if settings:
        c.execute("UPDATE users SET first_name=?, last_name=?, settings=? WHERE phone=?", (fn, ln, json.dumps(settings), session['phone']))
    else:
        c.execute("UPDATE users SET first_name=?, last_name=? WHERE phone=?", (fn, ln, session['phone']))
    conn.commit()
    conn.close()
    session['first_name'] = fn
    session['last_name'] = ln
    return jsonify({'status': 'ok'})

@app.route('/block_user', methods=['POST'])
def block_user():
    user = request.json.get('user')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT blocked FROM users WHERE phone=?", (session['phone'],))
    blocked = json.loads(c.fetchone()[0] or '[]')
    if user not in blocked:
        blocked.append(user)
        c.execute("UPDATE users SET blocked=? WHERE phone=?", (json.dumps(blocked), session['phone']))
        conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    with_user = request.json.get('with_user')
    chat_type = request.json.get('type')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    if chat_type == 'user':
        c.execute("UPDATE messages SET deleted=1 WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)", (session['phone'], with_user, with_user, session['phone']))
    else:
        c.execute("UPDATE group_messages SET deleted=1 WHERE group_id=?", (with_user,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/delete_message', methods=['POST'])
def delete_message():
    msg_id = request.json.get('msg_id')
    msg_type = request.json.get('type')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    if msg_type == 'user':
        c.execute("UPDATE messages SET deleted=1 WHERE id=?", (msg_id,))
    else:
        c.execute("UPDATE group_messages SET deleted=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/forward_message', methods=['POST'])
def forward_message():
    msg_id = request.json.get('msg_id')
    to = request.json.get('to')
    text = request.json.get('text')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_user, message, timestamp) VALUES (?, ?, ?, ?)", (session['phone'], to, f"[Переслано] {text}", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    socketio.emit('receive_message', {'from': session['phone'], 'message': f"[Переслано] {text}", 'timestamp': datetime.now().strftime("%H:%M:%S")}, room=to)
    return jsonify({'status': 'ok'})

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'})
    file = request.files['file']
    if file.filename:
        ext = file.filename.split('.')[-1]
        filename = secure_filename(f"{datetime.now().timestamp()}.{ext}")
        folder = 'static/uploads'
        if request.form.get('is_voice') == 'true':
            folder = 'static/voice'
        file.save(os.path.join(folder, filename))
        return jsonify({'url': f'/{folder}/{filename}'})
    return jsonify({'error': 'Upload failed'})

@app.route('/create_group', methods=['POST'])
def create_group():
    name = request.json.get('name')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("INSERT INTO groups (name, creator, members) VALUES (?, ?, ?)", (name, session['phone'], json.dumps([session['phone']])))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/get_gifts')
def get_gifts():
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT id, name, emoji, price FROM gifts")
    gifts = [{'id': r[0], 'name': r[1], 'emoji': r[2], 'price': r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({'gifts': gifts})

@app.route('/send_gift', methods=['POST'])
def send_gift():
    to = request.json.get('to')
    gift_id = request.json.get('gift_id')
    chat_type = request.json.get('type')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE phone=?", (session['phone'],))
    coins = c.fetchone()[0]
    c.execute("SELECT name, emoji, price FROM gifts WHERE id=?", (gift_id,))
    gift = c.fetchone()
    if coins >= gift[2]:
        c.execute("UPDATE users SET coins=coins-? WHERE phone=?", (gift[2], session['phone']))
        msg_text = f"🎁 Подарок: {gift[0]} {gift[1]} 🎁"
        if chat_type == 'user':
            c.execute("INSERT INTO messages (from_user, to_user, message, timestamp) VALUES (?, ?, ?, ?)", (session['phone'], to, msg_text, datetime.now().isoformat()))
            socketio.emit('receive_message', {'from': session['phone'], 'message': msg_text, 'timestamp': datetime.now().strftime("%H:%M:%S")}, room=to)
        else:
            c.execute("INSERT INTO group_messages (group_id, from_user, from_name, message, timestamp) VALUES (?, ?, ?, ?, ?)", (to, session['phone'], f"{session['first_name']} {session['last_name']}", msg_text, datetime.now().isoformat()))
            socketio.emit('receive_group_message', {'group_id': to, 'from_name': f"{session['first_name']} {session['last_name']}", 'message': msg_text, 'timestamp': datetime.now().strftime("%H:%M:%S")}, room=str(to))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    conn.close()
    return jsonify({'success': False})

@app.route('/get_user_status/<phone>')
def get_user_status(phone):
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("SELECT online FROM users WHERE phone=?", (phone,))
    row = c.fetchone()
    online = row[0] if row else 0
    conn.close()
    return jsonify({'online': online})

@socketio.on('join')
def handle_join():
    join_room(session['phone'])
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("UPDATE users SET online=1 WHERE phone=?", (session['phone'],))
    conn.commit()
    conn.close()
    emit('user_status', {'phone': session['phone'], 'online': True}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    to = data['to']
    if to == session['phone']: return
    msg = data['message']
    is_file = data.get('is_file', False)
    file_url = data.get('file_url', '')
    is_voice = data.get('is_voice', False)
    is_secret = data.get('is_secret', False)
    reply_to = data.get('reply_to', None)
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_user, message, timestamp, is_file, file_url, is_voice, is_secret, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
              (session['phone'], to, msg, datetime.now().isoformat(), 1 if is_file else 0, file_url, 1 if is_voice else 0, 1 if is_secret else 0, reply_to))
    msg_id = c.lastrowid
    conn.commit()
    reply_text = None
    if reply_to:
        c.execute("SELECT message FROM messages WHERE id=?", (reply_to,))
        rep = c.fetchone()
        if rep: reply_text = rep[0]
    conn.close()
    emit('receive_message', {'msg_id': msg_id, 'from': session['phone'], 'message': msg, 'timestamp': datetime.now().strftime("%H:%M:%S"), 'is_file': is_file, 'file_url': file_url, 'is_voice': is_voice, 'is_secret': is_secret, 'reply_text': reply_text}, room=to)

@socketio.on('send_group_message')
def handle_send_group_message(data):
    group_id = data['group_id']
    msg = data['message']
    is_file = data.get('is_file', False)
    file_url = data.get('file_url', '')
    conn = sqlite3.connect('soomlinggram.db')
    c = conn.cursor()
    c.execute("INSERT INTO group_messages (group_id, from_user, from_name, message, timestamp, is_file, file_url) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              (group_id, session['phone'], f"{session['first_name']} {session['last_name']}", msg, datetime.now().isoformat(), 1 if is_file else 0, file_url))
    msg_id = c.lastrowid
    conn.commit()
    c.execute("SELECT members FROM groups WHERE id=?", (group_id,))
    members = json.loads(c.fetchone()[0])
    conn.close()
    for member in members:
        emit('receive_group_message', {'msg_id': msg_id, 'group_id': group_id, 'from_name': f"{session['first_name']} {session['last_name']}", 'message': msg, 'timestamp': datetime.now().strftime("%H:%M:%S"), 'is_file': is_file, 'file_url': file_url}, room=member)

@socketio.on('call_user')
def handle_call(data):
    emit('incoming_call', {'from': session['phone'], 'from_name': f"{session['first_name']} {session['last_name']}"}, room=data['to'])

@socketio.on('accept_call')
def handle_accept(data):
    emit('call_accepted', {'from': session['phone'], 'from_name': f"{session['first_name']} {session['last_name']}"}, room=data['to'])

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)