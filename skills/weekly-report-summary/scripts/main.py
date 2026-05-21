#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周报 skill 双模式 CLI。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional, Sequence

import config
from content_parser import PERSONAL_SECTION_KEYS, get_section_label
from email_fetcher import close_imap_client, create_imap_client, ensure_mailbox_selected, list_mailboxes
from md_exporter import export_to_markdown
from personal_report_fetcher import (
    fetch_personal_reports,
    load_personal_reports_from_json,
    resolve_personal_section_key,
)


def validate_email_config() -> List[str]:
    """验证邮箱配置是否完整。"""
    errors = []

    if config.is_placeholder_email(config.EMAIL_ADDRESS):
        errors.append("请配置邮箱地址 EMAIL_ADDRESS")

    if config.is_placeholder_password(config.EMAIL_PASSWORD):
        errors.append("请配置邮箱授权码 EMAIL_PASSWORD")

    return errors


def validate_team_config() -> List[str]:
    """验证团队模式配置。"""
    errors = validate_email_config()

    if not os.path.exists(config.TEMPLATE_PATH):
        errors.append(f"模板文件不存在: {config.TEMPLATE_PATH}")

    return errors


def _print_config_errors(errors: Sequence[str]) -> None:
    print("配置错误:")
    for err in errors:
        print(f"  - {err}")
    print(f"\n请修改配置文件 {config.CONFIG_PATH} 或设置环境变量后重试")


def print_runtime_paths() -> None:
    """打印运行时目录信息。"""
    print("运行时目录:")
    print(f"  skills home: {config.SKILLS_HOME}")
    print(f"  skill home: {config.SKILL_HOME}")
    print(f"  config path: {config.CONFIG_PATH}")
    print(f"  output dir: {config.OUTPUT_DIR}")
    print(f"  default team output: {config.OUTPUT_PATH}")
    print(f"  default personal output: {config.PERSONAL_OUTPUT_PATH}")
    print(f"  template path: {config.TEMPLATE_PATH}")
    print("个人模式默认值:")
    print(f"  mailbox: {config.PERSONAL_MAILBOX}")
    print(f"  mailbox folder override: {config.PERSONAL_MAILBOX_FOLDER or '(auto resolve by alias)'}")
    print(f"  subject pattern: {config.PERSONAL_SUBJECT_PATTERN}")
    print(f"  sender emails: {config.PERSONAL_SENDER_EMAILS or '[]'}")
    print(f"  sender names: {config.PERSONAL_SENDER_NAMES or '[]'}")
    print(f"  section key: {config.PERSONAL_SECTION_KEY or '(not set)'}")


def resolve_section_key(section_key: Optional[str], section_only: bool) -> str:
    """解析 section-only 模式使用的标准区块键。"""
    effective_key = (section_key or config.PERSONAL_SECTION_KEY or "").strip()
    normalized_key = resolve_personal_section_key(effective_key)
    if section_only and not normalized_key:
        raise ValueError(
            "section-only 模式需要提供有效的 section key，可选值为: "
            + ", ".join(PERSONAL_SECTION_KEYS)
        )
    return normalized_key


def run_from_email(
    days: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    output_path: Optional[str] = None,
    use_simple_format: bool = False,
) -> Optional[str]:
    """从邮箱获取团队周报并生成汇总 Word。"""
    errors = validate_team_config()
    if errors:
        _print_config_errors(errors)
        return None

    from content_parser import group_reports_by_team, organize_reports_by_name
    from docx_filler import create_simple_report, fill_template_by_replacement
    from email_fetcher import fetch_weekly_reports

    print("=" * 50)
    print("周报自动汇总工具")
    print("=" * 50)

    print("\n[1/3] 正在获取周报邮件...")
    reports = fetch_weekly_reports(
        days=days,
        date_from=date_from,
        date_to=date_to,
    )

    if not reports:
        print("未找到周报邮件，请检查搜索条件")
        return None

    print("\n[2/3] 正在解析周报内容...")
    organized = organize_reports_by_name(reports)

    print(f"共解析 {len(organized)} 人的周报:")
    grouped = group_reports_by_team(organized)
    for group, members in grouped.items():
        if members:
            print(f"  {group}: {', '.join(members.keys())}")

    print("\n[3/3] 正在生成汇总文档...")
    if use_simple_format:
        week_info = f"周报汇总 - {datetime.now().strftime('%Y年%m月%d日')}"
        output = create_simple_report(
            organized,
            output_path=output_path,
            week_info=week_info,
        )
    else:
        output = fill_template_by_replacement(
            organized,
            output_path=output_path,
        )

    print("\n" + "=" * 50)
    print("汇总完成!")
    print(f"输出文件: {output}")
    print("=" * 50)
    return output


def run_from_json(json_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """从本地 JSON 数据生成团队周报汇总 Word。"""
    import json

    if not os.path.exists(json_path):
        print(f"JSON 文件不存在: {json_path}")
        return None

    from docx_filler import fill_template_by_replacement

    with open(json_path, "r", encoding="utf-8") as file:
        organized = json.load(file)

    print(f"从 JSON 加载了 {len(organized)} 人的周报")
    output = fill_template_by_replacement(
        organized,
        output_path=output_path,
    )
    print(f"汇总文档已生成: {output}")
    return output


def run_personal_from_email(
    days: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    mailbox_name: Optional[str] = None,
    subject_pattern: Optional[str] = None,
    section_key: Optional[str] = None,
    section_only: bool = False,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """从邮箱提取个人历史周报并导出 Markdown。"""
    errors = validate_email_config()
    if errors:
        _print_config_errors(errors)
        return None

    effective_section_key = resolve_section_key(section_key, section_only)

    print("=" * 50)
    print("个人历史周报提取")
    print("=" * 50)

    reports, diagnostics = fetch_personal_reports(
        days=days,
        date_from=date_from,
        date_to=date_to,
        mailbox_name=mailbox_name,
        subject_pattern=subject_pattern,
    )

    for message in diagnostics:
        print("\n" + message)

    if not reports:
        print("未找到符合条件的个人周报邮件，请检查邮箱目录、主题正则和日期范围。")
        return None

    print(f"\n共匹配到 {len(reports)} 封个人周报邮件")
    output = export_to_markdown(
        reports,
        output_path=output_path,
        section_only=section_only,
        section_key=effective_section_key,
    )

    print("\n" + "=" * 50)
    print("个人周报导出完成!")
    if section_only:
        print(f"导出区块: {get_section_label(effective_section_key)}")
    print(f"输出文件: {output}")
    print("=" * 50)
    return output


def run_personal_from_json(
    json_path: str,
    section_key: Optional[str] = None,
    section_only: bool = False,
    output_path: Optional[str] = None,
    subject_pattern: Optional[str] = None,
) -> Optional[str]:
    """从本地 fixture 导出个人历史周报 Markdown。"""
    effective_section_key = resolve_section_key(section_key, section_only)
    reports, diagnostics = load_personal_reports_from_json(
        json_path,
        subject_pattern=subject_pattern,
    )

    for message in diagnostics:
        print("\n" + message)

    if not reports:
        print("本地 fixture 中未找到符合条件的个人周报记录。")
        return None

    output = export_to_markdown(
        reports,
        output_path=output_path,
        section_only=section_only,
        section_key=effective_section_key,
    )
    print(f"个人周报 Markdown 已生成: {output}")
    return output


def test_email_connection() -> int:
    """测试邮箱连接。"""
    import imaplib

    print("测试邮箱连接...")
    print(f"服务器: {config.IMAP_SERVER}:{config.IMAP_PORT}")
    print(f"账号: {config.EMAIL_ADDRESS}")
    print(f"超时: {config.IMAP_TIMEOUT_SECONDS} 秒")
    mail = None

    try:
        mail = create_imap_client()
        mail.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        print("✓ 登录成功!")

        folders = list_mailboxes(mail)
        if folders:
            print("\n可用文件夹:")
            for folder in folders[:10]:
                print(f"  {folder}")

        total = ensure_mailbox_selected(mail, config.MAILBOX_FOLDER)
        print(f"\n{config.MAILBOX_FOLDER} 共有 {total} 封邮件")
        print("\n✓ 连接测试完成")
        return 0
    except imaplib.IMAP4.error as exc:
        print(f"✗ IMAP 错误: {exc}")
        return 1
    except Exception as exc:
        print(f"✗ 连接失败: {exc}")
        return 1
    finally:
        close_imap_client(mail)


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数。"""
    parser = argparse.ArgumentParser(
        description="周报自动汇总工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取最近7天的团队周报
  python scripts/main.py

  # 指定日期范围生成团队汇总
  python scripts/main.py --from 2026-01-13 --to 2026-01-19

  # 从本地 JSON 生成团队汇总
  python scripts/main.py --json evals/fixtures/sample_reports.json

  # 提取个人历史周报并导出 Markdown
  python scripts/main.py --personal --from 2026-01-01 --to 2026-04-01

  # 个人模式只导出本周完成工作区块
  python scripts/main.py --personal --section-only --section-key this_week_work

  # 用本地 fixture 回归个人模式
  python scripts/main.py --personal-json evals/fixtures/personal_reports.json
        """,
    )

    parser.add_argument(
        "--days",
        "-d",
        type=int,
        help="搜索最近 N 天的邮件",
    )
    parser.add_argument(
        "--from",
        "-f",
        dest="date_from",
        help="开始日期（格式：YYYY-MM-DD）",
    )
    parser.add_argument(
        "--to",
        "-t",
        dest="date_to",
        help="结束日期（格式：YYYY-MM-DD）",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出文件路径",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="测试邮箱连接",
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="打印配置文件、输出目录和模板路径",
    )
    parser.add_argument(
        "--json",
        "-j",
        help="从 JSON 文件读取团队周报数据",
    )
    parser.add_argument(
        "--simple",
        "-s",
        action="store_true",
        help="使用简单格式输出团队汇总（不依赖模板）",
    )
    parser.add_argument(
        "--personal",
        action="store_true",
        help="进入个人历史周报提取模式",
    )
    parser.add_argument(
        "--personal-mailbox",
        default=None,
        help="个人模式来源邮箱，可用 sent / inbox / 原始文件夹名",
    )
    parser.add_argument(
        "--subject-pattern",
        default=None,
        help="个人模式主题正则匹配模式",
    )
    parser.add_argument(
        "--section-key",
        choices=PERSONAL_SECTION_KEYS,
        default=None,
        help="个人模式使用的标准区块键",
    )
    parser.add_argument(
        "--section-only",
        action="store_true",
        help="个人模式只导出指定标准区块",
    )
    parser.add_argument(
        "--personal-json",
        default=None,
        help="从本地 JSON fixture 读取个人周报原始邮件数据",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    personal_mode = args.personal or bool(args.personal_json)

    if args.json and personal_mode:
        parser.error("--json 不能和个人模式同时使用")

    if args.section_only and not personal_mode:
        parser.error("--section-only 仅支持个人模式")

    if args.personal_mailbox and not personal_mode:
        parser.error("--personal-mailbox 仅支持个人模式")

    if args.subject_pattern and not personal_mode:
        parser.error("--subject-pattern 仅支持个人模式")

    if args.section_key and not personal_mode:
        parser.error("--section-key 仅支持个人模式")

    if args.print_paths:
        print_runtime_paths()
        return 0

    if args.test:
        return test_email_connection()

    try:
        if args.personal_json:
            output = run_personal_from_json(
                args.personal_json,
                section_key=args.section_key,
                section_only=args.section_only,
                output_path=args.output,
                subject_pattern=args.subject_pattern,
            )
            return 0 if output else 1

        if personal_mode:
            output = run_personal_from_email(
                days=args.days,
                date_from=args.date_from,
                date_to=args.date_to,
                mailbox_name=args.personal_mailbox,
                subject_pattern=args.subject_pattern,
                section_key=args.section_key,
                section_only=args.section_only,
                output_path=args.output,
            )
            return 0 if output else 1

        if args.json:
            output = run_from_json(args.json, args.output)
            return 0 if output else 1

        output = run_from_email(
            days=args.days,
            date_from=args.date_from,
            date_to=args.date_to,
            output_path=args.output,
            use_simple_format=args.simple,
        )
        return 0 if output else 1
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
