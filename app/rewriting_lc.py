"""
rewriting_lc.py — same rewrite prompt as app/rewriting.py (task 5.5),
using LangChain's AzureChatOpenAI. Now logs each call as a span (task 11).
"""

import os
import time
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from app.logging_lc import log_span

load_dotenv()

chat_model = AzureChatOpenAI(
    model="gpt-5-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)


def rewrite_question_lc(question, history, request_id=None):
    if not history:
        return question, 0, 0

    history_lines = []
    for turn in history:
        history_lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
    history_text = "\n\n".join(history_lines)

    prompt = f"""You rewrite a follow-up question into a standalone question, using the conversation history below.

Rules:
- ONLY resolve references (she, that, it, the same one, etc.) using the history.
- Never answer the question.
- Never add information that isn't already in the conversation.
- If the question is already standalone (no unresolved references), return it EXACTLY unchanged.

Conversation history:
{history_text}

Follow-up question: {question}

Standalone question:"""

    start = time.time()
    response = chat_model.invoke(prompt)
    elapsed = time.time() - start

    rewritten = response.content.strip()
    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    from app.config import CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M
    cost = (input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    cost += (output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    log_span(
        request_id=request_id, step="rewrite", model="gpt-5-mini",
        input_tokens=input_tokens, output_tokens=output_tokens,
        cost=round(cost, 6), latency_seconds=round(elapsed, 3)
    )

    return rewritten, input_tokens, output_tokens