from __future__ import annotations

import json
from pathlib import Path


def _sample_reports():
    return [
        {
            "sender_name": "木通-张丁力",
            "sender_email": "zhangdl@gancao.com",
            "subject": "3月第3周周报(2026.03.09-2026.03.15)",
            "date": "Mon, 16 Mar 2026 09:12:00 +0800",
            "body": (
                "本周完成工作\n"
                "1. 完成 A。\n"
                "2. 完成 B。\n\n"
                "下周工作计划\n"
                "1. 继续推进。\n\n"
                "本周得与失\n"
                "拆清双模式后扩展更稳。\n\n"
                "Best regards\n木通\nMob: 13800138000"
            ),
        },
        {
            "sender_name": "其他同学",
            "sender_email": "other@gancao.com",
            "subject": "运营周报同步",
            "date": "Mon, 10 Mar 2026 09:12:00 +0800",
            "body": "这不是要匹配的周报",
        },
    ]


def test_load_personal_reports_from_json_filters_and_parses(load_modules, tmp_path) -> None:
    modules = load_modules("config", "content_parser", "email_fetcher", "personal_report_fetcher")
    fetcher = modules["personal_report_fetcher"]

    fixture_path = tmp_path / "personal.json"
    fixture_path.write_text(
        json.dumps(_sample_reports(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    reports, diagnostics = fetcher.load_personal_reports_from_json(
        str(fixture_path),
        subject_pattern=r"周报",
        sender_emails=["zhangdl@gancao.com"],
    )

    assert diagnostics == []
    assert len(reports) == 1
    assert reports[0]["sender_email"] == "zhangdl@gancao.com"
    assert reports[0]["this_week_work"].startswith("1. 完成 A")
    assert "Best regards" not in reports[0]["this_week_work"]


def test_prepare_personal_reports_can_preserve_signature(load_modules) -> None:
    modules = load_modules("config", "content_parser", "email_fetcher", "personal_report_fetcher")
    fetcher = modules["personal_report_fetcher"]

    reports = fetcher.prepare_personal_reports(
        _sample_reports()[:1],
        requested_mailbox="sent",
        resolved_mailbox="&XfJT0ZAB-",
        skip_signature=False,
    )

    assert len(reports) == 1
    assert "Best regards" in reports[0]["gains_losses"]


def test_history_limit_diagnostic_for_long_sent_range(load_modules) -> None:
    modules = load_modules("config", "content_parser", "email_fetcher", "personal_report_fetcher")
    fetcher = modules["personal_report_fetcher"]

    message = fetcher.build_imap_history_limit_diagnostic(
        requested_mailbox="sent",
        requested_since=fetcher.datetime.now() - fetcher.timedelta(days=180),
        total_visible=20,
        oldest_visible_date=fetcher.datetime.now() - fetcher.timedelta(days=25),
    )

    assert message is not None
    assert "--personal-mailbox inbox" in message
