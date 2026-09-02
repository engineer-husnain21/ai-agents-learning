"""
vectorstore_lc.py — Chroma vector store with AzureOpenAIEmbeddings.
Replaces our hand-built embeddings.json + cosine similarity loop (task 3).
We still get scores back, because our threshold gate needs them — the
framework only retrieves; our code still decides if it's good enough.
"""

import os
from dotenv import load_dotenv
load_dotenv()
import shutil
from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_DIR = "chroma_db"

embeddings_model = AzureOpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)


def build_vectorstore(chunks):
    """
    Builds a fresh vector store from the given chunks. Instead of deleting
    the old Chroma directory (which can fail on Windows if a file handle
    is still held), we use a new, unique collection name each time — old
    collections are simply abandoned and never queried again.
    """
    import uuid
    collection_name = f"collection_{uuid.uuid4().hex[:8]}"

    docs = [
        Document(
            page_content=c["text"],
            metadata={"chunk_id": c["chunk_id"], "start_position": c["start_position"]}
        )
        for c in chunks
    ]

    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings_model,
        persist_directory=CHROMA_DIR,
        collection_name=collection_name
    )
    return vectorstore

def get_top_chunks_lc(vectorstore, question, top_n=3):
    """
    Same shape as our hand-built get_top_chunks(): returns a list of
    {chunk_id, score, text, start_position}, sorted best-first.

    Chroma returns DISTANCE (lower = more similar), not cosine similarity
    (higher = more similar) like our hand-built version — we convert so
    our threshold gate (built around "higher score = better") still works
    unchanged.
    """
    results = vectorstore.similarity_search_with_relevance_scores(question, k=top_n)

    top_chunks = []
    for doc, relevance_score in results:
        top_chunks.append({
            "chunk_id": doc.metadata["chunk_id"],
            "score": relevance_score,
            "text": doc.page_content,
            "start_position": doc.metadata["start_position"]
        })

    return top_chunks