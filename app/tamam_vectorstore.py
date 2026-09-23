"""
tamam_vectorstore.py — Tamam's own Chroma collection, separate from
Noor Market's, so document corpora never mix between clients.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

load_dotenv()

CHROMA_DIR = "tamam_chroma_db"
COLLECTION_NAME = "tamam_corpus"

embeddings_model = AzureOpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)


def get_vectorstore():
    return Chroma(
        embedding_function=embeddings_model,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )


def add_document_chunks(chunks, doc_id):
    vectorstore = get_vectorstore()
    docs = [
        Document(
            page_content=c["text"],
            metadata={"chunk_id": c["chunk_id"], "start_position": c["start_position"], "doc_id": doc_id}
        )
        for c in chunks
    ]
    vectorstore.add_documents(docs)
    return vectorstore


def delete_document_chunks(doc_id):
    vectorstore = get_vectorstore()
    vectorstore._collection.delete(where={"doc_id": doc_id})


def get_top_chunks_lc(vectorstore, question, top_n=3, allowed_doc_ids=None):
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