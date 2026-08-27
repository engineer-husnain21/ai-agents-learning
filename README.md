### What is an AI Agent?



* ### An AI agent is an AI System that not only works on the prompt you given it always perform an action on that particular prompt to complete the user requirement.
* ### It uses LLM as its brain to generate the best result and make decision
* ### It can perform multiple steps instead of giving the answer directly in one step
* ### In simple words, AI Agent can arrange a task, working on it and gave the best outcome
* For example,
A user said to an agent, check the weather tomorrow and if their is any chances of rain then gave me a remainder to grab an umbrella.
Now in this condition Agent start understand my question. check the weather and gave me the feedback of my prompt. This is the actual work of an AI Agent
  ---


## Experiment: Testing Search Relevance

I tested the search script on the book "Alice's Adventures in Wonderland" 
by running 5 different questions and checking whether the Rank 1 (top-scoring) 
chunk actually contained the answer.

### Questions and Observations

**1. "who is the main character"**
Result: No relevant answer found.
The top chunks matched only on common words like "who" and "is" — none of 
them actually talked about who the main character is.

**2. "what happens at the end of the story"**
Result: No relevant answer found.
The top chunk matched the word "end" (from the phrase "fall never come to 
an end"), but this is from the very beginning of the story (Alice falling 
down the rabbit hole), not the actual ending.

**3. "where does alice fall"**
Result: Partially relevant.
Rank 1 and 2 were topic-close (they mentioned "fall/fallen" and "Alice"), 
but they referred to a different scene (something falling into a 
"cucumber-frame") rather than the actual rabbit hole scene. Rank 3 was 
completely unrelated (a conversation with the Mock Turtle).

**4. "who is the mad hatter"**
Result: Partially relevant, but ranked incorrectly.
Rank 1 was completely unrelated — it was just the book's title page, 
which scored high only because of common word overlap. Rank 2 and 3 
were actually relevant (part of the tea-party scene with the Hatter), 
but they were ranked below the irrelevant title page because all three 
chunks had the same score.

**5. "what does the white rabbit say"**
Result: No relevant answer found.
None of the top 3 chunks mentioned the White Rabbit's dialogue. All 
three scored high (score 5) purely due to common word overlap 
("what", "does", "the", "say").

### Summary Table

Question | Relevant Answer Found? 

 1. who is the main character  
 No 

 2.  what happens at the end of the story 
  No 

 3.  where does alice fall
 Partial 

 4.  who is the mad hatter?  
 Partial (wrong ranking) 

 5.  what does the white rabbit say?
 No 

### Conclusion

The search is based purely on raw keyword/word overlap, not on semantic 
meaning. Common words (the, is, who, does) inflate the score, while truly 
relevant chunks — which may use different wording — often rank lower or 
get missed entirely. Even in cases where a relevant chunk was retrieved 
(e.g., the Mad Hatter question), its ranking was incorrect because the 
scoring method only counts word overlap and does not weigh actual 
relevance or meaning.


## Fix: Removing Stop Words

The problem above was clear: common words like "who", "is", "the", "what", "does" 
appear in almost every chunk, so they inflate the score without telling us 
anything about which chunk is actually relevant.

To fix this, I added a list of stop words (common filler words) and removed 
them from both the question and the chunks before scoring — so only 
meaningful words count toward the match.

### Same 5 Questions, After the Fix

**1. "who is the main character"**
Still no relevant answer found. Score dropped since "who" and "is" no longer 
count, but the top chunk still didn't answer the question — the book never 
directly states who the main character is in one chunk.

**2. "what happens at the end of the story"**
No real improvement. The word "end" still matched literally ("the fall would 
never come to an end") instead of meaning "the story's ending".

**3. "where does alice fall"**
Big improvement. All top 3 chunks were now from the actual falling scene in 
the book ("she fell very slowly", "down, down, down"). This is the clearest 
example of the fix working.

**4. "who is the mad hatter"**
Slight improvement — the word "hatter" showed up in one of the top chunks now, 
but the results were still not fully accurate.

**5. "what does the white rabbit say"**
No noticeable improvement. Matches were still weak and unrelated.

### Conclusion

Removing stop words helped in cases where the meaningful word was distinctive 
enough on its own (like "fall"), but it didn't fix everything. The search 
still only matches exact words — it has no idea that two different words can 
mean the same thing. For example, "doctor" and "physician" share zero words, 
so a chunk about a "physician" would never match a question about a "doctor", 
even though they mean the same thing. Word matching also can't understand the 
actual intent behind a question, only whether the same characters appear. 
This is exactly the kind of problem embeddings are designed to solve — they 
represent meaning, not just exact words.




## Task 3 - Semantic Search with Embeddings

I built embed.py, which converts every chunk into a vector using Azure OpenAI's text-embedding-3-small model, and saved them to embeddings.json.

Run summary: 205 chunks embedded, 51,477 tokens used, total cost $0.001030.

Then I built search_semantic.py, which embeds the question and compares it to every chunk using cosine similarity (written by hand, no numpy).

### Same 5 Questions: Word Match (Task 2) vs Embeddings (Task 3)

Q1. who is alice?
Task 2: Top chunk was the title page, matched only on the word "alice".
Task 3: Still the title page ranked highest, but score is now a meaningful similarity (0.4976) instead of a raw word count. No real improvement here since the book never directly "defines" alice in one chunk.

Q2. what happens at the end of the story?
Task 2: Top chunk was from the beginning of the book, matched on the literal word "end".
Task 3: Different chunks entirely (about the Mouse's story), still not the actual ending, but scores are much lower (0.35-0.36) - the model is honestly showing low confidence instead of falsely matching on the word "end".

Q3. where does alice fall?
Task 2: Big improvement already after removing stop words - top chunks were the correct falling scene.
Task 3: Even better - Rank 1 has the highest score I saw across all questions (0.6179), and it's the exact right scene. Embeddings understood "fall" strongly here.

4. who is the mad hatter?
Task 2: Slight improvement, "hatter" appeared in one top chunk.
Task 3: Rank 1 now directly mentions "the Hatter" with a solid score (0.5343) - better than task 2's ranking.

5. what does the white rabbit say?

Task 2: No relevant answer, weak matches.
Task 3: Rank 2 and 3 are actually about the Rabbit (score 0.5272 and 0.5225) - Rank 2 shows Alice hearing the Rabbit coming, Rank 3 shows the Rabbit's voice and Alice responding. This is a real improvement over task 2, though Rank 1 (score 0.5403) is unrelated - it's about the Queen, not the Rabbit.

### Which questions improved and why?

"Where does alice fall" and "who is the mad hatter" improved the most, because embeddings understand meaning, not just exact words - so words like "fall" and "hatter" pulled in chunks that were actually about that topic, ranked with real confidence scores.

### Did any get worse or stay bad?

"Who is the main character" and "what happens at the end of the story" still don't return a good answer. This isn't really a search problem - no single chunk in the book directly states "the main character is Alice" or clearly marks "this is the ending." Embeddings can only find similar meaning if that meaning actually exists in some chunk.

### Why embed all chunks once, but the question every time?

The chunks don't change - the book stays the same, so their embeddings only need to be calculated once and reused for every future question. The question is different every time someone searches, so it has to be embedded fresh each time. If we did it the other way around (re-embedding all 205 chunks on every search instead of just the question), it would cost roughly 205x more per search and be much slower, for no benefit since the chunks never changed.



## Task 4 - Full RAG Loop with Grounded Answers

I built answer.py, which combines everything from tasks 1-3: it retrieves the top 3 chunks using embeddings, checks a similarity threshold before calling any chat model, and if the score passes, sends gpt-5-mini a prompt with the chunks, the question, and strict grounding rules (answer only from the chunks, say so explicitly if the answer isn't there, never use outside knowledge).

### Choosing the threshold

I ran my 5 Alice questions plus 2 unanswerable questions (football scores, weather) and looked at the best similarity score for each:

| Question | Best Score | Should Answer? |
| where does alice fall | 0.6179 | Yes |
| who is the mad hatter | 0.5343 | Yes |
| what does the white rabbit say | 0.5403 | Yes |
| who is alice | 0.4976 | Yes |
| what happens at the end of the story | 0.3579 | No (no chunk answers it) |
| what was the football score yesterday | 0.1623 | No |
| what is the weather today | 0.1570 | No |

There's a clear gap between the real questions (0.49-0.62) and the unanswerable ones (0.16-0.36). I set the threshold at **0.45**, right in the middle of that gap, so it catches the unanswerable questions without blocking real ones.

### Running all 5 Alice questions through answer.py

Q1. where does alice fall? 
- Score 0.6179, passed the gate. 
Answer: "She fell upon a heap of sticks and dry leaves." This is correct and matches the book.

Q2. who is alice? 
- Score 0.4976, passed the gate. 
Answer described Alice correctly based on the retrieved chunks (sitting by her sister, entering the Rabbit's house, etc.) - a real improvement over tasks 2 and 3, since the chat model could combine multiple chunks into one coherent answer.

Q3. who is the mad hatter? 
- Score 0.5343, passed. 
Correct answer about the Hatter and the Cheshire Cat's comment.

Q4. what does the white rabbit say? 
- Score 0.5403, passed. 
The answer quoted a line from the retrieved chunks, but on checking the book, this line is more closely tied to another scene than to the Rabbit specifically - so retrieval pulled a real quote, but not perfectly matched to "the Rabbit says" as the question implied.

Q5. what happens at the end of the story? 
- Score 0.3579, correctly blocked by the gate. No chat model was called, cost was $0.

### Unanswerable questions

Both "what was the football score yesterday" (0.1623) and "what is the weather today" (0.1570) were correctly blocked by the threshold gate before any chat model call was made - cost was $0 for both.

### Honesty test

I asked "what is the name of alice's cat" - a fact that's in the book but not mentioned in every chunk. Score was 0.5579, passed the gate, and the model correctly answered "Dinah" with the right sources. This shows that when retrieval finds the right chunk, even for a less-common fact, the grounded answer is accurate.

### Lying test

I removed the grounding rules and gave the model 3 random, unrelated chunks along with the football question. Instead of making up a fake score, gpt-5-mini honestly said it doesn't have real-time internet access and asked me to clarify which match I meant. It did not hallucinate an answer in this case - but this isn't guaranteed for every question. Without the grounding rule, if I'd asked something the model actually "knows" from its training data, it likely would have answered from that training knowledge instead of admitting the context didn't contain the answer. That's exactly the risk the grounding rule protects against - it forces the model to rely only on the document, not what it might know generally.

### Reflections

1. Why refuse at the threshold BEFORE calling the chat model?

Two reasons: money and trust. Money - calling gpt-5-mini costs tokens even if the answer will be wrong or "I don't know," so blocking early with a free similarity check saves cost on every question that was never going to be answerable anyway. Trust - if we let the model see irrelevant chunks and decide on its own, there's a chance it ignores the rule and answers from its training data anyway, which would look correct but not actually be grounded in the document. Filtering before the call removes that risk entirely for the clearest cases.

2. "Retrieval found nothing" vs "the book doesn't contain it" - same or different?

They're different. "Retrieval found nothing relevant" means the similarity scores were low, so my search failed to find matching text. "The book doesn't contain it" means even a perfect search wouldn't find an answer, because the information genuinely isn't in the document anywhere. I can't fully tell them apart from the score alone - a low score usually means retrieval failed, but it could also mean the answer just isn't there. The only way to really tell the difference is manually checking the book myself, which is what I did for "what happens at the end of the story" - the score was low because no chunk actually describes an ending, not because my search was bad.

3. Which costs more - embeddings or the chat answer?

The chat answer costs far more per question. Embedding the question uses very few tokens and costs close to $0. The chat call costs $0.0005-$0.0016 per question because it has to process the full context (3 chunks of text) as input tokens, plus generate the answer as output tokens, and output tokens are priced 8x higher than input tokens ($2.00 vs $0.25 per 1M). This is exactly why the threshold gate matters - it avoids the more expensive chat call whenever retrieval already shows there's nothing worth answering.


**Second lying test attempt:**
I also tried asking "who was pakistan's first international cricket team captain" (a historical fact, unlike the football score which needs real-time data). This time, without the grounding rules, the model confidently answered "Abdul Hafeez Kardar (A. H. Kardar)" - even though the context chunks were from Alice in Wonderland and had nothing to do with cricket. This proves the exact risk the grounding rule protects against: the model used its own training knowledge instead of admitting the provided context didn't contain the answer. With the grounding rules in place (as in answer.py), this same question would correctly return "The document does not contain an answer to this question."


## Task 5 - RAG as a FastAPI service

The pipeline is now a small HTTP service in the `app/` package. Old terminal scripts (`chunk.py`, `embed.py`, `search.py`, `search_semantic.py`, `answer.py`) are kept so the earlier experiments can still be run the old way. The service does not import them — repeated Azure-client setup and cosine similarity now live in one place (`app/config.py` and `app/retrieval.py`).

### Run it

```
pip install fastapi uvicorn
uvicorn app.main:app --reload
```

- `POST /upload` — multipart `.txt` file. Chunks, embeds, replaces the current book.
- `POST /ask` — JSON `{ "session_id": "...", "question": "..." }`. Retrieve → threshold gate → grounded answer with citations and cost.
- `GET /history/{session_id}` — full conversation for that session.
- If `/ask` is called before any upload (and nothing is on disk from a previous run), it returns an error and does not call the model.

### Memory vs disk (what /upload does)

The live book (chunks + embeddings) sits in RAM in a `state` dict so every `/ask` can search without re-reading files. The same book is also written to `store/chunks.json` and `store/embeddings.json`, so a server restart can reload it without paying to embed the book again. Conversation history is not the RAM copy — SQLite (`memory.db`) is the source of truth, which is why killing the process does not wipe sessions. On `/upload`, RAM is replaced with the new chunks and embeddings first, then the old store files are deleted and rewritten, so nothing of the previous book remains in memory or on disk. History rows in SQLite are left alone because they belong to a `session_id`, not to a particular book.

### History length

I send the last **3** exchanges (`HISTORY_LENGTH = 3`) into the chat prompt, and I also use the last turn to rewrite follow-up questions for retrieval (so "who did she meet after that?" can find the White Rabbit). Three turns is enough for pronouns and "after that" without sending a whole afternoon of chat. Each extra turn is extra input tokens on the chat call; at $0.25 per 1M input tokens, 3 short turns cost a fraction of a cent, while sending unlimited history would make every later question more expensive for no real gain.

### If 100 people used this at once

I would worry most that there is only one book for the whole process. One person's `/upload` replaces the document everyone else is asking about. Upload also embeds chunks one by one on that request, so a large file would stall other users until it finished.

### Demo results (one server process, no restart except where noted)

**1. Upload Alice (`book.txt`), then two questions**

Upload: `{"message":"Uploaded and processed 'book.txt'","chunks_created":210}`

`where does alice fall` → `She fell down a very deep well.` Sources: chunks 4, 5, 8. Cost ~$0.00051.

`who did she meet after that?` → `The White Rabbit.` (only works because history is in the prompt / retrieval query). Cost ~$0.000886.

**2. Unanswerable question**

`what is the weather today` → `The document does not contain an answer to this question.` Sources `[]`, cost `$0.0` (gate refused before the chat model).

**3. Kill the server, restart, same session**

`GET /history/demo_task5` still returned all three turns from SQLite.

Without re-uploading, `what did she fall into?` answered `a very deep well.` — the book reloaded from `store/`, and `she` still resolved from history.

**4. Upload a different book, no restart**

Uploaded `book_b.txt` (a short space-voyage story, 2 chunks) on the same running server.

`where does alice fall` → refused, sources `[]`, cost `$0.0`. No Alice names, quotes, or chunk ids from the old book.

`Who is Captain Mira Solen?` → `She commanded the research ship Red Comet on a five-year survey of the outer planets.` Sources from the new file only (chunks 0 and 1).






## Task 5 - Making it a Service

### Refactor
I moved the repeated code (Azure client setup, cosine similarity) into a shared `app/` package: config.py, chunking.py, retrieval.py, answering.py, memory.py, main.py. I kept the old task 1-4 scripts (chunk.py, search.py, embed.py, search_semantic.py, answer.py, lying_test.py) in the repo as-is, since they document the step-by-step progress and were already reviewed - the new work happens in app/ now.

### Memory vs disk
The current book's chunks and embeddings live in memory (a Python dict in main.py) - this is fast but disappears if the server restarts, and a new /upload completely overwrites it so no old book data survives. Conversation history lives in SQLite (memory.db), a file on disk - this is why history survives a server restart, unlike the book data. Every /ask call also fetches the recent history from disk before answering, then saves the new turn back to disk immediately after.

### History length decision
I send the last 3 exchanges to the model as context. I chose 3 because it's enough for natural follow-ups ("who did she meet after that?") without growing the prompt (and cost) too much on long conversations. More history means more input tokens on every single question, even ones that don't need it.

### One thing I'd worry about with 100 concurrent users
The book state is stored in one shared Python dictionary. If 100 people used this at once, one person's /upload would wipe out the book for everyone else currently using it - there's no per-user or per-session isolation for the uploaded document, only for conversation history. This would need to become per-session state instead of one global state.




## Task 5.5 - Query Rewriting

The blending approach from Task 5 mixed old history text directly into the embedding, so the gate couldn't tell if a high score came from the actual question or from leftover history. I replaced it with proper query rewriting: before anything else touches the question, I call gpt-5-mini with the conversation history and ask it to rewrite the question into a standalone one - resolving pronouns like "she" and "that" - without answering it or adding new information.

I deleted the old blending code and the two-stage raw/combined check from Task 5 entirely - the rewrite step replaces both.

### Follow-up test
Original: "who did she meet after that?"
Rewritten: "Who did Alice meet after she fell down a very deep well and came to rest upon a heap of sticks and dry leaves?"
Gate score: 0.6103 - Answer: "The White Rabbit." Correct, and the rewrite cleanly resolved "she" and "that" using only the prior exchange.

### Weather test (unanswerable)
Original: "what is the weather today"
Rewritten: "what is the weather today" (unchanged - already standalone, no references to resolve)
Gate score: 0.1781 - correctly refused. This confirms the gate now sees a clean question with zero history contamination, unlike the Task 5 bug where old Alice history falsely dragged an unrelated question's score up.

### Pipeline trace
Original question: "who did she meet after that?"
↓ Rewrite (using history: "where does alice fall" → "She falls down a well...")
Rewritten question: "Who did Alice meet after she fell down a very deep well and came to rest upon a heap of sticks and dry leaves?"
↓ Embed the rewritten question
Gate score: 0.6103 (passes)
↓ Retrieve top 3 chunks
↓ Generate answer
Answer: "The White Rabbit."

### Cost: before vs after
Before (Task 5 blending): a single /ask call cost around $0.0008-0.0011 (embedding + chat only).
After (with rewrite): the follow-up question cost $0.001763 - the extra ~$0.0007-0.001 is the one small rewrite call (gpt-5-mini reading the question + history and outputting a rewritten question). A standalone question with no history (like "where does alice fall") costs the same as before ($0.000662), since rewrite_question() returns immediately with zero extra cost when there's no history to resolve.

### What I store in memory
I save the user's ORIGINAL question to history, not the rewrite. The rewrite is an internal retrieval detail - if I saved the rewritten version instead, the conversation history returned by /history would show questions the user never actually typed, which would be confusing and dishonest about what really happened in the conversation.






## Task 6 - Rebuild with LangChain (branch: task-6-langchain)

I rebuilt the /upload, /ask, /history endpoints using LangChain: RecursiveCharacterTextSplitter (chunking), Chroma + AzureOpenAIEmbeddings (vector store), and AzureChatOpenAI (rewrite + answer). The threshold gate and SQLite memory stayed mine - the framework only retrieves, my code still decides if it's good enough to answer from.

### Component comparison

| Component | My lines of code | Framework lines | What the framework hid from me |
|---|---|---|---|
| Chunking | ~25 lines (manual while loop, start/overlap math) | ~5 lines (just call RecursiveCharacterTextSplitter) | Where exactly to cut - it tries paragraph breaks, then sentences, then words, only falling back to raw characters as a last resort |
| Embeddings + similarity | ~50 lines (cosine_similarity written by hand, embed_text, scoring loop) | ~10 lines (Chroma.from_documents + similarity_search_with_relevance_scores) | The entire vector math, storage, and indexing - I never see a single number multiplied |
| Retrieval | included above | included above | How results get sorted/ranked internally |
| Rewrite + answer | ~70 lines (manual prompt strings, raw openai client calls, manual token math for cost) | ~55 lines (same prompt text, but AzureChatOpenAI.invoke() instead of client.chat.completions.create()) | Not much here - the framework mostly just wraps the same API call, the prompt itself is still fully mine |

### One thing the framework does differently

I ran the same book through my chunker (task 1) and the LangChain splitter. My chunker made 210 chunks; LangChain made 209. The real difference is WHERE it cuts: my chunker cuts at exactly `size` characters no matter what, even mid-word - that's literally the task 1 stretch goal I never built (cutting at the nearest space). LangChain's RecursiveCharacterTextSplitter does this automatically - it prefers to break on paragraph breaks first, then sentences, then spaces, and only cuts mid-word as an absolute last resort. So the framework gave me the stretch goal I skipped, for free.

### What did the framework decide for me?

The framework decided WHERE to cut chunks (paragraph/sentence/word boundaries instead of my fixed character count), and it decided how to store and search vectors internally (I never touch the actual similarity math anymore). 

The one I'd want back in a system I'm responsible for: the exact chunk-cutting boundary. Right now I don't know precisely why LangChain chose a specific cut point over another nearby one - with my hand-built version, I could always explain exactly why a chunk started and ended where it did, because I wrote the rule myself. If something goes wrong with a specific answer, I can debug my own chunker's decision instantly; with the framework, I'd have to go read its source code first.

### When would I reach for the framework vs build by hand?

I'd reach for the framework for anything where the "how" is genuinely a solved, boring problem that isn't the point of what I'm building - chunking logic, vector storage/indexing, and API call wrapping are all things thousands of people have already optimized, and reinventing them wastes time without teaching me anything new once I already understand the concept.

I'd build by hand for anything that IS the actual decision-making logic of my system - like the threshold gate and the grounding rules. Those aren't "solved problems" with one right answer; they're judgment calls specific to my use case (what counts as "confident enough," what the refusal message says, what the rewrite prompt is allowed and not allowed to do). If I let a framework make those decisions, I'd lose the ability to explain or defend exactly how my system behaves - which is the whole point of me being responsible for the answers it gives.


## Task 7 - First Agent (branch: task-7-agent)

I built an agent with two tools: `search_book` (wraps retrieval, threshold gate moved INSIDE the tool) and `book_stats` (deterministic, no AI — returns character/chunk count and filename). Exposed as `POST /ask_agent`, alongside the existing `/ask` pipeline, which was left untouched so both could be compared side by side.

### Why the gate moved inside the tool

In the pipeline, my own code calls retrieval and my own code checks the score before deciding to answer — I'm the trusted caller. With an agent, the model decides when to call `search_book`, and I can't trust it to check a similarity score before treating weak results as solid. The gate has to live wherever the untrusted decision-maker is — which is now inside the tool itself.

### Comparison table

| Question | Pipeline result | Agent tools called | Agent LLM calls | Agent cost | Agent correct? |
|---|---|---|---|---|---|
| where does alice fall | Correct (gate 0.62) | search_book | 2 | $0.0013 | Correct |
| who is alice | Correctly refused (gate 0.29) | search_book | 2 | $0.0006 | Correctly refused |
| who is the mad hatter | Correct (gate 0.34) | search_book (x2) | 3 | $0.0024 | Correct |
| what happens at the end of the story | Partially correct (gate 0.42, boosted by history) | search_book | 2 | $0.0004 | Correctly refused |
| what does the white rabbit say | Correct, good quotes | search_book | 2 | $0.0018 | Correct, same quotes |
| hello, how are you? | No small-talk path — always retrieves | none | 1 | $0.0001 | Correct, skipped retrieval |
| how many chunks is the book split into? | No stats capability | book_stats | 2 | $0.0003 | Correct |
| football score yesterday | Correctly refused, $0 chat cost | none | 1 | $0.0008 | Answered from general knowledge, admitted no live data |
| weather today | Correctly refused, $0 chat cost | none | 1 | $0.0008 | Same as above |
| **My prediction question:** "who did she meet after that?" | Correct, via dedicated rewrite step | search_book | 2 | $0.0006 | **Incorrect** — "nothing relevant found" |

### My prediction (written before running it)

The pipeline has a separate rewrite step that turns "who did she meet after that?" into a standalone question before searching. The agent has no such step — it only sees raw history inside its own reasoning. I predicted the agent might still get it right since it can "see" history directly, but if it failed, it would be because it passed the vague, un-rewritten question straight to `search_book`.

**Result:** it failed exactly as predicted — the agent sent something close to the original vague question to `search_book`, got "nothing relevant found," and told the user the answer wasn't there, even though the pipeline found it easily. Without an explicit rewrite step, a tool call doesn't automatically inherit the benefit of conversation context the way a final answer might.

### Reflections

**1. Where the agent did better / worse:** Better — it correctly skipped retrieval for the greeting and the two real-world unanswerable questions instead of forcing them through a fixed refusal path, and it has `book_stats`, which the pipeline lacks entirely. Worse — it failed the one follow-up question that needed history resolved *before* searching, something the pipeline's rewrite step handled correctly.

**2. The greeting:** The pipeline has no shortcut for it — it would run the full rewrite → embed → gate flow and likely get refused, still paying for at least one embedding call. The agent spent one LLM call (~$0.0001) and never touched the vector store, because the model itself recognized no tool was needed.

**3. Did the agent ever skip search_book on a real book question?** No — it always called the tool for genuine content questions. On the follow-up, it called the tool but with a bad query, producing a wrong refusal rather than a hallucination. That's safer than making something up, but still a failure a user can't detect without knowing the real answer. What prevents outright hallucination is the system prompt rule plus the tool itself refusing to return weak matches.

**4. Cost — predictable or not?** The pipeline's cost per question is fixed and known in advance: one embed call, sometimes a rewrite call, sometimes a chat call. The agent's cost varied even across similar questions (1–3 LLM calls, and once it called the same tool twice), so I can only give a range for it, not a fixed number.

**5. The verdict:** I'd ship the pipeline for this document Q&A use case, and save the agent for genuinely open-ended tasks. My evidence: the pipeline's grounding is enforced by code I fully control (gate, rewrite step), making its behavior 100% predictable. The agent's flexibility was real but came with a new failure mode I didn't have before, precisely because I no longer control every step. I'd rather ship a system where I can list everything it will do, and reach for an agent only when the task truly needs the model to choose between different multi-step paths — not just decide "answer directly" vs. "search."





## Task 8 - Automated Eval Harness (branch: task-8-evals)

I built `eval_set.json` (13 test cases: 5 Alice questions, 2 unanswerable, book stats, a follow-up pair, a greeting, a cat-name fact, and one intentionally hard-to-grade question) and `eval.py`, which runs the set against a live endpoint over HTTP, grades each response automatically, and saves a timestamped results file so runs can be compared later.

### Runs

| Run | Endpoint | Answer accuracy | Refusal accuracy | Cost | Time |
|---|---|---|---|---|---|
| 1 | /ask | 66.7% | 100% | $0.0071 | 53.6s |
| 2 | /ask | 66.7% | 100% | $0.0069 | 43.0s |
| 3 | /ask | 77.8% | 100% | $0.0085 | 50.6s |
| 1 | /ask_agent | 88.9% | 50% | $0.0175 | 99.3s |
| 2 | /ask_agent | 88.9% | 50% | $0.0134 | 86.8s |
| 3 | /ask_agent | 88.9% | 50% | $0.0131 | 79.9s |

### Variance observation

`/ask` (the pipeline) showed real question-level variance: the "mad_hatter" question FAILED in run 1 and 2, but PASSED in run 3, with no code changes between runs - the gate score for that question sits close enough to the threshold that small embedding/search fluctuations flip the result. Two other failures (cat_name, book_stats) were identical across all 3 runs - genuine, stable issues, not variance.

`/ask_agent`'s pass/fail pattern was identical across all 3 runs (same 3 failures every time) - but cost and time varied noticeably run to run ($0.0131-$0.0175, 80-99s), because the number of LLM calls the agent makes isn't fixed. So the pipeline has question-level result variance with fairly stable cost, while the agent has stable results but variable cost - the unpredictability shows up in a different place for each system.

### Tuning experiment

I raised `LC_SIMILARITY_THRESHOLD` from 0.30 to 0.40 and re-ran the harness on `/ask`. Answer accuracy dropped from ~67-78% to 22.2% - even "where does alice fall," which had passed in every prior run, started failing because its gate score no longer cleared the higher bar. Refusal accuracy stayed at 100% since the genuinely unanswerable questions were already scoring well below either threshold.

**Decision the numbers support:** keep the threshold at 0.30. Raising it did not meaningfully improve refusal accuracy (already perfect) but severely damaged answer accuracy - a strictly worse trade-off. I reverted the change.

### README reflections

1. Where does keyword grading break?
My "hard_to_grade" question ("is the hatter actually mad, or is that just what people call him?") uses keywords ("mad", "hatter") that will appear in almost any answer, correct or not - a wrong answer that simply repeats the question's own words would still pass. I also saw the reverse problem for real: on `/ask_agent`, the weather and football questions were graded FAIL even though the agent behaved correctly (it politely explained it has no live data) - my refusal grader only looks for the exact phrase "does not contain an answer," which the agent never says. A smarter grader — LLM-as-judge — would read the actual answer and decide if it's correct/appropriately-refused in meaning, not just in wording. The cost: an extra LLM call per graded question, which roughly doubles the harness's own cost and adds its own (smaller) risk of misjudging.

2. Why must every non-follow-up question run in a fresh session?
If two unrelated questions shared a session, the second question's rewrite step and the model's context would include the first question's history — this could wrongly "fix" a vague reference that isn't actually there, or bias retrieval toward the first question's topic. It would make a question artificially easier or harder to answer depending on what happened to run before it, instead of testing the system's real ability to handle that question cold.

3. Which scorecard number would I watch most closely in production?
Refusal accuracy. A wrong refusal on an answerable question is annoying but safe - the user just doesn't get help. A wrong "answer" on a question that should have been refused means the system is confidently making something up, which is the failure mode that actually damages trust. I'd rather over-refuse than ever under-refuse.

4. Tuning experiment summary
I changed the similarity threshold from 0.30 to 0.40. Answer accuracy dropped sharply (to 22.2%) while refusal accuracy stayed the same. Decision: keep 0.30 — the higher threshold only removed correct answers without gaining any real safety benefit.