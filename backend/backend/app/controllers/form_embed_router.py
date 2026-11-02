"""Embedding forms in other sites (``services/form_embed.py``, docs/embed.md).

``/workspaces/{id}/embed/settings`` lists and changes the sites a workspace
allows to frame its forms (workspace.manage to change, form.share or
workspace.manage to read); ``/workspaces/embed/policy`` is the public answer
the webapp's proxy turns into the ``frame-ancestors`` of a respondent page.
"""

from typing import Optional

from classy_fastapi import Routable, get, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Request, Response
from common.utils.client_ip import rate_limit_key

from backend.app.container import container
from backend.app.router import router
from backend.app.services.form_embed import (
    EmbedPolicyDto,
    EmbedSettingsDto,
    UpdateEmbedSettingsDto,
)
from backend.app.services.user_service import get_logged_user
from backend.app.utils.client_ip import request_client_ip


@router(
    prefix="/workspaces",
    tags=["Workspace embedding"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Not allowed to see or change the embedding settings."},
        404: {"description": "Embedding is not switched on on this server."},
        429: {
            "description": "Too many policy requests from this address or about this workspace."
        },
    },
)
class FormEmbedRouter(Routable):
    @get("/embed/policy", response_model=EmbedPolicyDto)
    async def policy(
        self,
        request: Request,
        response: Response,
        workspace_name: Optional[str] = Query(None, max_length=200),
        custom_domain: Optional[str] = Query(None, max_length=255),
        workspace_id: Optional[str] = Query(None, max_length=64),
    ) -> EmbedPolicyDto:
        """The sites that may frame the workspace's forms. Public: it holds
        what the ``frame-ancestors`` of any of its form pages shows anyway.
        Exactly one of the three queries. Limited per client address and per workspace (429 with
        Retry-After)."""
        # the webapp keeps it for 30 s; a browser or proxy need not
        response.headers["Cache-Control"] = "no-store"
        return await container.form_embed_service().policy(
            workspace_name=workspace_name,
            custom_domain=custom_domain,
            workspace_id=workspace_id,
            client=rate_limit_key(request_client_ip(request)),
        )

    @get("/{workspace_id}/embed/settings")
    async def get_settings(
        self,
        workspace_id: RecordId,
        user: User = Depends(get_logged_user),
    ) -> EmbedSettingsDto:
        return await container.form_embed_service().get_settings(workspace_id, user)

    @put("/{workspace_id}/embed/settings")
    async def update_settings(
        self,
        workspace_id: RecordId,
        request: UpdateEmbedSettingsDto,
        user: User = Depends(get_logged_user),
    ) -> EmbedSettingsDto:
        """Replace the list of allowed sites (the whole list, at most 20)."""
        return await container.form_embed_service().update_settings(
            workspace_id, request, user
        )
