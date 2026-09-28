# Tamam Living Assistant - Cost Evidence (for the Finance Director)

Source: `evidence\tamam_eval_summary_20260923_202725.json` - 26 real questions answered by the live system (1 run(s)). Costs are measured from the actual AI usage of each question, not estimated.

## Headline

- Average cost per question: **$0.0016** (US dollars, AI usage only).
- At the stated volume of 400-600 questions/month: **$0.65 - $0.97 per month**.
- Even if every question were the most expensive kind (DATA), 600 questions would cost **$1.45 per month**.
- Most expensive single question seen in testing: $0.00361.

## Cost per question, by type

| Type of question | Questions measured | Average cost | Per 1,000 questions |
|---|---|---|---|
| Own account data (rent, payments, lease, tickets) | 14 | $0.00242 | $2.42 |
| Building rules (handbook / addendum) | 6 | $0.00128 | $1.28 |
| Legal questions (handed to a human) | 5 | $0.00009 | $0.09 |
| Unrelated questions (politely declined) | 1 | $0.00009 | $0.09 |

Why they differ: a legal or off-topic question costs almost nothing because the assistant only has to recognise it and stop. A question about the tenant's own account costs the most because the assistant looks up their records and then writes the answer.

## Monthly projection

| Scenario | 400 / month | 500 / month | 600 / month |
|---|---|---|---|
| Same mix as the test set | $0.65 | $0.81 | $0.97 |
| Worst case: every question is DATA | $0.97 | $1.21 | $1.45 |
| Worst case x 3 safety margin (longer questions, retries) | $2.90 | $3.63 | $4.35 |

The real mix of questions is not known yet, so the worst-case rows assume every question is the most expensive kind. Even the most pessimistic figure above is $4.35 per month.

## What is included and what is not

- Included: every AI call made for a question (understanding the question, choosing the route, looking up data, writing the answer), priced at the rates in `app/config.py`: $0.25 per million input tokens and $2.00 per million output tokens (gpt-5-mini on Azure OpenAI).
- Not included, and negligible: the search step for building-rule questions ($0.02 per million tokens - a fraction of a cent per thousand questions).
- Not included: one-off cost of adding or updating a policy document (a few cents each time), and hosting/server costs, which depend on Tamam's IT setup rather than on question volume.
- If Azure changes its prices, update `app/config.py` and re-run `python tamam_report.py` - every figure here is recalculated from the stored measurements.
