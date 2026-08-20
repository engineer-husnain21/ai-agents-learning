"""
answering.py — builds the grounded prompt and calls the chat model.
Now also folds in recent conversation history, so follow-up questions work.
"""

from app.config import client, CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M


def build_prompt(question, top_chunks, history=None):
    """
    history: list of {"question": ..., "answer": ...} from past turns, oldest first.
    """
    context = "\n\n".join(
        f"[Chunk {c['chunk_id']}]: {c['text']}" for c in top_chunks
    )

    history_text = ""
    if history:
        history_lines = []
        for turn in history:
            history_lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
        history_text = "\n\nPrevious conversation:\n" + "\n\n".join(history_lines)

    prompt = f"""You must answer ONLY using the context chunks below.
Rules:
- Answer only from the provided chunks.
- If the chunks do not contain the answer, say exactly: "The document does not contain an answer to this question."
- Never use outside knowledge, even if you know the real answer.
- Use the previous conversation only to understand what the current question refers to (e.g. "she", "it"), not as a source of facts.
{history_text}

Context chunks:
{context}

Question: {question}

Answer:"""
    return prompt


def generate_answer(question, top_chunks, history=None):
    """Returns (answer_text, chat_cost)."""
    prompt = build_prompt(question, top_chunks, history)

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    answer_text = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    chat_cost = (input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    chat_cost += (output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    return answer_text, chat_cost