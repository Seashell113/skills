from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from codex_segments import read_owned_codex_stream  # noqa: E402
from collect import codex_parse  # noqa: E402


A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"


def row(kind: str, payload: dict, timestamp: str = "2026-07-01T00:00:00Z") -> dict:
    return {"timestamp": timestamp, "type": kind, "payload": payload}


class CodexSegmentTests(unittest.TestCase):
    def write_fixture(self, rows: list[dict]) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / f"rollout-test-{A}.jsonl"
        path.write_text(
            "".join(json.dumps(item) + "\n" for item in rows),
            encoding="utf-8",
        )
        return temp, path

    def test_foreign_history_is_excluded_after_physical_session_returns(self) -> None:
        temp, path = self.write_fixture(
            [
                row("session_meta", {"id": A, "thread_source": "user"}),
                row("session_meta", {"id": B, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "parent"}),
                row("session_meta", {"id": A, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "child"}),
            ]
        )
        self.addCleanup(temp.cleanup)

        parsed = read_owned_codex_stream(path, A)
        messages = [
            record.row["payload"]["message"]
            for record in parsed.records
            if record.row.get("type") == "event_msg"
            and record.row["payload"].get("type") == "user_message"
        ]

        self.assertEqual(messages, ["child"])
        self.assertEqual(parsed.audit["owner_leakage_lines"], 0)
        self.assertEqual(parsed.audit["imported_session_ids"], [B])

    def test_user_fork_without_return_is_header_only(self) -> None:
        temp, path = self.write_fixture(
            [
                row("session_meta", {"id": A, "thread_source": "user"}),
                row("session_meta", {"id": B, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "parent"}),
            ]
        )
        self.addCleanup(temp.cleanup)

        parsed = read_owned_codex_stream(path, A)

        self.assertEqual(parsed.audit["owned_non_meta_lines"], 0)
        self.assertEqual(
            parsed.audit["ownership_status"], "header_only_with_imported_history"
        )

    def test_physical_identity_mismatch_is_rejected(self) -> None:
        temp, path = self.write_fixture(
            [
                row("session_meta", {"id": B, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "foreign"}),
            ]
        )
        self.addCleanup(temp.cleanup)

        parsed = read_owned_codex_stream(path, A)

        self.assertFalse(parsed.audit["identity_valid"])
        self.assertEqual(parsed.audit["ownership_status"], "physical_session_mismatch")
        self.assertEqual(parsed.records, ())

    def test_subagent_live_tail_is_recovered_without_parent_messages(self) -> None:
        temp, path = self.write_fixture(
            [
                row(
                    "session_meta",
                    {
                        "id": A,
                        "thread_source": "subagent",
                        "parent_thread_id": B,
                    },
                ),
                row("session_meta", {"id": B, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "parent"}),
                row("event_msg", {"type": "task_started", "turn_id": "turn-a"}),
                row("turn_context", {"turn_id": "turn-a"}),
                row("inter_agent_communication_metadata", {"trigger_turn": "turn-a"}),
                row(
                    "response_item",
                    {
                        "type": "function_call",
                        "name": "exec_command",
                        "arguments": "{}",
                        "call_id": "call-a",
                    },
                ),
                row(
                    "response_item",
                    {
                        "type": "function_call_output",
                        "call_id": "call-a",
                        "output": "exited with code 0",
                    },
                ),
            ]
        )
        self.addCleanup(temp.cleanup)

        parsed = read_owned_codex_stream(path, A)
        owned_types = [
            (record.row.get("payload") or {}).get("type")
            for record in parsed.records
        ]

        self.assertNotIn("user_message", owned_types)
        self.assertIn("function_call", owned_types)
        self.assertEqual(parsed.audit["results_linked_to_owned_call"], 1)
        self.assertEqual(parsed.audit["result_call_link_rate"], 1.0)

    def test_collector_preserves_native_turn_and_call_ids(self) -> None:
        temp, path = self.write_fixture(
            [
                row("session_meta", {"id": A, "thread_source": "user"}),
                row(
                    "turn_context",
                    {"turn_id": "turn-a", "model": "gpt-test", "effort": "high"},
                ),
                row(
                    "response_item",
                    {
                        "type": "function_call",
                        "id": "item-call",
                        "name": "exec_command",
                        "arguments": "{}",
                        "call_id": "call-a",
                    },
                ),
                row(
                    "response_item",
                    {
                        "type": "function_call_output",
                        "id": "item-result",
                        "call_id": "call-a",
                        "output": "exited with code 0",
                    },
                ),
            ]
        )
        self.addCleanup(temp.cleanup)

        parsed = codex_parse(path, A)
        self.assertIsNotNone(parsed)
        tool_use = next(event for event in parsed.events if event["kind"] == "tool_use")
        tool_result = next(
            event for event in parsed.events if event["kind"] == "tool_result"
        )

        self.assertEqual(tool_use["turn_id"], "turn-a")
        self.assertEqual(tool_use["call_id"], "call-a")
        self.assertEqual(tool_use["native_id"], "item-call")
        self.assertEqual(tool_result["turn_id"], "turn-a")
        self.assertEqual(tool_result["call_id"], "call-a")
        self.assertEqual(tool_result["native_id"], "item-result")

    def test_frozen_prefix_is_stable_after_append(self) -> None:
        temp, path = self.write_fixture(
            [
                row("session_meta", {"id": A, "thread_source": "user"}),
                row("event_msg", {"type": "user_message", "message": "first"}),
            ]
        )
        self.addCleanup(temp.cleanup)
        frozen_size = path.stat().st_size
        first = read_owned_codex_stream(path, A, byte_limit=frozen_size)

        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    row("event_msg", {"type": "user_message", "message": "later"})
                )
                + "\n"
            )

        second = read_owned_codex_stream(
            path,
            A,
            byte_limit=frozen_size,
            expected_sha256=first.audit["sha256"],
        )

        self.assertEqual(first.audit["sha256"], second.audit["sha256"])
        self.assertEqual(
            [record.row for record in first.records],
            [record.row for record in second.records],
        )

    def test_invalid_and_pre_meta_rows_are_counted(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / f"rollout-test-{A}.jsonl"
        with path.open("wb") as handle:
            handle.write(json.dumps(row("event_msg", {"type": "task_started"})).encode())
            handle.write(b"\nnot-json\n")
            handle.write(json.dumps(row("session_meta", {"id": A})).encode())
            handle.write(b"\n")

        parsed = read_owned_codex_stream(path, A)

        self.assertEqual(parsed.audit["invalid_json_lines"], 1)
        self.assertEqual(parsed.audit["orphan_valid_lines"], 1)


if __name__ == "__main__":
    unittest.main()
