#!/usr/bin/env python3
"""Run one isolated codex-thread-organizer regression with Codex CLI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--evals", required=True, type=Path)
    parser.add_argument("--eval-id", required=True, type=int, choices=(1, 2))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_events(text: str) -> List[Dict[str, Any]]:
    events = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def find_usage(events: List[Dict[str, Any]]) -> Dict[str, int]:
    usage: Dict[str, int] = {}
    for event in events:
        candidate = event.get("usage")
        if isinstance(candidate, dict):
            usage = {key: int(value) for key, value in candidate.items() if isinstance(value, int)}
        item = event.get("item")
        if isinstance(item, dict) and isinstance(item.get("usage"), dict):
            usage = {
                key: int(value)
                for key, value in item["usage"].items()
                if isinstance(value, int)
            }
    return usage


def count_tools(events: List[Dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))
        if "tool" in item_type or "command" in item_type:
            counts[item_type] += 1
    return counts


def main() -> int:
    args = parse_args()
    eval_data = json.loads(args.evals.read_text(encoding="utf-8"))
    selected = next(item for item in eval_data["evals"] if item["id"] == args.eval_id)

    run_dir = args.output_dir.resolve()
    outputs_dir = run_dir / "outputs"
    input_dir = run_dir / "input"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    skill_copy = input_dir / "skill"
    skill_copy.mkdir(exist_ok=True)
    shutil.copy2(args.skill_path / "SKILL.md", skill_copy / "SKILL.md")
    fixture_copy = input_dir / "thread-scan-cases.json"
    shutil.copy2(args.fixture, fixture_copy)

    output_path = outputs_dir / "output.json"
    prompt = selected["prompt"].replace("FIXTURE_PATH", str(fixture_copy))
    prompt = prompt.replace("OUTPUT_PATH", str(output_path))
    prompt = (
        "先完整读取 "
        + str(skill_copy / "SKILL.md")
        + "，只按该版本 Skill 执行下面的评测任务。不要读取父目录或寻找期望答案。"
        + "bounded_read_cards 只有在你把对应 thread_id 放入 read_ids 后才能作为判断证据。"
        + "最终响应只输出符合 schema 的 JSON，不要 Markdown 或解释。\n\n"
        + prompt
    )

    metadata_path = run_dir.parent / "eval_metadata.json"
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(
                {
                    "eval_id": selected["id"],
                    "eval_name": selected["name"],
                    "prompt": selected["prompt"],
                    "assertions": selected["assertions"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    command = [
        "codex",
        "exec",
        "--model",
        args.model,
        "--config",
        'model_reasoning_effort="' + args.reasoning_effort + '"',
        "--sandbox",
        "read-only",
        "--cd",
        str(input_dir),
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--json",
        "--output-schema",
        str(args.schema.resolve()),
        "--output-last-message",
        str(output_path),
        prompt,
    ]

    started_at = iso_now()
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    duration = time.perf_counter() - started
    ended_at = iso_now()

    events_path = outputs_dir / "events.jsonl"
    events_path.write_text(completed.stdout, encoding="utf-8")
    (outputs_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    events = parse_events(completed.stdout)
    usage = find_usage(events)
    tool_counts = count_tools(events)
    total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    timing = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "total_tokens": total_tokens,
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "duration_ms": round(duration * 1000),
        "total_duration_seconds": round(duration, 3),
        "executor_start": started_at,
        "executor_end": ended_at,
        "executor_duration_seconds": round(duration, 3),
        "tool_calls": sum(tool_counts.values()),
        "tool_calls_by_type": dict(tool_counts),
        "return_code": completed.returncode,
    }
    (run_dir / "timing.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (outputs_dir / "metrics.json").write_text(
        json.dumps(
            {
                "tool_calls": dict(tool_counts),
                "total_tool_calls": sum(tool_counts.values()),
                "total_steps": len(events),
                "errors_encountered": int(completed.returncode != 0),
                "output_chars": len(output_path.read_text(encoding="utf-8"))
                if output_path.exists()
                else 0,
                "transcript_chars": len(completed.stdout),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(timing, ensure_ascii=False))
    if completed.returncode != 0:
        print(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
