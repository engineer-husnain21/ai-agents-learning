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