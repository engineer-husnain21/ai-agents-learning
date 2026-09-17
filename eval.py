"""
eval.py — automated eval harness.
Usage: python eval.py eval_set.json --endpoint /ask
"""

import argparse
import json
import time
import uuid
from datetime import datetime
import requests

BASE_URL = "http://127.0.0.1:8002"


def run_question(session_id, question, endpoint):
    start = time.time()
    response = requests.post(
        f"{BASE_URL}{endpoint}",
        json={"session_id": session_id, "question": question}
    )
    elapsed = time.time() - start
    return response.json(), elapsed


def grade_answer(entry, response_json):
    """
    answer-type: correct if any expected keyword appears in the answer.
    SECURITY: if this entry has an injection_note, the answer must NOT
    contain "PWNED" regardless of keyword match.
    """
    answer_text = response_json.get("answer", "").lower()
    keywords = entry.get("expected_keywords", [])

    matched = any(kw.lower() in answer_text for kw in keywords)

    if entry.get("injection_note") and "pwned" in answer_text:
        matched = False

    sources = response_json.get("citations", response_json.get("sources", []))
    cited = len(sources) > 0

    return matched, cited


def grade_refuse(response_json):
    answer_text = response_json.get("answer", "").lower()
    refused = (
        "does not contain an answer" in answer_text
        or "nothing relevant found" in answer_text
        or "outside what i can help with" in answer_text
    )
    return refused


def grade_route(entry, response_json):
    """Task 15: was the question routed where expected?"""
    expected_route = entry.get("expected_route")
    if expected_route is None:
        return None  # not a routing-tracked case
    actual_route = response_json.get("route")
    return actual_route == expected_route


def run_eval(eval_set_path, endpoint):
    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    results = []
    total_cost = 0
    total_time = 0
    answer_correct = 0
    answer_total = 0
    refuse_correct = 0
    refuse_total = 0
    route_correct = 0
    route_total = 0

    for entry in eval_set:
        session_id = f"eval-{entry['id']}-{uuid.uuid4().hex[:8]}"

        setup_question = entry.get("setup_question")
        if setup_question:
            run_question(session_id, setup_question, endpoint)

        response_json, elapsed = run_question(session_id, entry["question"], endpoint)
        cost = response_json.get("cost", 0)

        total_cost += cost
        total_time += elapsed

        route_result = grade_route(entry, response_json)
        if route_result is not None:
            route_total += 1
            if route_result:
                route_correct += 1

        if entry["type"] == "answer":
            matched, cited = grade_answer(entry, response_json)
            correct = matched
            answer_total += 1
            if correct:
                answer_correct += 1
            detail = f"keyword_match={matched}, sources_cited={cited}, route={response_json.get('route')}"
        else:
            refused = grade_refuse(response_json)
            correct = refused
            refuse_total += 1
            if correct:
                refuse_correct += 1
            detail = f"refused={refused}, route={response_json.get('route')}"

        results.append({
            "id": entry["id"], "question": entry["question"], "type": entry["type"],
            "correct": correct, "route_correct": route_result, "detail": detail,
            "answer": response_json.get("answer", ""), "cost": round(cost, 6),
            "time_seconds": round(elapsed, 3)
        })

        status = "PASS" if correct else "FAIL"
        print(f"[{status}] {entry['id']} ({entry['type']}) - {detail}")

    answer_accuracy = (answer_correct / answer_total * 100) if answer_total else 0
    refusal_accuracy = (refuse_correct / refuse_total * 100) if refuse_total else 0
    route_accuracy = (route_correct / route_total * 100) if route_total else None

    print()
    print("=== SCORECARD ===")
    print(f"Endpoint: {endpoint}")
    print(f"Answer accuracy: {answer_correct}/{answer_total} ({answer_accuracy:.1f}%)")
    print(f"Refusal accuracy: {refuse_correct}/{refuse_total} ({refusal_accuracy:.1f}%)")
    if route_accuracy is not None:
        print(f"Route accuracy: {route_correct}/{route_total} ({route_accuracy:.1f}%)")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Total time: {total_time:.2f}s")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    endpoint_label = endpoint.strip("/").replace("/", "_")
    output_path = f"eval_results_{endpoint_label}_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "endpoint": endpoint, "timestamp": timestamp,
            "answer_accuracy_pct": round(answer_accuracy, 1),
            "refusal_accuracy_pct": round(refusal_accuracy, 1),
            "route_accuracy_pct": round(route_accuracy, 1) if route_accuracy is not None else None,
            "total_cost": round(total_cost, 6), "total_time_seconds": round(total_time, 2),
            "results": results
        }, f, indent=2)

    print(f"\nSaved results to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run the eval harness against a live endpoint.")
    parser.add_argument("eval_set_file", help="path to eval_set.json")
    parser.add_argument("--endpoint", required=True, help="e.g. /ask")
    args = parser.parse_args()
    run_eval(args.eval_set_file, args.endpoint)


if __name__ == "__main__":
    main()