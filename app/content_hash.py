"""
content_hash.py — computes a stable hash of a document's text content.
Used to detect when a verified document's content has changed on disk
(read-time check, per plan decision — files can be edited out-of-band).
"""

import hashlib


def compute_content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()