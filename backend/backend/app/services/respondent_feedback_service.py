"""Staff post feedback on a submission (rules in ``respondent_feedback``)."""

import datetime as dt
from http import HTTPStatus
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.models.standard_form import RespondentFeedback
from common.models.user import User
from common.services.http_client import HttpClient
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.respondent_feedback_dto import (
    RespondentFeedbackPost,
    StaffFeedback,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.services.respondent_feedback import (
    current_status,
    decrypt_feedback,
    emails_respondent,
    encrypt_message,
    feedback_entries,
    staff_feedback,
)
from backend.config import settings

ONLY_ADMINS = "Only workspace admins can respond to submissions."
FEEDBACK_OFF = (
    "Responding to submissions is turned off for this form. "
    "Turn it on in the form's settings first."
)
# The auth service sends the notice (its mail templates and SMTP settings).
NOTIFY_PATH = "/notifications/submission-update"
INTERNAL_KEY_HEADER = "X-Internal-Key"
NOTIFY_TIMEOUT_SECONDS = 10


class RespondentFeedbackService:
    def __init__(
        self,
        form_response_repo: FormResponseRepository,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        workspace_user_repo: WorkspaceUserRepository,
        workspace_repo: WorkspaceRepository,
        http_client: HttpClient,
    ):
        self._form_response_repo = form_response_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._workspace_user_repo = workspace_user_repo
        self._workspace_repo = workspace_repo
        self._http_client = http_client

    async def post_feedback(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        response_id: str,
        body: RespondentFeedbackPost,
        user: User,
        access_token: Optional[str] = None,
    ) -> StaffFeedback:
        """Append one update for the respondent of ``response_id``.

        Workspace admins and the owner only (an active membership as well).
        The form must have feedback turned on, and a status must be one of
        the form's current statuses (422 otherwise). The respondent is
        emailed a notice when ``emails_respondent``; that mail going wrong
        never fails the update. ``access_token`` is the poster's, forwarded
        to the auth service that sends the mail."""
        if not await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN)
        if not await self._workspace_user_repo.is_user_admin_in_workspace(
            workspace_id, user
        ):
            raise HTTPException(HTTPStatus.FORBIDDEN, content=ONLY_ADMINS)
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id, form_id
            )
        )
        if not workspace_form:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "Form not found in the workspace."
            )
        response = await self._form_response_repo.get_response(response_id)
        if not response or str(response.form_id) != str(workspace_form.form_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        form_settings = workspace_form.settings
        if not form_settings.respondent_feedback_enabled:
            raise HTTPException(HTTPStatus.BAD_REQUEST, FEEDBACK_OFF)

        status = None
        if body.status is not None:
            # the form's own spelling, matched ignoring case
            statuses = {s.casefold(): s for s in form_settings.feedback_statuses or []}
            status = statuses.get(body.status.casefold())
            if status is None:
                raise HTTPException(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"'{body.status}' is not one of this form's statuses.",
                )

        entry = RespondentFeedback(
            id=str(uuid4()),
            status=status,
            message=encrypt_message(workspace_id, response.form_id, body.message),
            created_at=dt.datetime.now(dt.timezone.utc),
            created_by=str(user.id),
            created_by_email=user.sub,
        )
        saved = await self._form_response_repo.add_respondent_feedback(
            response.response_id, entry
        )
        if saved is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)

        notifies = emails_respondent(form_settings, saved)
        if notifies:
            await self._notify_respondent(
                workspace_id, saved, access_token=access_token
            )

        entries = decrypt_feedback(workspace_id, saved.form_id, feedback_entries(saved))
        return StaffFeedback(
            entries=staff_feedback(entries),
            current_status=current_status(entries),
            can_post=True,
            notifies_respondent=notifies,
        )

    async def _notify_respondent(
        self, workspace_id: PydanticObjectId, response, access_token: Optional[str]
    ) -> bool:
        """Ask the auth service to email the respondent a notice that links to
        their submission page. Never the status or the message: only the form
        title, the organisation and the link. Failures are logged (without
        the address) and swallowed: the update is already stored."""
        try:
            if not access_token:
                raise ValueError("no access token to forward")
            workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
            form = await self._form_repo.get_form_document_by_id(response.form_id)
            link = submission_link(workspace.workspace_name, response.response_id)
            await self._http_client.post(
                settings.auth_settings.BASE_URL + NOTIFY_PATH,
                json={
                    "recipient": response.dataOwnerIdentifier,
                    "form_title": (form.title if form else None) or "a form",
                    "workspace_title": workspace.title or None,
                    "link": link,
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    INTERNAL_KEY_HEADER: settings.auth_settings.INTERNAL_NOTIFY_KEY,
                },
                timeout=NOTIFY_TIMEOUT_SECONDS,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — the update is already stored
            logger.warning(
                f"Feedback notice for response {response.response_id} not sent "
                f"({type(exc).__name__})"
            )
            return False


def submission_link(workspace_name: str, response_id: str) -> str:
    """The respondent's own submission page on the client host (signed-in
    view). Always the client host, never a custom domain: the auth service
    only sends links to the hosts it is configured with."""
    base = (settings.api_settings.CLIENT_URL or "").rstrip("/")
    path = (
        f"/{quote(workspace_name, safe='')}/submissions/{quote(response_id, safe='')}"
    )
    return base + path
