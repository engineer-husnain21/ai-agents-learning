"""
main_agent.py — adds POST /ask_agent next to the existing /ask.
The agent gets two tools (search_book, book_stats) and decides its own
steps. Same session memory (SQLite), same response shape, plus one new
field: which tools were called, in what order.

This does NOT replace app/main_lc.py — run it separately for comparison,
or merge the route in later. For task 7 we run it as its own app so both
pipeline and agent can be tested side by side.
"""

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from langgraph.prebuilt import create_react_agent

from app.chunking_lc import chunk_text_lc
from app.vectorstore_lc import build_vectorstore
from app.agent_tools import search_book, book_stats, set_agent_state
from app.rewriting_lc import chat_model
from app.memory import init_db, save_turn, get_history
from app.config import HISTORY_LENGTH, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M

app = FastAPI()

state = {
    "vectorstore": None,
    "book_name": None,
    "total_characters": None,
    "chunk_count": None,
}

init_db()

SYSTEM_PROMPT = """You are a helpful assistant answering questions about an uploaded document.

Rules:
- For any question about the book's content, use the search_book tool. Answer ONLY from what it returns.
- If search_book says "nothing relevant found in the document", say exactly that to the user — do not guess or use outside knowledge.
- For questions about the book's size/structure (character count, chunk count, filename), use the book_stats tool.
- Never answer a content question about the book without calling search_book first.
- For greetings or small talk unrelated to the book, you may respond directly without calling any tool."""

agent = create_react_agent(chat_model, tools=[search_book, book_stats], prompt=SYSTEM_PROMPT)


@app.post("/upload")
async def upload(file: UploadFile):
    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8")

    chunks = chunk_text_lc(text)
    vectorstore = build_vectorstore(chunks)

    state["vectorstore"] = vectorstore
    state["book_name"] = file.filename
    state["total_characters"] = len(text)
    state["chunk_count"] = len(chunks)

    set_agent_state(vectorstore, file.filename, len(text), len(chunks))

    return {
        "message": f"Uploaded and processed '{file.filename}'",
        "chunks_created": len(chunks)
    }


class AskRequest(BaseModel):
    session_id: str
    question: str


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
        # tool calls show up as tool_calls on AI messages
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_called.append(tc["name"])
        # sum up token usage across every LLM call the agent made
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