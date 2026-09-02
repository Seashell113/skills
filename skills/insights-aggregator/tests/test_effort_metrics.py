from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from collect import ParsedSession, compute_meta  # noqa: E402
from render import bar_chart, high_effort_ratio  # noqa: E402


def meta(session_id, *, internal=False, models=None, efforts=None):
    return {
        "schema_version": 11,
        "agent": "codex",
        "session_id": session_id,
        "source": "Codex Desktop",
        "thread_source": "subagent" if internal else "user",
        "is_internal": internal,
        "auto_review_turns": 0,
        "project_path": "/tmp/project",
        "start_time": "2026-08-20T12:00:00Z",
        "end_time": "2026-08-20T12:05:00Z",
        "duration_minutes": 5,
        "active_minutes": 5,
        "user_message_count": 2,
        "assistant_message_count": 1,
        "tool_counts": {}, "tool_category_counts": {}, "languages": {},
        "git_commits": 0, "git_pushes": 0, "input_tokens": 0, "output_tokens": 0,
        "first_prompt": "test", "summary": None, "user_interruptions": 0,
        "user_response_times": [], "tool_errors": 0, "tool_error_categories": {},
        "uses_task_agent": False, "uses_mcp": False, "uses_web_search": False,
        "uses_web_fetch": False, "lines_added": 0, "lines_removed": 0,
        "files_modified": 0, "message_hours": [], "user_message_timestamps": [],
        "models": models or {}, "reasoning_effort": efforts or {},
        "thinking_turns": 0, "thinking_total": 0,
    }


class EffortMetricsTests(unittest.TestCase):
    def test_turn_context_is_deduplicated_by_turn_id(self):
        now = datetime(2026, 8, 20, tzinfo=timezone.utc)
        session = ParsedSession("codex", "session", "/tmp/project", [
            {"kind": "turn", "ts": now, "turn_id": "one", "model": "gpt", "effort": "max", "thinking": None},
            {"kind": "turn", "ts": now, "turn_id": "one", "model": "gpt", "effort": "max", "thinking": None},
            {"kind": "turn", "ts": now, "turn_id": None, "model": "gpt", "effort": "ultra", "thinking": None},
        ], now, now)

        result = compute_meta(session, {})

        self.assertEqual(result["models"], {"gpt": 2})
        self.assertEqual(result["reasoning_effort"], {"max": 1, "ultra": 1})

    def test_aggregate_and_render_keep_extended_efforts_separate_from_root_totals(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            meta_dir = home / "cache" / "meta" / "codex"
            meta_dir.mkdir(parents=True)
            (meta_dir / "root.json").write_text(json.dumps(meta(
                "root", models={"gpt-5.6-sol": 2, "gpt-5.6-luna": 1},
                efforts={"low": 1, "high": 1, "max": 1, "ultra": 1, "experimental": 1},
            )), encoding="utf-8")
            (meta_dir / "internal.json").write_text(json.dumps(meta(
                "internal", internal=True, models={"gpt-5.6-luna": 2}, efforts={"low": 2},
            )), encoding="utf-8")

            subprocess.run([
                sys.executable, str(SCRIPT_DIR / "aggregate.py"), "--home", str(home),
                "--days", "42", "--as-of", "2026-08-27T13:56:10.186054+00:00",
            ], check=True, capture_output=True, text=True)
            aggregated = json.loads((home / "work" / "aggregated.json").read_text(encoding="utf-8"))

            self.assertEqual(aggregated["generated_at"], "2026-08-27T13:56:10.186054+00:00")
            self.assertEqual(aggregated["combined"]["total_sessions"], 1)
            self.assertEqual(aggregated["combined"]["sessions_with_mixed_models"], 1)
            self.assertEqual(aggregated["combined"]["sessions_with_mixed_reasoning_effort"], 1)
            self.assertEqual(aggregated["internal_model_effort"]["models"], {"gpt-5.6-luna": 2})
            self.assertEqual(aggregated["internal_model_effort"]["reasoning_effort"], {"low": 2})

            out = home / "report.html"
            subprocess.run([
                sys.executable, str(SCRIPT_DIR / "render.py"), "--home", str(home), "--out", str(out),
            ], check=True, capture_output=True, text=True)
            report = out.read_text(encoding="utf-8")
            self.assertIn(">max<", report)
            self.assertIn(">ultra<", report)
            self.assertIn("Experimental", report)
            self.assertIn("内部会话模型配置记录", report)
            self.assertIn("不能据此判断 max 导致慢或过度设计", report)

    def test_high_effort_includes_max_and_ultra(self):
        efforts = {"low": 1, "high": 1, "xhigh": 1, "max": 1, "ultra": 1}
        self.assertEqual(high_effort_ratio(efforts), 80)
        self.assertIn("Experimental", bar_chart({"experimental": 2}, "#000", fixed_order=["low"]))


if __name__ == "__main__":
    unittest.main()
