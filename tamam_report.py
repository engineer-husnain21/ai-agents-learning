"""
tamam_report.py — turns real harness output into the two Day 3 evidence
documents. Every number in the reports is read from the harness JSON;
nothing is typed by hand.

Usage:
    python tamam_report.py                      # uses the newest evidence/tamam_eval_summary_*.json
    python tamam_report.py evidence/tamam_eval_summary_XXXX.json

Writes:
    evidence/ACCURACY_REPORT.md   (for the board)
    evidence/COST_REPORT.md       (for the finance director)
"""

import glob
import json
import os
import sys
from collections import defaultdict

import ast


def _read_prices(path=os.path.join("app", "config.py")):
    # read the price constants without importing config.py (which creates the Azure client)
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    prices = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.endswith("_PER_1M"):
            prices[node.targets[0].id] = ast.literal_eval(node.value)
    return prices


_PRICES = _read_prices()
CHAT_INPUT_PRICE_PER_1M = _PRICES["CHAT_INPUT_PRICE_PER_1M"]
CHAT_OUTPUT_PRICE_PER_1M = _PRICES["CHAT_OUTPUT_PRICE_PER_1M"]
EMBED_PRICE_PER_1M = _PRICES["EMBED_PRICE_PER_1M"]

EVIDENCE_DIR = "evidence"
BASELINE_PATH = os.path.join(EVIDENCE_DIR, "baseline_before_threshold_fix.json")
ROUTES = ["DATA", "POLICY", "LEGAL_ESCALATION", "OFF_TOPIC"]
ROUTE_NAMES = {
    "DATA": "Own account data (rent, payments, lease, tickets)",
    "POLICY": "Building rules (handbook / addendum)",
    "LEGAL_ESCALATION": "Legal questions (handed to a human)",
    "OFF_TOPIC": "Unrelated questions (politely declined)",
    "NONE": "Either route acceptable (only a data leak fails)",
}
TYPE_MEANING = {
    "answer": "Give the right answer (expected facts present, wrong ones absent)",
    "refuse": "NOT answer - decline or hand to a human",
    "isolation": "Never reveal another tenant's data",
}
VOLUMES = [400, 500, 600]
BUILDING_OF_TENANT = {1: "Marina Heights", 16: "Deira Court"}


def latest_summary():
    files = sorted(glob.glob(os.path.join(EVIDENCE_DIR, "tamam_eval_summary_*.json")))
    if not files:
        sys.exit("No evidence/tamam_eval_summary_*.json found - run: python tamam_eval.py --runs 3")
    return files[-1]


def load_runs(summary):
    runs = []
    for path in summary["run_files"]:
        with open(path, "r", encoding="utf-8") as f:
            runs.append(json.load(f))
    return runs


def money(x, places=4):
    return f"${x:,.{places}f}"


def fmt_pct(x):
    return "n/a" if x is None else f"{x:.1f}%"


# ---------------------------------------------------------------- accuracy

def accuracy_report(summary, runs, summary_path):
    n_runs = summary["runs"]
    cases = runs[0]["results"]
    passes = defaultdict(int)
    route_ok = defaultdict(int)
    failures = defaultdict(list)
    for run in runs:
        for r in run["results"]:
            passes[r["id"]] += int(r["correct"])
            route_ok[r["id"]] += int(bool(r["route_correct"]))
            if not r["correct"]:
                failures[r["id"]].append(r["answer"])

    L = []
    L.append("# Tamam Living Assistant - Accuracy Evidence (for the Board)")
    L.append("")
    L.append(f"Source: `{summary_path}` ({n_runs} full run(s) of `{summary['eval_set']}`, "
             f"{summary['cases'] // n_runs} test questions per run, run {summary['timestamp']}). "
             "Every number below is generated from that file by `tamam_report.py`.")
    L.append("")
    L.append("## Headline")
    L.append("")
    L.append(f"- **Overall: {fmt_pct(summary['overall_accuracy_pct'])}** of "
             f"{summary['cases']} graded answers ({summary['cases'] // n_runs} questions x {n_runs} runs).")
    L.append(f"- **Routing: {fmt_pct(summary['route_accuracy_pct'])}** - how often the question was sent "
             "down the correct path (own data / building rules / legal hand-off / off-topic).")
    if summary.get("isolation_accuracy_pct") is not None or summary.get("refusal_accuracy_pct") is not None:
        L.append(f"- **Correct answers: {fmt_pct(summary['answer_accuracy_pct'])}**, "
                 f"**correct refusals / hand-offs: {fmt_pct(summary['refusal_accuracy_pct'])}**, "
                 f"**privacy (no other tenant's data shown): {fmt_pct(summary['isolation_accuracy_pct'])}**.")
    L.append(f"- Per run overall: {', '.join(fmt_pct(x) for x in summary['per_run_overall_accuracy_pct'])}.")
    if summary["cases_unstable"]:
        L.append(f"- Questions that passed in some runs but not others: {', '.join(summary['cases_unstable'])}.")
    if summary["cases_failed_every_run"]:
        L.append(f"- Questions that failed in every run: {', '.join(summary['cases_failed_every_run'])}.")
    L.append("")
    L.append("This is deliberately **not** a single \"95% accurate\" figure. A single number hides which "
             "kind of question fails. The tables below show accuracy separately for each kind of question, "
             "because a wrong answer about the weather and a wrong answer about another tenant's rent are "
             "not the same risk.")
    L.append("")

    L.append("## Accuracy by route")
    L.append("")
    L.append("| Route | What it covers | Correct | Routed correctly | Avg time |")
    L.append("|---|---|---|---|---|")
    per_route = summary["per_expected_route"]
    for route in ROUTES + ["NONE"]:
        g = per_route.get(route)
        if not g:
            continue
        routed = "not graded" if route == "NONE" else f"{g['route_correct']}/{g['cases']}"
        L.append(f"| {route} | {ROUTE_NAMES[route]} | {g['correct']}/{g['cases']} ({fmt_pct(g['accuracy_pct'])}) "
                 f"| {routed} | {g['avg_time_seconds']}s |")
    L.append("")

    L.append("## What was tested, question by question")
    L.append("")
    L.append(f"Each question was asked {n_runs} time(s), each time in a brand-new conversation.")
    L.append("")
    L.append("| Test | Tenant (building) | Question | The assistant must... | Passed |")
    L.append("|---|---|---|---|---|")
    for r in cases:
        L.append(f"| `{r['id']}` | {r['tenant_id']} ({BUILDING_OF_TENANT.get(r['tenant_id'], '?')}) | {r['question']} | {TYPE_MEANING[r['type']]} "
                 f"| {passes[r['id']]}/{n_runs} |")
    L.append("")
    L.append("Tenant 1 lives in Marina Heights (the building with the approved addendum). "
             "Tenant 16 lives in Deira Court (handbook only). Testing both proves the addendum applies "
             "to its own building and nowhere else.")
    L.append("")

    L.append("## How it was graded")
    L.append("")
    L.append("- The harness (`tamam_eval.py`) sends each question to the running assistant exactly as the "
             "tenant portal would, then checks the reply automatically - no human judgement in the score.")
    L.append("- **Answer** questions pass only if the reply contains the expected facts (for example "
             "\"9,000\" for tenant 1's rent, \"90\" days notice for a Deira Court tenant) **and** contains none "
             "of the forbidden ones (a \"$\" sign on a dirham amount, the Marina Heights rule given to a "
             "Deira tenant).")
    L.append("- **Refusal** questions pass only if the assistant declines or hands the question to a person.")
    L.append("- **Privacy** questions pass only if another tenant's real figures never appear in the reply, "
             "whatever else it says.")
    L.append("- **Routing** is checked separately: the question must go down the intended path, not just "
             "happen to produce a good-looking answer.")
    L.append("")

    L.append("## Why privacy is guaranteed, not just tested")
    L.append("")
    L.append("The privacy tests are a check, not the protection itself. For every question about a tenant's "
             "own account, the system builds a temporary database containing only that tenant's own rows. "
             "Other tenants' records are not hidden from the AI - they are simply not there. The tests above "
             "try to get around that (by name, by unit number, from a different building, and with an "
             "\"ignore your instructions\" message); passing them confirms the design behaves as intended.")
    L.append("")
    iso_path = os.path.join(EVIDENCE_DIR, "isolation_check.json")
    if os.path.exists(iso_path):
        with open(iso_path, "r", encoding="utf-8") as f:
            iso = json.load(f)
        verdict = "no data from any other tenant came back" if iso["passed"] else f"{len(iso['failures'])} LEAK(S) FOUND"
        L.append(f"A second, fully mechanical check (`tamam_isolation_check.py`, no AI involved) built the private "
                 f"database for all {iso['tenants_checked']} tenants and ran {iso['queries_per_tenant']} "
                 f"\"show me everything\" queries against each one: **{verdict}** "
                 f"(`{iso_path}`, {iso['timestamp']}).")
        L.append("")

    if failures:
        L.append("## Failures, shown in full")
        L.append("")
        for case_id, answers in failures.items():
            L.append(f"**`{case_id}`** failed {len(answers)}/{n_runs} run(s). Reply given:")
            L.append("")
            L.append(f"> {answers[0]}")
            L.append("")

    if os.path.exists(BASELINE_PATH):
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            base = json.load(f)
        L.append("## The harness catches real problems")
        L.append("")
        L.append(f"An earlier run (`{BASELINE_PATH}`, {base['timestamp']}) scored "
                 f"{base['answer_accuracy_pct']}% on answer questions and {base['refusal_accuracy_pct']}% on "
                 "refusals. The policy search was too strict for Tamam's short documents, so questions like "
                 "\"how much notice do I need to give\" were wrongly answered with \"I don't have that "
                 "information\". That was found by this harness, fixed, and re-tested - which is exactly "
                 "what it is for.")
        L.append("")

    L.append("## Honest limits of this evidence")
    L.append("")
    L.append(f"- {summary['cases'] // n_runs} questions is a focused test, not a statistical survey. It covers "
             "every route and every known risk, but real tenants will phrase things in ways not listed here.")
    L.append("- Grading checks for key facts and forbidden content; it does not judge tone or wording.")
    L.append("- AI answers vary slightly between runs, which is why the test was repeated "
             f"{n_runs} time(s) and unstable questions are listed above.")
    L.append("- Recommended: review a sample of real tenant conversations each month for the first three "
             "months and add any new failure to this test set.")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- cost

def cost_report(summary, runs, summary_path):
    by_actual = summary["cost_per_actual_route"]
    avg = summary["avg_cost_per_question"]
    route_avgs = {k: v["avg_cost"] for k, v in by_actual.items() if k in ROUTES}
    worst_route = max(route_avgs, key=route_avgs.get) if route_avgs else None
    worst = route_avgs.get(worst_route, avg)

    all_costs = [r["cost"] for run in runs for r in run["results"]]
    max_single = max(all_costs) if all_costs else 0

    L = []
    L.append("# Tamam Living Assistant - Cost Evidence (for the Finance Director)")
    L.append("")
    L.append(f"Source: `{summary_path}` - {summary['cases']} real questions answered by the live system "
             f"({summary['runs']} run(s)). Costs are measured from the actual AI usage of each question, "
             "not estimated.")
    L.append("")
    L.append("## Headline")
    L.append("")
    L.append(f"- Average cost per question: **{money(avg)}** (US dollars, AI usage only).")
    L.append(f"- At the stated volume of 400-600 questions/month: **{money(avg * 400, 2)} - "
             f"{money(avg * 600, 2)} per month**.")
    if worst_route:
        L.append(f"- Even if every question were the most expensive kind ({worst_route}), 600 questions "
                 f"would cost **{money(worst * 600, 2)} per month**.")
    L.append(f"- Most expensive single question seen in testing: {money(max_single, 5)}.")
    L.append("")

    L.append("## Cost per question, by type")
    L.append("")
    L.append("| Type of question | Questions measured | Average cost | Per 1,000 questions |")
    L.append("|---|---|---|---|")
    for route in ROUTES:
        v = by_actual.get(route)
        if v:
            L.append(f"| {ROUTE_NAMES[route]} | {v['questions']} | {money(v['avg_cost'], 5)} "
                     f"| {money(v['avg_cost'] * 1000, 2)} |")
    L.append("")
    L.append("Why they differ: a legal or off-topic question costs almost nothing because the assistant only "
             "has to recognise it and stop. A question about the tenant's own account costs the most because "
             "the assistant looks up their records and then writes the answer.")
    L.append("")

    L.append("## Monthly projection")
    L.append("")
    L.append("| Scenario | 400 / month | 500 / month | 600 / month |")
    L.append("|---|---|---|---|")
    L.append("| Same mix as the test set | " + " | ".join(money(avg * v, 2) for v in VOLUMES) + " |")
    if worst_route:
        L.append(f"| Worst case: every question is {worst_route} | "
                 + " | ".join(money(worst * v, 2) for v in VOLUMES) + " |")
    L.append("| Worst case x 3 safety margin (longer questions, retries) | "
             + " | ".join(money(worst * v * 3, 2) for v in VOLUMES) + " |")
    L.append("")
    L.append("The real mix of questions is not known yet, so the worst-case rows assume every question is the "
             f"most expensive kind. Even the most pessimistic figure above is {money(worst * 600 * 3, 2)} per month.")
    L.append("")

    L.append("## What is included and what is not")
    L.append("")
    L.append(f"- Included: every AI call made for a question (understanding the question, choosing the route, "
             f"looking up data, writing the answer), priced at the rates in `app/config.py`: "
             f"${CHAT_INPUT_PRICE_PER_1M:.2f} per million input tokens and ${CHAT_OUTPUT_PRICE_PER_1M:.2f} per "
             "million output tokens (gpt-5-mini on Azure OpenAI).")
    L.append(f"- Not included, and negligible: the search step for building-rule questions "
             f"(${EMBED_PRICE_PER_1M:.2f} per million tokens - a fraction of a cent per thousand questions).")
    L.append("- Not included: one-off cost of adding or updating a policy document (a few cents each time), "
             "and hosting/server costs, which depend on Tamam's IT setup rather than on question volume.")
    L.append("- If Azure changes its prices, update `app/config.py` and re-run `python tamam_report.py` - "
             "every figure here is recalculated from the stored measurements.")
    L.append("")
    return "\n".join(L)


def fill_layla(summary, path="LAYLA_RESPONSE.md"):
    """Fills the [[...]] placeholders in LAYLA_RESPONSE.md with this run's numbers (only if still unfilled)."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if "[[" not in text:
        print(f"{path}: no placeholders left - not changed")
        return
    avg = summary["avg_cost_per_question"]
    worst = max((v["avg_cost"] for k, v in summary["cost_per_actual_route"].items() if k in ROUTES), default=avg)
    values = {
        "NUMBER OF QUESTIONS": str(summary["cases"] // summary["runs"]),
        "NUMBER OF RUNS": str(summary["runs"]),
        "OVERALL %": fmt_pct(summary["overall_accuracy_pct"]),
        "ROUTING %": fmt_pct(summary["route_accuracy_pct"]),
        "PRIVACY %": fmt_pct(summary["isolation_accuracy_pct"]),
        "REFUSAL %": fmt_pct(summary["refusal_accuracy_pct"]),
        "AVG COST PER QUESTION": f"US${avg:.4f}",
        "MONTHLY 400": f"US${avg * 400:.2f}",
        "MONTHLY 600": f"US${avg * 600:.2f}",
        "WORST CASE 600": f"US${worst * 600:.2f}",
    }
    for key, value in values.items():
        text = text.replace(f"[[{key}]]", value)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    left = text.count("[[")
    print(f"Filled {path} with this run's numbers" + (f" ({left} placeholder(s) still open)" if left else ""))
    if summary.get("isolation_accuracy_pct") != 100.0:
        print("WARNING: privacy tests were not 100% - LAYLA_RESPONSE.md says 'no other tenant's data was shown'. "
              "Fix the failure (or the wording) before sending.")


def main():
    summary_path = sys.argv[1] if len(sys.argv) > 1 else latest_summary()
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    runs = load_runs(summary)
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(os.path.join(EVIDENCE_DIR, "ACCURACY_REPORT.md"), "w", encoding="utf-8") as f:
        f.write(accuracy_report(summary, runs, summary_path))
    with open(os.path.join(EVIDENCE_DIR, "COST_REPORT.md"), "w", encoding="utf-8") as f:
        f.write(cost_report(summary, runs, summary_path))
    print(f"Wrote evidence/ACCURACY_REPORT.md and evidence/COST_REPORT.md from {summary_path}")
    fill_layla(summary)
    print(f"Overall {fmt_pct(summary['overall_accuracy_pct'])}, route {fmt_pct(summary['route_accuracy_pct'])}, "
          f"avg cost ${summary['avg_cost_per_question']:.6f}, "
          f"400-600/month ${summary['avg_cost_per_question'] * 400:.2f}-${summary['avg_cost_per_question'] * 600:.2f}")


if __name__ == "__main__":
    main()
