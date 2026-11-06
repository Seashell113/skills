from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codex_segments import load_snapshot_sources, read_owned_snapshot_session
from collect import codex_scan, codex_parse
from recover_codex_snapshot import authenticate_recovery
import test_codex_segments as fixtures

A, B, row = fixtures.A, fixtures.B, fixtures.row

ZSTD = shutil.which("zstd") or ("/opt/homebrew/bin/zstd" if Path("/opt/homebrew/bin/zstd").exists() else None)


@unittest.skipUnless(ZSTD, "zstd executable unavailable")
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / f"rollout-test-{A}.jsonl"
        self.frozen = (json.dumps(row("session_meta", {"id": A})) + "\n" +
                       json.dumps(row("event_msg", {"type": "user_message", "message": "frozen"})) + "\n").encode()
        self.item = {"session_id": A, "path": str(self.original), "byte_length": len(self.frozen),
                     "sha256": hashlib.sha256(self.frozen).hexdigest(), "mtime_ns": 1}
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"snapshot_id": "frozen", "files": [self.item]}))
        self.successor = Path(str(self.original) + ".zst")
        self.mapping = self.root / "recovery-map.json"

    def compress(self, raw):
        self.successor.write_bytes(subprocess.run([ZSTD, "-q", "-c"], input=raw, stdout=subprocess.PIPE, check=True).stdout)

    def map_entry(self):
        entry = authenticate_recovery(self.item, self.successor)
        self.mapping.write_text(json.dumps({"schema_version": 1, "snapshot_id": "frozen",
            "manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(), "files": [entry]}))
        return entry

    def read(self):
        sources = {s["session_id"]: s for s in codex_scan("unused", self.manifest, self.mapping)}
        return read_owned_snapshot_session(sources, A)

    def test_logical_frozen_prefix_excludes_later_appends_and_keeps_two_hashes(self):
        self.compress(self.frozen + (json.dumps(row("event_msg", {"type": "user_message", "message": "later"})) + "\n").encode())
        entry = self.map_entry()
        stream = self.read()
        self.assertEqual(stream.audit["sha256"], self.item["sha256"])
        self.assertNotEqual(entry["compressed"]["sha256"], stream.audit["sha256"])
        self.assertEqual([r.row["payload"].get("message") for r in stream.records], [None, "frozen"])
        self.assertEqual(self.manifest.read_text(), json.dumps({"snapshot_id": "frozen", "files": [self.item]}))
        info = load_snapshot_sources(self.manifest, self.mapping)[0]
        parsed = codex_parse(info["path"], A, info["byte_length"], info["sha256"], recovery_source=info["recovery_source"])
        self.assertEqual([e["text"] for e in parsed.events if e["kind"] == "user"], ["frozen"])

    def test_wrong_decoded_prefix_hash_rejected(self):
        self.compress(self.frozen.replace(b"frozen", b"wrong!"))
        with self.assertRaisesRegex(ValueError, "recovered snapshot SHA-256 mismatch"):
            self.map_entry()

    def test_short_decoded_prefix_rejected(self):
        self.compress(self.frozen[:-1])
        with self.assertRaisesRegex(ValueError, "shorter than frozen"):
            self.map_entry()

    def test_corrupt_compressed_file_rejected_even_when_physical_hash_matches(self):
        self.successor.write_bytes(b"not a zstd frame")
        with self.assertRaisesRegex(ValueError, "zstd decompression failed"):
            self.map_entry()

    def test_compressed_physical_hash_is_rechecked_on_read(self):
        self.compress(self.frozen)
        self.map_entry()
        data = bytearray(self.successor.read_bytes())
        data[-1] ^= 1
        self.successor.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "snapshot SHA-256 mismatch"):
            self.read()

    def test_existing_original_takes_precedence_and_bad_hash_never_falls_back(self):
        self.compress(self.frozen)
        self.map_entry()
        self.original.write_bytes(self.frozen)
        self.assertIsNone(self.read().audit["recovery_source"])
        self.original.write_bytes(self.frozen.replace(b"frozen", b"wrong!"))
        with self.assertRaisesRegex(ValueError, "snapshot SHA-256 mismatch"):
            self.read()

    def test_wrong_map_identity_and_wrong_manifest_digest_rejected(self):
        self.compress(self.frozen)
        self.map_entry()
        mapping = json.loads(self.mapping.read_text())
        mapping["files"][0]["original"]["sha256"] = "0" * 64
        self.mapping.write_text(json.dumps(mapping))
        with self.assertRaisesRegex(ValueError, "original identity mismatch"):
            self.read()
        self.map_entry()
        self.manifest.write_text(self.manifest.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "snapshot identity mismatch"):
            self.read()

    def test_missing_map_never_guesses_compressed_successor(self):
        self.compress(self.frozen)
        sources = {s["session_id"]: s for s in load_snapshot_sources(self.manifest)}
        with self.assertRaises(FileNotFoundError):
            read_owned_snapshot_session(sources, A)

    def test_collect_cli_replays_recovery_into_meta_and_transcript(self):
        self.frozen += (json.dumps(row("event_msg", {"type": "user_message", "message": "second"},
                                       "2026-07-01T00:02:00Z")) + "\n").encode()
        self.item.update(byte_length=len(self.frozen), sha256=hashlib.sha256(self.frozen).hexdigest())
        self.manifest.write_text(json.dumps({"snapshot_id": "frozen", "files": [self.item]}))
        self.compress(self.frozen)
        self.map_entry()
        home = self.root / "home"
        script = Path(__file__).resolve().parents[1] / "scripts/collect.py"
        command = [sys.executable, str(script), "--codex-snapshot-manifest", str(self.manifest),
                   "--codex-recovery-map", str(self.mapping), "--home", str(home),
                   "--claude-dir", str(self.root / "no-claude"), "--codex-dir", str(self.root / "no-codex"),
                   "--since", "2026-06-30T00:00:00Z", "--as-of", "2026-07-02T00:00:00Z",
                   "--max-facets", "1", "--timezone", "UTC"]
        summary = json.loads(subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout)
        self.assertEqual(summary["parse_failed_or_meta"], 0)
        self.assertEqual(summary["pending_facets"], 1)
        self.assertEqual(summary["metas_by_agent"], {"codex": 1})
        transcript = (home / "transcripts/codex" / (A + ".txt")).read_text()
        self.assertIn("frozen", transcript)
        self.assertIn("second", transcript)
        meta = json.loads((home / "cache/meta/codex" / (A + ".json")).read_text())
        self.assertEqual(meta["source_recovery"]["sha256"], hashlib.sha256(self.successor.read_bytes()).hexdigest())

    def test_physical_growth_is_rejected(self):
        self.compress(self.frozen)
        self.map_entry()
        with self.successor.open("ab") as handle:
            handle.write(b"extra")
        with self.assertRaisesRegex(ValueError, "source size changed"):
            self.read()

    def test_partial_failure_map_is_not_accepted(self):
        self.compress(self.frozen)
        self.map_entry()
        mapping = json.loads(self.mapping.read_text())
        mapping["failures"] = [{"session_id": B, "error": "bad hash"}]
        self.mapping.write_text(json.dumps(mapping))
        with self.assertRaisesRegex(ValueError, "contains failed sources"):
            self.read()

    def test_frozen_parent_can_be_recovered_before_packet_attribution(self):
        inherited = [row("event_msg", {"type": "task_started", "turn_id": "parent-turn"}),
                     row("event_msg", {"type": "user_message", "message": "inherited"})]
        parent = self.root / f"rollout-parent-{B}.jsonl"
        parent_raw = "".join(json.dumps(x) + "\n" for x in [row("session_meta", {"id": B}), *inherited]).encode()
        compressed_parent = Path(str(parent) + ".zst")
        compressed_parent.write_bytes(subprocess.run([ZSTD, "-q", "-c"], input=parent_raw, stdout=subprocess.PIPE, check=True).stdout)
        parent_item = {"session_id": B, "path": str(parent), "byte_length": len(parent_raw),
                       "sha256": hashlib.sha256(parent_raw).hexdigest(), "mtime_ns": 1}
        child_raw = "".join(json.dumps(x) + "\n" for x in [
            row("session_meta", {"id": A, "forked_from_id": B}), *inherited,
            row("event_msg", {"type": "user_message", "message": "owned tail"})]).encode()
        self.original.write_bytes(child_raw)
        child_item = {**self.item, "byte_length": len(child_raw), "sha256": hashlib.sha256(child_raw).hexdigest()}
        self.manifest.write_text(json.dumps({"snapshot_id": "frozen", "files": [child_item, parent_item]}))
        entry = authenticate_recovery(parent_item, compressed_parent)
        self.mapping.write_text(json.dumps({"schema_version": 1, "snapshot_id": "frozen",
            "manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(), "files": [entry]}))
        stream = self.read()
        self.assertEqual(stream.audit["fork_history"]["status"], "native_anchored_exact_prefix")
        self.assertEqual([r.line_number for r in stream.records], [1, 4])

    def test_recovery_map_requires_manifest(self):
        with self.assertRaisesRegex(ValueError, "requires --codex-snapshot-manifest"):
            codex_scan("unused", recovery_map=self.mapping)


class FrozenPacketOwnershipTests(unittest.TestCase):
    fork_fixture = fixtures.CodexSegmentTests.fork_fixture
    write_fixture = fixtures.CodexSegmentTests.write_fixture
    def test_packet_entry_uses_frozen_parent_and_never_clears_unknown(self):
        child, parent, sources = self.fork_fixture()
        child_raw = child.read_bytes()
        sources[A] = {"session_id": A, "path": str(child), "byte_length": len(child_raw),
                      "sha256": hashlib.sha256(child_raw).hexdigest()}
        owned = read_owned_snapshot_session(sources, A)
        self.assertEqual([r.line_number for r in owned.records], [1, 5, 6, 7, 8])
        # The actual parent still exists, but a manifest without it must not read it.
        unknown = read_owned_snapshot_session({A: sources[A]}, A)
        self.assertEqual(len(unknown.records), 8)
        self.assertEqual(unknown.audit["fork_history"]["status"], "parent_source_unavailable")


if __name__ == "__main__":
    unittest.main()
