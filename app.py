import os, subprocess, signal, psutil, time
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.middleware.proxy_fix import ProxyFix
from db import init_db, get_setting, set_setting, has_admin, set_admin_password, verify_admin_password, list_commands, get_command, add_command, update_command, delete_command

# Ensure psutil is available (fallback if not installed)
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "panel.db")
PID_FILE = os.path.join(BASE_DIR, "bot.pid")
RELOAD_FLAG = os.path.join(BASE_DIR, "reload.flag")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Init DB on startup
init_db()

def bot_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                return int(f.read().strip())
        except Exception:
            return None
    return None

def bot_is_running():
    pid = bot_pid()
    if not pid:
        return False
    try:
        if psutil:
            return psutil.pid_exists(pid)
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def start_bot():
    if bot_is_running():
        return True, "Bot is already running."
    env = os.environ.copy()
    env["DB_PATH"] = DB_PATH
    env["PID_FILE"] = PID_FILE
    env["RELOAD_FLAG"] = RELOAD_FLAG
    # Launch bot as a subprocess
    p = subprocess.Popen([env.get("PYTHON_BIN", "python"), os.path.join(BASE_DIR, "bot_runner.py")], env=env, cwd=BASE_DIR)
    time.sleep(1.0)
    if bot_is_running():
        return True, "Bot started."
    return False, "Failed to start bot. Check logs."

def stop_bot():
    if not bot_is_running():
        return True, "Bot is not running."
    pid = bot_pid()
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    # Wait for process to exit
    for _ in range(20):
        if not bot_is_running():
            break
        time.sleep(0.2)
    if not bot_is_running():
        return True, "Bot stopped."
    return False, "Failed to stop bot. Try again."

def restart_bot():
    stop_bot()
    return start_bot()

def require_login():
    if not has_admin():
        return redirect(url_for('first_time_setup'))
    if not session.get("logged_in"):
        return redirect(url_for('login'))
    return None

@app.route("/setup", methods=["GET", "POST"])
def first_time_setup():
    if has_admin():
        return redirect(url_for('login'))
    if request.method == "POST":
        pw = request.form.get("password", "")
        if len(pw) < 8:
            flash("ตั้งรหัสผ่านอย่างน้อย 8 ตัวอักษร", "danger")
        else:
            set_admin_password(pw)
            flash("ตั้งรหัสผ่านแอดมินสำเร็จแล้ว ล็อกอินเลย!", "success")
            return redirect(url_for('login'))
    return render_template("login.html", first_setup=True)

@app.route("/login", methods=["GET", "POST"])
def login():
    if not has_admin():
        return redirect(url_for('first_time_setup'))
    if request.method == "POST":
        pw = request.form.get("password", "")
        if verify_admin_password(pw):
            session["logged_in"] = True
            return redirect(url_for('dashboard'))
        else:
            flash("รหัสผ่านไม่ถูกต้อง", "danger")
    return render_template("login.html", first_setup=False)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/")
def dashboard():
    r = require_login()
    if r: return r
    status = "กำลังรัน" if bot_is_running() else "หยุดอยู่"
    token_set = bool(get_setting("bot_token", ""))
    return render_template("dashboard.html", status=status, token_set=token_set)

@app.route("/control/<action>", methods=["POST"])
def control(action):
    r = require_login()
    if r: return r
    ok, msg = False, "Unknown"
    if action == "start":
        ok, msg = start_bot()
    elif action == "stop":
        ok, msg = stop_bot()
    elif action == "restart":
        ok, msg = restart_bot()
    else:
        flash("คำสั่งไม่ถูกต้อง", "danger")
        return redirect(url_for('dashboard'))
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('dashboard'))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    r = require_login()
    if r: return r
    token = get_setting("bot_token", "") or ""
    if request.method == "POST":
        token = (request.form.get("bot_token") or "").strip()
        if not token:
            flash("กรุณาใส่โทเคนบอท", "danger")
        else:
            set_setting("bot_token", token)
            # Trigger bot to reload (if running, it will just reconnect on restart; for command changes we touch RELOAD_FLAG)
            flash("บันทึกโทเคนแล้ว", "success")
    return render_template("settings.html", token=token)

@app.route("/commands")
def commands_list():
    r = require_login()
    if r: return r
    cmds = list_commands()
    return render_template("commands_list.html", commands=cmds)

@app.route("/commands/new", methods=["GET","POST"])
def command_new():
    r = require_login()
    if r: return r
    if request.method == "POST":
        trigger = request.form.get("trigger","")
        response = request.form.get("response","")
        allowed_channels = request.form.get("allowed_channels","")
        allowed_users = request.form.get("allowed_users","")
        enabled = 1 if request.form.get("enabled") == "on" else 0
        if not trigger.strip() or not response.strip():
            flash("กรอก Trigger และ Response ด้วย", "danger")
        else:
            add_command(trigger, response, allowed_channels, allowed_users, enabled)
            # touch reload flag
            try:
                open(RELOAD_FLAG, "a").close()
            except Exception:
                pass
            flash("เพิ่มคำสั่งแล้ว", "success")
            return redirect(url_for('commands_list'))
    return render_template("command_form.html", cmd=None)

@app.route("/commands/<int:cmd_id>/edit", methods=["GET","POST"])
def command_edit(cmd_id):
    r = require_login()
    if r: return r
    cmd = get_command(cmd_id)
    if not cmd:
        flash("ไม่พบคำสั่ง", "danger")
        return redirect(url_for('commands_list'))
    if request.method == "POST":
        trigger = request.form.get("trigger","")
        response = request.form.get("response","")
        allowed_channels = request.form.get("allowed_channels","")
        allowed_users = request.form.get("allowed_users","")
        enabled = 1 if request.form.get("enabled") == "on" else 0
        if not trigger.strip() or not response.strip():
            flash("กรอก Trigger และ Response ด้วย", "danger")
        else:
            update_command(cmd_id, trigger, response, allowed_channels, allowed_users, enabled)
            try:
                open(RELOAD_FLAG, "a").close()
            except Exception:
                pass
            flash("บันทึกการแก้ไขแล้ว", "success")
            return redirect(url_for('commands_list'))
    return render_template("command_form.html", cmd=cmd)

@app.route("/commands/<int:cmd_id>/delete", methods=["POST"])
def command_delete(cmd_id):
    r = require_login()
    if r: return r
    delete_command(cmd_id)
    try:
        open(RELOAD_FLAG, "a").close()
    except Exception:
        pass
    flash("ลบคำสั่งแล้ว", "success")
    return redirect(url_for('commands_list'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
