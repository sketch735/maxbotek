import sqlite3
from datetime import datetime

DB = sqlite3.connect("bot.db", check_same_thread=False)
cur = DB.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    tariff TEXT DEFAULT 'free',
    requests INTEGER DEFAULT 0,
    created_at TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    text TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT
)
""")

DB.commit()


def get_user(tg_id):
    cur.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    return cur.fetchone()


def create_user(tg_id):
    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, 'free', 0, ?)",
        (tg_id, datetime.utcnow().isoformat())
    )
    DB.commit()


def add_request(tg_id):
    cur.execute("UPDATE users SET requests = requests + 1 WHERE tg_id=?", (tg_id,))
    DB.commit()


def create_ticket(tg_id, text):
    cur.execute(
        "INSERT INTO tickets (tg_id, text, created_at) VALUES (?, ?, ?)",
        (tg_id, text, datetime.utcnow().isoformat())
    )
    DB.commit()