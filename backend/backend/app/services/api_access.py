"""What a workspace API key may do, for every caller that takes one: the
MCP server (``mcp/server.py``) and the public REST API (``public_api/``).

A key carries scopes, and is bound to its workspace. On every call the
key's creator must still hold, right now, the permissions behind the scope:
a key never does more than the person who made it currently may (a removed,
disabled or demoted creator makes the key refuse). Every call is audited.
"""

import datetime as dt
from http import HTTPStatus
from typing import Dict, Tuple

from common.models.user import User

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.ai.api_keys import APIKeyService

# A bulk read of answers through the API is an export, so responses:read
# needs response.export as well as response.read (doc §4).
SCOPE_PERMISSIONS: Dict[str, Tuple[Permission, ...]] = {
    "forms:read": (Permission.FORM_READ,),
    "forms:write": (Permission.FORM_EDIT,),
    "responses:read": (Permission.RESPONSE_READ, Permission.RESPONSE_EXPORT),
    "deletion_requests:read": (Permission.PRIVACY_MANAGE,),
    "deletion_requests:write": (Permission.PRIVACY_MANAGE,),
}

MISSING_SCOPE_CODE = "missing_scope"
CREATOR_LACKS_PERMISSION_CODE = "key_creator_lacks_permission"


def _c():
    # Resolved at call time: the container imports services this module uses.
    from backend.app.container import container

    return container


def acting_user(key: WorkspaceAPIKeyDocument) -> User:
    """Authorization inside the product services runs as the key's creator."""
    return User(id=key.created_by, sub=f"api-key:{key.name}", roles=["FORM_CREATOR"])


async def require_key_scope(key: WorkspaceAPIKeyDocument, scope: str) -> None:
    """403 unless the key has ``scope`` and its creator still holds the
    scope's permissions in the key's workspace."""
    try:
        APIKeyService.require_scope(key, scope)
    except HTTPException as error:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            content={"code": MISSING_SCOPE_CODE, "message": str(error.content)},
        ) from error
    held = (
        await _c()
        .authorization_service()
        .effective_permissions(acting_user(key), key.workspace_id)
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
