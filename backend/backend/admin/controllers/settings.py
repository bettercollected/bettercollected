"""The portal's settings pages (write side): list, detail and edit, history,
integrity check and the notification outbox.

Every route is ``Level.SECOND_FACTOR``. State changes take two steps because the
portal has no script: the edit form (which includes a fresh second-factor code)
posts to ``/settings/<key>/prepare``, which validates, checks the code, seals the
pending value and answers with an "apply" page holding a single-use token; that
page posts to ``/settings/<key>/set|clear|restore|purge-history``, which are
``ActionBound``: the token must be issued for exactly this action, key, value
and the version the admin saw. ``prepare`` is the only mutating settings route
without a token, and it changes nothing: it spends a code attempt and mints a
token. No value ever appears in a URL, a log line or an audit row; a secret
also never appears in HTML (the pending value is an AES-GCM blob).
"""

from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks, Request
from fastapi.responses import RedirectResponse, Response

from backend.admin.controllers.pages import _page, _session
from backend.admin.controllers.portal import _ip, _portal, _rid, _schedule, _ua
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.stepup import ActionBound
from backend.admin.security.ratelimit import Rule
from backend.admin.services import factors as fsvc
from backend.admin.services import settings_pages as sp
from backend.admin.services.settings_store import HISTORY_KEEP, Actor, SettingsError
from backend.admin.services.stepup import TOKEN_SECONDS, action_hash
from common.settings.registry import Tier, ValidationError

MAX_VALUE = 20000
MAX_CODE = 24
VERIFY_RULE = Rule("settings_verify", 3, 60)
PREPARE_EXEMPT = (
    "verifies a fresh second-factor code and mints a single-use token bound to one "
    "action; it writes nothing (the set, clear, restore and purge routes are action-bound)"
)
VERIFY_EXEMPT = "read-only verification of the store, rate limited; it writes nothing"


def _see(path: str, notice: Optional[str] = None) -> Response:
    if notice:
        path = f"{path}?notice={notice}"
    return RedirectResponse(path, status_code=303)


def _detail_path(key: str) -> str:
    return f"/settings/{key}"


def _history_path(key: str) -> str:
    return f"/settings/{key}/history"


def _back(action: str, key: str) -> str:
    return _history_path(key) if action in ("restore", "purge_history") else _detail_path(key)


def _text(form, name: str, limit: int = MAX_VALUE) -> str:
    value = form.get(name, "")
    return value[:limit] if isinstance(value, str) else ""


def _material(portal, session, action: str, key: str, version: int, form):
    """What the action is bound to: the sealed new value (set), the version to
    restore, or nothing. ``sp.is_missing`` when it cannot be established."""
    if action == "set":
        return sp.open_pending(
            portal.pending_key, portal.clock, session.id, action, key, version, form.get("pending")
        )
    if action == "restore":
        target = sp.parse_int(form.get("version"), 1)
        return target if target is not None else sp.MISSING
    return None


def _parts(action: str):
    async def parts(request: Request):
        portal, session = _portal(request), _session(request)
        key = sp.key_or_none(request.path_params.get("key"))
        form = await request.form()
        version = sp.parse_int(form.get("expected_version"))
        if key is None or version is None:
            return ("invalid",)
        material = _material(portal, session, action, key, version, form)
        if sp.is_missing(material):
            return ("invalid",)
        return (key, portal.settings_pages.service.action_hash(action, key, material, version))

    return parts


def _refused_to(request: Request) -> str:
    key = sp.key_or_none(request.path_params.get("key"))
    return f"{_detail_path(key) if key else '/settings'}?notice=step_up_invalid"


def register(reg: RouteRegistry) -> None:
    # -- read-only pages ------------------------------------------------------------
    @reg.route("/settings", level=Level.SECOND_FACTOR)
    async def settings_list(request: Request):
        portal = _portal(request)
        config = await portal.pages.config()
        section = request.query_params.get("section") or ""
        tier = request.query_params.get("tier") or ""
        notice = sp.notice_view(request.query_params.get("notice"))
        if (section and section not in config.sections) or (tier and tier not in config.tiers):
            bad = "section" if section and section not in config.sections else "tier"
            return await _page(
                request, "settings.html", "settings", 400, config=config, rows=[], section="",
                tier="", error=bad, notice=notice,
            )
        rows = [
            r for r in config.rows
            if (not section or r.section == section) and (not tier or r.tier == tier)
        ]
        return await _page(
            request, "settings.html", "settings", config=config, rows=rows, section=section,
            tier=tier, error=None, notice=notice,
        )

    @reg.route("/settings/integrity", level=Level.SECOND_FACTOR)
    async def integrity_page(request: Request):
        portal = _portal(request)
        return await _page(
            request, "integrity.html", "settings", result=portal.integrity_status(),
            notice=sp.notice_view(request.query_params.get("notice")),
        )

    @reg.route(
        "/settings/integrity/run", level=Level.SECOND_FACTOR, methods=["POST"],
        stepup_exempt=VERIFY_EXEMPT,
    )
    async def integrity_run(request: Request):
        portal, session = _portal(request), _session(request)
        decision = await portal.limiter.hit(VERIFY_RULE, portal.limiter.email_key(session.email))
        if not decision.allowed:
            return await _page(
                request, "integrity.html", "settings", 429, result=portal.integrity_status(),
                notice=sp.notice_view("rate_limited"),
            )
        try:
            result = await portal.settings_pages.run_verify(portal.board)
        except Exception:  # noqa: BLE001 - class only, never the cause
            return await _page(
                request, "integrity.html", "settings", 500, result=portal.integrity_status(),
                notice=sp.notice_view("failed"),
            )
        return await _page(request, "integrity.html", "settings", result=result, notice=None)

    @reg.route("/settings/notifications", level=Level.SECOND_FACTOR)
    async def notifications_page(request: Request):
        items = await _portal(request).settings_pages.notifications()
        return await _page(request, "notifications.html", "settings", items=items)

    @reg.route("/settings/{key}", level=Level.SECOND_FACTOR)
    async def setting_page(request: Request, key: str):
        detail = await _detail_or_none(request, key)
        if isinstance(detail, Response):
            return detail
        return await _page(
            request, "setting.html", "settings", detail=detail, form_value=detail.form_value,
            error=None, notice=sp.notice_view(request.query_params.get("notice")),
            confirm=None,
        )

    @reg.route("/settings/{key}/history", level=Level.SECOND_FACTOR)
    async def history_page(request: Request, key: str):
        detail = await _detail_or_none(request, key)
        if isinstance(detail, Response):
            return detail
        items = await _portal(request).settings_pages.history(key)
        restore = None
        wanted = sp.parse_int(request.query_params.get("restore"), 1)
        if wanted is not None:
            restore = next((i for i in items if i.version == wanted and i.restorable), None)
        return await _page(
            request, "setting_history.html", "settings", detail=detail, items=items,
            restore=restore, keep=HISTORY_KEEP,
            notice=sp.notice_view(request.query_params.get("notice")),
        )

    # -- step 1: check the code, mint the token ----------------------------------------
    @reg.route(
        "/settings/{key}/prepare", level=Level.SECOND_FACTOR, methods=["POST"],
        stepup_exempt=PREPARE_EXEMPT,
    )
    async def prepare(request: Request, background: BackgroundTasks, key: str):
        portal, session = _portal(request), _session(request)
        service = portal.settings_pages.service
        form = await request.form()
        action = _text(form, "action", 20)
        if action not in sp.ACTIONS:
            return _see("/settings", "bad_request")
        if sp.key_or_none(key) is None:
            return _see("/settings", "unknown_key")
        why = sp.refusal_code(service.registry, key)
        if why:
            return _see(_detail_path(key) if why != "unknown_key" else "/settings", why)
        spec = service.registry.get(key)
        back = _back(action, key)
        version = sp.parse_int(_text(form, "expected_version", 12))
        if version is None:
            return _see(back, "bad_request")
        detail = await portal.settings_pages.detail(key)
        if detail is None or detail.version != version:
            return _see(back, "stale_version")

        # what the action is bound to
        confirmation = _text(form, "confirmation", 80)
        sealed = None
        if action == "set":
            pending = form.get("pending")
            if isinstance(pending, str) and pending:
                material = sp.open_pending(
                    portal.pending_key, portal.clock, session.id, action, key, version, pending
                )
                if sp.is_missing(material):
                    return _see(back, "step_up_invalid")
            else:
                raw = _text(form, "value")
                try:
                    material = service.registry.validate(key, raw)
                except ValidationError as exc:
                    return await _page(
                        request, "setting.html", "settings", 400, detail=detail,
                        form_value="" if spec.is_secret else raw,
                        error=_rule_text(spec, exc), notice=None, confirm=None,
                    )
            sealed = sp.seal_pending(
                portal.pending_key, portal.clock, session.id, action, key, version, material
            )
        elif action == "restore":
            material = sp.parse_int(_text(form, "version", 12), 1)
            if material is None:
                return _see(back, "no_such_version")
        else:
            material = None
            if action == "purge_history":
                if not spec.is_secret:
                    return _see(back, "not_secret")
                if _text(form, "confirm_purge", 8) != "yes":
                    return _see(back, "purge_unconfirmed")

        async def again(notice: str, status: int = 400) -> Response:
            if action == "set":  # keep the sealed value: nothing to retype
                return await _confirm(request, detail, sealed, notice, status)
            return _see(back, notice)

        if spec.tier is Tier.T3 and confirmation != key:
            return await again("confirmation_required")

        result = await portal.factors.verify_stepup(
            session, _text(form, "code", MAX_CODE), _ip(request), _ua(request), _rid(request)
        )
        _schedule(background, result.after)
        if not result.ok:
            locked = result.reason in (fsvc.LOCKED, fsvc.PAUSED)
            response = await again("locked" if locked else "wrong_code", 429 if locked else 200)
            response.background = background
            return response
        fresh = await portal.sessions.reload(session)
        token = None
        if fresh is not None:
            token = portal.stepup.issue(
                fresh,
                action_hash(
                    f"settings.{action}", key, service.action_hash(action, key, material, version)
                ),
            )
        if token is None:
            return _see(back, "step_up_required")
        response = await _page(
            request, "setting_apply.html", "settings", detail=detail, action=action,
            url_name=sp.URL_NAMES[action], token=token, pending=sealed, version=version,
            target=material if action == "restore" else None, confirmation=confirmation,
            new_value=None if (action != "set" or spec.is_secret) else sp.display_value(spec, material),
            seconds=min(TOKEN_SECONDS, sp.PENDING_SECONDS),
        )
        response.background = background
        return response

    # -- step 2: the action-bound routes ------------------------------------------------
    def make(action: str) -> None:
        @reg.route(
            f"/settings/{{key}}/{sp.URL_NAMES[action]}", level=Level.SECOND_FACTOR,
            methods=["POST"],
            stepup=ActionBound(f"settings.{action}", _parts(action), _refused_to),
        )
        async def apply(request: Request, key: str):
            portal, session = _portal(request), _session(request)
            service = portal.settings_pages.service
            form = await request.form()
            back = _back(action, key)
            version = sp.parse_int(_text(form, "expected_version", 12))
            material = _material(portal, session, action, key, version or 0, form)
            if version is None or sp.is_missing(material):
                return _see(back, "step_up_invalid")
            actor = Actor(
                "admin", session.email, str(session.id), _ip(request), _ua(request), _rid(request)
            )
            step = sp.step_up_for(
                service, action, key, material, version, session.email, portal.clock.now()
            )
            common = {"step_up": step, "confirmation": _text(form, "confirmation", 80),
                      "expected_version": version}
            try:
                if action == "set":
                    change = await service.set(key, material, actor, **common)
                    done = "done_set" if change.changed else "no_change"
                elif action == "clear":
                    await service.clear(key, actor, **common)
                    done = "done_clear"
                elif action == "restore":
                    await service.restore(key, material, actor, **common)
                    done = "done_restore"
                else:
                    await service.purge_history(key, actor, **common)
                    done = "done_purge"
            except SettingsError as error:
                return _see(back, sp.notice_for_error(error))
            return _see(_history_path(key) if action == "purge_history" else _detail_path(key), done)

    for name in sp.ACTIONS:
        make(name)


async def _detail_or_none(request: Request, key: str):
    if sp.key_or_none(key) is None:
        return _see("/settings", "unknown_key")
    detail = await _portal(request).settings_pages.detail(key)
    return detail if detail is not None else _see("/settings", "unknown_key")


def _rule_text(spec, exc: ValidationError) -> str:
    """The rule a value broke. A secret only ever gets a fixed sentence."""
    if spec.is_secret:
        return "The secret was not accepted: it must be non-empty, without surrounding whitespace, and strong enough."
    message = str(exc)
    return message.split(": ", 1)[1] if ": " in message else sp.NOTICES["invalid_value"][1]


async def _confirm(request: Request, detail, sealed: str, notice: str, status: int):
    """The code (and typed confirmation) form again, holding the sealed value."""
    return await _page(
        request, "setting.html", "settings", status, detail=detail, form_value="", error=None,
        notice=sp.notice_view(notice), confirm={"pending": sealed},
    )
