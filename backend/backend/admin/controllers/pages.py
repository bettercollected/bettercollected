"""The portal's read-only pages: dashboard, health, configuration, metrics,
audit log and sessions, plus ``GET /api/audit``.

Every route is ``Level.SECOND_FACTOR`` and ``GET``: nothing here changes state.
(The session forms on ``/sessions`` post to the account routes that already
exist, with the session's CSRF token.) No route under ``/settings`` or
``/tasks`` is registered here; those prefixes are reserved for later pages whose
mutating routes must declare a step-up. (They live in ``controllers/settings.py``.)
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.admin.controllers.portal import _portal
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.portal import Portal
from backend.admin.security import csrf
from backend.admin.services import pages as pg

MASTER_KEY_REMINDER = (
    "Back up SETTINGS_MASTER_KEY now and keep the copy somewhere separate from the "
    "server. It cannot be recovered: without it the stored secrets and the "
    "second-factor enrolments cannot be opened."
)
SHORT = 8


def _session(request: Request):
    return request.scope["state"]["session"]


async def _shell(request: Request, active: str) -> dict:
    """What every signed-in page's header needs."""
    portal, session = _portal(request), _session(request)
    pending = await portal.pages.restart_pending()
    banners = []
    if pending:
        banners.append({"kind": "restart", "services": ", ".join(pending)})
    last = portal.integrity.last
    if last is not None and last.problems:
        banners.append({"kind": "integrity", "count": len(last.problems)})
    return {
        "active": active,
        "email": session.email,
        "csrf_token": csrf.session_token(portal.csrf_key, session.csrf_subject),
        "banners": banners,
        "master_key_reminder": MASTER_KEY_REMINDER,
    }


async def _page(request: Request, template: str, active: str, status: int = 200, **context):
    return _portal(request).render(template, status, **(await _shell(request, active)), **context)


def _bad_request(request: Request, template: str, active: str, name: str, **context):
    return _page(request, template, active, 400, error=name, **context)


def register(reg: RouteRegistry) -> None:
    @reg.route("/", level=Level.SECOND_FACTOR)
    async def dashboard(request: Request):
        portal, session = _portal(request), _session(request)
        health = await portal.pages.health()
        config = await portal.pages.config()
        head = await portal.pages.audit(pg.AuditFilters(limit=1))
        live = await portal.pages.live_sessions(session.email)
        return await _page(
            request, "dashboard.html", "dashboard",
            health=health, config=config, audit=head, live_sessions=live,
        )

    @reg.route("/health", level=Level.SECOND_FACTOR)
    async def health_page(request: Request):
        return await _page(
            request, "health.html", "health", health=await _portal(request).pages.health(),
        )

    @reg.route("/config", level=Level.SECOND_FACTOR)
    async def config_page(request: Request):
        portal = _portal(request)
        config = await portal.pages.config()
        section = request.query_params.get("section") or ""
        tier = request.query_params.get("tier") or ""
        if (section and section not in config.sections) or (tier and tier not in config.tiers):
            return await _bad_request(
                request, "config.html", "config", "section" if section not in config.sections and section else "tier",
                config=config, rows=[], section="", tier="",
                admins=sorted(portal.settings.admin_emails),
            )
        rows = [
            r for r in config.rows
            if (not section or r.section == section) and (not tier or r.tier == tier)
        ]
        return await _page(
            request, "config.html", "config", config=config, rows=rows, section=section,
            tier=tier, error=None, admins=sorted(portal.settings.admin_emails),
        )

    @reg.route("/metrics", level=Level.SECOND_FACTOR)
    async def metrics_page(request: Request):
        counts, why = await _portal(request).pages.metrics()
        return await _page(request, "metrics.html", "metrics", counts=counts, why=why)

    def _filters(request: Request):
        return pg.parse_audit_filters(request.query_params)

    @reg.route("/audit", level=Level.SECOND_FACTOR)
    async def audit_page(request: Request):
        portal = _portal(request)
        try:
            filters = _filters(request)
        except pg.BadFilter as bad:
            return await _bad_request(
                request, "audit.html", "audit", bad.name,
                page=None, form={}, older_url=None, outcomes=sorted(pg.audit_service.OUTCOMES),
                pretty=pg.pretty, limit_max=pg.AUDIT_LIMIT_MAX,
            )
        page = await portal.pages.audit(filters)
        older = (
            "/audit?" + urlencode({**filters.raw, "before": page.next_before})
            if page.next_before else None
        )
        return await _page(
            request, "audit.html", "audit", page=page, form=filters.raw, error=None,
            older_url=older, outcomes=sorted(pg.audit_service.OUTCOMES), pretty=pg.pretty,
            limit_max=pg.AUDIT_LIMIT_MAX,
        )

    @reg.route("/api/audit", level=Level.SECOND_FACTOR)
    async def audit_api(request: Request):
        try:
            filters = _filters(request)
        except pg.BadFilter as bad:
            return JSONResponse({"error": "bad_filter", "parameter": bad.name}, status_code=400)
        page = await _portal(request).pages.audit(filters)
        return {
            "items": [pg.item_json(i) for i in page.items],
            "next_before": page.next_before,
            "head": {
                "seq": page.head_seq,
                "hash_prefix": page.head_hash_prefix,
                "at": page.head_at.isoformat() if page.head_at else None,
            },
        }

    @reg.route("/sessions", level=Level.SECOND_FACTOR)
    async def sessions_page(request: Request):
        portal, session = _portal(request), _session(request)
        rows = await portal.sessions.list_live(session.email)
        shown = [
            {
                "id": str(row.id),
                "current": row.id == session.id,
                "created": row.created_at,
                "last_seen": row.last_seen_at,
                "ip": row.ip or "-",
                "browser": row.ua_hash.hex()[:SHORT] if row.ua_hash else "-",
            }
            for row in rows
        ]
        return await _page(request, "sessions.html", "sessions", sessions=shown)
