"""Workspace API keys — the auth layer for MCP and the future public API.

Token format: ``bc_<64 hex chars>``. Only the SHA-256 lands in Mongo; the
full token is returned exactly once, at creation. Admin-only management;
authentication resolves a Bearer token to (workspace, scopes, acting user).
"""

import datetime as dt
import hashlib
import secrets
from http import HTTPStatus
from typing import Dict, List, Optional

from bson import ObjectId
from common.records import RecordId
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.repositories.postgres.identity import PostgresWorkspaceAPIKeyRepository
from backend.app.schemas.form_access_grant import SUBJECT_KEY, FormAccessGrantDocument
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_audit_event import (
    API_KEY_CREATED,
    API_KEY_FORM_ADDED,
    API_KEY_FORM_REMOVED,
    API_KEY_REVOKED,
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
    KEY_ROLE_AS_CREATOR,
    REVOKED_BY_ADMIN,
)
from backend.app.services.api_key_roles import validation
from backend.app.services.api_key_roles.mode import (
    refuse_setting_when_off,
    refuse_when_off,
)
from backend.app.services.api_key_roles.model import SCOPE_ALL, SCOPE_LISTED
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_access.audit import record_or_refuse
from backend.app.models.enum.permission import Permission

# Scopes gate tool/endpoint access. Deliberately coarse in v1.
VALID_SCOPES = {
    "forms:read",
    "forms:write",
    # its own scope: a key given out to edit forms never gains deleting
    # them (and their responses)
    "forms:delete",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
    # its own scope, never implied by another: the key writes responses as the
    # respondent's submit path accepts them (docs/submissions-api.md); only
    # while SUBMISSIONS_API_ENABLED is on
    "submissions:write",
}
SUBMISSIONS_SCOPE = "submissions:write"
# at most this many forms in a key's submission form list
MAX_SUBMISSION_FORMS = 200

TOKEN_PREFIX = "bc_"
# Scopes that hand respondents' answers, unredacted, to whatever holds the key.
UNREDACTED_RESPONSE_SCOPES = {"responses:read"}


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CreateAPIKeyDto(_CamelModel):
    name: str = Field(..., min_length=1, max_length=60)
    scopes: List[str] = Field(..., min_length=1)
    # required with responses:read: the admin acknowledges that the key gives
    # an external AI client full, unredacted answers
    acknowledge_unredacted_responses: bool = False
    # with submissions:write: the forms the key may submit to (none = every
    # form of the workspace); each must be a form of this workspace
    submission_form_ids: Optional[List[str]] = Field(
        None, max_length=MAX_SUBMISSION_FORMS
    )
    # API_KEY_ROLES_ENABLED: the most the key may do (EDITOR, REVIEWER, VIEWER or
    # PRIVACY_OFFICER; none = as its creator) and the forms it may open ("all",
    # the default, or "listed": only ``form_ids``). Setting either while the
    # switch is off answers 422 ``api_key_roles_off``.
    role: Optional[str] = Field(None, max_length=40)
    form_scope: Optional[str] = Field(None, max_length=10)
    form_ids: Optional[List[str]] = Field(None, max_length=MAX_SUBMISSION_FORMS)


class UpdateAPIKeyDto(_CamelModel):
    """What an edit may change: the name, the role and the forms, nothing else.
    What the key does (its scopes), who made it and its secret never change:
    that is a new key. A field left out stays as it is; ``role: null`` is "as
    its creator"."""

    model_config = ConfigDict(
        populate_by_name=True, alias_generator=to_camel, extra="forbid"
    )

    name: Optional[str] = Field(None, min_length=1, max_length=60)
    role: Optional[str] = Field(None, max_length=40)
    form_scope: Optional[str] = Field(None, max_length=10)
    form_ids: Optional[List[str]] = Field(None, max_length=MAX_SUBMISSION_FORMS)


class APIKeyFormDto(_CamelModel):
    """A form on a key's list: its id, and its title when the reader may see the
    form."""

    id: str
    title: Optional[str] = None


class APIKeyDto(_CamelModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    revoked: bool
    created_by: Optional[str] = None
    last_used_at: Optional[dt.datetime] = None
    responses_read_acknowledged_by: Optional[str] = None
    responses_read_acknowledged_at: Optional[dt.datetime] = None
    # forms a submissions:write key is limited to (None = every form)
    submission_form_ids: Optional[List[str]] = None
    # the most the key may do (None = as its creator), the forms it may open
    # ("all" or "listed") and, for a listed key, which. Shown as stored, whatever
    # the switch says.
    role: Optional[str] = None
    form_scope: str = SCOPE_ALL
    forms: List[APIKeyFormDto] = []


class CreatedAPIKeyDto(APIKeyDto):
    # The one and only time the full token leaves the server.
    token: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_dto(
    document: WorkspaceAPIKeyDocument, forms: Optional[List[APIKeyFormDto]] = None
) -> APIKeyDto:
    return APIKeyDto(
        id=str(document.id),
        name=document.name,
        prefix=document.prefix,
        scopes=document.scopes,
        revoked=document.revoked,
        created_by=document.created_by,
        last_used_at=document.last_used_at,
        responses_read_acknowledged_by=document.responses_read_acknowledged_by,
        responses_read_acknowledged_at=document.responses_read_acknowledged_at,
        submission_form_ids=document.submission_form_ids,
        role=document.role,
        form_scope=document.form_scope,
        forms=forms or [],
    )


def _c():
    # Resolved at call time: the container imports this module.
    from backend.app.container import container

    return container


def _role_value(role: Optional[str]) -> str:
    """What an audit entry says of a key's role: its name, or "creator"."""
    return KEY_ROLE_AS_CREATOR if role is None else role


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="API key not found")


class APIKeyService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        api_key_repo: PostgresWorkspaceAPIKeyRepository,
        audit_repo=None,
        grant_repo=None,
        form_repo=None,
    ):
        self._authorization = authorization_service
        self._api_key_repo = api_key_repo
        self._audit_repo = audit_repo
        self._grants = grant_repo
        self._forms = form_repo

    # -- create -----------------------------------------------------------------
    async def create_key(
        self, workspace_id: RecordId, dto: CreateAPIKeyDto, user: User
    ) -> CreatedAPIKeyDto:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        invalid = set(dto.scopes) - VALID_SCOPES
        if invalid:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=f"Unknown scopes: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(VALID_SCOPES))}",
            )
        # a role or a list of forms while the switch is off: 422, before anything
        # else of them is looked at
        refuse_setting_when_off(dto.role, dto.form_scope)
        role = validation.normalise_role(dto.role)
        form_scope = validation.normalise_form_scope(dto.form_scope)
        listed = form_scope == SCOPE_LISTED
        validation.check_matrix(role, form_scope, dto.scopes)
        await self._require_within_creator(workspace_id, user, role, dto.scopes)
        list_ids = await self._checked_list(workspace_id, user, dto.form_ids, listed)
        submits = SUBMISSIONS_SCOPE in dto.scopes
        if submits:
            from backend.app.services.submissions_api.mode import (
                refuse_scope_when_off,
            )

            refuse_scope_when_off()
        form_ids = await self._checked_submission_forms(
            workspace_id, dto.submission_form_ids, submits
        )
        self._require_submission_forms_listed(form_ids, listed, list_ids)
        reads_responses = bool(set(dto.scopes) & UNREDACTED_RESPONSE_SCOPES)
        if reads_responses and not dto.acknowledge_unredacted_responses:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=(
                    "A key with responses:read gives the AI client that uses it "
                    "full, unredacted answers. Acknowledge this to create the key."
                ),
            )
        token = TOKEN_PREFIX + secrets.token_hex(32)
        document = WorkspaceAPIKeyDocument(
            id=RecordId(),
            workspace_id=workspace_id,
            name=dto.name.strip(),
            key_hash=_hash(token),
            prefix=token[: len(TOKEN_PREFIX) + 8],
            scopes=sorted(set(dto.scopes)),
            created_by=user.id,
            submission_form_ids=form_ids,
            responses_read_acknowledged_by=str(user.id) if reads_responses else None,
            responses_read_acknowledged_at=(
                dt.datetime.now(dt.timezone.utc) if reads_responses else None
            ),
            role=role,
            form_scope=form_scope,
        )
        key_id = str(document.id)
        # the entries first (ids and enum values, never the name, the prefix or the
        # token): the key is not made when they cannot be stored
        await record_or_refuse(
            self._audit_repo,
            API_KEY_CREATED,
            workspace_id,
            user,
            key_id=key_id,
            key_role=_role_value(role),
            form_scope=form_scope,
            count=len(list_ids),
        )
        for form_id in list_ids:
            await record_or_refuse(
                self._audit_repo,
                API_KEY_FORM_ADDED,
                workspace_id,
                user,
                key_id=key_id,
                form_id=form_id,
            )
        await self._api_key_repo.save(document)
        if listed:
            try:
                await self._write_rows(workspace_id, document, list_ids, user)
            except HTTPException:
                # a key with the list it was asked for or not at all: never one
                # that is listed with no rows and a secret that was never shown
                await self._api_key_repo.revoke_one(workspace_id, document.id)
                raise
        forms = await self._forms_of_list(workspace_id, user, list_ids)
        return CreatedAPIKeyDto(**_to_dto(document, forms).model_dump(), token=token)

    async def _require_within_creator(
        self,
        workspace_id: RecordId,
        person: User,
        role: Optional[str],
        scopes,
    ) -> None:
        """403 when the role would let a key do more than ``person`` may now: a
        key never exceeds the person it acts as. No role is "as its creator" and
        is never more."""
        if role is None:
            return
        held = await self._authorization.effective_permissions(person, workspace_id)
        if not validation.ceiling_set(role, scopes) <= held:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content={
                    "code": "key_role_exceeds_creator",
                    "message": "A key cannot have a role that allows more than "
                    "the person it acts as may do.",
                },
            )

    async def _checked_list(
        self,
        workspace_id: RecordId,
        user: User,
        form_ids: Optional[List[str]],
        listed: bool,
    ) -> List[str]:
        """The ids of a key's list of forms: none for a key that is not limited
        to a list; for one that is, ids of forms of this workspace that the
        person setting the list may open (one answer for a form that is not
        there and one they may not open)."""
        if not listed:
            if form_ids is not None:
                validation.refuse(
                    "form_ids_need_listed_scope",
                    "formIds only goes with formScope 'listed'.",
                )
            return []
        if form_ids is None:
            validation.refuse(
                "form_ids_required",
                "formScope 'listed' needs formIds (empty for a key that opens "
                "no form).",
            )
        wanted = validation.unique_ids(form_ids)
        if not all(ObjectId.is_valid(f) for f in wanted):
            self._unknown_form()
        known = {
            str(a.form_id)
            for a in await _c().workspace_form_repo().list_in_workspace(workspace_id)
        }
        if not set(wanted) <= known:
            self._unknown_form()
        visible = await self._authorization.restrict_to_visible(
            user, workspace_id, wanted, Permission.FORM_READ
        )
        if set(visible) != set(wanted):
            self._unknown_form()
        return wanted

    @staticmethod
    def _unknown_form() -> None:
        validation.refuse(
            "form_not_in_workspace",
            "formIds names a form that is not in this workspace.",
        )

    @staticmethod
    def _require_submission_forms_listed(
        submission_form_ids: Optional[List[str]], listed: bool, list_ids: List[str]
    ) -> None:
        """A listed key submits only to forms of its list: a submission form
        outside it is refused, never quietly dropped."""
        if listed and submission_form_ids is not None:
            if not set(submission_form_ids) <= set(list_ids):
                validation.refuse(
                    "submission_form_outside_list",
                    "submissionFormIds names a form that is not on the key's list.",
                )

    async def _write_rows(
        self,
        workspace_id: RecordId,
        document: WorkspaceAPIKeyDocument,
        list_ids: List[str],
        user: User,
    ) -> None:
        """Make ``list_ids`` the key's rows, each with the role the key's role
        allows on a row, in one transaction."""
        from backend.app.repositories.postgres.form_access import AccessTargetNotFound

        row_role = validation.row_role_for(document.role)
        rows = [
            FormAccessGrantDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                subject_type=SUBJECT_KEY,
                subject_id=str(document.id),
                role=row_role,
                created_by=str(user.id),
            )
            for form_id in list_ids
        ]
        try:
            await self._grants.replace_for_key(workspace_id, document.id, rows)
        except AccessTargetNotFound as error:
            # a form deleted since it was checked, or a key revoked meanwhile
            if error.what == "key":
                raise _not_found() from error
            self._unknown_form()

    async def _checked_submission_forms(
        self,
        workspace_id: RecordId,
        form_ids: Optional[List[str]],
        submits: bool,
    ) -> Optional[List[str]]:
        """The key's form list: None (every form) or ids of this workspace's
        forms; a list needs the scope it limits."""
        if form_ids is None:
            return None
        if not submits:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=f"submissionFormIds needs the '{SUBMISSIONS_SCOPE}' scope.",
            )
        wanted = sorted(set(form_ids))
        if not wanted:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Name at least one form, or leave submissionFormIds out "
                "for every form of the workspace.",
            )
        known = {
            str(a.form_id)
            for a in await _c().workspace_form_repo().list_in_workspace(workspace_id)
        }
        if not set(wanted) <= known:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="submissionFormIds names a form that is not in this workspace.",
            )
        return wanted

    # -- read -------------------------------------------------------------------
    async def _forms_of_list(
        self, workspace_id: RecordId, user: User, form_ids: List[str]
    ) -> List[APIKeyFormDto]:
        return (await self._forms_by_key(workspace_id, user, {"": form_ids}))[""]

    async def _forms_by_key(
        self,
        workspace_id: RecordId,
        user: User,
        lists: Dict[str, List[str]],
    ) -> Dict[str, List[APIKeyFormDto]]:
        """``{key id: its forms}``: every id, and the title of the ones the
        reader may open (one visibility check and one title query for all)."""
        every = sorted({f for ids in lists.values() for f in ids})
        titles: Dict[str, Optional[str]] = {}
        if every:
            visible = await self._authorization.restrict_to_visible(
                user, workspace_id, every, Permission.FORM_READ
            )
            titles = await self._forms.titles_of(list(visible))
        return {
            key_id: [APIKeyFormDto(id=f, title=titles.get(f)) for f in sorted(ids)]
            for key_id, ids in lists.items()
        }

    async def _dtos(
        self,
        workspace_id: RecordId,
        user: User,
        documents: List[WorkspaceAPIKeyDocument],
    ) -> List[APIKeyDto]:
        keys = [str(d.id) for d in documents if d.form_scope != SCOPE_ALL]
        lists: Dict[str, List[str]] = {k: [] for k in keys}
        for row in await self._grants.for_keys(workspace_id, keys):
            lists[str(row.subject_id)].append(str(row.form_id))
        forms = await self._forms_by_key(workspace_id, user, lists)
        return [_to_dto(d, forms.get(str(d.id))) for d in documents]

    async def list_keys(
        self, workspace_id: RecordId, user: User
    ) -> List[APIKeyDto]:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        documents = await self._api_key_repo.list_by_workspace(workspace_id)
        return await self._dtos(workspace_id, user, documents)

    # -- edit -------------------------------------------------------------------
    async def update_key(
        self, workspace_id: RecordId, key_id: str, dto: UpdateAPIKeyDto, user: User
    ) -> APIKeyDto:
        """Change a key's name, role and list of forms (security.manage; Owner and
        Admin). Widening is allowed to them and recorded as such. An entry per
        change is stored first; the change is refused when one cannot be."""
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        refuse_when_off()
        document = await self._live_key(workspace_id, key_id)
        fields = dto.model_fields_set
        role = (
            validation.normalise_role(dto.role) if "role" in fields else document.role
        )
        form_scope = (
            validation.normalise_form_scope(dto.form_scope)
            if "form_scope" in fields and dto.form_scope is not None
            else document.form_scope
        )
        listed = form_scope == SCOPE_LISTED
        was_listed = document.form_scope != SCOPE_ALL
        old_ids = await self._stored_list(workspace_id, document) if was_listed else []
        if "form_ids" in fields and dto.form_ids is not None:
            new_ids = await self._checked_list(workspace_id, user, dto.form_ids, listed)
        elif listed and was_listed:
            new_ids = old_ids  # the list is left as it is
        elif listed:
            validation.refuse(
                "form_ids_required", "formScope 'listed' needs formIds."
            )
        else:
            new_ids = []
        validation.check_matrix(role, form_scope, document.scopes)
        # the role may not exceed the admin who sets it, nor the person the key
        # acts as (whom it follows at every request anyway)
        await self._require_within_creator(workspace_id, user, role, document.scopes)
        if role != document.role and role is not None:
            from backend.app.services.api_access import acting_user

            await self._require_within_creator(
                workspace_id,
                acting_user(document, with_ceiling=False),
                role,
                document.scopes,
            )
        self._require_submission_forms_listed(
            document.submission_form_ids, listed, new_ids
        )
        name = dto.name.strip() if dto.name is not None else document.name

        role_changed = role != document.role
        scope_changed = form_scope != document.form_scope or (
            listed and set(new_ids) != set(old_ids)
        )
        added = sorted(set(new_ids) - set(old_ids))
        removed = sorted(set(old_ids) - set(new_ids))
        scope_widened = (was_listed and not listed) or (
            listed and was_listed and bool(added)
        )
        rows_stale = listed and (role_changed or added or removed or not was_listed)
        key = str(document.id)
        if role_changed:
            await record_or_refuse(
                self._audit_repo,
                API_KEY_ROLE_CHANGED,
                workspace_id,
                user,
                key_id=key,
                key_role=_role_value(role),
                key_role_before=_role_value(document.role),
                widened=validation.widens_role(document.role, role, document.scopes),
            )
        if scope_changed:
            await record_or_refuse(
                self._audit_repo,
                API_KEY_SCOPE_CHANGED,
                workspace_id,
                user,
                key_id=key,
                form_scope=form_scope,
                count=len(new_ids),
                widened=scope_widened,
            )
        for event, form_ids in (
            (API_KEY_FORM_ADDED, added),
            (API_KEY_FORM_REMOVED, removed),
        ):
            for form_id in form_ids:
                await record_or_refuse(
                    self._audit_repo,
                    event,
                    workspace_id,
                    user,
                    key_id=key,
                    form_id=form_id,
                )
        updated = await self._api_key_repo.update_limits(
            workspace_id,
            document.id,
            name=name,
            role=role,
            form_scope=form_scope,
        )
        if updated is None:
            raise _not_found()
        # the key first, then its rows: a failure in between leaves the key
        # narrower than asked (a list with no rows opens nothing), never wider
        if rows_stale:
            await self._write_rows(workspace_id, updated, new_ids, user)
        elif was_listed and not listed:
            await self._grants.delete_for_subject(workspace_id, SUBJECT_KEY, key)
        return (await self._dtos(workspace_id, user, [updated]))[0]

    async def _stored_list(
        self, workspace_id: RecordId, document: WorkspaceAPIKeyDocument
    ) -> List[str]:
        rows = await self._grants.for_key(workspace_id, document.id)
        return sorted(str(r.form_id) for r in rows)

    async def _live_key(
        self, workspace_id: RecordId, key_id: str
    ) -> WorkspaceAPIKeyDocument:
        """The key of this workspace, not revoked: 404 for a key that is not
        there or belongs to another workspace, 409 for a revoked one."""
        if not ObjectId.is_valid(str(key_id)):
            raise _not_found()
        document = await self._api_key_repo.find_by_id(RecordId(key_id))
        if not document or str(document.workspace_id) != str(workspace_id):
            raise _not_found()
        if document.revoked:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content={
                    "code": "key_revoked",
                    "message": "A revoked key cannot be changed.",
                },
            )
        return document

    # -- revoke -----------------------------------------------------------------
    async def revoke_key(
        self, workspace_id: RecordId, key_id: str, user: User
    ) -> List[APIKeyDto]:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        document = await self._api_key_repo.get_or_404(RecordId(key_id))
        if not document or str(document.workspace_id) != str(workspace_id):
            raise _not_found()
        if not document.revoked:
            # the entry first; the key and its form rows go in one transaction
            await record_or_refuse(
                self._audit_repo,
                API_KEY_REVOKED,
                workspace_id,
                user,
                key_id=str(document.id),
                reason=REVOKED_BY_ADMIN,
            )
            await self._api_key_repo.revoke_one(workspace_id, document.id)
        return await self.list_keys(workspace_id, user)

    @staticmethod
    async def authenticate(token: str) -> WorkspaceAPIKeyDocument:
        """Resolve a Bearer token to its key document, or 401."""
        if not token or not token.startswith(TOKEN_PREFIX):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Invalid API key"
            )
        document = await _c().workspace_api_key_repo().find_by_key_hash(_hash(token))
        if not document or document.revoked:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content="Invalid or revoked API key",
            )
        # only last_used_at changes, and only while the key is still live: a
        # whole-document save would write a stale ``revoked=False`` back over
        # a revocation made while this request was in flight
        now = dt.datetime.now(dt.timezone.utc)
        if not await _c().workspace_api_key_repo().touch_last_used(document.id, now):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content="Invalid or revoked API key",
            )
        document.last_used_at = now
        return document

    @staticmethod
    def require_scope(document: WorkspaceAPIKeyDocument, scope: str) -> None:
        if scope not in document.scopes:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content=f"This API key lacks the '{scope}' scope.",
            )
