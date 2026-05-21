from __future__ import annotations


class FakeMail:
    def list(self):
        return (
            "OK",
            [
                b'(\\HasNoChildren) "/" INBOX',
                b'(\\HasNoChildren) "/" "&XfJT0ZAB-"',
            ],
        )


def test_resolve_mailbox_alias_for_sent(load_modules) -> None:
    email_fetcher = load_modules("config", "email_fetcher")["email_fetcher"]

    resolved, diagnostics = email_fetcher.resolve_mailbox_name(FakeMail(), "sent")

    assert resolved == "&XfJT0ZAB-"
    assert diagnostics == []


def test_explicit_mailbox_folder_override_wins(load_modules) -> None:
    email_fetcher = load_modules("config", "email_fetcher")["email_fetcher"]

    resolved, diagnostics = email_fetcher.resolve_mailbox_name(
        FakeMail(),
        "sent",
        explicit_folder="Archive/Sent",
    )

    assert resolved == "Archive/Sent"
    assert diagnostics == []
