"""
main.py — FastAPI routes: /upload, /ask, /history/{session_id}
Run with: uvicorn app.main:app --reload
"""

import json
import os

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

from app.chunking import chunk_text
from app.retrieval import embed_text, get_top_chunks, passes_gate
from app.answering import generate_answer
from app.memory import init_db, save_turn, get_history
from app.config import HISTORY_LENGTH

STORE_DIR = "store"
CHUNKS_PATH = os.path.join(STORE_DIR, "chunks.json")
EMBEDDINGS_PATH = os.path.join(STORE_DIR, "embeddings.json")

app = FastAPI()

state = {
    "chunks": [],
    "embeddings": []
}


def save_book(chunks, embeddings):
    """Writes the current book to disk, replacing any previous files."""
    os.makedirs(STORE_DIR, exist_ok=True)
    for path in (CHUNKS_PATH, EMBEDDINGS_PATH):
        if os.path.exists(path):
            os.remove(path)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f)
    with open(EMBEDDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(embeddings, f)


def load_book():
    """Loads the last uploaded book from disk, if it exists."""
    if not os.path.exists(CHUNKS_PATH) or not os.path.exists(EMBEDDINGS_PATH):
        return [], []
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
        embeddings = json.load(f)
    return chunks, embeddings


init_db()
state["chunks"], state["embeddings"] = load_book()


@app.post("/upload")
async def upload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".txt"):
        return {"error": "Only .txt files are accepted."}

    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")

    chunks = chunk_text(text)

    embeddings = []
    for chunk in chunks:
        vector, _ = embed_text(chunk["text"])
        embeddings.append({"chunk_id": chunk["chunk_id"], "embedding": vector})

    # Replace RAM first so no request can still see the old book, then replace disk.
    state["chunks"] = chunks
    state["embeddings"] = embeddings
    save_book(chunks, embeddings)

    return {
        "message": f"Uploaded and processed '{file.filename}'",
        "chunks_created": len(chunks)
    }


class AskRequest(BaseModel):
    session_id: str
    question: str


CLEARLY_UNRELATED_CUTOFF = 0.30


@app.post("/ask")
async def ask(request: AskRequest):
    if not state["chunks"]:
        return {"error": "No document has been uploaded yet. Use /upload first."}

    history = get_history(request.session_id, limit=HISTORY_LENGTH)

    raw_chunks, raw_tokens, raw_cost = get_top_chunks(
        request.question, state["embeddings"], state["chunks"]
    )
    raw_score = raw_chunks[0]["score"] if raw_chunks else 0

    if raw_score < CLEARLY_UNRELATED_CUTOFF:
        answer_text = "The document does not contain an answer to this question."
        save_turn(request.session_id, request.question, answer_text)
        return {
            "answer": answer_text,
            "sources": [],
            "cost": round(raw_cost, 6)
        }

    if passes_gate(raw_chunks):
        top_chunks, embed_cost = raw_chunks, raw_cost
    else:
        if history:
            last_turn = history[-1]
            retrieval_query = f"{last_turn['question']} {last_turn['answer']} {request.question}"
            top_chunks, embed_tokens, embed_cost = get_top_chunks(
                retrieval_query, state["embeddings"], state["chunks"]
            )
        else:
            top_chunks, embed_cost = raw_chunks, raw_cost

        if not passes_gate(top_chunks):
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