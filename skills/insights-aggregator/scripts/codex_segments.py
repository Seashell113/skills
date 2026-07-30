#!/usr/bin/env python3
"""Read one Codex rollout at a frozen byte cutoff and isolate its owned events.

Codex may materialize an ancestor session inside a fork/subagent rollout.  The
physical rollout starts with its own ``session_meta`` and can then contain one
or more foreign ``session_meta`` blocks as imported history.  Only blocks owned
by the physical session are eligible for per-session metrics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JsonlRecord:
    line_number: int
    start_offset: int
    end_offset: int
    row: dict[str, Any]


@dataclass(frozen=True)
class OwnedCodexStream:
    records: tuple[JsonlRecord, ...]
    audit: dict[str, Any]


def _session_id(record: JsonlRecord) -> str | None:
    if record.row.get("type") != "session_meta":
        return None
    payload = record.row.get("payload") or {}
    value = payload.get("id") or payload.get("session_id")
    return str(value) if value else None


def _is_subagent_live_marker(record: JsonlRecord) -> bool:
    return record.row.get("type") == "inter_agent_communication_metadata"


def _is_subagent_live_prefix(record: JsonlRecord) -> bool:
    row = record.row
    payload = row.get("payload") or {}
    return row.get("type") == "turn_context" or (
        row.get("type") == "event_msg" and payload.get("type") == "task_started"
    )


def _compress_segments(
    records: list[JsonlRecord],
    owners: list[str | None],
    expected_session_id: str,
    recovered_start: int | None,
) -> list[dict[str, Any]]:
    if not records:
        return []
    segments: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(records) + 1):
        if index < len(records) and owners[index] == owners[start]:
            continue
        owner = owners[start]
        first = records[start]
        last = records[index - 1]
        if owner is None:
            kind = "orphan"
        elif owner == expected_session_id:
            kind = (
                "owned_live_recovered_subagent"
                if recovered_start is not None and start >= recovered_start
                else "owned"
            )
        else:
            kind = "imported_history"
        segments.append(
            {
                "owner_session_id": owner,
                "kind": kind,
                "start_offset": first.start_offset,
                "end_offset": last.end_offset,
                "start_line": first.line_number,
                "end_line": last.line_number,
                "valid_json_lines": index - start,
            }
        )
        start = index
    return segments


def _call_link_audit(records: list[JsonlRecord]) -> dict[str, Any]:
    call_ids: set[str] = set()
    result_ids: list[str] = []
    turn_ids: set[str] = set()
    for record in records:
        row = record.row
        payload = row.get("payload") or {}
        for key in ("turn_id", "trigger_turn"):
            if payload.get(key):
                turn_ids.add(str(payload[key]))
        if row.get("type") != "response_item":
            continue
        item_type = payload.get("type")
        call_id = payload.get("call_id")
        if item_type in {"function_call", "custom_tool_call"} and call_id:
            call_ids.add(str(call_id))
        elif item_type in {"function_call_output", "custom_tool_call_output"} and call_id:
            result_ids.append(str(call_id))
    matched = sum(call_id in call_ids for call_id in result_ids)
    return {
        "native_turn_ids": len(turn_ids),
        "native_call_ids": len(call_ids),
        "results_with_call_id": len(result_ids),
        "results_linked_to_owned_call": matched,
        "result_call_link_rate": (
            round(matched / len(result_ids), 6) if result_ids else None
        ),
    }


def read_owned_codex_stream(
    path: str | Path,
    expected_session_id: str,
    *,
    byte_limit: int | None = None,
    expected_sha256: str | None = None,
) -> OwnedCodexStream:
    """Return valid rows owned by ``expected_session_id`` plus an audit record.

    ``byte_limit`` freezes an append-only rollout.  The SHA-256 covers every
    byte in that prefix, including malformed or partial JSONL records.
    """

    source_path = Path(path)
    file_size = source_path.stat().st_size
    limit = file_size if byte_limit is None else int(byte_limit)
    if limit < 0:
        raise ValueError("byte_limit must be non-negative")
    if file_size < limit:
        raise ValueError(
            f"source shorter than frozen cutoff: current={file_size}, cutoff={limit}"
        )

    records: list[JsonlRecord] = []
    invalid_lines: list[dict[str, int]] = []
    digest = hashlib.sha256()
    offset = 0
    line_number = 0
    with source_path.open("rb") as handle:
        while offset < limit:
            chunk = handle.readline(limit - offset)
            if not chunk:
                break
            line_number += 1
            start_offset = offset
            offset += len(chunk)
            digest.update(chunk)
            try:
                decoded = json.loads(chunk)
            except (json.JSONDecodeError, UnicodeDecodeError):
                invalid_lines.append(
                    {
                        "line_number": line_number,
                        "start_offset": start_offset,
                        "end_offset": offset,
                    }
                )
                continue
            if not isinstance(decoded, dict):
                invalid_lines.append(
                    {
                        "line_number": line_number,
                        "start_offset": start_offset,
                        "end_offset": offset,
                    }
                )
                continue
            records.append(
                JsonlRecord(line_number, start_offset, offset, decoded)
            )
    if offset != limit:
        raise ValueError(f"unable to read frozen cutoff: read={offset}, cutoff={limit}")

    prefix_sha256 = digest.hexdigest()
    if expected_sha256 and prefix_sha256 != expected_sha256:
        raise ValueError(
            "snapshot SHA-256 mismatch: "
            f"expected={expected_sha256}, actual={prefix_sha256}"
        )

    meta_indexes = [
        index for index, record in enumerate(records) if _session_id(record)
    ]
    first_meta_index = meta_indexes[0] if meta_indexes else None
    physical_meta = (
        records[first_meta_index].row.get("payload") or {}
        if first_meta_index is not None
        else {}
    )
    first_meta_session_id = (
        _session_id(records[first_meta_index])
        if first_meta_index is not None
        else None
    )

    owners: list[str | None] = []
    current_owner: str | None = None
    for record in records:
        marker = _session_id(record)
        if marker:
            current_owner = marker
        owners.append(current_owner)

    foreign_indexes = [
        index
        for index in meta_indexes
        if _session_id(records[index]) != expected_session_id
    ]
    physical_recurrences = [
        index
        for index in meta_indexes
        if index > (foreign_indexes[0] if foreign_indexes else -1)
        and _session_id(records[index]) == expected_session_id
    ]

    recovered_start: int | None = None
    thread_source = physical_meta.get("thread_source")
    if (
        first_meta_session_id == expected_session_id
        and foreign_indexes
        and not physical_recurrences
        and thread_source == "subagent"
    ):
        marker_index = next(
            (
                index
                for index in range(foreign_indexes[0] + 1, len(records))
                if _is_subagent_live_marker(records[index])
            ),
            None,
        )
        if marker_index is not None:
            recovered_start = marker_index
            while (
                recovered_start > foreign_indexes[0] + 1
                and _is_subagent_live_prefix(records[recovered_start - 1])
            ):
                recovered_start -= 1
            for index in range(recovered_start, len(owners)):
                owners[index] = expected_session_id

    identity_valid = first_meta_session_id == expected_session_id
    owned_records = (
        [
            record
            for record, owner in zip(records, owners)
            if owner == expected_session_id
        ]
        if identity_valid
        else []
    )
    imported_ids = sorted(
        {
            owner
            for owner in owners
            if owner and owner != expected_session_id
        }
    )
    non_meta_owned = sum(
        record.row.get("type") != "session_meta" for record in owned_records
    )
    if not meta_indexes:
        ownership_status = "no_session_meta"
    elif not identity_valid:
        ownership_status = "physical_session_mismatch"
    elif non_meta_owned == 0 and imported_ids:
        ownership_status = "header_only_with_imported_history"
    elif recovered_start is not None:
        ownership_status = "owned_with_subagent_recovery"
    elif imported_ids:
        ownership_status = "owned_with_imported_history_excluded"
    else:
        ownership_status = "owned_single_session"

    link_audit = _call_link_audit(owned_records)
    audit = {
        "expected_session_id": expected_session_id,
        "first_meta_session_id": first_meta_session_id,
        "identity_valid": identity_valid,
        "ownership_status": ownership_status,
        "byte_length": limit,
        "sha256": prefix_sha256,
        "line_count": line_number,
        "valid_json_lines": len(records),
        "invalid_json_lines": len(invalid_lines),
        "invalid_line_locations": invalid_lines,
        "orphan_valid_lines": sum(owner is None for owner in owners),
        "owned_valid_lines": len(owned_records),
        "owned_non_meta_lines": non_meta_owned,
        "owner_leakage_lines": 0,
        "imported_session_ids": imported_ids,
        "segments": _compress_segments(
            records, owners, expected_session_id, recovered_start
        ),
        "lineage": {
            "forked_from_id": physical_meta.get("forked_from_id"),
            "parent_thread_id": physical_meta.get("parent_thread_id"),
            "thread_source": thread_source,
        },
        **link_audit,
    }
    return OwnedCodexStream(tuple(owned_records), audit)
