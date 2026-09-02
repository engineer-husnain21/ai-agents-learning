"""
logging_lc.py — structured event logging for every /ask request.
Writes one JSON line per request to events.jsonl.

RULE: logging must NEVER break a request. log_event() is wrapped in a
try/except that swallows any logging failure silently — the user always
gets their answer even if the disk is full, the file is locked, etc.
"""

import json
import time
from datetime import datetime

LOG_PATH = "events.jsonl"


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
    request_id=None
):
    """
    outcome: "answered" | "refused_by_gate" | "refused_by_model"
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
            "latency_seconds": latency_seconds
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


SPAN_LOG_PATH = "spans.jsonl"


def log_span(request_id, step, model, input_tokens, output_tokens, cost, latency_seconds):
    """
    One child record per LLM call. step: "rewrite" | "answer" | "retry_answer"
    Same never-breaks-a-request rule as log_event().
    """
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