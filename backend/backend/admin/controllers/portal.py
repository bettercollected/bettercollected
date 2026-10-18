"""Routes of the admin portal: sign-in pages, logout, a minimal signed-in shell, a small JSON API and the stylesheet.

Levels: pages shown before sign-in are ``ADDRESS``; ``/mfa/enrol``, ``/mfa/verify``
and ``/logout`` are ``ADMIN`` (a session whose second factor is still pending can
reach them, narrowed by ``controllers/mfa.py``); everything else is
``SECOND_FACTOR``.
"""

from __future__ import annotations

import re
import uuid

from fastapi import BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from backend.admin import cookies
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.portal import STATIC_DIR, Portal
from backend.admin.security import csrf

MAX_FIELD = 400
STATIC_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\.css$")


def _portal(request: Request) -> Portal:
    return request.app.state.portal


def _ip(request: Request):
    return request.scope["state"].get("client_ip")


def _ua(request: Request):
    return request.headers.get("user-agent")


def _rid(request: Request):
    return request.scope["state"].get("request_id")


def _schedule(background: BackgroundTasks, jobs) -> None:
    """Run mail jobs after the response (each job returns an awaitable)."""
    for job in jobs:

        async def run(job=job):
            await job()

        background.add_task(run)


async def _field(request: Request, name: str) -> str:
    form = await request.form()
    value = form.get(name, "")
    return value[:MAX_FIELD] if isinstance(value, str) else ""


def _form_page(portal: Portal, template: str, status: int = 200, **context) -> Response:
    """A pre-sign-in page with a fresh double-submit token (cookie + hidden field)."""
    token = csrf.issue_form_token(portal.csrf_key, portal.clock)
    response = portal.render(template, status, csrf_token=token, **context)
    cookies.set_cookie(response, cookies.FORM_COOKIE, token, max_age=csrf.FORM_TOKEN_MAX_AGE)
    return response


def build_registry() -> RouteRegistry:
    reg = RouteRegistry()

    # -- stylesheet --------------------------------------------------------------
    @reg.route("/static/{name}", level=Level.ADDRESS)
    async def static_file(name: str):
        path = (STATIC_DIR / name) if STATIC_NAME.match(name) else None
        if path is None or not path.is_file() or path.is_symlink():
            return Response(status_code=404)
        return FileResponse(path, media_type="text/css")

    # -- before sign-in ----------------------------------------------------------
    @reg.route("/login", level=Level.ADDRESS)
    async def login_page(request: Request):
        return _form_page(_portal(request), "login.html")

    @reg.route("/login", level=Level.ADDRESS, methods=["POST"])
    async def login_submit(request: Request, background: BackgroundTasks):
        portal = _portal(request)
        email = await _field(request, "email")
        result = await portal.signin.request_code(email, _ip(request), _ua(request), _rid(request))
        _schedule(background, result.after)
        # the same answer for every address
        response = RedirectResponse("/login/code", status_code=303)
        cookies.set_cookie(
            response, cookies.CHALLENGE_COOKIE, result.cookie,
            max_age=portal.settings.code_ttl_seconds,
        )
        response.background = background
        return response

    @reg.route("/login/code", level=Level.ADDRESS)
    async def code_page(request: Request):
        return _form_page(_portal(request), "code.html", failed=False)

    @reg.route("/login/code", level=Level.ADDRESS, methods=["POST"])
    async def code_submit(request: Request, background: BackgroundTasks):
        portal = _portal(request)
        code = await _field(request, "code")
        result = await portal.signin.verify_code(
            cookies.read_cookie(request.scope, cookies.CHALLENGE_COOKIE),
            code, _ip(request), _ua(request), _rid(request),
        )
        _schedule(background, result.after)
        if not result.ok:
            response = _form_page(portal, "code.html", failed=True)
            response.background = background
            return response
        response = RedirectResponse("/mfa", status_code=303)
        cookies.set_cookie(response, cookies.SESSION_COOKIE, result.session_token)
        cookies.clear_cookie(response, cookies.CHALLENGE_COOKIE)
        cookies.clear_cookie(response, cookies.FORM_COOKIE)
        response.background = background
        return response

    # -- signed in, second factor pending: /mfa/* lives in controllers/mfa.py ------
    from backend.admin.controllers import mfa

    mfa.register(reg)

    @reg.route("/logout", level=Level.ADMIN, methods=["POST"])
    async def logout(request: Request):
        portal = _portal(request)
        session = request.scope["state"]["session"]
        await portal.sessions.logout(session, _ip(request), _ua(request), _rid(request))
        response = RedirectResponse("/login", status_code=303)
        cookies.clear_cookie(response, cookies.SESSION_COOKIE)
        return response

    # -- fully signed in -----------------------------------------------------------
    @reg.route("/", level=Level.SECOND_FACTOR)
    async def home(request: Request):
        portal = _portal(request)
        session = request.scope["state"]["session"]
        token = csrf.session_token(portal.csrf_key, str(session.id))
        return portal.render("home.html", csrf_token=token, email=session.email)

    @reg.route("/api/me", level=Level.SECOND_FACTOR)
    async def me(request: Request):
        session = request.scope["state"]["session"]
        return {"email": session.email, "mfa_state": session.mfa_state}

    @reg.route("/api/sessions", level=Level.SECOND_FACTOR)
    async def list_sessions(request: Request):
        portal = _portal(request)
        session = request.scope["state"]["session"]
        rows = await portal.sessions.list_live(session.email)
        return [
            {
                "id": str(row.id),
                "current": row.id == session.id,
                "created_at": row.created_at.isoformat(),
                "last_seen_at": row.last_seen_at.isoformat(),
            }
            for row in rows
        ]

    @reg.route("/api/sessions/revoke-others", level=Level.SECOND_FACTOR, methods=["POST"])
    async def revoke_others(request: Request):
        portal = _portal(request)
        session = request.scope["state"]["session"]
        count = await portal.sessions.revoke_all(
            session.email, keep=session.id, by=session.email,
            reason="revoked_by_owner", ip=_ip(request), user_agent=_ua(request),
            request_id=_rid(request),
        )
        return {"revoked": count}

    @reg.route("/api/sessions/{session_id}/revoke", level=Level.SECOND_FACTOR, methods=["POST"])
    async def revoke_session(request: Request, session_id: uuid.UUID):
        portal = _portal(request)
        session = request.scope["state"]["session"]
        args = (_ip(request), _ua(request), _rid(request))
        if await portal.sessions.revoke_own(session, session_id, *args):
            return {"revoked": 1}
        # not the caller's own session: another admin's needs a fresh step-up
        outcome = await portal.sessions.revoke_other_admin(session, session_id, *args)
        if outcome is None:
            return JSONResponse({"error": "stepup_required"}, status_code=403)
        return JSONResponse({"revoked": int(outcome)}, status_code=200 if outcome else 404)

    return reg
