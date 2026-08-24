"""
answering_lc.py — grounded answer using a LangChain PromptTemplate with
the SAME rules as app/answering.py (task 4), and AzureChatOpenAI instead
of a raw openai client call.
"""

from langchain_core.prompts import PromptTemplate
from app.rewriting_lc import chat_model  # reuse the same chat model instance

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


def generate_answer_lc(question, top_chunks, history=None):
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

    response = chat_model.invoke(prompt)

    answer_text = response.content
    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    from app.config import CHAT_INPUT_PRICE_PER_1M, CHAT_OUTPUT_PRICE_PER_1M
    chat_cost = (input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    chat_cost += (output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    return answer_text, chat_cost