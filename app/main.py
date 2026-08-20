"""
main.py — FastAPI routes: /upload, /ask, /history/{session_id}
Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

from app.chunking import chunk_text
from app.retrieval import embed_text, get_top_chunks, passes_gate
from app.answering import generate_answer
from app.memory import init_db, save_turn, get_history
from app.config import HISTORY_LENGTH

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


last_chunks_by_session = {}


@app.post("/ask")
async def ask(request: AskRequest):
    if not state["chunks"]:
        return {"error": "No document has been uploaded yet. Use /upload first."}

    history = get_history(request.session_id, limit=HISTORY_LENGTH)

    if history:
        last_turn = history[-1]
        retrieval_query = f"{last_turn['question']} {last_turn['answer']} {request.question}"
    else:
        retrieval_query = request.question

    top_chunks, embed_tokens, embed_cost = get_top_chunks(
        retrieval_query, state["embeddings"], state["chunks"]
    )

    gate_passed = passes_gate(top_chunks)

    if not gate_passed and history and request.session_id in last_chunks_by_session:
        top_chunks = last_chunks_by_session[request.session_id]
        gate_passed = True

    if not gate_passed:
        answer_text = "The document does not contain an answer to this question."
        save_turn(request.session_id, request.question, answer_text)
        return {
            "answer": answer_text,
            "sources": [],
            "cost": round(embed_cost, 6)
        }

    answer_text, chat_cost = generate_answer(request.question, top_chunks, history)
    total_cost = embed_cost + chat_cost

    save_turn(request.session_id, request.question, answer_text)
    last_chunks_by_session[request.session_id] = top_chunks

    return {
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