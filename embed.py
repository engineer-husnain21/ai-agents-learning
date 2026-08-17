"""
embed.py — turn chunks into embedding vectors using Azure OpenAI
Usage: python embed.py chunks.json
"""

import argparse
import json
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()  # reads .env file into environment variables

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

PRICE_PER_1M_TOKENS = 0.02


def main():
    parser = argparse.ArgumentParser(description="Embed chunks using Azure OpenAI.")
    parser.add_argument("chunks_file", help="path to chunks.json")
    args = parser.parse_args()

    with open(args.chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = []
    total_tokens = 0

    for chunk in chunks:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk["text"]
        )
        vector = response.data[0].embedding
        total_tokens += response.usage.total_tokens

        embeddings.append({
            "chunk_id": chunk["chunk_id"],
            "embedding": vector
        })

    with open("embeddings.json", "w", encoding="utf-8") as f:
        json.dump(embeddings, f)

    cost = (total_tokens / 1_000_000) * PRICE_PER_1M_TOKENS

    print(f"Embedded {len(embeddings)} chunks")
    print(f"Total tokens used: {total_tokens}")
    print(f"Total cost: ${cost:.6f}")


if __name__ == "__main__":
    main()