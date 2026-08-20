"""
retrieval.py — embedding + cosine similarity + top-chunk retrieval.
This is the ONE place cosine similarity lives now (it used to be duplicated
in search_semantic.py and answer.py).
"""

import math
from app.config import client, EMBED_PRICE_PER_1M, SIMILARITY_THRESHOLD


def cosine_similarity(vec_a, vec_b):
    """
    similarity = (A . B) / (|A| * |B|)
    Written by hand, no numpy.
    """
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    length_a = math.sqrt(sum(a * a for a in vec_a))
    length_b = math.sqrt(sum(b * b for b in vec_b))
    if length_a == 0 or length_b == 0:
        return 0
    return dot_product / (length_a * length_b)


def embed_text(text):
    """Embeds one piece of text, returns (vector, tokens_used)."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding, response.usage.total_tokens


def get_top_chunks(question, embeddings, chunks, top_n=3):
    """
    embeddings: list of {chunk_id, embedding}
    chunks: list of {chunk_id, text, start_position}
    Returns (top_chunks, embed_tokens, embed_cost)
    """
    chunk_by_id = {c["chunk_id"]: c for c in chunks}

    question_vector, embed_tokens = embed_text(question)

    scored = []
    for item in embeddings:
        score = cosine_similarity(question_vector, item["embedding"])
        chunk = chunk_by_id[item["chunk_id"]]
        scored.append({
            "chunk_id": item["chunk_id"],
            "score": score,
            "text": chunk["text"],
            "start_position": chunk["start_position"]
        })

    scored.sort(key=lambda c: c["score"], reverse=True)
    embed_cost = (embed_tokens / 1_000_000) * EMBED_PRICE_PER_1M

    return scored[:top_n], embed_tokens, embed_cost


def passes_gate(top_chunks):
    """Returns True if the best score clears the similarity threshold."""
    if not top_chunks:
        return False
    return top_chunks[0]["score"] >= SIMILARITY_THRESHOLD