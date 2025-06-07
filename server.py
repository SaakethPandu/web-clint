from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import sqlite3
import os
import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for REST API
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable CORS for Socket.IO

# --- Database Setup ---
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )
''')
conn.commit()

connected_users = {}  # sid -> username
CHAT_LOG_FILE = "chat_log.txt"

# --- Routes ---
@app.route("/")
def index():
    return jsonify({"status": "Server is running"})

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Missing username or password"}), 400

    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    if cursor.fetchone():
        return jsonify({"success": False, "message": "Username already exists"}), 409

    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    return jsonify({"success": True, "message": "Registration successful"})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    if cursor.fetchone():
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid username or password"}), 401

# --- Socket.IO Events ---
@socketio.on("connect")
def handle_connect():
    print("Client connected:", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    username = connected_users.pop(sid, None)
    if username:
        print(f"{username} disconnected.")
        emit("user_left", {"username": username}, broadcast=True)
        send_online_users()

@socketio.on("join")
def handle_join(data):
    username = data.get("username")
    if not username:
        return
    connected_users[request.sid] = username
    print(f"{username} joined.")
    emit("user_joined", {"username": username}, broadcast=True)
    send_online_users()

@socketio.on("message")
def handle_message(data):
    username = data.get("username")
    message = data.get("message")
    if username and message:
        log_chat(username, message)
        emit("message", {"username": username, "message": message}, broadcast=True)

def send_online_users():
    users = list(connected_users.values())
    emit("online_users", users, broadcast=True)

def log_chat(username, message):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {username}: {message}\n")

# --- Run the Server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
