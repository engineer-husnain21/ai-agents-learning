"""
restart_test_part2.py — a COMPLETELY FRESH Python process. Proves the
paused graph from part1 survives a real process restart by resuming it
from here, in a process that has no memory of part1 ever running.
"""

from learn_interrupt import build_graph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
import sqlite3

conn = sqlite3.connect("learn_interrupt.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = build_graph(checkpointer)

thread_id = "restart-test-doc"
config = {"configurable": {"thread_id": thread_id}}

print("=== Fresh process. Checking for a paused run on this thread_id... ===")
state = graph.get_state(config)
print(f"Found state: {state.values}")
print(f"Is it paused (has next steps waiting)? {state.next}")
print()

print("=== Resuming with decision='approve' ===")
final_result = graph.invoke(Command(resume="approve"), config=config)
print(f"Final state: {final_result}")