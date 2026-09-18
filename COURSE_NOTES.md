**# LangGraph Course Notes**



**## Module 0**

1\. This module is course setup — installing dependencies, configuring the Python environment, and setting up API keys (Azure OpenAI) and LangSmith/Jupyter. No new LangGraph concepts introduced.

2\. Nothing to compare here — this is pure infrastructure setup, not something I'd previously built by hand.



**## Module 1**

1\. This module covers the core LangGraph building blocks: simple graphs, chains, routers, agents, and agent memory — how to wire nodes and edges instead of writing plain sequential Python.



2\. I had already built most of these by hand in my RAG pipeline (tasks 1-5):

- My chunk -> retrieve -> gate -> answer flow (tasks 1-4) IS a graph — a fixed sequence of steps, same as what LangGraph calls a "simple graph" or "chain".

- My threshold gate in answer.py (task 4) is a conditional edge — it decides whether to continue to the chat model or stop and refuse, based on the similarity score. LangGraph gives this a name and a visual branch instead of a plain if/else.

- My SQLite session memory in main.py (task 5) is what LangGraph calls agent memory / state persistence — conversation history that survives a restart, keyed by session\_id.

- What I didn't have: a real "agent" that decides its own next step (tool calls in a loop). My pipeline is a fixed path — retrieve always happens, then gate, then answer, in that order. An agent would decide dynamically what to do next based on the model's own output. That part is genuinely new to me.



**## Module 2**

1\. This module covers state and memory management: custom state schemas (beyond just messages), trimming/filtering message history, and summarizing older messages so the conversation doesn't grow unbounded.



2\. I had already solved a version of this problem, but differently:

- My SQLite session memory (task 5) persists the full raw conversation history per session\_id and re-sends the last few exchanges to the model on every call. LangGraph's summarization approach is smarter about the same problem: instead of trimming, it folds old messages into a `summary` field in state and keeps sending that instead of raw history, so context never grows unbounded even in a long conversation.

- My query-rewrite step (task 5.5) solves a related but different problem: resolving references before retrieval, not compressing history for cost. The two are complementary.

- What's new to me: the conditional edge deciding "summarize vs continue" by message count (`should\_continue`), and `RemoveMessage` to actually delete old messages from state once summarized.

- Task 6 confirmed this comparison is the right call, not just my guess — the senior's own instruction was to rebuild the RAG service with LangChain but keep my SQLite memory exactly as it is, calling out "knowing when NOT to use a framework part" as its own skill. That's the same lesson Module 2 teaches from the other direction: LangGraph gives you summarization for free when you need it, but a custom store like mine is still the right tool when the job is just "remember what happened," not "keep a bounded context window."



## Task 14 — What LangGraph gave me, what I gave up

**What the framework gave me:**
- A genuine pause: `interrupt()` suspends execution and persists the full state to disk via the checkpointer. My task-13 hand-built version was really "return a status field and wait for another HTTP call" — the process never actually paused; each HTTP call started fresh and I manually reconstructed where things stood by reading the database. Proven with a real test: killed the server mid-review, started a completely separate process, and it correctly found the paused run and resumed it — no re-running of screening or contradiction_check.
- Automatic state persistence — I never wrote a line of code to save "what step are we on" or "what were the intermediate results." The checkpointer did that for every node automatically.
- Time travel for free — `get_state_history()` already returns every checkpoint the graph has ever produced, and replaying from an old one via `invoke(None, config={"checkpoint_id": ...})` forks a new branch without deleting the original. I built no extra history table myself; I just exposed what already existed.

HEAD

## Module 5
1. This module covers long-term memory: the LangGraph Store for memory that persists ACROSS threads/sessions (not just within one conversation), two schema patterns — a single evolving user profile vs. a growing collection of memory items — and wiring an agent to read/write that store as part of its own loop.

2. Comparison to what I'd already built:
   - My SQLite memory (task 5) is session-scoped — it remembers a conversation within one session_id, but nothing carries over to a NEW session for the same user. That's short-term/conversation memory, not what this module means by "long-term memory."
   - I have no hand-built equivalent of a cross-session user profile or a memory collection. My system has never needed to answer "what do I know about this user across all their sessions?" — every session starts fresh except for its own history.
   - The profile-schema vs. collection-schema distinction is new to me too: one evolving object (like a user profile that gets updated) vs. many independent memory items (like a list of facts that grows over time) are different tradeoffs I hadn't had to make, because my memory was always just "the conversation so far."
   - This is genuinely new material — nothing to replace here, just a capability I haven't built.

**What I gave up:**
- Directness. My task-13 code was linear Python I could trace top to bottom. This graph's control flow is split across node functions and edges, and a node re-enters on resume (it runs again from the top, with `interrupt()` returning the resumed value instead of pausing again) — that behavior surprised me the first time I saw it and took explanation to trust.
- A new dependency and a new persistence file to reason about (`verification_graph.db`) on top of the ones I already had (`documents.db`, `memory.db`). More moving pieces, even though each one individually does less work than my hand-built equivalent.


## Module 6
1. This module covers deployment: what a "deployment" means for a LangGraph app, creating one, connecting to it from client code, the concept of "assistants" (configured versions of a graph), and double-texting (handling a new message while a previous run is still in progress).

2. Comparison to what I'd already built:
   - Task 5 (FastAPI service) and task 6 (LangChain rebuild) ARE a deployment — I already turned my pipeline into a running HTTP service with POST /upload, POST /ask, GET /history, serving many requests over a real process instead of a one-off script. That's the same core idea this module teaches, just via FastAPI/uvicorn instead of LangGraph's own deployment tooling.
   - What's new to me: the "assistants" concept (multiple configured versions of the same graph served from one deployment) has no equivalent in my service — I only ever run one fixed pipeline. And double-texting is a real gap in my system: my /ask endpoint has no concept of "a new message arrived while the previous one was still running" — I never handled concurrent requests to the same session_id, and I don't know what my SQLite memory would do if two requests hit it at once for the same session. That's a genuine bug surface Module 6 made me notice.
