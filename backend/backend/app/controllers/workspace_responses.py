from http import HTTPStatus
from typing import Any, List, Optional

from common.ids import RecordId
from classy_fastapi import delete, get, patch, post
from common.models.user import User
from fastapi import BackgroundTasks, Depends, Query
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response
from fastapi_pagination import Page, Params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.user_service import forwarded_access_token
from backend.app.decorators.user_tag_decorators import user_tag_from_workspace
from backend.app.models.dtos.deletion_request_dto import (
    ClosedDeletionRequest,
    CloseDeletionRequestBody,
)
from backend.app.models.dtos.address_lookup_dto import AddressLookupRequest
from backend.app.models.dtos.flow_event_dto import FlowEventRequest
from backend.app.models.dtos.form_response_dto import (
    InternalAnswersPatch,
    InternalAnswersResponse,
    SubmissionPath,
)
from backend.app.models.dtos.respondent_feedback_dto import (
    RespondentFeedbackPost,
    StaffFeedback,
)
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.dtos.response_list_page import ResponseListPage
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.response_list import (
    KEYSET_SORTS,
    ResponseListFilters,
    ResponseListOptions,
    ResponseListQuery,
    response_list_options,
)
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.repositories.postgres.analytics import PostgresFlowEventRepository
from backend.app.router import router
from backend.app.services.address_lookup.service import AddressLookupService
from backend.app.services.flow_event_service import FlowEventService
from backend.app.services.option_sources.service import OptionSourceService
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.receipt_limits import (
    DELETION_REQUEST as RECEIPT_DELETION_REQUEST,
    READ as RECEIPT_READ,
    ReceiptLimits,
)
from backend.app.services.respondent_feedback_service import (
    RespondentFeedbackService,
)
from backend.app.services.response_export.http import NO_STORE as EXPORT_NO_STORE
from backend.app.services.response_export.http import attachment
from backend.app.services.signatures import carry_headers, read_throttle
from backend.app.services.user_service import (
    get_full_user,
    get_logged_user,
    get_user_if_logged_in,
)
from backend.app.utils.client_ip import request_client_ip
from backend.app.utils.custom_routable import CustomRoutable
from backend.app.utils.flow_analytics import aggregate_flow_events


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
        flow_event_repo: PostgresFlowEventRepository = container.flow_event_repo(),
        respondent_feedback_service: RespondentFeedbackService = (
            container.respondent_feedback_service()
        ),
        flow_event_service: FlowEventService = container.flow_event_service(),
        receipt_limits: ReceiptLimits = container.receipt_limits(),
        address_lookup_service: AddressLookupService = (
            container.address_lookup_service()
        ),
        option_source_service: OptionSourceService = (
            container.option_source_service()
        ),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_response_service = form_response_service
        self._respondent_feedback_service = respondent_feedback_service
        self._flow_event_repo = flow_event_repo
        self._flow_event_service = flow_event_service
        self._receipt_limits = receipt_limits
        self._address_lookup_service = address_lookup_service
        self._option_source_service = option_source_service

    @get(
        "/forms/{form_id}/submissions",
        response_model=ResponseListPage[StandardFormResponseCamelModel],
    )
    async def _get_workspace_form_responses(
        self,
        workspace_id: RecordId,
        form_id: str,
        filter_query: FormResponseFilterQuery = Depends(None),
        sort: SortRequest = Depends(),
        request_for_deletion: bool = False,
        list_options: ResponseListOptions = Depends(response_list_options),
        params: Params = Depends(),
        user: User = Depends(get_logged_user),
    ):
        """A page of the form's responses (``response.read``), or of its
        deletion requests (``privacy.manage``).

        As before: ``page``, ``size``, the ``dataOwnerIdentifier`` search and
        ``sort_by`` / ``sort_order`` (any stored field, offset paging). New:
        ``paging=keyset``, or any of the filters ``submittedFrom`` /
        ``submittedTo`` (UTC instants), ``status`` (deletion request: none,
        pending, declined, success), ``respondent`` (anonymous, known) and
        ``formVersion``, or a ``cursor``, serve the list from the sort index:
        ``sort_by`` is then ``created_at`` (submitted time) or
        ``form_version``, the page carries ``totalExact``, ``hasNext`` and the
        ``cursor`` to send back for a page near it. Not for deletion requests.
        """
        if list_options.keyset:
            if request_for_deletion:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    "Filters and cursors are not available for deletion requests.",
                )
            if sort.sort_by not in KEYSET_SORTS:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    f"Sort by one of: {', '.join(KEYSET_SORTS)}.",
                )
            order = (sort.sort_order or SortOrder.DESCENDING).upper()
            if order not in ("ASCENDING", "DESCENDING", "ASC", "DESC"):
                raise HTTPException(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "sort_order is ASCENDING or DESCENDING.",
                )
            try:
                query = ResponseListQuery(
                    filters=ResponseListFilters(
                        **list_options.filters,
                        search=(
                            filter_query.data_owner_identifier
                            if filter_query
                            else None
                        ),
                    ),
                    sort_by=sort.sort_by,
                    descending=not order.startswith("ASC"),
                    page=params.page,
                    size=params.size,
                    cursor=list_options.cursor,
                )
            except ValidationError:
                # e.g. a search longer than the 320 characters of an address
                raise HTTPException(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "The search is too long (at most 320 characters).",
                ) from None
            return await self._form_response_service.get_workspace_form_response_page(
                workspace_id, form_id, query, user
            )
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
        workspace_id: RecordId,
        form_id: str,
        background_tasks: BackgroundTasks,
        user: User = Depends(get_logged_user),
    ):
        """Every response of the form, decrypted and unpaginated: a bulk
        download, so response.export. The webapp's export is
        ``POST .../exports`` (streamed or a job); this route is audited and
        rate limited the same way (``services/response_export``); the flow view
        reads ``.../submission-paths``."""
        return await container.response_export_service().bulk_read(
            workspace_id, form_id, user, background_tasks
        )

    @get(
        "/forms/{form_id}/submission-paths",
        response_model=List[SubmissionPath],
    )
    async def get_workspace_form_submission_paths(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """Each submission's path through the form's pages (page ids, jumps
        taken, ending reached), no answers: the flow view's insights
        (response.read)."""
        return await self._form_response_service.get_workspace_form_submission_paths(
            form_id, workspace_id, user
        )

    @patch(
        "/forms/{form_id}/submissions/{submission_id}/internal-answers",
        response_model=InternalAnswersResponse,
    )
    async def update_internal_answers(
        self,
        workspace_id: RecordId,
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
        "/forms/{form_id}/submissions/{submission_id}/deletion-request/close",
        response_model=ClosedDeletionRequest,
    )
    async def close_deletion_request(
        self,
        workspace_id: RecordId,
        form_id: str,
        submission_id: str,
        body: CloseDeletionRequestBody,
        user: User = Depends(get_logged_user),
    ):
        """Close a pending deletion request by hand (``privacy.manage``),
        without the form's provider: ``completed`` deletes the workspace's
        stored copy of the response, ``declined`` keeps it and records one of
        the fixed reasons. Who and when are kept on the request; 409 when it
        is already closed."""
        closed = await self._form_response_service.close_deletion_request(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=submission_id,
            outcome=body.outcome,
            reason=body.reason,
            user=user,
        )
        return ClosedDeletionRequest(
            form_id=str(closed.form_id),
            response_id=closed.response_id,
            status=closed.status.value,
            closed_by=closed.closed_by,
            closed_at=closed.closed_at,
            decline_reason=closed.decline_reason.value if closed.decline_reason else None,
        )

    @post(
        "/forms/{form_id}/submissions/{submission_id}/feedback",
        response_model=StaffFeedback,
    )
    async def post_respondent_feedback(
        self,
        workspace_id: RecordId,
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

    @post("/forms/{form_id}/address-lookup")
    async def look_up_address(
        self,
        workspace_id: RecordId,
        form_id: str,
        body: AddressLookupRequest,
        request: Request,
        response: Response,
    ):
        """
        Street and city of a Dutch postcode and house number, for an address
        question of a published form (the respondent's form fills them in; the
        respondent can change them). Public, like the form. 404 unless the
        server has the lookup on, the form is published in this workspace, takes
        responses now (not closed, not open yet, not full, not hidden; a private
        form only for a signed-in member of its responder groups) and the
        question asks for a lookup (all the same 404); 422 for input that
        is not a postcode and a house number; 429 per client and form and per
        form; 503 when the service cannot answer (type the address instead).
        Nothing is stored or logged of what was asked.
        """
        response.headers["Cache-Control"] = "no-store"
        return await self._address_lookup_service.lookup(
            workspace_id=workspace_id,
            form_ref=form_id,
            field_id=body.field_id,
            postcode=body.postcode,
            house_number=body.house_number,
            client=request_client_ip(request),
            # read only for a private form, once the cheap limits have held
            user_loader=lambda: get_user_if_logged_in(request, response),
        )

    @get("/forms/{form_id}/options/{field_id}")
    async def get_question_options(
        self,
        workspace_id: RecordId,
        form_id: str,
        field_id: str,
        request: Request,
        response: Response,
        q: Optional[str] = Query(None, max_length=100),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100_000),
        parent: List[str] = Query([]),
    ):
        """
        One page of the choices of a dropdown or multiple choice question whose
        options come from a workspace list or from another form's answers
        (``{items: [{id, label}], total, truncated, available}``: labels only).
        Public, like the form: 404 (the same) unless the form is published in
        this workspace, is one a respondent may fill in now (not hidden, open,
        not full, signed in where it asks for a verified identity, a member of
        its responder groups when private) and has that question with a source;
        429 per client and form and per form. ``parent``: the ids the respondent chose in the
        question this one depends on. Never cached.
        """
        response.headers["Cache-Control"] = "no-store"
        return await self._option_source_service.serve(
            workspace_id=workspace_id,
            form_ref=form_id,
            field_id=field_id,
            query=q,
            limit=limit,
            offset=offset,
            parent_ids=parent,
            client=request_client_ip(request),
            # read only for a form that asks for a signed-in respondent
            user_loader=lambda: get_user_if_logged_in(request, response),
        )

    @post("/forms/{form_id}/flow-events")
    async def record_flow_event(
        self,
        workspace_id: RecordId,
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
            client=request_client_ip(request),
        )
        return {"ok": True}

    @get("/forms/{form_id}/flow-analytics")
    async def get_flow_analytics(
        self,
        workspace_id: RecordId,
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
        workspace_id: RecordId,
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
        workspace_id: RecordId,
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
        workspace_id: RecordId,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_response_service.get_workspace_submission(
            workspace_id, submission_id, user
        )

    @get("/submissions/{submission_id}/signatures/{field_id}")
    async def _get_signature_image(
        self,
        workspace_id: RecordId,
        submission_id: str,
        field_id: str,
        response: Response,
        user: User = Depends(get_logged_user),
    ):
        """A drawn signature's image, decrypted for the people who may read
        the response (services/signatures.py). Never cached, never sniffed,
        never run as a page."""
        await read_throttle(user.sub)
        image = await self._form_response_service.signature_image(
            workspace_id, submission_id, field_id, user
        )
        served = Response(
            content=image,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": 'inline; filename="signature.png"',
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Cross-Origin-Resource-Policy": "same-site",
            },
        )
        # A raw Response replaces the one FastAPI injects, which is where the
        # sign-in dependency puts a refreshed session's cookies: carry them over.
        carry_headers(response, served)
        return served

    @get("/submissions/{submission_id}/pdf")
    async def _get_submission_pdf(
        self,
        workspace_id: RecordId,
        submission_id: str,
        response: Response,
        lang: str | None = Query(None, max_length=16),
        tz: str | None = Query(None, max_length=64),
        user: User = Depends(get_full_user),
    ):
        """The PDF of one response, drawn on demand and never stored, for
        the people who may read it (``response.read``): the form's title, when
        it was submitted (in ``tz``, an IANA zone, default UTC), the answers with
        their questions, in ``lang`` (``en`` or ``nl``). Rate limited and audited
        like an export (docs/response-export.md): who and which response, never
        its content."""
        file = await container.response_export_service().response_pdf(
            workspace_id, submission_id, user, lang, tz
        )
        served = Response(
            content=file.data,
            media_type="application/pdf",
            headers={
                **EXPORT_NO_STORE,
                "Content-Disposition": attachment(file.file_name),
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )
        # the sign-in dependency's refreshed-session cookies live on the injected response
        carry_headers(response, served)
        return served

    # The receipt routes need no sign-in: the number is the credential, so
    # each lookup is rate limited per client address, unknown numbers more
    # strictly (services/receipt_limits.py; 429 with Retry-After).
    @get("/submissions/by-uuid/{submission_uuid}")
    async def get_submission_by_uuid(
        self, workspace_id: RecordId, submission_uuid: str, request: Request
    ):
        async with self._receipt_limits.lookup(
            RECEIPT_READ, request_client_ip(request)
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
        workspace_id: RecordId,
        submission_id: str,
        user: User = Depends(get_logged_user),
    ):
        await self._form_response_service.request_for_response_deletion(
            workspace_id, submission_id, user
        )
        return {"message": "Request for deletion created successfully."}

    @delete("/submissions/by-uuid/{submission_uuid}")
    async def _request_workspace_form_response_delete_by_uuid(
        self, workspace_id: RecordId, submission_uuid: str, request: Request
    ):
        async with self._receipt_limits.lookup(
            RECEIPT_DELETION_REQUEST, request_client_ip(request)
        ):
            await self._form_response_service.request_for_response_deletion_by_uuid(
                workspace_id, submission_uuid
            )
        return {"message": "Request for deletion created successfully."}
