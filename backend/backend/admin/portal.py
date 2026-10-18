"""The admin portal's assembled services, built once per application.

``Portal.build`` wires the engine, clock, rate limiter, mailer, session and
sign-in services and the template environment from the master key and the
environment. Tests pass their own engine, clock and mail transport.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import HTMLResponse

from backend.admin.config import MASTER_KEY_KEY, parse_master_key
from backend.admin.gate.checkers import build_checkers, build_setup_checker
from backend.admin.loops.base import LoopRunner
from backend.admin.loops.config import LoopSettings
from backend.admin.loops.status import IntegrityStatus, LoopStatus, StatusBoard
from backend.admin.portal_config import PortalSettings
from backend.admin.repositories.tables import attempts
from backend.admin.security.clock import Clock, SystemClock
from backend.admin.security.keycheck import require_key
from backend.admin.security.keys import MASTER_KEY_KEY, admin_key, parse_master_key
from common.settings.keys import SectionKeys
from backend.admin.security.mailer import AdminMailer, LayeredMailConfigProvider
from backend.admin.security.ratelimit import Limiter, SqlAttemptStore
from backend.admin.services.factors import FactorService
from backend.admin.services.pages import PageService
from backend.admin.services.sessions import SessionService
from backend.admin.services.settings_pages import SettingsPages
from backend.admin.services.settings_store import SettingsService, store_registry
from backend.admin.services.setup_wizard import SetupWizard
from backend.admin.services.signin import SignInService
from backend.admin.services.stepup import StepUpService

log = logging.getLogger("backend.admin")

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
CLEANUP_EVERY_SECONDS = 600
MASTER_KEY_PREVIOUS_KEY = "SETTINGS_MASTER_KEY_PREVIOUS"


def _timestamp(value: Optional[datetime]) -> str:
    """A UTC moment as ``2026-10-18 09:30:00 UTC`` (``-`` for none)."""
    if value is None:
        return "-"
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def make_templates(directory: Path = TEMPLATE_DIR) -> Environment:
    """Autoescaped Jinja2, strict about missing values, English strings through
    a gettext-style ``_()`` so a catalogue can be added later."""
    env = Environment(
        loader=FileSystemLoader(str(directory)),
        autoescape=True,
        undefined=StrictUndefined,
        extensions=["jinja2.ext.i18n"],
    )
    env.install_null_translations(newstyle=True)
    env.filters["ts"] = _timestamp
    return env


class _MailRefresher:
    """Reloads the saved admin mail settings for the mailer, at most once a minute."""

    EVERY_SECONDS = 60

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._last = float("-inf")
        self.wizard: Optional[SetupWizard] = None

    async def __call__(self) -> None:
        now = self._clock.time()
        if self.wizard is None or now - self._last < self.EVERY_SECONDS:
            return
        self._last = now
        await self.wizard.refresh_mail()


@dataclass
class Portal:
    settings: PortalSettings
    engine: AsyncEngine
    clock: Clock
    limiter: Limiter
    mailer: AdminMailer
    sessions: SessionService
    signin: SignInService
    factors: FactorService
    stepup: StepUpService
    pages: PageService
    csrf_key: bytes
    templates: Environment
    settings_pages: SettingsPages
    pending_key: bytes
    setup: SetupWizard
    loop_settings: LoopSettings = field(default_factory=LoopSettings)
    board: StatusBoard = field(default_factory=StatusBoard)
    master_key: bytes = field(default=b"", repr=False)
    master_previous: Optional[bytes] = field(default=None, repr=False)
    runner: Optional[LoopRunner] = None

    @classmethod
    def build(
        cls,
        engine: AsyncEngine,
        *,
        env: Optional[Mapping[str, str]] = None,
        clock: Optional[Clock] = None,
        mailer: Optional[AdminMailer] = None,
        settings: Optional[PortalSettings] = None,
        limiter_store=None,
    ) -> "Portal":
        source = os.environ if env is None else env
        settings = settings or PortalSettings.from_env(source)
        clock = clock or SystemClock()
        pepper = require_key(admin_key("pepper", env=source), "pepper")
        csrf_key = require_key(admin_key("csrf", env=source), "CSRF key")
        cookie_key = require_key(admin_key("signin", env=source), "sign-in key")
        store = limiter_store or SqlAttemptStore(engine, attempts)
        limiter = Limiter(store, clock, pepper)
        totp_key = require_key(admin_key("totp", env=source), "TOTP key")
        stepup_key = require_key(admin_key("stepup", env=source), "step-up key")
        mail_provider = LayeredMailConfigProvider(None if env is None else source)
        refresher = _MailRefresher(clock)
        mailer = mailer or AdminMailer(mail_provider, refresh=refresher)
        sessions = SessionService(engine, clock, settings)
        signin = SignInService(
            engine, clock, settings, limiter, mailer, sessions, pepper, cookie_key
        )
        factors = FactorService(
            engine, clock, settings, limiter, mailer, sessions, pepper, totp_key
        )
        stepup = StepUpService(clock, sessions, store, stepup_key)
        pending_key = require_key(admin_key("pending", env=source), "pending-change key")
        pages = PageService(engine, clock)
        registry = store_registry()
        previous_raw = (source.get(MASTER_KEY_PREVIOUS_KEY) or "").strip()
        master_key = parse_master_key(source.get(MASTER_KEY_KEY))
        master_previous = parse_master_key(previous_raw) if previous_raw else None
        keys = SectionKeys(
            master_key,
            sections={s.section for s in registry},
            master_previous=master_previous,
        )
        service = SettingsService(engine, registry, keys, clock=clock.now)
        wizard = SetupWizard(
            engine, clock, settings, limiter, mailer, sessions, service, mail_provider,
            pending_key, master_key, keys.fingerprint,
        )
        refresher.wizard = wizard
        return cls(
            settings, engine, clock, limiter, mailer, sessions, signin, factors,
            stepup, pages, csrf_key, make_templates(),
            SettingsPages(engine, service, pages, clock), pending_key, wizard,
            loop_settings=LoopSettings.from_env(source),
            master_key=master_key,
            master_previous=master_previous,
        )

    def checkers(self) -> dict:
        return build_checkers(self.sessions, self.settings, self.setup)

    def setup_checker(self):
        return build_setup_checker(self.setup)

    def render(self, name: str, status: int = 200, **context: Any) -> HTMLResponse:
        html = self.templates.get_template(name).render(**context)
        return HTMLResponse(html, status_code=status)

    async def startup(self) -> int:
        """Revoke sessions whose email left PLATFORM_ADMIN_EMAILS; returns how many."""
        revoked = await self.sessions.sweep_removed_admins(self.settings.admin_emails)
        log.info("admin sessions swept at start: %d revoked", revoked)
        try:
            await self.setup.refresh_mail()  # saved admin mail settings
        except Exception as exc:  # noqa: BLE001 - class only; mail then uses the environment
            log.warning("saved admin mail settings not loaded (%s)", type(exc).__name__)
        if not self.settings.admin_emails:
            log.warning("PLATFORM_ADMIN_EMAILS is empty: nobody can sign in")
        return revoked

    # ------------------------------------------------------------- loops

    def integrity_status(self) -> IntegrityStatus:
        """The latest settings integrity result (for the shell banner)."""
        return self.board.integrity

    def loop_status(self) -> dict[str, LoopStatus]:
        """Each background loop's state, a read-only copy (for the Health page)."""
        return self.board.snapshot()

    def mail_status(self) -> str:
        """``ok``, ``mail not configured`` or ``unknown`` (sender not run yet)."""
        return self.board.mail

    async def start_loops(self) -> bool:
        """Start the background loops (full portal mode only); False when they
        are switched off with ``ADMIN_LOOPS_ENABLED=false``."""
        if not self.loop_settings.enabled:
            return False
        from backend.admin.loops.build import build_runner

        self.runner = build_runner(self)
        await self.runner.start()
        return True

    async def stop_loops(self) -> None:
        if self.runner is not None:
            await self.runner.stop()
            self.runner = None

    async def cleanup_loop(self) -> None:
        """The plain cleanup, used only when the loops are switched off."""
        while True:
            await asyncio.sleep(CLEANUP_EVERY_SECONDS)
            try:
                await self.sessions.cleanup()
                await self.limiter.cleanup()
            except Exception as exc:  # keep looping; type only
                log.warning("admin cleanup failed: %s", type(exc).__name__)
