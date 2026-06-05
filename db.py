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
    subscribed INTEGER DEFAULT 0
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
    ("subscribed", "INTEGER DEFAULT 0")
]:
    try:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
    except sqlite3.OperationalError:
        pass

DB.commit()

# ==================== ФУНКЦИИ ====================
def create_user(tg_id):
    cur.execute("""INSERT OR IGNORE INTO users 
                (tg_id, created_at, balance, total_earned, max_submitted, cards_submitted, subscribed) 
                VALUES (?, ?, 0, 0, 0, 0, 0)""", 
                (tg_id, datetime.utcnow().isoformat()))
    DB.commit()

def get_user(tg_id):
    cur.execute("""SELECT tg_id, created_at, balance, total_earned, 
                   max_submitted, cards_submitted, subscribed 
                   FROM users WHERE tg_id=?""", (tg_id,))
    return cur.fetchone()

def set_subscribed(tg_id):
    cur.execute("UPDATE users SET subscribed = 1 WHERE tg_id = ?", (tg_id,))
    DB.commit()

def is_subscribed(tg_id):
    cur.execute("SELECT subscribed FROM users WHERE tg_id=?", (tg_id,))
    result = cur.fetchone()
    return bool(result and result[0] == 1)

def update_user_balance(tg_id, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, tg_id))
    if amount > 0:
        cur.execute("UPDATE users SET total_earned = total_earned + ? WHERE tg_id = ?", (amount, tg_id))
    DB.commit()

def create_ticket(user_id, ttype, data=None, invoice_url=None):
    cur.execute("""INSERT INTO tickets (user_id, type, data, created_at, invoice_url) 
                   VALUES (?, ?, ?, ?, ?)""", 
                (user_id, ttype, data, datetime.utcnow().isoformat(), invoice_url))
    DB.commit()
    return cur.lastrowid

def get_ticket(ticket_id):
    cur.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
    return cur.fetchone()

def get_pending_withdrawals():
    cur.execute("""
        SELECT id, user_id, data, invoice_url 
        FROM tickets 
        WHERE type='WITHDRAW' AND status='new'
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
    cur.execute("UPDATE tickets SET status='done', completed_at=? WHERE id=?", 
                (datetime.utcnow().isoformat(), ticket_id))
    if amount > 0:
        cur.execute("SELECT user_id FROM tickets WHERE id=?", (ticket_id,))
        result = cur.fetchone()
        if result:
            update_user_balance(result[0], amount)
    DB.commit()

def increment_max_submitted(tg_id):
    cur.execute("UPDATE users SET max_submitted = max_submitted + 1 WHERE tg_id = ?", (tg_id,))
    DB.commit()

def increment_cards_submitted(tg_id):
    cur.execute("UPDATE users SET cards_submitted = cards_submitted + 1 WHERE tg_id = ?", (tg_id,))
    DB.commit()