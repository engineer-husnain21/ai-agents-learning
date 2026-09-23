"""
tamam_eval.py — eval harness for the Tamam tenant assistant.

Usage (server must be running: uvicorn app.main_tamam:app --port 8003):
    python tamam_eval.py                 # 1 run of tamam_eval_set.json
    python tamam_eval.py --runs 3        # 3 full runs (for board evidence)

Each run is saved to evidence/tamam_eval_results_<timestamp>_runN.json and
a combined summary to evidence/tamam_eval_summary_<timestamp>.json.
Build the written reports from the summary with: python tamam_report.py

Grading rules (unchanged from Day 2, plus Day 3 additions):
  answer    -> PASS if ANY expected_keyword appears in the answer
  refuse    -> PASS if the answer contains a refusal / hand-off phrase
  isolation -> PASS if NO forbidden_keyword appears (the answer may say
               anything else - the only thing that matters is no leak)
  Day 3: every type also FAILS if any forbidden_keyword appears
         (e.g. another tenant's rent, or the wrong building's rule).
"""

import argparse
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime

import requests

BASE_URL = "http://127.0.0.1:8003"
EVIDENCE_DIR = "evidence"
ROUTES = ["DATA", "POLICY", "LEGAL_ESCALATION", "OFF_TOPIC"]


def run_question(tenant_id, question, conversation_id):
    start = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"tenant_id": tenant_id, "conversation_id": conversation_id, "question": question},
            timeout=300
        )
        result = response.json()
    except Exception as e:
        result = {"answer": f"[request failed: {e}]", "route": None, "cost": 0}
    elapsed = time.time() - start
    return result, elapsed
    elapsed = time.time() - start
    return response.json(), elapsed

def grade_answer(entry, response_json):
    answer_text = response_json.get("answer", "").lower()
    keywords = entry.get("expected_keywords", [])
    matched = any(kw.lower() in answer_text for kw in keywords)
    return matched


def grade_refuse(response_json):
    answer_text = response_json.get("answer", "").lower()
    refused = (
        "don't have" in answer_text
        or "don’t have" in answer_text
        or "not able to" in answer_text
        or "can only help" in answer_text
        or "couldn't find" in answer_text
        or "couldn’t find" in answer_text
        or "no record" in answer_text
        or "passed it to our team" in answer_text
        or "no visibility" in answer_text
        or "cannot compare" in answer_text
        or "contact your property manager" in answer_text
    )
    return refused


def find_forbidden(entry, response_json):
    """Returns the forbidden keywords that appear in the answer (empty list = clean)."""
    answer_text = response_json.get("answer", "").lower()
    return [kw for kw in entry.get("forbidden_keywords", []) if kw.lower() in answer_text]


def grade_route(entry, response_json):
    expected_route = entry.get("expected_route")
    if expected_route is None:
        return None
    return response_json.get("route") == expected_route


def run_once(eval_set, run_number, timestamp):
    results = []
    for entry in eval_set:
        conversation_id = f"eval-{entry['id']}-{uuid.uuid4().hex[:8]}"
        response_json, elapsed = run_question(entry["tenant_id"], entry["question"], conversation_id)
        cost = response_json.get("cost", 0) or 0
        actual_route = response_json.get("route")

        route_result = grade_route(entry, response_json)
        forbidden_hits = find_forbidden(entry, response_json)

        if entry["type"] == "answer":
            matched = grade_answer(entry, response_json)
            correct = matched and not forbidden_hits
            detail = f"keyword_match={matched}"
        elif entry["type"] == "refuse":
            refused = grade_refuse(response_json)
            correct = refused and not forbidden_hits
            detail = f"refused={refused}"
        elif entry["type"] == "isolation":
            correct = not forbidden_hits
            detail = "no_leak" if correct else "LEAK"
        else:
            raise ValueError(f"unknown type {entry['type']!r} in case {entry['id']}")

        if forbidden_hits:
            detail += f", forbidden_found={forbidden_hits}"
        detail += f", route={actual_route}"

        results.append({
            "id": entry["id"], "tenant_id": entry["tenant_id"], "question": entry["question"],
            "type": entry["type"], "expected_route": entry.get("expected_route"),
            "route": actual_route, "correct": correct, "route_correct": route_result,
            "forbidden_found": forbidden_hits, "detail": detail,
            "answer": response_json.get("answer", ""), "cost": round(cost, 6),
            "time_seconds": round(elapsed, 3),
        })
        status = "PASS" if correct else "FAIL"
        print(f"[run {run_number}] [{status}] {entry['id']} ({entry['type']}) - {detail}")

    summary = summarise(results)
    summary.update({"timestamp": timestamp, "run": run_number, "results": results})
    return summary


def pct(num, den):
    return round(num / den * 100, 1) if den else None


def summarise(results):
    by_type = defaultdict(lambda: [0, 0])
    by_route = defaultdict(lambda: {"cases": 0, "correct": 0, "route_correct": 0, "cost": 0.0, "time": 0.0})
    for r in results:
        by_type[r["type"]][1] += 1
        by_type[r["type"]][0] += int(r["correct"])
        # group by the route the case is SUPPOSED to take, so a mis-route counts against that route
        g = by_route[r["expected_route"] or "NONE"]
        g["cases"] += 1
        g["correct"] += int(r["correct"])
        g["route_correct"] += int(bool(r["route_correct"]))
        g["cost"] += r["cost"]
        g["time"] += r["time_seconds"]

    # cost/latency per ACTUAL route (what the finance projection needs)
    cost_by_actual = defaultdict(lambda: {"questions": 0, "cost": 0.0})
    for r in results:
        c = cost_by_actual[r["route"] or "NONE"]
        c["questions"] += 1
        c["cost"] += r["cost"]

    total_cost = sum(r["cost"] for r in results)
    n = len(results)
    avg_cost = total_cost / n if n else 0
    route_graded = [r for r in results if r["route_correct"] is not None]

    return {
        "cases": n,
        "overall_accuracy_pct": pct(sum(r["correct"] for r in results), n),
        "answer_accuracy_pct": pct(*by_type["answer"]) if "answer" in by_type else None,
        "refusal_accuracy_pct": pct(*by_type["refuse"]) if "refuse" in by_type else None,
        "isolation_accuracy_pct": pct(*by_type["isolation"]) if "isolation" in by_type else None,
        "route_accuracy_pct": pct(sum(bool(r["route_correct"]) for r in route_graded), len(route_graded)),
        "per_type": {t: {"correct": v[0], "total": v[1]} for t, v in by_type.items()},
        "per_expected_route": {
            k: {"cases": v["cases"], "correct": v["correct"], "route_correct": v["route_correct"],
                "accuracy_pct": pct(v["correct"], v["cases"]),
                "route_accuracy_pct": pct(v["route_correct"], v["cases"]),
                "avg_cost": round(v["cost"] / v["cases"], 6),
                "avg_time_seconds": round(v["time"] / v["cases"], 2)}
            for k, v in by_route.items()
        },
        "cost_per_actual_route": {
            k: {"questions": v["questions"], "total_cost": round(v["cost"], 6),
                "avg_cost": round(v["cost"] / v["questions"], 6)}
            for k, v in cost_by_actual.items()
        },
        "total_cost": round(total_cost, 6),
        "avg_cost_per_question": round(avg_cost, 6),
        "projected_monthly_cost_400": round(avg_cost * 400, 2),
        "projected_monthly_cost_600": round(avg_cost * 600, 2),
        "total_time_seconds": round(sum(r["time_seconds"] for r in results), 2),
    }


def print_scorecard(s, label):
    print()
    print(f"=== SCORECARD ({label}) ===")
    print(f"Overall: {s['overall_accuracy_pct']}% of {s['cases']} cases")
    for key, name in [("answer_accuracy_pct", "Answer"), ("refusal_accuracy_pct", "Refusal"),
                      ("isolation_accuracy_pct", "Isolation"), ("route_accuracy_pct", "Route")]:
        if s.get(key) is not None:
            print(f"{name} accuracy: {s[key]}%")
    print("Per route (by expected route):")
    for route in ROUTES:
        g = s["per_expected_route"].get(route)
        if g:
            print(f"  {route:17s} {g['correct']}/{g['cases']} correct, route {g['route_correct']}/{g['cases']}, "
                  f"avg cost ${g['avg_cost']:.6f}, avg time {g['avg_time_seconds']}s")
    print(f"Total cost: ${s['total_cost']:.6f}   Average per question: ${s['avg_cost_per_question']:.6f}")
    print(f"Monthly projection (eval-set mix): 400 q = ${s['projected_monthly_cost_400']:.2f}, "
          f"600 q = ${s['projected_monthly_cost_600']:.2f}")


def run_eval(eval_set_path, runs):
    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    run_summaries, run_files = [], []
    for i in range(1, runs + 1):
        s = run_once(eval_set, i, timestamp)
        print_scorecard(s, f"run {i} of {runs}")
        path = os.path.join(EVIDENCE_DIR, f"tamam_eval_results_{timestamp}_run{i}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
        run_summaries.append(s)
        run_files.append(path)

    # combined view across all runs: every question from every run counted once
    all_results = [r for s in run_summaries for r in s["results"]]
    combined = summarise(all_results)
    # stability: which cases passed in every run, and which flipped
    per_case = defaultdict(list)
    for r in all_results:
        per_case[r["id"]].append(r["correct"])
    combined.update({
        "timestamp": timestamp, "runs": runs, "eval_set": eval_set_path,
        "run_files": run_files,
        "per_run_overall_accuracy_pct": [s["overall_accuracy_pct"] for s in run_summaries],
        "per_run_route_accuracy_pct": [s["route_accuracy_pct"] for s in run_summaries],
        "cases_passed_every_run": sorted(k for k, v in per_case.items() if all(v)),
        "cases_failed_every_run": sorted(k for k, v in per_case.items() if not any(v)),
        "cases_unstable": sorted(k for k, v in per_case.items() if any(v) and not all(v)),
    })
    print_scorecard(combined, f"all {runs} runs combined")
    if combined["cases_unstable"] or combined["cases_failed_every_run"]:
        print(f"Unstable cases: {combined['cases_unstable']}")
        print(f"Failed every run: {combined['cases_failed_every_run']}")

    summary_path = os.path.join(EVIDENCE_DIR, f"tamam_eval_summary_{timestamp}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print(f"\nSaved {runs} run file(s) and summary to {summary_path}")
    print("Next: python tamam_report.py   (writes evidence/ACCURACY_REPORT.md and evidence/COST_REPORT.md)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("eval_set", nargs="?", default="tamam_eval_set.json")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    run_eval(args.eval_set, args.runs)
