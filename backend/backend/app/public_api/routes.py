"""The public API's endpoints. Thin: each authenticates the key for its
scope, then calls the same services as the MCP server and the builder."""

import json
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Dict, List, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.public_api.auth import ApiCaller, api_key
from backend.app.public_api.errors import error_payload
from backend.app.public_api.models import (
    CreatedForm,
    DryRunResult,
    Error,
    FormList,
    OpsRequest,
    OpsResult,
    PublishResult,
    ReplacePreview,
    ResponseDetail,
    ResponseList,
    ValidationResult,
)
from backend.app.services.api_responses import (
    MAX_PAGE_SIZE,
    list_response_summaries,
    response_detail,
)
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.service import (
    parse_json_document,
    read_document_bytes,
)
from backend.app.services.form_spec.writes import parse_if_match
from backend.app.services.idempotency import StoredResponse, request_hash

router = APIRouter()
# deepest page a list goes to (with 100 per page: a million items)
MAX_PAGE = 10_000

FORMS = "Forms"
OPERATIONS = "Form operations"
RESPONSES = "Responses"

SPEC_EXAMPLE = {
    "specVersion": "1",
    "title": "Event sign-up",
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {
                    "id": "name",
                    "type": "short_text",
                    "title": "Your name",
                    "validations": {"required": True, "maxLength": 80},
                },
                {
                    "id": "dinner",
                    "type": "yes_no",
                    "title": "Will you join the dinner?",
                    "choices": [{"value": "Yes"}, {"value": "No"}],
                },
            ],
        }
    ],
    "endings": [{"title": "Thanks", "message": "See you there."}],
    "trust": {"purpose": "To plan seats and catering."},
}
OPS_EXAMPLE = {
    "ops": [
        {
            "op": "add_page",
            "ref": "contact",
            "fields": [{"title": "Your email", "type": "email", "ref": "email"}],
        },
        {
            "op": "set_field_validation",
            "fieldId": "$ref:email",
            "validation": {"required": True},
        },
    ],
    "atomic": True,
}


def _json_body(schema_ref: str, example: Optional[Dict[str, Any]] = None) -> dict:
    """The request body's description: these endpoints read the body
    themselves (at most 1 MB), so it is declared here."""
    content: Dict[str, Any] = {"schema": {"$ref": f"#/components/schemas/{schema_ref}"}}
    if example is not None:
        content["example"] = example
    return {"requestBody": {"required": True, "content": {"application/json": content}}}


def _errors(*statuses: int) -> Dict[int, Dict[str, Any]]:
    descriptions = {
        401: "No valid API key.",
        403: "The key lacks the scope, or its creator lacks the permission.",
        404: "No such form (or response) in the key's workspace.",
        409: "A request with the same Idempotency-Key is still running.",
        412: "The form changed since the ETag in If-Match.",
        413: "The body is larger than 1 MB.",
        422: "The body is not valid; `errors` locates each problem.",
        428: "If-Match is required.",
        429: "Rate limited; see Retry-After.",
    }
    return {s: {"model": Error, "description": descriptions[s]} for s in statuses}


IDEMPOTENCY_KEY = Header(
    None,
    alias="Idempotency-Key",
    description="Retry safely: the same key and request within 24 hours "
    "returns the first response (Idempotent-Replayed: true) instead of "
    "running again; the same key with another request is refused (422).",
)
IF_MATCH_OPTIONAL = Header(
    None,
    alias="If-Match",
    description="The ETag of the form version these operations are for; "
    "when given, a stale one is refused with 412.",
)


def _c():
    from backend.app.container import container

    return container


def _with_etag(body: Any, etag: str, status: int = 200, **headers) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=body, headers={"ETag": etag, **headers}
    )


def _object_id(value: str) -> PydanticObjectId:
    try:
        return PydanticObjectId(value)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")


async def _require_form(caller: ApiCaller, form_id: str) -> None:
    association = (
        await _c()
        .workspace_form_repo()
        .find_workspace_form(caller.workspace_id, form_id)
    )
    if association is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")


def _summary(kind: str, response: JSONResponse) -> Dict[str, Any]:
    """What is kept to replay ``response``: never a whole form."""
    body = json.loads(bytes(response.body))
    if kind == "created":
        return {"kind": "created", "formId": body["formId"]}
    if kind == "ops":
        return {
            "kind": "ops",
            "applied": body["applied"],
            "atomic": body["atomic"],
            "results": body["results"],
        }
    return {"kind": "body", "body": body}


async def _replay(
    request: Request, caller: ApiCaller, stored: StoredResponse
) -> Response:
    """The response a retry gets: rebuilt from the summary, with the form
    as it is now and its current ETag."""
    summary = json.loads(stored.body)
    headers = {"Idempotent-Replayed": "true"}
    kind = summary.get("kind")
    if kind in ("created", "ops"):
        form_id = summary.get("formId") or request.path_params.get("form_id")
        document, etag = (
            await _c().form_spec_writer().read(caller.workspace_id, form_id)
        )
        headers["ETag"] = etag
        if kind == "created":
            headers["Location"] = _location(request, form_id)
            content = {"formId": form_id, "form": document}
        else:
            content = {
                key: summary[key]
                for key in ("applied", "atomic", "results", "truncated")
                if key in summary
            }
            content["form"] = document
        return JSONResponse(content, stored.status_code, headers)
    if stored.etag:
        headers["ETag"] = stored.etag
    return JSONResponse(summary.get("body"), stored.status_code, headers)


def _location(request: Request, form_id: str) -> str:
    return f"{request.scope.get('root_path', '')}/forms/{form_id}"


async def _idempotent(
    request: Request,
    caller: ApiCaller,
    idempotency_key: Optional[str],
    body: bytes,
    kind: str,
    run: Callable[[], Awaitable[JSONResponse]],
) -> Response:
    """Run ``run`` once per Idempotency-Key (services/idempotency.py);
    ``kind`` says what to keep for a replay (created, ops or body)."""
    if idempotency_key is None:
        return await run()
    service = _c().idempotency_service()
    fingerprint = request_hash(request.method, request.url.path, body)
    stored = await service.begin(caller.key_id, idempotency_key, fingerprint)
    if stored is not None:
        return await _replay(request, caller, stored)
    try:
        response = await run()
    except HTTPException as error:
        payload = error_payload(error.status_code, error.content)
        await service.finish(
            caller.key_id,
            idempotency_key,
            error.status_code,
            {"kind": "body", "body": payload},
        )
        raise
    except BaseException:
        await service.abandon(caller.key_id, idempotency_key)
        raise
    await service.finish(
        caller.key_id,
        idempotency_key,
        response.status_code,
        _summary(kind, response),
        response.headers.get("etag"),
    )
    return response


# -- forms ---------------------------------------------------------------------


@router.get(
    "/forms",
    tags=[FORMS],
    operation_id="listForms",
    summary="List the workspace's forms",
    response_model=FormList,
    responses=_errors(401, 403, 429),
)
async def list_forms(
    page: int = Query(1, ge=1, le=MAX_PAGE),
    size: int = Query(50, ge=1, le=100),
    caller: ApiCaller = Depends(api_key("forms:read", "api:list_forms")),
):
    associations = (
        await _c().workspace_form_repo().list_in_workspace(caller.workspace_id)
    )
    total = len(associations)
    window = associations[(page - 1) * size : page * size]
    forms = {
        f.form_id: f
        for f in await _c()
        .form_repo()
        .get_forms_by_form_ids([a.form_id for a in window])
    }
    items = []
    for association in window:
        form = forms.get(association.form_id)
        if form is None:
            continue
        updated_at = getattr(form, "updated_at", None)
        items.append(
            {
                "formId": form.form_id,
                "title": form.title,
                "slug": (
                    association.settings.custom_url if association.settings else None
                ),
                "published": form.published_at is not None,
                "updatedAt": updated_at.isoformat() if updated_at else None,
            }
        )
    return JSONResponse({"items": items, "page": page, "size": size, "total": total})


@router.post(
    "/forms",
    tags=[FORMS],
    operation_id="createForm",
    summary="Create a draft form from a spec document",
    description="All or nothing: the whole document is checked first; any "
    "error is a 422 listing every problem, and nothing is created. A logo URL "
    "in the document is ignored (logos are uploaded). Answers 201 with the "
    "stored document, its ETag and Location.",
    status_code=201,
    response_model=CreatedForm,
    responses=_errors(401, 403, 409, 413, 422, 429),
    openapi_extra=_json_body("FormSpec", SPEC_EXAMPLE),
)
async def create_form(
    request: Request,
    idempotency_key: Optional[str] = IDEMPOTENCY_KEY,
    caller: ApiCaller = Depends(api_key("forms:write", "api:create_form")),
):
    body = await read_document_bytes(request)

    async def run() -> JSONResponse:
        raw = parse_json_document(body)
        form_id, document, etag = (
            await _c().form_spec_writer().create(caller.workspace_id, raw, caller.user)
        )
        return _with_etag(
            {"formId": form_id, "form": document},
            etag,
            status=201,
            Location=_location(request, form_id),
        )

    return await _idempotent(request, caller, idempotency_key, body, "created", run)


@router.post(
    "/forms/validate",
    tags=[FORMS],
    operation_id="validateForm",
    summary="Check a spec document without storing it",
    description="Always 200 for a JSON body: `valid`, and every error with "
    "its JSON pointer `path`.",
    response_model=ValidationResult,
    responses=_errors(401, 403, 413, 422, 429),
    openapi_extra=_json_body("FormSpec", SPEC_EXAMPLE),
)
async def validate_form(
    request: Request,
    caller: ApiCaller = Depends(api_key("forms:read", "api:validate_form")),
):
    raw = parse_json_document(await read_document_bytes(request))
    # CPU-bound on a large document: off the event loop
    return JSONResponse(await run_in_threadpool(check_spec_document, raw))


@router.get(
    "/forms/{form_id}",
    tags=[FORMS],
    operation_id="getForm",
    summary="Get a form as a spec document",
    description="The `ETag` header names this version; send it as `If-Match` "
    "to replace the form or to apply operations to exactly this version.",
    response_model=None,
    responses={
        200: {
            "description": "The form's spec document.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/FormSpec"}
                }
            },
            "headers": {"ETag": {"schema": {"type": "string"}}},
        },
        **_errors(401, 403, 404, 422, 429),
    },
)
async def get_form(
    form_id: str,
    caller: ApiCaller = Depends(api_key("forms:read", "api:get_form")),
):
    document, etag = await _c().form_spec_writer().read(caller.workspace_id, form_id)
    return _with_etag(document, etag)


@router.put(
    "/forms/{form_id}",
    tags=[FORMS],
    operation_id="replaceForm",
    summary="Replace a form from a spec document",
    description="Needs `If-Match` with the ETag from GET (428 without it, 412 "
    "when the form changed since, also when another save lands at the same "
    "moment). The document replaces the form's content; in `trust` and "
    '`logo` a key you leave out keeps its stored value ("" clears a text). '
    "Answers the stored document and its new ETag.",
    response_model=None,
    responses={
        200: {
            "description": "The stored spec document.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/FormSpec"}
                }
            },
            "headers": {"ETag": {"schema": {"type": "string"}}},
        },
        **_errors(401, 403, 404, 412, 413, 422, 428, 429),
    },
    openapi_extra=_json_body("FormSpec", SPEC_EXAMPLE),
)
async def replace_form(
    form_id: str,
    request: Request,
    if_match: Optional[str] = Header(
        None, alias="If-Match", description="The form's ETag, from GET."
    ),
    caller: ApiCaller = Depends(api_key("forms:write", "api:replace_form")),
):
    tags = parse_if_match(if_match)
    _object_id(form_id)
    await _require_form(caller, form_id)
    raw = parse_json_document(await read_document_bytes(request))
    document, etag = (
        await _c()
        .form_spec_writer()
        .replace(caller.workspace_id, form_id, raw, tags, caller.user)
    )
    return _with_etag(document, etag)


@router.post(
    "/forms/{form_id}/replace/dry-run",
    tags=[FORMS],
    operation_id="previewReplaceForm",
    summary="Preview a replace",
    description="What PUT would store for this document, and the diff from "
    "the stored form. Stores nothing.",
    response_model=ReplacePreview,
    responses=_errors(401, 403, 404, 413, 422, 429),
    openapi_extra=_json_body("FormSpec", SPEC_EXAMPLE),
)
async def preview_replace_form(
    form_id: str,
    request: Request,
    caller: ApiCaller = Depends(api_key("forms:write", "api:preview_replace")),
):
    await _require_form(caller, form_id)
    raw = parse_json_document(await read_document_bytes(request))
    return JSONResponse(
        await _c().form_spec_writer().preview_replace(caller.workspace_id, form_id, raw)
    )


@router.post(
    "/forms/{form_id}/publish",
    tags=[FORMS],
    operation_id="publishForm",
    summary="Publish a form",
    description="The product's publish, with its checks (422 "
    "`form_not_publishable` lists what blocks it).",
    response_model=PublishResult,
    responses=_errors(401, 403, 404, 409, 422, 429),
)
async def publish_form(
    form_id: str,
    request: Request,
    idempotency_key: Optional[str] = IDEMPOTENCY_KEY,
    caller: ApiCaller = Depends(api_key("forms:write", "api:publish_form")),
):
    _object_id(form_id)
    await _require_form(caller, form_id)
    body = await read_document_bytes(request)

    async def run() -> JSONResponse:
        result = (
            await _c()
            .form_spec_writer()
            .publish(caller.workspace_id, form_id, caller.user)
        )
        return JSONResponse(result)

    return await _idempotent(request, caller, idempotency_key, body, "body", run)


# -- operations ----------------------------------------------------------------


def _ops_request(raw: Any) -> OpsRequest:
    try:
        return OpsRequest.model_validate(raw)
    except ValidationError as error:
        from common.form_spec import validation_errors

        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": "invalid_request",
                "message": "The request is not valid.",
                "errors": validation_errors(error),
            },
        )


@router.post(
    "/forms/{form_id}/ops",
    tags=[OPERATIONS],
    operation_id="applyFormOps",
    summary="Apply edit operations",
    description="The operations engine the builder's AI chat and MCP use. "
    "Atomic by default: any failed operation is a 422 `ops_failed` and "
    "nothing is stored. With `atomic: false`, what applies is stored and "
    "each result says how it went. `If-Match` is optional; when given, it is "
    "enforced (412).",
    response_model=OpsResult,
    responses=_errors(401, 403, 404, 409, 412, 413, 422, 429),
    openapi_extra=_json_body("OpsRequest", OPS_EXAMPLE),
)
async def apply_ops(
    form_id: str,
    request: Request,
    if_match: Optional[str] = IF_MATCH_OPTIONAL,
    idempotency_key: Optional[str] = IDEMPOTENCY_KEY,
    caller: ApiCaller = Depends(api_key("forms:write", "api:apply_ops")),
):
    await _require_form(caller, form_id)
    body = await read_document_bytes(request)

    async def run() -> JSONResponse:
        payload = _ops_request(parse_json_document(body))
        result, etag = (
            await _c()
            .form_spec_writer()
            .apply_ops(
                caller.workspace_id,
                form_id,
                payload.ops,
                payload.atomic,
                parse_if_match(if_match),
            )
        )
        return _with_etag(result, etag)

    return await _idempotent(request, caller, idempotency_key, body, "ops", run)


@router.post(
    "/forms/{form_id}/ops/dry-run",
    tags=[OPERATIONS],
    operation_id="dryRunFormOps",
    summary="Preview edit operations",
    description="Applies the operations to a copy of the form: the resulting "
    "document, a diff and per-operation results. Stores nothing.",
    response_model=DryRunResult,
    responses=_errors(401, 403, 404, 413, 422, 429),
    openapi_extra=_json_body("OpsRequest", OPS_EXAMPLE),
)
async def dry_run_ops(
    form_id: str,
    request: Request,
    caller: ApiCaller = Depends(api_key("forms:write", "api:dry_run_ops")),
):
    await _require_form(caller, form_id)
    payload = _ops_request(parse_json_document(await read_document_bytes(request)))
    service = _c().form_spec_service()
    form, settings = await service.load(caller.workspace_id, form_id)
    preview = await service.preview_async(form, settings, payload.ops, payload.atomic)
    return JSONResponse(preview.model_dump(mode="json", by_alias=True))


# -- responses -----------------------------------------------------------------


@router.get(
    "/forms/{form_id}/responses",
    tags=[RESPONSES],
    operation_id="listResponses",
    summary="List a form's responses",
    description="Most recent first. Answers are in GET .../responses/{id}. "
    "Needs `responses:read`, and the key's creator needs to read and export "
    "responses. Respondents' identities are never returned.",
    response_model=ResponseList,
    responses=_errors(401, 403, 404, 429),
)
async def list_responses(
    form_id: str,
    page: int = Query(1, ge=1, le=MAX_PAGE),
    size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    caller: ApiCaller = Depends(api_key("responses:read", "api:list_responses")),
):
    await _require_form(caller, form_id)
    items, total = await list_response_summaries(
        caller.workspace_id, form_id, size, (page - 1) * size
    )
    return JSONResponse({"items": items, "page": page, "size": size, "total": total})


@router.get(
    "/forms/{form_id}/responses/{response_id}",
    tags=[RESPONSES],
    operation_id="getResponse",
    summary="Get one response with its answers",
    response_model=ResponseDetail,
    responses=_errors(401, 403, 404, 429),
)
async def get_response(
    form_id: str,
    response_id: str,
    caller: ApiCaller = Depends(api_key("responses:read", "api:get_response")),
):
    await _require_form(caller, form_id)
    detail = await response_detail(caller.workspace_id, response_id)
    if detail is None or detail["formId"] != form_id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, content="Response not found"
        )
    return JSONResponse(detail)


__all__: List[str] = ["router"]
