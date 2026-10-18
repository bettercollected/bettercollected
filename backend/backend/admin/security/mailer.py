"""Fixed plain-text mails of the admin sign-in.

Subjects are constants; nothing a user typed reaches a subject, and values put
in a body (addresses, account names) are reduced to one escaped line first.
Sending never raises: a failure is logged without recipient or code, and the
send methods answer whether the mail went out.

Settings use the same ``MAIL_*`` environment names as the rest of the
platform (``MAIL_USER``, ``MAIL_PASSWORD``, ``MAIL_SMTP_SERVER``,
``MAIL_SMTP_PORT``, ``MAIL_SENDER``, ``MAIL_STARTTLS``, ``MAIL_SSL_TLS``,
``MAIL_USE_CREDENTIALS``, ``MAIL_VALIDATE_CERTS``).
"""

import html
import logging
import os
import re
from dataclasses import dataclass
from typing import List, Mapping, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)

SUBJECT_SIGN_IN_CODE = "Your admin sign-in code"
SUBJECT_ENROLMENT = "Security notice: a second factor was set up for an admin account"
SUBJECT_RECOVERY_USE = "Security notice: a recovery code was used"
SUBJECT_LOCKOUT = "Security notice: admin sign-in was locked"

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")
MAX_VALUE = 120


def clean(value: object) -> str:
    """One short escaped line: control characters and line breaks collapse to
    a space, length is capped, ``<>&"'`` are HTML-escaped."""
    text = " ".join(_CONTROL.sub(" ", str(value)).split())
    if len(text) > MAX_VALUE:
        text = text[: MAX_VALUE - 1] + "…"
    return html.escape(text, quote=True)


@dataclass(frozen=True)
class Message:
    subject: str
    body: str


def sign_in_code_message(code: str, ip: str, ttl_minutes: int = 10) -> Message:
    body = (
        f"Your admin sign-in code is: {clean(code)}\n\n"
        f"It is valid for {int(ttl_minutes)} minutes and works once.\n"
        f"The request came from the address {clean(ip)}.\n\n"
        "Not you? Ignore this message; nobody can sign in without the code.\n"
    )
    return Message(SUBJECT_SIGN_IN_CODE, body)


def enrolment_message(account: str, ip: str) -> Message:
    body = (
        f"A second factor was set up for the admin account {clean(account)}.\n"
        f"It was done from the address {clean(ip)}.\n\n"
        "If this was not expected, review the admin audit log and remove the "
        "account's access.\n"
    )
    return Message(SUBJECT_ENROLMENT, body)


def recovery_use_message(account: str, ip: str, remaining: int) -> Message:
    body = (
        f"A recovery code was used to sign in to the admin account {clean(account)}.\n"
        f"It was used from the address {clean(ip)}.\n"
        f"Recovery codes left: {int(remaining)}.\n\n"
        "If this was not expected, review the admin audit log.\n"
    )
    return Message(SUBJECT_RECOVERY_USE, body)


def lockout_message(account: str, ip: str, minutes: int) -> Message:
    body = (
        f"Admin sign-in for {clean(account)} was locked for {int(minutes)} minutes "
        "after repeated wrong codes.\n"
        f"The last attempt came from the address {clean(ip)}.\n\n"
        "If this was not you, someone may be guessing codes.\n"
    )
    return Message(SUBJECT_LOCKOUT, body)


class MailTransport(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None:
        """Deliver one plain-text mail; raise on failure."""
        ...


@dataclass(frozen=True)
class MailConfig:
    user: str = ""
    password: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    sender: str = ""
    sender_name: str = "BetterCollected Admin"
    starttls: bool = True
    ssl_tls: bool = False
    use_credentials: bool = True
    validate_certs: bool = True

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "MailConfig":
        source = os.environ if env is None else env

        def flag(name: str, default: bool) -> bool:
            raw = source.get(name)
            if raw is None or raw == "":
                return default
            return raw.strip().lower() in ("1", "true", "yes", "on")

        port = source.get("MAIL_SMTP_PORT", "")
        return cls(
            user=source.get("MAIL_USER", ""),
            password=source.get("MAIL_PASSWORD", ""),
            smtp_server=source.get("MAIL_SMTP_SERVER", ""),
            smtp_port=int(port) if port.strip().isdigit() else 587,
            sender=source.get("MAIL_SENDER", ""),
            starttls=flag("MAIL_STARTTLS", True),
            ssl_tls=flag("MAIL_SSL_TLS", False),
            use_credentials=flag("MAIL_USE_CREDENTIALS", True),
            validate_certs=flag("MAIL_VALIDATE_CERTS", True),
        )

    @property
    def configured(self) -> bool:
        return bool(self.smtp_server and self.sender)


class FastMailTransport:
    """SMTP delivery through fastapi-mail."""

    def __init__(self, config: MailConfig) -> None:
        from fastapi_mail import ConnectionConfig, FastMail

        self._config = config
        self._client = FastMail(
            ConnectionConfig(
                MAIL_USERNAME=config.user,
                MAIL_PASSWORD=config.password,
                MAIL_PORT=config.smtp_port,
                MAIL_SERVER=config.smtp_server,
                MAIL_FROM=config.sender,
                MAIL_FROM_NAME=config.sender_name,
                MAIL_STARTTLS=config.starttls,
                MAIL_SSL_TLS=config.ssl_tls,
                USE_CREDENTIALS=config.use_credentials,
                VALIDATE_CERTS=config.validate_certs,
            )
        )

    async def send(self, to: str, subject: str, body: str) -> None:
        from fastapi_mail import MessageSchema, MessageType

        message = MessageSchema(
            subject=subject,
            recipients=[to],
            body=body,
            subtype=MessageType.plain,
        )
        await self._client.send_message(message)


class FakeTransport:
    """Records mails instead of sending them; ``fail`` makes sends raise."""

    def __init__(self, fail: bool = False) -> None:
        self.sent: List[Message] = []
        self.recipients: List[str] = []
        self.fail = fail

    async def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise ConnectionError("simulated delivery failure")
        self.recipients.append(to)
        self.sent.append(Message(subject, body))


class AdminMailer:
    def __init__(self, transport: MailTransport) -> None:
        self._transport = transport

    async def _deliver(self, to: str, message: Message) -> bool:
        try:
            await self._transport.send(to, message.subject, message.body)
            return True
        except Exception as exc:  # fire-and-forget: never reaches the caller
            # type only: the message of a mail error can carry the address
            logger.warning("admin mail not sent (%s)", type(exc).__name__)
            return False

    async def send_sign_in_code(self, to: str, code: str, ip: str) -> bool:
        return await self._deliver(to, sign_in_code_message(code, ip))

    async def _notify(self, admins: Sequence[str], message: Message) -> int:
        sent = 0
        for address in admins:
            if await self._deliver(address, message):
                sent += 1
        return sent

    async def notify_enrolment(
        self, admins: Sequence[str], account: str, ip: str
    ) -> int:
        """Mail every admin; returns how many mails went out."""
        return await self._notify(admins, enrolment_message(account, ip))

    async def notify_recovery_use(
        self, admins: Sequence[str], account: str, ip: str, remaining: int
    ) -> int:
        return await self._notify(admins, recovery_use_message(account, ip, remaining))

    async def notify_lockout(
        self, admins: Sequence[str], account: str, ip: str, minutes: int
    ) -> int:
        return await self._notify(admins, lockout_message(account, ip, minutes))
