"""Sending sign-in codes by email (F9.1).

``ADVISOR_MAIL_MODE=smtp`` sends through any SMTP server: AUIB's own mail server, or a service such
as Mailgun, Postmark, SendGrid or Brevo. ``log`` writes the code to the API log instead, so
development and tests need no mail server; the settings refuse it in production.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from app.settings import Settings

log = logging.getLogger("app.mail")
TIMEOUT_SECONDS = 15


class MailError(Exception):
    """The code could not be handed to the mail server."""


def send_sign_in_code(settings: Settings, to: str, code: str) -> None:
    minutes = settings.login_code_minutes
    if settings.mail_mode == "log":
        log.warning("Sign-in code for %s: %s (ADVISOR_MAIL_MODE=log, for development only)", to, code)
        return
    message = EmailMessage()
    message["Subject"] = "Your AUIB Academic Advisor sign-in code"
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Message-ID"] = make_msgid(domain=settings.smtp_from.rsplit("@", 1)[-1].strip("> ") or None)
    message.set_content(
        f"Your sign-in code is {code}.\n\n"
        f"It works once and expires in {minutes} minutes. If you did not ask for it, you can ignore this "
        "email: nobody can sign in without the code.\n\n"
        "AUIB Academic Advisor\n"
    )
    message.add_alternative(
        "<p>Your sign-in code is</p>"
        f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px;font-family:monospace">{code}</p>'
        f"<p>It works once and expires in {minutes} minutes. If you did not ask for it, you can ignore "
        "this email: nobody can sign in without the code.</p><p>AUIB Academic Advisor</p>",
        subtype="html",
    )
    try:
        context = ssl.create_default_context()
        if settings.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS, context=context
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS)
        with server:
            if settings.smtp_security == "starttls":
                server.starttls(context=context)
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        # The error names the server's complaint, never the code.
        log.error("Could not send a sign-in code: %s", type(error).__name__)
        raise MailError from error
