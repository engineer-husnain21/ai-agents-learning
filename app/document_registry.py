"""
document_registry.py — Task 13: documents now go through a verification
lifecycle: pending -> verified -> demoted (or -> rejected).
status: "pending" | "verified" | "demoted" | "rejected"
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


def add_document(filename, trust_level, chunk_count, content_hash):
    """Registers a new document as PENDING. Returns its doc_id."""
    doc_id = uuid.uuid4().hex[:12]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO documents
           (doc_id, filename, trust_level, chunk_count, status, content_hash)
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (doc_id, filename, trust_level, chunk_count, content_hash)
    )
    conn.commit()
    conn.close()
    return doc_id


def approve_document(doc_id, approved_by, content_hash):
    """
    Marks a document verified. Records who approved it, when, and the
    exact content hash approved — this hash is what later read-time
    checks compare against to detect a content change (demotion trigger).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE documents
           SET status = 'verified', approved_by = ?, approved_at = ?,
               content_hash = ?, rejection_reason = NULL
           WHERE doc_id = ?""",
        (approved_by, datetime.now().isoformat(), content_hash, doc_id)
    )
    conn.commit()
    conn.close()


def reject_document(doc_id, rejected_by, reason):
    """
    Marks a document rejected with a required reason. A rejected
    document is not eligible to answer questions until re-reviewed.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE documents
           SET status = 'rejected', approved_by = ?, approved_at = ?,
               rejection_reason = ?
           WHERE doc_id = ?""",
        (rejected_by, datetime.now().isoformat(), reason, doc_id)
    )
    conn.commit()
    conn.close()


def demote_document(doc_id):
    """
    Content changed under a verified document — demote it. The original
    approver (approved_by) is preserved in the record, so demotion
    routes back to them, not a general queue, per review guidance.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE documents SET status = 'demoted' WHERE doc_id = ?",
        (doc_id,)
    )
    conn.commit()
    conn.close()


def list_documents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT doc_id, filename, uploaded_at, trust_level, chunk_count,
               status, approved_by, approved_at, content_hash, rejection_reason
        FROM documents ORDER BY uploaded_at
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT doc_id, filename, uploaded_at, trust_level, chunk_count,
               status, approved_by, approved_at, content_hash, rejection_reason
        FROM documents WHERE doc_id = ?
    """, (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def _row_to_dict(row):
    return {
        "doc_id": row[0], "filename": row[1], "uploaded_at": row[2],
        "trust_level": row[3], "chunk_count": row[4], "status": row[5],
        "approved_by": row[6], "approved_at": row[7],
        "content_hash": row[8], "rejection_reason": row[9]
    }


def delete_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()