"""
contradiction_detector.py — Task 13, addition #4 from review.

Two layers, per review guidance:
  Layer 1 (code): keyword overlap finds CANDIDATE pairs — chunks that are
  about the same topic. This only proves relatedness, not disagreement
  (two agreeing passages about the same topic overlap heavily too).
  Layer 2 (one LLM call per candidate): asks "do these contradict?
  yes/no, quote the claims." This is a detector, not a decider.
A human still makes the final call — flags are surfaced, never
auto-resolved.
"""

import re
import json
from app.rewriting_lc import chat_model
from app.vectorstore_lc import get_vectorstore
from app.document_registry import list_documents

FLAGS_PATH = "contradiction_flags.jsonl"
OVERLAP_THRESHOLD = 0.25  # loose on purpose — this only picks candidates


def _keyword_overlap(text_a, text_b):
    words_a = set(re.findall(r"[a-zA-Z']+", text_a.lower()))
    words_b = set(re.findall(r"[a-zA-Z']+", text_b.lower()))
    if not words_a or not words_b:
        return 0
    return len(words_a & words_b) / len(words_a | words_b)


def _llm_judge(text_a, text_b):
    """One LLM call per candidate pair — a detector, not the decider."""
    prompt = f"""Do these two passages contradict each other on a specific factual claim?
Answer with exactly one line:
"YES: <claim from A> vs <claim from B>" if they contradict,
or "NO" if they do not.

Passage A: {text_a}

Passage B: {text_b}

Answer:"""
    response = chat_model.invoke(prompt)
    return response.content.strip()


def check_new_document_for_contradictions(new_chunks, new_doc_id):
    """
    Compares a newly uploaded document's chunks against the EXISTING
    VERIFIED corpus only (per plan — pending/rejected/demoted docs
    aren't the trusted baseline to check against).
    Returns the list of flagged contradictions (also appended to
    contradiction_flags.jsonl for the reviewer to see).
    """
    all_docs = list_documents()
    verified_doc_ids = {d["doc_id"] for d in all_docs if d["status"] == "verified"}
    if not verified_doc_ids:
        return []

    vectorstore = get_vectorstore()
    flags = []

    for new_chunk in new_chunks:
        results = vectorstore.similarity_search_with_relevance_scores(new_chunk["text"], k=5)
        for doc, _score in results:
            existing_doc_id = doc.metadata.get("doc_id")
            if existing_doc_id not in verified_doc_ids:
                continue

            overlap = _keyword_overlap(new_chunk["text"], doc.page_content)
            if overlap < OVERLAP_THRESHOLD:
                continue

            verdict = _llm_judge(new_chunk["text"], doc.page_content)
            if verdict.upper().startswith("YES"):
                flags.append({
                    "new_doc_id": new_doc_id,
                    "new_chunk_id": new_chunk["chunk_id"],
                    "existing_doc_id": existing_doc_id,
                    "existing_chunk_id": doc.metadata.get("chunk_id"),
                    "verdict": verdict
                })

    if flags:
        try:
            with open(FLAGS_PATH, "a", encoding="utf-8") as f:
                for flag in flags:
                    f.write(json.dumps(flag) + "\n")
        except Exception:
            pass

    return flags