"""
main_lc.py — Task 12: multi-document corpus with trust tiers.
/upload ADDS a document. GET /documents lists them. DELETE /documents/{id}
removes only that document's chunks. Citations name the document.
Trust tiers control eligibility and preference — decided in CODE, not
by asking the model to "be careful."
Run with: uvicorn app.main_lc:app --reload --port 8002
"""

import uuid
from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel
from langgraph.prebuilt import create_react_agent

from app.chunking_lc import chunk_text_lc
from app.vectorstore_lc import get_vectorstore, add_document_chunks, delete_document_chunks, get_top_chunks_lc
from app.rewriting_lc import rewrite_question_lc, chat_model
from app.answering_lc import generate_answer_lc
from app.agent_tools import search_book, book_stats, set_agent_state
from app.memory import init_db, save_turn, get_history
from app.logging_lc import log_event, Timer
from app.injection_screen import screen_chunks
from app.document_registry import init_registry_db, add_document, list_documents, get_document, delete_document
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M, LC_SIMILARITY_THRESHOLD

app = FastAPI()

init_db()
init_registry_db()

TRUST_LEVELS = ["verified", "unverified"]


@app.post("/upload")
async def upload(file: UploadFile, trust_level: str = Form(default="unverified")):
    if trust_level not in TRUST_LEVELS:
        return {"error": f"trust_level must be one of {TRUST_LEVELS}"}

    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")

    chunks = chunk_text_lc(text)
    chunks = screen_chunks(chunks)
    flagged_count = sum(1 for c in chunks if c["flagged"])

    doc_id = add_document(file.filename, trust_level, len(chunks))
    add_document_chunks(chunks, doc_id)

    return {
        "message": f"Added document '{file.filename}' to the corpus",
        "doc_id": doc_id,
        "trust_level": trust_level,
        "chunks_created": len(chunks),
        "chunks_flagged_for_injection_patterns": flagged_count
    }


@app.get("/documents")
async def get_documents():
    return {"documents": list_documents()}


@app.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}

    delete_document_chunks(doc_id)  # only this doc's vectors
    delete_document(doc_id)          # only this doc's registry row

    return {"message": f"Removed document '{doc['filename']}' (doc_id: {doc_id})"}


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
        "trust_level": doc["trust_level"] if doc else "unknown",
        "chunk_id": chunk["chunk_id"],
        "start_position": chunk["start_position"]
    }


@app.post("/ask")
async def ask(request: AskRequest):
    request_id = uuid.uuid4().hex[:12]

    with Timer() as request_timer:
        all_docs = list_documents()
        if not all_docs:
            return {"error": "No documents have been uploaded yet. Use /upload first."}

        # Trust tier eligibility: CODE decides which doc_ids are allowed to
        # answer at all — this is not a prompt instruction to the model.
        if request.trust_filter == "verified_only":
            allowed_doc_ids = {d["doc_id"] for d in all_docs if d["trust_level"] == "verified"}
        else:
            allowed_doc_ids = {d["doc_id"] for d in all_docs}

        if not allowed_doc_ids:
            return {"error": "No documents match the requested trust filter."}

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

    # Code-level signal (not relying on the model's wording): if the
    # answer draws on more than one document, or documents at different
    # trust levels, surface that explicitly.
    distinct_doc_ids = {c["doc_id"] for c in citations}
    distinct_trust_levels = {c["trust_level"] for c in citations}
    multiple_sources_used = len(distinct_doc_ids) > 1
    mixed_trust_levels = len(distinct_trust_levels) > 1

    log_event(
        session_id=request.session_id, endpoint="/ask", question=request.question,
        was_rewritten=was_rewritten, gate_score=gate_score, gate_passed=True,
        outcome=outcome, retry_fired=retry_fired, retry_succeeded=retry_succeeded,
        llm_calls=llm_calls, cost=round(total_cost, 6), latency_seconds=round(request_timer.elapsed, 3),
        request_id=request_id, cited_documents=[{"doc_id": c["doc_id"], "trust_level": c["trust_level"]} for c in citations]
    )

    return {
        "original_question": request.question,
        "rewritten_question": rewritten_question,
        "gate_score": gate_score,
        "answer": answer_text,
        "citations": citations,
        "multiple_sources_used": multiple_sources_used,
        "mixed_trust_levels": mixed_trust_levels,
        "cost": round(total_cost, 6)
    }

@app.get("/history/{session_id}")
async def history(session_id: str):
    return {"session_id": session_id, "history": get_history(session_id)}