"""
main_lc.py — /upload, /ask, /ask_agent, /history, /stats.
Task 10: every /ask call is logged as a structured event.
Run with: uvicorn app.main_lc:app --reload --port 8002
"""

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from langgraph.prebuilt import create_react_agent

from app.chunking_lc import chunk_text_lc
from app.vectorstore_lc import build_vectorstore, get_top_chunks_lc
from app.rewriting_lc import rewrite_question_lc, chat_model
from app.answering_lc import generate_answer_lc
from app.agent_tools import search_book, book_stats, set_agent_state
from app.memory import init_db, save_turn, get_history
from app.logging_lc import log_event, Timer
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M, LC_SIMILARITY_THRESHOLD

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

    set_agent_state(state["vectorstore"], file.filename, len(text), len(chunks))

    return {
        "message": f"Uploaded and processed '{file.filename}'",
        "chunks_created": len(chunks)
    }


class AskRequest(BaseModel):
    session_id: str
    question: str


@app.post("/ask")
async def ask(request: AskRequest):
    with Timer() as request_timer:
        if state["vectorstore"] is None:
            return {"error": "No document has been uploaded yet. Use /upload first."}

        history = get_history(request.session_id, limit=HISTORY_LENGTH)

        rewritten_question, rw_in, rw_out = rewrite_question_lc(request.question, history)
        was_rewritten = rewritten_question != request.question
        rewrite_cost = (rw_in / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
        rewrite_cost += (rw_out / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M
        llm_calls = 1 if history else 0  # rewrite only calls the model if there's history

        top_chunks = get_top_chunks_lc(state["vectorstore"], rewritten_question)
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
                llm_calls=llm_calls, cost=round(total_cost, 6), latency_seconds=None
            )
            result = {
                "original_question": request.question, "rewritten_question": rewritten_question,
                "gate_score": gate_score, "answer": answer_text, "sources": [],
                "cost": round(total_cost, 6)
            }
            return result

        answer_text, chat_cost = generate_answer_lc(rewritten_question, top_chunks, history)
        llm_calls += 1

        outcome = "answered"
        if "does not contain an answer" in answer_text.lower():
            outcome = "refused_by_model"
            retry_fired = True
            retry_answer, retry_cost = generate_answer_lc(rewritten_question, top_chunks, history)
            llm_calls += 1
            chat_cost += retry_cost
            answer_text = retry_answer
            retry_succeeded = "does not contain an answer" not in retry_answer.lower()
            if retry_succeeded:
                outcome = "answered"

        total_cost = rewrite_cost + chat_cost
        save_turn(request.session_id, request.question, answer_text)

    log_event(
        session_id=request.session_id, endpoint="/ask", question=request.question,
        was_rewritten=was_rewritten, gate_score=gate_score, gate_passed=True,
        outcome=outcome, retry_fired=retry_fired, retry_succeeded=retry_succeeded,
        llm_calls=llm_calls, cost=round(total_cost, 6), latency_seconds=round(request_timer.elapsed, 3)
    )

    return {
        "original_question": request.question,
        "rewritten_question": rewritten_question,
        "gate_score": gate_score,
        "answer": answer_text,
        "sources": [
            {"chunk_id": c["chunk_id"], "start_position": c["start_position"]}
            for c in top_chunks
        ],
        "cost": round(total_cost, 6)
    }


SYSTEM_PROMPT = """You are a helpful assistant answering questions about an uploaded document.

Rules:
- For any question about the book's content, use the search_book tool. Answer ONLY from what it returns.
- If search_book says "nothing relevant found in the document", say exactly that to the user — do not guess or use outside knowledge.
- For questions about the book's size/structure (character count, chunk count, filename), use the book_stats tool.
- Never answer a content question about the book without calling search_book first.
- For greetings or small talk unrelated to the book, you may respond directly without calling any tool."""

agent = create_react_agent(chat_model, tools=[search_book, book_stats], prompt=SYSTEM_PROMPT)


@app.post("/ask_agent")
async def ask_agent(request: AskRequest):
    if state["vectorstore"] is None:
        return {"error": "No document has been uploaded yet. Use /upload first."}

    history = get_history(request.session_id, limit=HISTORY_LENGTH)

    messages = []
    for turn in history:
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": request.question})

    result = agent.invoke({"messages": messages})

    tools_called = []
    total_input_tokens = 0
    total_output_tokens = 0

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_called.append(tc["name"])
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            total_input_tokens += msg.usage_metadata.get("input_tokens", 0)
            total_output_tokens += msg.usage_metadata.get("output_tokens", 0)

    answer_text = result["messages"][-1].content

    cost = (total_input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    cost += (total_output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    save_turn(request.session_id, request.question, answer_text)

    return {
        "answer": answer_text,
        "tools_called": tools_called,
        "llm_calls": sum(1 for m in result["messages"] if hasattr(m, "usage_metadata") and m.usage_metadata),
        "cost": round(cost, 6)
    }


@app.get("/history/{session_id}")
async def history(session_id: str):
    return {"session_id": session_id, "history": get_history(session_id)}