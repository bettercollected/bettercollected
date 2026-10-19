"""Fixed plain-text mails of the admin sign-in.

Subjects are constants; nothing a user typed reaches a subject, and values put
in a body (addresses, account names) are reduced to one plain line first.
Sending never raises: a failure is logged without recipient or code, and the
send methods answer whether the mail went out.

Settings use the same ``MAIL_*`` environment names as the rest of the
platform (``MAIL_USER``, ``MAIL_PASSWORD``, ``MAIL_SMTP_SERVER``,
``MAIL_SMTP_PORT``, ``MAIL_SENDER``, ``MAIL_STARTTLS``, ``MAIL_SSL_TLS``,
``MAIL_USE_CREDENTIALS``, ``MAIL_VALIDATE_CERTS``).
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

logger = logging.getLogger(__name__)

SUBJECT_SIGN_IN_CODE = "Your admin sign-in code"
SUBJECT_ENROLMENT = "Security notice: a second factor was set up for an admin account"
SUBJECT_RECOVERY_USE = "Security notice: a recovery code was used"
SUBJECT_LOCKOUT = "Security notice: admin sign-in was locked"
SUBJECT_NEW_ADDRESS = "Security notice: admin sign-in from a new address"
SUBJECT_FACTOR_RESET = "Security notice: a second factor was reset by an operator"
SUBJECT_SETUP_STARTED = "Security notice: the first-run setup of the admin portal was started"
SUBJECT_SETUP_LOCKED = "Security notice: the first-run setup token was locked"
SUBJECT_SETUP_FINISHED = "Security notice: the first-run setup of the admin portal was finished"
SUBJECT_MAIL_TEST = "Test mail for the admin sign-in"

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")
MAX_VALUE = 120


def clean(value: object) -> str:
    """One short line of plain text: control characters and line breaks
    collapse to a space (no header or line injection), length is capped. The
    mails are plain text, so nothing is HTML-escaped."""
    text = " ".join(_CONTROL.sub(" ", str(value)).split())
    if len(text) > MAX_VALUE:
        text = text[: MAX_VALUE - 1] + "…"
    return text


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


def new_address_message(account: str, ip: str) -> Message:
    body = (
        f"The admin account {clean(account)} signed in from an address it has "
        f"not used recently: {clean(ip)}.\n\n"
        "If this was not expected, review the admin audit log and revoke the "
        "account's sessions.\n"
    )
    return Message(SUBJECT_NEW_ADDRESS, body)


def factor_reset_message(account: str) -> Message:
    body = (
        f"The second factor of the admin account {clean(account)} was removed "
        "with the operator command on the host.\n"
        "Its sessions were revoked; the account must set up a new second factor "
        "at its next sign-in.\n\n"
        "If this was not expected, review the admin audit log.\n"
    )
    return Message(SUBJECT_FACTOR_RESET, body)


def setup_started_message(account: str, ip: str) -> Message:
    body = (
        f"The first-run setup token of the admin portal was used for {clean(account)}.\n"
        f"It was used from the address {clean(ip)}.\n\n"
        "If this was not expected, review the admin audit log.\n"
    )
    return Message(SUBJECT_SETUP_STARTED, body)


def setup_locked_message(ip: str) -> Message:
    body = (
        "The first-run setup token was locked after too many wrong tries.\n"
        f"The last attempt came from the address {clean(ip)}.\n\n"
        "Someone may be guessing the token. Issue a new one on the host with the "
        "setup-token command when you are ready.\n"
    )
    return Message(SUBJECT_SETUP_LOCKED, body)


def setup_finished_message(account: str, ip: str) -> Message:
    body = (
        f"{clean(account)} finished the first-run setup of the admin portal.\n"
        f"It was done from the address {clean(ip)}.\n\n"
        "If this was not expected, review the admin audit log.\n"
    )
    return Message(SUBJECT_SETUP_FINISHED, body)


def mail_test_message(code: str) -> Message:
    body = (
        f"Your confirmation code is {clean(code)}\n\n"
        "Enter it in the admin setup to confirm that this mail server works. "
        "Nothing is saved until you do.\n"
    )
    return Message(SUBJECT_MAIL_TEST, body)


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


@runtime_checkable
class MailConfigProvider(Protocol):
    def get(self) -> MailConfig:
        """The mail settings to use for the next send."""
        ...


class EnvMailConfigProvider:
    """The default: ``MAIL_*`` environment variables, read on every call."""

    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        self._env = env

    def get(self) -> MailConfig:
        return MailConfig.from_env(self._env)


class StaticMailConfigProvider:
    def __init__(self, config: MailConfig) -> None:
        self._config = config

    def get(self) -> MailConfig:
        return self._config


def mail_config_from_settings(values: Mapping[str, object]) -> MailConfig:
    """A ``MailConfig`` from stored ``admin_mail`` settings (keys ``ADMIN_MAIL_*``);
    a missing key keeps the code default."""

    def get(name: str, default):
        value = values.get(f"ADMIN_MAIL_{name}")
        return default if value is None else value

    return MailConfig(
        user=str(get("USER", "")),
        password=str(get("PASSWORD", "")),
        smtp_server=str(get("SMTP_SERVER", "")),
        smtp_port=int(get("SMTP_PORT", 587)),
        sender=str(get("SENDER", "")),
        starttls=bool(get("STARTTLS", True)),
        ssl_tls=bool(get("SSL_TLS", False)),
        use_credentials=bool(get("USE_CREDENTIALS", True)),
        validate_certs=bool(get("VALIDATE_CERTS", True)),
    )


class LayeredMailConfigProvider:
    """The portal's own mail settings: an environment value wins (``ADMIN_MAIL_*``,
    then the platform's ``MAIL_*``), the saved ``admin_mail`` settings come next.

    ``stored`` is filled by the portal (at start, after the setup wizard saves,
    and by ``refresher`` at most once a minute); ``get`` itself never touches a
    database."""

    PREFIX = "ADMIN_MAIL_"

    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        self._env = env
        self.stored: Optional[MailConfig] = None

    def _environment(self) -> Tuple[MailConfig, MailConfig]:
        source = os.environ if self._env is None else self._env
        renamed = {
            "MAIL_" + key[len(self.PREFIX):]: value
            for key, value in source.items()
            if key.startswith(self.PREFIX)
        }
        return MailConfig.from_env(renamed), MailConfig.from_env(source)

    def get(self) -> MailConfig:
        admin_env, platform_env = self._environment()
        if admin_env.configured:
            return admin_env
        if platform_env.configured:
            return platform_env
        return self.stored or platform_env

    def source(self) -> str:
        """Where the settings in use come from: ``environment``, ``store`` or ``none``."""
        admin_env, platform_env = self._environment()
        if admin_env.configured or platform_env.configured:
            return "environment"
        return "store" if self.stored is not None and self.stored.configured else "none"


TransportFactory = Callable[[MailConfig], MailTransport]


class AdminMailer:
    """Sends the fixed mails. The settings come from a provider on every
    send, so a later settings store can supply them without code changes;
    the transport is rebuilt only when the settings change."""

    def __init__(
        self,
        provider: Optional[MailConfigProvider] = None,
        transport_factory: TransportFactory = FastMailTransport,
        refresh: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> None:
        self._provider = provider or EnvMailConfigProvider()
        self._factory = transport_factory
        self._refresh = refresh  # keeps stored settings current; never fatal
        self._cached: Optional[Tuple[MailConfig, MailTransport]] = None

    @classmethod
    def for_transport(cls, transport: MailTransport) -> "AdminMailer":
        """A mailer on a ready transport (tests, or an embedding service)."""
        return cls(
            StaticMailConfigProvider(MailConfig(smtp_server="-", sender="-")),
            lambda _config: transport,
        )

    def with_config(self, config: MailConfig) -> "AdminMailer":
        """A mailer on exactly ``config`` (same transport factory): the setup
        wizard's test mail is sent with the candidate settings, never the saved
        ones."""
        return AdminMailer(StaticMailConfigProvider(config), self._factory)

    def _transport(self) -> MailTransport:
        config = self._provider.get()
        if not config.configured:
            raise RuntimeError("mail is not configured")
        if self._cached is None or self._cached[0] != config:
            self._cached = (config, self._factory(config))
        return self._cached[1]

    async def refresh_settings(self) -> None:
        """Let the provider pick up saved settings (a no-op without a refresher;
        a failure keeps the last known settings)."""
        if self._refresh is None:
            return
        try:
            await self._refresh()
        except Exception as exc:  # noqa: BLE001 - class only
            logger.warning("admin mail settings not refreshed (%s)", type(exc).__name__)

    async def _deliver(self, to: str, message: Message) -> bool:
        await self.refresh_settings()
        try:
            await self._transport().send(to, message.subject, message.body)
            return True
        except Exception as exc:  # fire-and-forget: never reaches the caller
            # type only: the message of a mail error can carry the address
            logger.warning("admin mail not sent (%s)", type(exc).__name__)
            return False

    def is_configured(self) -> bool:
        """Whether the current settings can send mail at all."""
        try:
            return self._provider.get().configured
        except Exception:  # noqa: BLE001 - a broken provider counts as not configured
            return False

    async def send_message(self, to: str, message: Message) -> bool:
        """Send one prepared message to one address; True when the transport
        accepted it. Never raises."""
        return await self._deliver(to, message)

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

    async def notify_new_address(
        self, admins: Sequence[str], account: str, ip: str
    ) -> int:
        return await self._notify(admins, new_address_message(account, ip))

    async def notify_setup_started(self, admins: Sequence[str], account: str, ip: str) -> int:
        return await self._notify(admins, setup_started_message(account, ip))

    async def notify_setup_locked(self, admins: Sequence[str], ip: str) -> int:
        return await self._notify(admins, setup_locked_message(ip))

    async def notify_setup_finished(self, admins: Sequence[str], account: str, ip: str) -> int:
        return await self._notify(admins, setup_finished_message(account, ip))

    async def notify_factor_reset(self, admins: Sequence[str], account: str) -> int:
        return await self._notify(admins, factor_reset_message(account))
