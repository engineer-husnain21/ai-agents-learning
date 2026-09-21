"""
tamam_document_registry.py — Tamam's own document registry (separate
tamam_documents.db), same verification lifecycle as task 13/14:
pending -> verified/rejected, demoted on content change.
"""

import sqlite3
import uuid
from datetime import datetime

DB_PATH = "tamam_documents.db"


def init_registry_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scope TEXT NOT NULL,
            building_id INTEGER,
            chunk_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by TEXT,
            approved_at TIMESTAMP,
            content_hash TEXT,
            rejection_reason TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_document(filename, scope, building_id, chunk_count, content_hash):
    """scope: 'master' (applies to all buildings) or 'addendum' (one building only, needs building_id)."""
    doc_id = uuid.uuid4().hex[:12]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO documents
           (doc_id, filename, scope, building_id, chunk_count, status, content_hash)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (doc_id, filename, scope, building_id, chunk_count, content_hash)
    )
    conn.commit()
    conn.close()
    return doc_id


def approve_document(doc_id, approved_by, content_hash):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE documents SET status = 'verified', approved_by = ?, approved_at = ?,
           content_hash = ?, rejection_reason = NULL WHERE doc_id = ?""",
        (approved_by, datetime.now().isoformat(), content_hash, doc_id)
    )
    conn.commit()
    conn.close()


def reject_document(doc_id, rejected_by, reason):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE documents SET status = 'rejected', approved_by = ?, approved_at = ?,
           rejection_reason = ? WHERE doc_id = ?""",
        (rejected_by, datetime.now().isoformat(), reason, doc_id)
    )
    conn.commit()
    conn.close()


def demote_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE documents SET status = 'demoted' WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()


def list_documents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT doc_id, filename, uploaded_at, scope, building_id, chunk_count,
               status, approved_by, approved_at, content_hash, rejection_reason
        FROM documents ORDER BY uploaded_at
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT doc_id, filename, uploaded_at, scope, building_id, chunk_count,
               status, approved_by, approved_at, content_hash, rejection_reason
        FROM documents WHERE doc_id = ?
    """, (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def _row_to_dict(row):
    return {
        "doc_id": row[0], "filename": row[1], "uploaded_at": row[2],
        "scope": row[3], "building_id": row[4], "chunk_count": row[5],
        "status": row[6], "approved_by": row[7], "approved_at": row[8],
        "content_hash": row[9], "rejection_reason": row[10]
    }


def delete_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()