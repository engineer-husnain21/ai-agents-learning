"""
tamam_contradiction_detector.py — same two-layer design as the Noor
Market version (task 13), pointed at Tamam's own vectorstore/registry.
Checks a new document against the existing VERIFIED corpus.
"""

import json
from app.rewriting_lc import chat_model
from app.tamam_vectorstore import get_vectorstore
from app.tamam_document_registry import list_documents

FLAGS_PATH = "tamam_contradiction_flags.jsonl"
SIMILARITY_CANDIDATE_THRESHOLD = 0.15


def _llm_judge(text_a, text_b):
    prompt = f"""Do these two passages contradict each other on a specific factual rule or policy?
Answer with exactly one line:
"YES: <claim from A> vs <claim from B>" if they contradict,
or "NO" if they do not.

Passage A: {text_a}

Passage B: {text_b}

Answer:"""
    response = chat_model.invoke(prompt)
    return response.content.strip()


def check_new_document_for_contradictions(new_chunks, new_doc_id):
    all_docs = list_documents()
    verified_doc_ids = {d["doc_id"] for d in all_docs if d["status"] == "verified"}
    if not verified_doc_ids:
        return []

    vectorstore = get_vectorstore()
    flags = []

    for new_chunk in new_chunks:
        results = vectorstore.similarity_search_with_relevance_scores(new_chunk["text"], k=5)
        for doc, relevance_score in results:
            existing_doc_id = doc.metadata.get("doc_id")
            if existing_doc_id not in verified_doc_ids:
                continue
            if relevance_score < SIMILARITY_CANDIDATE_THRESHOLD:
                continue

            verdict = _llm_judge(new_chunk["text"], doc.page_content)
            if verdict.upper().startswith("YES"):
                flags.append({
                    "new_doc_id": new_doc_id, "new_chunk_id": new_chunk["chunk_id"],
                    "existing_doc_id": existing_doc_id, "existing_chunk_id": doc.metadata.get("chunk_id"),
                    "similarity_score": round(relevance_score, 4), "verdict": verdict
                })

    if flags:
        try:
            with open(FLAGS_PATH, "a", encoding="utf-8") as f:
                for flag in flags:
                    f.write(json.dumps(flag) + "\n")
        except Exception:
            pass

    return flags