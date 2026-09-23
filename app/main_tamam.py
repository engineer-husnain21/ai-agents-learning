"""
main_tamam.py — Tamam Living tenant assistant.

Security model (client's #1 requirement: "never, ever see another
tenant's data"):
  - tenant_id comes from the portal's own login session, NOT typed by
    the tenant — the API trusts the portal, not the user's free text.
  - Every DATA question runs against a freshly-built, in-memory,
    tenant-scoped database (tamam_isolation.py) containing ONLY that
    tenant's rows. Other tenants' data is structurally absent, not
    just filtered out by a WHERE clause we hope the model got right.
  - Conversation history is keyed by tenant_id + conversation_id, so a
    tenant can never address another tenant's session either.

Legal questions are ALWAYS escalated to a human, never answered by the
model — a hard rule, not a preference (see tamam_router.py).

Run with: uvicorn app.main_tamam:app --reload --port 8003
"""

import json
import sqlite3
import uuid
from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel
from langgraph.types import Command

from app.chunking_lc import chunk_text_lc
from app.rewriting_lc import rewrite_question_lc, chat_model
from app.answering_lc import generate_answer_lc
from app.injection_screen import screen_chunks
from app.content_hash import compute_content_hash
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M, LC_SIMILARITY_THRESHOLD

from app.tamam_memory import init_db as init_tamam_memory_db, save_turn, get_history
from app.tamam_logging import log_event, log_span, Timer, LOG_PATH as TAMAM_LOG_PATH
from app.tamam_isolation import build_tenant_scoped_db, build_manager_scoped_db, MAIN_DB_PATH
from app.tamam_router import classify_route
from app.tamam_sql_pipeline import generate_and_run_sql, TENANT_SCHEMA, BUILDING_SCHEMA
from app.tamam_contradiction_detector import check_new_document_for_contradictions
from app.tamam_vectorstore import get_vectorstore, add_document_chunks, delete_document_chunks, get_top_chunks_lc
from app.tamam_verification_graph import get_verification_graph
from app.tamam_document_registry import (
    init_registry_db, add_document, list_documents, get_document, delete_document
)

app = FastAPI()

init_tamam_memory_db()
init_registry_db()

_document_text_cache = {}

LEGAL_ESCALATION_MESSAGE = (
    "This looks like a legal question, and I'm not able to answer it - "
    "I've passed it to our team, and someone will follow up with you directly."
)


# ---------- Document management (manager uploads, OD approves) ----------

@app.post("/upload")
async def upload(file: UploadFile, scope: str = Form(...), building_id: int = Form(default=None)):
    if scope not in ("master", "addendum"):
        return {"error": "scope must be 'master' or 'addendum'"}
    if scope == "addendum" and building_id is None:
        return {"error": "building_id is required for an addendum"}

    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")
    content_hash = compute_content_hash(text)

    chunks = chunk_text_lc(text)
    doc_id = add_document(file.filename, scope, building_id, len(chunks), content_hash)
    add_document_chunks(chunks, doc_id)
    _document_text_cache[doc_id] = text

    graph = get_verification_graph()
    config = {"configurable": {"thread_id": doc_id}}
    paused_state = graph.invoke({
        "doc_id": doc_id, "filename": file.filename, "chunks": chunks,
        "content_hash": content_hash, "decision": "", "approved_by": "",
        "reason": "", "status": "pending"
    }, config=config)

    return {
        "message": f"'{file.filename}' added as PENDING ({scope}) - waiting for Operations Director approval",
        "doc_id": doc_id, "status": "pending",
        "chunks_flagged_for_injection_patterns": paused_state.get("flagged_count", 0),
        "contradictions_flagged": len(paused_state.get("contradiction_flags", [])),
        "contradiction_details": paused_state.get("contradiction_flags", [])
    }


class ApproveRequest(BaseModel):
    approved_by: str


@app.post("/documents/{doc_id}/approve")
async def approve(doc_id: str, request: ApproveRequest):
    doc = get_document(doc_id)
    if doc is None:
        return {"error": f"No document with doc_id '{doc_id}'"}
    graph = get_verification_graph()
    config = {"configurable": {"thread_id": doc_id}}
    graph.invoke(Command(resume={"decision": "approve", "by": request.approved_by}), config=config)
    return {"message": f"'{doc['filename']}' approved and verified", "status": "verified"}


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
    graph = get_verification_graph()
    config = {"configurable": {"thread_id": doc_id}}
    graph.invoke(Command(resume={"decision": "reject", "by": request.rejected_by, "reason": request.reason}), config=config)
    return {"message": f"'{doc['filename']}' rejected", "status": "rejected"}


@app.get("/documents")
async def get_documents():
    return {"documents": list_documents()}


# ---------- Helper: which building does a tenant belong to ----------

def get_tenant_building_id(tenant_id):
    conn = sqlite3.connect(f"file:{MAIN_DB_PATH}?mode=ro", uri=True)
    row = conn.execute("""
        SELECT u.building_id FROM tenants t JOIN units u ON t.unit_id = u.unit_id
        WHERE t.tenant_id = ?
    """, (tenant_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def get_building_name(building_id):
    conn = sqlite3.connect(f"file:{MAIN_DB_PATH}?mode=ro", uri=True)
    row = conn.execute("SELECT building_name FROM buildings WHERE building_id = ?", (building_id,)).fetchone()
    conn.close()
    return row[0] if row else "your building"


# ---------- Tenant-facing ask ----------

class TenantAskRequest(BaseModel):
    tenant_id: int          # trusted: supplied by the portal's own login session, not typed by the tenant
    conversation_id: str    # arbitrary per-conversation id, namespaced by tenant_id below
    question: str


@app.post("/ask")
async def ask(request: TenantAskRequest):
    request_id = uuid.uuid4().hex[:12]
    session_key = f"t{request.tenant_id}_{request.conversation_id}"  # tenant_id baked in, not user-controlled

    with Timer() as request_timer:
        history = get_history(session_key, limit=HISTORY_LENGTH)

        rewritten_question, rw_in, rw_out = rewrite_question_lc(request.question, history, request_id=request_id)
        rewrite_cost = (rw_in / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
        rewrite_cost += (rw_out / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

        context = "\n".join(f"Q: {t['question']}\nA: {t['answer']}" for t in history) if history else ""
        route, route_in, route_out = classify_route(rewritten_question, context)
        route_cost = (route_in / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
        route_cost += (route_out / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

        llm_calls = 2 if history else 1

        if route == "LEGAL_ESCALATION":
            total_cost = rewrite_cost + route_cost
            save_turn(session_key, request.question, LEGAL_ESCALATION_MESSAGE)
            log_event(session_key, route, request.question, "escalated", llm_calls,
                      round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
            return {"route": route, "answer": LEGAL_ESCALATION_MESSAGE, "cost": round(total_cost, 6)}

        if route == "OFF_TOPIC":
            answer_text = "I can only help with questions about your own tenancy or Tamam Living's policies."
            total_cost = rewrite_cost + route_cost
            save_turn(session_key, request.question, answer_text)
            log_event(session_key, route, request.question, "off_topic", llm_calls,
                      round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
            return {"route": route, "answer": answer_text, "cost": round(total_cost, 6)}

        if route == "DATA":
            scoped_conn = build_tenant_scoped_db(request.tenant_id)
            if scoped_conn is None:
                return {"error": "Tenant not found."}

            sql_result = generate_and_run_sql(rewritten_question, scoped_conn, TENANT_SCHEMA)
            scoped_conn.close()

            sql_cost = (sql_result["input_tokens"] / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
            sql_cost += (sql_result["output_tokens"] / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M
            total_cost = rewrite_cost + route_cost + sql_cost

            if sql_result["error"]:
                answer_text = "I couldn't safely answer this question about your account right now."
                save_turn(session_key, request.question, answer_text)
                log_event(session_key, route, request.question, "sql_error", llm_calls + 1,
                          round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
                return {"route": route, "answer": answer_text, "sql_query": sql_result["query"], "cost": round(total_cost, 6)}

            if sql_result["no_data"]:
                answer_text = "I don't have a record matching that for your account."
                save_turn(session_key, request.question, answer_text)
                log_event(session_key, route, request.question, "no_data", llm_calls + 1,
                          round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
                return {"route": route, "answer": answer_text, "sql_query": sql_result["query"], "cost": round(total_cost, 6)}

            phrase_prompt = f"""Question: {rewritten_question}
SQL query used: {sql_result['query']}
Columns: {sql_result['columns']}
Rows: {sql_result['rows']}

Answer in one or two plain, friendly sentences, using ONLY these results. Speak directly to the tenant ("you", "your").
CURRENCY: every money amount in these results is in UAE dirhams. Always write amounts as "AED 9,000" - never use "$" or "dollars".
IMPORTANT: these results are ONLY this one tenant's own data - you have no visibility into any other tenant's records. NEVER claim a comparison to other tenants (e.g. "highest among all tenants," "the only one with this"), even if the query's row count or matched_rows value seems to suggest it. If the question asked for a comparison to others, state only this tenant's own value and say you don't have visibility into other tenants' data to compare."""
            response = chat_model.invoke(phrase_prompt)
            phrase_cost = (response.usage_metadata["input_tokens"] / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
            phrase_cost += (response.usage_metadata["output_tokens"] / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M
            total_cost += phrase_cost

            answer_text = response.content.strip()
            save_turn(session_key, request.question, answer_text)
            log_event(session_key, route, request.question, "answered", llm_calls + 2,
                      round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
            return {"route": route, "answer": answer_text, "sql_query": sql_result["query"], "cost": round(total_cost, 6)}

        # route == "POLICY"
        building_id = get_tenant_building_id(request.tenant_id)
        all_docs = list_documents()
        allowed_doc_ids = {
            d["doc_id"] for d in all_docs
            if d["status"] == "verified" and (d["scope"] == "master" or d["building_id"] == building_id)
        }

        if not allowed_doc_ids:
            answer_text = "I don't have an approved policy document to answer that from yet."
            total_cost = rewrite_cost + route_cost
            save_turn(session_key, request.question, answer_text)
            return {"route": route, "answer": answer_text, "citations": [], "cost": round(total_cost, 6)}

        vectorstore = get_vectorstore()
        top_chunks = get_top_chunks_lc(vectorstore, rewritten_question, allowed_doc_ids=allowed_doc_ids)
        gate_score = round(top_chunks[0]["score"], 4) if top_chunks else 0
        gate_passed = top_chunks and top_chunks[0]["score"] >= LC_SIMILARITY_THRESHOLD

        if not gate_passed:
            answer_text = "I don't have policy information to answer that."
            total_cost = rewrite_cost + route_cost
            save_turn(session_key, request.question, answer_text)
            log_event(session_key, route, request.question, "refused_by_gate", llm_calls,
                      round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)
            return {"route": route, "gate_score": gate_score, "answer": answer_text, "citations": [], "cost": round(total_cost, 6)}

        # Day 3 fix: the model used to receive bare chunks with no idea which
        # document each came from, so "addendum overrides handbook" only worked
        # because the addendum's own text happens to say so. Now every chunk is
        # labelled with its source, precedence is stated, and the tenant's
        # building is named - enforced here, not left to the model to infer.
        building_name = get_building_name(building_id)
        docs_by_id = {d["doc_id"]: d for d in all_docs}
        labelled_chunks = []
        for c in top_chunks:
            doc = docs_by_id.get(c["doc_id"])
            if doc and doc["scope"] == "addendum":
                source = (f"{building_name} building addendum - where it differs from the Tenant Handbook, "
                          f"THIS rule applies to {building_name} tenants")
            else:
                source = "Tamam Living Tenant Handbook - applies to all buildings unless a building addendum says otherwise"
            labelled_chunks.append({**c, "text": f"[Source: {source}]\n{c['text']}"})
        answer_question = (f"{rewritten_question}\n(The tenant asking lives in {building_name}. "
                           f"Answer directly for {building_name}; do not describe rules for other buildings.)")

        answer_text, chat_cost = generate_answer_lc(answer_question, labelled_chunks, history, request_id=request_id, step="answer")
        total_cost = rewrite_cost + route_cost + chat_cost
        save_turn(session_key, request.question, answer_text)

    citations = []
    for c in top_chunks:
        doc = get_document(c["doc_id"])
        citations.append({
            "document": doc["filename"] if doc else "unknown",
            "scope": doc["scope"] if doc else "unknown",
            "chunk_id": c["chunk_id"]
        })

    # Day 3 fix: this used to sit inside the citation loop with outcome
    # "escalated", so every answered policy question was logged N times
    # as an escalation. One answered event per question now.
    log_event(session_key, route, request.question, "answered", llm_calls + 1,
              round(total_cost, 6), None, tenant_id=request.tenant_id, request_id=request_id)

    return {
        "route": route, "gate_score": gate_score, "answer": answer_text,
        "citations": citations, "cost": round(total_cost, 6)
    }


# ---------- Building-manager-facing ask (aggregate only, no tenant PII) ----------

class ManagerAskRequest(BaseModel):
    building_id: int
    question: str


@app.post("/manager_ask")
async def manager_ask(request: ManagerAskRequest):
    request_id = uuid.uuid4().hex[:12]
    scoped_conn = build_manager_scoped_db(request.building_id)
    if scoped_conn is None:
        return {"error": "Building not found."}

    sql_result = generate_and_run_sql(request.question, scoped_conn, BUILDING_SCHEMA)
    scoped_conn.close()

    cost = (sql_result["input_tokens"] / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    cost += (sql_result["output_tokens"] / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    if sql_result["error"]:
        return {"answer": "Couldn't safely answer that.", "sql_query": sql_result["query"], "cost": round(cost, 6)}
    if sql_result["no_data"]:
        return {"answer": "No matching data for that.", "sql_query": sql_result["query"], "cost": round(cost, 6)}

    phrase_prompt = f"""Question: {request.question}
SQL: {sql_result['query']}
Columns: {sql_result['columns']}
Rows: {sql_result['rows']}

Answer in one or two plain sentences using ONLY these results.
CURRENCY: any money amount is in UAE dirhams - write it as "AED 9,000", never "$"."""
    response = chat_model.invoke(phrase_prompt)
    cost += (response.usage_metadata["input_tokens"] / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    cost += (response.usage_metadata["output_tokens"] / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    log_event(f"manager_{request.building_id}", "DATA", request.question, "answered", 2,
              round(cost, 6), None, request_id=request_id)

    return {"answer": response.content.strip(), "sql_query": sql_result["query"], "cost": round(cost, 6)}


# ---------- Staff-facing escalation queue ----------
# The legal message tells the tenant "I've passed it to our team". Before
# Day 3 that was only a log line nobody was shown. This endpoint is the
# team's list of legal questions waiting for a human follow-up.
# Staff-only: it must sit behind Tamam's staff login, never the tenant portal.

@app.get("/escalations")
async def escalations():
    items = []
    try:
        with open(TAMAM_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("route") == "LEGAL_ESCALATION" and event.get("outcome") == "escalated":
                    items.append({
                        "timestamp": event.get("timestamp"),
                        "tenant_id": event.get("tenant_id"),
                        "question": event.get("question"),
                        "request_id": event.get("request_id"),
                    })
    except FileNotFoundError:
        pass
    items.reverse()  # newest first
    return {"count": len(items), "escalations": items}


@app.get("/history/{tenant_id}/{conversation_id}")
async def history(tenant_id: int, conversation_id: str):
    session_key = f"t{tenant_id}_{conversation_id}"
    return {"session_id": session_key, "history": get_history(session_key)}