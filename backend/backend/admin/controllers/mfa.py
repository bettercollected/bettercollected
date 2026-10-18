"""Second-factor pages: enrolment, sign-in verification, step-up prompt,
recovery codes and the account page.

Who may reach what (``Level.ADMIN`` routes are open to a session whose email
step is done; the handlers narrow that):

* ``email_ok`` and NO confirmed factor: only ``/mfa/enrol*`` (and ``/logout``);
  ``/mfa`` sends the browser there.
* ``email_ok`` WITH a confirmed factor: only ``/mfa/verify`` (and ``/logout``).
* ``mfa_ok``: everything else; adding or replacing a factor needs a fresh step-up.

Recovery codes are rendered in the response that creates them and nowhere else.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from backend.admin import cookies
from backend.admin.controllers.portal import (
    _field, _ip, _portal, _rid, _schedule, _ua,
)
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.stepup import STEPUP_ATTR, ActionBound, PROMPT_PATH, require_stepup
from backend.admin.portal import Portal
from backend.admin.security import csrf
from backend.admin.services import factors as fsvc
from backend.admin.services.sessions import hash_token
from backend.admin.services.stepup import TOKEN_SECONDS, action_hash

# where the step-up prompt may send the browser back to (never a request value)
STEPUP_RETURNS = ("/mfa/recovery-codes", "/mfa/enrol", "/account")
RECOVERY_PAGE = "/mfa/recovery-codes"


def _session(request: Request):
    return request.scope["state"]["session"]


def _csrf(portal: Portal, session) -> str:
    return csrf.session_token(portal.csrf_key, session.csrf_subject)


def _csrf_after_rotation(portal: Portal, session, new_token: str) -> str:
    """The CSRF token for forms rendered in the response that rotates the session
    token (the old subject is refused from now on)."""
    subject = f"{session.id}.{hash_token(new_token).hex()}"
    return csrf.session_token(portal.csrf_key, subject)


def _token(request: Request) -> str:
    return cookies.read_cookie(request.scope, cookies.SESSION_COOKIE) or ""


def _see(path: str) -> Response:
    return RedirectResponse(path, status_code=303)


def _prompt(next_path: str) -> Response:
    return _see(f"{PROMPT_PATH}?next={next_path}")


def _refused_page(portal, template: str, session, outcome, **context) -> Response:
    """A failed or refused code: wrong answers re-show the form, a lock or the
    breaker pause answers 429 with a generic text and the minutes left."""
    minutes = outcome.retry_minutes if outcome.reason in (fsvc.LOCKED, fsvc.PAUSED) else 0
    return portal.render(
        template, 429 if minutes else 200, csrf_token=_csrf(portal, session),
        email=session.email, failed=outcome.reason == fsvc.WRONG,
        locked_minutes=minutes, **context,
    )


def register(reg: RouteRegistry) -> None:
    # -- dispatch ------------------------------------------------------------------
    @reg.route("/mfa", level=Level.ADMIN)
    async def mfa_home(request: Request):
        session = _session(request)
        if session.mfa_state == "mfa_ok":
            return _see("/")
        status = await _portal(request).factors.status(session.email)
        return _see("/mfa/verify" if status.confirmed else "/mfa/enrol")

    # -- enrolment -------------------------------------------------------------------
    @reg.route("/mfa/enrol", level=Level.ADMIN)
    async def enrol_page(request: Request):
        portal, session = _portal(request), _session(request)
        status = await portal.factors.status(session.email)
        if session.mfa_state == "email_ok" and status.confirmed:
            return _see("/mfa/verify")
        if session.mfa_state == "mfa_ok" and not portal.sessions.stepup_fresh(session):
            return _prompt("/mfa/enrol")
        return portal.render(
            "enrol_start.html", csrf_token=_csrf(portal, session), email=session.email,
            replacing=status.confirmed,
        )

    @reg.route("/mfa/enrol", level=Level.ADMIN, methods=["POST"])
    async def enrol_start(request: Request):
        portal, session = _portal(request), _session(request)
        result = await portal.factors.start_enrol(session, _ip(request), _ua(request), _rid(request))
        if isinstance(result, fsvc.Outcome):
            return _prompt("/mfa/enrol") if result.reason == fsvc.STEPUP_REQUIRED else _see("/mfa/verify")
        return portal.render(
            "enrol.html", csrf_token=_csrf(portal, session), factor_id=str(result.factor_id),
            secret=result.secret, qr=result.qr, failed=False, locked_minutes=0,
        )

    @reg.route("/mfa/enrol/confirm", level=Level.ADMIN, methods=["POST"])
    async def enrol_confirm(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        raw_id = await _field(request, "factor_id")
        try:
            factor_id: Optional[uuid.UUID] = uuid.UUID(raw_id)
        except ValueError:
            factor_id = None
        result = await portal.factors.confirm_enrol(
            session, _token(request), factor_id, await _field(request, "code"),
            _ip(request), _ua(request), _rid(request),
        )
        _schedule(background, result.after)
        if result.ok:
            response = portal.render(
                "recovery_codes.html",
                csrf_token=_csrf_after_rotation(portal, session, result.new_token),
                codes=result.codes,
            )
            cookies.set_cookie(response, cookies.SESSION_COOKIE, result.new_token)
        elif result.reason == fsvc.STEPUP_REQUIRED:
            response = _prompt("/mfa/enrol")
        elif result.reason in (fsvc.NOT_ALLOWED, fsvc.STALE):
            response = _see("/mfa")
        else:  # wrong code, lock or pause: the code form again (no secret is shown twice)
            response = _refused_page(
                portal, "enrol.html", session, result, factor_id=str(factor_id), qr=None,
                secret=None,
            )
        response.background = background
        return response

    # -- sign-in verification ---------------------------------------------------------
    @reg.route("/mfa/verify", level=Level.ADMIN)
    async def verify_page(request: Request):
        portal, session = _portal(request), _session(request)
        if session.mfa_state == "mfa_ok":
            return _see("/")
        if not (await portal.factors.status(session.email)).confirmed:
            return _see("/mfa/enrol")
        return portal.render(
            "verify.html", csrf_token=_csrf(portal, session), email=session.email,
            failed=False, locked_minutes=0,
        )

    @reg.route("/mfa/verify", level=Level.ADMIN, methods=["POST"])
    async def verify_submit(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        if session.mfa_state == "mfa_ok":
            return _see("/")
        result = await portal.factors.verify_login(
            session, _token(request), await _field(request, "code"),
            _ip(request), _ua(request), _rid(request),
        )
        _schedule(background, result.after)
        if result.ok:
            response = _see("/")
            cookies.set_cookie(response, cookies.SESSION_COOKIE, result.new_token)
        elif result.reason in (fsvc.NO_FACTOR, fsvc.STALE):
            response = _see("/mfa")
        else:
            response = _refused_page(portal, "verify.html", session, result)
        response.background = background
        return response

    # -- step-up ----------------------------------------------------------------------
    def _next(value: str) -> str:
        return value if value in STEPUP_RETURNS else "/account"

    @reg.route(PROMPT_PATH, level=Level.SECOND_FACTOR)
    async def stepup_page(request: Request):
        portal, session = _portal(request), _session(request)
        return portal.render(
            "stepup.html", csrf_token=_csrf(portal, session), email=session.email,
            next=_next(request.query_params.get("next", "")), failed=False, locked_minutes=0,
        )

    @reg.route(PROMPT_PATH, level=Level.SECOND_FACTOR, methods=["POST"])
    async def stepup_submit(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        target = _next(await _field(request, "next"))
        result = await portal.factors.verify_stepup(
            session, await _field(request, "code"), _ip(request), _ua(request), _rid(request)
        )
        _schedule(background, result.after)
        response = (
            _see(target) if result.ok
            else _refused_page(portal, "stepup.html", session, result, next=target)
        )
        response.background = background
        return response

    @reg.route("/api/stepup", level=Level.SECOND_FACTOR, methods=["POST"])
    async def stepup_token(request: Request, background: BackgroundTasks):
        """JSON ``{"code", "action", "parts": [...]}`` -> ``{"token", "expires_in"}``:
        a fresh factor code buys one single-use token for one registered
        ``ActionBound`` action and exactly those ``parts``."""
        portal, session = _portal(request), _session(request)
        try:
            body = await request.json()
            code, action, parts = body["code"], body["action"], body.get("parts", [])
            valid = (
                isinstance(code, str) and isinstance(action, str) and isinstance(parts, list)
                and len(parts) <= 8 and all(isinstance(p, str) and len(p) <= 200 for p in parts)
            )
        except (ValueError, KeyError, TypeError):
            valid = False
        known = {
            spec.name
            for route in request.app.router.routes
            for spec in [getattr(getattr(route, "endpoint", None), STEPUP_ATTR, None)]
            if isinstance(spec, ActionBound)
        }
        if not valid or action not in known:
            return JSONResponse({"error": "bad_request"}, status_code=400)
        result = await portal.factors.verify_stepup(
            session, code, _ip(request), _ua(request), _rid(request)
        )
        _schedule(background, result.after)
        if not result.ok:
            locked = result.reason in (fsvc.LOCKED, fsvc.PAUSED)
            response = JSONResponse(
                {"error": "locked" if locked else "wrong_code", "retry_minutes": result.retry_minutes},
                status_code=429 if locked else 403,
            )
        else:
            fresh = await portal.sessions.reload(session)
            token = portal.stepup.issue(fresh, action_hash(action, *parts)) if fresh else None
            response = JSONResponse(
                {"token": token, "expires_in": TOKEN_SECONDS}, status_code=200 if token else 403
            )
        response.background = background
        return response

    # -- recovery codes ---------------------------------------------------------------
    @reg.route(RECOVERY_PAGE, level=Level.SECOND_FACTOR)
    async def recovery_page(request: Request):
        portal, session = _portal(request), _session(request)
        status = await portal.factors.status(session.email)
        return portal.render(
            "recovery_manage.html", csrf_token=_csrf(portal, session), left=status.recovery_left
        )

    @reg.route(
        RECOVERY_PAGE, level=Level.SECOND_FACTOR, methods=["POST"],
        stepup=require_stepup(max_age=300, return_to=RECOVERY_PAGE),
    )
    async def recovery_regenerate(request: Request):
        portal, session = _portal(request), _session(request)
        result = await portal.factors.regenerate_codes(
            session, _ip(request), _ua(request), _rid(request)
        )
        if not result.ok:
            return _prompt(RECOVERY_PAGE) if result.reason == fsvc.STEPUP_REQUIRED else _see("/account")
        return portal.render(
            "recovery_codes.html", csrf_token=_csrf(portal, session), codes=result.codes
        )

    @reg.route("/mfa/recovery-codes/saved", level=Level.SECOND_FACTOR, methods=["POST"])
    async def recovery_saved(request: Request):
        return _see("/account")

    # -- account ------------------------------------------------------------------------
    @reg.route("/account", level=Level.SECOND_FACTOR)
    async def account(request: Request):
        portal, session = _portal(request), _session(request)
        status = await portal.factors.status(session.email)
        rows = await portal.sessions.list_live(session.email)
        shown = [
            {
                "id": str(row.id),
                "current": row.id == session.id,
                "created": row.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                "last_seen": row.last_seen_at.strftime("%Y-%m-%d %H:%M UTC"),
                "ip": row.ip or "-",
            }
            for row in rows
        ]
        return portal.render(
            "account.html", csrf_token=_csrf(portal, session), email=session.email,
            left=status.recovery_left, sessions=shown,
        )

    @reg.route("/account/sessions/revoke-others", level=Level.SECOND_FACTOR, methods=["POST"])
    async def account_revoke_others(request: Request):
        portal, session = _portal(request), _session(request)
        await portal.sessions.revoke_all(
            session.email, keep=session.id, by=session.email, reason="revoked_by_owner",
            ip=_ip(request), user_agent=_ua(request), request_id=_rid(request),
        )
        return _see("/account")

    @reg.route("/account/sessions/{session_id}/revoke", level=Level.SECOND_FACTOR, methods=["POST"])
    async def account_revoke(request: Request, session_id: uuid.UUID):
        portal, session = _portal(request), _session(request)
        await portal.sessions.revoke_own(
            session, session_id, _ip(request), _ua(request), _rid(request)
        )
        return _see("/account")
