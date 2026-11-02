"""What a workspace API key may do, for every caller that takes one: the
MCP server (``mcp/server.py``) and the public REST API (``public_api/``).

A key carries scopes, and is bound to its workspace. On every call the
key's creator must still hold, right now, the permissions behind the scope:
a key never does more than the person who made it currently may (a removed,
disabled or demoted creator makes the key refuse). Every call is audited.

Form-level access (``FORM_ACCESS_ENABLED``): a call that names a form is decided
on that form too, as the key's creator (an Owner or Admin reaches every form; a
member only what their role, grants and the form's access mode give). A form
closed to the creator answers as a form that does not exist. Every such
decision, for a single form or a list, goes through ``key_permissions_on_form``
and the helpers below it, so a key of its own (its own role and form list) is
one change in one place. Switched off, none of it reads anything.

A key can carry limits of its own (``API_KEY_ROLES_ENABLED``; ``services/
api_key_roles``): a role (the most it may do) and a list of forms (the only
forms it may open). Its decision is always the creator's current one narrowed by
them, recomputed on every request, never widened. A limit already stored on a
key is enforced whatever the switch says; a key with neither limit takes
exactly the path it always did, with the same queries.
"""

import datetime as dt
from http import HTTPStatus
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from bson import ObjectId
from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.services.api_key_roles.model import (
    is_listed,
    key_decision,
    role_ceiling,
    row_ceiling,
)
from backend.app.services.form_access.mode import form_access_enabled
from backend.app.services.form_access.model import FormPermissions
from backend.app.services.request_context import current_request

# A bulk read of answers through the API is an export, so responses:read
# needs response.export as well as response.read (doc §4).
SCOPE_PERMISSIONS: Dict[str, Tuple[Permission, ...]] = {
    "forms:read": (Permission.FORM_READ,),
    "forms:write": (Permission.FORM_EDIT,),
    "forms:delete": (Permission.FORM_DELETE,),
    "responses:read": (Permission.RESPONSE_READ, Permission.RESPONSE_EXPORT),
    "deletion_requests:read": (Permission.PRIVACY_MANAGE,),
    "deletion_requests:write": (Permission.PRIVACY_MANAGE,),
    # a write key: its creator must still be able to edit forms (an Editor,
    # Admin or Owner), checked on every call, so a creator who was demoted to
    # Viewer, Reviewer or Privacy officer, or whose workspace was disabled
    # (read-only), no longer has a key that writes
    "submissions:write": (Permission.FORM_EDIT,),
}

MISSING_SCOPE_CODE = "missing_scope"
CREATOR_LACKS_PERMISSION_CODE = "key_creator_lacks_permission"
ROLE_LACKS_PERMISSION_CODE = "key_role_lacks_permission"
_ROWS_MEMO = "api_key_rows"


def _c():
    # Resolved at call time: the container imports services this module uses.
    from backend.app.container import container

    return container


def _ceiling(key: WorkspaceAPIKeyDocument) -> Optional[FrozenSet[Permission]]:
    """The most the key's role lets it do (``None``: no role, as its creator)."""
    return role_ceiling(key.role, key.scopes)


def _has_limits(key: WorkspaceAPIKeyDocument) -> bool:
    """Whether the key carries a role or a list of forms (stored on it: this
    does not depend on any switch, so switching one off never widens a key)."""
    return key.role is not None or is_listed(key.form_scope)


def acting_user(key: WorkspaceAPIKeyDocument, *, with_ceiling: bool = True) -> User:
    """Authorization inside the product services runs as the key's creator.
    The one place this user is built (the public API, the MCP server and the
    decisions below all come here).

    ``with_ceiling``: the user carries the key's role ceiling, so a service that
    authorizes as the creator (``form_spec``, the outline and ops services) can
    never exceed the key's role even if it forgets the gate in this module.
    ``False`` is the creator exactly, for the decision that has to tell what the
    creator lacks from what the key's role lacks."""
    # auth_method "api_key": a machine credential, which the workspace's
    # single sign-on requirement does not cover (services/sso/policy.py)
    ceiling = _ceiling(key) if with_ceiling else None
    return User(
        id=key.created_by,
        sub=f"api-key:{key.name}",
        roles=["FORM_CREATOR"],
        auth_method="api_key",
        key_ceiling=None if ceiling is None else frozenset(p.value for p in ceiling),
    )


def _creator(key: WorkspaceAPIKeyDocument) -> User:
    return acting_user(key, with_ceiling=False)


def require_key_has_scope(key: WorkspaceAPIKeyDocument, scope: str) -> None:
    """403 ``missing_scope`` unless the key has ``scope`` (no permission
    lookup: cheap enough to run before the key is rate limited)."""
    try:
        APIKeyService.require_scope(key, scope)
    except HTTPException as error:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content={"code": MISSING_SCOPE_CODE, "message": str(error.content)},
        ) from error


async def require_key_scope(
    key: WorkspaceAPIKeyDocument, scope: str, form_id: Optional[str] = None
) -> None:
    """403 unless the key has ``scope``, its creator still holds the scope's
    permissions in the key's workspace and the key's role allows them; with
    ``form_id`` (a call on one form) also on that form while form-level access
    is on or the key carries a limit: 404 for a form closed to the key, 403 for
    a permission it lacks on it."""
    require_key_has_scope(key, scope)
    held = (
        await _c()
        .authorization_service()
        .effective_permissions(_creator(key), key.workspace_id)
    )
    missing = [p.value for p in SCOPE_PERMISSIONS[scope] if p not in held]
    if missing:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content={
                "code": CREATOR_LACKS_PERMISSION_CODE,
                "message": "Forbidden: the person who created this API key no "
                "longer has "
                f"{', '.join(repr(p) for p in missing)} in this workspace.",
            },
        )
    ceiling = _ceiling(key)
    if ceiling is not None:
        _require_role_allows(
            [p for p in SCOPE_PERMISSIONS[scope] if p not in ceiling],
            "in this workspace",
        )
    if form_id is not None:
        # a call on one form: a form that is not there answers exactly as one
        # that is closed to the creator, before anything else of the request
        await require_key_on_form(key, scope, form_id, must_exist=True)


def _require_role_allows(missing: List[Permission], where: str) -> None:
    """403 ``key_role_lacks_permission`` naming ``missing`` (what the key's role,
    or its row for the form, does not allow)."""
    if missing:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content={
                "code": ROLE_LACKS_PERMISSION_CODE,
                "message": "Forbidden: this API key's role does not allow "
                f"{', '.join(repr(p.value) for p in missing)} {where}.",
            },
        )


async def _key_row(
    key: WorkspaceAPIKeyDocument, form_id: str
) -> Optional[FormAccessGrantDocument]:
    """The key's row for the form (one indexed read, remembered for the
    request). Only a key limited to a list of forms asks."""
    context = current_request()
    memo = None if context is None else context.memo.setdefault(_ROWS_MEMO, {})
    at = (str(key.id), str(form_id))
    if memo is not None and at in memo:
        return memo[at]
    row = await _c().form_access_grant_repo().for_key_on_form(
        key.workspace_id, key.id, str(form_id)
    )
    if memo is not None:
        memo[at] = row
    return row


async def _decide(
    key: WorkspaceAPIKeyDocument, form_id: str
) -> Tuple[FormPermissions, FormPermissions]:
    """``(creator's decision, key's decision)`` on one form. The key's is the
    creator's current one intersected with the key's role ceiling and, for a key
    limited to a list of forms, with its row for the form (no row: the form is
    closed to it, as a form that does not exist). Never wider than the
    creator's."""
    creator = await _c().authorization_service().form_permissions(
        _creator(key), key.workspace_id, form_id
    )
    listed = is_listed(key.form_scope)
    row = None
    if listed and creator.permissions and not creator.hidden:
        row = await _key_row(key, form_id)
    decided = key_decision(
        creator,
        ceiling=_ceiling(key),
        listed=listed,
        row=row,
        scopes=key.scopes,
    )
    return creator, decided


async def key_permissions_on_form(
    key: WorkspaceAPIKeyDocument, form_id: str
) -> FormPermissions:
    """What the key may do on one form: the one place a key's decision on a
    form is taken. It is the creator's decision (role, grants, the form's access
    mode) narrowed by the key's own role and form list. Callers check
    ``form_access_enabled()`` or the key's limits first: this always reads."""
    return (await _decide(key, form_id))[1]


async def require_key_on_form(
    key: WorkspaceAPIKeyDocument, scope: str, form_id: str, must_exist: bool = False
) -> None:
    """While form-level access is on, or when the key carries a role or a list
    of forms: 404 (as for a form that does not exist) when the form is closed to
    the key, 403 when the key can open it but lacks a permission ``scope``
    needs on it. A form that is not one of the workspace's decides nothing here
    (the creator's workspace-level permissions stand, and the caller's own 404
    follows), unless ``must_exist``: then it is the very same 404 as for a
    closed form, so that the answer to any input, good or bad, never tells a
    missing form from a closed one. Switched off and no limit on the key:
    nothing, and no query."""
    if not (form_access_enabled() or _has_limits(key)):
        return
    creator, decided = await _decide(key, form_id)
    if decided.hidden or (
        must_exist and not await _form_is_there(key, form_id, decided)
    ):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")
    missing = [p for p in SCOPE_PERMISSIONS[scope] if p not in decided.permissions]
    if not missing:
        return
    by_creator = [p for p in missing if p not in creator.permissions]
    if by_creator:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content={
                "code": CREATOR_LACKS_PERMISSION_CODE,
                "message": "Forbidden: the person who created this API key does "
                f"not have {', '.join(repr(p.value) for p in by_creator)} on this form.",
            },
        )
    _require_role_allows(missing, "on this form")


async def _form_is_there(
    key: WorkspaceAPIKeyDocument, form_id: str, decided: FormPermissions
) -> bool:
    """Whether ``form_id`` is a form of the key's workspace (the decision found
    it, or a lookup does: Owners and Admins are decided without one)."""
    if decided.form_found:
        return True
    if not ObjectId.is_valid(str(form_id)):
        return False
    return (
        await _c()
        .workspace_form_repo()
        .find_workspace_form(key.workspace_id, str(form_id))
    ) is not None


async def key_may_use_form(
    key: WorkspaceAPIKeyDocument, scope: str, form_id: str
) -> bool:
    """Whether the key may do what ``scope`` stands for on the form (always
    true while form-level access is off, without a query): for a call that
    finds its form only after reading something else, a response say."""
    try:
        await require_key_on_form(key, scope, form_id)
    except HTTPException:
        return False
    return True


async def restrict_to_key_visible(
    key: WorkspaceAPIKeyDocument,
    form_ids: Iterable[str],
    permissions: Iterable[Permission],
) -> List[str]:
    """``form_ids`` (in their order) on which the key may do every one of
    ``permissions``: its creator holds them there, its role allows them and,
    for a key limited to a list of forms, its row for the form does. For a list
    the key must not learn of a form it cannot open from. Narrow before counting
    or paginating. Switched off, and with no limit on the key, the ids come back
    as they are, without a query."""
    ids = [str(f) for f in form_ids]
    needed = list(permissions)
    ceiling = _ceiling(key)
    if ceiling is not None and any(p not in ceiling for p in needed):
        return []
    if is_listed(key.form_scope):
        if not ids:
            return []
        rows = {
            str(r.form_id): r
            for r in await _c()
            .form_access_grant_repo()
            .for_key(key.workspace_id, key.id, ids)
        }
        ids = [
            f
            for f in ids
            if f in rows and set(needed) <= row_ceiling(rows[f].role, key.scopes)
        ]
    service = _c().authorization_service()
    for permission in needed:
        if not ids:
            break
        ids = await service.restrict_to_visible(
            _creator(key), key.workspace_id, ids, permission
        )
    return ids


async def audit_key_call(
    key: WorkspaceAPIKeyDocument, tool: str, ok: bool, detail: str = ""
) -> None:
    """One audit entry per call (``mcp_audit_logs``); ids and counts only,
    never content. Never raises: auditing must not break a call."""
    try:
        await _c().mcp_audit_log_repo().add(
            workspace_id=key.workspace_id,
            key_id=str(key.id),
            tool=tool,
            ok=ok,
            detail=detail[:300],
            at=dt.datetime.now(dt.timezone.utc),
        )
    except Exception:  # noqa: BLE001
        pass
