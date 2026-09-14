"""
learn_interrupt.py — a THROWAWAY graph, just to learn how interrupt()
and Command(resume=...) actually behave, before wiring anything real
to it. Per the plan (build order step 1).

Run this file directly: python learn_interrupt.py
"""

from langgraph.graph import StateGraph, END, START
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from typing_extensions import TypedDict
import sqlite3


class State(TypedDict):
    document_name: str
    decision: str


def screening_step(state: State):
    print(f"[screening] checking '{state['document_name']}'... looks clean.")
    return state


def human_review_step(state: State):
    print(f"[human_review] PAUSING here — waiting for a human decision...")
    # interrupt() saves the current state to the checkpointer and stops.
    # Whatever we pass in here is shown to whoever resumes it.
    decision = interrupt({"question": f"Approve '{state['document_name']}'? (approve/reject)"})
    print(f"[human_review] RESUMED — got decision: {decision}")
    return {"decision": decision}


def finalize_step(state: State):
    print(f"[finalize] document '{state['document_name']}' is now: {state['decision']}")
    return state


def build_graph(checkpointer):
    builder = StateGraph(State)
    builder.add_node("screening", screening_step)
    builder.add_node("human_review", human_review_step)
    builder.add_node("finalize", finalize_step)

    builder.add_edge(START, "screening")
    builder.add_edge("screening", "human_review")
    builder.add_edge("human_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    conn = sqlite3.connect("learn_interrupt.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    graph = build_graph(checkpointer)

    thread_id = "test-doc-1"
    config = {"configurable": {"thread_id": thread_id}}

    print("=== FIRST RUN (will pause at human_review) ===")
    result = graph.invoke({"document_name": "test.txt", "decision": ""}, config=config)
    print(f"Graph state after first run: {result}")
    print()
    print("=== Graph is now PAUSED. Its state is saved in learn_interrupt.db ===")
    print("=== Simulating a 'restart' — nothing more happens until we resume ===")
    print()

    input("Press Enter to simulate the human decision arriving (resume)...")

    print("=== RESUMING with decision='approve' ===")
    final_result = graph.invoke(Command(resume="approve"), config=config)
    print(f"Final graph state: {final_result}")