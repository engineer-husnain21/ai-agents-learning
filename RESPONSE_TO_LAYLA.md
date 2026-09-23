# Response to Layla — Tamam Living Tenant Assistant

Hi Layla,

Thanks for the detailed brief and the discovery call notes — they made it much easier to build something that fits how Tamam actually works, rather than a generic chatbot. Here's what I've built, what I've deliberately left out, and why.

## What it does

Your tenants can ask it about their own tenancy — their rent, their lease dates, their maintenance tickets, whether a payment was late — and about your building policies, in plain language, day or night. It answers from two sources: your live tenant database for anything about their account, and your approved handbook (plus any approved building addendums) for anything about policy.

It handles the four kinds of questions differently on purpose:
- **Account questions** ("what's my rent?") — answered from your database, showing only that tenant's own data.
- **Policy questions** ("can I have a pet?") — answered from your approved documents, and it tells the tenant which document the answer came from.
- **Legal questions** ("can I break my lease?") — it never answers these. It tells the tenant a person will follow up, and flags it for your team. You mentioned you've been burned on this before; this is the safeguard.
- **Anything else** (weather, small talk) — politely declined.

## The thing you said would end this for you

You were very clear that a tenant seeing another tenant's information is unacceptable. I treated that as the single most important requirement.

Rather than relying on the AI to "remember" to only show the right tenant's data — which is a promise, not a guarantee — the system is built so that when a tenant asks a question, it can only ever access their own records. Another tenant's data isn't hidden or filtered; it's simply not present in what the assistant can see for that request. I tested this directly by asking, as one tenant, for another tenant's rent by name — the system had no way to answer, because that person's data wasn't there to find. This isn't "we're fairly sure it's safe"; it's built so the leak can't happen.

## The handbook conflict you didn't know how to solve

You mentioned managers want to add their own building rules, but you can't have a tenant told something that isn't real policy — and the Marina Heights draft is a good example, since it disagrees with the main handbook in a few places.

Here's how it works now: a manager can upload their building's document, but it does **nothing** until someone on your side approves it. Until then, tenants only ever see the approved handbook. The moment a document is uploaded, the system automatically points out exactly where it disagrees with existing approved policy — for the Marina Heights draft, it flagged four conflicts (the notice period, the pet rule, and two others) without being told to look for anything specific. Your approver sees those conflicts and decides. Once approved, tenants in that building correctly get the building-specific rule, and tenants elsewhere keep getting the general one. I tested both states — before approval the tenant got the general pet rule, after approval they correctly got Marina Heights' stricter one.

## What I did NOT build, and why

Three things you asked about, I'd recommend against — and I'd rather tell you now than have them cause the exact problems you hired this to avoid:

**"I don't want it saying I don't know."** I understand the frustration, but this is precisely what went wrong with your last vendor — it sounded confident and told a tenant something false. A system that never says "I don't know" doesn't know more; it just hides when it's guessing. I've built it to be honest about its limits instead, because a confident wrong answer about a pet policy or a payment is worse for you than an honest "let me get a person for that."

**Reading the tenants' WhatsApp group.** This directly conflicts with your most important requirement — it would mean the system reading tenants' private conversations with each other, which is exactly the kind of cross-tenant exposure you said would end this. I'd strongly advise against it. If you want to know what tenants actually ask, the system already logs every question it receives — that gives you the same insight, from data you're allowed to use.

**Automatically chasing late payers and replying on WhatsApp.** Chasing payments is a sensitive, sometimes legally-touchy action, and having an AI do it automatically is a real risk — a wrong message to the wrong tenant about money is not something to automate on day one. The system can already tell a tenant their own payment status when they ask. Actively pursuing people, and the WhatsApp integration itself, I'd treat as a separate, later project with its own careful review — not part of this build.

## Cost and reliability

I tested the system against a set of realistic questions covering all four types, including deliberate attempts to break the tenant-isolation rule and ambiguous questions that could be misrouted. It answered correctly, refused correctly where it should, and routed every question to the right place — with the full evidence in the project's documentation, not just a number I'm asking you to trust.

On cost: at the 400–600 questions a month you mentioned, it runs well under a dollar a month in AI costs. The expensive part of the current setup is a person's time to approve documents — which is by design, because that's the human judgment that keeps a tenant from being told the wrong policy.

Happy to walk you or the board through any of this.

Best,
Hussnain