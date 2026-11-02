"""Reading the workspace audit log (``AUDIT_LOG_UI_ENABLED``): a keyset page of
``workspace_audit_events`` for staff holding ``audit.read``, newest first.

Rules this module keeps:

* Read only. Reading the log is not itself audited (an export would be, in its
  own phase); nothing here writes.
* Every query carries the workspace id from the path, and a form id from the
  path or a filter is only ever compared with that workspace's rows: no id
  reaches across workspaces. A form feed answers 404 for a form that is not the
  workspace's, exactly like every other form route.
* The reply is built field by field from ``AuditEntryDto``: nothing stored is
  passed through. A response id goes only to someone who may read that form's
  responses, a session id only to an Owner or an Admin, so a Privacy officer
  sees who did what to which form and when, and never an answer, a link to one
  or a session.
* Ids become names here, once per page and inside this workspace: current
  members by display name (never an address), anyone else as ``former`` with no
  name; forms by their current title; teams by their current name. The names
  are the only thing that needs the auth service, which gets a short timeout
  and whose failure only means "name unavailable".
* Only kinds of the catalogue are ever read, so a kind of the schema that is
  not listed (the account-level second-factor events) can never appear.
"""

import datetime as dt
from http import HTTPStatus
from typing import Dict, List, Optional, Sequence

from common.constants import MESSAGE_FORBIDDEN
from common.ids import RecordId
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.audit_log_dto import (
    AuditEntryDto,
    AuditLabelsDto,
    AuditPageDto,
    FormLabelDto,
    MemberLabelDto,
    TeamLabelDto,
)
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.app.services.audit_log import catalog
from backend.app.services.audit_log.mode import refuse_when_off
from backend.app.services.audit_log.retention import retention_days
from backend.app.services.sso.policy import (
    AUDIT_PAGE_MAX,
    AUDIT_PAGE_SIZE,
    decode_audit_cursor,
    encode_audit_cursor,
)

# Names are looked up on every visit of the page: the auth service gets this
# long, then the page shows "name unavailable" instead of waiting for it.
NAMES_TIMEOUT_SECONDS = 3

MEMBER = "member"
FORMER = "former"
AVAILABLE = "available"
GONE = "gone"

INVALID_FILTER_CODE = "invalid_filter"


def _invalid(message: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": INVALID_FILTER_CODE, "message": message},
    )


def _aware(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class AuditLogReader:
    def __init__(
        self,
        authorization_service,
        audit_repo,
        workspace_form_repo,
        group_repo,
        member_directory,
    ):
        self._authorization = authorization_service
        self._audit = audit_repo
        self._forms = workspace_form_repo
        self._groups = group_repo
        self._members = member_directory

    # -- the two routes -------------------------------------------------------
    async def workspace_page(
        self,
        workspace_id: RecordId,
        user: User,
        cursor: Optional[str] = None,
        limit: int = AUDIT_PAGE_SIZE,
        areas: Sequence[str] = (),
        events: Sequence[str] = (),
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        form_id: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ) -> AuditPageDto:
        """``audit.read``: the workspace's entries."""
        refuse_when_off()
        kinds = self._kinds(areas, events, since, until)
        base = await self._gate(user, workspace_id, None)
        return await self._page(
            workspace_id,
            user,
            base,
            cursor,
            limit,
            kinds,
            form_id=form_id,
            actor=actor,
            target=target,
            involving=involving,
            since=since,
            until=until,
        )

    async def form_page(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User,
        cursor: Optional[str] = None,
        limit: int = AUDIT_PAGE_SIZE,
        areas: Sequence[str] = (),
        events: Sequence[str] = (),
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ) -> AuditPageDto:
        """``audit.read`` and a form of this workspace (404 otherwise): the
        entries about that form."""
        refuse_when_off()
        kinds = self._kinds(areas, events, since, until)
        base = await self._gate(user, workspace_id, str(form_id))
        return await self._page(
            workspace_id,
            user,
            base,
            cursor,
            limit,
            kinds,
            form_id=str(form_id),
            actor=actor,
            target=target,
            involving=involving,
            since=since,
            until=until,
        )

    # -- permissions ----------------------------------------------------------
    async def _gate(self, user: User, workspace_id, form_id: Optional[str]):
        """403 without ``audit.read``; with a form, 404 when it is not this
        workspace's (or is closed to the caller) and, while form-level access is
        on, the permission is the one held on that form (a Privacy officer
        keeps it on a restricted form, a grantee Editor never held it). Returns
        the caller's workspace-level access."""
        if form_id is not None:
            await self._authorization.authorize(
                user, Permission.AUDIT_READ, workspace_id, form_id=form_id
            )
            return await self._authorization.base_access(user, workspace_id)
        base = await self._authorization.base_access(
            user, workspace_id, raise_sso_required=True
        )
        if Permission.AUDIT_READ not in base.permissions:
            raise HTTPException(HTTPStatus.FORBIDDEN, MESSAGE_FORBIDDEN)
        return base

    # -- the page -------------------------------------------------------------
    @staticmethod
    def _kinds(areas, events, since, until) -> Sequence[str]:
        try:
            kinds = catalog.kinds_of(areas, events)
        except ValueError:
            raise _invalid("That type of entry is not one the audit log lists.")
        if since is not None and until is not None and _aware(since) > _aware(until):
            raise _invalid("The start of the range is after its end.")
        return kinds

    async def _page(
        self,
        workspace_id,
        user: User,
        base,
        cursor: Optional[str],
        limit: int,
        kinds: Sequence[str],
        *,
        form_id: Optional[str],
        actor: Optional[str],
        target: Optional[str],
        involving: Optional[str],
        since: Optional[dt.datetime],
        until: Optional[dt.datetime],
    ) -> AuditPageDto:
        limit = max(1, min(int(limit or AUDIT_PAGE_SIZE), AUDIT_PAGE_MAX))
        before = decode_audit_cursor(cursor) if cursor else None
        rows = await self._audit.page(
            workspace_id,
            limit + 1,
            before,
            events=kinds,
            form_id=form_id,
            actor=actor,
            target=target,
            involving=involving,
            since=_aware(since),
            until=_aware(until),
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_audit_cursor(rows[-1]) if more and rows else None

        readable = await self._readable_responses(user, workspace_id, rows)
        entries = [
            self._entry(row, readable, may_see_sessions=bool(base.privileged))
            for row in rows
        ]
        return AuditPageDto(
            entries=entries,
            next_cursor=next_cursor,
            labels=await self._labels(workspace_id, rows),
            retention_days=await retention_days(workspace_id),
        )

    async def _readable_responses(self, user, workspace_id, rows) -> Optional[set]:
        """The forms (of this page) whose responses the caller may read; None
        means every form. One decision for the whole page, none when no entry
        carries a response id."""
        forms = {r.form_id for r in rows if r.response_id and r.form_id}
        if not forms:
            return set()
        visible = await self._authorization.visible_form_ids(
            user, workspace_id, Permission.RESPONSE_READ, forms
        )
        return None if visible is None else set(visible)

    @staticmethod
    def _entry(
        row: WorkspaceAuditEventDocument, readable: Optional[set], may_see_sessions: bool
    ) -> AuditEntryDto:
        may_open_response = bool(row.response_id) and (
            readable is None or (row.form_id or "") in readable
        )
        return AuditEntryDto(
            id=str(row.id),
            event=row.event,
            area=catalog.area_of(row.event) or "",
            at=row.created_at,
            actor_id=row.user_id or None,
            session_id=row.session_id if may_see_sessions else None,
            target_user_id=row.target_user_id,
            to_user_id=row.to_user_id,
            form_id=row.form_id,
            response_id=row.response_id if may_open_response else None,
            revision=row.revision,
            group_id=row.group_id,
            grant_role=row.grant_role,
            grant_export=row.grant_export,
            access_mode=row.access_mode,
            linked=row.linked,
            scim_group_id=row.scim_group_id,
            role=row.role,
            previous_role=row.previous_role,
            count=row.count,
            required=row.required,
            export_channel=row.export_channel,
            export_format=row.export_format,
            key_id=row.key_id,
            reason=row.reason,
            key_role=row.key_role,
            key_role_before=row.key_role_before,
            form_scope=row.form_scope,
            widened=row.widened,
            method=row.method,
            path=row.path,
        )

    # -- ids to names ---------------------------------------------------------
    async def _labels(
        self, workspace_id, rows: List[WorkspaceAuditEventDocument]
    ) -> AuditLabelsDto:
        people = {
            str(i)
            for r in rows
            for i in (r.user_id, r.target_user_id, r.to_user_id)
            if i
        }
        forms = {str(r.form_id) for r in rows if r.form_id}
        teams = {str(r.group_id) for r in rows if r.group_id}

        members: Dict[str, MemberLabelDto] = {}
        if people:
            roles, names = await self._members.lookup(
                workspace_id, people, timeout=NAMES_TIMEOUT_SECONDS
            )
            for person in people:
                if person in roles:
                    members[person] = MemberLabelDto(
                        status=MEMBER, name=names.get(person)
                    )
                else:
                    # not (or no longer) a member: no name, whatever the auth
                    # service knows
                    members[person] = MemberLabelDto(status=FORMER)

        form_labels: Dict[str, FormLabelDto] = {}
        if forms:
            titles = await self._forms.titles_in_workspace(workspace_id, forms)
            for form in forms:
                form_labels[form] = (
                    FormLabelDto(status=AVAILABLE, title=titles[form])
                    if form in titles
                    else FormLabelDto(status=GONE)
                )

        team_labels: Dict[str, TeamLabelDto] = {}
        if teams:
            names_of = await self._groups.names_of(workspace_id, teams)
            for team in teams:
                team_labels[team] = (
                    TeamLabelDto(status=AVAILABLE, name=names_of[team])
                    if team in names_of
                    else TeamLabelDto(status=GONE)
                )
        return AuditLabelsDto(members=members, forms=form_labels, teams=team_labels)
