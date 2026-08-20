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