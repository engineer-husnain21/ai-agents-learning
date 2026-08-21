"""
rewriting.py — turns a follow-up question into a standalone question
using conversation history, BEFORE anything else touches it (embedding,
gate, retrieval).
"""

from app.config import client


def rewrite_question(question, history):
    """
    If there's no history, there's nothing to resolve — return unchanged,
    with zero extra cost. Otherwise, ask gpt-5-mini to resolve references
    (she, that, it) using the history, without answering or adding new
    information.
    Returns (rewritten_question, input_tokens, output_tokens).
    """
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

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    rewritten = response.choices[0].message.content.strip()
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    return rewritten, input_tokens, output_tokens