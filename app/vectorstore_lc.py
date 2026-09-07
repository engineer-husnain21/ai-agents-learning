"""
vectorstore_lc.py — Chroma vector store, now a CORPUS (task 12): documents
are ADDED, never wipe each other. Every chunk carries a doc_id.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

load_dotenv()

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "corpus"  # one persistent collection, shared by all documents

embeddings_model = AzureOpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)


def get_vectorstore():
    """Returns the one persistent, shared vector store (the corpus)."""
    return Chroma(
        embedding_function=embeddings_model,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )


def add_document_chunks(chunks, doc_id):
    """
    Adds one document's chunks to the shared corpus — does NOT touch any
    other document's chunks. This is the task 12 reversal of task 5's
    "replace everything" rule.
    """
    vectorstore = get_vectorstore()

    docs = [
        Document(
            page_content=c["text"],
            metadata={
                "chunk_id": c["chunk_id"],
                "start_position": c["start_position"],
                "doc_id": doc_id
            }
        )
        for c in chunks
    ]

    vectorstore.add_documents(docs)
    return vectorstore


def delete_document_chunks(doc_id):
    """
    Removes ONLY this document's chunks from the corpus. Proves the task 5
    bug (old state leaking) stays impossible even in add-mode: deleting
    document A must never touch document B's chunks.
    """
    vectorstore = get_vectorstore()
    vectorstore._collection.delete(where={"doc_id": doc_id})


def get_top_chunks_lc(vectorstore, question, top_n=3, allowed_doc_ids=None):
    """
    Same shape as before, but each result now includes doc_id, and results
    can optionally be restricted to a set of allowed_doc_ids (used for
    trust-tier eligibility in task 12 part 3 — code decides eligibility,
    not the model).
    """
    # Chroma's similarity_search_with_relevance_scores doesn't support a
    # "where" filter directly here across LC versions consistently for
    # scored search, so we over-fetch and filter in Python if needed.
    fetch_n = top_n if allowed_doc_ids is None else max(top_n * 4, 12)
    results = vectorstore.similarity_search_with_relevance_scores(question, k=fetch_n)

    top_chunks = []
    for doc, relevance_score in results:
        doc_id = doc.metadata.get("doc_id")
        if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
            continue
        top_chunks.append({
            "chunk_id": doc.metadata["chunk_id"],
            "score": relevance_score,
            "text": doc.page_content,
            "start_position": doc.metadata["start_position"],
            "doc_id": doc_id
        })
        if len(top_chunks) >= top_n:
            break

    return top_chunks