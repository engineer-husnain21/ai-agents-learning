"""
tamam_memory.py — Tamam's own conversation history (separate
tamam_memory.db). Callers must build session_key from the trusted
tenant_id (not user-supplied), so one tenant can never address another
tenant's conversation history even by guessing a session id.
"""

import sqlite3

DB_PATH = "tamam_memory.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_turn(session_id, question, answer):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO history (session_id, question, answer) VALUES (?, ?, ?)",
        (session_id, question, answer)
    )
    conn.commit()
    conn.close()


def get_history(session_id, limit=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT question, answer FROM history WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    history = [{"question": q, "answer": a} for q, a in rows]
    if limit is not None:
        history = history[-limit:]
    return history