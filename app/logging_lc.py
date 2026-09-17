"""
logging_lc.py — structured event logging for every /ask request, plus
per-LLM-call span logging. Writes one JSON line per event/span.

RULE: logging must NEVER break a request. Both log_event() and
log_span() are wrapped in try/except that swallow any logging failure
silently — the user always gets their answer even if the disk is full,
the file is locked, etc.
"""

import json
import time
from datetime import datetime

LOG_PATH = "events.jsonl"
SPAN_LOG_PATH = "spans.jsonl"


def log_event(
    session_id,
    endpoint,
    question,
    was_rewritten,
    gate_score,
    gate_passed,
    outcome,
    retry_fired,
    retry_succeeded,
    llm_calls,
    cost,
    latency_seconds,
    request_id=None,
    cited_documents=None,
    route=None
):
    """
    outcome: "answered" | "refused_by_gate" | "refused_by_model" |
             "refused_off_topic" | "no_data" | "sql_error"
    route: "DATA" | "POLICY" | "OFF_TOPIC" (task 15)
    cited_documents: list of {"doc_id", "trust_level"} actually used.
    Never raises — a logging failure must never break the user's request.
    """
    try:
        record = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "session_id": session_id,
            "endpoint": endpoint,
            "question": question,
            "was_rewritten": was_rewritten,
            "gate_score": gate_score,
            "gate_passed": gate_passed,
            "outcome": outcome,
            "retry_fired": retry_fired,
            "retry_succeeded": retry_succeeded,
            "llm_calls": llm_calls,
            "cost": cost,
            "latency_seconds": latency_seconds,
            "cited_documents": cited_documents or [],
            "route": route
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def log_span(request_id, step, model, input_tokens, output_tokens, cost, latency_seconds):
    """One child record per LLM call. step: "rewrite" | "route" | "answer" |
    "retry_answer" | "sql_generate" | "sql_repair" """
    try:
        record = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "step": step,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "latency_seconds": latency_seconds
        }
        with open(SPAN_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


class Timer:
    """Small helper: with Timer() as t: ... ; t.elapsed"""
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start