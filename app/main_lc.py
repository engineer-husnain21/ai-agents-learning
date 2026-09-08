"""
main_lc.py — Task 13: verification lifecycle (pending -> verified/rejected,
with demotion on content change). /ask only answers from verified
documents when trust_filter=verified_only; pending/rejected/demoted are
never eligible for verified-only queries.
Run with: uvicorn app.main_lc:app --reload --port 8002
"""

import uuid
from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel

from app.chunking_lc import chunk_text_lc
from app.vectorstore_lc import get_vectorstore, add_document_chunks, delete_document_chunks, get_top_chunks_lc
from app.rewriting_lc import rewrite_question_lc, chat_model
from app.answering_lc import generate_answer_lc
from app.memory import init_db, save_turn, get_history
from app.logging_lc import log_event, Timer
from app.injection_screen import screen_chunks
from app.content_hash import compute_content_hash
from app.contradiction_detector import check_new_document_for_contradictions
from app.document_registry import (
    init_registry_db, add_document, approve_document, reject_document,
    demote_document, list_documents, get_document, delete_document
)
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M, LC_SIMILARITY_THRESHOLD

app = FastAPI()

init_db()
init_registry_db()

TRUST_LEVELS = ["verified", "unverified"]

# in-memory cache of each doc's full text, so we can re-hash it on read
# to detect out-of-band content changes (demotion trigger)
_document_text_cache = {}


@app.post("/upload")
async def upload(file: UploadFile, trust_level: str = Form(default="unverified")):
    if trust_level not in TRUST_LEVELS:
        return {"error": f"trust_level must be one of {TRUST_LEVELS}"}

    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")
    content_hash = compute_content_hash(text)

    chunks = chunk_text_lc(text)
    chunks = screen_chunks(chunks)
    flagged_count = sum(1 for c in chunks if c["flagged"])

    doc_id = add_document(file.filename, trust_level, len(chunks), content_hash)
    add_document_chunks(chunks, doc_id)
    _document_text_cache[doc_id] = text
    contradiction_flags = check_new_document_for_contradictions(chunks, doc_id)

    return {
        "message": f"Added document '{file.filename}' as PENDING — not eligible for verified-only questions until approved",
        "doc_id": doc_id,
        "status": "pending",
        "chunks_created": len(chunks),
        "chunks_flagged_for_injection_patterns": flagged_count,
        "contradictions_flagged": len(contradiction_flags),
        "contradiction_details": contradiction_flags
    }


class ApproveRequest(BaseModel):
    approved_by: str


@app.post("/documents/{doc_id}/approve")
async def approve(doc_id: str, request: ApproveRequest):
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}

    text = _document_text_cache.get(doc_id, "")
    current_hash = compute_content_hash(text)

    approve_document(doc_id, request.approved_by, current_hash)
    return {
        "message": f"'{doc['filename']}' approved and verified",
        "approved_by": request.approved_by,
        "status": "verified"
    }


class RejectRequest(BaseModel):
    rejected_by: str
    reason: str


@app.post("/documents/{doc_id}/reject")
async def reject(doc_id: str, request: RejectRequest):
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}
    if not request.reason.strip():
        return {"error": "A rejection reason is required."}

    reject_document(doc_id, request.rejected_by, request.reason)
    return {
        "message": f"'{doc['filename']}' rejected",
        "rejected_by": request.rejected_by,
        "reason": request.reason,
        "status": "rejected"
    }


@app.get("/documents")
async def get_documents():
    return {"documents": list_documents()}


@app.put("/documents/{doc_id}/content")
async def update_document_content(doc_id: str, file: UploadFile):
    """
    Task 13, corrected per testing: since documents arrive as uploaded
    bytes (no persistent disk path the server can re-read), content can
    only change through OUR API — there is no out-of-band file to poll.
    So the demotion check happens at WRITE time (here), not on every read.
    If the document was verified, changing its content demotes it.
    """
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}

    raw_bytes = await file.read()
    new_text = raw_bytes.decode("utf-8")
    new_hash = compute_content_hash(new_text)

    was_verified = doc["status"] == "verified"
    content_changed = new_hash != doc["content_hash"]

    delete_document_chunks(doc_id)
    new_chunks = chunk_text_lc(new_text)
    new_chunks = screen_chunks(new_chunks)
    add_document_chunks(new_chunks, doc_id)
    _document_text_cache[doc_id] = new_text

    if was_verified and content_changed:
        demote_document(doc_id)
        new_status = "demoted"
    else:
        new_status = doc["status"]

    return {
        "message": f"Content updated for '{doc['filename']}'",
        "content_changed": content_changed,
        "was_verified": was_verified,
        "new_status": new_status
    }

@app.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}
    delete_document_chunks(doc_id)
    delete_document(doc_id)
    _document_text_cache.pop(doc_id, None)
    return {"message": f"Removed document '{doc['filename']}' (doc_id: {doc_id})"}


def check_and_demote_if_changed(doc):
    """
    Read-time content-change check (per plan decision: files can be
    edited out-of-band, so we check on read, not only on write).
    """
    if doc["status"] != "verified":
        return doc
    cached_text = _document_text_cache.get(doc["doc_id"], "")
    current_hash = compute_content_hash(cached_text)
    if current_hash != doc["content_hash"]:
        demote_document(doc["doc_id"])
        return get_document(doc["doc_id"])
    return doc


class AskRequest(BaseModel):
    session_id: str
    question: str
    trust_filter: str = "any"  # "any" | "verified_only"


def build_citation(chunk):
    doc = get_document(chunk["doc_id"])
    filename = doc["filename"] if doc else "unknown document"
    return {
        "document": filename,
        "doc_id": chunk["doc_id"],
        "status": doc["status"] if doc else "unknown",
        "chunk_id": chunk["chunk_id"],
        "start_position": chunk["start_position"]
    }


@app.post("/ask")
async def ask(request: AskRequest):
    request_id = uuid.uuid4().hex[:12]

    with Timer() as request_timer:
        all_docs = [check_and_demote_if_changed(d) for d in list_documents()]
        if not all_docs:
            return {"error": "No documents have been uploaded yet. Use /upload first."}

        # Eligibility is a CODE decision: only verified docs count for
        # verified_only; pending/rejected/demoted are never eligible.
        if request.trust_filter == "verified_only":
            allowed_doc_ids = {d["doc_id"] for d in all_docs if d["status"] == "verified"}
        else:
            allowed_doc_ids = {d["doc_id"] for d in all_docs if d["status"] in ("verified", "pending")}

        if not allowed_doc_ids:
            return {"error": "No documents match the requested filter."}

        vectorstore = get_vectorstore()
        history = get_history(request.session_id, limit=HISTORY_LENGTH)

        rewritten_question, rw_in, rw_out = rewrite_question_lc(request.question, history, request_id=request_id)
        was_rewritten = rewritten_question != request.question
        rewrite_cost = (rw_in / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
        rewrite_cost += (rw_out / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M
        llm_calls = 1 if history else 0

        top_chunks = get_top_chunks_lc(vectorstore, rewritten_question, allowed_doc_ids=allowed_doc_ids)
        gate_score = round(top_chunks[0]["score"], 4) if top_chunks else 0
        gate_passed = top_chunks and top_chunks[0]["score"] >= LC_SIMILARITY_THRESHOLD

        retry_fired = False
        retry_succeeded = None

        if not gate_passed:
            answer_text = "The document does not contain an answer to this question."
            outcome = "refused_by_gate"
            total_cost = rewrite_cost
            save_turn(request.session_id, request.question, answer_text)
            log_event(
                session_id=request.session_id, endpoint="/ask", question=request.question,
                was_rewritten=was_rewritten, gate_score=gate_score, gate_passed=False,
                outcome=outcome, retry_fired=False, retry_succeeded=None,
                llm_calls=llm_calls, cost=round(total_cost, 6), latency_seconds=None,
                request_id=request_id
            )
            return {
                "original_question": request.question, "rewritten_question": rewritten_question,
                "gate_score": gate_score, "answer": answer_text, "citations": [],
                "cost": round(total_cost, 6)
            }

        answer_text, chat_cost = generate_answer_lc(
            rewritten_question, top_chunks, history, request_id=request_id, step="answer"
        )
        llm_calls += 1

        outcome = "answered"
        if "does not contain an answer" in answer_text.lower():
            outcome = "refused_by_model"
            retry_fired = True
            retry_answer, retry_cost = generate_answer_lc(
                rewritten_question, top_chunks, history, request_id=request_id, step="retry_answer"
            )
            llm_calls += 1
            chat_cost += retry_cost
            answer_text = retry_answer
            retry_succeeded = "does not contain an answer" not in retry_answer.lower()
            if retry_succeeded:
                outcome = "answered"

        total_cost = rewrite_cost + chat_cost
        save_turn(request.session_id, request.question, answer_text)

    citations = [build_citation(c) for c in top_chunks]
    distinct_doc_ids = {c["doc_id"] for c in citations}
    distinct_statuses = {c["status"] for c in citations}

    log_event(
        session_id=request.session_id, endpoint="/ask", question=request.question,
        was_rewritten=was_rewritten, gate_score=gate_score, gate_passed=True,
        outcome=outcome, retry_fired=retry_fired, retry_succeeded=retry_succeeded,
        llm_calls=llm_calls, cost=round(total_cost, 6), latency_seconds=round(request_timer.elapsed, 3),
        request_id=request_id,
        cited_documents=[{"doc_id": c["doc_id"], "trust_level": c["status"]} for c in citations]
    )

    return {
        "original_question": request.question,
        "rewritten_question": rewritten_question,
        "gate_score": gate_score,
        "answer": answer_text,
        "citations": citations,
        "multiple_sources_used": len(distinct_doc_ids) > 1,
        "mixed_status": len(distinct_statuses) > 1,
        "cost": round(total_cost, 6)
    }


@app.get("/history/{session_id}")
async def history(session_id: str):
    return {"session_id": session_id, "history": get_history(session_id)}