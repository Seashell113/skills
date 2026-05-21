# -*- coding: utf-8 -*-
"""
周报汇总工具配置与运行时目录约定。

约定：
1. skill 安装目录只放只读资源（脚本、模板、共享默认值）
2. 用户本地 config.json 只存凭据和个性化 override
3. 用户配置、状态和输出全部放到安装目录外
4. 默认运行时根目录：
   - macOS/Linux: ~/.gancao-skills
   - Windows: %USERPROFILE%\\.gancao-skills
5. 可通过 GANCAO_SKILLS_HOME 覆盖整个运行时根目录
"""

from __future__ import annotations

import glob as _glob
import json
import os
from datetime import datetime
from typing import Iterable, List

SKILL_NAME = "weekly-report-summary"
DEFAULT_SKILLS_HOME_DIR = ".gancao-skills"
DEFAULT_EMAIL_PLACEHOLDER = "your_email@company.com"
DEFAULT_PASSWORD_PLACEHOLDER = "your_auth_code"
DEFAULT_PASSWORD_PLACEHOLDERS = {
    DEFAULT_PASSWORD_PLACEHOLDER,
    "your_authorization_code",
}


def _expand_path(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def _resolve_skills_home() -> str:
    override = os.getenv("GANCAO_SKILLS_HOME")
    if override:
        return _expand_path(override)
    return _expand_path(os.path.join("~", DEFAULT_SKILLS_HOME_DIR))


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _normalize_mapping(raw, fallback):
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    return dict(fallback)


def _normalize_group_members(raw, fallback):
    if not isinstance(raw, dict):
        return {group: list(members) for group, members in fallback.items()}

    normalized = {}
    for group, members in raw.items():
        if isinstance(members, list):
            normalized[str(group)] = [str(item) for item in members]
    return normalized or {group: list(members) for group, members in fallback.items()}


def _normalize_str_list(raw, fallback=None) -> List[str]:
    fallback = list(fallback or [])
    values = []

    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        values = raw.split(",")
    else:
        return fallback

    normalized = []
    for item in values:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized or fallback


def _merge_mapping(base, raw):
    merged = dict(base)
    merged.update(_normalize_mapping(raw, {}))
    return merged


def _merge_group_members(base, raw):
    merged = {group: list(members) for group, members in base.items()}
    merged.update(_normalize_group_members(raw, {}))
    return merged


def _merge_unique_str_list(*groups: Iterable[str]) -> List[str]:
    merged = []
    seen = set()

    for group in groups:
        for item in group:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)

    return merged


def _load_json_file(file_path: str):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_default_local_config():
    if os.path.exists(CONFIG_PATH):
        return
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(LOCAL_CONFIG_TEMPLATE, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _read_str_env(name: str, fallback: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else fallback


def _read_int_env(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _read_bool_env(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_list_env(name: str, fallback=None) -> List[str]:
    value = os.getenv(name)
    if value in (None, ""):
        return list(fallback or [])
    return _normalize_str_list(value, fallback)


def _read_str_config(key: str, fallback: str) -> str:
    value = _user_config.get(key)
    return str(value) if value not in (None, "") else fallback


def _read_int_config(key: str, fallback: int) -> int:
    value = _user_config.get(key)
    if value in (None, ""):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _read_bool_config(key: str, fallback: bool) -> bool:
    value = _user_config.get(key)
    if value in (None, ""):
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_list_config(key: str, fallback=None) -> List[str]:
    return _normalize_str_list(_user_config.get(key), fallback)


def _build_member_to_group(group_members):
    mapping = {}
    for group, members in group_members.items():
        for member in members:
            mapping[member] = group
    return mapping


def _derive_sender_emails(email_address: str) -> List[str]:
    if is_placeholder_email(email_address):
        return []
    return [email_address.strip()]


def is_placeholder_email(value: str) -> bool:
    return value.strip() == DEFAULT_EMAIL_PLACEHOLDER


def is_placeholder_password(value: str) -> bool:
    return value.strip() in DEFAULT_PASSWORD_PLACEHOLDERS


def build_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ====================
# skill 只读资源目录
# ====================
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _discover_default_template_path() -> str:
    candidates = [
        os.path.join(SKILL_DIR, "templates", "周报模版.docx"),
        os.path.join(SKILL_DIR, "assets", "周报模版.docx"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    glob_candidates = (
        _glob.glob(os.path.join(SKILL_DIR, "templates", "*.docx"))
        + _glob.glob(os.path.join(SKILL_DIR, "assets", "*.docx"))
        + _glob.glob(os.path.join(SKILL_DIR, "*.docx"))
    )
    return glob_candidates[0] if glob_candidates else ""


DEFAULT_TEMPLATE_PATH = _discover_default_template_path()

# ====================
# 运行时目录
# ====================
SKILLS_HOME = _resolve_skills_home()
SKILL_HOME = _ensure_dir(os.path.join(SKILLS_HOME, SKILL_NAME))
CONFIG_DIR = _ensure_dir(os.path.join(SKILL_HOME, "config"))
STATE_DIR = _ensure_dir(os.path.join(SKILL_HOME, "state"))
CACHE_DIR = _ensure_dir(os.path.join(SKILL_HOME, "cache"))
RUNS_DIR = _ensure_dir(os.path.join(SKILL_HOME, "runs"))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# ====================
# 默认配置
# ====================
TEAM_DEFAULT_NAME_ALIAS_MAP = {
    "lij@gancao.com": "麻黄",
    "张德检": "西瓜霜",
    "王飞翔": "升药",
}

TEAM_DEFAULT_GROUP_MEMBERS = {
    "管理层": ["诃子"],
    "web前端组": [
        "木通", "广木香", "黎豆", "空心柳", "樚木",
        "赤火绳", "青蛇子", "尖山橙", "水雍花", "秋枫",
    ],
    "移动端组": [
        "升药", "刺李", "夏天无", "二郎剑", "赤阳子",
        "倒挂草", "枇杷叶", "孔雀草", "欧李", "松节", "三石",
    ],
    "PHP后端组": [
        "西瓜霜", "麻黄", "蓝矾", "大蒜", "白河车",
        "炉甘石", "麦冬", "莨菪", "白马骨",
    ],
    "JAVA后端组": [
        "华山参", "绿豆", "薄雪草", "龙角草", "秦归",
        "鸟不宿", "不凋木", "左壳", "一点红", "壶卢",
        "天葵子", "九转香", "大阳关", "花蚁虫",
    ],
    "测试组": [
        "细辛", "番荔枝", "八月瓜", "蚕豆", "藜实",
        "照山白", "阿虞", "八步紧", "桑臣", "过山青",
        "金猫头", "地核桃", "南瓜",
    ],
    "运维支持组": [
        "红景天", "鸡蛋壳", "忽木", "法罗海", "半天钓",
    ],
    "数据": ["丹砂"],
}

DEFAULT_CONTENT_SECTIONS = [
    "本周完成工作",
    "下周工作计划",
    "本周得与失",
    "本周工作回顾",
    "其他收获与思考",
]

PERSONAL_MAILBOX_ALIASES = {
    "sent": (
        "Sent",
        "Sent Messages",
        "Sent Items",
        "Sent Mail",
        "已发送",
        "已发送邮件",
        "&XfJT0ZAB-",
    ),
    "inbox": (
        "INBOX",
        "Inbox",
        "收件箱",
    ),
}

SHARED_DEFAULT_CONFIG = {
    "imap_server": "imap.qiye.aliyun.com",
    "imap_port": 993,
    "imap_use_ssl": True,
    "imap_timeout_seconds": 30,
    "mailbox_folder": "INBOX",
    "search_subject_keyword": "周报",
    "search_days": 5,
    "template_path": DEFAULT_TEMPLATE_PATH,
    "output_dir": RUNS_DIR,
    "personal_search_days": 365,
    "personal_mailbox": "sent",
    "personal_mailbox_folder": "",
    "personal_subject_pattern": "周报",
    "personal_skip_signature": True,
    "personal_section_key": "",
}

LOCAL_CONFIG_TEMPLATE = {
    "email_address": DEFAULT_EMAIL_PLACEHOLDER,
    "email_password": DEFAULT_PASSWORD_PLACEHOLDER,
    "template_path": "",
    "output_dir": "",
    "name_alias_map": {},
    "group_members": {},
    "personal_search_days": "",
    "personal_mailbox": "",
    "personal_mailbox_folder": "",
    "personal_subject_pattern": "",
    "personal_sender_emails": [],
    "personal_sender_names": [],
    "personal_skip_signature": True,
    "personal_section_key": "",
}

_write_default_local_config()
_user_config = _load_json_file(CONFIG_PATH)

# ====================
# 阿里邮箱 IMAP 配置
# ====================
IMAP_SERVER = _read_str_env(
    "IMAP_SERVER",
    _read_str_config("imap_server", SHARED_DEFAULT_CONFIG["imap_server"]),
)
IMAP_PORT = _read_int_env(
    "IMAP_PORT",
    _read_int_config("imap_port", SHARED_DEFAULT_CONFIG["imap_port"]),
)
IMAP_USE_SSL = _read_bool_env(
    "IMAP_USE_SSL",
    _read_bool_config("imap_use_ssl", SHARED_DEFAULT_CONFIG["imap_use_ssl"]),
)
IMAP_TIMEOUT_SECONDS = _read_int_env(
    "IMAP_TIMEOUT_SECONDS",
    _read_int_config("imap_timeout_seconds", SHARED_DEFAULT_CONFIG["imap_timeout_seconds"]),
)

EMAIL_ADDRESS = _read_str_env(
    "EMAIL_ADDRESS",
    _read_str_config("email_address", DEFAULT_EMAIL_PLACEHOLDER),
)
EMAIL_PASSWORD = _read_str_env(
    "EMAIL_PASSWORD",
    _read_str_config("email_password", DEFAULT_PASSWORD_PLACEHOLDER),
)

# ====================
# 团队模式邮件搜索配置
# ====================
MAILBOX_FOLDER = _read_str_env(
    "MAILBOX_FOLDER",
    _read_str_config("mailbox_folder", SHARED_DEFAULT_CONFIG["mailbox_folder"]),
)
SEARCH_SUBJECT_KEYWORD = _read_str_env(
    "SEARCH_SUBJECT_KEYWORD",
    _read_str_config("search_subject_keyword", SHARED_DEFAULT_CONFIG["search_subject_keyword"]),
)
SEARCH_DAYS = _read_int_env(
    "SEARCH_DAYS",
    _read_int_config("search_days", SHARED_DEFAULT_CONFIG["search_days"]),
)

# ====================
# 个人模式邮件搜索配置
# ====================
PERSONAL_SEARCH_DAYS = _read_int_env(
    "PERSONAL_SEARCH_DAYS",
    _read_int_config("personal_search_days", SHARED_DEFAULT_CONFIG["personal_search_days"]),
)
PERSONAL_MAILBOX = _read_str_env(
    "PERSONAL_MAILBOX",
    _read_str_config("personal_mailbox", SHARED_DEFAULT_CONFIG["personal_mailbox"]),
).strip()
PERSONAL_MAILBOX_FOLDER = _read_str_env(
    "PERSONAL_MAILBOX_FOLDER",
    _read_str_config("personal_mailbox_folder", SHARED_DEFAULT_CONFIG["personal_mailbox_folder"]),
).strip()
PERSONAL_SUBJECT_PATTERN = _read_str_env(
    "PERSONAL_SUBJECT_PATTERN",
    _read_str_config("personal_subject_pattern", SHARED_DEFAULT_CONFIG["personal_subject_pattern"]),
).strip()
PERSONAL_SKIP_SIGNATURE = _read_bool_env(
    "PERSONAL_SKIP_SIGNATURE",
    _read_bool_config("personal_skip_signature", SHARED_DEFAULT_CONFIG["personal_skip_signature"]),
)
PERSONAL_SECTION_KEY = _read_str_env(
    "PERSONAL_SECTION_KEY",
    _read_str_config("personal_section_key", SHARED_DEFAULT_CONFIG["personal_section_key"]),
).strip()
PERSONAL_SENDER_EMAILS = _merge_unique_str_list(
    _derive_sender_emails(EMAIL_ADDRESS),
    _read_list_config("personal_sender_emails", []),
    _read_list_env("PERSONAL_SENDER_EMAILS", []),
)
PERSONAL_SENDER_NAMES = _merge_unique_str_list(
    _read_list_config("personal_sender_names", []),
    _read_list_env("PERSONAL_SENDER_NAMES", []),
)

# ====================
# 输出配置
# ====================
TEMPLATE_PATH = _expand_path(
    _read_str_env(
        "WEEKLY_REPORT_TEMPLATE_PATH",
        _read_str_config("template_path", SHARED_DEFAULT_CONFIG["template_path"]),
    )
)
OUTPUT_DIR = _ensure_dir(
    _expand_path(
        _read_str_env(
            "WEEKLY_REPORT_OUTPUT_DIR",
            _read_str_config("output_dir", SHARED_DEFAULT_CONFIG["output_dir"]),
        )
    )
)
OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    f"周报汇总_自动生成-{build_timestamp()}.docx",
)
PERSONAL_OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    f"个人周报归档_自动生成-{build_timestamp()}.md",
)

# ====================
# 发件人 → 模板花名 映射
# ====================
NAME_ALIAS_MAP = _merge_mapping(TEAM_DEFAULT_NAME_ALIAS_MAP, _user_config.get("name_alias_map"))

# ====================
# 组-成员映射（用于识别组别）
# ====================
GROUP_MEMBERS = _merge_group_members(TEAM_DEFAULT_GROUP_MEMBERS, _user_config.get("group_members"))
MEMBER_TO_GROUP = _build_member_to_group(GROUP_MEMBERS)

# ====================
# 内容提取规则
# ====================
CONTENT_SECTIONS = list(DEFAULT_CONTENT_SECTIONS)
