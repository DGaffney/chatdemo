#!/usr/bin/env python3
"""Evaluation runner for AI Front Desk.

Hits the local API with each test question and validates the response
against expectations. Prints a pass/fail table.

Usage:
    python -m backend.tests.run_evals [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import json
import os
import sys
import httpx


TESTS_PATH = os.path.join(os.path.dirname(__file__), "test_questions.json")


async def run_question(client: httpx.AsyncClient, question: str) -> dict:
    """Send a question to the API and collect the SSE response."""
    response = await client.post(
        "/api/ask",
        json={"question": question},
        timeout=60.0,
    )
    response.raise_for_status()

    answer_parts = []
    metadata = {}

    for line in response.text.split("\n"):
        if line.startswith("data: "):
            raw = line[6:].strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if data.get("type") == "token":
                    answer_parts.append(data["content"])
                elif data.get("type") == "done":
                    metadata = data
            except json.JSONDecodeError:
                pass

    return {
        "answer": "".join(answer_parts),
        **metadata,
    }


def check(label: str, condition: bool) -> tuple[str, bool]:
    return (label, condition)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    with open(TESTS_PATH) as f:
        tests = json.load(f)

    results = []
    passed = 0
    failed = 0

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        for i, test in enumerate(tests):
            question = test["question"]
            print(f"\n[{i+1}/{len(tests)}] {question}")

            try:
                result = await run_question(client, question)
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({"question": question, "error": str(e), "checks": []})
                failed += 1
                continue

            checks = []

            if "expected_intent" in test:
                checks.append(check(
                    f"intent={test['expected_intent']}",
                    result.get("intent") == test["expected_intent"],
                ))

            if "expected_topic" in test:
                checks.append(check(
                    f"topic={test['expected_topic']}",
                    result.get("topic") == test["expected_topic"],
                ))

            if "should_escalate" in test:
                checks.append(check(
                    f"escalated={test['should_escalate']}",
                    result.get("escalated") == test["should_escalate"],
                ))

            if "should_cite" in test:
                cited = result.get("policy_cited", "") or ""
                checks.append(check(
                    f"cites {test['should_cite']}",
                    test["should_cite"].replace(".md", "") in cited.lower()
                    or test["should_cite"] in cited,
                ))

            if test.get("must_contain_staff_notification"):
                answer_lower = result.get("answer", "").lower()
                has_staff_note = any(
                    phrase in answer_lower
                    for phrase in ["flagged", "staff", "follow up", "follow-up", "notified"]
                )
                checks.append(check("staff notification", has_staff_note))

            if test.get("must_not_answer_autonomously"):
                is_escalation = result.get("escalated", False)
                checks.append(check("does not answer autonomously", is_escalation))

            if test.get("should_block"):
                flags = result.get("guardrail_flags", [])
                expected_guard = test.get("expected_guardrail", "")
                has_flag = any(expected_guard in f for f in flags) if expected_guard else len(flags) > 0
                checks.append(check(f"blocked ({expected_guard})", has_flag))

            all_passed = all(ok for _, ok in checks)
            status = "PASS" if all_passed else "FAIL"

            for label, ok in checks:
                mark = "+" if ok else "x"
                print(f"  [{mark}] {label}")

            if all_passed:
                passed += 1
            else:
                failed += 1

            results.append({
                "question": question,
                "intent": result.get("intent"),
                "topic": result.get("topic"),
                "escalated": result.get("escalated"),
                "confidence": result.get("confidence"),
                "checks": [{"label": label, "passed": p} for label, p in checks],
                "status": status,
            })

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if r.get("status") == "FAIL" or r.get("error"):
                print(f"  - {r['question']}")
                for c in r.get("checks", []):
                    if not c["passed"]:
                        print(f"    [x] {c['label']}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
