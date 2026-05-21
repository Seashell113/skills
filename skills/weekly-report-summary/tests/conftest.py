from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
SKILL_MODULES = [
    "config",
    "content_parser",
    "email_fetcher",
    "personal_report_fetcher",
    "md_exporter",
    "docx_filler",
    "main",
]

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def load_modules(tmp_path, monkeypatch):
    def _load(*module_names, extra_env=None):
        monkeypatch.setenv("GANCAO_SKILLS_HOME", str(tmp_path / "runtime"))
        monkeypatch.delenv("EMAIL_ADDRESS", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        monkeypatch.delenv("PERSONAL_SENDER_EMAILS", raising=False)
        monkeypatch.delenv("PERSONAL_SENDER_NAMES", raising=False)

        if extra_env:
            for key, value in extra_env.items():
                if value is None:
                    monkeypatch.delenv(key, raising=False)
                else:
                    monkeypatch.setenv(key, str(value))

        for name in SKILL_MODULES:
            sys.modules.pop(name, None)

        targets = module_names or tuple(SKILL_MODULES)
        loaded = {}
        for name in targets:
            loaded[name] = importlib.import_module(name)
        return loaded

    return _load
