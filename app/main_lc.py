"""
main_lc.py — SAME contract as app/main.py (task 5.5): /upload, /ask, /history.
Internals rebuilt with LangChain: RecursiveCharacterTextSplitter, Chroma,
AzureOpenAIEmbeddings, AzureChatOpenAI. Threshold gate, refusal messages,
and SQLite memory are still OURS — the framework doesn't decide those.
Run with: uvicorn app.main_lc:app --reload --port 8002
"""

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

from app.chunking_lc import chunk_text_lc
from app.vectorstore_lc import build_vectorstore, get_top_chunks_lc
from app.rewriting_lc import rewrite_question_lc
from app.answering_lc import generate_answer_lc
from app.retrieval import passes_gate  # our gate logic, unchanged
from app.memory import init_db, save_turn, get_history
from app.config import HISTORY_LENGTH

app = FastAPI()

state = {
    "vectorstore": None
}

init_db()


@app.post("/upload")
async def upload(file: UploadFile):
    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")

    chunks = chunk_text_lc(text)
    state["vectorstore"] = build_vectorstore(chunks)

    return {
        "message": f"Uploaded and processed '{file.filename}'",
        "chunks_created": len(chunks)
    }


class AskRequest(BaseModel):
    session_id: str
    question: str


@app.post("/ask")
async def ask(request: AskRequest):
    if state["vectorstore"] is None:
        return {"error": "No document has been uploaded yet. Use /upload first."}

    history = get_history(request.session_id, limit=HISTORY_LENGTH)

    # STEP 1: rewrite (only if history exists) — same rules as task 5.5
    rewritten_question, rw_in, rw_out = rewrite_question_lc(request.question, history)
    from app.config import CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M
    rewrite_cost = (rw_in / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    rewrite_cost += (rw_out / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    # STEP 2: retrieve via Chroma. STEP 3: OUR gate, unchanged.
    top_chunks = get_top_chunks_lc(state["vectorstore"], rewritten_question)

    from app.config import LC_SIMILARITY_THRESHOLD
    gate_passed = top_chunks and top_chunks[0]["score"] >= LC_SIMILARITY_THRESHOLD

    if not gate_passed:
        answer_text = "The document does not contain an answer to this question."
        save_turn(request.session_id, request.question, answer_text)
        return {
            "original_question": request.question,
            "rewritten_question": rewritten_question,
            "gate_score": round(top_chunks[0]["score"], 4) if top_chunks else 0,
            "answer": answer_text,
            "sources": [],
            "cost": round(rewrite_cost, 6)
        }

    # STEP 4: grounded answer, same rules
    answer_text, chat_cost = generate_answer_lc(rewritten_question, top_chunks, history)
    total_cost = rewrite_cost + chat_cost

    save_turn(request.session_id, request.question, answer_text)

    return {
        "original_question": request.question,
        "rewritten_question": rewritten_question,
        "gate_score": round(top_chunks[0]["score"], 4),
        "answer": answer_text,
        "sources": [
            {"chunk_id": c["chunk_id"], "start_position": c["start_position"]}
            for c in top_chunks
        ],
        "cost": round(total_cost, 6)
    }


@app.get("/history/{session_id}")
async def history(session_id: str):
    return {"session_id": session_id, "history": get_history(session_id)}