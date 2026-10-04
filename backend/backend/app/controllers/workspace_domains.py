from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, delete, get, post
from common.models.user import User
from fastapi import Depends, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.user_service import get_logged_user
from backend.app.services.workspace_domain_service import (
    ClaimDomainDto,
    WorkspaceDomainDto,
)


@router(
    prefix="/workspaces",
    tags=["Workspace domains"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "Only the workspace owner and admins manage domains."},
    },
)
class WorkspaceDomainsRouter(Routable):
    """Email domains a workspace verifies with a DNS TXT record
    (docs/verified-domains.md). Owner and admins only."""

    @get("/{workspace_id}/domains")
    async def list_domains(
        self,
        workspace_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ) -> List[WorkspaceDomainDto]:
        return await container.workspace_domain_service().list_domains(
            workspace_id, user
        )

    @post(
        "/{workspace_id}/domains",
        status_code=HTTPStatus.CREATED,
        responses={
            409: {"description": "Already claimed here, or verified elsewhere."},
            422: {"description": "Not a domain this workspace may claim."},
        },
    )
    async def claim_domain(
        self,
        workspace_id: PydanticObjectId,
        request: ClaimDomainDto,
        user: User = Depends(get_logged_user),
    ) -> WorkspaceDomainDto:
        return await container.workspace_domain_service().claim_domain(
            workspace_id, request, user
        )

    @post(
        "/{workspace_id}/domains/{domain_id}/verify",
        responses={404: {"description": "No such domain in this workspace."}},
    )
    async def verify_domain(
        self,
        workspace_id: PydanticObjectId,
        domain_id: str,
        user: User = Depends(get_logged_user),
    ) -> WorkspaceDomainDto:
        """Check the TXT record now; the outcome is in ``status`` and
        ``lastCheckError``."""
        return await container.workspace_domain_service().verify_domain(
            workspace_id, domain_id, user
        )

    @delete(
        "/{workspace_id}/domains/{domain_id}",
        status_code=HTTPStatus.NO_CONTENT,
        responses={404: {"description": "No such domain in this workspace."}},
    )
    async def delete_domain(
        self,
        workspace_id: PydanticObjectId,
        domain_id: str,
        user: User = Depends(get_logged_user),
    ) -> Response:
        await container.workspace_domain_service().delete_domain(
            workspace_id, domain_id, user
        )
        return Response(status_code=HTTPStatus.NO_CONTENT)
