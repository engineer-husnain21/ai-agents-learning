"""
answer.py — the full RAG loop: retrieve, gate, and answer
Usage: python answer.py embeddings.json chunks.json "where does alice fall"
"""

import argparse
import json
import os
import math
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

# ----- pricing -----
EMBED_PRICE_PER_1M = 0.02
CHAT_INPUT_PRICE_PER_1M = 0.25
CHAT_OUTPUT_PRICE_PER_1M = 2.00

# ----- the line that separates "found something real" from "found nothing" -----
# chosen after looking at scores for 5 real + 2 unanswerable questions (see README)
SIMILARITY_THRESHOLD = 0.45


def cosine_similarity(vec_a, vec_b):
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    length_a = math.sqrt(sum(a * a for a in vec_a))
    length_b = math.sqrt(sum(b * b for b in vec_b))
    if length_a == 0 or length_b == 0:
        return 0
    return dot_product / (length_a * length_b)


def get_top_chunks(question, embeddings, chunks, top_n=3):
    chunk_by_id = {c["chunk_id"]: c for c in chunks}

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )
    question_vector = response.data[0].embedding
    embed_tokens = response.usage.total_tokens

    scored = []
    for item in embeddings:
        score = cosine_similarity(question_vector, item["embedding"])
        scored.append({
            "chunk_id": item["chunk_id"],
            "score": score,
            "text": chunk_by_id[item["chunk_id"]]["text"],
            "start_position": chunk_by_id[item["chunk_id"]]["start_position"]
        })

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_n], embed_tokens


def build_prompt(question, top_chunks):
    context = "\n\n".join(
        f"[Chunk {c['chunk_id']}]: {c['text']}" for c in top_chunks
    )
    prompt = f"""You must answer ONLY using the context chunks below.
Rules:
- Answer only from the provided chunks.
- If the chunks do not contain the answer, say exactly: "The document does not contain an answer to this question."
- Never use outside knowledge, even if you know the real answer.

Context chunks:
{context}

Question: {question}

Answer:"""
    return prompt


def main():
    parser = argparse.ArgumentParser(description="Full RAG: retrieve, gate, answer.")
    parser.add_argument("embeddings_file", help="path to embeddings.json")
    parser.add_argument("chunks_file", help="path to chunks.json")
    parser.add_argument("question", help="the question to ask, in quotes")
    args = parser.parse_args()

    with open(args.embeddings_file, "r", encoding="utf-8") as f:
        embeddings = json.load(f)
    with open(args.chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    top_chunks, embed_tokens = get_top_chunks(args.question, embeddings, chunks)
    best_score = top_chunks[0]["score"]

    embed_cost = (embed_tokens / 1_000_000) * EMBED_PRICE_PER_1M

    print(f"Question: {args.question}")
    print(f"Best similarity score: {best_score:.4f}")
    print()

    # ----- LAYER 1: threshold gate -----
    if best_score < SIMILARITY_THRESHOLD:
        print("The document does not contain an answer to this question.")
        print()
        print(f"Cost: ${embed_cost:.6f} (embedding only, chat model was not called)")
        return

    # ----- LAYERS 2 & 3: grounded chat answer -----
    prompt = build_prompt(args.question, top_chunks)

    chat_response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    answer_text = chat_response.choices[0].message.content
    input_tokens = chat_response.usage.prompt_tokens
    output_tokens = chat_response.usage.completion_tokens

    chat_cost = (input_tokens / 1_000_000) * CHAT_INPUT_PRICE_PER_1M
    chat_cost += (output_tokens / 1_000_000) * CHAT_OUTPUT_PRICE_PER_1M

    total_cost = embed_cost + chat_cost

    print("Answer:")
    print(answer_text)
    print()
    print("Sources:")
    for c in top_chunks:
        print(f"  chunk_id: {c['chunk_id']}, start_position: {c['start_position']}")
    print()
    print(f"Cost: ${total_cost:.6f} (embedding: ${embed_cost:.6f}, chat: ${chat_cost:.6f})")


if __name__ == "__main__":
    main()