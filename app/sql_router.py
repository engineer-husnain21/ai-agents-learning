"""
sql_router.py — Task 15: classifies each question into exactly one of
three fully-enumerable outcomes. A dedicated call, kept separate from
the rewrite step per review addition #2 — a single call doing both
rewriting AND routing can invent words to make a question fit its own
routing decision, and since rewrite runs first, everything downstream
would trust whatever it invented. This is a workflow decision (per
task 7's own measurements: workflows win when every outcome is
enumerable), not an agent choosing between tools.
"""

from app.rewriting_lc import chat_model

ROUTE_PROMPT = """Classify this question into EXACTLY one category: DATA, POLICY, or OFF_TOPIC.

DATA = questions about sales, revenue, quantities sold, stores, products, prices, numbers - anything answerable from a sales database (stores, products, sales tables).
POLICY = questions answerable from an uploaded document - company policies, branch managers, opening hours, returns, delivery, loyalty program, OR any other topic covered in a verified document (e.g. a story, a handbook, any reference text that has been uploaded).
OFF_TOPIC = anything not answerable from either the sales database or any uploaded document (weather, general knowledge with no document backing, unrelated small talk).

{context_block}Question: {question}

Answer with exactly one word: DATA, POLICY, or OFF_TOPIC"""


def classify_route(question, context=""):
    """
    context: recent conversation (question+answer pairs), so a follow-up
    like "who manages that branch?" can be classified correctly even
    though "that branch" only makes sense given a prior answer.
    Returns (route, input_tokens, output_tokens).
    """
    context_block = f"Recent conversation:\n{context}\n\n" if context else ""
    prompt = ROUTE_PROMPT.format(context_block=context_block, question=question)

    response = chat_model.invoke(prompt)
    route = response.content.strip().upper()

    if route not in ("DATA", "POLICY", "OFF_TOPIC"):
        route = "OFF_TOPIC"  # safe default if the model returns something unexpected

    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    return route, input_tokens, output_tokens