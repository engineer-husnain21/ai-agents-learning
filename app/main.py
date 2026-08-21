"""
main.py — FastAPI routes: /upload, /ask, /history/{session_id}
Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

from app.chunking import chunk_text
from app.retrieval import embed_text, get_top_chunks, passes_gate
from app.answering import generate_answer
from app.rewriting import rewrite_question
from app.memory import init_db, save_turn, get_history
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M

app = FastAPI()

state = {
    "chunks": [],
    "embeddings": []
}

init_db()


@app.post("/upload")
async def upload(file: UploadFile):
    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")

    chunks = chunk_text(text)

    embeddings = []
    for chunk in chunks:
        vector, _ = embed_text(chunk["text"])
        embeddings.append({"chunk_id": chunk["chunk_id"], "embedding": vector})

    state["chunks"] = chunks
    state["embeddings"] = embeddings

    return {
        "message": f"Uploaded and processed '{file.filename}'",
        "chunks_created": len(chunks)
    }


class AskRequest(BaseModel):
    session_id: str
    question: str


@app.post("/ask")
async def ask(request: AskRequest):
    if not state["chunks"]:
        return {"error": "No document has been uploaded yet. Use /upload first."}

    history = get_history(request.session_id, limit=HISTORY_LENGTH)

    # STEP 1: rewrite (only if history exists). Resolves pronouns/references
    # into a standalone question BEFORE anything else touches it.
    rewritten_question, rw_input_tokens, rw_output_tokens = rewrite_question(
        request.question, history
    )
    rewrite_cost = (rw_input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    rewrite_cost += (rw_output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    # STEP 2: embed the rewritten (clean, standalone) question.
    # STEP 3: gate. STEP 4: retrieve.
    top_chunks, embed_tokens, embed_cost = get_top_chunks(
        rewritten_question, state["embeddings"], state["chunks"]
    )

    total_cost_so_far = rewrite_cost + embed_cost

    if not passes_gate(top_chunks):
        answer_text = "The document does not contain an answer to this question."
        save_turn(request.session_id, request.question, answer_text)
        return {
            "original_question": request.question,
            "rewritten_question": rewritten_question,
            "gate_score": round(top_chunks[0]["score"], 4) if top_chunks else 0,
            "answer": answer_text,
            "sources": [],
            "cost": round(total_cost_so_far, 6)
        }

    # STEP 5: answer, using the rewritten question (clean) but still
    # passing history so the model has full context if needed.
    answer_text, chat_cost = generate_answer(rewritten_question, top_chunks, history)
    total_cost = total_cost_so_far + chat_cost

    # We save the user's ORIGINAL question to history (what they actually
    # asked), not the rewrite — the rewrite is an internal retrieval detail.
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