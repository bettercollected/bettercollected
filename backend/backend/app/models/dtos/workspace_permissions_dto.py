from typing import List

from fastapi_camelcase import CamelModel

from backend.app.models.enum.permission import Permission


class WorkspacePermissionsDto(CamelModel):
    """The caller's effective permissions in a workspace; empty when they
    hold none there (not a member, a disabled membership or workspace)."""

    permissions: List[Permission] = []
