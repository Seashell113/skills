from __future__ import annotations


def _reports():
    return [
        {
            "subject": "较早的一周",
            "sender_name": "木通",
            "sender_email": "zhangdl@gancao.com",
            "resolved_mailbox": "&XfJT0ZAB-",
            "date": "Mon, 02 Mar 2026 08:35:00 +0800",
            "parsed_date": "2026-03-02T08:35:00",
            "this_week_work": "1. 完成旧任务",
            "next_week_plan": "",
            "gains_losses": "",
            "praise": "",
        },
        {
            "subject": "较新的一周",
            "sender_name": "木通",
            "sender_email": "zhangdl@gancao.com",
            "resolved_mailbox": "&XfJT0ZAB-",
            "date": "Mon, 16 Mar 2026 09:12:00 +0800",
            "parsed_date": "2026-03-16T09:12:00",
            "this_week_work": "1. 完成新任务",
            "next_week_plan": "1. 继续推进",
            "gains_losses": "",
            "praise": "",
        },
    ]


def test_export_to_markdown_writes_single_archive(load_modules, tmp_path) -> None:
    exporter = load_modules("config", "content_parser", "md_exporter")["md_exporter"]

    output_path = tmp_path / "personal.md"
    result = exporter.export_to_markdown(_reports(), output_path=str(output_path))

    content = output_path.read_text(encoding="utf-8")
    assert result == str(output_path)
    assert content.index("## 较新的一周") < content.index("## 较早的一周")
    assert "### 本周完成工作" in content
    assert "### 下周工作计划" in content
    assert "- 来源邮箱: 已发送" in content
    assert "- 邮箱目录: 已发送" in content


def test_export_to_markdown_supports_section_only(load_modules, tmp_path) -> None:
    exporter = load_modules("config", "content_parser", "md_exporter")["md_exporter"]

    output_path = tmp_path / "section-only.md"
    exporter.export_to_markdown(
        _reports(),
        output_path=str(output_path),
        section_only=True,
        section_key="this_week_work",
    )

    content = output_path.read_text(encoding="utf-8")
    assert "### 本周完成工作" in content
    assert "### 下周工作计划" not in content
