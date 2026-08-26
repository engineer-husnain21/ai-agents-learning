"""
agent_tools.py — the two tools given to the agent.

IMPORTANT: the threshold gate lives INSIDE search_book now, not outside
it like in our pipeline. Why: in the pipeline, OUR code calls retrieval
and then WE check the score before deciding to answer. But an agent tool
can be called by the model at any time, for any reason — the model is
the one "calling" retrieval now, not us. We can't trust the model to
remember to check a score before using weak results, so the tool itself
must refuse to hand back low-confidence chunks. The gate has to move to
wherever the untrusted caller is.
"""

from langchain_core.tools import tool
from app.vectorstore_lc import get_top_chunks_lc
from app.config import LC_SIMILARITY_THRESHOLD

# set by main_agent.py before each request, so the tools can see the
# current book's vectorstore and metadata without global imports everywhere
_current_state = {
    "vectorstore": None,
    "book_name": None,
    "total_characters": None,
    "chunk_count": None,
}


def set_agent_state(vectorstore, book_name, total_characters, chunk_count):
    _current_state["vectorstore"] = vectorstore
    _current_state["book_name"] = book_name
    _current_state["total_characters"] = total_characters
    _current_state["chunk_count"] = chunk_count


@tool
def search_book(question: str) -> str:
    """Search the uploaded book for chunks relevant to a question about its content.
    Use this whenever the user asks something about what's IN the book."""
    vectorstore = _current_state["vectorstore"]
    if vectorstore is None:
        return "No document has been uploaded yet."

    top_chunks = get_top_chunks_lc(vectorstore, question)

    if not top_chunks or top_chunks[0]["score"] < LC_SIMILARITY_THRESHOLD:
        return "nothing relevant found in the document"

    context = "\n\n".join(
        f"[Chunk {c['chunk_id']}]: {c['text']}" for c in top_chunks
    )
    return context


@tool
def book_stats() -> str:
    """Return deterministic stats about the currently uploaded book:
    total characters, number of chunks, and the book's filename.
    Use this for questions about the book's size or structure, not its content."""
    if _current_state["book_name"] is None:
        return "No document has been uploaded yet."

    return (
        f"Book: {_current_state['book_name']}, "
        f"Total characters: {_current_state['total_characters']}, "
        f"Chunk count: {_current_state['chunk_count']}"
    )