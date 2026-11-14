"""The challenge route of the proof of work (``services/captcha``,
docs/captcha.md): ``POST /workspaces/{id}/captcha/challenge``.

Public, stateless (nothing is stored, no cookie is set) and never cacheable.
The session is read only to learn that the respondent is signed in, which
lowers the difficulty. While ``CAPTCHA_ENABLED`` is off it answers 404 before
it looks at anything.
"""

from http import HTTPStatus
from typing import Literal, Optional

from classy_fastapi import Routable, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from starlette.requests import Request

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.captcha import mode
from backend.app.services.user_service import get_user_if_logged_in
from backend.app.utils.client_ip import limit_client_ip


class ChallengeBody(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    purpose: Literal["submit"]
    form_id: str = Field(min_length=1, max_length=200)


@router(
    prefix="/workspaces/{workspace_id}/captcha",
    tags=["Spam check"],
    responses={
        404: {"description": "No such form, or the spam check is not switched on."},
        429: {"description": "Too many challenge requests."},
    },
)
class CaptchaRouter(Routable):
    @post("/challenge")
    async def challenge(
        self,
        workspace_id: RecordId,
        body: ChallengeBody,
        request: Request,
        response: Response,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """A signed challenge for a response to the form: the browser finds the
        counters it asks for and sends them in the ``X-BC-Captcha`` header
        (single use, valid 15 minutes, bound to this workspace, form and
        network). Limited per client (429 with Retry-After)."""
        if not mode.captcha_enabled():
            raise mode.off_error()
        response.headers["Cache-Control"] = "no-store"
        service = container.captcha_service()
        client = limit_client_ip(request)
        service.allow_request(client, body.purpose)
        # looked up the way the submit does it (submit_response): the forms this
        # respondent may answer, so a private form they may answer gets a
        # challenge like any other, and one they may not, or one of another
        # workspace, answers like one that does not exist
        repo = container.workspace_form_repo()
        visible = await repo.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=True,
            user=user,
            form_id_or_slug=body.form_id,
        )
        link = (
            await repo.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=body.form_id
            )
            if visible
            else None
        )
        if link is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                content={"code": "form_not_found", "message": "Form not found."},
            )
        issued = service.issue(
            purpose=body.purpose,
            workspace_id=workspace_id,
            form_id=str(link.form_id),
            client=client,
            signed_in=user is not None,
        )
        if issued is None:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content={
                    "code": "captcha_unavailable",
                    "message": "The spam check is not available.",
                },
            )
        return issued
