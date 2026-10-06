from http import HTTPStatus
from typing import Any, List

from beanie import PydanticObjectId
from classy_fastapi import delete, get, patch, post
from common.models.user import User
from fastapi import Depends
from starlette.requests import Request
from starlette.responses import Response
from fastapi_pagination import Page

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.controllers.platform_metrics_router import forwarded_access_token
from backend.app.decorators.user_tag_decorators import user_tag_from_workspace
from backend.app.models.dtos.flow_event_dto import FlowEventRequest
from backend.app.models.dtos.form_response_dto import (
    InternalAnswersPatch,
    InternalAnswersResponse,
)
from backend.app.models.dtos.respondent_feedback_dto import (
    RespondentFeedbackPost,
    StaffFeedback,
)
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.repositories.flow_event_repository import FlowEventRepository
from backend.app.router import router
from backend.app.services.flow_event_service import FlowEventService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.respondent_feedback_service import (
    RespondentFeedbackService,
)
from backend.app.services.user_service import get_logged_user
from backend.app.utils.client_ip import client_ip
from backend.app.utils.custom_routable import CustomRoutable
from backend.app.utils.flow_analytics import aggregate_flow_events
from backend.config import settings


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
        flow_event_repo: FlowEventRepository = container.flow_event_repo(),
        respondent_feedback_service: RespondentFeedbackService = (
            container.respondent_feedback_service()
        ),
        flow_event_service: FlowEventService = container.flow_event_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_response_service = form_response_service
        self._respondent_feedback_service = respondent_feedback_service
        self._flow_event_repo = flow_event_repo
        self._flow_event_service = flow_event_service

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
        """Every response of the form, for the flow view (response.read)."""
        responses = (
            await self._form_response_service.get_workspace_form_all_submissions(
                form_id, workspace_id, user
            )
        )
        return responses

    @get(
        "/forms/{form_id}/all-submissions/export",
        response_model=List[StandardFormResponseCamelModel],
    )
    async def export_workspace_form_submissions(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """Every response of the form for the CSV download (response.export)."""
        return await self._form_response_service.get_workspace_form_all_submissions(
            form_id, workspace_id, user, permission=Permission.RESPONSE_EXPORT
        )

    @patch(
        "/forms/{form_id}/submissions/{submission_id}/internal-answers",
        response_model=InternalAnswersResponse,
    )
    async def update_internal_answers(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        submission_id: str,
        body: InternalAnswersPatch,
        user: User = Depends(get_logged_user),
    ):
        """Staff fill in the form's internal fields on one submission. Only
        workspace members; respondents can neither read nor write these."""
        return await self._form_response_service.update_internal_answers(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=submission_id,
            answers=body.answers,
            user=user,
            expected_version=body.version,
        )

    @post(
        "/forms/{form_id}/submissions/{submission_id}/feedback",
        response_model=StaffFeedback,
    )
    async def post_respondent_feedback(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        submission_id: str,
        body: RespondentFeedbackPost,
        request: Request,
        response: Response,
        user: User = Depends(get_logged_user),
    ):
        """Workspace admins post an update (status and/or message) that the
        submission's respondent sees; the respondent may be emailed a notice
        (never the update itself). Returns the history, staff view."""
        return await self._respondent_feedback_service.post_feedback(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=submission_id,
            body=body,
            user=user,
            access_token=forwarded_access_token(request, response),
        )

    @post("/forms/{form_id}/flow-events")
    async def record_flow_event(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        event: FlowEventRequest,
        request: Request,
    ):
        """
        Record one anonymous navigation step from a responder. Public and
        fire-and-forget by design: no answers, no identity — see
        FlowEventDocument. Only for a published form of this workspace (404
        otherwise, the same for unknown and unpublished), between pages of
        its published version (422), and at most
        API_FLOW_EVENTS_PER_WINDOW per client and form per window (429).
        """
        if len(form_id) > 64:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        await self._flow_event_service.record(
            workspace_id=workspace_id,
            form_ref=form_id,
            event=event,
            client=client_ip(request, settings.api_settings.TRUSTED_PROXIES),
        )
        return {"ok": True}

    @get("/forms/{form_id}/flow-analytics")
    async def get_flow_analytics(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """Aggregate drop-off + transition counts for the builder's Insights overlay."""
        await self._form_response_service.check_member_and_form_in_workspace(
            workspace_id, form_id, user
        )
        events = await self._flow_event_repo.list_by_form_id(form_id)
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
