import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "panel.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS settings (
               key TEXT PRIMARY KEY,
               value TEXT
           )'''
    )
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS admin (
               id INTEGER PRIMARY KEY CHECK (id=1),
               password_hash TEXT
           )'''
    )
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS commands (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               trigger TEXT NOT NULL,
               response TEXT NOT NULL,
               allowed_channels TEXT DEFAULT '',
               allowed_users TEXT DEFAULT '',
               enabled INTEGER DEFAULT 1
           )'''
    )
    conn.commit()

def get_setting(key, default=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()

def has_admin():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admin WHERE id=1")
    return cur.fetchone() is not None

def set_admin_password(password):
    conn = get_conn()
    cur = conn.cursor()
    ph = generate_password_hash(password)
    cur.execute("INSERT INTO admin(id, password_hash) VALUES(1, ?) ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash", (ph,))
    conn.commit()

def verify_admin_password(password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM admin WHERE id=1")
    row = cur.fetchone()
    if not row:
        return False
    return check_password_hash(row["password_hash"], password)

def list_commands():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM commands ORDER BY id DESC")
    return cur.fetchall()

def get_command(cmd_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM commands WHERE id=?", (cmd_id,))
    return cur.fetchone()

def add_command(trigger, response, allowed_channels, allowed_users, enabled=1):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO commands(trigger, response, allowed_channels, allowed_users, enabled) VALUES(?,?,?,?,?)",
        (trigger.strip(), response.strip(), allowed_channels.strip(), allowed_users.strip(), int(enabled)),
    )
    conn.commit()

def update_command(cmd_id, trigger, response, allowed_channels, allowed_users, enabled):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE commands SET trigger=?, response=?, allowed_channels=?, allowed_users=?, enabled=? WHERE id=?",
        (trigger.strip(), response.strip(), allowed_channels.strip(), allowed_users.strip(), int(enabled), cmd_id),
    )
    conn.commit()

def delete_command(cmd_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM commands WHERE id=?", (cmd_id,))
    conn.commit()
