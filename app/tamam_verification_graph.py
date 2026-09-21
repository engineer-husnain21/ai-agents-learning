"""
tamam_verification_graph.py — same LangGraph pause/resume lifecycle as
task 14, pointed at Tamam's own registry/vectorstore/checkpointer.
A manager uploads a document; it stays pending until the Operations
Director (the approver) approves or rejects it.
"""

import sqlite3
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver

from app.injection_screen import screen_chunks
from app.tamam_contradiction_detector import check_new_document_for_contradictions
from app.tamam_document_registry import approve_document, reject_document


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
    payload = interrupt({
        "doc_id": state["doc_id"], "filename": state["filename"],
        "flagged_count": state["flagged_count"], "contradiction_flags": state["contradiction_flags"],
        "message": "Waiting for Operations Director decision."
    })
    return {
        "decision": payload.get("decision"),
        "approved_by": payload.get("by", "unknown"),
        "reason": payload.get("reason", "")
    }


def finalize_node(state: VerificationState):
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
    global _checkpointer, _conn, _graph
    if _graph is None:
        _conn = sqlite3.connect("tamam_verification_graph.db", check_same_thread=False)
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