#!/usr/bin/env python3
"""Authenticate missing manifest JSONL paths against explicit zstd successors.

No LLM, source mutation, whole-history scan or persistent decompressed copy.
The output is a private supplemental map; the original manifest is immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from codex_segments import RECOVERY_IDENTITY, _source_jsonl


def authenticate_recovery(item, successor):
    if str(item["path"]).endswith(".zst"):
        raise ValueError("recovery supports original uncompressed JSONL identities only")
    if not item.get("sha256") or item.get("byte_length") is None:
        raise ValueError("recovery requires original byte_length and SHA-256")
    successor = Path(successor)
    if not str(successor).endswith(".jsonl.zst"):
        raise ValueError("successor must be .jsonl.zst")
    before = successor.stat()
    digest = hashlib.sha256()
    with successor.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    physical = {"path": str(successor.resolve()), "byte_length": before.st_size,
                "mtime_ns": before.st_mtime_ns, "sha256": digest.hexdigest()}
    # The reader first verifies physical SHA, then full zstd integrity, then the
    # original decoded prefix SHA. Appends after that prefix are never exposed.
    with _source_jsonl(Path(item["path"]), int(item["byte_length"]), item["sha256"], physical):
        pass
    after = successor.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("compressed successor changed during authentication")
    return {"original": {key: item[key] for key in RECOVERY_IDENTITY},
            "compressed": physical, "status": "decoded_frozen_prefix_sha256_verified"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="new private recovery map; refuses overwrite")
    args = ap.parse_args()
    if args.out.resolve() == args.manifest.resolve():
        ap.error("output must not overwrite the original manifest")
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    entries, failures = [], []
    present = 0
    for item in manifest["files"]:
        if Path(item["path"]).exists():
            present += 1
            continue
        # This name is a candidate only, never proof of equivalence.
        successor = Path(item["path"] + ".zst")
        try:
            entries.append(authenticate_recovery(item, successor))
        except (OSError, ValueError) as exc:
            failures.append({"session_id": item["session_id"], "error": str(exc)})
    mapping = {"schema_version": 1, "snapshot_id": manifest.get("snapshot_id"),
               "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
               "files": entries, "failures": failures,
               "summary": {"manifest_files": len(manifest["files"]), "original_paths_present": present,
                           "recovered": len(entries), "failed": len(failures),
                           "logical_frozen_bytes": sum(e["original"]["byte_length"] for e in entries),
                           "compressed_physical_bytes": sum(e["compressed"]["byte_length"] for e in entries)}}
    args.out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    # Exclusive create: no original manifest or prior evidence can be replaced.
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(mapping, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(mapping["summary"]))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
