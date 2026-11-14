"""The routes of the proof of work (``services/captcha``, docs/captcha.md):

* ``POST /workspaces/{id}/captcha/challenge``: a challenge for a response
  (purpose ``submit``, with the form) or for a mail (purpose ``mail``: the
  workspace's sign-in code, with no form, or a form's draft link, with it);
* ``POST /auth/captcha/challenge``: a challenge for the creator's sign-in code
  (purpose ``mail``, no workspace);
* ``GET|PUT /workspaces/{id}/captcha/settings``: the workspace's default;
* ``GET /workspaces/{id}/captcha/stats`` and
  ``GET /workspaces/{id}/forms/{form_id}/captcha/stats``: counts by day, no person.

The challenge routes are public, stateless (nothing is stored, no cookie is set)
and never cacheable. The session is read only to learn that a respondent is
signed in, which lowers the difficulty of a ``submit`` challenge. While
``CAPTCHA_ENABLED`` is off every route answers 404 before it looks at anything
(a change of the default answers 422 ``captcha_disabled``).
"""

from http import HTTPStatus
from typing import Literal, Optional

from classy_fastapi import Routable, get, post, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from starlette.requests import Request

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.captcha import mode
from backend.app.services.captcha.settings import (
    CaptchaSettingsDto,
    SetCaptchaDefaultDto,
)
from backend.app.services.user_service import get_logged_user, get_user_if_logged_in
from backend.app.utils.client_ip import limit_client_ip


class ChallengeBody(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    purpose: Literal["submit", "mail"]
    # a submit names its form; a mail names one only for a form's draft link
    form_id: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _submit_needs_a_form(self):
        if self.purpose == "submit" and not self.form_id:
            raise ValueError("A submit challenge names its form.")
        return self


class CreatorChallengeBody(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    purpose: Literal["mail"]


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.NOT_FOUND, content={"code": code, "message": message}
    )


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={
            "code": "captcha_unavailable",
            "message": "The spam check is not available.",
        },
    )


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
        """A signed challenge: the browser finds the counters it asks for and
        sends them in the ``X-BC-Captcha`` header (single use, valid 15
        minutes, bound to this purpose, workspace, form and network). Limited
        per client (429 with Retry-After)."""
        if not mode.captcha_enabled():
            raise mode.off_error()
        response.headers["Cache-Control"] = "no-store"
        service = container.captcha_service()
        client = limit_client_ip(request)
        service.allow_request(client, body.purpose)
        repo = container.workspace_form_repo()
        form_id = ""
        if body.form_id:
            # looked up the way the submit does it (submit_response): the forms
            # this respondent may answer, so a private form they may answer gets
            # a challenge like any other, and one they may not, or one of another
            # workspace, answers like one that does not exist
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
                raise _not_found("form_not_found", "Form not found.")
            form_id = str(link.form_id)
        elif await container.workspace_repo().find_by_id(workspace_id) is None:
            # the workspace's sign-in code: it must exist (the code route mails
            # nothing for one that does not)
            raise _not_found("workspace_not_found", "Workspace not found.")
        issued = service.issue(
            purpose=body.purpose,
            workspace_id=workspace_id,
            form_id=form_id,
            client=client,
            signed_in=user is not None,
        )
        if issued is None:
            raise _unavailable()
        return issued

    @get("/settings")
    async def get_settings(
        self, workspace_id: RecordId, user: User = Depends(get_logged_user)
    ) -> CaptchaSettingsDto:
        """The workspace's default (``workspace.manage``)."""
        return await container.captcha_settings_service().get(workspace_id, user)

    @put("/settings")
    async def set_settings(
        self,
        workspace_id: RecordId,
        body: SetCaptchaDefaultDto,
        user: User = Depends(get_logged_user),
    ) -> CaptchaSettingsDto:
        """Set the workspace's default (``workspace.manage``; recorded in the
        audit log; 422 ``captcha_disabled`` while the server switch is off)."""
        return await container.captcha_settings_service().set_default(
            workspace_id, user, body.captcha_default
        )

    @get("/stats")
    async def workspace_stats(
        self, workspace_id: RecordId, user: User = Depends(get_logged_user)
    ):
        """The last 30 days of the workspace, by purpose: proofs that passed and
        proofs refused. Counts only (``workspace.manage``)."""
        return await container.captcha_settings_service().workspace_counts(
            workspace_id, user
        )


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/captcha",
    tags=["Spam check"],
    responses={404: {"description": "No such form, or the spam check is off."}},
)
class FormCaptchaRouter(Routable):
    @get("/stats")
    async def form_stats(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        """The last 30 days of one form, by purpose: proofs that passed and
        proofs refused. Counts only (``analytics.read`` on the form)."""
        return await container.captcha_settings_service().form_counts(
            workspace_id, form_id, user
        )


@router(
    prefix="/auth/captcha",
    tags=["Spam check"],
    responses={
        404: {"description": "The spam check is not switched on."},
        429: {"description": "Too many challenge requests."},
    },
)
class CreatorCaptchaRouter(Routable):
    @post("/challenge")
    async def challenge(
        self, body: CreatorChallengeBody, request: Request, response: Response
    ):
        """A challenge for the creator's sign-in code mail (purpose ``mail``,
        bound to no workspace and no form)."""
        if not mode.captcha_enabled():
            raise mode.off_error()
        response.headers["Cache-Control"] = "no-store"
        service = container.captcha_service()
        client = limit_client_ip(request)
        service.allow_request(client, body.purpose)
        issued = service.issue(
            purpose=body.purpose,
            workspace_id="",
            form_id="",
            client=client,
            signed_in=False,
        )
        if issued is None:
            raise _unavailable()
        return issued
