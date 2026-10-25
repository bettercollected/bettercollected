"""Notification mails the backend sends on behalf of the signed-in user who
caused them (rules in ``services/notification_service.py``). Only the backend
may call this: requests must carry the shared internal key
(``AUTH_INTERNAL_NOTIFY_KEY``); a user's token alone is refused, or any
signed-in user could mail any address from this instance's domain.
The user's token still names who caused the notice, for the per-sender cap."""

from http import HTTPStatus
from typing import Optional

from classy_fastapi import Routable, post
from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.background import BackgroundTasks

from auth.app.container import container
from auth.app.controllers.internal_key import require_internal_key
from auth.app.exceptions import HTTPException
from auth.app.router import router
from auth.app.services.auth_service import AuthService
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.notification_service import (
    NotificationService,
    is_allowed_submission_link,
    one_line,
    sheets_reconnect_link,
)
from common.models.user import User


def get_bearer_user(authorization: Optional[str] = Header(None)) -> User:
    """The caller from a ``Bearer`` token; 401 without a valid one."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Authorization token is missing.")
    try:
        return AuthService.get_logged_user(token)
    except Exception:  # noqa: BLE001 — expired, forged or malformed alike
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid authorization token.")


class SubmissionUpdateNotice(BaseModel):
    """Structured fields only: the mail's wording is fixed."""

    model_config = ConfigDict(extra="forbid")

    recipient: EmailStr
    form_title: str = Field(..., min_length=1, max_length=1000)
    workspace_title: Optional[str] = Field(None, max_length=1000)
    link: str = Field(..., max_length=2000)
    # the mail's language (the form's); English unless Dutch
    locale: Optional[str] = Field(None, max_length=35)


class SheetsReconnectNotice(BaseModel):
    """A form's Google Sheets action must be reconnected: the auth service
    finds the billing owner's address and builds the link itself."""

    model_config = ConfigDict(extra="forbid")

    # the workspace's billing owner (owner_id)
    user_id: str = Field(..., min_length=1, max_length=64)
    workspace_name: str = Field(..., min_length=1, max_length=200)
    workspace_title: Optional[str] = Field(None, max_length=1000)
    form_id: str = Field(..., min_length=1, max_length=64)
    form_title: Optional[str] = Field(None, max_length=1000)
    locale: Optional[str] = Field(None, max_length=35)


@router(prefix="/notifications", tags=["Notifications"])
class NotificationsRouter(Routable):
    def __init__(
        self,
        notification_service=container.notification_service(),
        user_repository=container.user_repository(),
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.notification_service: NotificationService = notification_service
        self.user_repository: UserRepository = user_repository

    @post("/submission-update")
    async def send_submission_update(
        self,
        notice: SubmissionUpdateNotice,
        background_tasks: BackgroundTasks,
        _: None = Depends(require_internal_key),
        user: User = Depends(get_bearer_user),
    ):
        """Tell a respondent that staff responded to their submission. The
        mail names the form and links to the submission page; it never
        carries the update itself."""
        if not is_allowed_submission_link(notice.link):
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "The link must point at a submission page of this instance.",
            )
        if not self.notification_service.allow(str(user.id)):
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS, "Too many notices; try again later."
            )
        background_tasks.add_task(
            self.notification_service.send_submission_update,
            recipient=str(notice.recipient),
            form_title=one_line(notice.form_title),
            workspace_title=one_line(notice.workspace_title),
            link=notice.link,
            locale=notice.locale,
        )
        return {"message": "Notice queued."}

    @post("/sheets-reconnect")
    async def send_sheets_reconnect(
        self,
        notice: SheetsReconnectNotice,
        background_tasks: BackgroundTasks,
        _: None = Depends(require_internal_key),
    ):
        """Tell a workspace's billing owner, once per action (the backend keeps
        the marker), that a form's Google Sheets connection must be renewed.
        Sent by the backend on its own (a submission or the builder found the
        old grant), so no user token: the internal key alone."""
        link = sheets_reconnect_link(notice.workspace_name, notice.form_id)
        if link is None:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Unknown workspace handle or form id shape.",
            )
        if not self.notification_service.allow(f"sheets-reconnect:{notice.user_id}"):
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS, "Too many notices; try again later."
            )
        try:
            owner = await self.user_repository.get_user_by_id(notice.user_id)
        except Exception:  # noqa: BLE001 — a malformed id finds nobody
            owner = None
        email = getattr(owner, "email", None)
        if not email:
            # nobody to tell: the backend keeps its marker, no retries
            return {"message": "No recipient."}
        background_tasks.add_task(
            self.notification_service.send_sheets_reconnect,
            recipient=str(email),
            form_title=one_line(notice.form_title),
            workspace_title=one_line(notice.workspace_title),
            link=link,
            locale=notice.locale,
        )
        return {"message": "Notice queued."}
