"""The public REST API: forms as code, for programs.

A FastAPI application of its own, mounted at ``/api/v1/public/v1`` (the
backend's prefix, then the public contract's own version). Its own
application so that its OpenAPI document holds only the public contract
(docs/api/public-v1.openapi.json), its errors all have one shape, and
nothing of the cookie-authenticated API (sessions, CSRF) applies to it.
"""

import json
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from loguru import logger

from backend.app.public_api.auth import AUDIT_STATE
from backend.app.public_api.errors import error_payload, install_error_handlers
from backend.app.public_api.models import OpsRequest
from backend.app.public_api.routes import router
from backend.app.services.api_access import audit_key_call

PUBLIC_API_PATH = "/public/v1"
PUBLIC_API_VERSION = "1.0.0"
DESCRIPTION = """\
Create, read, change and publish forms as **form spec v1** documents, and read
their responses. Authenticate with a workspace API key:
`Authorization: Bearer bc_...`. A key works in its own workspace only, with
its scopes (`forms:read`, `forms:write`, `responses:read`), and never does
more than the person who created it may do at the time of the call.

- Errors: `{"code", "message", "errors"?: [{"path", "message"}]}`; `path` is
  a JSON pointer into the request body.
- Versions: `GET /forms/{formId}` answers an `ETag`; `PUT` needs it as
  `If-Match` (428 without, 412 when stale), operations accept it.
- Retries: `Idempotency-Key` on `POST /forms`, `/ops` and `/publish`.
- Rate limits per API key and per workspace: 429 with `Retry-After`.
"""


class AuditAndErrors:
    """Outermost wrapper: audit every authenticated call (operation, status
    and path ids, never a body), and answer an unexpected failure with the
    API's error shape (logging its type only)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        state = scope.setdefault("state", {})
        status = {"code": 500, "started": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                status["started"] = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as error:  # noqa: BLE001
            logger.error(f"Public API request failed: {type(error).__name__}")
            if not status["started"]:
                body = json.dumps(
                    error_payload(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "code": "internal_error",
                            "message": "Something went wrong on our side.",
                        },
                    )
                ).encode()
                await send_wrapper(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
        finally:
            audit = state.get(AUDIT_STATE) if isinstance(state, dict) else None
            if audit is not None:
                key, operation = audit
                ids = " ".join(
                    f"{k}={v}" for k, v in (scope.get("path_params") or {}).items()
                )
                await audit_key_call(
                    key,
                    operation,
                    status["code"] < 400,
                    f"{scope.get('method')} {status['code']} {ids}".strip(),
                )


def build_public_api() -> FastAPI:
    app = FastAPI(
        title="BetterCollected public API",
        version=PUBLIC_API_VERSION,
        description=DESCRIPTION,
        openapi_url="/openapi.json",
        # No interactive docs: they would load their scripts from a CDN. The
        # document is served here and committed in docs/api.
        docs_url=None,
        redoc_url=None,
        servers=[{"url": "/api/v1" + PUBLIC_API_PATH}],
        separate_input_output_schemas=False,
        openapi_tags=[
            {"name": "Forms", "description": "Forms as spec documents."},
            {
                "name": "Form operations",
                "description": "Edit a form with typed operations.",
            },
            {"name": "Responses", "description": "Read a form's responses."},
        ],
    )
    install_error_handlers(app)
    app.include_router(router)

    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
                tags=app.openapi_tags,
                servers=app.servers,
                separate_input_output_schemas=False,
            )
            # bodies the endpoints read themselves (size-capped) are only
            # named in their requestBody: add the ones no response names
            schema["components"]["schemas"].setdefault(
                "OpsRequest",
                OpsRequest.model_json_schema(
                    by_alias=True, ref_template="#/components/schemas/{model}"
                ),
            )
            # FastAPI's default 422 schemas are never sent: every error is Error
            schema["components"]["schemas"].pop("HTTPValidationError", None)
            schema["components"]["schemas"].pop("ValidationError", None)
            for path in schema.get("paths", {}).values():
                for operation in path.values():
                    responses = operation.get("responses", {})
                    error = responses.get("422")
                    if error and "HTTPValidationError" in json.dumps(error):
                        responses["422"] = {
                            "description": "The request is not valid.",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        }
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    return app


def build_public_api_asgi():
    """The public API, wrapped for auditing, ready to mount."""
    return AuditAndErrors(build_public_api())
