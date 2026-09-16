Task 15 Plan — "A Second Kind of Source"
1. What I'll build

Add a second source (a SQL database) alongside the existing document pipeline. One /ask endpoint, unchanged from the outside. Behind it: a router classifies each question as data / policy / off-topic, routes accordingly, and answers - refusing honestly when neither source has it.

Database choice: SQLite. My whole system already runs on SQLite (memory.db, documents.db, verification_graph.db) - same tooling, same connection pattern, no new server setup to learn. SQL Server is more enterprise-realistic, but introducing a new server, driver, and connection-string layer would add complexity unrelated to this task's actual point (routing and SQL safety). Honest trade-off: real companies more often run MySQL/Postgres/SQL Server in production - SQLite doesn't handle concurrent writes well at scale. This choice optimizes for "what I already know and what fits my existing architecture," not for production-realism, and I'm stating that plainly rather than pretending otherwise.

Router design: workflow, not agent. Per my own task 7 measurements: workflows win when every possible outcome is enumerable; agents earn their flexibility when the task is genuinely open-ended. Here there are exactly three outcomes - data, policy, off-topic - fully enumerable. So the router is one small, dedicated LLM call that classifies the question into one of those three, inside a controlled workflow - not an agent choosing between tools.

SQL generation pipeline: send the question plus the table schema to the model, get back a SQL query, and before running it, my own code (not the model) verifies it starts with SELECT and contains none of INSERT/UPDATE/DELETE/DROP/ALTER. The SQLite connection itself is also opened in read-only mode (mode=ro URI) as a second, independent layer of protection. The actual query that ran is always shown to the user alongside the answer.

Bounded repair: if a generated query fails to execute, retry up to 2 times, feeding the error back to the model to fix. Two, not more - task 9 taught me repairs should be rare and cheap; a genuine syntax slip gets one or two honest chances, beyond that it's a systemic problem worth surfacing, not hiding behind more retries.

No data vs. off-topic - two distinct outcomes: if a question correctly routes to SQL and the query runs successfully but returns nothing (e.g. "how were sales in 2025?" - a real question about data that doesn't exist), the answer says so explicitly: no data for this. If a question doesn't belong to either source (e.g. weather), it's refused as out of scope. Different messages, so the user can tell "your data just isn't here" from "this system can't help with this at all."

2. Order I'll build it in
Set up the SQLite database from the seed file, verify the schema and sample rows.
Upload the handbook through the existing document pipeline as a verified document (nothing new here).
Build the router (the classification step).
Build SQL generation + the two-layer safety check (code validation + read-only connection).
Build bounded repair (max 2 retries).
Wire memory and the rewrite step across both routes, so a follow-up like "who manages that branch?" after a data question works.
Extend stats.py with route as a new dimension.
Extend eval_set.json with data-question and follow-up test cases.
Document cost per question type, worst case included.
3. What I'll test
A data question gets a correct answer with the actual query shown.
A policy question still goes through the existing document pipeline, citations and all.
An off-topic question is refused as out of scope.
"How were sales in 2025?" (real data question, no data exists) vs. a weather question (off-topic) produce two distinctly different refusal messages.
The follow-up "who manages that branch?" after a data question about a specific branch correctly resolves via memory, even though it's now a policy-route question referring back to a data-route answer.
A destructive query attempt (e.g. "delete all sales") is confirmed - not just asserted - to never execute, at both the code-validation layer and the read-only connection layer.
A query that fails on first attempt is corrected by the repair loop within the 2-retry ceiling.
4. Where I expect it to be hard
Router accuracy on genuinely ambiguous questions (e.g. anything mentioning a "branch" could plausibly be either a data or policy question).
Keeping memory coherent across a route switch - a data-route answer followed by a policy-route follow-up question referring back to it.
5. One decision I'm not sure about

Should the router be a fully separate LLM call, or folded into the existing rewrite step to save a call? I'm leaning toward keeping it separate - clarity and testability (I can grade routing accuracy on its own) outweigh the cost of one extra small call per question, but I want to defend this rather than just assume it.

6. Review additions (approved with 3 additions, folded in)

**Addition 1 — "no data" vs. "measured zero":** an aggregate query (`SUM`, `COUNT`, `AVG`) on a time range with no matching rows still returns exactly one row, containing NULL or 0 — not zero rows. My original "did any rows come back" check would misreport this as "sales were zero," a false factual claim, instead of "no data exists for this period." Decision: before running any aggregate query, I will also run a companion existence check — `SELECT COUNT(*) FROM sales WHERE <same filter>` — separately from the aggregate itself. If that count is 0, the answer is "no data exists for this period," never a number. If the count is >0 but the aggregate is NULL (e.g. a column genuinely has no value), that's a different, rarer case I'll also refuse rather than guess. Only when the existence check confirms rows > 0 does the aggregate's actual value get reported.

**Addition 2 — router stays separate, real reason is contamination:** the stronger reason (per review) isn't just clarity/testability — it's that a single call doing both rewriting and routing can invent words to make a question fit its own routing decision, and since rewrite runs first, everything downstream trusts whatever it invented. Keeping them separate means the rewrite step's only job is resolving references, and the router's only job is classifying — neither can quietly influence the other. In the cost table, the router's extra LLM call is documented as the price of traceability (a separately gradable, auditable step), not as overhead.

**Addition 3 — rewrite context needs answers, not just questions, reconciled with task 5.5:** task 5.5 decided the ORIGINAL user question (not the rewrite) is what gets saved to history — that stands, unchanged. What changes: the context I feed INTO the rewrite step will now include both the question and its answer for recent turns, not questions alone — because "who manages that branch?" can only resolve if the rewrite step can see that the previous answer named "Marina." This doesn't change what's stored (still the original question), only what's read back out when building the next rewrite's context.

**Bonus — route accuracy as a measured harness number:** rather than just noting "router may struggle with ambiguous questions" as a prediction, I will add deliberately ambiguous test cases (e.g. questions mentioning "branch" that could plausibly be data or policy) to the eval set, and report route accuracy as its own tracked metric — turning a guess into a number I can watch move between changes.

---
*Plan approved 15 September 2026, three additions folded in same day. Two-day build window.*