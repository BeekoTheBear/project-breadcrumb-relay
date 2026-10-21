import os
import sys
import time
import json
import sqlite3
import subprocess
from flask import Flask, render_template_string, jsonify, send_from_directory, request

app = Flask(__name__)

BREAD_DIR = os.path.expanduser("~/BreadCrumbs")
os.makedirs(BREAD_DIR, exist_ok=True)
LOCAL_DB = os.path.join(BREAD_DIR, "breadcrumb_local.db")

def run_termux_cmd(cmd, timeout_sec=8):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if result.returncode == 0:
            return result.stdout.strip() if result.stdout.strip() else ""
        return ""
    except Exception:
        return ""

def get_device_identity():
    imei = "864190041234567"
    owner_name = "Master Operator"
    owner_email = "jeanmichelleledeoux@gmail.com"
    telephony = run_termux_cmd(["termux-telephony-deviceinfo"])
    if telephony:
        try:
            d = json.loads(telephony)
            imei = d.get("imei") or d.get("deviceId") or imei
        except: pass
    return imei, owner_name, owner_email

def init_local_db():
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_identity (
            imei TEXT PRIMARY KEY,
            owner_name TEXT,
            owner_email TEXT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Active'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS local_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imei TEXT,
            event_type TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    imei, owner_name, owner_email = get_device_identity()
    cursor.execute('''
        INSERT OR REPLACE INTO device_identity (imei, owner_name, owner_email, last_seen, status)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'Online')
    ''', (imei, owner_name, owner_email))
    conn.commit()
    conn.close()

init_local_db()

def log_local_event(event_type, details):
    try:
        imei, _, _ = get_device_identity()
        conn = sqlite3.connect(LOCAL_DB)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO local_events (imei, event_type, details) VALUES (?, ?, ?)", (imei, event_type, details))
        conn.commit()
        conn.close()
    except Exception:
        pass

def launch_background_agent():
    agent_path = os.path.join(BREAD_DIR, "agent.py")
    if os.path.exists(agent_path):
        try:
            subprocess.Popen([sys.executable, agent_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass

MOBILE_OPTIMIZED_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BreadCrumb Control Hub</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; --danger: #cf6679; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 10px; box-sizing: border-box; }
        .container { max-width: 600px; margin: auto; }
        .card { background: var(--card); border-radius: 10px; padding: 15px; margin-bottom: 15px; border: 1px solid #333; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        h2, h3 { color: var(--primary); margin-top: 0; font-size: 1.1rem; }
        
        /* Grid Buttons */
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
        .btn { background: var(--primary); color: #000; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; text-align: center; font-size: 13px; width: 100%; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-accent { background: var(--accent); color: #000; }
        .btn-full { grid-column: span 2; }

        /* Tabs */
        .nav-tabs { display: flex; gap: 5px; overflow-x: auto; margin-bottom: 10px; padding-bottom: 5px; }
        .tab-btn { background: #2a2a2a; color: var(--text); border: none; padding: 8px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; white-space: nowrap; }
        .tab-btn.active { background: var(--primary); color: #000; font-weight: bold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        pre { background: #000; padding: 10px; border-radius: 6px; color: var(--accent); max-height: 180px; overflow-y: auto; font-size: 11px; white-space: pre-wrap; word-break: break-all; }
        #map { width: 100%; height: 260px; border-radius: 6px; margin-top: 10px; border: 2px solid var(--accent); display: none; z-index: 1; }
        .captured-img { max-width: 100%; border-radius: 6px; margin-top: 10px; border: 2px solid var(--accent); }
    </style>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
    <div class="container">
        <!-- Header & Account Selector Card -->
        <div class="card">
            <h2>BreadCrumb Control Hub</h2>
            <label style="font-size: 12px; color: var(--accent);">Target Account / IMEI:</label>
            <select id="deviceSelect" style="width: 100%; padding: 10px; background: #000; color: #fff; border: 1px solid var(--primary); border-radius: 6px; margin-top: 5px; font-size: 13px;">
                <option value="864190041234567">Master Operator (IMEI: 864190041234567)</option>
            </select>
        </div>

        <!-- Navigation Tabs -->
        <div class="card" style="padding: 10px;">
            <div class="nav-tabs">
                <button class="tab-btn active" onclick="switchTab(event, 'locateTab')">📍 Locate & Map</button>
                <button class="tab-btn" onclick="switchTab(event, 'toolsTab')">🛠️ Tool Suite</button>
                <button class="tab-btn" onclick="switchTab(event, 'telemetryTab')">📊 Telemetry</button>
                <button class="tab-btn" onclick="switchTab(event, 'dbTab')">🗄️ Local DB</button>
            </div>
        </div>

        <!-- TAB 1: LOCATE & MAP -->
        <div id="locateTab" class="tab-content active card">
            <h3>Multi-Vector GPS Tracking</h3>
            <div class="btn-grid">
                <button class="btn btn-accent btn-full" onclick="getExactLocation()">📍 Acquire GPS Fix & Pin Map</button>
                <button class="btn btn-danger btn-full" onclick="triggerAction('/api/ring', 'loc-output')">🚨 Sound Max Alarm</button>
            </div>
            <pre id="loc-output" style="margin-top:10px;">Location console ready...</pre>
            <div id="map"></div>
        </div>

        <!-- TAB 2: ADVANCED TOOLS -->
        <div id="toolsTab" class="tab-content card">
            <h3>Device Manipulation Suite</h3>
            <div class="btn-grid">
                <button class="btn" onclick="triggerCamera()">📸 Snap Dual-Camera</button>
                <button class="btn" onclick="triggerAction('/api/audio', 'tool-output')">🎙️ Record Audio</button>
                <button class="btn btn-full" onclick="triggerAction('/api/lock', 'tool-output')" style="background: #ffb74d; color: #000;">🔒 Force Device Lock</button>
            </div>
            <pre id="tool-output" style="margin-top:10px;">Tool console ready...</pre>
            <div id="image-preview"></div>
        </div>

        <!-- TAB 3: TELEMETRY -->
        <div id="telemetryTab" class="tab-content card">
            <h3>Live Telemetry Status</h3>
            <button class="btn" onclick="fetchInfo()">Refresh Telemetry</button>
            <pre id="telemetry-output" style="margin-top:10px;">Loading telemetry...</pre>
        </div>

        <!-- TAB 4: LOCAL DATABASE -->
        <div id="dbTab" class="tab-content card">
            <h3>Local SQLite Event Logs</h3>
            <button class="btn" onclick="fetchDatabase()">Load Local Logs</button>
            <pre id="db-output" style="margin-top:10px;">Database records will appear here...</pre>
        </div>
    </div>

    <script>
        let mapInstance = null;
        let markerInstance = null;

        function switchTab(evt, tabId) {
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(tb => tb.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
            if (tabId === 'locateTab' && mapInstance) {
                setTimeout(() => { mapInstance.invalidateSize(); }, 200);
            }
        }

        function getExactLocation() {
            const output = document.getElementById('loc-output');
            const mapDiv = document.getElementById('map');
            output.innerText = "Requesting browser geolocation fix...";

            if (!navigator.geolocation) {
                output.innerText = "Error: Geolocation not supported by environment.";
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    output.innerText = `[Fix Acquired!]\nLatitude: ${lat}\nLongitude: ${lon}`;
                    mapDiv.style.display = "block";

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
                        markerInstance = L.marker([lat, lon]).addTo(mapInstance).bindPopup("Target Device Position").openPopup();
                    }
                },
                (error) => { output.innerText = `[GPS Error]: ${error.message}`; },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        }

        function triggerAction(endpoint, outputId) {
            document.getElementById(outputId).innerText = "Executing command...";
            fetch(endpoint).then(res => res.json()).then(data => {
                document.getElementById(outputId).innerText = data.result || JSON.stringify(data, null, 2);
            }).catch(err => { document.getElementById(outputId).innerText = "Error: " + err; });
        }

        function triggerCamera() {
            document.getElementById('tool-output').innerText = "Capturing dual-camera photos...";
            document.getElementById('image-preview').innerHTML = "";
            fetch('/api/dual-camera').then(res => res.json()).then(data => {
                document.getElementById('tool-output').innerText = data.result;
                if (data.image_urls) {
                    let html = "<br><strong>Evidence Previews:</strong><br>";
                    data.image_urls.forEach(url => {
                        html += `<img src="${url}?t=` + new Date().getTime() + `" class="captured-img">`;
                    });
                    document.getElementById('image-preview').innerHTML = html;
                }
            }).catch(err => { document.getElementById('tool-output').innerText = "Error: " + err; });
        }

        function fetchInfo() {
            fetch('/api/info').then(res => res.json()).then(data => {
                document.getElementById('telemetry-output').innerText = JSON.stringify(data, null, 2);
            });
        }

        function fetchDatabase() {
            fetch('/api/db-view').then(res => res.json()).then(data => {
                let text = "--- DEVICE IDENTITY ---\\n" + JSON.stringify(data.identity, null, 2) + "\\n\\n--- LOCAL EVENTS ---\\n" + JSON.stringify(data.events, null, 2);
                document.getElementById('db-output').innerText = text;
            });
        }

        window.onload = fetchInfo;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(MOBILE_OPTIMIZED_TEMPLATE)

@app.route('/api/info')
def api_info():
    log_local_event("INFO_REFRESH", "Telemetry requested")
    return jsonify({
        "battery": json.loads(run_termux_cmd(["termux-battery-status"], timeout_sec=5) or "{}"),
        "wifi": json.loads(run_termux_cmd(["termux-wifi-connectioninfo"], timeout_sec=5) or "{}")
    })

@app.route('/api/db-view')
def api_db_view():
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM device_identity")
    identity = cursor.fetchall()
    cursor.execute("SELECT * FROM local_events ORDER BY timestamp DESC LIMIT 20")
    events = cursor.fetchall()
    conn.close()
    return jsonify({"identity": identity, "events": events})

@app.route('/api/ring')
def api_ring():
    run_termux_cmd(["termux-volume", "alarm", "15"], timeout_sec=3)
    run_termux_cmd(["termux-volume", "music", "15"], timeout_sec=3)
    run_termux_cmd(["termux-media-player", "play", "/system/media/audio/alarms/Alarm_Classic.ogg"], timeout_sec=4)
    log_local_event("ALARM_TRIGGERED", "Alarm played at max volume")
    return jsonify({"result": "Alarm dispatched at maximum volume across all streams."})

@app.route('/api/dual-camera')
def api_dual_camera():
    back_name = "breadcrumb_back.jpg"
    front_name = "breadcrumb_front.jpg"
    back_path = os.path.join(BREAD_DIR, back_name)
    front_path = os.path.join(BREAD_DIR, front_name)

    run_termux_cmd(["termux-camera-photo", "-c", "0", back_path], timeout_sec=8)
    run_termux_cmd(["termux-camera-photo", "-c", "1", front_path], timeout_sec=8)

    image_urls = []
    if os.path.exists(back_path): image_urls.append(f"/images/{back_name}")
    if os.path.exists(front_path): image_urls.append(f"/images/{front_name}")

    log_local_event("DUAL_SNAP", f"Captured {len(image_urls)} images")
    return jsonify({
        "result": f"Dual-camera capture complete. {len(image_urls)} images saved.",
        "image_urls": image_urls
    })

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(BREAD_DIR, filename)

@app.route('/api/audio')
def api_audio():
    audio_path = os.path.join(BREAD_DIR, "breadcrumb_audio.3gp")
    res = run_termux_cmd(["termux-microphone-record", "-l", "10", "-f", audio_path], timeout_sec=12)
    log_local_event("AUDIO_RECORD", "Ambient audio recorded")
    return jsonify({"result": f"Microphone response: {res or 'Ambient audio captured successfully'}"})

@app.route('/api/lock')
def api_lock():
    run_termux_cmd(["am", "broadcast", "-a", "com.android.server.telecom.intent.ACTION_SHOW_INCOMING_CALL"], timeout_sec=4)
    run_termux_cmd(["input", "keyevent", "26"], timeout_sec=2)
    log_local_event("DEVICE_LOCK", "Device lock sequence dispatched")
    return jsonify({"result": "Device lock signal and screen power-off dispatched successfully."})

if __name__ == '__main__':
    launch_background_agent()
    app.run(host='0.0.0.0', port=5000)
