from __future__ import annotations

import json
from pathlib import Path


def test_personal_defaults_derive_sender_email(load_modules) -> None:
    modules = load_modules("config")
    config = modules["config"]

    config_path = Path(config.CONFIG_PATH)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["email_address"] = "zhangdl@gancao.com"
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    config = load_modules("config")["config"]

    assert config.PERSONAL_MAILBOX == "sent"
    assert config.PERSONAL_SEARCH_DAYS == 365
    assert config.PERSONAL_SUBJECT_PATTERN == "周报"
    assert config.PERSONAL_SENDER_EMAILS == ["zhangdl@gancao.com"]


def test_personal_overrides_win_from_local_config(load_modules) -> None:
    modules = load_modules("config")
    config = modules["config"]

    config_path = Path(config.CONFIG_PATH)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "email_address": "zhangdl@gancao.com",
            "personal_mailbox": "inbox",
            "personal_mailbox_folder": "Archive/Sent",
            "personal_subject_pattern": "^\\d+月第\\d+周周报",
            "personal_sender_emails": ["alias@gancao.com"],
            "personal_sender_names": ["木通"],
            "personal_section_key": "this_week_work",
            "personal_skip_signature": False,
        }
    )
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    config = load_modules("config")["config"]

    assert config.PERSONAL_MAILBOX == "inbox"
    assert config.PERSONAL_MAILBOX_FOLDER == "Archive/Sent"
    assert config.PERSONAL_SUBJECT_PATTERN == "^\\d+月第\\d+周周报"
    assert config.PERSONAL_SENDER_EMAILS == ["zhangdl@gancao.com", "alias@gancao.com"]
    assert config.PERSONAL_SENDER_NAMES == ["木通"]
    assert config.PERSONAL_SECTION_KEY == "this_week_work"
    assert config.PERSONAL_SKIP_SIGNATURE is False
