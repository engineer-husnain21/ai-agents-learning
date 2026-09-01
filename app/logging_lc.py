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
    latency_seconds
):
    """
    outcome: "answered" | "refused_by_gate" | "refused_by_model"
    Never raises — a logging failure must never break the user's request.
    """
    try:
        record = {
            "timestamp": datetime.now().isoformat(),
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
        # Logging must never break a request. Swallow any failure here —
        # disk full, file locked, permissions, whatever — the user still
        # gets their answer regardless of whether we managed to log it.
        pass


class Timer:
    """Small helper: with Timer() as t: ... ; t.elapsed"""
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start