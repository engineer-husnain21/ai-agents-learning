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


## Module 3
1. This module covers human-in-the-loop control: streaming, breakpoints (pausing a graph before/after a specific node), editing state manually while paused, dynamic breakpoints (`NodeInterrupt` — pausing based on a runtime condition instead of a fixed node), and time travel (replaying or forking execution from an earlier checkpoint).
2. I had already built pieces of this, but as one-way, automatic decisions rather than a real pause-and-resume loop:
- My threshold gate in answer.py (task 4) is the closest thing I had to a static breakpoint — it checks a condition before letting execution reach the chat model call and can stop it. The difference: my gate's "stop" is a permanent refusal, not a pause. LangGraph's breakpoint actually halts the graph, waits, and can resume from that exact point later — mine never resumes, it just ends.
- My session persistence in main.py (task 5) — SQLite state that survives a server restart — is a hand-built version of what LangGraph's checkpointer does automatically. The difference: I only save conversation history (question/answer pairs); the checkpointer saves the entire graph state after every node, which is what makes breakpoints and time travel possible in the first place. My persistence lets a session continue; theirs lets you rewind and re-run from any past step.
- The grey-zone option I chose in task 9 (borderline scores get "I found something possibly related but I'm not confident" instead of a hard pass/fail) is the same instinct as Editing State and Human Feedback — pause and surface the uncertain state instead of forcing a decision. The difference: my version still answers automatically and never gets real human input back into the pipeline; the framework's `interrupt()` genuinely stops the graph, waits for a human response, and feeds that response back into state before continuing.
- What's genuinely new to me: real pause-and-resume (not just refuse-or-continue), and time travel — being able to jump back to any earlier checkpoint and re-run from there with a different input. Nothing I built has that; once my pipeline finishes a request, it's done, there's no history to rewind into.


## Module 4
1. This module covers building a more complex assistant: parallelization (fanning out work to run at the same time instead of one step after another), sub-graphs (encapsulating a chunk of logic behind a clean interface so it can be built, tested, and swapped independently), map-reduce (applying the same operation across a list of items, then combining the results), and a "research assistant" that puts all three together — plans sub-questions, runs them in parallel, and synthesizes one final answer.

2. I had pieces of this pattern already, mostly as sequential code where the framework would parallelize it, plus one strong structural match:
- **Map-reduce, already built:** My chunk scoring in task 2 (word overlap) and task 3 (cosine similarity) is exactly map-reduce — score EVERY chunk against the question (the map step), then take the top 3 (the reduce step). I just wrote it as a for-loop instead of a fan-out. Task 9's instability test (ask the same question N times, then report min/max/spread) is the same shape again — map over N runs, reduce to a summary. Task 10's stats.py (reading every logged request and reporting outcome percentages, retry rate, average cost/latency) is a reduce over the whole event log.
- **Parallelization, mostly new:** none of my map steps actually ran concurrently — task 2/3's chunk scoring and task 8's "three runs each" for both endpoints were all sequential loops. The operations were parallelizable (each chunk/run is independent), I just never exploited that. This is the real new piece from this module — using `Send()` to fan work out and let the graph run it concurrently instead of looping.
- **Sub-graphs, already built and confirmed by the senior's own instructions:** task 5's refactor (config.py, chunking.py, retrieval.py, answering.py, memory.py, main.py — each concern isolated, one place per responsibility) is the same idea as a sub-graph: a self-contained unit with its own logic, callable from the outer flow without the outer flow caring about its internals. Task 6 makes this exact principle explicit — I rebuilt the internals piece by piece (chunker, vector store, rewrite, answer) while the rule was "from the outside, NOTHING changes: same endpoints, same request/response shapes, same behaviour." That's the sub-graph contract by definition: internals change, the outer interface holds.
- **Research assistant, mostly new:** task 7's agent (decides which tool to call, in what order) is the closest thing I built, but it's a single agent calling tools one at a time, not multiple parallel sub-researchers whose outputs get merged into one synthesized report. Task 8's harness (run against two endpoints, multiple runs, produce one comparison scorecard) has the same gather-then-synthesize shape, but it's me running things and combining results by hand, not the graph doing the fan-out and merge itself. The actual multi-agent parallel research + synthesis pattern is new material.

