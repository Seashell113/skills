# -*- coding: utf-8 -*-
"""
邮件抓取模块。

从阿里邮箱通过 IMAP 协议获取周报邮件，并提供个人模式需要的通用邮箱 helper。
"""

from __future__ import annotations

import email
import html
import imaplib
import re
import socket
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple

import config


def create_imap_client() -> imaplib.IMAP4:
    """创建带超时控制的 IMAP 客户端。"""
    timeout = max(1, int(config.IMAP_TIMEOUT_SECONDS))
    if config.IMAP_USE_SSL:
        return imaplib.IMAP4_SSL(
            config.IMAP_SERVER,
            config.IMAP_PORT,
            timeout=timeout,
        )
    return imaplib.IMAP4(
        config.IMAP_SERVER,
        config.IMAP_PORT,
        timeout=timeout,
    )


def close_imap_client(mail: Optional[imaplib.IMAP4]) -> None:
    """尽力关闭 IMAP 连接，避免尾部收口卡死主流程。"""
    if mail is None:
        return

    try:
        mail.close()
    except (imaplib.IMAP4.error, OSError, socket.timeout):
        pass

    try:
        mail.logout()
    except (imaplib.IMAP4.error, OSError, socket.timeout):
        pass


def _normalize_mailbox_token(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().strip('"')).lower()


def decode_mailbox_name(entry) -> str:
    """从 IMAP LIST 返回值中解析邮箱文件夹名。"""
    text = entry.decode(errors="ignore") if isinstance(entry, (bytes, bytearray)) else str(entry)
    quoted_match = re.search(r' "((?:[^"\\]|\\.)*)"$', text)
    if quoted_match:
        return quoted_match.group(1).replace('\\"', '"').strip()

    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        return parts[1].strip().strip('"')
    return text.strip().strip('"')


def list_mailboxes(mail: imaplib.IMAP4) -> List[str]:
    """列出当前账号可见的邮箱文件夹名。"""
    status, folders = mail.list()
    if status != "OK" or not folders:
        return []
    return [name for name in (decode_mailbox_name(item) for item in folders) if name]


def resolve_mailbox_name(
    mail: imaplib.IMAP4,
    requested_mailbox: str,
    explicit_folder: str = "",
    alias_map: Optional[Dict[str, Sequence[str]]] = None,
) -> Tuple[str, List[str]]:
    """根据 sent/inbox 别名解析实际邮箱文件夹名。"""
    diagnostics: List[str] = []

    if explicit_folder.strip():
        return explicit_folder.strip(), diagnostics

    requested = (requested_mailbox or "").strip()
    if not requested:
        return config.MAILBOX_FOLDER, diagnostics

    alias_map = alias_map or config.PERSONAL_MAILBOX_ALIASES
    candidates = [requested]
    candidates.extend(alias_map.get(requested.lower(), ()))

    available = list_mailboxes(mail)
    normalized_lookup = {_normalize_mailbox_token(name): name for name in available}

    for candidate in candidates:
        actual = normalized_lookup.get(_normalize_mailbox_token(candidate))
        if actual:
            return actual, diagnostics

    if requested.lower() in alias_map:
        diagnostics.append(
            f"未在邮箱列表中解析到 {requested} 的标准别名，将直接尝试使用 {requested}"
        )
    return requested, diagnostics


def ensure_mailbox_selected(mail: imaplib.IMAP4, mailbox_name: Optional[str] = None) -> int:
    """选择目标邮箱文件夹，失败时直接抛错。"""
    target = mailbox_name or config.MAILBOX_FOLDER
    status, data = mail.select(target)
    if status != "OK":
        raise RuntimeError(f"选择邮箱文件夹失败: {target}")

    try:
        return int(data[0]) if data and data[0] else 0
    except (TypeError, ValueError, IndexError):
        return 0


def reconnect_imap_client(mailbox_name: Optional[str] = None) -> imaplib.IMAP4:
    """重建 IMAP 会话并重新选择目标邮箱。"""
    mail = create_imap_client()
    mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
    ensure_mailbox_selected(mail, mailbox_name)
    return mail


def build_date_window(
    days: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    default_days: Optional[int] = None,
) -> Tuple[datetime, datetime]:
    """构建 IMAP 搜索使用的日期窗口。"""
    effective_days = default_days if default_days is not None else config.SEARCH_DAYS
    effective_days = days if days is not None else effective_days

    if date_from:
        since_date = datetime.strptime(date_from, "%Y-%m-%d")
    else:
        since_date = datetime.now() - timedelta(days=effective_days)

    if date_to:
        before_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    else:
        before_date = datetime.now() + timedelta(days=1)

    return since_date, before_date


def build_search_criteria(since_date: datetime, before_date: datetime) -> List[str]:
    """构建 IMAP 日期搜索条件。"""
    return [
        "SINCE",
        since_date.strftime("%d-%b-%Y"),
        "BEFORE",
        before_date.strftime("%d-%b-%Y"),
    ]


def search_message_ids(mail: imaplib.IMAP4, search_criteria: Sequence[str]) -> List[bytes]:
    """执行 IMAP 搜索并返回消息 ID 列表。"""
    status, messages = mail.search(None, *search_criteria)
    if status != "OK" or not messages or not messages[0]:
        return []
    return messages[0].split()


def extract_fetch_bytes(msg_data) -> bytes:
    """从 IMAP fetch 返回值中提取有效字节内容。"""
    if not msg_data:
        return b""

    for item in msg_data:
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])

    return b""


def decode_mime_header(header_value: str) -> str:
    """解码 MIME 邮件头。"""
    if not header_value:
        return ""

    decoded_parts = decode_header(header_value)
    result = []

    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                result.append(part.decode(charset))
            except (UnicodeDecodeError, LookupError):
                result.append(part.decode("utf-8", errors="ignore"))
        else:
            result.append(part)

    return "".join(result)


def extract_sender_name(from_header: str) -> str:
    """
    从 From 头中提取发件人显示名（花名）。

    格式可能是：
    - "张三 <zhangsan@company.com>"
    - "诃子-张三 <zhangsan@company.com>"
    - "<zhangsan@company.com>"
    """
    decoded = decode_mime_header(from_header)

    match = re.match(r'^"?([^"<]+)"?\s*<', decoded)
    if match:
        name = match.group(1).strip()
        if "-" in name:
            parts = name.split("-")
            return parts[0].strip()
        return name

    match = re.search(r"<([^@]+)@", decoded)
    if match:
        return match.group(1)

    return decoded


def extract_message_headers(raw_message: bytes) -> Dict[str, str]:
    """从原始邮件数据中提取主题、发件人和日期。"""
    msg = email.message_from_bytes(raw_message)
    subject = decode_mime_header(msg.get("Subject", ""))
    from_header = msg.get("From", "")
    decoded_from_header = decode_mime_header(from_header)
    date_header = msg.get("Date", "")
    sender_name = extract_sender_name(from_header)
    sender_email_match = re.search(r"<([^>]+)>", decoded_from_header)
    sender_email = sender_email_match.group(1) if sender_email_match else decoded_from_header

    return {
        "subject": subject,
        "from_header": decoded_from_header,
        "date": date_header,
        "sender_name": sender_name,
        "sender_email": sender_email.strip(),
    }


def fetch_header_info(mail: imaplib.IMAP4, email_id: bytes) -> Dict[str, str]:
    """获取指定邮件的主题、发件人和日期。"""
    status, header_data = mail.fetch(
        email_id,
        "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])",
    )
    if status != "OK":
        return {}

    raw_headers = extract_fetch_bytes(header_data)
    if not raw_headers:
        return {}

    return extract_message_headers(raw_headers)


def fetch_raw_message(mail: imaplib.IMAP4, email_id: bytes) -> bytes:
    """获取指定邮件的完整 RFC822 内容。"""
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    if status != "OK":
        return b""
    return extract_fetch_bytes(msg_data)


def parse_email_date(date_header: str) -> Optional[datetime]:
    """解析邮件日期头，转为无时区 datetime 便于比较和排序。"""
    if not date_header:
        return None
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError):
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed.replace(tzinfo=None)


def fetch_oldest_visible_date(mail: imaplib.IMAP4) -> Tuple[Optional[datetime], int]:
    """获取当前邮箱文件夹最早可见邮件日期和总可见数量。"""
    all_ids = search_message_ids(mail, ["ALL"])
    if not all_ids:
        return None, 0

    header_info = fetch_header_info(mail, all_ids[0])
    return parse_email_date(header_info.get("date", "")), len(all_ids)


class HTMLTextExtractor(HTMLParser):
    """HTML 文本提取器。"""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip_tags = {"script", "style", "head", "meta", "link"}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in ("br", "p", "div", "tr", "li"):
            self.result.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            text = data.strip()
            if text:
                self.result.append(text)

    def get_text(self) -> str:
        return " ".join(self.result)


def html_to_text(html_content: str) -> str:
    """将 HTML 内容转换为纯文本。"""
    try:
        parser = HTMLTextExtractor()
        parser.feed(html_content)
        text = parser.get_text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html_content)

    text = html.unescape(text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def extract_email_body(msg: Message) -> str:
    """提取邮件正文内容。"""
    body = ""

    if msg.is_multipart():
        text_parts = []
        html_parts = []

        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                charset = part.get_content_charset() or "utf-8"
                try:
                    decoded_payload = payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    decoded_payload = payload.decode("utf-8", errors="ignore")

                if content_type == "text/plain":
                    text_parts.append(decoded_payload)
                elif content_type == "text/html":
                    html_parts.append(decoded_payload)
            except Exception as exc:
                print(f"解析邮件部分时出错: {exc}")
                continue

        if text_parts:
            body = "\n".join(text_parts)
        elif html_parts:
            body = html_to_text("\n".join(html_parts))
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    body = payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    body = payload.decode("utf-8", errors="ignore")

                if content_type == "text/html":
                    body = html_to_text(body)
        except Exception as exc:
            print(f"解析邮件正文时出错: {exc}")

    return body.strip()


def fetch_weekly_reports(
    days: int = None,
    date_from: str = None,
    date_to: str = None,
    subject_keyword: str = None,
) -> List[Dict]:
    """
    从邮箱获取团队周报邮件。

    Returns:
        周报列表，每个元素包含：
        - sender_name: 发件人显示名（花名）
        - sender_email: 发件人邮箱
        - subject: 邮件主题
        - date: 邮件日期
        - body: 邮件正文
    """
    from content_parser import should_skip_email

    days = days if days is not None else config.SEARCH_DAYS
    subject_keyword = subject_keyword or config.SEARCH_SUBJECT_KEYWORD
    since_date, before_date = build_date_window(
        days=days,
        date_from=date_from,
        date_to=date_to,
        default_days=config.SEARCH_DAYS,
    )
    search_criteria = build_search_criteria(since_date, before_date)

    reports = []
    mailbox_name = config.MAILBOX_FOLDER
    mail = None

    try:
        print(f"正在连接邮箱服务器 {config.IMAP_SERVER}...")
        mail = reconnect_imap_client(mailbox_name)
        print("邮箱登录成功")
        print(f"搜索条件: {' '.join(search_criteria)}")

        email_ids = search_message_ids(mail, search_criteria)
        print(f"找到 {len(email_ids)} 封邮件")

        for email_id in email_ids:
            try:
                header_info = fetch_header_info(mail, email_id)
                if not header_info:
                    continue

                subject = header_info["subject"]
                sender_name = header_info["sender_name"]

                if subject_keyword and subject_keyword not in subject:
                    continue

                if should_skip_email(sender_name, subject):
                    continue

                raw_email = fetch_raw_message(mail, email_id)
                if not raw_email:
                    continue

                msg = email.message_from_bytes(raw_email)
                body = extract_email_body(msg)
                if not body:
                    print(f"警告: {sender_name} 的邮件正文为空")
                    continue

                report = {
                    "sender_name": sender_name,
                    "sender_email": header_info["sender_email"],
                    "subject": subject,
                    "date": header_info["date"],
                    "body": body,
                }
                reports.append(report)
                print(f"已获取: {sender_name} - {subject}")
            except (socket.timeout, TimeoutError, OSError) as exc:
                print(f"处理邮件时网络超时，跳过 {email_id!r}: {exc}")
                close_imap_client(mail)
                mail = reconnect_imap_client(mailbox_name)
                continue
            except Exception as exc:
                print(f"处理邮件时出错: {exc}")
                continue

        print(f"成功获取 {len(reports)} 封周报邮件")
    except imaplib.IMAP4.error as exc:
        print(f"IMAP 错误: {exc}")
        print("请检查邮箱账号、授权码是否正确")
    except Exception as exc:
        print(f"获取邮件时出错: {exc}")
    finally:
        close_imap_client(mail)

    return reports


def normalize_sender_name(sender_name: str) -> str:
    """
    规范化发件人名称，转换为模板中的花名。

    1. 首先检查别名映射
    2. 然后尝试匹配组成员列表
    """
    if sender_name in config.NAME_ALIAS_MAP:
        return config.NAME_ALIAS_MAP[sender_name]

    if sender_name in config.MEMBER_TO_GROUP:
        return sender_name

    for member in config.MEMBER_TO_GROUP.keys():
        if member in sender_name:
            return member

    return sender_name


if __name__ == "__main__":
    print("测试邮件抓取...")
    print(f"配置的邮箱: {config.EMAIL_ADDRESS}")
    print(f"搜索关键词: {config.SEARCH_SUBJECT_KEYWORD}")
    print(f"搜索天数: {config.SEARCH_DAYS}")
