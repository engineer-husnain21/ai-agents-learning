"""
document_registry.py — SQLite table tracking every uploaded document:
doc_id, filename, uploaded_at, trust_level, chunk_count.

Separate from memory.db (conversation history) — this is corpus metadata,
a different concern, so it gets its own table logic even if it ends up
in the same SQLite file later. Kept as its own file for clarity.
"""

import sqlite3
import uuid
from datetime import datetime

DB_PATH = "documents.db"


def init_registry_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trust_level TEXT NOT NULL,
            chunk_count INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_document(filename, trust_level, chunk_count):
    """Registers a new document, returns its doc_id."""
    doc_id = uuid.uuid4().hex[:12]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO documents (doc_id, filename, trust_level, chunk_count) VALUES (?, ?, ?, ?)",
        (doc_id, filename, trust_level, chunk_count)
    )
    conn.commit()
    conn.close()
    return doc_id


def list_documents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT doc_id, filename, uploaded_at, trust_level, chunk_count FROM documents ORDER BY uploaded_at"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "doc_id": r[0], "filename": r[1], "uploaded_at": r[2],
            "trust_level": r[3], "chunk_count": r[4]
        }
        for r in rows
    ]


def get_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT doc_id, filename, uploaded_at, trust_level, chunk_count FROM documents WHERE doc_id = ?",
        (doc_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "doc_id": row[0], "filename": row[1], "uploaded_at": row[2],
        "trust_level": row[3], "chunk_count": row[4]
    }


def delete_document(doc_id):
    """Removes the document from the registry. Removing its chunks from
    the vector store is a separate step, done by the caller."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()