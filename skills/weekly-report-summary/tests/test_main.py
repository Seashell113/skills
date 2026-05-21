from __future__ import annotations


def test_main_routes_personal_json_mode(load_modules, monkeypatch) -> None:
    main = load_modules("config", "content_parser", "main")["main"]
    captured = {}

    def fake_run_personal_from_json(json_path, section_key, section_only, output_path, subject_pattern):
        captured["json_path"] = json_path
        captured["section_key"] = section_key
        captured["section_only"] = section_only
        captured["output_path"] = output_path
        captured["subject_pattern"] = subject_pattern
        return "/tmp/personal.md"

    monkeypatch.setattr(main, "run_personal_from_json", fake_run_personal_from_json)

    result = main.main(
        [
            "--personal-json",
            "evals/fixtures/personal_reports.json",
            "--section-only",
            "--section-key",
            "this_week_work",
            "--output",
            "/tmp/out.md",
        ]
    )

    assert result == 0
    assert captured["json_path"] == "evals/fixtures/personal_reports.json"
    assert captured["section_key"] == "this_week_work"
    assert captured["section_only"] is True
    assert captured["output_path"] == "/tmp/out.md"


def test_main_routes_team_default_without_regression(load_modules, monkeypatch) -> None:
    main = load_modules("config", "content_parser", "main")["main"]
    calls = {}

    def fake_run_from_email(days, date_from, date_to, output_path, use_simple_format):
        calls["days"] = days
        calls["date_from"] = date_from
        calls["date_to"] = date_to
        calls["output_path"] = output_path
        calls["use_simple_format"] = use_simple_format
        return "/tmp/team.docx"

    monkeypatch.setattr(main, "run_from_email", fake_run_from_email)

    result = main.main([])

    assert result == 0
    assert calls == {
        "days": None,
        "date_from": None,
        "date_to": None,
        "output_path": None,
        "use_simple_format": False,
    }
