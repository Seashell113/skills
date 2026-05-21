# -*- coding: utf-8 -*-
"""个人历史周报提取与清洗。"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import config
from content_parser import normalize_section_key, parse_weekly_report_content
from email_fetcher import (
    build_date_window,
    build_search_criteria,
    close_imap_client,
    create_imap_client,
    ensure_mailbox_selected,
    extract_email_body,
    fetch_header_info,
    fetch_oldest_visible_date,
    fetch_raw_message,
    parse_email_date,
    resolve_mailbox_name,
    search_message_ids,
)


def compile_subject_pattern(pattern: str) -> re.Pattern:
    """编译用户提供的主题正则。"""
    try:
        return re.compile(pattern or config.PERSONAL_SUBJECT_PATTERN)
    except re.error as exc:
        raise ValueError(f"无效的主题正则: {exc}") from exc


def normalize_sender_emails(sender_emails: Optional[Sequence[str]]) -> List[str]:
    """规范化发件人邮箱过滤条件。"""
    values = sender_emails if sender_emails is not None else config.PERSONAL_SENDER_EMAILS
    return [str(item).strip().lower() for item in values if str(item).strip()]


def normalize_sender_names(sender_names: Optional[Sequence[str]]) -> List[str]:
    """规范化发件人姓名过滤条件。"""
    values = sender_names if sender_names is not None else config.PERSONAL_SENDER_NAMES
    return [str(item).strip() for item in values if str(item).strip()]


def matches_subject_pattern(subject: str, compiled_pattern: re.Pattern) -> bool:
    """判断主题是否匹配个人周报规则。"""
    return bool(compiled_pattern.search(subject or ""))


def matches_sender_filters(
    header_info: Dict[str, str],
    sender_emails: Sequence[str],
    sender_names: Sequence[str],
) -> bool:
    """按邮箱和显示名过滤发件人，满足任一条件即可通过。"""
    if not sender_emails and not sender_names:
        return True

    sender_email = str(header_info.get("sender_email", "")).strip().lower()
    sender_name = str(header_info.get("sender_name", "")).strip()
    from_header = str(header_info.get("from_header", ""))

    if sender_emails and sender_email in sender_emails:
        return True

    if sender_names:
        for candidate in sender_names:
            if candidate == sender_name or candidate in sender_name or candidate in from_header:
                return True

    return False


def prepare_personal_reports(
    raw_reports: Sequence[Dict],
    requested_mailbox: str,
    resolved_mailbox: str,
    skip_signature: bool = True,
) -> List[Dict]:
    """将原始邮件记录转换为 Markdown 导出所需的结构。"""
    prepared = []

    for report in raw_reports:
        parsed = parse_weekly_report_content(
            report.get("body", ""),
            skip_signature=skip_signature,
        )
        parsed_date = parse_email_date(report.get("date", ""))
        prepared_report = dict(report)
        prepared_report.update(parsed)
        prepared_report["mailbox"] = requested_mailbox
        prepared_report["resolved_mailbox"] = resolved_mailbox
        prepared_report["parsed_date"] = parsed_date.isoformat() if parsed_date else ""
        prepared.append(prepared_report)

    prepared.sort(
        key=lambda item: item.get("parsed_date") or item.get("date", ""),
        reverse=True,
    )
    return prepared


def build_imap_history_limit_diagnostic(
    requested_mailbox: str,
    requested_since: datetime,
    total_visible: int,
    oldest_visible_date: Optional[datetime],
) -> Optional[str]:
    """基于启发式规则提示 IMAP 历史邮件同步范围可能受限。"""
    normalized_mailbox = (requested_mailbox or "").strip().lower()
    requested_span_days = max((datetime.now() - requested_since).days, 0)

    if normalized_mailbox != "sent" or requested_span_days < 90:
        return None

    suspicious = False
    if total_visible and total_visible <= 50:
        suspicious = True
    if oldest_visible_date and oldest_visible_date > requested_since + timedelta(days=45):
        suspicious = True

    if not suspicious:
        return None

    oldest_text = oldest_visible_date.strftime("%Y-%m-%d") if oldest_visible_date else "未知"
    return (
        "[提示] 检测到已发送文件夹的可见邮件历史可能受 IMAP 同步范围限制。\n"
        f"- 请求起始日期: {requested_since.strftime('%Y-%m-%d')}\n"
        f"- 当前文件夹最早可见邮件: {oldest_text}\n"
        f"- 当前文件夹总可见邮件数: {total_visible}\n"
        "可能原因：阿里邮箱客户端同步范围只开放了最近一段历史。\n"
        "建议排查：登录网页版邮箱，进入设置中的客户端或 IMAP 相关配置，将历史同步范围调整为更长时间或全部。\n"
        "如暂时无法调整，可显式改用 `--personal-mailbox inbox` 再试。"
    )


def load_personal_reports_from_json(
    json_path: str,
    requested_mailbox: str = "fixture",
    resolved_mailbox: str = "fixture",
    subject_pattern: Optional[str] = None,
    sender_emails: Optional[Sequence[str]] = None,
    sender_names: Optional[Sequence[str]] = None,
    skip_signature: Optional[bool] = None,
) -> Tuple[List[Dict], List[str]]:
    """从本地 JSON fixture 读取个人周报原始邮件记录。"""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON 文件不存在: {json_path}")

    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, dict):
        raw_reports = payload.get("reports", [])
    else:
        raw_reports = payload

    if not isinstance(raw_reports, list):
        raise ValueError("个人周报 JSON 必须是列表，或包含 reports 列表的对象")

    compiled_pattern = compile_subject_pattern(subject_pattern or config.PERSONAL_SUBJECT_PATTERN)
    normalized_emails = normalize_sender_emails(sender_emails)
    normalized_names = normalize_sender_names(sender_names)
    effective_skip_signature = config.PERSONAL_SKIP_SIGNATURE if skip_signature is None else skip_signature

    matched_reports = []
    for item in raw_reports:
        if not isinstance(item, dict):
            continue

        header_info = {
            "subject": item.get("subject", ""),
            "sender_name": item.get("sender_name", ""),
            "sender_email": item.get("sender_email", ""),
            "from_header": item.get("from_header", item.get("sender_name", "")),
        }
        if not matches_subject_pattern(header_info["subject"], compiled_pattern):
            continue
        if not matches_sender_filters(header_info, normalized_emails, normalized_names):
            continue

        matched_reports.append(
            {
                "sender_name": header_info["sender_name"],
                "sender_email": header_info["sender_email"],
                "subject": header_info["subject"],
                "date": item.get("date", ""),
                "body": item.get("body", ""),
            }
        )

    return (
        prepare_personal_reports(
            matched_reports,
            requested_mailbox=requested_mailbox,
            resolved_mailbox=resolved_mailbox,
            skip_signature=effective_skip_signature,
        ),
        [],
    )


def fetch_personal_reports(
    days: int = None,
    date_from: str = None,
    date_to: str = None,
    mailbox_name: Optional[str] = None,
    explicit_mailbox_folder: Optional[str] = None,
    subject_pattern: Optional[str] = None,
    sender_emails: Optional[Sequence[str]] = None,
    sender_names: Optional[Sequence[str]] = None,
    skip_signature: Optional[bool] = None,
) -> Tuple[List[Dict], List[str]]:
    """从邮箱获取个人历史周报并返回清洗后的记录。"""
    requested_mailbox = (mailbox_name or config.PERSONAL_MAILBOX or "sent").strip()
    explicit_mailbox_folder = (
        explicit_mailbox_folder
        if explicit_mailbox_folder is not None
        else config.PERSONAL_MAILBOX_FOLDER
    )
    compiled_pattern = compile_subject_pattern(subject_pattern or config.PERSONAL_SUBJECT_PATTERN)
    normalized_emails = normalize_sender_emails(sender_emails)
    normalized_names = normalize_sender_names(sender_names)
    effective_skip_signature = config.PERSONAL_SKIP_SIGNATURE if skip_signature is None else skip_signature

    since_date, before_date = build_date_window(
        days=days,
        date_from=date_from,
        date_to=date_to,
        default_days=config.PERSONAL_SEARCH_DAYS,
    )
    search_criteria = build_search_criteria(since_date, before_date)

    diagnostics: List[str] = []
    raw_reports: List[Dict] = []
    resolved_mailbox = requested_mailbox
    total_visible = 0
    oldest_visible_date = None
    mail = None

    try:
        print(f"正在连接邮箱服务器 {config.IMAP_SERVER}...")
        mail = create_imap_client()
        mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)

        resolved_mailbox, resolution_diagnostics = resolve_mailbox_name(
            mail,
            requested_mailbox=requested_mailbox,
            explicit_folder=explicit_mailbox_folder or "",
        )
        diagnostics.extend(resolution_diagnostics)
        total_visible = ensure_mailbox_selected(mail, resolved_mailbox)
        oldest_visible_date, _ = fetch_oldest_visible_date(mail)

        print(f"个人周报来源邮箱: {requested_mailbox} -> {resolved_mailbox}")
        print(f"搜索条件: {' '.join(search_criteria)}")

        email_ids = search_message_ids(mail, search_criteria)
        print(f"搜索窗口内找到 {len(email_ids)} 封邮件")

        for email_id in email_ids:
            try:
                header_info = fetch_header_info(mail, email_id)
                if not header_info:
                    continue

                if not matches_subject_pattern(header_info["subject"], compiled_pattern):
                    continue
                if not matches_sender_filters(header_info, normalized_emails, normalized_names):
                    continue

                raw_email = fetch_raw_message(mail, email_id)
                if not raw_email:
                    continue

                msg = email.message_from_bytes(raw_email)
                body = extract_email_body(msg)
                if not body:
                    continue

                raw_reports.append(
                    {
                        "sender_name": header_info["sender_name"],
                        "sender_email": header_info["sender_email"],
                        "subject": header_info["subject"],
                        "date": header_info["date"],
                        "body": body,
                    }
                )
            except (socket.timeout, TimeoutError, OSError) as exc:
                print(f"处理邮件时网络超时，跳过 {email_id!r}: {exc}")
                close_imap_client(mail)
                mail = create_imap_client()
                mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
                ensure_mailbox_selected(mail, resolved_mailbox)
                continue
            except Exception as exc:
                print(f"处理个人周报邮件时出错: {exc}")
                continue
    except imaplib.IMAP4.error as exc:
        print(f"IMAP 错误: {exc}")
        print("请检查邮箱账号、授权码是否正确")
    finally:
        close_imap_client(mail)

    diagnostic_message = build_imap_history_limit_diagnostic(
        requested_mailbox=requested_mailbox,
        requested_since=since_date,
        total_visible=total_visible,
        oldest_visible_date=oldest_visible_date,
    )
    if diagnostic_message:
        diagnostics.append(diagnostic_message)

    prepared_reports = prepare_personal_reports(
        raw_reports,
        requested_mailbox=requested_mailbox,
        resolved_mailbox=resolved_mailbox,
        skip_signature=effective_skip_signature,
    )
    return prepared_reports, diagnostics


def resolve_personal_section_key(section_key: str) -> str:
    """解析个人模式使用的标准区块键。"""
    normalized = normalize_section_key(section_key)
    if section_key and not normalized:
        raise ValueError(f"不支持的 section key: {section_key}")
    return normalized
