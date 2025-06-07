from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import sqlite3
import os
import datetime
from collections import defaultdict

# --- Flask App and SocketIO Setup ---
app = Flask(__name__)
CORS(app)  # Enable CORS for REST API
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable CORS for Socket.IO
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")  # Accept all CORS for external client

# --- Database Setup ---
conn = sqlite3.connect('users.db', check_same_thread=False)
@@ -20,17 +21,21 @@
''')
conn.commit()

# --- Globals ---
connected_users = {}  # sid -> username
user_sockets = defaultdict(list)  # username -> list of sids
CHAT_LOG_FILE = "chat_log.txt"
PRIVATE_CHAT_LOG_FILE = "private_chat_log.txt"

# --- Routes ---
# --- Status Route ---
@app.route("/")
def index():
    return jsonify({"status": "Server is running"})
    return "✅ Flask Chat Server is Running with Socket.IO and Auth!"

# --- Auth Routes ---
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    data = request.json
username = data.get("username")
password = data.get("password")

@@ -47,7 +52,7 @@ def register():

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    data = request.json
username = data.get("username")
password = data.get("password")

@@ -59,46 +64,129 @@ def login():

# --- Socket.IO Events ---
@socketio.on("connect")
def handle_connect():
def on_connect():
print("Client connected:", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
def on_disconnect():
sid = request.sid
    username = connected_users.pop(sid, None)
    if username:
    if sid in connected_users:
        username = connected_users[sid]
print(f"{username} disconnected.")
        emit("user_left", {"username": username}, broadcast=True)
        
        # Remove this socket from user's socket list
        if username in user_sockets:
            if sid in user_sockets[username]:
                user_sockets[username].remove(sid)
            if not user_sockets[username]:  # No more sockets for this user
                del user_sockets[username]
                emit("user_left", {"username": username}, broadcast=True)
        
        del connected_users[sid]
send_online_users()

@socketio.on("join")
def handle_join(data):
def on_join(data):
username = data.get("username")
if not username:
return

connected_users[request.sid] = username
    print(f"{username} joined.")
    emit("user_joined", {"username": username}, broadcast=True)
    user_sockets[username].append(request.sid)
    
    # Only broadcast join if this is the first socket for this user
    if len(user_sockets[username]) == 1:
        print(f"{username} joined.")
        emit("user_joined", {"username": username}, broadcast=True)
    
send_online_users()

@socketio.on("message")
def handle_message(data):
def on_message(data):
username = data.get("username")
message = data.get("message")

if username and message:
log_chat(username, message)
        emit("message", {"username": username, "message": message}, broadcast=True)
        emit("message", data, broadcast=True)

@socketio.on("private_message")
def on_private_message(data):
    from_user = data.get("from")
    to_user = data.get("to")
    message = data.get("message")

    if not all([from_user, to_user, message]):
        emit("private_message_error", {"message": "Missing required fields"}, room=request.sid)
        return

    # Check if recipient is online
    if to_user not in user_sockets:
        emit("private_message_error", 
             {"message": f"{to_user} is offline"}, 
             room=request.sid)
        return

    # Prepare the message data
    message_data = {
        "from": from_user,
        "to": to_user,
        "message": message,
        "timestamp": datetime.datetime.now().isoformat()
    }

    # Log the private message
    log_private_chat(from_user, to_user, message)

    # Send to all sockets of the recipient
    for sid in user_sockets[to_user]:
        emit("private_message", message_data, room=sid)

    # Also send to sender's other sockets (for multi-device sync)
    for sid in user_sockets[from_user]:
        if sid != request.sid:  # Don't send back to the originating socket
            emit("private_message", message_data, room=sid)

    # Send to originating socket with success
    emit("private_message_sent", message_data, room=request.sid)

@socketio.on("typing")
def on_typing(data):
    username = data.get("username")
    is_typing = data.get("is_typing")
    recipient = data.get("recipient")  # For private chat typing indicators

    if not username:
        return

    if recipient:  # Private chat typing indicator
        if recipient in user_sockets:
            for sid in user_sockets[recipient]:
                emit("typing_indicator", {
                    "username": username,
                    "is_typing": is_typing
                }, room=sid)
    else:  # Public chat typing indicator
        emit("typing_indicator", {
            "username": username,
            "is_typing": is_typing
        }, broadcast=True)

def send_online_users():
    users = list(connected_users.values())
    emit("online_users", users, broadcast=True)
    user_list = list(user_sockets.keys())
    emit("online_users", user_list, broadcast=True)

def log_chat(username, message):
timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
f.write(f"{timestamp} {username}: {message}\n")

# --- Run the Server ---
def log_private_chat(from_user, to_user, message):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(PRIVATE_CHAT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {from_user} -> {to_user}: {message}\n")

# --- Run Server ---
if __name__ == "__main__":
port = int(os.environ.get("PORT", 5000))
socketio.run(app, host="0.0.0.0", port=port)
