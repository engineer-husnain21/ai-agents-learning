"""
vectorstore_lc.py — Chroma vector store with AzureOpenAIEmbeddings.
Replaces our hand-built embeddings.json + cosine similarity loop (task 3).
We still get scores back, because our threshold gate needs them — the
framework only retrieves; our code still decides if it's good enough.
"""

import os
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
    Wipes any old vector store and builds a fresh one from the given chunks.
    This is what /upload calls — same "nothing of the old book survives"
    rule as task 5.
    """
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

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
        persist_directory=CHROMA_DIR
    )
    return vectorstore


def load_vectorstore():
    return Chroma(
        embedding_function=embeddings_model,
        persist_directory=CHROMA_DIR
    )


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