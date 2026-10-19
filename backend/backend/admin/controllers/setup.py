"""The first-run setup wizard's pages (``services/setup_wizard.py`` has the rules).

Every route here is under ``/setup`` and declares its stage (default deny):

* ``OPEN``: ``GET|POST /setup``, the token page. Reachable only while no admin has
  a confirmed second factor and a valid token waits; otherwise the bare 404 every
  unknown path gets. A wrong token, an unlisted address, a rate limit and a spent
  token all answer alike. The token travels in the POST body only.
* ``CHECKLIST``: ``/setup/mail*`` and ``/setup/finish``, for the signed-in admin
  who redeemed the token (until finished or two hours later). Anything that writes
  needs a fresh second-factor code.

The second-factor enrolment between the two stages is the portal's own
(``controllers/mfa.py``), unchanged; its "Continue" button leads here.
"""

from __future__ import annotations

from fastapi import BackgroundTasks, Request
from fastapi.responses import RedirectResponse, Response

from backend.admin import cookies
from backend.admin.controllers.portal import (
    _field, _form_page, _ip, _portal, _rid, _schedule, _ua,
)
from backend.admin.gate.levels import Level, RouteRegistry, SetupStage
from backend.admin.security import csrf
from backend.admin.services import factors as fsvc
from backend.admin.services import setup_wizard as wiz

MAX_CODE = 24

REDEEM_EXEMPT = (
    "redeems the one-time setup token (constant time, 5 tries per address and 15 minutes, "
    "20 wrong tries lock the token) and writes only a session and audit rows"
)
CODE_EXEMPT = (
    "checks a fresh second-factor code itself, or the session's recent one, before it "
    "saves anything"
)
CLOSE_EXEMPT = "records that the operator finished the checklist; it changes no setting"

# the only text a notice can show
NOTICES = {
    "not_delivered": (
        "error",
        "The test mail could not be delivered with these settings. Nothing was saved. "
        "Check the server, port, security options and login, then try again.",
    ),
    "rate_limited": ("error", "Too many tries. Wait a few minutes and try again."),
    "expired": ("error", "The test expired. Fill in the form and send a new test mail."),
    "refused": ("error", "The settings were refused. Nothing was saved."),
    "wrong_code": ("error", "That code was not accepted."),
    "wrong_factor": ("error", "The authenticator code was not accepted. Nothing was saved."),
    "locked": ("error", "Too many wrong codes. Wait before trying again."),
    "needs_factor": ("error", "Enter a fresh code from your authenticator app to save."),
    "no_ack": ("error", "Tick the box to confirm that you backed up the master key."),
}


def _session(request: Request):
    return request.scope["state"]["session"]


def _csrf(portal, session) -> str:
    return csrf.session_token(portal.csrf_key, session.csrf_subject)


def _see(path: str) -> Response:
    return RedirectResponse(path, status_code=303)


def _notice(code):
    if code not in NOTICES:
        return None
    kind, text = NOTICES[code]
    return {"kind": kind, "text": text}


async def _mail_page(request: Request, status: int = 200, form=None, notice=None):
    portal, session = _portal(request), _session(request)
    defaults = await portal.setup.mail_form_defaults()
    values = dict(form.values) if form is not None else {}
    shown = {name: values.get(name, defaults.get(name, "")) for name, _ in wiz.MAIL_FIELDS}
    return portal.render(
        "setup_mail.html", status, csrf_token=_csrf(portal, session), email=session.email,
        values=shown, errors=form.errors if form is not None else {},
        field_errors=wiz.FIELD_ERRORS, password_saved=defaults.get("password_saved", False),
        source=portal.setup.mail_source(), notice=_notice(notice),
    )


def _code_page(request: Request, blob: str, status: int = 200, notice=None):
    portal, session = _portal(request), _session(request)
    return portal.render(
        "setup_mail_code.html", status, csrf_token=_csrf(portal, session), email=session.email,
        blob=blob, notice=_notice(notice),
    )


def register(reg: RouteRegistry) -> None:
    # -- step 1: the token (no session yet) -------------------------------------------
    @reg.route("/setup", level=Level.ADDRESS, setup=SetupStage.OPEN)
    async def token_page(request: Request):
        return _form_page(
            _portal(request), "setup.html", failed=request.query_params.get("failed") == "1"
        )

    @reg.route(
        "/setup", level=Level.ADDRESS, methods=["POST"], setup=SetupStage.ATTEMPT,
        stepup_exempt=REDEEM_EXEMPT,
    )
    async def token_submit(request: Request, background: BackgroundTasks):
        portal = _portal(request)
        result = await portal.setup.redeem(
            await _field(request, "token"), await _field(request, "email"),
            _ip(request), _ua(request), _rid(request),
        )
        _schedule(background, result.after)
        if not result.ok:
            # one answer for every refusal; the page itself is the bare 404 when setup is closed
            response = _see("/setup?failed=1")
        else:
            response = _see("/mfa/enrol")  # the portal's own enrolment, then back here
            cookies.set_cookie(response, cookies.SESSION_COOKIE, result.session_token)
            cookies.clear_cookie(response, cookies.FORM_COOKIE)
        response.background = background
        return response

    # -- step 3: mail (after enrolment) -----------------------------------------------
    @reg.route("/setup/mail", level=Level.SECOND_FACTOR, setup=SetupStage.CHECKLIST)
    async def mail_page(request: Request):
        return await _mail_page(request)

    @reg.route(
        "/setup/mail/test", level=Level.SECOND_FACTOR, methods=["POST"],
        setup=SetupStage.CHECKLIST,
        stepup=_require_stepup(),
    )
    async def mail_test(request: Request):
        portal, session = _portal(request), _session(request)
        form = await request.form()
        parsed = portal.setup.parse_mail_form(form)
        result = await portal.setup.start_mail_test(
            session, parsed, _ip(request), _ua(request), _rid(request)
        )
        if result.ok:
            return _code_page(request, result.blob)
        if result.reason == "invalid":
            return await _mail_page(request, 400, parsed)
        status = 429 if result.reason == "rate_limited" else 400
        return await _mail_page(request, status, parsed, result.reason)

    @reg.route(
        "/setup/mail/confirm", level=Level.SECOND_FACTOR, methods=["POST"],
        setup=SetupStage.CHECKLIST, stepup_exempt=CODE_EXEMPT,
    )
    async def mail_confirm(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        form = await request.form()
        blob = form.get("pending") if isinstance(form.get("pending"), str) else ""
        mail_code = await _field(request, "mail_code")
        factor_code = (await _field(request, "code"))[:MAX_CODE].strip()
        ip, ua, rid = _ip(request), _ua(request), _rid(request)
        if factor_code:
            outcome = await portal.factors.verify_stepup(session, factor_code, ip, ua, rid)
            _schedule(background, outcome.after)
            if not outcome.ok:
                locked = outcome.reason in (fsvc.LOCKED, fsvc.PAUSED)
                response = _code_page(
                    request, blob, 429 if locked else 200, "locked" if locked else "wrong_factor"
                )
                response.background = background
                return response
            session = await portal.sessions.reload(session) or session
        if not portal.sessions.stepup_fresh(session):
            response = _code_page(request, blob, 200, "needs_factor")
            response.background = background
            return response
        result = await portal.setup.confirm_mail(session, blob, mail_code, ip, ua, rid)
        if result.ok:
            response = _see("/setup/finish")
        elif result.reason == "wrong":
            response = _code_page(request, blob, 200, "wrong_code")
        elif result.reason == "locked":
            response = _code_page(request, blob, 429, "locked")
        else:  # expired or refused: start again
            response = await _mail_page(request, 400, None, result.reason)
        response.background = background
        return response

    @reg.route(
        "/setup/mail/skip", level=Level.SECOND_FACTOR, methods=["POST"],
        setup=SetupStage.CHECKLIST, stepup_exempt=CLOSE_EXEMPT,
    )
    async def mail_skip(request: Request):
        portal, session = _portal(request), _session(request)
        await portal.setup.skip_mail(session, _ip(request), _ua(request), _rid(request))
        return _see("/setup/finish")

    # -- step 4: the master key, then close ---------------------------------------------
    @reg.route("/setup/finish", level=Level.SECOND_FACTOR, setup=SetupStage.CHECKLIST)
    async def finish_page(request: Request):
        portal, session = _portal(request), _session(request)
        step = await portal.setup.mail_step()
        if step is None:
            return _see("/setup/mail")
        return portal.render(
            "setup_finish.html", csrf_token=_csrf(portal, session), email=session.email,
            fingerprint=portal.setup.fingerprint, mail_step=step, notice=None,
        )

    @reg.route(
        "/setup/finish", level=Level.SECOND_FACTOR, methods=["POST"],
        setup=SetupStage.CHECKLIST, stepup_exempt=CLOSE_EXEMPT,
    )
    async def finish_submit(request: Request, background: BackgroundTasks):
        portal, session = _portal(request), _session(request)
        step = await portal.setup.mail_step()
        if step is None:
            return _see("/setup/mail")
        if await _field(request, "ack") != "yes":
            return portal.render(
                "setup_finish.html", 400, csrf_token=_csrf(portal, session), email=session.email,
                fingerprint=portal.setup.fingerprint, mail_step=step, notice=_notice("no_ack"),
            )
        jobs = await portal.setup.finish(session, _ip(request), _ua(request), _rid(request))
        if jobs is None:
            return _see("/")
        _schedule(background, jobs)
        response = _see("/")
        response.background = background
        return response


def _require_stepup():
    from backend.admin.gate.stepup import require_stepup

    return require_stepup(max_age=300, return_to="/setup/mail")
