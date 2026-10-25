"""Read-only SQL for the portal's pages. Nothing here writes.

The configuration query never selects a secret's value or blob: for a secret
row the ``value`` column is replaced by NULL in the statement itself, so a
secret cannot reach the process, let alone a page.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories.tables import audit_log, sessions


async def ping(conn: AsyncConnection) -> bool:
    return (await conn.execute(text("SELECT 1"))).scalar_one() == 1


async def service_states(conn: AsyncConnection) -> list[Any]:
    """One row per reporting service instance: names and numbers only."""
    return (
        await conn.execute(
            text(
                "SELECT service, instance, revision_applied, restart_pending, "
                "cardinality(rejected_keys) AS rejected, env_overrides, "
                "extract(epoch FROM (now() - reported_at))::bigint AS age_seconds "
                "FROM settings.service_state ORDER BY service, instance LIMIT 500"
            )
        )
    ).all()


async def manifest_revision(conn: AsyncConnection) -> Optional[int]:
    return (
        await conn.execute(text("SELECT revision FROM settings.manifest WHERE id = 1"))
    ).scalar_one_or_none()


async def entries_for_display(conn: AsyncConnection) -> list[Any]:
    """Settings rows without any secret material (see the module docstring)."""
    return (
        await conn.execute(
            text(
                "SELECT key, is_secret, cleared, version, source, updated_by, updated_at, "
                "CASE WHEN is_secret OR cleared THEN NULL ELSE value::text END AS value "
                "FROM settings.entries ORDER BY key"
            )
        )
    ).all()


def parse_json(raw: Any) -> Any:
    if isinstance(raw, (str, bytes)):
        return json.loads(raw)
    return raw


def _n(value: Any) -> int:
    """A count from a definer function's answer: a whole number or 0. The
    functions run as roles other services' owners could have put code in front of,
    so their answers are data to be checked, never trusted for shape."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(0, int(value))


def _section(source: Any, name: str) -> dict:
    value = source.get(name) if isinstance(source, dict) else None
    return value if isinstance(value, dict) else {}


def combine_counts(app: Any, auth: Any) -> dict:
    """The metrics page's counts from the two per-schema answers
    (``admin.platform_counts_app()`` and ``admin.platform_counts_auth()``),
    rebuilt field by field from whole numbers: unknown fields are dropped."""
    orgs, forms, creators = _section(app, "organizations"), _section(app, "forms"), _section(app, "form_creators")
    responses, responders = _section(app, "responses"), _section(app, "form_responders")
    users = _section(auth, "users")
    plans = _section(users, "by_plan")
    providers = forms.get("by_provider")
    by_provider = {}
    if isinstance(providers, dict):
        for name, count in list(providers.items())[:20]:
            if isinstance(name, str):
                by_provider[name[:40]] = _n(count)

    def week_start(value: Any) -> str:
        return value if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else ""

    new_users = {}
    auth_weeks = auth.get("weekly") if isinstance(auth, dict) else None
    for week in (auth_weeks if isinstance(auth_weeks, list) else [])[:12]:
        if isinstance(week, dict):
            new_users[week_start(week.get("week_start"))] = _n(week.get("new_users"))
    weekly = []
    app_weeks = app.get("weekly") if isinstance(app, dict) else None
    for week in (app_weeks if isinstance(app_weeks, list) else [])[:12]:
        if not isinstance(week, dict):
            continue
        start = week_start(week.get("week_start"))
        weekly.append(
            {
                "week_start": start,
                "new_users": new_users.get(start, 0),
                "new_organizations": _n(week.get("new_organizations")),
                "new_forms": _n(week.get("new_forms")),
                "responses": _n(week.get("responses")),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organizations": {
            "total": _n(orgs.get("total")),
            "new_last_30_days": _n(orgs.get("new_last_30_days")),
            "disabled": _n(orgs.get("disabled")),
        },
        "users": {
            "total": _n(users.get("total")),
            "new_last_30_days": _n(users.get("new_last_30_days")),
            "active_last_30_days": _n(users.get("active_last_30_days")),
            "by_plan": {"FREE": _n(plans.get("FREE")), "PRO": _n(plans.get("PRO"))},
        },
        "forms": {
            "total": _n(forms.get("total")),
            "published": _n(forms.get("published")),
            "new_last_30_days": _n(forms.get("new_last_30_days")),
            "by_provider": by_provider,
        },
        "form_creators": {
            "total": _n(creators.get("total")),
            "active_last_30_days": _n(creators.get("active_last_30_days")),
        },
        "responses": {
            "total": _n(responses.get("total")),
            "last_7_days": _n(responses.get("last_7_days")),
            "last_30_days": _n(responses.get("last_30_days")),
        },
        "form_responders": {
            "identified_responses": _n(responders.get("identified_responses")),
            "identified": _n(responders.get("identified")),
            "anonymous_responses": _n(responders.get("anonymous_responses")),
        },
        "weekly": weekly,
    }


async def platform_counts(conn: AsyncConnection) -> dict:
    """The platform counts: one definer function per owning schema, combined here
    (see postgres/ensure-admin-roles.sh). No function reads tables of two owners."""
    app = parse_json((await conn.execute(text("SELECT admin.platform_counts_app()"))).scalar_one())
    auth = parse_json((await conn.execute(text("SELECT admin.platform_counts_auth()"))).scalar_one())
    return combine_counts(app, auth)


# The other services' schemas, each read through its own definer functions
# (postgres/ensure-admin-roles.sh); the admin role has no access to the schemas.
OTHER_SCHEMA_FUNCTIONS = {
    "app": ("admin.schema_revision_app()", "admin.outbox_counts_app()"),
    "auth": ("admin.schema_revision_auth()", "admin.outbox_counts_auth()"),
    "google": ("admin.schema_revision_google()", "admin.outbox_counts_google()"),
}
_REVISION = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


async def schema_revisions(conn: AsyncConnection, schema: str) -> Optional[tuple[str, ...]]:
    """The schema's Alembic revision(s); ``None`` before its first migration.
    The answer is data from another owner: anything that is not a plain
    revision id is dropped."""
    function = OTHER_SCHEMA_FUNCTIONS[schema][0]
    raw = (await conn.execute(text(f"SELECT {function}"))).scalar_one()
    if raw is None:
        return None
    return tuple(sorted(v for v in raw if isinstance(v, str) and _REVISION.match(v)))


async def outbox_counts(conn: AsyncConnection, schema: str) -> Optional[tuple[int, int]]:
    """(unresolved, total) rows of the schema's mirror outbox; ``None`` before the
    table exists."""
    function = OTHER_SCHEMA_FUNCTIONS[schema][1]
    row = (await conn.execute(text(f"SELECT unresolved, total FROM {function}"))).one()
    if row.unresolved is None or row.total is None:
        return None
    return max(int(row.unresolved), 0), max(int(row.total), 0)


_AUDIT_COLUMNS = (
    audit_log.c.seq, audit_log.c.id, audit_log.c.at, audit_log.c.actor_kind,
    audit_log.c.actor_email, audit_log.c.ip, audit_log.c.action,
    audit_log.c.target_type, audit_log.c.target_id, audit_log.c.outcome,
    audit_log.c.before, audit_log.c.after, audit_log.c.detail, audit_log.c.request_id,
)


async def audit_page(
    conn: AsyncConnection,
    *,
    before_seq: Optional[int],
    actor: Optional[str],
    action: Optional[str],
    outcome: Optional[str],
    since: Optional[datetime],
    until: Optional[datetime],
    limit: int,
) -> list[Any]:
    """Newest first, ``seq < before_seq`` (keyset); ``limit + 1`` rows so the
    caller can tell whether another page exists."""
    where = []
    if before_seq is not None:
        where.append(audit_log.c.seq < before_seq)
    if actor:
        where.append(audit_log.c.actor_email == actor)
    if action:
        where.append(
            or_(
                audit_log.c.action == action,
                func.starts_with(audit_log.c.action, action + "."),
            )
        )
    if outcome:
        where.append(audit_log.c.outcome == outcome)
    if since is not None:
        where.append(audit_log.c.at >= since)
    if until is not None:
        where.append(audit_log.c.at < until)
    query = (
        select(*_AUDIT_COLUMNS)
        .where(and_(*where) if where else text("true"))
        .order_by(audit_log.c.seq.desc())
        .limit(limit + 1)
    )
    return (await conn.execute(query)).all()


async def audit_head(conn: AsyncConnection) -> Optional[tuple[int, bytes, datetime]]:
    row = (
        await conn.execute(
            select(audit_log.c.seq, audit_log.c.row_hash, audit_log.c.at)
            .order_by(audit_log.c.seq.desc())
            .limit(1)
        )
    ).first()
    return (row[0], bytes(row[1]), row[2]) if row else None


async def live_session_count(conn: AsyncConnection, email: str, now: datetime) -> int:
    return (
        await conn.execute(
            select(func.count())
            .select_from(sessions)
            .where(
                sessions.c.email == email,
                sessions.c.revoked_at.is_(None),
                sessions.c.idle_expires_at > now,
                sessions.c.abs_expires_at > now,
            )
        )
    ).scalar_one()
