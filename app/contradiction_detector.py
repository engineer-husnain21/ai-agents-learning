"""
contradiction_detector.py — Task 13, addition #4 from review, corrected
Day 2 per review point 3.

Two layers, per review guidance:
  Layer 1 (code): the vector store's own semantic similarity search finds
  CANDIDATE pairs — chunks about the same topic. This is the SAME fix as
  task 3 (embeddings replacing word-matching, because word overlap missed
  paraphrases like "doctor" vs "physician"). The original version of this
  file used keyword overlap for candidates and had that exact weakness —
  fixed here by reusing the embeddings we already have.
  Layer 2 (one LLM call per candidate): asks "do these contradict?
  yes/no, quote the claims." This is a detector, not a decider.
A human still makes the final call — flags are surfaced, never
auto-resolved.
"""

import json
from app.rewriting_lc import chat_model
from app.vectorstore_lc import get_vectorstore
from app.document_registry import list_documents

FLAGS_PATH = "contradiction_flags.jsonl"
SIMILARITY_CANDIDATE_THRESHOLD = 0.15  # semantic similarity, not keyword overlap


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
    Compares a newly uploaded (or updated) document's chunks against the
    EXISTING VERIFIED corpus only. Returns the list of flagged
    contradictions (also appended to contradiction_flags.jsonl for the
    reviewer to see).
    """
    all_docs = list_documents()
    verified_doc_ids = {d["doc_id"] for d in all_docs if d["status"] == "verified"}
    if not verified_doc_ids:
        return []

    vectorstore = get_vectorstore()
    flags = []

    for new_chunk in new_chunks:
        # Layer 1: semantic similarity finds candidates — catches
        # paraphrases that keyword overlap would miss (task 2 -> 3 fix,
        # reapplied here).
        results = vectorstore.similarity_search_with_relevance_scores(new_chunk["text"], k=5)
        for doc, relevance_score in results:
            existing_doc_id = doc.metadata.get("doc_id")
            if existing_doc_id not in verified_doc_ids:
                continue
            if relevance_score < SIMILARITY_CANDIDATE_THRESHOLD:
                continue

            # Layer 2: LLM judges whether this candidate is an actual
            # contradiction, not just an agreeing passage on the same topic.
            verdict = _llm_judge(new_chunk["text"], doc.page_content)
            if verdict.upper().startswith("YES"):
                flags.append({
                    "new_doc_id": new_doc_id,
                    "new_chunk_id": new_chunk["chunk_id"],
                    "existing_doc_id": existing_doc_id,
                    "existing_chunk_id": doc.metadata.get("chunk_id"),
                    "similarity_score": round(relevance_score, 4),
                    "verdict": verdict
                })

    if flags:
        try:
            with open(FLAGS_PATH, "a", encoding="utf-8") as f:
                for flag in flags:
                    f.write(json.dumps(flag) + "\n")
        except Exception:
            pass  # flagging must never break the upload itself

    return flags