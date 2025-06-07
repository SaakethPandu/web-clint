from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import os
import datetime

# --- Flask App and SocketIO Setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")  # Accept all CORS for external client

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

# --- Globals ---
connected_users = {}  # sid -> username
CHAT_LOG_FILE = "chat_log.txt"

# --- Status Route ---
@app.route("/")
def index():
    return "✅ Flask Chat Server is Running with Socket.IO and Auth!"

# --- Auth Routes ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
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
    data = request.json
    username = data.get("username")
    password = data.get("password")

    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    if cursor.fetchone():
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid username or password"}), 401

# --- Socket.IO Events ---
@socketio.on("connect")
def on_connect():
    print("Client connected:", request.sid)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    if sid in connected_users:
        username = connected_users[sid]
        print(f"{username} disconnected.")
        emit("user_left", {"username": username}, broadcast=True)
        del connected_users[sid]
        send_online_users()

@socketio.on("join")
def on_join(data):
    username = data.get("username")
    if not username:
        return

    connected_users[request.sid] = username
    print(f"{username} joined.")
    emit("user_joined", {"username": username}, broadcast=True)
    send_online_users()

@socketio.on("message")
def on_message(data):
    username = data.get("username")
    message = data.get("message")

    if username and message:
        log_chat(username, message)
        emit("message", data, broadcast=True)

def send_online_users():
    user_list = list(connected_users.values())
    emit("online_users", user_list, broadcast=True)

def log_chat(username, message):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {username}: {message}\n")

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
