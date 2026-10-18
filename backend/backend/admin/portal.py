"""The admin portal's assembled services, built once per application.

``Portal.build`` wires the engine, clock, rate limiter, mailer, session and
sign-in services and the template environment from the master key and the
environment. Tests pass their own engine, clock and mail transport.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import HTMLResponse

from backend.admin.gate.checkers import build_checkers
from backend.admin.portal_config import PortalSettings
from backend.admin.repositories.tables import attempts
from backend.admin.security.clock import Clock, SystemClock
from backend.admin.security.keycheck import require_key
from backend.admin.security.keys import admin_key
from backend.admin.security.mailer import AdminMailer
from backend.admin.security.ratelimit import Limiter, SqlAttemptStore
from backend.admin.services.factors import FactorService
from backend.admin.services.pages import PageService
from backend.admin.services.sessions import SessionService
from backend.admin.services.signin import SignInService
from backend.admin.services.stepup import StepUpService
from backend.admin.services.task_pages import TaskPageService

log = logging.getLogger("backend.admin")

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
CLEANUP_EVERY_SECONDS = 600


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
    tasks: TaskPageService
    csrf_key: bytes
    templates: Environment

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
        mailer = mailer or AdminMailer()
        sessions = SessionService(engine, clock, settings)
        signin = SignInService(
            engine, clock, settings, limiter, mailer, sessions, pepper, cookie_key
        )
        factors = FactorService(
            engine, clock, settings, limiter, mailer, sessions, pepper, totp_key
        )
        stepup = StepUpService(clock, sessions, store, stepup_key)
        return cls(
            settings, engine, clock, limiter, mailer, sessions, signin, factors,
            stepup, PageService(engine, clock), TaskPageService(engine, clock), csrf_key, make_templates(),
        )

    def checkers(self) -> dict:
        return build_checkers(self.sessions, self.settings)

    def render(self, name: str, status: int = 200, **context: Any) -> HTMLResponse:
        html = self.templates.get_template(name).render(**context)
        return HTMLResponse(html, status_code=status)

    async def startup(self) -> int:
        """Revoke sessions whose email left PLATFORM_ADMIN_EMAILS; returns how many."""
        revoked = await self.sessions.sweep_removed_admins(self.settings.admin_emails)
        log.info("admin sessions swept at start: %d revoked", revoked)
        if not self.settings.admin_emails:
            log.warning("PLATFORM_ADMIN_EMAILS is empty: nobody can sign in")
        return revoked

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_EVERY_SECONDS)
            try:
                await self.sessions.cleanup()
                await self.limiter.cleanup()
            except Exception as exc:  # keep looping; type only
                log.warning("admin cleanup failed: %s", type(exc).__name__)
