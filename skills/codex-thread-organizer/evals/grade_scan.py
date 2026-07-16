#!/usr/bin/env python3
"""Grade a codex-thread-organizer JSON regression output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--suite", required=True, choices=("scan", "scan_all"))
    parser.add_argument("--result", type=Path)
    parser.add_argument("--grading", type=Path)
    return parser.parse_args()


def load_model_output(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def normalize_title(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return "".join(value.split())


def main() -> int:
    args = parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    actual = load_model_output(args.output)

    suite = expected["suites"][args.suite]
    target_ids = suite["thread_ids"]
    expected_decisions = expected["decisions"]
    actual_list = actual.get("decisions", [])
    actual_decisions = {
        item.get("thread_id"): item
        for item in actual_list
        if isinstance(item, dict) and item.get("thread_id") in target_ids
    }

    exact = 0
    action_correct = 0
    rename_candidates = []
    rename_correct = 0
    predicted_review = 0
    details = []

    for thread_id in target_ids:
        wanted = expected_decisions[thread_id]
        got = actual_decisions.get(thread_id, {})
        action_ok = got.get("action") == wanted["action"]
        accepted_titles = wanted.get("accepted_titles", [wanted["proposed_title"]])
        title_ok = any(
            normalize_title(got.get("proposed_title")) == normalize_title(candidate)
            for candidate in accepted_titles
        )
        if wanted["action"] == "needs-review":
            title_ok = True
        accepted_categories = wanted.get("accepted_categories", [wanted["category"]])
        category_ok = got.get("category") in accepted_categories
        accepted_relations = wanted.get(
            "accepted_relation_groups", [wanted["relation_group"]]
        )
        relation_ok = got.get("relation_group") in accepted_relations
        number_ok = got.get("number") == wanted["number"]
        row_exact = action_ok and title_ok and category_ok and relation_ok and number_ok
        exact += int(row_exact)
        action_correct += int(action_ok)
        predicted_review += int(got.get("action") == "needs-review")

        confidences = [
            got.get("topic_confidence"),
            got.get("category_confidence"),
            got.get("relation_confidence"),
            got.get("number_confidence"),
        ]
        if got.get("action") == "rename" and all(value == "high" for value in confidences):
            rename_candidates.append(thread_id)
            rename_correct += int(wanted["action"] == "rename" and title_ok)

        details.append(
            {
                "thread_id": thread_id,
                "passed": row_exact,
                "expected": wanted,
                "actual": got,
            }
        )

    expected_reads = set(suite["read_ids"])
    actual_reads = set(actual.get("read_ids", []))
    numbered_ids = [item for item in expected["numbered_ids"] if item in target_ids]
    numbering_correct = sum(
        1
        for thread_id in numbered_ids
        if actual_decisions.get(thread_id, {}).get("number")
        == expected_decisions[thread_id]["number"]
    )
    protected_ids = [item for item in expected["protected_ids"] if item in target_ids]
    protected_mischanges = sum(
        1
        for thread_id in protected_ids
        if actual_decisions.get(thread_id, {}).get("action") != "skip"
    )
    automatic = sum(
        1
        for thread_id in target_ids
        if actual_decisions.get(thread_id, {}).get("action") in {"rename", "skip"}
    )

    metrics = {
        "suite": args.suite,
        "sample_size": len(target_ids),
        "returned_decisions": len(actual_decisions),
        "exact_decision_accuracy": ratio(exact, len(target_ids)),
        "action_accuracy": ratio(action_correct, len(target_ids)),
        "high_confidence_rename_accuracy": ratio(rename_correct, len(rename_candidates)),
        "high_confidence_rename_count": len(rename_candidates),
        "automatic_coverage": ratio(automatic, len(target_ids)),
        "needs_review_rate": ratio(predicted_review, len(target_ids)),
        "numbering_accuracy": ratio(numbering_correct, len(numbered_ids)),
        "protected_mischange_rate": ratio(protected_mischanges, len(protected_ids)),
        "read_precision": ratio(len(actual_reads & expected_reads), len(actual_reads)),
        "read_recall": ratio(len(actual_reads & expected_reads), len(expected_reads)),
        "unexpected_read_ids": sorted(actual_reads - expected_reads),
        "missing_read_ids": sorted(expected_reads - actual_reads),
    }
    result = {"metrics": metrics, "details": details}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.result:
        args.result.write_text(rendered + "\n", encoding="utf-8")
    if args.grading:
        expected_reviews = {
            thread_id
            for thread_id in target_ids
            if expected_decisions[thread_id]["action"] == "needs-review"
        }
        actual_reviews = {
            thread_id
            for thread_id in target_ids
            if actual_decisions.get(thread_id, {}).get("action") == "needs-review"
        }
        checks = [
            {
                "text": "返回范围内每个线程的内部决策",
                "passed": len(actual_decisions) == len(target_ids),
                "evidence": f"returned={len(actual_decisions)}, expected={len(target_ids)}",
            },
            {
                "text": "Automation 和系统线程均安全跳过",
                "passed": protected_mischanges == 0,
                "evidence": f"protected_mischanges={protected_mischanges}",
            },
            {
                "text": "needs-review 集合与期望一致",
                "passed": actual_reviews == expected_reviews,
                "evidence": f"actual={sorted(actual_reviews)}, expected={sorted(expected_reviews)}",
            },
            {
                "text": "动作、标题、类别、关联和编号全部与期望一致",
                "passed": exact == len(target_ids),
                "evidence": f"exact={exact}/{len(target_ids)}",
            },
            {
                "text": "限量补读集合与期望一致",
                "passed": actual_reads == expected_reads,
                "evidence": f"actual={sorted(actual_reads)}, expected={sorted(expected_reads)}",
            },
        ]
        if numbered_ids:
            checks.append(
                {
                    "text": "连续主线编号与标题顺序正确",
                    "passed": numbering_correct == len(numbered_ids),
                    "evidence": f"numbering={numbering_correct}/{len(numbered_ids)}",
                }
            )
        passed = sum(int(item["passed"]) for item in checks)
        grading = {
            "expectations": checks,
            "summary": {
                "passed": passed,
                "failed": len(checks) - passed,
                "total": len(checks),
                "pass_rate": ratio(passed, len(checks)),
            },
        }
        args.grading.write_text(
            json.dumps(grading, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(rendered)

    return 0 if exact == len(target_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
