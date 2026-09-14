"""
restart_test_part1.py — starts the graph, lets it pause at interrupt(),
then the Python process EXITS COMPLETELY. Run part 2 separately
afterward (a totally fresh process) to prove the pause survived.
"""

from learn_interrupt import build_graph
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

conn = sqlite3.connect("learn_interrupt.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = build_graph(checkpointer)

thread_id = "restart-test-doc"
config = {"configurable": {"thread_id": thread_id}}

print("=== Starting graph, will pause at human_review ===")
result = graph.invoke({"document_name": "restart_test.txt", "decision": ""}, config=config)
print(f"Paused. State: {result}")
print()
print("Process exiting now. Run restart_test_part2.py separately (fresh process) to resume.")