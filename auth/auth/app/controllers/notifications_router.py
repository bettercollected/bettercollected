"""Notification mails the backend sends on behalf of the signed-in user who
caused them (rules in ``services/notification_service.py``). Only the backend
may call this: requests must carry the shared internal key
(``AUTH_INTERNAL_NOTIFY_KEY``); a user's token alone is refused, or any
signed-in user could mail any address from this instance's domain.
The user's token still names who caused the notice, for the per-sender cap."""

from http import HTTPStatus
from typing import Optional

from classy_fastapi import Routable, post
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.background import BackgroundTasks

from auth.app.container import container
from auth.app.controllers.admin_router import get_bearer_user
from auth.app.controllers.internal_key import require_internal_key
from auth.app.exceptions import HTTPException
from auth.app.router import router
from auth.app.services.notification_service import (
    NotificationService,
    is_allowed_submission_link,
    one_line,
)
from common.models.user import User


class SubmissionUpdateNotice(BaseModel):
    """Structured fields only: the mail's wording is fixed."""

    model_config = ConfigDict(extra="forbid")

    recipient: EmailStr
    form_title: str = Field(..., min_length=1, max_length=1000)
    workspace_title: Optional[str] = Field(None, max_length=1000)
    link: str = Field(..., max_length=2000)


@router(prefix="/notifications", tags=["Notifications"])
class NotificationsRouter(Routable):
    def __init__(
        self, notification_service=container.notification_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.notification_service: NotificationService = notification_service

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
        )
        return {"message": "Notice queued."}
