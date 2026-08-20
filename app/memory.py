"""
memory.py — saves and loads conversation history in SQLite.
Survives server restarts, because it's a file on disk, not just RAM.
"""

import sqlite3

DB_PATH = "memory.db"


def init_db():
    """Creates the table if it doesn't exist yet. Called once on startup."""
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
    """Saves one question+answer pair for a session."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO history (session_id, question, answer) VALUES (?, ?, ?)",
        (session_id, question, answer)
    )
    conn.commit()
    conn.close()


def get_history(session_id, limit=None):
    """
    Returns the session's history, oldest first, as a list of
    {"question": ..., "answer": ...}. If limit is given, returns only
    the most recent `limit` turns (still oldest-first order).
    """
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