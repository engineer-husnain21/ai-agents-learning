"""
verification_graph.py — Task 14: the real LangGraph rebuild of task 13's
verification lifecycle.

thread_id = doc_id (per plan addition #1) — this is how a restarted
server finds the right paused run when a decision arrives for a doc_id.

The graph is now the SINGLE owner of a document's verification state.
main_lc.py's /approve and /reject endpoints no longer write to the
registry directly — they just submit a decision into this graph via
Command(resume=...), and finalize_node is what actually updates the
registry.
"""

import sqlite3
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver

from app.injection_screen import screen_chunks
from app.contradiction_detector import check_new_document_for_contradictions
from app.document_registry import approve_document, reject_document


class VerificationState(TypedDict):
    doc_id: str
    filename: str
    chunks: list
    content_hash: str
    flagged_count: int
    contradiction_flags: list
    decision: str
    approved_by: str
    reason: str
    status: str


def screening_node(state: VerificationState):
    chunks = screen_chunks(state["chunks"])
    flagged_count = sum(1 for c in chunks if c["flagged"])
    return {"chunks": chunks, "flagged_count": flagged_count}


def contradiction_check_node(state: VerificationState):
    flags = check_new_document_for_contradictions(state["chunks"], state["doc_id"])
    return {"contradiction_flags": flags}


def human_review_node(state: VerificationState):
    """
    This is where the graph genuinely pauses. Whatever is passed to
    interrupt() is what a caller sees while it's waiting; whatever is
    passed to Command(resume=...) later is what comes back as the
    return value of interrupt() here.
    """
    payload = interrupt({
        "doc_id": state["doc_id"],
        "filename": state["filename"],
        "flagged_count": state["flagged_count"],
        "contradiction_flags": state["contradiction_flags"],
        "message": "Waiting for human approve/reject decision."
    })
    return {
        "decision": payload.get("decision"),
        "approved_by": payload.get("by", "unknown"),
        "reason": payload.get("reason", "")
    }


def finalize_node(state: VerificationState):
    """
    The graph is the state owner: THIS is what writes the final decision
    to the document registry, not the API endpoint that triggered resume.
    """
    if state["decision"] == "approve":
        approve_document(state["doc_id"], state["approved_by"], state["content_hash"])
        status = "verified"
    else:
        reject_document(state["doc_id"], state["approved_by"], state["reason"])
        status = "rejected"
    return {"status": status}


_checkpointer = None
_conn = None
_graph = None


def get_verification_graph():
    """Builds (once) and returns the compiled graph, backed by a
    disk-based SqliteSaver checkpointer — not the in-memory one from
    the course notebooks, per the plan's checkpointer decision."""
    global _checkpointer, _conn, _graph
    if _graph is None:
        _conn = sqlite3.connect("verification_graph.db", check_same_thread=False)
        _checkpointer = SqliteSaver(_conn)

        builder = StateGraph(VerificationState)
        builder.add_node("screening", screening_node)
        builder.add_node("contradiction_check", contradiction_check_node)
        builder.add_node("human_review", human_review_node)
        builder.add_node("finalize", finalize_node)

        builder.add_edge(START, "screening")
        builder.add_edge("screening", "contradiction_check")
        builder.add_edge("contradiction_check", "human_review")
        builder.add_edge("human_review", "finalize")
        builder.add_edge("finalize", END)

        _graph = builder.compile(checkpointer=_checkpointer)

    return _graph