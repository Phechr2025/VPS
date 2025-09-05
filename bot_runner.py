import os, time, signal, sqlite3, asyncio
import discord
from discord.ext import commands

DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(__file__), "panel.db")
PID_FILE = os.environ.get("PID_FILE") or os.path.join(os.path.dirname(__file__), "bot.pid")
RELOAD_FLAG = os.environ.get("RELOAD_FLAG") or os.path.join(os.path.dirname(__file__), "reload.flag")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key, default=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return row["value"] if row else default

def load_commands_from_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT trigger, response, allowed_channels, allowed_users, enabled FROM commands")
    rows = cur.fetchall()
    cmds = []
    for r in rows:
        if r["enabled"] != 1: 
            continue
        trig = (r["trigger"] or "").strip()
        resp = (r["response"] or "").strip()
        allowed_channels = set([x.strip() for x in (r["allowed_channels"] or "").split(",") if x.strip()])
        allowed_users = set([x.strip() for x in (r["allowed_users"] or "").split(",") if x.strip()])
        if trig and resp:
            cmds.append({
                "trigger": trig,
                "response": resp,
                "allowed_channels": allowed_channels,
                "allowed_users": allowed_users,
            })
    return cmds

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = False

bot = commands.Bot(command_prefix="!", intents=intents)

class CommandCache:
    def __init__(self):
        self._data = []
        self._last_load = 0

    def needs_reload(self):
        # reload on startup or when reload.flag touched or every 30s
        if time.time() - self._last_load > 30:
            return True
        if os.path.exists(RELOAD_FLAG):
            return True
        return False

    def load(self):
        self._data = load_commands_from_db()
        self._last_load = time.time()
        # clear reload flag if exists
        if os.path.exists(RELOAD_FLAG):
            try:
                os.remove(RELOAD_FLAG)
            except OSError:
                pass

    @property
    def data(self):
        if self.needs_reload():
            self.load()
        return self._data

cmd_cache = CommandCache()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = (message.content or "").strip()
    if not content:
        return

    # Load/refresh commands if needed
    cmds = cmd_cache.data

    for c in cmds:
        if content == c["trigger"]:
            # Check channel restriction
            if c["allowed_channels"]:
                if str(message.channel.id) not in c["allowed_channels"]:
                    continue
            # Check user restriction
            if c["allowed_users"]:
                if str(message.author.id) not in c["allowed_users"]:
                    continue
            try:
                await message.channel.send(c["response"])
            except Exception as e:
                print("Failed to send response:", e)
            break  # match one command only

    await bot.process_commands(message)

def main():
    token = get_setting("bot_token", None)
    if not token:
        print("No bot token set. Please set it in the web panel.")
        return

    loop = asyncio.get_event_loop()
    try:
        bot.run(token)
    except KeyboardInterrupt:
        pass
    finally:
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except OSError:
                pass

if __name__ == "__main__":
    main()
