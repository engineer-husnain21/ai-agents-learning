"""
search_semantic.py — search chunks using embeddings + cosine similarity
Usage: python search_semantic.py embeddings.json chunks.json "who is the main character"
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


def main():
    parser = argparse.ArgumentParser(description="Search chunks using embeddings.")
    parser.add_argument("embeddings_file", help="path to embeddings.json")
    parser.add_argument("chunks_file", help="path to chunks.json")
    parser.add_argument("question", help="the question to search for, in quotes")
    args = parser.parse_args()

    with open(args.embeddings_file, "r", encoding="utf-8") as f:
        embeddings = json.load(f)

    with open(args.chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # map chunk_id -> text, so we can print it later
    chunk_text_by_id = {c["chunk_id"]: c["text"] for c in chunks}

    # embed the question (1 API call)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=args.question
    )
    question_vector = response.data[0].embedding

    # score every chunk
    scored_chunks = []
    for item in embeddings:
        score = cosine_similarity(question_vector, item["embedding"])
        scored_chunks.append({
            "chunk_id": item["chunk_id"],
            "score": score,
            "text": chunk_text_by_id[item["chunk_id"]]
        })

    scored_chunks.sort(key=lambda c: c["score"], reverse=True)

    print(f"Question: {args.question}")
    print()
    top_3 = scored_chunks[:3]
    for rank, chunk in enumerate(top_3, start=1):
        print(f"--- Rank {rank} | chunk_id: {chunk['chunk_id']} | score: {chunk['score']:.4f} ---")
        print(chunk["text"][:200])
        print()


if __name__ == "__main__":
    main()