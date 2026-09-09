# Task 13 — Who Decides What's Verified? — PLAN (approved, with 4 additions folded in)

## 1. What I'll build

- Extend document registry: `status` (pending / verified / demoted / **rejected**), `approved_by`, `approved_at`, `content_hash`, and a **`rejection_reason`** field for the new rejected state.
- `/upload` defaults every new document to `pending` — never auto-verified.
- `POST /documents/{id}/approve` — human action recording approver name, timestamp, and a hash of the exact content approved.
- **`POST /documents/{id}/reject`** — human action recording who rejected it and **why** (a required reason string). A rejected document stays out of the corpus for answering until someone re-reviews it.
- Contradiction detector at ingestion, built in **two layers** (per review): (1) code-based keyword/claim overlap finds *candidate* pairs between the new document and the existing verified corpus — this only proves relatedness, not disagreement; (2) one LLM call per high-overlap candidate pair asks "do these two passages contradict each other? yes/no, quote the claims" — this is a detector, not a decider. The human reviewer makes the final call on any flagged pair.
- Auto-demotion: content-change detection strategy is decided by **where content can be edited** (see decision below), not by "every use vs periodic" directly.
- **Pending vs demoted stay two distinct states** (confirmed correct instinct): `pending` = "nobody has ever reviewed this." `demoted` = "someone approved it, then the content changed underneath them." A demoted document routes back to its **original approver**, not the general review queue — this preserves accountability history a company needs.
- `stats.py`: document counts per state (pending/verified/demoted/rejected), and **approval latency** (`approved_at - uploaded_at`), as the task originally asked.

## 2. Order of work (revised per review: demotion/state-machine BEFORE the detector)

1. Registry fields (status, approved_by, approved_at, content_hash, rejection_reason) — everything else depends on this.
2. `/upload` defaults to pending.
3. Approval endpoint (`/approve`).
4. **Rejection endpoint (`/reject`)** — new, addition #1.
5. Content-change / demotion logic — get the whole state machine (pending → verified → demoted → back to original approver) solid first, since this is well-defined and testable.
6. Contradiction detector last — this is the riskiest, least well-defined piece (per review), so it's built once the surrounding state machine is proven correct.
7. `eval_set.json` + `stats.py` updates.

## 3. Decision on hash-checking timing (resolved per review's prerequisite question)

The review's point: the "every use vs. periodic" question has a prerequisite — **who can change a document's content, and through what path?**

**What I assumed:** I assumed documents could be edited out-of-band on disk (simulating a real file being changed by someone outside the API), so I planned to check the content hash on READ — re-hashing the document's cached text every time it was used to answer a query.

**What I found:** when I actually tested this by editing a local test file and re-asking a question, nothing happened — the document stayed "verified." The reason: the server never keeps a live path to the uploaded file. `/upload` only ever receives raw bytes over HTTP; there is no ongoing reference to a file on disk that the server can re-open and re-read. Editing my local copy had zero effect on the server, because the server was never watching that file in the first place.

**What changed:** the read-time check was solving a problem that doesn't exist in this architecture. The only way a document's content can actually change, given how this system is built, is through the system's own API. So I built a new `PUT /documents/{id}/content` endpoint — content changes go through this endpoint, and the demotion check happens at WRITE time, right there, not on every read. This matches the review's own logic: "if content only changes through your API, check at write time and you're done — no polling, no per-read cost."

## 3b. Update per review (Day 2, point 2): the write path was incomplete

The first version of `PUT /documents/{id}/content` re-ran injection screening on the new content but NOT the contradiction check. That's wrong — changed content is a new version of the document, and it deserves the same scrutiny a brand-new upload gets. Fixed: content updates now go through the full ingestion pipeline (injection screen + contradiction check against the verified corpus), not half of it.

## 3c. Update per review (Day 2, point 3): the contradiction detector's candidate stage was reusing a mistake I already fixed once

Word-overlap as the candidate filter has the exact weakness word-matching had in task 2 — it misses paraphrases ("doctor" vs "physician" then; two chunks stating the same fact in different wording now). Task 3 fixed this by switching from word matching to embeddings, because embeddings capture meaning, not exact words. The contradiction detector already imports the vector store for its initial retrieval — the fix is to use that retrieval's semantic similarity score as the candidate filter, instead of layering a word-overlap check on top of it that reintroduces the weakness embeddings were supposed to solve.

## 4. What I'll test

- New upload stays pending, cannot answer verified-only questions until approved.
- After approval, it can.
- **Rejecting a document records a reason; a rejected document does not answer questions.**
- A contradicting upload gets flagged: keyword overlap finds the candidate, one LLM call judges "contradiction: yes," and the human sees both quoted claims.
- Manually editing a verified document's content on disk demotes it automatically on next read, with a test proving this — and confirm it routes back to the **original approver**, not a general queue.
- Existing harness (Task 11 injection + Task 12 conflict cases) still passes.
- `stats.py` shows correct per-state counts and a plausible approval latency number.

## 5. Where I expect it to be hard

- The contradiction detector's two-layer design (keyword candidates → LLM judgment → human decision) is the riskiest piece — getting the LLM prompt to reliably say "yes/no, with quotes" in a parseable way, without false positives on merely-related-but-agreeing passages (the Mad Hatter tea party example from the review).
- Correctly wiring "demoted routes back to the original approver" — need to make sure the approver identity survives from the original approval record through to the demotion event.

## 6. Small additions from review

- `stats.py` now includes approval latency (`approved_at - uploaded_at`) per document and averaged.
- Build order changed: demotion/state-machine before the contradiction detector (done above).

---
*Plan approved by senior on 31 August 2026, with the above 4 additions folded in. Two-day build window started when this file and the diagram were pushed on 31 August 2026. Day 2 corrections (this update) made on 8 September 2026.*