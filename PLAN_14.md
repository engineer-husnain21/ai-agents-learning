# Task 14 — The Pause That Waits — PLAN

## 1. What I'll build

Rebuild the task 13 verification lifecycle as a LangGraph graph:
`upload → screening → contradiction_check → interrupt() (waits for human) → approve/reject → verified/rejected`.

Use a **disk-based checkpointer** — the course notebooks' in-memory checkpointer will not survive a server restart, so I'll use `SqliteSaver` (from `langgraph-checkpoint-sqlite`, a new install), writing to a file on disk, consistent with how the rest of this system already persists state (SQLite for memory.db, documents.db).

**State ownership decision (the one the task specifically asked me to make):** the graph becomes the single owner of a document's verification state during a review. The existing task-13 `/approve` and `/reject` endpoints stop writing to the document registry directly — instead, they submit the human's decision into the graph via `Command(resume=...)`, and the graph itself is what updates the registry when it resumes. This avoids two systems (my old endpoint logic and the new graph) both trying to be the source of truth for the same document at the same time.

## 2. Order I'll build it in

1. Build a small standalone LangGraph (just screening -> contradiction_check -> interrupt) first, to learn how interrupt() and Command(resume=...) actually behave before wiring anything real to it.
2. Add the SqliteSaver checkpointer, confirm state genuinely persists to a file on disk (not just in the running process).
3. Connect the existing /upload, /approve, /reject endpoints to this graph so the external API shape doesn't change - same routes, same request/response contract as task 13.
4. Test the restart-survival case specifically, since that's the part a hand-built version cannot do at all.
5. Add the time-travel feature: list a document's checkpoint history, and re-run from a chosen earlier checkpoint.
6. Re-run the full task-13 eval harness against the rebuilt version, before and after.

## 3. What I'll test

- A document's review pauses at the human step and stays paused - not failed, not timed out - for as long as the human takes.
- Kill the server while a review is paused, restart it - the review is still paused at the exact same step.
- Sending the human decision through the API resumes the exact graph run - no re-running of the screening or contradiction_check steps, no lost state.
- List a document's checkpoint history and re-run from an earlier step - specifically: lower the contradiction threshold, then re-run just the contradiction_check step from that checkpoint without re-uploading the document, and show the outcome changes.
- Task 13's existing eval harness (including the injection and conflict cases) still passes against the rebuilt version.

## 4. Where I expect it to be hard

- This is my first time using interrupt() and Command(resume=...) - understanding exactly what LangGraph stores to make a genuine pause-and-resume possible (as opposed to my hand-built "return a status and wait for another HTTP call") will take some hands-on experimentation before I fully trust it.
- Bridging the old REST endpoints to the new graph-based execution model without changing the external contract, while moving actual state ownership entirely into the graph, is the part most likely to need iteration.

## 5. One decision I'm not sure about

When re-running from an earlier checkpoint produces a different outcome than the original run (for example, a contradiction that wasn't flagged before now IS flagged after a threshold change), should the new result overwrite the old one, or should both be kept - so there's a record of "what we thought before vs. what we found after"? I lean toward keeping both, since task 13 taught me that losing that kind of history is exactly the problem an audit trail is supposed to prevent, but I want to defend this with reasoning rather than just picking one.

---
Plan for review - pending approval before any code is written, per the standing rule from task 13.