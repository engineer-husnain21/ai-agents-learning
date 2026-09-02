"""
answering_lc.py — grounded answer using a LangChain PromptTemplate.
Now logs each call as a span (task 11), and accepts a `step` label so
retries can be tagged separately from the first answer attempt.
"""

import time
from langchain_core.prompts import PromptTemplate
from app.rewriting_lc import chat_model
from app.logging_lc import log_span

ANSWER_PROMPT = PromptTemplate.from_template("""You must answer ONLY using the context chunks below.
Rules:
- Answer only from the provided chunks.
- If the chunks do not contain the answer, say exactly: "The document does not contain an answer to this question."
- Never use outside knowledge, even if you know the real answer.
- Use the previous conversation only to understand what the current question refers to (e.g. "she", "it"), not as a source of facts.
{history_text}

Context chunks:
{context}

Question: {question}

Answer:""")


def generate_answer_lc(question, top_chunks, history=None, request_id=None, step="answer"):
    context = "\n\n".join(
        f"[Chunk {c['chunk_id']}]: {c['text']}" for c in top_chunks
    )

    history_text = ""
    if history:
        history_lines = []
        for turn in history:
            history_lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
        history_text = "\n\nPrevious conversation:\n" + "\n\n".join(history_lines)

    prompt = ANSWER_PROMPT.format(
        context=context, question=question, history_text=history_text
    )

    start = time.time()
    response = chat_model.invoke(prompt)
    elapsed = time.time() - start

    answer_text = response.content
    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    from app.config import CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M
    chat_cost = (input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    chat_cost += (output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    log_span(
        request_id=request_id, step=step, model="gpt-5-mini",
        input_tokens=input_tokens, output_tokens=output_tokens,
        cost=round(chat_cost, 6), latency_seconds=round(elapsed, 3)
    )

    return answer_text, chat_cost