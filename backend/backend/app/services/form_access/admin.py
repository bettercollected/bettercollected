"""Managing form-level access: teams (member groups), the grants on one form
and a form's access mode (docs/enterprise-access-model.md, "Form-level scope").

Every route here answers 422 ``form_access_off`` while ``FORM_ACCESS_ENABLED``
is off (the one exception, ``GET .../access``, says ``enabled: false``), and
writes nothing then. Teams need ``members.manage`` (owners and admins); grants
and the mode need ``form.share`` **on that form**, plus the rules of who may
widen the circle:

* a grant is at most the grantor's own role on the form (what a grant gives is
  a subset of what the grantor holds there), never ``export`` unless the
  grantor is an Owner or Admin, never to oneself, never to a Privacy officer
  (a grant does not apply to one: it would be a row that does nothing);
* on a restricted form only an Owner, an Admin or the form's creator manage
  the circle (a grantee who can edit the form cannot widen who sees it), and
  only they change the mode.

Every team, grant and mode change is written to the audit log **before** it is
made (``audit.record_or_refuse``), ids only. The person, the team and the form
a request names are looked up inside the workspace first (the same 404 whether
they do not exist or belong to another workspace) and checked again by the
write itself. The request's remembered decisions are dropped after every write.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Dict, List, Literal, Optional

from common.ids import RecordId
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy.exc import IntegrityError

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    canonical_role,
    is_owner_membership,
)
from backend.app.repositories.postgres.form_access import (
    AccessTargetNotFound,
    PostgresFormAccessGrantRepository,
)
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.member_groups import (
    PostgresMemberGroupRepository,
    TeamFull,
    TeamLimit,
)
from backend.app.schemas.form_access_grant import (
    ROLE_REVIEWER,
    ROLE_VIEWER,
    MEMBER_SUBJECTS,
    SUBJECT_GROUP,
    SUBJECT_USER,
    FormAccessGrantDocument,
)
from backend.app.schemas.member_group import MemberGroupDocument, name_key
from backend.app.schemas.workspace_audit_event import (
    ACCESS_GRANT_ADDED,
    ACCESS_GRANT_CHANGED,
    ACCESS_GRANT_REMOVED,
    ACCESS_MODE_CHANGED,
    TEAM_CREATED,
    TEAM_DELETED,
    TEAM_MEMBER_ADDED,
    TEAM_MEMBER_REMOVED,
    TEAM_RENAMED,
)
from backend.app.services.form_access import audit
from backend.app.services.form_access.cleanup import FormAccessCleanup
from backend.app.services.form_access.mode import form_access_enabled, refuse_when_off
from backend.app.services.form_access.model import GRANT_PERMISSIONS, is_restricted

# at most this many teams in a workspace, and members in a team
MAX_TEAMS = 20
MAX_TEAM_MEMBERS = 500
MAX_NAME = 80
MAX_DESCRIPTION = 280

_ID = re.compile(r"^[0-9a-f]{24}$")


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# -- teams ---------------------------------------------------------------------
class TeamCreateDto(_Model):
    name: str = Field(..., max_length=400)
    description: Optional[str] = Field(None, max_length=2000)


class TeamUpdateDto(_Model):
    name: Optional[str] = Field(None, max_length=400)
    description: Optional[str] = Field(None, max_length=2000)


class TeamDto(_Model):
    id: str
    name: str
    description: Optional[str] = None
    # "manual": the members are the ones listed; "directory" (later): the
    # members come from a linked directory group
    source: str = "manual"
    member_count: int = 0
    # how many directory groups feed the team (FORM_ACCESS_ENABLED; a number
    # only, the groups are listed by the directory settings)
    linked_groups: int = 0
    created_at: Optional[str] = None


class TeamMemberDto(_Model):
    user_id: str
    name: Optional[str] = None
    role: Optional[str] = None
    # in the team through a linked directory group: removed by the directory,
    # not here
    via_directory: bool = False


class TeamDetailDto(TeamDto):
    members: List[TeamMemberDto] = []
    # the forms the team holds a grant on
    form_count: int = 0


# -- grants and the mode -----------------------------------------------------------
class GrantRequestDto(_Model):
    subject_type: Literal["user", "group"]
    subject_id: str = Field(..., max_length=64)
    role: Literal["EDITOR", "REVIEWER", "VIEWER"]
    # may export responses (Reviewer and Viewer grants; owners and admins only)
    export: bool = False


class ModeRequestDto(_Model):
    mode: Literal["workspace", "restricted"]


class GrantDto(_Model):
    id: str
    subject_type: str
    subject_id: str
    role: str
    export: bool = False
    # a person: their name when known; a team: its name
    name: Optional[str] = None
    # a person whose membership is disabled: the grant does nothing until they
    # are enabled again
    disabled: bool = False
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    # who gave it, by name (a current member's; none for anyone else: best
    # effort, like every name here)
    granted_by: Optional[str] = None
    # a team grant: how many people the team has (one number, never who)
    member_count: Optional[int] = None
    # only in a member's own access view: the form the grant is on and its
    # title, left out for a form the caller may not open
    form_id: Optional[str] = None
    form_title: Optional[str] = None


class FormAccessDto(_Model):
    """What the Access settings of a form show."""

    enabled: bool
    # the stored choice: workspace, restricted, or none (not chosen: a Private
    # form then counts as restricted)
    access_mode: Optional[str] = None
    restricted: bool = False
    # what the caller may do on this form, and where it comes from
    my_permissions: List[str] = []
    source: Optional[str] = None
    # the caller may change the mode and the circle
    can_manage: bool = False
    # the people and teams with a grant (for whoever may share the form)
    grants: Optional[List[GrantDto]] = None


class CandidateMemberDto(_Model):
    id: str
    name: Optional[str] = None


class CandidateTeamDto(_Model):
    id: str
    name: str
    member_count: int = 0


class CandidatesDto(_Model):
    """Who may be given access to one form, for whoever holds ``form.share``
    on it: names and ids to pick from, and a team's size. No address, no role,
    no grant."""

    members: List[CandidateMemberDto] = []
    teams: List[CandidateTeamDto] = []


class ImpactDto(_Model):
    """What changing a form's mode would do (a dry run: nothing is changed or
    recorded)."""

    mode: str
    # active members who open the form now and would no longer (restricting a
    # form: everyone whose role gave them the form and who is not an owner, an
    # admin, the creator or a grantee); 0 for any other change
    members_losing_access: int = 0


class MemberAccessDto(_Model):
    """What one member holds beyond their role (the Members page)."""

    teams: List[TeamDto] = []
    grants: List[GrantDto] = []


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _valid_id(value) -> Optional[str]:
    text = str(value or "")
    return text if _ID.match(text) else None


def _not_found(message: str = "Not found") -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, message)


def _refused(code: str, message: str, status: int = HTTPStatus.FORBIDDEN) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message})


def _clean(value: Optional[str], limit: int, required: bool, field: str) -> Optional[str]:
    text = " ".join(str(value or "").split())
    if not text:
        if required:
            raise _refused(
                f"invalid_{field}", f"The {field} can't be empty.", HTTPStatus.UNPROCESSABLE_ENTITY
            )
        return None
    if len(text) > limit or any(ord(char) < 32 for char in text):
        raise _refused(
            f"invalid_{field}",
            f"The {field} is too long or holds characters that aren't allowed.",
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    return text


class FormAccessAdminService:
    def __init__(
        self,
        authorization_service,
        form_access,
        group_repo: PostgresMemberGroupRepository,
        grant_repo: PostgresFormAccessGrantRepository,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        workspace_user_repo,
        workspace_repo,
        audit_repo,
        cleanup: FormAccessCleanup,
        member_directory=None,
        form_repo=None,
        scim_group_repo=None,
    ):
        self._authz = authorization_service
        self._form_access = form_access
        self._groups = group_repo
        self._grants = grant_repo
        self._links = workspace_form_repo
        self._members = workspace_user_repo
        self._workspaces = workspace_repo
        self._audit = audit_repo
        self._cleanup = cleanup
        self._directory = member_directory
        self._forms = form_repo
        self._scim_groups = scim_group_repo

    async def _linked_counts(self, workspace_id) -> Dict[str, int]:
        if self._scim_groups is None:
            return {}
        return await self._scim_groups.link_counts(workspace_id)

    # ------------------------------------------------------------------ teams
    async def _manage_teams(self, workspace_id, user) -> None:
        await self._authz.authorize(user, Permission.MEMBERS_MANAGE, workspace_id)
        refuse_when_off()

    def _team_dto(
        self, team: MemberGroupDocument, count: int = 0, linked: int = 0
    ) -> TeamDto:
        return TeamDto(
            id=str(team.id),
            name=team.name,
            description=team.description,
            source=team.source,
            member_count=count,
            linked_groups=linked,
            created_at=_iso(team.created_at),
        )

    async def _team(self, workspace_id, group_id) -> MemberGroupDocument:
        found = (
            await self._groups.find(workspace_id, group_id)
            if _valid_id(group_id)
            else None
        )
        if found is None:
            raise _not_found("Team not found")
        return found

    async def _current_dto(self, team: MemberGroupDocument) -> TeamDto:
        return self._team_dto(
            team,
            len(await self._groups.member_ids(team.workspace_id, team.id)),
            (await self._linked_counts(team.workspace_id)).get(str(team.id), 0),
        )

    async def list_teams(self, workspace_id, user) -> List[TeamDto]:
        await self._manage_teams(workspace_id, user)
        counts = await self._groups.member_counts(workspace_id)
        linked = await self._linked_counts(workspace_id)
        teams = await self._groups.list_in_workspace(workspace_id)
        return [
            self._team_dto(team, counts.get(str(team.id), 0), linked.get(str(team.id), 0))
            for team in sorted(teams, key=lambda t: t.name_key)
        ]

    async def create_team(self, workspace_id, request: TeamCreateDto, user) -> TeamDto:
        await self._manage_teams(workspace_id, user)
        name = _clean(request.name, MAX_NAME, True, "name")
        description = _clean(request.description, MAX_DESCRIPTION, False, "description")
        if await self._groups.find_by_name(workspace_id, name) is not None:
            raise self._name_taken()
        team = MemberGroupDocument(
            id=RecordId(),
            workspace_id=RecordId(str(workspace_id)),
            name=name,
            description=description,
            created_by=str(user.id),
        )
        await audit.record_or_refuse(
            self._audit, TEAM_CREATED, workspace_id, user, group_id=str(team.id)
        )
        try:
            await self._groups.create(team, max_teams=MAX_TEAMS)
        except IntegrityError:
            raise self._name_taken() from None
        except TeamLimit:
            raise _refused(
                "too_many_teams",
                f"A workspace has at most {MAX_TEAMS} teams.",
                HTTPStatus.CONFLICT,
            ) from None
        self._form_access.invalidate()
        return self._team_dto(team)

    @staticmethod
    def _name_taken() -> HTTPException:
        return _refused(
            "team_name_taken",
            "A team with this name already exists.",
            HTTPStatus.CONFLICT,
        )

    async def get_team(self, workspace_id, group_id, user) -> TeamDetailDto:
        await self._manage_teams(workspace_id, user)
        team = await self._team(workspace_id, group_id)
        by_hand = set(await self._groups.manual_member_ids(workspace_id, team.id))
        member_ids = await self._groups.member_ids(workspace_id, team.id)
        roles, names = (
            await self._directory.lookup(workspace_id, member_ids)
            if self._directory is not None
            else ({}, {})
        )
        members = [
            TeamMemberDto(
                user_id=member,
                name=names.get(member),
                role=roles.get(member),
                via_directory=member not in by_hand,
            )
            for member in member_ids
        ]
        linked = (await self._linked_counts(workspace_id)).get(str(team.id), 0)
        grants = await self._cleanup.count_team_grants(workspace_id, team.id)
        return TeamDetailDto(
            **self._team_dto(team, len(member_ids), linked).model_dump(),
            members=members,
            form_count=grants,
        )

    async def update_team(
        self, workspace_id, group_id, request: TeamUpdateDto, user
    ) -> TeamDto:
        await self._manage_teams(workspace_id, user)
        team = await self._team(workspace_id, group_id)
        fields = request.model_fields_set
        name = team.name
        description = team.description
        if "name" in fields:
            name = _clean(request.name, MAX_NAME, True, "name")
        if "description" in fields:
            description = _clean(request.description, MAX_DESCRIPTION, False, "description")
        if name == team.name and description == team.description:
            return await self._current_dto(team)
        if name_key(name) != team.name_key:
            other = await self._groups.find_by_name(workspace_id, name)
            if other is not None and str(other.id) != str(team.id):
                raise self._name_taken()
        await audit.record_or_refuse(
            self._audit, TEAM_RENAMED, workspace_id, user, group_id=str(team.id)
        )
        try:
            # under the team's row lock, and never an insert: a team deleted
            # meanwhile stays deleted
            saved = await self._groups.rename(workspace_id, team.id, name, description)
        except IntegrityError:
            raise self._name_taken() from None
        if saved is None:
            raise _not_found("Team not found")
        return await self._current_dto(saved)

    async def delete_team(self, workspace_id, group_id, user) -> None:
        await self._manage_teams(workspace_id, user)
        team = await self._team(workspace_id, group_id)
        grants = await self._cleanup.count_team_grants(workspace_id, team.id)
        await audit.record_or_refuse(
            self._audit,
            TEAM_DELETED,
            workspace_id,
            user,
            group_id=str(team.id),
            count=grants,
        )
        await self._cleanup.forget_team(workspace_id, team.id)

    async def add_team_member(self, workspace_id, group_id, member_id, user) -> None:
        await self._manage_teams(workspace_id, user)
        team = await self._team(workspace_id, group_id)
        member = await self._active_member(workspace_id, member_id)
        if str(member.user_id) in await self._groups.manual_member_ids(
            workspace_id, team.id
        ):
            return  # already listed: nothing changes, nothing to record
        await audit.record_or_refuse(
            self._audit,
            TEAM_MEMBER_ADDED,
            workspace_id,
            user,
            group_id=str(team.id),
            target_user_id=str(member.user_id),
        )
        try:
            await self._groups.add_member(
                workspace_id, team.id, member.user_id, max_members=MAX_TEAM_MEMBERS
            )
        except AccessTargetNotFound:
            raise _not_found("Team or member not found") from None
        except TeamFull:
            raise _refused(
                "team_full",
                f"A team has at most {MAX_TEAM_MEMBERS} members.",
                HTTPStatus.CONFLICT,
            ) from None
        self._form_access.invalidate()

    async def remove_team_member(self, workspace_id, group_id, member_id, user) -> None:
        await self._manage_teams(workspace_id, user)
        team = await self._team(workspace_id, group_id)
        by_hand = await self._groups.manual_member_ids(workspace_id, team.id)
        if not _valid_id(member_id) or str(member_id) not in by_hand:
            if _valid_id(member_id) and str(member_id) in await self._groups.member_ids(
                workspace_id, team.id
            ):
                # in through a linked directory group: the directory decides
                raise _refused(
                    "managed_by_directory",
                    "This person is in the team through a directory group. "
                    "Remove them from that group in your directory.",
                    HTTPStatus.CONFLICT,
                )
            raise _not_found("Not a member of this team")
        await audit.record_or_refuse(
            self._audit,
            TEAM_MEMBER_REMOVED,
            workspace_id,
            user,
            group_id=str(team.id),
            target_user_id=str(member_id),
        )
        await self._groups.remove_member(workspace_id, team.id, member_id)
        self._form_access.invalidate()

    async def _active_member(self, workspace_id, member_id):
        """The membership of an active member of this workspace, or the 404 of
        a person who isn't one (another workspace's member included)."""
        found = (
            await self._members.find_workspace_user(workspace_id, member_id)
            if _valid_id(member_id)
            else None
        )
        if found is None or found.disabled:
            raise _not_found("Member not found")
        return found

    async def member_access(self, workspace_id, member_id, user) -> MemberAccessDto:
        """What one member holds beyond their role: their teams and the grants
        made to them (for the Members page)."""
        await self._manage_teams(workspace_id, user)
        if not _valid_id(member_id) or (
            await self._members.find_workspace_user(workspace_id, member_id)
        ) is None:
            raise _not_found("Member not found")
        team_ids = set(await self._groups.group_ids_of(workspace_id, member_id))
        teams = [
            self._team_dto(team)
            for team in await self._groups.list_in_workspace(workspace_id)
            if str(team.id) in team_ids
        ]
        grants = await self._grants.direct_for_user(workspace_id, member_id)
        names, disabled, sizes = await self._names(workspace_id, grants)
        titles = await self._visible_titles(workspace_id, grants, user)
        dtos = []
        for grant in grants:
            dto = self._grant_dto(grant, names, disabled, sizes)
            if str(grant.form_id) in titles:
                dto.form_id = str(grant.form_id)
                dto.form_title = titles[str(grant.form_id)]
            dtos.append(dto)
        return MemberAccessDto(teams=teams, grants=dtos)

    async def _visible_titles(self, workspace_id, grants, user) -> Dict[str, Optional[str]]:
        """form id -> title for the forms of ``grants`` that are the
        workspace's and that ``user`` may open: a grant on any other form says
        nothing of it (no id, no title)."""
        form_ids = list(dict.fromkeys(str(g.form_id) for g in grants))
        if not form_ids or self._forms is None:
            return {}
        linked = {
            str(link.form_id) for link in await self._links.list_in_workspace(workspace_id)
        }
        form_ids = [f for f in form_ids if f in linked]
        form_ids = await self._authz.restrict_to_visible(
            user, workspace_id, form_ids, Permission.FORM_READ
        )
        if not form_ids:
            return {}
        return {
            str(form.form_id): form.title
            for form in await self._forms.get_forms_by_form_ids(form_ids)
        }

    # ------------------------------------------------------------ one form
    async def _form(self, workspace_id, form_id, user, permission: Permission):
        """The caller's standing on one form: ``(link, base, held, may_manage,
        restricted)``. The permission is checked on the form (a form closed to
        the caller, or not the workspace's, is the 404 of an unknown form)."""
        await self._authz.authorize(user, permission, workspace_id, form_id=form_id)
        base = await self._authz.base_access(user, workspace_id)
        decided = await self._authz.form_permissions(user, workspace_id, form_id)
        link = await self._links.find_workspace_form(workspace_id, str(form_id))
        if link is None:
            raise _not_found("Form not found in workspace")
        settings = link.settings
        restricted = is_restricted(
            getattr(settings, "access_mode", None), getattr(settings, "hidden", None)
        )
        may_manage = base.privileged or str(link.user_id) == str(user.id)
        return link, base, decided, may_manage, restricted

    def _grant_dto(
        self,
        grant: FormAccessGrantDocument,
        names: Optional[Dict[str, str]] = None,
        disabled: Optional[set] = None,
        sizes: Optional[Dict[str, int]] = None,
    ) -> GrantDto:
        is_team = grant.subject_type == SUBJECT_GROUP
        return GrantDto(
            id=str(grant.id),
            subject_type=grant.subject_type,
            subject_id=str(grant.subject_id),
            role=grant.role,
            export=bool(grant.export),
            name=(names or {}).get(str(grant.subject_id)),
            disabled=str(grant.subject_id) in (disabled or set()),
            created_by=grant.created_by,
            created_at=_iso(grant.created_at),
            granted_by=(
                (names or {}).get(str(grant.created_by)) if grant.created_by else None
            ),
            member_count=(sizes or {}).get(str(grant.subject_id), 0) if is_team else None,
        )

    async def get_access(self, workspace_id, form_id, user) -> FormAccessDto:
        link, base, decided, may_manage, restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_READ
        )
        if not form_access_enabled():
            return FormAccessDto(enabled=False)
        held = decided.permissions
        grants: Optional[List[GrantDto]] = None
        if Permission.FORM_SHARE in held:
            stored = await self._grants.list_for_form(workspace_id, form_id)
            names, disabled, sizes = await self._names(workspace_id, stored)
            grants = [self._grant_dto(g, names, disabled, sizes) for g in stored]
        return FormAccessDto(
            enabled=True,
            access_mode=getattr(link.settings, "access_mode", None),
            restricted=restricted,
            my_permissions=sorted(p.value for p in held),
            source=decided.source,
            can_manage=Permission.FORM_SHARE in held and (may_manage or not restricted),
            grants=grants,
        )

    async def _names(self, workspace_id, grants):
        """``(names, disabled, sizes)`` for ``grants``: display names (a
        team's name, a person's and a granter's when the lookup finds one: a
        current member's only), the persons whose membership is disabled, and
        each team's size."""
        names: Dict[str, str] = {}
        disabled = set()
        sizes: Dict[str, int] = {}
        people = [str(g.subject_id) for g in grants if g.subject_type == SUBJECT_USER]
        granters = [str(g.created_by) for g in grants if g.created_by]
        if any(g.subject_type == SUBJECT_GROUP for g in grants):
            for team in await self._groups.list_in_workspace(workspace_id):
                names[str(team.id)] = team.name
            sizes = await self._groups.member_counts(workspace_id)
        if people:
            for member in await self._members.get_workspace_users(workspace_id):
                if member.disabled and str(member.user_id) in people:
                    disabled.add(str(member.user_id))
        if (people or granters) and self._directory is not None:
            _, found = await self._directory.lookup(
                workspace_id, list(dict.fromkeys(people + granters))
            )
            names.update(found)
        return names, disabled, sizes

    async def set_mode(
        self, workspace_id, form_id, request: ModeRequestDto, user
    ) -> FormAccessDto:
        refuse_when_off()
        link, _base, _decided, may_manage, _restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_SHARE
        )
        if not may_manage:
            raise _refused(
                "access_manage_forbidden",
                "Only an owner, an admin or the person who created the form can "
                "change who may open it.",
            )
        stored = getattr(link.settings, "access_mode", None)
        if stored != request.mode:
            await audit.record_or_refuse(
                self._audit,
                ACCESS_MODE_CHANGED,
                workspace_id,
                user,
                form_id=str(form_id),
                access_mode=request.mode,
            )
            try:
                await self._links.set_access_mode(workspace_id, str(form_id), request.mode)
            finally:
                self._form_access.invalidate()
        return await self.get_access(workspace_id, form_id, user)

    async def candidates(self, workspace_id, form_id, user) -> CandidatesDto:
        """The people and teams of this workspace who could be given access to
        this form, for whoever may change its circle but cannot list the
        members (an Editor who created it): names and ids, a team's size.
        Reads the same people the circle manager may then name in a grant, and
        nothing else (no address, no role, no grant); records nothing."""
        refuse_when_off()
        _link, _base, _decided, may_manage, restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_SHARE
        )
        self._refuse_unless_circle_manager(restricted, may_manage)
        workspace = await self._workspaces.find_by_id(workspace_id)
        # no one who always has access, no privacy officer (a grant does
        # nothing for one), no deactivated member, not the caller
        never_granted = {
            WorkspaceRoles.OWNER,
            WorkspaceRoles.ADMIN,
            WorkspaceRoles.PRIVACY_OFFICER,
        }
        eligible = [
            str(member.user_id)
            for member in await self._members.get_workspace_users(workspace_id)
            if not member.disabled
            and str(member.user_id) != str(user.id)
            and not is_owner_membership(workspace, member)
            and not ({canonical_role(role) for role in (member.roles or [])} & never_granted)
        ]
        names: Dict[str, str] = {}
        if eligible and self._directory is not None:
            _, names = await self._directory.lookup(workspace_id, eligible)
        # a person the directory cannot name (a deleted account) is not offered
        members = sorted(
            (
                CandidateMemberDto(id=member, name=names[member])
                for member in eligible
                if member in names
            ),
            key=lambda m: ((m.name or "").casefold(), m.id),
        )
        counts = await self._groups.member_counts(workspace_id)
        teams = [
            CandidateTeamDto(
                id=str(team.id), name=team.name, member_count=counts.get(str(team.id), 0)
            )
            for team in sorted(
                await self._groups.list_in_workspace(workspace_id),
                key=lambda t: t.name_key,
            )
        ]
        return CandidatesDto(members=members, teams=teams)

    async def impact(self, workspace_id, form_id, mode: str, user) -> ImpactDto:
        """A dry run of ``set_mode``: how many active members would lose access
        to the form (and so its answers) if it were restricted. Only whoever
        may change the mode asks; nothing is changed or recorded; a count,
        never names."""
        refuse_when_off()
        _link, _base, _decided, may_manage, restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_SHARE
        )
        if not may_manage:
            raise _refused(
                "access_manage_forbidden",
                "Only an owner, an admin or the person who created the form can "
                "change who may open it.",
            )
        losing = 0
        if mode == "restricted" and not restricted:
            now = await self._authz.member_ids_holding(
                workspace_id, form_id, Permission.FORM_READ
            )
            after = await self._authz.member_ids_holding(
                workspace_id, form_id, Permission.FORM_READ, restricted=True
            )
            if now is not None and after is not None:
                losing = len(now - after)
        return ImpactDto(mode=mode, members_losing_access=losing)

    async def put_grant(
        self, workspace_id, form_id, request: GrantRequestDto, user
    ) -> GrantDto:
        refuse_when_off()
        link, base, decided, may_manage, restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_SHARE
        )
        self._refuse_unless_circle_manager(restricted, may_manage)
        if not GRANT_PERMISSIONS[request.role] <= decided.permissions:
            raise _refused(
                "grant_above_own_role",
                "You can't give a role with more access than your own on this form.",
            )
        if request.export and not base.privileged:
            raise _refused(
                "export_grant_reserved",
                "Only an owner or an admin can allow exporting responses.",
            )
        subject_id = _valid_id(request.subject_id)
        if subject_id is None:
            raise _not_found("Not found")
        if request.subject_type == SUBJECT_USER:
            if subject_id == str(user.id):
                raise _refused(
                    "cannot_grant_self", "You can't change your own access to a form."
                )
            membership = await self._members.find_workspace_user(workspace_id, subject_id)
            if membership is None:
                raise _not_found("Member not found")
            if WorkspaceRoles.PRIVACY_OFFICER in {
                canonical_role(role) for role in (membership.roles or [])
            }:
                raise _refused(
                    "privacy_officer_cannot_be_granted",
                    "A privacy officer never reads answers, so a grant to one would "
                    "do nothing.",
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
        elif await self._groups.find(workspace_id, subject_id) is None:
            raise _not_found("Team not found")
        existing = next(
            (
                grant
                for grant in await self._grants.list_for_form(workspace_id, form_id)
                if grant.subject_type == request.subject_type
                and str(grant.subject_id) == subject_id
            ),
            None,
        )
        if existing is not None and existing.export and not base.privileged:
            raise _refused(
                "export_grant_reserved",
                "Only an owner or an admin can change a grant that allows exporting "
                "responses.",
            )
        # an Editor grant exports anyway: the flag only means something for
        # the other two roles
        export = bool(request.export) and request.role in (ROLE_REVIEWER, ROLE_VIEWER)
        grant = FormAccessGrantDocument(
            workspace_id=RecordId(str(workspace_id)),
            form_id=str(link.form_id),
            subject_type=request.subject_type,
            subject_id=subject_id,
            role=request.role,
            export=export,
            created_by=(existing.created_by if existing else str(user.id)),
        )
        ids = {"form_id": str(link.form_id), "grant_role": grant.role, "grant_export": export}
        ids["target_user_id" if request.subject_type == SUBJECT_USER else "group_id"] = (
            subject_id
        )
        await audit.record_or_refuse(
            self._audit,
            ACCESS_GRANT_CHANGED if existing else ACCESS_GRANT_ADDED,
            workspace_id,
            user,
            **ids,
        )
        try:
            saved = await self._grants.put(grant)
        except AccessTargetNotFound:
            raise _not_found("Not found") from None
        finally:
            self._form_access.invalidate()
        names, disabled, sizes = await self._names(workspace_id, [saved])
        return self._grant_dto(saved, names, disabled, sizes)

    async def delete_grant(self, workspace_id, form_id, grant_id, user) -> None:
        refuse_when_off()
        _link, base, decided, may_manage, restricted = await self._form(
            workspace_id, form_id, user, Permission.FORM_SHARE
        )
        self._refuse_unless_circle_manager(restricted, may_manage)
        grant = (
            await self._grants.find(workspace_id, form_id, grant_id)
            if _valid_id(grant_id)
            else None
        )
        if grant is None or grant.subject_type not in MEMBER_SUBJECTS:
            # (the repository already finds people's and teams' grants only: an
            # API key's row is not a grant of this route, and is never named
            # in its audit entry)
            raise _not_found("Grant not found")
        if not base.privileged:
            # the same caps as giving it: no taking away, then giving back
            # something the giver may not give
            if not GRANT_PERMISSIONS.get(grant.role, frozenset()) <= decided.permissions:
                raise _refused(
                    "grant_above_own_role",
                    "You can't change a role with more access than your own on this form.",
                )
            if grant.export:
                raise _refused(
                    "export_grant_reserved",
                    "Only an owner or an admin can change a grant that allows exporting "
                    "responses.",
                )
        if (
            not base.privileged
            and grant.subject_type == SUBJECT_USER
            and str(grant.subject_id) == str(user.id)
        ):
            raise _refused(
                "cannot_grant_self", "You can't change your own access to a form."
            )
        ids = {"form_id": str(form_id), "grant_role": grant.role, "grant_export": bool(grant.export)}
        ids["target_user_id" if grant.subject_type == SUBJECT_USER else "group_id"] = str(
            grant.subject_id
        )
        await audit.record_or_refuse(
            self._audit, ACCESS_GRANT_REMOVED, workspace_id, user, **ids
        )
        try:
            await self._grants.delete(workspace_id, form_id, grant_id)
        finally:
            self._form_access.invalidate()

    @staticmethod
    def _refuse_unless_circle_manager(restricted: bool, may_manage: bool) -> None:
        if restricted and not may_manage:
            raise _refused(
                "access_manage_forbidden",
                "On a restricted form only an owner, an admin or the person who "
                "created it decide who may open it.",
            )
