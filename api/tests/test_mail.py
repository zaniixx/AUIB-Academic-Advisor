"""Sign-in codes go out by SMTP with TLS; the message holds the code and says how long it lasts."""

from email.message import EmailMessage
from typing import Any, ClassVar

import pytest

from app.services import mail
from app.settings import Settings


class FakeSMTP:
    sent: ClassVar[list[EmailMessage]] = []
    calls: ClassVar[list[str]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.calls.append(f"connect {host}:{port}")

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_: Any) -> None:
        self.calls.append("quit")

    def starttls(self, context: Any) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login {user}")

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


def test_a_code_is_sent_over_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.sent, FakeSMTP.calls = [], []
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    settings = Settings(  # type: ignore[call-arg]
        mail_mode="smtp",
        smtp_host="smtp.example.com",
        smtp_username="advisor",
        smtp_password="secret",
        smtp_from="AUIB Academic Advisor <advisor@auib.edu.iq>",
    )
    mail.send_sign_in_code(settings, "student@auib.edu.iq", "482913")
    assert FakeSMTP.calls == ["connect smtp.example.com:587", "starttls", "login advisor", "quit"]
    message = FakeSMTP.sent[0]
    assert message["To"] == "student@auib.edu.iq"
    assert message["Subject"] == "Your AUIB Academic Advisor sign-in code"
    body = message.get_body(("plain",))
    assert body is not None and "482913" in body.get_content() and "10 minutes" in body.get_content()


def test_a_mail_server_failure_is_reported_without_the_code(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def refuse(*_: Any, **__: Any) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(mail.smtplib, "SMTP", refuse)
    settings = Settings(mail_mode="smtp", smtp_host="smtp.example.com", smtp_from="a@auib.edu.iq")  # type: ignore[call-arg]
    with pytest.raises(mail.MailError):
        mail.send_sign_in_code(settings, "student@auib.edu.iq", "482913")
    assert "482913" not in caplog.text
