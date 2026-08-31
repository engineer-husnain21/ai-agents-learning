"""
repeat_test.py — runs the SAME question N times (no history, fresh session
each time) and records the gate score every time. This tells us whether
the SCORE itself is unstable, or whether the score is stable and only the
final ANSWER varies.

Usage: python repeat_test.py "who is the mad hatter" --n 10
"""

import argparse
import uuid
import requests

BASE_URL = "http://127.0.0.1:8002"


def main():
    parser = argparse.ArgumentParser(description="Repeat the same question N times, record gate scores.")
    parser.add_argument("question", help="the question to repeat, in quotes")
    parser.add_argument("--n", type=int, default=10, help="how many times to run it")
    args = parser.parse_args()

    scores = []
    answers = []

    for i in range(args.n):
        session_id = f"repeat-{uuid.uuid4().hex[:8]}"  # fresh session every time
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"session_id": session_id, "question": args.question}
        )
        result = response.json()
        score = result.get("gate_score", None)
        answer = result.get("answer", "")

        scores.append(score)
        answers.append(answer)

        print(f"Run {i+1}: gate_score={score}, answer={answer[:80]}")

    print()
    print("=== SUMMARY ===")
    print(f"Question: {args.question}")
    print(f"Scores: {scores}")
    if scores and all(s is not None for s in scores):
        print(f"Min: {min(scores)}, Max: {max(scores)}, Spread: {max(scores) - min(scores):.4f}")

    unique_answers = set(answers)
    print(f"Unique answers seen: {len(unique_answers)}")
    if len(unique_answers) > 1:
        print("NOTE: answer text varied across runs even where scores were similar/identical")


if __name__ == "__main__":
    main()