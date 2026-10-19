"""The first-run setup wizard: what is allowed, in which order, and what it writes.

The host operator prints a one-time token on the console (``setup-token``, see
``services/setup_token.py``). The wizard is reachable only while no admin has a
confirmed second factor and a valid token exists, and it walks one path:

1. ``redeem``: the token and an address from ``PLATFORM_ADMIN_EMAILS``. The
   token is consumed and a short ``setup`` session is created: it reaches the
   setup page, second-factor enrolment and sign-out, nothing else.
2. Enrolment through the existing machinery (``FactorService``): the first
   confirmed factor ends the token's life for good (``setup_token`` refuses
   when any factor is confirmed) and turns the session into a normal one.
3. Mail (optional): a test mail with a six-digit code goes to the admin's own
   address using exactly the candidate settings; only a matching code saves the
   ``admin_mail`` keys (through ``SettingsService.set(mail_verified=True)``).
4. Finish: the master key fingerprint and the backup reminder, then the wizard
   is closed in the database and unreachable from then on.

Steps 3 and 4 need a fully signed-in session of the admin who redeemed the
token, within two hours of it, and a fresh second-factor code (the portal's
step-up) for anything that writes.

Nothing here logs or audits a secret: the token, the test code, the mail
password and the sealed blobs never appear in an audit row, a log line, a URL
or a response (a sealed blob is AES-GCM and bound to the session).
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Awaitable, Callable, List, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.portal_config import PortalSettings
from backend.admin.repositories import settings_views
from backend.admin.repositories import setup_state as state_repo
from backend.admin.security.clock import Clock
from backend.admin.security.mailer import (
    AdminMailer,
    LayeredMailConfigProvider,
    mail_config_from_settings,
    mail_test_message,
)
from backend.admin.security.ratelimit import Limiter, Rule
from backend.admin.services import audit, setup_token
from backend.admin.services import settings_pages as sp
from backend.admin.services.sessions import SETUP_STATE, Session, SessionService
from backend.admin.services.settings_store import Actor, SettingsError, SettingsService
from common.settings.registry import ValidationError

log = logging.getLogger("backend.admin.setup")

AfterResponse = Callable[[], Awaitable[object]]

# five tries per address and 15 minutes; the token itself locks after 20 in all
TOKEN_TRIES = Rule("setup_try", 5, 15 * 60)
MAIL_SENDS = Rule("setup_mail_send", 3, 10 * 60)
MAIL_CODE_TRIES = Rule("setup_mail_code", 5, 10 * 60)
CHECKLIST_WINDOW = timedelta(hours=2)
MAIL_PENDING_SECONDS = 10 * 60
MAIL_SEND_TIMEOUT_SECONDS = 20
MAIL_SECTION = "admin_mail"
MAX_TOKEN_FIELD = 200
SEAL_ACTION = "setup.mail"
_STAND_IN = "0"  # never equals a real token (160 bits of base32)
_NO_OP_UPDATE = text("UPDATE admin.setup_tokens SET failed_attempts = failed_attempts WHERE false")

# form field -> store key, in the order the page shows them
MAIL_FIELDS = (
    ("server", "ADMIN_MAIL_SMTP_SERVER"),
    ("port", "ADMIN_MAIL_SMTP_PORT"),
    ("sender", "ADMIN_MAIL_SENDER"),
    ("user", "ADMIN_MAIL_USER"),
    ("password", "ADMIN_MAIL_PASSWORD"),
    ("starttls", "ADMIN_MAIL_STARTTLS"),
    ("ssl_tls", "ADMIN_MAIL_SSL_TLS"),
    ("use_credentials", "ADMIN_MAIL_USE_CREDENTIALS"),
    ("validate_certs", "ADMIN_MAIL_VALIDATE_CERTS"),
)
MAIL_KEYS = frozenset(key for _, key in MAIL_FIELDS)

# the only text a field error can show (fixed per kind; no typed value in it)
FIELD_ERRORS = {
    "required": "This field is required.",
    "invalid": "This value is not accepted.",
    "tls_both": "Choose STARTTLS or TLS from the start, not both.",
    "credentials": "Logging in needs a user name (and a saved or new password).",
    "password_retype": (
        "The server, port or user name changed: type the password again. "
        "A saved password is never sent to a different server."
    ),
    "port_required": "Enter the port when you use TLS from the start (usually 465).",
}
DEFAULT_PORT = 587
_SERVER, _PORT, _USER, _PASSWORD = (
    "ADMIN_MAIL_SMTP_SERVER", "ADMIN_MAIL_SMTP_PORT", "ADMIN_MAIL_USER", "ADMIN_MAIL_PASSWORD",
)


@dataclass
class RedeemResult:
    ok: bool
    session_token: Optional[str] = None
    after: List[AfterResponse] = field(default_factory=list)


@dataclass
class MailForm:
    """The mail form as typed. ``typed`` holds the validated store values and is
    empty while ``errors`` is not; the password is never in ``values``."""

    values: dict
    errors: dict
    typed: dict = field(default_factory=dict)


@dataclass
class MailTestResult:
    ok: bool
    reason: Optional[str] = None  # invalid | rate_limited | not_delivered
    blob: Optional[str] = None
    form: Optional[MailForm] = None


@dataclass
class MailConfirmResult:
    ok: bool
    reason: Optional[str] = None  # expired | locked | wrong | refused


def group_fingerprint(raw: str) -> str:
    """The master key's short id in groups of four, as the host command prints it."""
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


class SetupWizard:
    def __init__(
        self,
        engine: AsyncEngine,
        clock: Clock,
        settings: PortalSettings,
        limiter: Limiter,
        mailer: AdminMailer,
        sessions: SessionService,
        service: SettingsService,
        mail_provider: LayeredMailConfigProvider,
        pending_key: bytes,
        master_key: bytes,
        fingerprint: str,
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._settings = settings
        self._limiter = limiter
        self._mailer = mailer
        self._sessions = sessions
        self._service = service
        self._mail_provider = mail_provider
        self._pending_key = pending_key
        self._master_key = master_key
        self.fingerprint = group_fingerprint(fingerprint)

    # ---------------------------------------------------------------- state
    def _admins(self) -> List[str]:
        return sorted(self._settings.admin_emails)

    async def is_open(self) -> bool:
        """The token page exists: no admin has a confirmed factor and an
        unexpired, unlocked, unused token is waiting."""
        async with self._engine.connect() as conn:
            if await setup_token.enrolment_complete(conn):
                return False
            return await setup_token.active(conn) is not None

    async def setup_session_allowed(self, session: Session) -> bool:
        """A ``setup`` session is good only while nobody has a confirmed factor."""
        if session.mfa_state != SETUP_STATE:
            return False
        async with self._engine.connect() as conn:
            return not await setup_token.enrolment_complete(conn)

    async def checklist_open(self, session: Session) -> bool:
        """The post-enrolment steps: the signed-in admin who redeemed the token,
        until the wizard is finished or two hours after the redeem."""
        if session.mfa_state != "mfa_ok":
            return False
        async with self._engine.connect() as conn:
            row = await state_repo.get(conn)
        if row is None or row.completed_at is not None:
            return False
        if row.started_by.strip().lower() != session.email.strip().lower():
            return False
        return self._clock.now() < row.started_at + CHECKLIST_WINDOW

    async def mail_step(self) -> Optional[str]:
        async with self._engine.connect() as conn:
            row = await state_repo.get(conn)
        return None if row is None else row.mail_step

    # ---------------------------------------------------------------- redeem
    async def redeem(self, raw_token: str, raw_email: str, ip, ua, rid) -> RedeemResult:
        """Token plus admin address -> a ``setup`` session. Every refusal looks
        the same to the caller (wrong token, unlisted address, rate limit,
        expired, locked, setup over)."""
        email = str(raw_email or "").strip().lower()[:320]
        token = str(raw_token or "")[:MAX_TOKEN_FIELD]
        decision = await self._limiter.hit(TOKEN_TRIES, self._limiter.ip_key(ip))
        if not decision.allowed:
            return RedeemResult(False)  # not audited: a refused try must not grow the log
        # Every refusal runs the same statements: the token is looked up whether or
        # not the address is listed or setup is over (a stand-in value is checked
        # then), and a refused try always writes the same audit row.
        listed = email in self._settings.admin_emails and bool(setup_token.normalise(token))
        after: List[AfterResponse] = []
        async with self._engine.begin() as conn:
            complete = await setup_token.enrolment_complete(conn)
            before = await setup_token.active(conn)
            real = listed and not complete
            ok = await setup_token.redeem(
                conn, self._master_key, token if real else _STAND_IN
            )
            if not ok:
                if before is None:  # same statement count as a counted wrong try
                    await conn.execute(_NO_OP_UPDATE)
                await self._audit_refused(conn, ip, ua, rid)
                now_active = await setup_token.active(conn)
                if (
                    before is not None
                    and now_active is None
                    and before.failed_attempts + 1 >= setup_token.MAX_FAILED_ATTEMPTS
                ):
                    await audit.write(
                        conn, "setup.token_locked", "setup", None, None, None, "denied",
                        actor_kind="system", ip=ip, request_id=rid,
                        detail={"failed_attempts": setup_token.MAX_FAILED_ATTEMPTS},
                    )
                    after.append(
                        lambda: self._mailer.notify_setup_locked(self._admins(), ip or "unknown")
                    )
                return RedeemResult(False, after=after)
            session_token, session = await self._sessions.create(
                email, ip, ua, mfa_state=SETUP_STATE, request_id=rid, conn=conn
            )
            await state_repo.start(conn, email, self._clock.now())
            await audit.write(
                conn, "setup.token_redeemed", "setup", None, None, None, "success",
                actor_kind="anonymous", actor_email=email, session_id=session.id,
                ip=ip, ua=ua, request_id=rid,
            )
        after.append(
            lambda: self._mailer.notify_setup_started(self._admins(), email, ip or "unknown")
        )
        return RedeemResult(True, session_token, after)

    @staticmethod
    async def _audit_refused(conn, ip, ua, rid) -> None:
        await audit.write(
            conn, "setup.token_refused", "setup", None, None, None, "failure",
            actor_kind="anonymous", ip=ip, ua=ua, request_id=rid,
        )

    # ------------------------------------------------------------------ mail
    def mail_source(self) -> str:
        return self._mail_provider.source()

    async def mail_form_defaults(self) -> dict:
        """Saved non-secret mail settings for the form (and whether a password
        is saved); the password itself never leaves the store."""
        stored = await self._service.stored()
        out: dict = {}
        for name, key in MAIL_FIELDS:
            if name == "password" or key not in stored.values:
                continue
            value = stored.values[key]
            out[name] = ("true" if value else "false") if isinstance(value, bool) else str(value)
        out["password_saved"] = "ADMIN_MAIL_PASSWORD" in stored.values
        return out

    def parse_mail_form(self, form: Mapping[str, Any]) -> MailForm:
        registry = self._service.registry
        values: dict = {}
        typed: dict = {}
        errors: dict = {}
        for name, key in MAIL_FIELDS:
            raw = form.get(name, "")
            if not isinstance(raw, str):
                raw = ""
            if name != "password":
                raw = raw.strip()
            values[name] = "" if name == "password" else raw[:400]
            if raw == "":
                if name in ("server", "sender"):
                    errors[name] = "required"
                continue
            try:
                typed[key] = registry.validate(key, raw)
            except ValidationError:
                errors[name] = "invalid"
        if not errors:
            if typed.get("ADMIN_MAIL_STARTTLS") is True and typed.get("ADMIN_MAIL_SSL_TLS") is True:
                errors["ssl_tls"] = "tls_both"
        return MailForm(values, errors, {} if errors else typed)

    @staticmethod
    def _candidate_problem(saved: Mapping[str, Any], typed: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict:
        """Checks on the settings that would really be used (saved ones overlaid
        with the form): never both TLS modes, a port for implicit TLS, a user for
        a login, and a saved password only for the same server, port and user."""
        problems: dict = {}
        if candidate.get("ADMIN_MAIL_STARTTLS", True) and candidate.get("ADMIN_MAIL_SSL_TLS", False):
            problems["ssl_tls"] = "tls_both"
        elif candidate.get("ADMIN_MAIL_SSL_TLS", False) and _PORT not in typed:
            problems["port"] = "port_required"
        if candidate.get("ADMIN_MAIL_USE_CREDENTIALS", True) and not candidate.get(_USER):
            problems["user"] = "credentials"
        if _PASSWORD not in typed and _PASSWORD in saved:
            same = (
                candidate.get(_SERVER) == saved.get(_SERVER)
                and candidate.get(_PORT, DEFAULT_PORT) == saved.get(_PORT, DEFAULT_PORT)
                and candidate.get(_USER) == saved.get(_USER)
            )
            if not same:
                problems["password"] = "password_retype"
        return problems

    async def start_mail_test(self, session: Session, form: MailForm, ip, ua, rid) -> MailTestResult:
        """Send a six-digit code to the admin's own address using the candidate
        settings (the saved ones overlaid with the form). Nothing is saved."""
        if form.errors or not form.typed:
            return MailTestResult(False, "invalid", form=form)
        stored = await self._service.stored()
        candidate = {k: v for k, v in stored.values.items() if k in MAIL_KEYS}
        candidate.update(form.typed)
        refused = self._candidate_problem(stored.values, form.typed, candidate)
        if refused:
            form.errors.update(refused)
            return MailTestResult(False, "invalid", form=form)
        decision = await self._limiter.hit(MAIL_SENDS, self._limiter.email_key(session.email))
        if not decision.allowed:
            return MailTestResult(False, "rate_limited", form=form)
        config = mail_config_from_settings(candidate)
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        delivered = False
        if config.configured:
            try:
                delivered = await asyncio.wait_for(
                    self._mailer.with_config(config).send_message(
                        session.email, mail_test_message(code)
                    ),
                    MAIL_SEND_TIMEOUT_SECONDS,
                )
            except Exception:  # noqa: BLE001 - class only; an SMTP message can carry an address
                delivered = False
        async with self._engine.begin() as conn:
            await audit.write(
                conn, "setup.mail_test", "setup", None, None, None,
                "success" if delivered else "failure", actor_kind="admin",
                actor_email=session.email, session_id=session.id, ip=ip, ua=ua, request_id=rid,
            )
        if not delivered:
            return MailTestResult(False, "not_delivered", form=form)
        blob = sp.seal_pending(
            self._pending_key, self._clock, session.id, SEAL_ACTION, MAIL_SECTION, 0,
            {"v": form.typed, "c": code}, seconds=MAIL_PENDING_SECONDS,
        )
        return MailTestResult(True, blob=blob, form=form)

    async def confirm_mail(
        self, session: Session, blob: Any, typed_code: str, ip, ua, rid
    ) -> MailConfirmResult:
        """Save the tested settings if the typed code is the mailed one."""
        decision = await self._limiter.hit(MAIL_CODE_TRIES, self._limiter.email_key(session.email))
        if not decision.allowed:
            return MailConfirmResult(False, "locked")
        material = sp.open_pending(
            self._pending_key, self._clock, session.id, SEAL_ACTION, MAIL_SECTION, 0, blob
        )
        if sp.is_missing(material) or not isinstance(material, dict):
            return MailConfirmResult(False, "expired")
        code = str(material.get("c", ""))
        typed = str(typed_code or "").strip()[:12]
        if not (code and hmac.compare_digest(typed.encode(), code.encode())):
            return MailConfirmResult(False, "wrong")
        values = material.get("v")
        if not isinstance(values, dict) or not values or not set(values) <= MAIL_KEYS:
            return MailConfirmResult(False, "expired")
        actor = Actor("admin", session.email, str(session.id), ip, ua, rid)
        try:
            for key in sorted(values):
                async with self._engine.connect() as conn:
                    found = await settings_views.entry_version(conn, key)
                version = found[0] if found else 0
                step = sp.step_up_for(
                    self._service, "set", key, values[key], version, session.email,
                    self._clock.now(),
                )
                await self._service.set(
                    key, values[key], actor, step_up=step, confirmation=key,
                    expected_version=version, mail_verified=True,
                )
        except SettingsError:
            return MailConfirmResult(False, "refused")
        await self.refresh_mail()
        async with self._engine.begin() as conn:
            await state_repo.set_mail_step(conn, "saved", self._clock.now())
            await audit.write(
                conn, "setup.mail_saved", "setup", None, None, None, "success",
                actor_kind="admin", actor_email=session.email, session_id=session.id,
                ip=ip, ua=ua, request_id=rid, detail={"settings": len(values)},
            )
        return MailConfirmResult(True)

    async def refresh_mail(self) -> None:
        """Load the saved ``admin_mail`` settings into the portal's mail provider."""
        stored = await self._service.stored()
        saved = {k: v for k, v in stored.values.items() if k in MAIL_KEYS}
        self._mail_provider.stored = mail_config_from_settings(saved) if saved else None

    async def skip_mail(self, session: Session, ip, ua, rid) -> None:
        async with self._engine.begin() as conn:
            if await state_repo.set_mail_step(conn, "skipped", self._clock.now()):
                await audit.write(
                    conn, "setup.mail_skipped", "setup", None, None, None, "success",
                    actor_kind="admin", actor_email=session.email, session_id=session.id,
                    ip=ip, ua=ua, request_id=rid,
                )

    # ---------------------------------------------------------------- finish
    async def finish(self, session: Session, ip, ua, rid) -> Optional[List[AfterResponse]]:
        """Close the wizard for good. None when the mail step was not decided
        yet (or it was already closed); else the mails to send."""
        async with self._engine.begin() as conn:
            row = await state_repo.get(conn)
            if row is None or row.completed_at is not None or row.mail_step is None:
                return None
            await state_repo.complete(conn, session.email, self._clock.now())
            await audit.write(
                conn, "setup.completed", "setup", None, None, None, "success",
                actor_kind="admin", actor_email=session.email, session_id=session.id,
                ip=ip, ua=ua, request_id=rid, detail={"mail": row.mail_step},
            )
        return [
            lambda: self._mailer.notify_setup_finished(self._admins(), session.email, ip or "unknown")
        ]
