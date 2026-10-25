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
                .grid { display: grid; grid-template-columns: 300px 1fr; gap: 20px; }
                @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
                .card { background: #1e293b; padding: 20px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 20px; }
                .device-item { padding: 12px; background: #0f172a; border-radius: 6px; margin-bottom: 10px; cursor: pointer; border: 1px solid #334155; }
                .device-item.active { border-color: #38bdf8; background: #09203f; }
                .device-item a { color: #f8fafc; text-decoration: none; display: block; }
                pre { background: #0f172a; padding: 12px; border-radius: 6px; overflow-x: auto; color: #38bdf8; font-size: 13px; white-space: pre-wrap; word-wrap: break-word; }
                .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px; }
                button, .btn { padding: 10px
