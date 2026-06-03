# FILE: db.py

import sqlite3
from datetime import datetime

DB = sqlite3.connect("bot.db", check_same_thread=False)
cur = DB.cursor()

# USERS
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY
)
""")

# TICKETS (CRM заявки)
cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    status TEXT DEFAULT 'new',
    admin_id INTEGER,
    created_at TEXT
)
""")

# MESSAGES (чат user ↔ admin)
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    sender TEXT,
    text TEXT,
    created_at TEXT
)
""")

DB.commit()


def create_user(tg_id):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (tg_id,))
    DB.commit()


def create_ticket(user_id, ttype):
    cur.execute("""
        INSERT INTO tickets (user_id, type, created_at)
        VALUES (?, ?, ?)
    """, (user_id, ttype, datetime.utcnow().isoformat()))
    DB.commit()
    return cur.lastrowid


def get_ticket(ticket_id):
    cur.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
    return cur.fetchone()


def get_user_tickets(user_id):
    cur.execute("SELECT * FROM tickets WHERE user_id=?", (user_id,))
    return cur.fetchall()


def get_new_tickets():
    cur.execute("SELECT * FROM tickets WHERE status='new'")
    return cur.fetchall()


def assign_ticket(ticket_id, admin_id):
    cur.execute("""
        UPDATE tickets SET status='processing', admin_id=?
        WHERE id=?
    """, (admin_id, ticket_id))
    DB.commit()


def close_ticket(ticket_id):
    cur.execute("""
        UPDATE tickets SET status='done'
        WHERE id=?
    """, (ticket_id,))
    DB.commit()


def add_message(ticket_id, sender, text):
    cur.execute("""
        INSERT INTO messages (ticket_id, sender, text, created_at)
        VALUES (?, ?, ?, ?)
    """, (ticket_id, sender, text, datetime.utcnow().isoformat()))
    DB.commit()


def get_messages(ticket_id):
    cur.execute("SELECT * FROM messages WHERE ticket_id=?", (ticket_id,))
    return cur.fetchall()