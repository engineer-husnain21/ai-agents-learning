"""
chunking.py — splits text into overlapping chunks.
Moved from the original chunk.py (task 1), same logic.
"""


def chunk_text(text, size=1000, overlap=200):
    """
    Splits `text` into overlapping chunks.
    size    = how many characters per chunk
    overlap = how many characters repeat from the end of the previous chunk
    """
    if size - overlap <= 0:
        raise ValueError("overlap must be smaller than size")

    chunks = []
    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + size
        piece = text[start:end]

        chunks.append({
            "chunk_id": chunk_id,
            "text": piece,
            "start_position": start
        })

        chunk_id += 1
        start += (size - overlap)

    return chunks