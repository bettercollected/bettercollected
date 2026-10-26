"""The builder's op-batch save: ``POST /workspaces/{ws}/forms/{id}/ops``.

The editor sends each batch of edits as operations instead of the whole
form. Session auth with ``form.edit``; behind ``API_EDITOR_OPS_SAVE_ENABLED``
(404 while off).

- ``If-Match`` is required (428 without it, 412 when stale), with the same
  ETag as the public API (``writes.form_etag``: the draft's ``updated_at`` and
  a hash of its spec document). The editor's form GET hands it out as the
  ``ETag`` header and the ``etag`` field when asked (``?withEtag=1``).
- ``Idempotency-Key`` is required (400 without it) and kept in the public
  API's store (``services/idempotency.py``), scoped to the user and the form.
  ``If-Match`` is part of the request a key names. A 412 is not kept: the key
  is released, so the batch can be resent with it once rebased.
- At most ``API_EDITOR_OPS_PER_WINDOW`` batches per person in each window
  (429 with Retry-After).
- Atomic only: any failed op is a 422 ``ops_failed`` and nothing is stored.
  The write is conditional (``persist_ops_to_form(expected_updated_at=...)``),
  so a save landing between the check and the write is a 412 too.
- The answer is the form in the editor GET's shape, its new ETag and the
  per-op results.

Logs carry ids and counts, never values.
"""

import json
from http import HTTPStatus
from typing import Any, Dict, List, Literal, Optional, Tuple

from common.ids import RecordId
from common.form_spec import (
    SpecConversionError,
    form_to_spec_dict,
    validation_errors,
)
from common.models.standard_form import StandardForm
from common.models.user import User
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from backend.app.constants.consents import default_consents
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.enum.permission import Permission
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import (
    EDITOR_ONLY_OPS,
    OP_NAMES,
    parse_ops,
    too_many_ops,
)
from backend.app.services.form_spec.service import (
    ops_errors,
    parse_json_document,
    read_document_bytes,
)
from backend.app.services.form_spec.writes import (
    OPS_FAILED_CODE,
    _EPOCH,
    _is_form_changed,
    form_etag,
    parse_if_match,
    precondition_failed,
    precondition_required,
)
from backend.app.services.idempotency import (
    IdempotencyService,
    StoredResponse,
    request_hash,
)
from backend.config import settings as app_settings
from common.settings.loader import live

IDEMPOTENCY_KEY_REQUIRED_CODE = "idempotency_key_required"
RATE_LIMIT_SCOPE = "editor_ops"
RATE_LIMITED_CODE = "rate_limited"
# answers about the form's version, not the request: never kept for the key,
# so the same batch resent after a refetch runs again
_NOT_KEPT = {HTTPStatus.PRECONDITION_FAILED, HTTPStatus.PRECONDITION_REQUIRED}

# Editor-only ops (lossless, id-addressed edits only the builder makes) are
# refused on the AI, MCP and public API paths; this endpoint is the one place
# they are allowed, next to every op those paths accept.
EDITOR_OP_NAMES = frozenset(OP_NAMES) | EDITOR_ONLY_OPS


class EditorOpsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ops: List[Dict[str, Any]]
    # atomic only; accepted so a client may say so explicitly
    atomic: Literal[True] = True


def _unprocessable(code: str, message: str, errors: List[Dict[str, str]]):
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": code, "message": message, "errors": errors},
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")


def editor_etag(updated_at, form: StandardForm, settings: Any) -> str:
    """The form's ETag: the public API's (``form_etag`` over its spec
    document). A form the spec cannot express (built before pages) gets the
    same scheme over its stored content, so its GET still has a version."""
    try:
        document = form_to_spec_dict(form, settings)
    except SpecConversionError:
        document = {
            "form": form.model_dump(mode="json"),
            "settings": settings.model_dump(mode="json") if settings else None,
        }
    return form_etag(updated_at, document)


def idempotency_scope(user: User, form_id: str) -> str:
    """Whose keys these are: one user's saves of one form (an API key's id
    never has this shape, so the two never meet)."""
    return f"editor:{user.id}:{form_id}"


def _parse_request(body: bytes) -> EditorOpsRequest:
    raw = parse_json_document(body)
    try:
        request = EditorOpsRequest.model_validate(raw)
    except ValidationError as error:
        raise _unprocessable(
            "invalid_request", "The request is not valid.", validation_errors(error)
        )
    refusal = too_many_ops(len(request.ops))
    if refusal:
        raise _unprocessable(
            "too_many_ops", refusal, [{"path": "/ops", "message": refusal}]
        )
    unknown = [
        {"path": f"/ops/{index}/op", "message": "Unknown operation."}
        for index, op in enumerate(request.ops)
        if not isinstance(op, dict) or op.get("op") not in EDITOR_OP_NAMES
    ]
    if unknown:
        raise _unprocessable(
            "invalid_ops", "The operations are not valid.", unknown
        )
    return request


class EditorOpsService:
    def __init__(
        self,
        authorization_service,
        workspace_form_repo,
        form_repo,
        idempotency_service: IdempotencyService,
        rate_limiter=None,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo
        self._idempotency = idempotency_service
        self._limiter = rate_limiter

    # -- reading -----------------------------------------------------------

    async def _load(self, workspace_id: RecordId, form_id: str):
        """(stored draft, StandardForm, association settings) of a form of
        this workspace; None when it is not one."""
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        )
        if association is None:
            return None
        document = await self._form_repo.get_form_document_by_id(str(form_id))
        if document is None:
            return None
        return document, StandardForm(**document.model_dump()), association.settings

    async def _etag_of(self, loaded) -> str:
        document, form, settings = loaded
        # CPU-bound on a large form: off the event loop
        return await run_in_threadpool(
            editor_etag, document.updated_at, form, settings
        )

    async def etag_for_editor(
        self, user: Optional[User], workspace_id: RecordId, form_id: str
    ) -> Optional[str]:
        """The draft's ETag for someone who may edit it while op saves are
        on, else None (the GET then simply has none)."""
        if not live().api.EDITOR_OPS_SAVE_ENABLED:
            return None
        if user is None or not await self._authorization.has_permission(
            user, Permission.FORM_EDIT, workspace_id
        ):
            return None
        loaded = await self._load(workspace_id, form_id)
        return await self._etag_of(loaded) if loaded else None

    async def editor_form(
        self, workspace_id: RecordId, form_id: str
    ) -> Tuple[Dict[str, Any], str]:
        """(the draft as the editor's GET serves it, its ETag).

        The ETag is read before the form, so it is never newer than the form
        it comes with: a save landing in between can only make the next
        If-Match stale (412), never let a stale edit through. The importer's
        details are left out: no op changes them and they cost a call to the
        auth service."""
        loaded = await self._load(workspace_id, form_id)
        if loaded is None:
            raise _not_found()
        etag = await self._etag_of(loaded)
        rows = await self._form_repo.get_forms_in_workspace(
            workspace_id=workspace_id, form_id_list=[str(form_id)], is_admin=True
        )
        if not rows:
            raise _not_found()
        form = FormDtoCamelModel(**rows[0])
        if form.consent is None:
            form.consent = default_consents
        body = form.model_dump(mode="json", by_alias=True, exclude={"importer_details"})
        body["etag"] = etag
        return body, etag

    # -- saving ------------------------------------------------------------

    async def save(
        self,
        workspace_id: RecordId,
        form_id: str,
        request,
        user: User,
        if_match: Optional[str],
        idempotency_key: Optional[str],
    ) -> JSONResponse:
        if not live().api.EDITOR_OPS_SAVE_ENABLED:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not Found")
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        if await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        ) is None:
            raise _not_found()
        await self._rate_limit(user)
        tags = parse_if_match(if_match)
        if tags is None:
            raise precondition_required()
        if idempotency_key is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content={
                    "code": IDEMPOTENCY_KEY_REQUIRED_CODE,
                    "message": "Send an Idempotency-Key with each batch, the "
                    "same one again only when retrying it.",
                },
            )
        IdempotencyService.check_key(idempotency_key)
        body = await read_document_bytes(request)

        scope = idempotency_scope(user, form_id)
        fingerprint = request_hash(
            request.method, request.url.path, body, ",".join(tags)
        )
        stored = await self._idempotency.begin(scope, idempotency_key, fingerprint)
        if stored is not None:
            return await self._replay(workspace_id, form_id, stored)
        try:
            results = await self._apply(workspace_id, form_id, body, tags)
        except HTTPException as error:
            if error.status_code in _NOT_KEPT:
                await self._idempotency.abandon(scope, idempotency_key)
            else:
                await self._idempotency.finish(
                    scope,
                    idempotency_key,
                    error.status_code,
                    {"kind": "body", "body": error.content},
                )
            logger.info(
                "editor ops save: form {} refused with {}", form_id, error.status_code
            )
            raise
        except BaseException:
            await self._idempotency.abandon(scope, idempotency_key)
            raise
        # stored before the answer is built: a retry replays these results
        # with the form as it is then
        await self._idempotency.finish(
            scope, idempotency_key, 200, {"kind": "ops", "results": results}
        )
        form, etag = await self.editor_form(workspace_id, form_id)
        logger.info("editor ops save: form {} applied {} ops", form_id, len(results))
        return JSONResponse(
            {"applied": True, "results": results, "etag": etag, "form": form},
            headers={"ETag": etag},
        )

    async def _rate_limit(self, user: User) -> None:
        limit = live().api.EDITOR_OPS_PER_WINDOW
        if self._limiter is None or limit <= 0:
            return
        verdict = await self._limiter.hit(
            RATE_LIMIT_SCOPE,
            str(user.id),
            limit,
            live().api.EDITOR_OPS_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                content={
                    "code": RATE_LIMITED_CODE,
                    "message": "Too many saves; try again shortly.",
                },
                headers={"Retry-After": str(verdict.retry_after)},
            )

    async def _apply(
        self,
        workspace_id: RecordId,
        form_id: str,
        body: bytes,
        tags: List[str],
    ) -> List[Dict[str, Any]]:
        payload = _parse_request(body)
        try:
            ops = parse_ops(payload.ops, allow_editor_ops=True)
        except ValidationError as error:
            raise _unprocessable(
                "invalid_ops", "The operations are not valid.", ops_errors(error)
            ) from error
        loaded = await self._load(workspace_id, form_id)
        if loaded is None:
            raise _not_found()
        document, form, _ = loaded
        current = await self._etag_of(loaded)
        if "*" not in tags and current not in tags:
            raise precondition_failed()
        try:
            _, results, _ = await persist_ops_to_form(
                document,
                form,
                ops,
                workspace_id=workspace_id,
                atomic=True,
                expected_updated_at=document.updated_at or _EPOCH,
            )
        except HTTPException as error:
            if _is_form_changed(error):
                raise precondition_failed() from error
            raise
        if not all(r.ok for r in results):
            raise _unprocessable(
                OPS_FAILED_CODE,
                "An operation failed, so none was applied.",
                [
                    {"path": f"/ops/{r.index}", "message": r.message}
                    for r in results
                    if not r.ok
                ],
            )
        return [r.model_dump(mode="json", by_alias=True) for r in results]

    async def _replay(
        self, workspace_id: RecordId, form_id: str, stored: StoredResponse
    ) -> JSONResponse:
        """A retry's answer: the stored results with the form as it is now
        and its current ETag, or the stored error as it was."""
        summary = json.loads(stored.body)
        headers = {"Idempotent-Replayed": "true"}
        if summary.get("kind") == "ops":
            form, etag = await self.editor_form(workspace_id, form_id)
            headers["ETag"] = etag
            content = {
                "applied": True,
                "results": summary.get("results") or [],
                "etag": etag,
                "form": form,
            }
            if summary.get("truncated"):
                content["truncated"] = True
            return JSONResponse(content, stored.status_code, headers)
        return JSONResponse(summary.get("body"), stored.status_code, headers)
