# Tamam Living — Tenant Assistant

A hybrid AI assistant answering tenant questions from two sources: a SQL database (accounts, payments, tickets) and approved policy documents (handbook + building addendums).

## How it works

Every question is classified into one of four routes:
- **DATA** — the tenant's own account info, answered by generating SQL against a tenant-scoped database.
- **POLICY** — building rules, answered from approved documents with citations.
- **LEGAL_ESCALATION** — never answered by the AI; always routed to a human.
- **OFF_TOPIC** — politely declined.

## The tenant-isolation guarantee (most important)

For every request, a fresh in-memory database is built containing ONLY that tenant's own rows. Another tenant's data is never present, so it cannot leak — regardless of what SQL the model generates. Proven by test: asking as one tenant for another's rent by name returns nothing, because that data isn't there.

## Document verification (handbook vs addendum conflict)

Manager uploads a document → it stays PENDING until the Operations Director approves it. Tenants only ever see APPROVED documents. On upload, the system auto-flags conflicts against the approved corpus (the Marina Heights draft flagged 4 conflicts with the handbook automatically). Before approval, tenants get the general handbook rule; after approval, building-specific tenants get the stricter addendum rule — both states tested.

## Two safety patterns worth noting

- **No false comparisons:** the model can only see one tenant's data, so it's explicitly prevented from claiming cross-tenant comparisons ("you pay the highest rent") it has no visibility to support.
- **Zero vs. missing data:** a legitimate zero (e.g. "no late payments" — good news) is distinguished from "no data exists," so tenants get honest answers.

## Evidence

Full eval harness (`tamam_eval.py`, 13 test cases): **100% answer accuracy, 100% refusal accuracy, 100% route accuracy** — covering all four routes, isolation attempts, ambiguous data/policy/legal cases.

**Cost:** ~$0.0015 per question. At the client's stated 400–600 questions/month: **$0.58–$0.87/month** in AI costs.

## Deliberately not built (with reasons in RESPONSE_TO_LAYLA.md)
- "Never say I don't know" — rejected; it's what caused the previous vendor's confident-wrong-answer failure.
- Reading tenants' WhatsApp group — rejected; a privacy/cross-tenant violation.
- Automated payment chasing + WhatsApp — deferred; sensitive, needs its own reviewed project.