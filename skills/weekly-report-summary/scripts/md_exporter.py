# -*- coding: utf-8 -*-
"""个人历史周报 Markdown 导出。"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Sequence

import config
from content_parser import PERSONAL_SECTION_KEYS, get_section_label, normalize_section_key


def _display_date(record: Dict) -> str:
    parsed_date = record.get("parsed_date", "")
    if parsed_date:
        try:
            return datetime.fromisoformat(parsed_date).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return parsed_date
    return record.get("date", "") or "未知日期"


def _sorted_records(records: Sequence[Dict]) -> List[Dict]:
    return sorted(
        records,
        key=lambda item: item.get("parsed_date") or item.get("date", ""),
        reverse=True,
    )


def _display_mailbox(record: Dict) -> str:
    requested = str(record.get("mailbox", "")).strip()
    resolved = str(record.get("resolved_mailbox", "")).strip()

    alias_sets = {
        "已发送": {"sent", *config.PERSONAL_MAILBOX_ALIASES.get("sent", ())},
        "收件箱": {"inbox", *config.PERSONAL_MAILBOX_ALIASES.get("inbox", ())},
        "本地样例": {"fixture"},
    }

    for label, candidates in alias_sets.items():
        normalized_candidates = {str(item).strip().lower() for item in candidates}
        if requested.lower() in normalized_candidates or resolved.lower() in normalized_candidates:
            return label

    for value in (requested, resolved):
        if not value:
            continue
        if any("\u4e00" <= char <= "\u9fff" for char in value):
            return value

    return requested or resolved or "未知"


def build_markdown_document(
    reports: Sequence[Dict],
    section_only: bool = False,
    section_key: str = "",
) -> str:
    """将个人周报记录拼成单个 Markdown 归档文档。"""
    normalized_section_key = normalize_section_key(section_key)
    sorted_reports = _sorted_records(reports)

    mailboxes = []
    for report in sorted_reports:
        mailbox = _display_mailbox(report)
        if mailbox and mailbox not in mailboxes:
            mailboxes.append(mailbox)

    lines = [
        "# 个人历史周报归档",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 周报数量: {len(sorted_reports)}",
    ]
    if mailboxes:
        lines.append(f"- 来源邮箱: {', '.join(mailboxes)}")
    lines.append("")

    for report in sorted_reports:
        lines.append(f"## {report.get('subject', '未命名周报')}")
        lines.append("")
        lines.append(f"- 日期: {_display_date(report)}")
        lines.append(
            f"- 发件人: {report.get('sender_name', '未知')} <{report.get('sender_email', '未知邮箱')}>"
        )
        lines.append(
            f"- 邮箱目录: {_display_mailbox(report)}"
        )
        lines.append("")

        if section_only:
            label = get_section_label(normalized_section_key)
            content = report.get(normalized_section_key, "").strip()
            lines.append(f"### {label}")
            lines.append("")
            lines.append(content or f"未识别到 {label} 区块。")
            lines.append("")
            continue

        has_any_section = False
        for key in PERSONAL_SECTION_KEYS:
            content = report.get(key, "").strip()
            if not content:
                continue
            has_any_section = True
            lines.append(f"### {get_section_label(key)}")
            lines.append("")
            lines.append(content)
            lines.append("")

        if not has_any_section:
            raw_body = report.get("raw_body") or report.get("body") or ""
            lines.append("### 原始正文")
            lines.append("")
            lines.append(raw_body.strip() or "未提取到正文内容。")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def export_to_markdown(
    reports: Sequence[Dict],
    output_path: str = None,
    section_only: bool = False,
    section_key: str = "",
) -> str:
    """将个人历史周报导出为单个 Markdown 文件。"""
    normalized_section_key = normalize_section_key(section_key)
    if section_only and not normalized_section_key:
        raise ValueError("section_only 模式需要提供有效的 section_key")

    target_path = output_path or config.PERSONAL_OUTPUT_PATH
    target_dir = os.path.dirname(target_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    document = build_markdown_document(
        reports,
        section_only=section_only,
        section_key=normalized_section_key,
    )
    with open(target_path, "w", encoding="utf-8") as file:
        file.write(document)
    return target_path
