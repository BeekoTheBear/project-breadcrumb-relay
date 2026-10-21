import os
import sqlite3
import time
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CLOUD_DB = "cloud_relay.db"
UPLOAD_FOLDER = "media_vault_storage"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# SECURE: Pulled strictly from environment variables
MASTER_USER = os.environ.get("MASTER_USER")
MASTER_PASS_HASH = os.environ.get("MASTER_PASS_HASH")

def init_cloud_db():
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registered_devices (
            imei TEXT PRIMARY KEY,
            make_model TEXT,
            owner_name TEXT,
            owner_email TEXT,
            unlock_credentials TEXT,
            verified INTEGER,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            device_profile TEXT DEFAULT 'Standard Android'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            command_type TEXT,
            payload TEXT,
            status TEXT DEFAULT 'PENDING',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensic_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            data_type TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            filename TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_cloud_db()

MOBILE_ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>BreadCrumb Control Center</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; --danger: #cf6679; --border: #333; }
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 10px; font-size: 14px; }
        .container { width: 100%; max-width: 600px; margin: auto; }
        .card { background: var(--card); border-radius: 10px; padding: 15px; margin-bottom: 15px; border: 1px solid var(--border); box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h2 { color: var(--primary); font-size: 18px; margin: 0 0 5px 0; }
        h3 { color: var(--accent); font-size: 15px; margin: 0 0 10px 0; border-bottom: 1px solid var(--border); padding-bottom: 5px; }
        p { margin: 5px 0; color: #aaa; font-size: 12px; }
        .device-box { background: #252525; border-radius: 8px; padding: 12px; margin-bottom: 10px; border: 1px solid #444; }
        .device-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .badge { background: var(--accent); color: #000; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .btn { background: var(--primary); color: #000; border: none; padding: 8px 12px; border-radius: 6px; font-weight: bold; cursor: pointer; text-decoration: none; font-size: 12px; flex: 1; text-align: center; min-width: 75px; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-accent { background: var(--accent); color: #000; }
        pre { background: #000; padding: 8px; border-radius: 4px; color: var(--accent); max-height: 120px; overflow-y: auto; font-size: 11px; white-space: pre-wrap; word-break: break-all; margin: 5px 0; }
        .media-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .media-thumb { background: #000; border: 1px solid #444; border-radius: 6px; padding: 4px; text-align: center; }
        .media-thumb img, .media-thumb video { width: 100%; height: 75px; object-fit: cover; border-radius: 4px; display: block; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card top-bar">
            <div>
                <h2>BreadCrumb Hub</h2>
                <p>Mobile Command & Recovery</p>
            </div>
            <a href="/logout" class="btn btn-danger" style="flex: none; padding: 6px 12px;">Logout</a>
        </div>

        <div class="card">
            <h3>📱 Managed Handsets</h3>
            {% for dev in devices %}
            <div class="device-box">
                <div class="device-header">
                    <b style="font-size: 13px; color: #fff;">{{ dev[1] }}</b>
                    <span class="badge">{{ dev[7] }}</span>
                </div>
                <p><b>ID / IMEI:</b> <code>{{ dev[0] }}</code></p>
                <p><b>Owner:</b> {{ dev[2] }} ({{ dev[3] }})</p>
                <div class="btn-group">
                    <form method="POST" action="/api/queue-command" style="flex:1;">
                        <input type="hidden" name="imei" value="{{ dev[0] }}">
                        <input type="hidden" name="command" value="LOCATE">
                        <button type="submit" class="btn btn-accent">📍 Locate</button>
                    </form>
                    <form method="POST" action="/api/queue-command" style="flex:1;">
                        <input type="hidden" name="imei" value="{{ dev[0] }}">
                        <input type="hidden" name="command" value="HARVEST_FORENSICS">
                        <button type="submit" class="btn">🕵️ Logs</button>
                    </form>
                    <form method="POST" action="/api/queue-command" style="flex:1;">
                        <input type="hidden" name="imei" value="{{ dev[0] }}">
                        <input type="hidden" name="command" value="SNAP">
                        <button type="submit" class="btn">📸 Snap</button>
                    </form>
                    <form method="POST" action="/api/queue-command" style="flex:1;">
                        <input type="hidden" name="imei" value="{{ dev[0] }}">
                        <input type="hidden" name="command" value="ALARM">
                        <button type="submit" class="btn btn-danger">🚨 Alarm</button>
                    </form>
                </div>
            </div>
            {% else %}
            <p style="text-align: center; color: #777;">No active devices synced.</p>
            {% endfor %}
        </div>

        <div class="card">
            <h3>📸 Media & Video Vault</h3>
            <div class="media-grid">
                {% for item in media_items %}
                <div class="media-thumb">
                    <a href="/media/{{ item[2] }}" target="_blank">
                        {% if item[2].endswith('.mp4') or item[2].endswith('.mov') %}
                        <video src="/media/{{ item[2] }}"></video>
                        {% else %}
                        <img src="/media/{{ item[2] }}" alt="Vault Media">
                        {% endif %}
                    </a>
                    <span style="font-size: 9px; color: #aaa; display:block; overflow:hidden; text-overflow: ellipsis; white-space: nowrap;">{{ item[3] }}</span>
                </div>
                {% else %}
                <p style="color: #777; font-size: 11px; grid-column: span 3; text-align: center;">No media captured yet.</p>
                {% endfor %}
            </div>
        </div>

        <div class="card">
            <h3>🕵️ Forensic Intelligence Logs</h3>
            {% for log in forensic_logs %}
            <div style="background: #161616; padding: 8px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #282828;">
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: #888;">
                    <span><b>{{ log[2] }}</b> (<code>{{ log[1] }}</code>)</span>
                    <span>{{ log[4] }}</span>
                </div>
                <pre>{{ log[3] }}</pre>
            </div>
            {% else %}
            <p style="text-align: center; color: #777;">No forensic logs harvested yet.</p>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Login</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 15px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 10px; width: 100%; max-width: 320px; border: 1px solid #333; }
        input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #444; background: #000; color: #fff; box-sizing: border-box; font-size: 14px; }
        button { background: #bb86fc; color: #000; border: none; padding: 12px; border-radius: 6px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: #bb86fc; text-align: center; margin-top:0;">Master Auth</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Access Portal</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def cloud_dashboard():
    if not MASTER_USER or not MASTER_PASS_HASH:
        return "<h3>[Security Configuration Error]: Master credentials not set in environment variables.</h3>", 500

    if request.cookies.get("auth") != "true":
        if request.method == 'POST':
            username = request.form.get("username")
            password = request.form.get("password")
            if username == MASTER_USER and check_password_hash(MASTER_PASS_HASH, password):
                resp = redirect(url_for('cloud_dashboard'))
                resp.set_cookie("auth", "true")
                return resp
            return render_template_string(LOGIN_TEMPLATE)
        return render_template_string(LOGIN_TEMPLATE)

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT imei, make_model, owner_name, owner_email, unlock_credentials, verified, last_seen, status, device_profile FROM registered_devices")
    devices = cursor.fetchall()
    cursor.execute("SELECT id, imei, data_type, content, timestamp FROM forensic_logs ORDER BY timestamp DESC LIMIT 25")
    forensic_logs = cursor.fetchall()
    cursor.execute("SELECT id, imei, filename, timestamp FROM media_vault ORDER BY timestamp DESC LIMIT 15")
    media_items = cursor.fetchall()
    conn.close()

    return render_template_string(MOBILE_ADMIN_TEMPLATE, devices=devices, forensic_logs=forensic_logs, media_items=media_items)

@app.route('/logout')
def logout():
    resp = redirect(url_for('cloud_dashboard'))
    resp.set_cookie("auth", "", expires=0)
    return resp

@app.route('/media/<filename>')
def serve_media(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json or {}
    imei = data.get("imei")
    if not imei: return jsonify({"error": "Missing IMEI or Device ID"}), 400
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO registered_devices (imei, make_model, owner_name, owner_email, unlock_credentials, verified, status, device_profile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (imei, data.get("make_model", "Android Agent"), "Master Operator", "jeanmichelleledeoux@gmail.com", "Set", 1, "Online", "Mobile Node"))
    conn.commit()
    conn.close()
    return jsonify({"status": "synced"})

@app.route('/api/upload-forensics', methods=['POST'])
def upload_forensics():
    data = request.json or {}
    imei = data.get("imei")
    data_type = data.get("data_type")
    content = data.get("content")
    if not imei or not data_type: return jsonify({"error": "Missing IMEI or data_type"}), 400
    
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO forensic_logs (imei, data_type, content) VALUES (?, ?, ?)", (imei, data_type, content))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route('/api/upload-media', methods=['POST'])
def upload_media():
    imei = request.form.get("imei")
    file = request.files.get("file")
    if not imei or not file: return jsonify({"error": "Missing file or IMEI"}), 400
    filename = f"{imei}_{int(time.time())}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO media_vault (imei, filename) VALUES (?, ?)", (imei, filename))
    conn.commit()
    conn.close()
    return jsonify({"status": "media_saved"})

@app.route('/api/queue-command', methods=['POST'])
def queue_command():
    if request.cookies.get("auth") != "true": return redirect(url_for('cloud_dashboard'))
    imei, cmd = request.form.get("imei"), request.form.get("command")
    if imei and cmd:
        conn = sqlite3.connect(CLOUD_DB)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pending_commands (imei, command_type) VALUES (?, ?)", (imei, cmd))
        conn.commit()
        conn.close()
    return redirect(url_for('cloud_dashboard'))

@app.route('/api/poll-commands', methods=['GET'])
def poll_commands():
    imei = request.args.get("imei")
    if not imei: return jsonify([])
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, command_type FROM pending_commands WHERE imei = ? AND status = 'PENDING'", (imei,))
    cmds = cursor.fetchall()
    if cmds:
        cmd_ids = [c[0] for c in cmds]
        cursor.execute(f"UPDATE pending_commands SET status = 'EXECUTED' WHERE id IN ({','.join(['?']*len(cmd_ids))})", tuple(cmd_ids))
        conn.commit()
    conn.close()
    return jsonify([{"id": c[0], "command": c[1]} for c in cmds])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
