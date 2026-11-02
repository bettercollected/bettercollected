"""How long a workspace's audit entries are kept (docs/audit-log.md).

An owner picks 6, 12, 24 or 60 months for the workspace; none is shorter than
six months and the default is twelve. The choice is a field of the workspace's
own document (``audit_retention_months``, no migration; None means the
default). This module is the one place that knows the choices and what they
come to in days: the reader asks here for the figure the page states, the daily
purge asks here for the cutoff it deletes by, and nothing else holds a number.

Rules this module keeps:

* Only an owner changes it, and the change is recorded first (the entry carries
  the months before and after, both enum-like whole numbers) or refused.
* A value that is not one of the choices (an edited document, an older build) is
  read as the default, never as a shorter period; and the cutoff of a purge is
  clamped so that it can never be newer than the minimum, whatever is stored.
* Shortening deletes nothing at once: the entries beyond the new period go at
  the next daily purge, and the reply says so. Lengthening cannot bring back
  what an earlier purge already deleted; the page says nothing of the past.
"""

import datetime as dt
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Optional, Tuple

from common.constants import MESSAGE_FORBIDDEN
from common.ids import RecordId
from common.models.user import User
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.audit_log_dto import AuditRetentionDto
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import AUDIT_RETENTION_CHANGED
from backend.app.services.audit_log.mode import refuse_when_off
from backend.app.services.form_access import audit

DEFAULT_MONTHS = 12
MINIMUM_MONTHS = 6
# the choices, shortest first, and what each comes to in days (a year is 365)
DAYS_OF_MONTHS: Dict[int, int] = {6: 183, 12: 365, 24: 730, 60: 1826}
CHOICES: Tuple[int, ...] = tuple(sorted(DAYS_OF_MONTHS))
MINIMUM_DAYS = DAYS_OF_MONTHS[MINIMUM_MONTHS]

INVALID_CODE = "invalid_retention"
BELOW_MINIMUM_CODE = "retention_below_minimum"


def months_of(stored: Any) -> int:
    """The months a stored value means: one of the choices, else the default."""
    try:
        months = int(str(stored).strip())
    except (TypeError, ValueError):
        return DEFAULT_MONTHS
    return months if months in DAYS_OF_MONTHS else DEFAULT_MONTHS


def days_of(months: int) -> int:
    """The days a period of ``months`` comes to; never below the minimum."""
    return max(DAYS_OF_MONTHS.get(months, DAYS_OF_MONTHS[DEFAULT_MONTHS]), MINIMUM_DAYS)


def cutoff(now: dt.datetime, months: int) -> dt.datetime:
    """Entries older than this are past a retention of ``months``."""
    return now - dt.timedelta(days=days_of(months))


def _refused(code: str, message: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.UNPROCESSABLE_ENTITY, {"code": code, "message": message}
    )


class AuditRetention:
    def __init__(self, authorization_service, workspace_repo, audit_repo):
        self._authorization = authorization_service
        self._workspaces = workspace_repo
        self._audit = audit_repo

    # -- the figure -----------------------------------------------------------
    async def months(self, workspace_id: RecordId) -> int:
        workspace = await self._workspaces.find_by_id(workspace_id)
        return months_of(getattr(workspace, "audit_retention_months", None))

    async def days(self, workspace_id: RecordId) -> int:
        """The number of days the entries of ``workspace_id`` are kept (what the
        page states)."""
        return days_of(await self.months(workspace_id))

    # -- the setting ----------------------------------------------------------
    async def overview(self, workspace_id: RecordId, user: User) -> AuditRetentionDto:
        """``audit.read``: the workspace's period, and whether the caller may
        change it."""
        refuse_when_off()
        base = await self._authorization.base_access(
            user, workspace_id, raise_sso_required=True
        )
        if Permission.AUDIT_READ not in base.permissions:
            raise HTTPException(HTTPStatus.FORBIDDEN, MESSAGE_FORBIDDEN)
        return await self._dto(
            workspace_id,
            can_change=await self._authorization.is_owner(user, workspace_id),
        )

    async def set_months(
        self, workspace_id: RecordId, user: User, months: int
    ) -> AuditRetentionDto:
        """Owners only. The change is recorded first (503 ``audit_unavailable``
        when it cannot be) and applies to entries at the next daily purge."""
        refuse_when_off()
        await self._authorization.require_owner(user, workspace_id)
        if months < MINIMUM_MONTHS:
            raise _refused(
                BELOW_MINIMUM_CODE,
                f"Audit entries are kept for at least {MINIMUM_MONTHS} months.",
            )
        if months not in DAYS_OF_MONTHS:
            raise _refused(
                INVALID_CODE,
                "Choose " + ", ".join(str(c) for c in CHOICES[:-1]) + f" or {CHOICES[-1]} months.",
            )
        workspace = await self._workspaces.get_or_404(workspace_id)
        previous = months_of(workspace.audit_retention_months)
        if months != previous:
            await audit.record_or_refuse(
                self._audit,
                AUDIT_RETENTION_CHANGED,
                workspace_id,
                user,
                retention_months=months,
                previous_retention_months=previous,
            )
            await self._workspaces.set_fields(
                workspace,
                {
                    "audit_retention_months": months,
                    "updated_at": dt.datetime.now(dt.timezone.utc),
                },
            )
        dto = await self._dto(workspace_id, can_change=True)
        dto.applies_at_next_purge = months < previous
        return dto

    async def _dto(self, workspace_id, can_change: bool) -> AuditRetentionDto:
        months = await self.months(workspace_id)
        return AuditRetentionDto(
            months=months,
            days=days_of(months),
            options=list(CHOICES),
            minimum_months=MINIMUM_MONTHS,
            default_months=DEFAULT_MONTHS,
            can_change=can_change,
        )

    # -- the daily purge ------------------------------------------------------
    async def purge(self, now: Optional[dt.datetime] = None) -> "PurgeResult":
        """Delete the entries past their workspace's period, each workspace by
        its own setting; entries of a workspace that never chose (and those
        that belong to no workspace) by the default. Never newer than the
        minimum, whatever is stored. Deletes in bounded batches, and a failure
        of one workspace (logged with its id only) never stops the others:
        the result says how many were deleted and how many parts failed."""
        if self._audit is None:
            return PurgeResult(0, 0)
        now = now or dt.datetime.now(dt.timezone.utc)
        chosen = {
            ws: months_of(value)
            for ws, value in (await self._workspaces.audit_retention_choices()).items()
        }
        result = PurgeResult(0, 0)
        try:
            result.deleted += await self._audit.purge_before(
                cutoff(now, DEFAULT_MONTHS), except_workspaces=list(chosen)
            )
        except Exception as error:  # noqa: BLE001 - the others still run
            result.failed += 1
            logger.bind(audit=True).error(
                "AUDIT purge of the default retention failed ({})", type(error).__name__
            )
        for workspace_id, months in chosen.items():
            try:
                result.deleted += await self._audit.purge_workspace_before(
                    workspace_id, cutoff(now, months)
                )
            except Exception as error:  # noqa: BLE001 - the next workspace still runs
                result.failed += 1
                logger.bind(audit=True).error(
                    "AUDIT purge failed workspace={} ({})",
                    workspace_id,
                    type(error).__name__,
                )
        return result


@dataclass
class PurgeResult:
    """How a purge went: entries deleted, and parts (a workspace, or the
    default period) that failed."""

    deleted: int
    failed: int
