from typing import Any, List

from beanie import PydanticObjectId
from classy_fastapi import delete, get, post
from common.models.user import User
from fastapi import Depends
from fastapi_camelcase import CamelModel
from fastapi_pagination import Page

from backend.app.container import container
from backend.app.decorators.user_tag_decorators import user_tag_from_workspace
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.router import router
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.user_service import get_logged_user
from backend.app.utils.custom_routable import CustomRoutable
from backend.app.utils.flow_analytics import aggregate_flow_events


class FlowEventRequest(CamelModel):
    session_id: str
    from_page: str
    to_page: str


@router(
    prefix="/workspaces/{workspace_id}",
    tags=["Workspace Form Submissions"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class WorkspaceResponsesRouter(CustomRoutable):
    def __init__(
        self,
        form_response_service: FormResponseService = container.form_response_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_response_service = form_response_service

    @get(
        "/forms/{form_id}/submissions",
        response_model=Page[StandardFormResponseCamelModel],
    )
    async def _get_workspace_form_responses(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        filter_query: FormResponseFilterQuery = Depends(None),
        sort: SortRequest = Depends(),
        request_for_deletion: bool = False,
        user: User = Depends(get_logged_user),
    ):
        responses = await self._form_response_service.get_workspace_form_submissions(
            workspace_id, request_for_deletion, form_id, filter_query, sort, user
        )
        return responses

    @get(
        "/forms/{form_id}/all-submissions",
        response_model=List[StandardFormResponseCamelModel],
    )
    async def get_workspace_form_all_submissions(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        responses = (
            await self._form_response_service.get_workspace_form_all_submissions(
                form_id, workspace_id, user
            )
        )
        return responses

    @post("/forms/{form_id}/flow-events")
    async def record_flow_event(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        event: FlowEventRequest,
    ):
        """
        Record one anonymous navigation step from a responder. Public and
        fire-and-forget by design: no answers, no identity — see
        FlowEventDocument. Inputs are length-capped so the open endpoint can't
        be used to store arbitrary payloads.
        """
        if len(event.session_id) > 64 or len(event.from_page) > 64 or len(event.to_page) > 64:
            return {"ok": False}
        await FlowEventDocument(
            form_id=form_id,
            session_id=event.session_id,
            from_page=event.from_page,
            to_page=event.to_page,
        ).save()
        return {"ok": True}

    @get("/forms/{form_id}/flow-analytics")
    async def get_flow_analytics(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """Aggregate drop-off + transition counts for the builder's Insights overlay."""
        events = await FlowEventDocument.find(
            FlowEventDocument.form_id == form_id
        ).to_list()
        return aggregate_flow_events([e.model_dump() for e in events])

    @get(
        "/all-submissions",
        response_model=Page[StandardFormResponseCamelModel | Any],
    )
    async def _get_all_workspace_responses(
        self,
        workspace_id: PydanticObjectId,
        filter_query: FormResponseFilterQuery = Depends(None),
        sort: SortRequest = Depends(None),
        request_for_deletion: bool = False,
        user=Depends(get_logged_user),
    ):
        responses = await self._form_response_service.get_all_workspace_responses(
            workspace_id=workspace_id,
            filter_query=filter_query,
            sort=sort,
            request_for_deletion=request_for_deletion,
            user=user,
        )
        return responses

    @get(
        "/submissions",
        response_model=Page[StandardFormResponseCamelModel],
    )
    async def _get_user_submissions_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        request_for_deletion: bool = False,
        user: User = Depends(get_logged_user),
    ):
        submissions = await self._form_response_service.get_user_submissions(
            workspace_id, user, request_for_deletion
        )
        return submissions

    @get(
        "/submissions/{submission_id}",
    )
    async def _get_workspace_form_response(
        self,
        workspace_id: PydanticObjectId,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submission(
            workspace_id, submission_id, user
        )

    @get("/submissions/by-uuid/{submission_uuid}")
    async def get_submission_by_uuid(
        self, workspace_id: PydanticObjectId, submission_uuid: str
    ):
        return await self._form_response_service.get_by_uuid(
            submission_uuid=submission_uuid, workspace_id=workspace_id
        )

    @delete(
        "/submissions/{submission_id}",
    )
    @user_tag_from_workspace(tag=UserTagType.DELETION_REQUEST_RECEIVED)
    async def _request_workspace_form_response_delete(
        self,
        workspace_id: PydanticObjectId,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        await self._form_response_service.request_for_response_deletion(
            workspace_id, submission_id, user
        )
        return {"message": "Request for deletion created successfully."}

    @delete("/submissions/by-uuid/{submission_uuid}")
    async def _request_workspace_form_response_delete_by_uuid(
        self, workspace_id: PydanticObjectId, submission_uuid: str
    ):
        await self._form_response_service.request_for_response_deletion_by_uuid(
            workspace_id, submission_uuid
        )
        return {"message": "Request for deletion created successfully."}
