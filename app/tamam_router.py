"""
tamam_router.py — classifies tenant questions into 4 categories.
LEGAL_ESCALATION exists because the client was explicit: "some
questions we should not be answering at all... has to go to a human —
we've been burned on that before." This is a hard rule, not a
preference — the router's job here is to catch it before anything
tries to answer it.
"""

from app.rewriting_lc import chat_model

ROUTE_PROMPT = """Classify this tenant's question into EXACTLY one category: DATA, POLICY, LEGAL_ESCALATION, or OFF_TOPIC.

DATA = questions about the tenant's own rent, payments, lease dates, maintenance tickets, unit details - anything answerable from the tenant database.
POLICY = questions about building rules, procedures, amenities, contact info, general "how does X work" - anything answerable from the handbook or an approved building addendum.
LEGAL_ESCALATION = anything asking whether something is LEGAL, asking to break/terminate a lease early, disputing a charge as unlawful, asking about eviction, or any question where the tenant is really asking "what are my legal rights/options" rather than "what is the policy." When in doubt between POLICY and LEGAL_ESCALATION, choose LEGAL_ESCALATION - the cost of over-escalating a policy question to a human is small; the cost of a bot answering a legal question is not.
OFF_TOPIC = anything unrelated to this tenant's building, unit, lease, or Tamam Living's policies.

{context_block}Question: {question}

Answer with exactly one word: DATA, POLICY, LEGAL_ESCALATION, or OFF_TOPIC"""


def classify_route(question, context=""):
    context_block = f"Recent conversation:\n{context}\n\n" if context else ""
    prompt = ROUTE_PROMPT.format(context_block=context_block, question=question)

    response = chat_model.invoke(prompt)
    route = response.content.strip().upper()

    if route not in ("DATA", "POLICY", "LEGAL_ESCALATION", "OFF_TOPIC"):
        route = "LEGAL_ESCALATION"  # safe default: escalate, never guess

    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]

    return route, input_tokens, output_tokens