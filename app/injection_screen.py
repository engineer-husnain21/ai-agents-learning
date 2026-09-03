"""
injection_screen.py — Defense: screen chunks for instruction-shaped
patterns at ingestion time, BEFORE they are embedded and stored.

This is code, not AI — cheap, deterministic, and doesn't depend on the
model "choosing well" (which is not a security control, per review).

We don't try to be clever about detecting every possible injection —
that's an arms race. We flag the small set of clearly instruction-shaped
patterns that have no legitimate reason to appear in narrative document
text, and mark those chunks so they can be handled differently
(e.g. stripped, or flagged in logs for review).
"""

import re

# Patterns that look like an attempt to give the model new instructions.
# Deliberately narrow and literal — false positives are cheap (a flagged
# chunk still gets used, just marked), false negatives are the real risk,
# so this is a first layer, not a complete solution.
INSTRUCTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (all )?(previous|prior|above) instructions",
    r"system (settings|note|message|prompt)[:\s]",
    r"you (are|must) now (act|behave|respond) as",
    r"new instructions?:",
    r"reply only (with)?:?\s*[\"']",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INSTRUCTION_PATTERNS]


def screen_chunk(text):
    """
    Returns (is_flagged, matched_pattern_or_None).
    Does NOT modify the text — screening is a detection layer; what to do
    with a flagged chunk (strip it, log it, block it) is a separate
    decision made by the caller.
    """
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text):
            return True, pattern.pattern
    return False, None


def screen_chunks(chunks):
    """
    chunks: list of {chunk_id, text, start_position}
    Returns the same list, with a "flagged" and "flag_reason" key added
    to each chunk dict. Nothing is removed — flagging is visibility,
    not silent deletion, so a human can see what got caught and why.
    """
    for chunk in chunks:
        is_flagged, reason = screen_chunk(chunk["text"])
        chunk["flagged"] = is_flagged
        chunk["flag_reason"] = reason
    return chunks