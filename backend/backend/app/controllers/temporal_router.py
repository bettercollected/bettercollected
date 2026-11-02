from common.ids import RecordId
from classy_fastapi import Routable, post, patch
from http import HTTPStatus

from fastapi import Depends, Request, Response
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.action_run_token import (
    EXPIRED,
    HEADER,
    INVALID,
    check_run_token,
    job_matches,
    run_lock,
)
from backend.jobs.app import ACTIONS_QUEUE, app as jobs_app
from backend.app.router import router
from backend.app.services.user_service import get_api_key, get_logged_admin
from backend.app.models.dtos.form_actions_dto import (
    CREDENTIAL_SECRET,
    FormActionsDto,
    RunSecretDto,
)

# the answers below carry a run's data or secrets: never kept by a cache
NO_STORE = "no-store"

SEALED_REFUSED = (
    "Sealed secrets are no longer handed out (ACTION_SECRETS_SEALED_ALLOWED is "
    "off): run an actions executor of version 4.3 or later and remove "
    "AES_HEX_KEY from it."
)


def sealed_secrets_allowed() -> bool:
    """Is ``ACTION_SECRETS_SEALED_ALLOWED`` on (the default): may an actions
    executor older than 4.3 still get the run's secrets sealed and write a
    refreshed credential back on the key-only route?"""
    from backend.config import settings

    return bool(getattr(settings, "ACTION_SECRETS_SEALED_ALLOWED", True))


def refuse_sealed(route: str) -> None:
    """426 with a log line an operator can act on (ids are in the route's own
    access log; no value is ever logged)."""
    logger.error(
        "an actions executor asked for sealed secrets ({}) but "
        "ACTION_SECRETS_SEALED_ALLOWED is off: it is older than 4.3 or has "
        "not been restarted; upgrade it and remove AES_HEX_KEY from it",
        route,
    )
    raise HTTPException(
        status_code=HTTPStatus.UPGRADE_REQUIRED,
        content=SEALED_REFUSED,
        headers={"Cache-Control": NO_STORE},
    )


class CopyRecipientQuery(BaseModel):
    # one address: no longer than an address can be, and not blank
    address: str = Field(max_length=254)

    @field_validator("address")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("address must not be blank")
        return value


class RunContextRequest(BaseModel):
    """What the executor asks of the run's data. ``plain``: this action's
    secrets opened (the executor of 4.3 and later, which holds no key); the
    default, ``sealed``, is what every older executor gets."""

    secrets: Literal["sealed", "plain"] = "sealed"


@router(
    prefix="/temporal",
    tags=["Temporal Router"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        403: {"description": "You are not allowed to perform this action."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class TemporalRouter(Routable):
    def __init__(
        self,
        form_schedular=container.form_schedular(),
        form_actions_service=container.form_actions_service(),
        copy_recipient_service=container.copy_recipient_service(),
        action_service=container.action_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.form_schedular = form_schedular
        self.form_actions_service = form_actions_service
        self.copy_recipient_service = copy_recipient_service
        self.action_service = action_service

    @patch("/forms/{form_id}/actions/{action_id}/secrets")
    async def patch_form_secrets(
        self,
        form_id: RecordId,
        action_id: RecordId,
        payload: FormActionsDto,
        response: Response,
        api_key=Depends(get_api_key),
    ):
        """The key-only route of executors older than 4.3 (they refresh a Google
        credential and write it back sealed with their own copy of the key). It
        replaces the ``Credentials`` secret of the form's action and nothing
        else, and is refused with 426 once ``ACTION_SECRETS_SEALED_ALLOWED`` is
        off. Removed in 4.4: the run-scoped route below replaces it."""
        response.headers["Cache-Control"] = NO_STORE
        if not sealed_secrets_allowed():
            refuse_sealed("key-only credential write-back")
        if payload.name != CREDENTIAL_SECRET:
            # only the credential is an executor's to replace: not whatever
            # sealed text it has seen, under any other name of any action
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content="Only the credential can be replaced here.",
            )
        await self.form_actions_service.update_form_secrets(form_id, action_id, payload)
        # never echo the form back: it carries every action's secrets
        return "Updated"

    @post("/workspaces/{workspace_id}/forms/{form_id}/copy-recipient")
    async def check_copy_recipient(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        payload: CopyRecipientQuery,
        api_key=Depends(get_api_key),
    ):
        """The actions executor asks, right before a "send me a copy" mail,
        whether the address may still receive it (a member of the workspace
        who is still enabled, the form's creator included, as of now). Only a yes or no goes back, never
        who the members are."""
        allowed = await self.copy_recipient_service.is_allowed(
            payload.address, workspace_id, form_id
        )
        return {"allowed": allowed}

    @post(
        "/workspaces/{workspace_id}/forms/{form_id}/actions/{action_id}"
        "/runs/{response_id}/context"
    )
    async def action_run_context(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        action_id: RecordId,
        response_id: str,
        request: Request,
        response: Response,
        body: Optional[RunContextRequest] = None,
        api_key=Depends(get_api_key),
    ):
        """The actions executor reads what one queued run needs, when it runs:
        the job carries ids only, so no answers or action secrets sit in the
        job queue's rows. Besides the job key it must present the run's own
        token (``run-token``, minted when the run was queued, expiring after a
        day) and the run's job must be in the actions queue, ``doing``, with these
        ids and this token: the job key alone reads nobody's answers, and a token
        read from the queue opens nothing once its run is over. 410 when the run
        is too old or no longer applies (the
        response was erased, the action was switched off or removed): the
        executor skips the job, it is not retried. Sealed secrets (what an
        executor older than 4.3 asks for) are refused with 426 while
        ``ACTION_SECRETS_SEALED_ALLOWED`` is off, and plain ones answer 503 when
        this backend has no key to open them with."""
        response.headers["Cache-Control"] = NO_STORE
        await self._authorise_run(
            request, workspace_id, form_id, action_id, response_id
        )
        plain = bool(body and body.secrets == "plain")
        if not plain and not sealed_secrets_allowed():
            refuse_sealed("run context")
        context = await self.action_service.action_run_context(
            workspace_id,
            form_id,
            action_id,
            response_id,
            plain_secrets=plain,
        )
        if context is None:
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="This action run no longer applies."
            )
        return context

    async def _authorise_run(
        self, request: Request, workspace_id, form_id, action_id, response_id
    ) -> None:
        """The run's own token (valid, not expired) and the run's job in the
        actions queue, being run, with these ids and this token: else 403 (the
        job key alone opens nothing) or 410 (the token's day is over)."""
        token = request.headers.get(HEADER, "")
        ids = (workspace_id, form_id, action_id, response_id)
        verdict = check_run_token(token, *ids)
        if verdict == INVALID:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You are not allowed to perform this action.",
            )
        if verdict == EXPIRED:
            # queued too long ago to be run now (an executor that was down)
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="This action run no longer applies."
            )
        # the token is only good for the run in flight: its job is in the actions
        # queue, being run, with these ids and this token
        running = await jobs_app.job_manager.list_jobs_async(
            queue=ACTIONS_QUEUE,
            task="run_action",
            status="doing",
            queueing_lock=run_lock(action_id, form_id, response_id),
        )
        if not any(job_matches(job, token, *ids) for job in running):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You are not allowed to perform this action.",
            )

    @patch(
        "/workspaces/{workspace_id}/forms/{form_id}/actions/{action_id}"
        "/runs/{response_id}/secrets"
    )
    async def patch_run_secret(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        action_id: RecordId,
        response_id: str,
        payload: RunSecretDto,
        request: Request,
        response: Response,
        api_key=Depends(get_api_key),
    ):
        """The executor hands a credential it refreshed (a Google access token)
        back, in plain, for this backend to seal with its own key. Scoped to the
        run like its context: the run's token and the run's job being ``doing``,
        so the job key alone writes no form's secret; the form must belong to the
        workspace and have the action switched on, and only a secret the form's
        action already holds can be replaced."""
        response.headers["Cache-Control"] = NO_STORE
        await self._authorise_run(
            request, workspace_id, form_id, action_id, response_id
        )
        if not await self.action_service.run_in_force(
            workspace_id, form_id, action_id, response_id
        ):
            raise HTTPException(
                status_code=HTTPStatus.GONE, content="This action run no longer applies."
            )
        await self.form_actions_service.update_run_secret(form_id, action_id, payload)
        return "Updated"

    @post("/delete/submissions/{submission_id}")
    async def delete_expired_submissions(
        self, submission_id: str, api_key=Depends(get_api_key)
    ):
        return await self.form_schedular.delete_response(submission_id=submission_id)
