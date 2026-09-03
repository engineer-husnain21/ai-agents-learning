\# LangGraph Course Notes



**## Module 0:**



**1.** This module is course setup — installing dependencies, configuring the Python environment, and setting up API keys (Azure OpenAI) and LangSmith/Jupyter. No new LangGraph concepts introduced.

**2.** Nothing to compare here — this is pure infrastructure setup, not something I'd previously built by hand.





**## Module 1**

**1.** This module covers the various and most important topics of Python AI Langgraph course like simple graphs, chains, routers, agents, and agent memory - Now I can  understand the actual flow of AI in real world Projects by using these concepts.



**2.** I had already built most of these by hand in my RAG pipeline (tasks 1-5):



* My chunk -> retrieve -> gate -> answer flow (tasks 1-4) IS a graph — a fixed sequence of steps, same as what LangGraph calls a simple graph or chain.
* My threshold gate in answer.py (task 4) is a conditional edge — it decides whether to continue to the chat model or stop and refuse, based on the similarity score. LangGraph gives this a name and a visual branch instead of a plain if/else.
* My SQLite session memory in main.py (task 5) is what LangGraph calls agent memory / state persistence — conversation history that survives a restart, keyed by session\_id.
* What I didn't have: a real "agent" that decides its own next step (tool calls in a loop). My pipeline is a fixed path — retrieve always happens, then gate, then answer, in that order. An agent would decide dynamically what to do next based on the model's own output. That part is genuinely new to me.

