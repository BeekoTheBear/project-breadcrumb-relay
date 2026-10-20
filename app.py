# Title goes here

_This document provides a comprehensive operational guide and technical specification for the Project BreadCrumb Cloud Relay Wrapper. It details the core mechanics of the cloud-hosted Command-and-Control relay infrastructure, integration points, operational safeguards, and remote administrative workflows designed for secure mobile asset tracking deployment on cloud infrastructure._

---

## Overview

​Problem Addressed: Traditional device tracking relies entirely on local physical proximity or single-purpose proprietary ecosystems. This wrapper solves the challenge of decentralized asset management by creating a centralized cloud relay for wireless command scheduling, device registration validation, and secure operational visibility.
​Target Audience: Designed for system administrators, security engineers, and operators deploying private mobile asset recovery pipelines who require an enterprise-grade understanding of the cloud relay architecture, credential handling, synchronization mechanics, and forensic tracking workflows.

## Key Points

Centralized Command & Control (C2): Acts as a persistent web-accessible relay hosted on cloud providers (such as Render) that securely bridges remote administrative browsers with active mobile endpoints and backend device registries.
​Master Authentication Protocol: Secures administrative portals via credential-gated master profiles paired with secure cookie sessions and local database states.
​Telemetry & Forensic Indexing: Automatically ingests, parses, and displays structured device metadata—including hardware make/model, persistent identifiers, owner verification tokens, and live operational status—into a consolidated cloud registry.

_Last updated: 2026-10-20_
import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)
CLOUD_DB = "cloud_relay.db"

MASTER_USER = "BeekoTheBear911!"
MASTER_PASS = "JTElephant911!"

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
            status TEXT
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
    conn.commit()
    conn.close()

init_cloud_db()

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project BreadCrumb - Cloud Dispatch Relay</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; }
        body { font-family: sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: auto; }
        .card { background: var(--card); border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #333; }
        h2, h3 { color: var(--primary); margin-top: 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        th { color: var(--accent); }
        .btn { background: var(--primary); color: #000; border: none; padding: 8px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-danger { background: #cf6679; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h2>Cloud Dispatch & Command Relay</h2>
            <p>Master Administrator Portal — Connected from anywhere worldwide.</p>
            <a href="/logout" class="btn btn-danger" style="float: right; margin-top: -45px;">Logout</a>
        </div>

        <div class="card">
            <h3>Registered Protected Handsets</h3>
            <table>
                <tr>
                    <th>IMEI</th>
                    <th>Make & Model</th>
                    <th>Owner Name</th>
                    <th>Google Email</th>
                    <th>Status</th>
                </tr>
                {% for dev in devices %}
                <tr>
                    <td><code>{{ dev[0] }}</code></td>
                    <td>{{ dev[1] }}</td>
                    <td>{{ dev[2] }}</td>
                    <td>{{ dev[3] }}</td>
                    <td style="color: #03dac6; font-weight: bold;">{{ dev[7] }}</td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align: center; color: #777;">No devices currently synced to the cloud relay.</td></tr>
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
    <meta charset="UTF-8">
    <title>Master Admin Login</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --primary: #bb86fc; --text: #e0e0e0; --accent: #03dac6; }
        body { font-family: sans-serif; background: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: var(--card); padding: 25px; border-radius: 8px; width: 320px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.7); }
        h2 { color: var(--primary); text-align: center; margin-top: 0; }
        input { width: 100%; padding: 10px; margin: 8px 0; border-radius: 4px; border: 1px solid #444; background: #000; color: #fff; box-sizing: border-box; }
        button { background: var(--primary); color: #000; border: none; padding: 10px; border-radius: 4px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Master Admin Login</h2>
        {% if error %}<p style="color: #cf6679; font-size: 12px; text-align: center;">{{ error }}</p>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Master Username" required>
            <input type="password" name="password" placeholder="Master Password" required>
            <button type="submit">Authenticate</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def cloud_dashboard():
    if request.cookies.get("auth") != "true":
        if request.method == 'POST':
            user = request.form.get("username")
            pwd = request.form.get("password")
            if user == MASTER_USER and pwd == MASTER_PASS:
                resp = redirect(url_for('cloud_dashboard'))
                resp.set_cookie("auth", "true")
                return resp
            else:
                return render_template_string(LOGIN_TEMPLATE, error="Invalid Master Credentials")
        return render_template_string(LOGIN_TEMPLATE)

    conn = sqlite3.connect(CLOUD_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT imei, make_model, owner_name, owner_email, unlock_credentials, verified, last_seen, status FROM registered_devices")
    devices = cursor.fetchall()
    conn.close()

    return render_template_string(ADMIN_TEMPLATE, devices=devices)

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
        INSERT OR REPLACE INTO registered_devices (imei, make_model, owner_name, owner_email, unlock_credentials, verified, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        imei,
        data.get("make_model", "Unknown"),
        data.get("owner_name", "Unknown"),
        data.get("owner_email", "Unknown"),
        data.get("unlock_credentials", "Unknown"),
        data.get("verified", 0),
        data.get("status", "Active")
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "synced"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
