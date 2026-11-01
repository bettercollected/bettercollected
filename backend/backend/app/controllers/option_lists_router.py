from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, delete, get, patch, post
from common.ids import RecordId
from common.models.standard_form import OptionSource
from common.models.user import User
from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.router import router
from backend.app.services.option_lists.service import (
    CSV_BYTES_MAX,
    OptionListCreateDto,
    OptionListDto,
    OptionListSummaryDto,
    OptionListUpdateDto,
)
from backend.app.services.user_service import get_full_user


class SourcePreviewRequest(BaseModel):
    """The builder's look at a source (``POST .../option-sources/preview``)."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    source: OptionSource
    # the labels of the parent question's options, to try a dependent list
    parent_labels: List[str] = Field(default_factory=list, max_length=50)
    # the form being edited (a form cannot take options from its own answers)
    form_id: Optional[str] = Field(None, max_length=64)
    q: Optional[str] = Field(None, max_length=100)
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


@router(
    prefix="/workspaces",
    tags=["Option lists"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks the permission."},
        404: {"description": "No such list in this workspace."},
    },
)
class OptionListsRouter(Routable):
    """A workspace's option lists, and the builder's preview of an option
    source (docs/option-sources.md). Reading needs ``form.read``, every change
    ``form.edit``; every list is looked up through the workspace."""

    @get("/{workspace_id}/option-lists")
    async def list_option_lists(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ) -> List[OptionListSummaryDto]:
        return await container.option_list_service().list_lists(workspace_id, user)

    @post(
        "/{workspace_id}/option-lists",
        status_code=HTTPStatus.CREATED,
        responses={
            409: {"description": "name_taken"},
            422: {
                "description": "option_sources_disabled, limit_reached, invalid_name, "
                "invalid_item, duplicate_item"
            },
        },
    )
    async def create_option_list(
        self,
        workspace_id: RecordId,
        body: OptionListCreateDto,
        user: User = Depends(get_full_user),
    ) -> OptionListDto:
        return await container.option_list_service().create_list(
            workspace_id, body, user
        )

    @get("/{workspace_id}/option-lists/{list_id}")
    async def get_option_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        limit: int = Query(2000, ge=1, le=2000),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_full_user),
    ) -> OptionListDto:
        return await container.option_list_service().get_list(
            workspace_id, list_id, user, limit=limit, offset=offset
        )

    @patch(
        "/{workspace_id}/option-lists/{list_id}",
        responses={409: {"description": "name_taken, list_changed"}},
    )
    async def update_option_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        body: OptionListUpdateDto,
        user: User = Depends(get_full_user),
    ) -> OptionListDto:
        return await container.option_list_service().update_list(
            workspace_id, list_id, body, user
        )

    @delete(
        "/{workspace_id}/option-lists/{list_id}",
        status_code=HTTPStatus.NO_CONTENT,
        responses={409: {"description": "list_in_use"}},
    )
    async def delete_option_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        await container.option_list_service().delete_list(workspace_id, list_id, user)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @post(
        "/{workspace_id}/option-lists/{list_id}/import",
        responses={
            409: {"description": "list_changed"},
            413: {"description": "file_too_large"},
            422: {"description": "invalid_file, limit_reached, invalid_item"},
        },
    )
    async def import_option_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        request: Request,
        expected_revision: Optional[int] = Query(None, ge=1, alias="expectedRevision"),
        user: User = Depends(get_full_user),
    ) -> OptionListDto:
        """Replace the items with the rows of a CSV sent as the request body
        (``label``, optional ``group`` and ``id``; 1 MB, UTF-8)."""
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > CSV_BYTES_MAX:
            raise HTTPException(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"code": "file_too_large", "message": "The file is larger than 1 MB."},
            )
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > CSV_BYTES_MAX:
                raise HTTPException(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {
                        "code": "file_too_large",
                        "message": "The file is larger than 1 MB.",
                    },
                )
        return await container.option_list_service().import_csv(
            workspace_id, list_id, body, user, expected_revision
        )

    @get("/{workspace_id}/option-lists/{list_id}/export")
    async def export_option_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        user: User = Depends(get_full_user),
    ) -> Response:
        content = await container.option_list_service().export_csv(
            workspace_id, list_id, user
        )
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="list.csv"',
                "Cache-Control": "no-store",
            },
        )

    @post(
        "/{workspace_id}/option-sources/preview",
        responses={
            403: {"description": "option_source_forbidden"},
            422: {"description": "option_source_invalid"},
        },
    )
    async def preview_option_source(
        self,
        workspace_id: RecordId,
        body: SourcePreviewRequest,
        response: Response,
        user: User = Depends(get_full_user),
    ):
        """What a source offers now (labels and counts), for the form builder.
        Needs ``form.edit``; another form's answers also need ``response.read``
        on that form. Never cached."""
        response.headers["Cache-Control"] = "no-store"
        await container.authorization_service().authorize(
            user, Permission.FORM_EDIT, workspace_id
        )
        service = container.option_source_service()
        source = body.source.model_dump(exclude_none=True)
        await service.authorize_source(workspace_id, source, user, body.form_id)
        return await service.preview(
            workspace_id, source, body.parent_labels, body.q, body.limit, body.offset
        )
