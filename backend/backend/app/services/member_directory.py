"""Who a staff member is, for screens that name them (the versions list, the
history of a response): the current members of a workspace, their names and
their role.

Only current, enabled members are looked up; what the auth service knows about
anyone else is never shown, and an id that is not a member is "a former
member" to the screen. Names are best effort (a failed or slow lookup shows
the role only) and never addresses.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from loguru import logger

from backend.app.models.enum.workspace_roles import is_owner_membership, primary_role
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings


class MemberDirectory:
    def __init__(self, workspace_repo, workspace_user_repo, http_client=None):
        self._workspaces = workspace_repo
        self._members = workspace_user_repo
        self._http_client = http_client

    async def role_of(self, workspace_id, user_id) -> Optional[str]:
        """The role of one current member (None when they are not one, or hold
        no known role). No lookup of names."""
        roles, _ = await self._roles(workspace_id, [str(user_id)])
        return roles.get(str(user_id))

    async def _roles(self, workspace_id, wanted):
        workspace = await self._workspaces.find_by_id(workspace_id)
        roles: Dict[str, Optional[str]] = {}
        for member in await self._members.get_workspace_users(workspace_id):
            user_id = str(member.user_id)
            if user_id not in wanted or member.disabled:
                continue
            roles[user_id] = primary_role(
                member.roles, is_owner=is_owner_membership(workspace, member)
            )
        return roles, workspace

    async def lookup(
        self, workspace_id, user_ids: Iterable[str]
    ) -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        """``(roles, names)``: ``roles`` has an entry for each id among
        ``user_ids`` that is a current member (its role, or None when it has
        no known one); ``names`` the display names found, by id."""
        wanted = {str(u) for u in user_ids if u}
        if not wanted:
            return {}, {}
        roles, _ = await self._roles(workspace_id, wanted)
        if not roles or self._http_client is None:
            return roles, {}
        try:
            reply = await self._http_client.get(
                settings.auth_settings.BASE_URL + "/users",
                params={"user_ids": sorted(roles)},
                headers=auth_service_headers(),
                timeout=10,
            )
        except Exception as error:  # noqa: BLE001 - names are best effort
            logger.warning("Member names lookup failed: {}", type(error).__name__)
            return roles, {}
        names: Dict[str, str] = {}
        for info in (reply or {}).get("users_info") or []:
            name = " ".join(
                p for p in (info.get("first_name"), info.get("last_name")) if p
            ).strip()
            user_id = str(info.get("_id") or info.get("id") or "")
            if name and user_id in roles:
                names[user_id] = name
        return roles, names
