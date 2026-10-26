"""Validate a form spec document, read a form as one, and dry-run edit
operations against a form. Nothing here writes."""

import json
from http import HTTPStatus
from typing import Any, Dict, List

from common.ids import RecordId
from common.form_spec import (
    SpecConversionError,
    form_to_spec_dict,
    validation_errors,
)
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel
from starlette.concurrency import run_in_threadpool

from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.services.ai.ops import (
    OP_NAMES,
    OpResult,
    applied,
    apply_settings_ops,
    apply_form_ops,
    parse_ops,
    too_many_ops,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.diff import spec_diff

# Largest spec document the validate endpoint (and MCP validate_form) reads.
MAX_DOCUMENT_BYTES = 1024 * 1024
DOCUMENT_TOO_LARGE = (
    "The document is larger than 1 MB; a form spec document is far smaller."
)


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class DryRunRequest(_CamelModel):
    ops: List[Dict[str, Any]]
    atomic: bool = False


class DryRunResponse(_CamelModel):
    # Whether every op applied, and whether the batch would change the form
    # (atomic: only when every op applied).
    ok: bool
    applied: bool
    atomic: bool
    form: Dict[str, Any]
    diff: Dict[str, Any]
    results: List[OpResult]


def _unprocessable(message: str, errors: List[Dict[str, str]]) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"message": message, "errors": errors},
    )


def document_too_large() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={"message": DOCUMENT_TOO_LARGE},
    )


async def read_document_bytes(request) -> bytes:
    """The raw body of ``request``, read up to MAX_DOCUMENT_BYTES: 413
    beyond that (without reading the rest)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_DOCUMENT_BYTES:
        raise document_too_large()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_DOCUMENT_BYTES:
            raise document_too_large()
    return bytes(body)


def parse_json_document(body: bytes) -> Any:
    """``body`` as JSON, 422 when it is not."""
    try:
        return json.loads(body)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"message": "The body is not valid JSON."},
        )


async def read_json_document(request) -> Any:
    """The JSON body of ``request``, read up to MAX_DOCUMENT_BYTES: 413
    beyond that (without reading the rest), 422 when it is not JSON."""
    return parse_json_document(await read_document_bytes(request))


def ops_errors(error: ValidationError) -> List[Dict[str, str]]:
    """Parse errors of an ops payload as ``/ops/<index>/<key>`` (without
    the op name pydantic puts in the location of a tagged union)."""
    errors = []
    for e in validation_errors(error):
        parts = e["path"].split("/")
        # ["", "ops", "<index>", "<op name>", ...]
        if len(parts) > 3 and parts[1] == "ops" and parts[3] in OP_NAMES:
            del parts[3]
        errors.append({"path": "/".join(parts), "message": e["message"]})
    return errors


def settings_after_ops(settings: Any, ops, results: List[OpResult]) -> Any:
    """A copy of the association ``settings`` with the applied
    update_form_settings ops on it, as persist_ops_to_form writes them
    ('' clears a text value)."""
    if settings is None:
        return None
    settings = settings.model_copy(deep=True)
    apply_settings_ops(settings, ops, results)
    return settings


class FormSpecService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        form_repo: PostgresFormRepository,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo

    async def validate_request(
        self, workspace_id: RecordId, request: Any, user: User
    ) -> Dict[str, Any]:
        """Authorise, then read the body (at most MAX_DOCUMENT_BYTES) and
        check it: a non-member never gets the body read."""
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await read_json_document(request)
        # CPU-bound (up to 1 MB of JSON): off the event loop
        return await run_in_threadpool(check_spec_document, document)

    async def load(self, workspace_id: RecordId, form_id: str):
        """(StandardForm, association settings) of a form of this workspace,
        404 otherwise. Callers authorise first."""
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        )
        document = (
            await self._form_repo.get_form_document_by_id(str(form_id))
            if association
            else None
        )
        if document is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        return StandardForm(**document.model_dump()), association.settings

    @staticmethod
    def spec_of(form: StandardForm, settings: Any) -> Dict[str, Any]:
        try:
            return form_to_spec_dict(form, settings)
        except SpecConversionError as error:
            raise _unprocessable(str(error), error.errors)

    async def dry_run(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: DryRunRequest,
        user: User,
    ) -> DryRunResponse:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        form, settings = await self.load(workspace_id, form_id)
        return await self.preview_async(form, settings, request.ops, request.atomic)

    async def preview_async(
        self,
        form: StandardForm,
        settings: Any,
        raw_ops: List[Dict[str, Any]],
        atomic: bool,
    ) -> DryRunResponse:
        """``preview`` off the event loop: applying a batch, converting and
        diffing a large form is CPU-bound."""
        return await run_in_threadpool(self.preview, form, settings, raw_ops, atomic)

    def preview(
        self,
        form: StandardForm,
        settings: Any,
        raw_ops: List[Dict[str, Any]],
        atomic: bool,
    ) -> DryRunResponse:
        """What ``raw_ops`` would make of ``form``: the resulting spec, the
        diff and per-op results. Stores nothing."""
        refusal = too_many_ops(len(raw_ops))
        if refusal:
            raise _unprocessable(refusal, [{"path": "/ops", "message": refusal}])
        before = self.spec_of(form, settings)
        try:
            ops = parse_ops(raw_ops)
        except ValidationError as error:
            raise _unprocessable("The operations are not valid.", ops_errors(error))
        new_form, results = apply_form_ops(form, ops, atomic=atomic)
        did_apply = applied(results, atomic)
        after = (
            self.spec_of(new_form, settings_after_ops(settings, ops, results))
            if did_apply
            else before
        )
        return DryRunResponse(
            ok=all(r.ok for r in results),
            applied=did_apply,
            atomic=atomic,
            form=after,
            diff=spec_diff(before, after),
            results=results,
        )
