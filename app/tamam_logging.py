"""
tamam_logging.py — Tamam's own event/span logs (separate files from
Noor Market's), so evidence for Layla's board never mixes with the
other client's data.
"""

import json
import time
from datetime import datetime

LOG_PATH = "tamam_events.jsonl"
SPAN_LOG_PATH = "tamam_spans.jsonl"


def log_event(session_id, route, question, outcome, llm_calls, cost, latency_seconds, tenant_id=None, request_id=None):
    """outcome: "answered" | "refused_by_gate" | "no_data" | "sql_error" | "escalated" | "off_topic" """
    try:
        record = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id, "session_id": session_id, "tenant_id": tenant_id,
            "route": route, "question": question, "outcome": outcome,
            "llm_calls": llm_calls, "cost": cost, "latency_seconds": latency_seconds
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def log_span(request_id, step, model, input_tokens, output_tokens, cost, latency_seconds):
    try:
        record = {
            "timestamp": datetime.now().isoformat(), "request_id": request_id, "step": step,
            "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost": cost, "latency_seconds": latency_seconds
        }
        with open(SPAN_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


class Timer:
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start