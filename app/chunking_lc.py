"""
chunking_lc.py — chunking using LangChain's RecursiveCharacterTextSplitter.
Replaces the hand-built loop in app/chunking.py (task 1) with the framework
equivalent, using the same size and overlap chosen in task 1.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text_lc(text, size=1000, overlap=200):
    """
    Same interface as our hand-built chunk_text(): returns a list of
    {chunk_id, text, start_position} dicts.

    RecursiveCharacterTextSplitter tries to split on paragraph breaks,
    then sentences, then words — falling back to raw characters only if
    it has to. Our hand-built version always cut at exactly `size`
    characters, mid-word if needed.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap
    )

    pieces = splitter.split_text(text)

    chunks = []
    search_from = 0
    for chunk_id, piece in enumerate(pieces):
        # find where this piece actually starts in the original text,
        # so start_position stays meaningful (needed for citations)
        start_position = text.find(piece, search_from)
        if start_position == -1:
            start_position = search_from  # fallback, shouldn't normally happen

        chunks.append({
            "chunk_id": chunk_id,
            "text": piece,
            "start_position": start_position
        })
        search_from = start_position + 1  # allow overlap to be found again

    return chunks