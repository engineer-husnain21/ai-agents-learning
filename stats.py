"""
stats.py — reads events.jsonl and reports aggregate metrics.
Usage: python stats.py
"""

import json
from collections import defaultdict

LOG_PATH = "events.jsonl"
THRESHOLD = 0.30  # keep in sync with app/config.py LC_SIMILARITY_THRESHOLD
BORDERLINE_WINDOW = 0.05


def load_events():
    events = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except FileNotFoundError:
        pass
    return events


def print_stats():
    events = load_events()
    total = len(events)

    if total == 0:
        print("No events logged yet.")
        return

    # ----- outcome breakdown -----
    outcome_counts = defaultdict(int)
    for e in events:
        outcome_counts[e["outcome"]] += 1

    # ----- retry stats -----
    retries_fired = [e for e in events if e.get("retry_fired")]
    retries_succeeded = [e for e in retries_fired if e.get("retry_succeeded")]

    # ----- cost / latency -----
    total_cost = sum(e.get("cost", 0) for e in events)
    avg_cost = total_cost / total
    latencies = [e.get("latency_seconds", 0) for e in events]
    avg_latency = sum(latencies) / total
    worst_latency = max(latencies)

    # ----- gate score distribution -----
    scores = [e["gate_score"] for e in events if e.get("gate_score") is not None]
    borderline = [
        s for s in scores
        if THRESHOLD - BORDERLINE_WINDOW <= s <= THRESHOLD + BORDERLINE_WINDOW
    ]

    # ----- systemic vs random: group retries by question -----
    retry_by_question = defaultdict(int)
    for e in retries_fired:
        retry_by_question[e["question"]] += 1

    print("=== STATS ===")
    print(f"Total requests: {total}")
    print()
    print("Outcome breakdown:")
    for outcome, count in outcome_counts.items():
        pct = (count / total) * 100
        print(f"  {outcome}: {count} ({pct:.1f}%)")
    print()
    print(f"Retry rate: {len(retries_fired)}/{total} ({len(retries_fired)/total*100:.1f}%)")
    if retries_fired:
        success_rate = len(retries_succeeded) / len(retries_fired) * 100
        print(f"Retry success rate: {len(retries_succeeded)}/{len(retries_fired)} ({success_rate:.1f}%)")
    print()
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Average cost per question: ${avg_cost:.6f}")
    print()
    print(f"Average latency: {avg_latency:.2f}s")
    print(f"Worst-case latency: {worst_latency:.2f}s")
    print()
    print(f"Gate scores logged: {len(scores)}")
    if scores:
        print(f"  Score range: {min(scores):.4f} to {max(scores):.4f}")
    print(f"Borderline population (within ±{BORDERLINE_WINDOW} of threshold {THRESHOLD}): "
          f"{len(borderline)}/{len(scores)} ({len(borderline)/len(scores)*100:.1f}%)" if scores else "0")
    print()
    print("=== SYSTEMIC vs RANDOM: retries grouped by question ===")
    if retry_by_question:
        for question, count in sorted(retry_by_question.items(), key=lambda x: -x[1]):
            flag = " <- PATTERN (repeated retries on same question)" if count > 1 else ""
            print(f"  \"{question}\": {count} retr{'y' if count == 1 else 'ies'}{flag}")
    else:
        print("  No retries logged yet.")


if __name__ == "__main__":
    print_stats()