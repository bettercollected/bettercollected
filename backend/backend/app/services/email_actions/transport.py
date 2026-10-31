"""One plain-text mail through the instance's mail server (``MAIL_*``).

The server is the operator's own configuration (it may be an internal relay),
so the destination rules of ``safe_http`` do not apply to it; what is sent is
what this module builds from already-cleaned parts:

- a **plain text** message (no HTML part, no attachments);
- ``Subject`` is one line (the caller collapses it; a line break would raise
  here, never become a header), ``From`` is the instance's sender address with
  the instance's own display name, never a workspace's;
- every recipient is one plain address (the stdlib refuses a header value with
  a line break), all in ``To``; no ``Cc``, ``Bcc`` or ``Reply-To``;
- ``Auto-Submitted: auto-generated`` so auto-responders do not answer it.

A failure is one of our codes (never the server's text or an address):
``recipient_rejected`` and ``smtp_rejected`` are permanent, the rest retry.
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional, Protocol, Sequence

import aiosmtplib

from backend.config import settings

TIMEOUT_SECONDS = 20.0


class MailFailed(Exception):
    """``code``: one of our codes; ``permanent``: retrying cannot help."""

    def __init__(self, code: str, *, permanent: bool = False):
        super().__init__(code)
        self.code = code
        self.permanent = permanent


class MailTransport(Protocol):
    async def send(self, *, recipients: Sequence[str], subject: str, body: str) -> None:
        """Deliver one plain-text mail to ``recipients``; raise
        :class:`MailFailed` on failure."""
        ...


@dataclass(frozen=True)
class _Config:
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    sender: str
    sender_name: str
    starttls: bool
    ssl_tls: bool
    use_credentials: bool
    validate_certs: bool


def _config() -> _Config:
    mail = settings.mail_settings
    from backend.app.services.email_actions.templates import one_line

    return _Config(
        host=(mail.smtp_server or "").strip(),
        port=int(mail.smtp_port or 587),
        username=mail.user or None,
        password=mail.password or None,
        sender=(mail.sender or "").strip(),
        sender_name=one_line(settings.ORGANIZATION_NAME, 100) or "BetterCollected",
        starttls=bool(mail.starttls),
        ssl_tls=bool(mail.ssl_tls),
        use_credentials=bool(mail.use_credentials),
        validate_certs=bool(mail.validate_certs),
    )


def build_message(
    *, sender: str, sender_name: str, recipients: Sequence[str], subject: str, body: str
) -> EmailMessage:
    """The message. The standard library refuses a header value that holds a
    line break (``ValueError``), so a value that slipped past cleaning stops
    the mail instead of adding a header."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender))
    message["To"] = ", ".join(recipients)
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2] or None)
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body, subtype="plain", charset="utf-8")
    return message


def failure_of(error: BaseException) -> MailFailed:
    """Our code for what went wrong."""
    if isinstance(error, MailFailed):
        return error
    if isinstance(error, aiosmtplib.SMTPRecipientsRefused):
        return MailFailed("recipient_rejected", permanent=True)
    if isinstance(error, aiosmtplib.SMTPAuthenticationError):
        return MailFailed("smtp_auth")
    if isinstance(error, aiosmtplib.SMTPResponseException):
        if 500 <= int(error.code) < 600:
            return MailFailed("smtp_rejected", permanent=True)
        return MailFailed("smtp_busy")
    if isinstance(error, (asyncio.TimeoutError, aiosmtplib.SMTPTimeoutError)):
        return MailFailed("timeout")
    if isinstance(error, ssl.SSLError):
        return MailFailed("tls_error")
    if isinstance(error, (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, OSError)):
        return MailFailed("smtp_unavailable")
    if isinstance(error, ValueError):
        # a header value the standard library refused: never retried
        return MailFailed("invalid_message", permanent=True)
    return MailFailed("smtp_error")


class SmtpTransport:
    async def send(self, *, recipients: Sequence[str], subject: str, body: str) -> None:
        config = _config()
        if not config.host or not config.sender:
            raise MailFailed("mail_not_configured", permanent=True)
        try:
            message = build_message(
                sender=config.sender,
                sender_name=config.sender_name,
                recipients=recipients,
                subject=subject,
                body=body,
            )
            await aiosmtplib.send(
                message,
                sender=config.sender,
                recipients=list(recipients),
                hostname=config.host,
                port=config.port,
                username=config.username if config.use_credentials else None,
                password=config.password if config.use_credentials else None,
                start_tls=config.starttls and not config.ssl_tls,
                use_tls=config.ssl_tls,
                validate_certs=config.validate_certs,
                timeout=TIMEOUT_SECONDS,
            )
        except MailFailed:
            raise
        except Exception as error:  # noqa: BLE001 - one of our codes, never the text
            raise failure_of(error) from None
