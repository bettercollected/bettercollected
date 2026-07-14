"""BetterCollected's MCP server (plan §2.5) — forms as tools for any LLM.

Transport: stateless streamable-HTTP, mounted at /mcp on the main FastAPI
app. Auth: workspace-scoped API keys as Bearer tokens (see
services/ai/api_keys.py); a pure-ASGI middleware resolves the key into a
contextvar the tools read. Every call lands in the MCP audit log.

Tools deliberately reuse the same services/pipelines as the product —
``update_form`` goes through the exact ops engine the builder chat uses.
"""

import datetime as dt
import json
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import parse_ops
from backend.app.services.ai.profile import AIProfileService

current_api_key: ContextVar[Optional[WorkspaceAPIKeyDocument]] = ContextVar(
    "current_api_key", default=None
)

mcp = FastMCP(
    "bettercollected",
    instructions=(
        "BetterCollected is a privacy-first form builder. Tools operate on the "
        "workspace your API key belongs to. Respect the workspace's AI profile "
        "(get_ai_profile) when creating or editing forms."
    ),
    stateless_http=True,
    streamable_http_path="/",
    # Host pinning (DNS-rebinding protection) is for unauthenticated localhost
    # servers; this endpoint requires a Bearer API key and is deployed under
    # arbitrary hostnames, so the Host allowlist can't be known here.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _key(scope: str) -> WorkspaceAPIKeyDocument:
    key = current_api_key.get()
    if key is None:
        raise ValueError("Not authenticated")
    try:
        APIKeyService.require_scope(key, scope)
    except HTTPException as e:
        # Our HTTPException carries the message in `content`, which str() drops
        # — re-raise as ValueError so the MCP client sees why it was denied.
        raise ValueError(str(e.content)) from e
    return key


def _acting_user(key: WorkspaceAPIKeyDocument) -> User:
    # Authorization inside the product services runs as the key's creator.
    return User(id=key.created_by, sub=f"api-key:{key.name}", roles=["FORM_CREATOR"])


async def _audit(tool: str, ok: bool, detail: str = "") -> None:
    try:
        key = current_api_key.get()
        if key is None:
            return
        await MCPAuditLogDocument(
            workspace_id=key.workspace_id,
            key_id=str(key.id),
            tool=tool,
            ok=ok,
            detail=detail[:300],
            at=dt.datetime.now(dt.timezone.utc),
        ).save()
    except Exception:  # noqa: BLE001 — auditing must not break tool calls
        pass


async def _workspace_form_ids(workspace_id: PydanticObjectId) -> Dict[str, WorkspaceFormDocument]:
    docs = await WorkspaceFormDocument.find(
        WorkspaceFormDocument.workspace_id == workspace_id
    ).to_list()
    return {d.form_id: d for d in docs}


def _require_form_in_workspace(form_id: str, workspace_forms: Dict[str, Any]) -> None:
    if form_id not in workspace_forms:
        raise ValueError(f"Form '{form_id}' does not exist in this workspace.")


@mcp.tool()
async def list_forms() -> str:
    """List the workspace's forms: id, title, share slug and publish state."""
    key = _key("forms:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    forms = await FormDocument.find({"form_id": {"$in": list(workspace_forms)}}).to_list()
    items = [
        {
            "formId": f.form_id,
            "title": f.title,
            "slug": workspace_forms[f.form_id].settings.custom_url if workspace_forms[f.form_id].settings else None,
            "published": f.published_at is not None,
        }
        for f in forms
    ]
    await _audit("list_forms", True, f"{len(items)} forms")
    return json.dumps(items)


@mcp.tool()
async def get_form(form_id: str) -> str:
    """Get a form's full structure (pages, fields, settings) as JSON."""
    key = _key("forms:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    form = await FormDocument.find_one({"form_id": form_id})
    await _audit("get_form", True, form_id)
    return json.dumps(
        StandardFormCamelModel(**StandardForm(**form.model_dump()).model_dump()).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    )


@mcp.tool()
async def create_form(title: str, description: str = "") -> str:
    """Create a blank draft form (one empty page) — for building precisely
    with update_form ops. Use create_form_with_ai when you want the platform
    to design the form from a prompt instead."""
    key = _key("forms:write")
    import uuid as _uuid

    from common.models.standard_form import (
        LayoutType,
        StandardFieldProperty,
        StandardFormField,
        StandardFormFieldType,
        ThankYouPageField,
        WelcomePageField,
    )

    from backend.app.container import container

    # Mirror the builder's defaultForm (webapp constants/form.ts): forms need a
    # welcome + thank-you page — the responder's post-submit screen renders
    # thankyouPage, and API-born forms must behave like builder-born ones.
    blank = StandardForm(
        title=title,
        description=description or None,
        builder_version="v2",
        welcome_page=WelcomePageField(title="", layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND),
        thankyou_page=[ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)],
        fields=[
            StandardFormField(
                id=str(_uuid.uuid4()),
                index=0,
                type=StandardFormFieldType.SLIDE,
                properties=StandardFieldProperty(fields=[], layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND),
            )
        ],
    )
    form = await container.workspace_form_service().create_form(
        workspace_id=key.workspace_id, form=blank, user=_acting_user(key)
    )
    await _audit("create_form", True, form.form_id)
    return json.dumps({"formId": form.form_id, "title": form.title, "published": False})


@mcp.tool()
async def create_form_with_ai(prompt: str) -> str:
    """Create a new draft form from a natural-language prompt. Generation is
    grounded in the workspace's AI profile (guidelines + compliance)."""
    key = _key("forms:write")
    from backend.app.container import container

    form = await container.openai_service().create_form_with_ai(
        workspace_id=key.workspace_id,
        create_form_ai=CreateFormWithAI(prompt=prompt),
        user=_acting_user(key),
    )
    await _audit("create_form_with_ai", True, form.form_id)
    return json.dumps({"formId": form.form_id, "title": form.title, "published": False})


@mcp.tool()
async def update_form(form_id: str, ops: List[Dict[str, Any]]) -> str:
    """Edit a form with typed operations — the same pipeline the builder's AI
    chat uses. Reference page/field ids from get_form. Op shapes (camelCase):
    {"op":"add_field","pageId":str,"field":{"title":str,"type":str,"required"?:bool,
    "placeholder"?:str,"choices"?:[str],"steps"?:int},"afterFieldId"?:str,"index"?:int} ·
    {"op":"update_field","fieldId":str,"patch":{...same keys as field}} ·
    {"op":"remove_field","fieldId":str} ·
    {"op":"move_field","fieldId":str,"toPageId"?:str,"index":int} ·
    {"op":"add_page","index"?:int,"fields"?:[field]} · {"op":"remove_page","pageId":str} ·
    {"op":"update_form_info","title"?:str,"description"?:str} ·
    {"op":"update_form_settings","patch":{"purpose"?:str,"retentionText"?:str,
    "privacyPolicyUrl"?:str,"requireVerifiedIdentity"?:bool,"allowEditingResponse"?:bool,
    "showSubmissionNumber"?:bool}} (trust metadata; "" clears a text value) ·
    {"op":"set_field_logic","fieldId":str,"logic":{"action":"SHOW"|"HIDE","operator":"AND"|"OR",
    "conditions":[{"fieldId":str,"comparison":"IS_EQUAL"|"IS_NOT_EQUAL"|"CONTAINS"|"IS_EMPTY"|...,
    "value"?:any}]}|null} (conditional visibility; choice values use the LABEL, yes/no uses "Yes"/"No") ·
    {"op":"set_page_jumps","pageId":str,"jumps":[{"operator":"AND"|"OR","conditions":[...],
    "target":"<page id or __SUBMIT__>"}]|null} (branching) ·
    {"op":"duplicate_page","pageId":str,"index"?:int} (clone a page, fresh ids).
    Field types: short_text, long_text, email, number, url, phone_number, date,
    yes_no, multiple_choice, dropdown, rating, linear_rating, file_upload, text."""
    key = _key("forms:write")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    form_document = await FormDocument.find_one({"form_id": form_id})
    parsed = parse_ops(ops)
    form = StandardForm(**form_document.model_dump())
    _, results, updated_settings = await persist_ops_to_form(form_document, form, parsed)
    payload = [r.model_dump(by_alias=True) for r in results]
    await _audit("update_form", all(r.ok for r in results), f"{form_id}: {len(results)} ops")
    return json.dumps({"results": payload, "settings": updated_settings})


@mcp.tool()
async def publish_form(form_id: str) -> str:
    """Publish a form so it can accept responses. Returns the share slug."""
    key = _key("forms:write")
    from backend.app.container import container

    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    await container.workspace_form_service().publish_form(
        workspace_id=key.workspace_id, form_id=PydanticObjectId(form_id), user=_acting_user(key)
    )
    refreshed = await WorkspaceFormDocument.find_one(
        WorkspaceFormDocument.workspace_id == key.workspace_id,
        WorkspaceFormDocument.form_id == form_id,
    )
    slug = refreshed.settings.custom_url if refreshed and refreshed.settings else None
    await _audit("publish_form", True, form_id)
    return json.dumps({"formId": form_id, "published": True, "slug": slug})


@mcp.tool()
async def list_responses(form_id: str, limit: int = 20) -> str:
    """List a form's responses (most recent first): response id, submission
    time, and answer count. Use get_response for full answers."""
    key = _key("responses:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    _require_form_in_workspace(form_id, workspace_forms)
    limit = max(1, min(limit, 100))
    responses = (
        await FormResponseDocument.find(FormResponseDocument.form_id == form_id)
        .sort("-created_at")
        .limit(limit)
        .to_list()
    )
    items = [
        {
            "responseId": r.response_id,
            "submittedAt": str(getattr(r, "created_at", "")),
            # Answers are encrypted at rest (str/bytes) — len() of ciphertext
            # is meaningless, so only count when they are a readable dict.
            "answerCount": len(r.answers) if isinstance(r.answers, dict) else None,
        }
        for r in responses
    ]
    await _audit("list_responses", True, f"{form_id}: {len(items)}")
    return json.dumps(items)


@mcp.tool()
async def get_response(response_id: str) -> str:
    """Get one response's full answers."""
    key = _key("responses:read")
    response = await FormResponseDocument.find_one(FormResponseDocument.response_id == response_id)
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    if not response or response.form_id not in workspace_forms:
        raise ValueError("Response not found in this workspace.")
    # Answers are encrypted at rest — decrypt on this read path (the same
    # rule as the dashboard's response views).
    answers = response.answers
    if isinstance(answers, (bytes, str)):
        from common.services.crypto_service import crypto_service

        answers = json.loads(
            crypto_service.decrypt(workspace_id=key.workspace_id, form_id=response.form_id, data=answers)
        )
    await _audit("get_response", True, response_id)
    return json.dumps(
        {
            "responseId": response.response_id,
            "formId": response.form_id,
            "submittedAt": str(getattr(response, "created_at", "")),
            "answers": json.loads(json.dumps(answers if isinstance(answers, dict) else {}, default=str)),
        }
    )


@mcp.tool()
async def list_deletion_requests() -> str:
    """List pending response-deletion requests across the workspace — the
    privacy queue an operator (or agent) should act on."""
    key = _key("deletion_requests:read")
    workspace_forms = await _workspace_form_ids(key.workspace_id)
    requests = await FormResponseDeletionRequest.find(
        {"form_id": {"$in": list(workspace_forms)}}
    ).to_list()
    items = [
        {
            "responseId": r.response_id,
            "formId": r.form_id,
            "status": getattr(r, "status", None),
            "requestedAt": str(getattr(r, "created_at", "")),
        }
        for r in requests
    ]
    await _audit("list_deletion_requests", True, f"{len(items)} requests")
    return json.dumps(items)


@mcp.tool()
async def get_ai_profile() -> str:
    """The workspace's AI profile: about, form guidelines and compliance
    requirements. Respect these when creating or editing forms."""
    key = _key("forms:read")
    profile = await AIProfileService.get_profile_for_prompt(key.workspace_id)
    await _audit("get_ai_profile", True)
    return json.dumps(
        {
            "about": profile.about if profile else "",
            "guidelines": profile.guidelines if profile else "",
            "compliance": profile.compliance if profile else "",
        }
    )


class MCPAuthMiddleware:
    """Bearer API key → contextvar; anything else is a clean 401."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        try:
            key = await APIKeyService.authenticate(token)
        except HTTPException:
            body = json.dumps({"error": "Provide a valid workspace API key as a Bearer token."}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        ctx_token = current_api_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            current_api_key.reset(ctx_token)


def build_mcp_asgi_app():
    """The auth-wrapped MCP ASGI app, ready to mount at /mcp."""
    return MCPAuthMiddleware(mcp.streamable_http_app())
