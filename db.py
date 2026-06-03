import sqlite3
from datetime import datetime

DB = sqlite3.connect("bot_v2.db", check_same_thread=False)
cur = DB.cursor()

# ==================== ТАБЛИЦЫ ====================
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    created_at TEXT,
    balance REAL DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    status TEXT DEFAULT 'new',
    data TEXT,
    admin_id INTEGER,
    created_at TEXT,
    completed_at TEXT
)""")

DB.commit()

# ==================== ФУНКЦИИ ====================
def create_user(tg_id):
    cur.execute("INSERT OR IGNORE INTO users (tg_id, created_at) VALUES (?, ?)", 
                (tg_id, datetime.utcnow().isoformat()))
    DB.commit()

def get_user(tg_id):
    cur.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    return cur.fetchone()

def update_user_balance(tg_id, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, tg_id))
    DB.commit()

def create_ticket(user_id, ttype, data=None):
    cur.execute("""INSERT INTO tickets (user_id, type, data, created_at) 
                   VALUES (?, ?, ?, ?)""", 
                (user_id, ttype, data, datetime.utcnow().isoformat()))
    DB.commit()
    return cur.lastrowid

def get_ticket(ticket_id):
    cur.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
    return cur.fetchone()

def get_new_tickets():
    cur.execute("SELECT * FROM tickets WHERE status='new'")
    return cur.fetchall()

def get_user_tickets(user_id=None):
    if user_id:
        cur.execute("SELECT * FROM tickets WHERE user_id=?", (user_id,))
    else:
        cur.execute("SELECT * FROM tickets")
    return cur.fetchall()

def assign_ticket(ticket_id, admin_id):
    cur.execute("UPDATE tickets SET admin_id=?, status='processing' WHERE id=?", 
                (admin_id, ticket_id))
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
            user_id = result[0]
            cur.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, user_id))
    DB.commit()