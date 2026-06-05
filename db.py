# db.py
import sqlite3
from datetime import datetime

DB = sqlite3.connect("bot_v2.db", check_same_thread=False)
cur = DB.cursor()

# ==================== ТАБЛИЦЫ ====================
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    created_at TEXT,
    balance REAL DEFAULT 0,
    total_earned REAL DEFAULT 0,
    max_submitted INTEGER DEFAULT 0,
    cards_submitted INTEGER DEFAULT 0,
    subscribed INTEGER DEFAULT 0,
    username TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    status TEXT DEFAULT 'new',
    data TEXT,
    admin_id INTEGER,
    created_at TEXT,
    completed_at TEXT,
    invoice_url TEXT
)""")

# Миграции
for col, col_type in [
    ("total_earned", "REAL DEFAULT 0"),
    ("max_submitted", "INTEGER DEFAULT 0"),
    ("cards_submitted", "INTEGER DEFAULT 0"),
    ("subscribed", "INTEGER DEFAULT 0"),
    ("username", "TEXT")
]:
    try:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
    except sqlite3.OperationalError:
        pass

DB.commit()

# ==================== ФУНКЦИИ ====================
def create_user(tg_id, username=None):
    cur.execute("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (tg_id, created_at, username) VALUES (?, ?, ?)",
            (tg_id, datetime.utcnow().isoformat(), username)
        )
        DB.commit()
    elif username:
        cur.execute("UPDATE users SET username=? WHERE tg_id=?", (username, tg_id))
        DB.commit()

def get_user(tg_id):
    cur.execute("SELECT tg_id, created_at, balance, total_earned, max_submitted, cards_submitted, subscribed, username FROM users WHERE tg_id=?", (tg_id,))
    return cur.fetchone()

def update_user_balance(tg_id, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE tg_id=?", (amount, tg_id))
    if amount > 0:
        cur.execute("UPDATE users SET total_earned = total_earned + ? WHERE tg_id=?", (amount, tg_id))
    DB.commit()

def create_ticket(user_id, ticket_type, data, invoice_url=None):
    cur.execute(
        "INSERT INTO tickets (user_id, type, data, invoice_url, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, ticket_type, data, invoice_url, datetime.utcnow().isoformat())
    )
    DB.commit()
    return cur.lastrowid

def get_ticket(ticket_id):
    cur.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
    return cur.fetchone()

def get_pending_withdrawals():
    cur.execute("""
        SELECT t.id, t.user_id, t.data, t.invoice_url, u.username 
        FROM tickets t
        LEFT JOIN users u ON t.user_id = u.tg_id
        WHERE t.type='WITHDRAW' AND t.status='new'
    """)
    return cur.fetchall()

def assign_ticket(ticket_id, admin_id):
    cur.execute("UPDATE tickets SET admin_id=?, status='processing' WHERE id=?", (admin_id, ticket_id))
    DB.commit()

def update_ticket_data(ticket_id, data):
    cur.execute("UPDATE tickets SET data=? WHERE id=?", (data, ticket_id))
    DB.commit()

def reject_ticket_db(ticket_id):
    cur.execute("UPDATE tickets SET status='rejected', completed_at=? WHERE id=?", 
                (datetime.utcnow().isoformat(), ticket_id))
    DB.commit()

def complete_ticket(ticket_id, amount=0):
    cur.execute("SELECT status, user_id FROM tickets WHERE id=?", (ticket_id,))
    res = cur.fetchone()
    if not res or res[0] in ['done', 'rejected']:
        return False
    cur.execute("UPDATE tickets SET status='done', completed_at=? WHERE id=?", 
                (datetime.utcnow().isoformat(), ticket_id))
    if amount > 0 and res[1]:
        update_user_balance(res[1], amount)
    DB.commit()
    return True

def increment_max_submitted(tg_id):
    cur.execute("UPDATE users SET max_submitted = max_submitted + 1 WHERE tg_id=?", (tg_id,))
    DB.commit()

def increment_cards_submitted(tg_id):
    cur.execute("UPDATE users SET cards_submitted = cards_submitted + 1 WHERE tg_id=?", (tg_id,))
    DB.commit()

def set_subscribed(tg_id, status=1):
    cur.execute("UPDATE users SET subscribed=? WHERE tg_id=?", (status, tg_id))
    DB.commit()

def is_subscribed(tg_id):
    cur.execute("SELECT subscribed FROM users WHERE tg_id=?", (tg_id,))
    res = cur.fetchone()
    return res[0] if res else 0