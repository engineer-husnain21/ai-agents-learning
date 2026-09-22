"""
tamam_eval.py — eval harness for the Tamam tenant assistant.
Usage: python tamam_eval.py tamam_eval_set.json
"""

import json
import time
import uuid
from datetime import datetime
import requests

BASE_URL = "http://127.0.0.1:8003"


def run_question(tenant_id, question, conversation_id):
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/ask",
        json={"tenant_id": tenant_id, "conversation_id": conversation_id, "question": question}
    )
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
        or "not able to" in answer_text
        or "can only help" in answer_text
        or "couldn't find" in answer_text
        or "no record" in answer_text
        or "passed it to our team" in answer_text
    )
    return refused


def grade_route(entry, response_json):
    expected_route = entry.get("expected_route")
    if expected_route is None:
        return None
    return response_json.get("route") == expected_route


def run_eval(eval_set_path):
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
        conversation_id = f"eval-{entry['id']}-{uuid.uuid4().hex[:8]}"
        response_json, elapsed = run_question(entry["tenant_id"], entry["question"], conversation_id)
        cost = response_json.get("cost", 0)
        total_cost += cost
        total_time += elapsed

        route_result = grade_route(entry, response_json)
        if route_result is not None:
            route_total += 1
            if route_result:
                route_correct += 1

        if entry["type"] == "answer":
            matched = grade_answer(entry, response_json)
            correct = matched
            answer_total += 1
            if correct:
                answer_correct += 1
            detail = f"keyword_match={matched}, route={response_json.get('route')}"
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
    avg_cost = total_cost / len(eval_set) if eval_set else 0

    print()
    print("=== SCORECARD ===")
    print(f"Answer accuracy: {answer_correct}/{answer_total} ({answer_accuracy:.1f}%)")
    print(f"Refusal accuracy: {refuse_correct}/{refuse_total} ({refusal_accuracy:.1f}%)")
    if route_accuracy is not None:
        print(f"Route accuracy: {route_correct}/{route_total} ({route_accuracy:.1f}%)")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Average cost per question: ${avg_cost:.6f}")
    print(f"Total time: {total_time:.2f}s")
    print()
    print("=== MONTHLY COST PROJECTION (client's stated 400-600 questions/month) ===")
    print(f"  At 400 questions/month: ${avg_cost * 400:.2f}")
    print(f"  At 600 questions/month: ${avg_cost * 600:.2f}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"tamam_eval_results_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp, "answer_accuracy_pct": round(answer_accuracy, 1),
            "refusal_accuracy_pct": round(refusal_accuracy, 1),
            "route_accuracy_pct": round(route_accuracy, 1) if route_accuracy is not None else None,
            "total_cost": round(total_cost, 6), "avg_cost_per_question": round(avg_cost, 6),
            "projected_monthly_cost_400": round(avg_cost * 400, 2),
            "projected_monthly_cost_600": round(avg_cost * 600, 2),
            "total_time_seconds": round(total_time, 2), "results": results
        }, f, indent=2)
    print(f"\nSaved results to {output_path}")


if __name__ == "__main__":
    run_eval("tamam_eval_set.json")