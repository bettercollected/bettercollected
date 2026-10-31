"""Save and continue later: a respondent's draft of a form
(``services/form_drafts``). Respondent routes, no workspace permission: a
signed-in respondent is known by the session, an anonymous one by the magic
link's token or the edit key in the body (never the query string or a header,
which logs and proxies keep). Every response carries decrypted answers or a
secret, so none is cacheable (``middlewares/request_privacy.py``)."""

import json
from http import HTTPStatus
from typing import Optional, Type, TypeVar

from classy_fastapi import Routable, post, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends
from pydantic import BaseModel, ValidationError
from starlette.requests import Request

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.form_drafts import limits
from backend.app.services.form_drafts.service import (
    DiscardBody,
    LinkRequestBody,
    OpenDraftBody,
    SaveDraftBody,
)
from backend.app.services.user_service import get_user_if_logged_in
from backend.app.utils.client_ip import request_client_ip

M = TypeVar("M", bound=BaseModel)
# a draft body: the payload's cap plus the keys, the address and the position
MAX_BODY_BYTES = limits.MAX_PAYLOAD_BYTES + 64 * 1024


async def read_body(request: Request, model: Type[M]) -> M:
    """The request's JSON as ``model``: read with a hard cap (413 past it,
    whatever the headers say), and a body json cannot parse or nests too deeply
    is a clean 422, never a 500."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise _too_large()
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > MAX_BODY_BYTES:
            raise _too_large()
    try:
        parsed = json.loads(bytes(received) or b"{}")
        return model.model_validate(parsed)
    except (ValueError, RecursionError, ValidationError) as error:
        message = "The draft is not valid."
        if isinstance(error, ValidationError):
            message = (
                "; ".join(
                    str(problem.get("msg", "")).removeprefix("Value error, ")
                    for problem in error.errors()
                )
                or message
            )
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"code": "invalid_draft", "message": message},
        )


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={
            "code": "draft_too_large",
            "message": "This draft is too large to save.",
        },
    )


def _json(dto: BaseModel) -> dict:
    return dto.model_dump(mode="json", by_alias=True, exclude_none=True)


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/drafts",
    tags=["Form Drafts"],
    responses={
        404: {"description": "No such form or draft (or the form keeps no drafts)."},
        409: {"description": "The form takes no responses now."},
        429: {"description": "Too many requests."},
    },
)
class FormDraftsRouter(Routable):
    @put("")
    async def save_draft(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """Save the signed-in respondent's draft, or update the anonymous one
        the browser's edit key names."""
        body = await read_body(request, SaveDraftBody)
        saved = await container.form_draft_service().save(
            workspace_id, form_id, user, body, request_client_ip(request)
        )
        return _json(saved)

    @post("/link")
    async def request_link(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """Anonymous respondents: save the draft and mail them a link to it."""
        body = await read_body(request, LinkRequestBody)
        sent = await container.form_draft_service().request_link(
            workspace_id, form_id, user, body, request_client_ip(request)
        )
        return _json(sent)

    @post("/open")
    async def open_draft(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """Open the draft a magic link names (the token is in the body)."""
        body = await read_body(request, OpenDraftBody)
        opened = await container.form_draft_service().open_with_token(
            workspace_id, form_id, user, body, request_client_ip(request)
        )
        return _json(opened)

    @post("/mine")
    async def my_draft(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """The signed-in respondent's own draft of the form."""
        if user is None:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content={"code": "sign_in_required", "message": "Sign in first."},
            )
        found = await container.form_draft_service().mine(
            workspace_id, form_id, user, request_client_ip(request)
        )
        return _json(found)

    @post("/discard")
    async def discard_draft(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: Optional[User] = Depends(get_user_if_logged_in),
    ):
        """Delete the respondent's own draft."""
        body = await read_body(request, DiscardBody)
        await container.form_draft_service().discard(
            workspace_id, form_id, user, body, request_client_ip(request)
        )
        return {"deleted": True}
