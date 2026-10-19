"""Checkers for gate levels 2 to 4, in the shape ``GateMiddleware`` expects:
``async checker(scope) -> bool``. A checker that passes leaves what later code
needs in ``scope["state"]``; one that fails leaves an internal ``deny_reason``
(logged at debug level, never sent to the client).

Level 2 (session) resolves the cookie token, checks revoked / idle / absolute
expiry and the address + user-agent binding. Level 3 (admin) checks the
session's email is still in ``PLATFORM_ADMIN_EMAILS``; if not, the session is
revoked. Level 4 (second factor) needs ``mfa_state = mfa_ok``.

A session in the ``setup`` state (made by redeeming a first-run setup token)
passes levels 2 and 3 only for the paths in ``SETUP_SESSION_PATHS`` (the
second-factor enrolment and sign-out) and only while no admin has a confirmed
second factor; everything else is refused. ``build_setup_checker`` decides the
wizard stage of a ``/setup`` route.
"""

from __future__ import annotations

import logging
from typing import Dict

from backend.admin.cookies import SESSION_COOKIE, read_cookie
from backend.admin.gate.levels import Level, SetupStage
from backend.admin.portal_config import PortalSettings
from backend.admin.services import sessions as sess

log = logging.getLogger("backend.admin.gate")


def _header(scope, name: bytes) -> str:
    for key, value in scope.get("headers", ()):
        if key == name:
            return value.decode("latin-1")
    return ""


# the whole of what a ``setup`` session may reach (default deny)
SETUP_SESSION_PATHS = frozenset({"/mfa", "/mfa/enrol", "/mfa/enrol/confirm", "/logout"})
SETUP_SCOPE = "setup_scope"


def build_checkers(sessions: sess.SessionService, settings: PortalSettings, wizard=None) -> Dict:
    async def session_level(scope) -> bool:
        state = scope["state"]
        result = await sessions.authenticate(
            read_cookie(scope, SESSION_COOKIE),
            state.get("client_ip"),
            _header(scope, b"user-agent"),
            state.get("request_id"),
        )
        if not result.ok:
            state["deny_reason"] = result.reason
            log.debug("session refused: %s", result.reason)
            return False
        state["session"] = result.session
        return True

    async def admin_level(scope) -> bool:
        state = scope["state"]
        session = state["session"]
        if session.mfa_state == sess.SETUP_STATE and (
            scope["path"] not in SETUP_SESSION_PATHS
            or wizard is None
            or not await wizard.setup_session_allowed(session)
        ):
            state["deny_reason"] = SETUP_SCOPE
            return False
        if settings.is_admin(session.email):
            return True
        await sessions.revoke_for_removed_admin(session, state.get("request_id"))
        state["deny_reason"] = sess.NOT_ADMIN
        return False

    async def second_factor_level(scope) -> bool:
        state = scope["state"]
        if state["session"].mfa_state == "mfa_ok":
            return True
        state["deny_reason"] = sess.MFA_REQUIRED
        return False

    return {
        Level.SESSION: session_level,
        Level.ADMIN: admin_level,
        Level.SECOND_FACTOR: second_factor_level,
    }


def build_setup_checker(wizard):
    """``async checker(scope, stage) -> bool`` for the routes under ``/setup``."""

    async def setup_stage(scope, stage: SetupStage) -> bool:
        if stage is SetupStage.OPEN:
            return await wizard.is_open()
        if stage is SetupStage.ATTEMPT:
            return True
        if stage is SetupStage.CHECKLIST:
            session = scope["state"].get("session")
            return session is not None and await wizard.checklist_open(session)
        return False

    return setup_stage
