"""Chat-based form editing (plan §2.2) — one turn = ops applied to the draft.

Flow per turn:
  authorize → load draft → snapshot + system prompt (org profile grounded)
  → provider.chat() → tolerant JSON parse → parse_ops (schema) →
  apply_form_ops (per-op graceful) → persist draft → append to session.

The same ops pipeline will serve MCP's ``update_form`` — one way to mutate a
form, never two.
"""

import datetime as dt
from http import HTTPStatus
from typing import Callable, List, Optional

from fastapi import BackgroundTasks

from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.ai.memory import AIMemoryService
from backend.app.services.ai.ops import OpResult, apply_form_ops, parse_ops
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.ai.prompt_builder import (
    build_chat_system_prompt,
    extract_json_object,
    project_form,
)
from backend.app.services.workspace_user_service import WorkspaceUserService

# Context discipline: resend at most this many prior turns.
MAX_HISTORY_MESSAGES = 20


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FormAIChatRequest(_CamelModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    provider: Optional[str] = None


class FormAIChatResponse(_CamelModel):
    session_id: str
    reply: str
    results: List[OpResult] = []
    # The updated draft, camelised by the controller's response model.
    form: dict


async def persist_ops_to_form(form_document: FormDocument, form: StandardForm, ops) -> tuple:
    """Apply ops and persist the draft when anything applied.

    The ONE write path for AI form mutation — the chat turn and MCP's
    update_form both go through here; never two ways to mutate a form.
    """
    new_form, results = apply_form_ops(form, ops)
    if any(r.ok for r in results):
        form_document.title = new_form.title
        form_document.description = new_form.description
        form_document.fields = new_form.fields
        form_document.theme = new_form.theme
        form_document.welcome_page = new_form.welcome_page
        form_document.thankyou_page = new_form.thankyou_page
        await form_document.save()
    return new_form, results


class FormAIChatService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        provider_resolver: Callable,
    ):
        self._workspace_user_service = workspace_user_service
        # Injected so tests (and future per-workspace BYO keys) swap providers
        # without touching this flow. Signature: (provider_name|None) -> provider.
        self._provider_resolver = provider_resolver

    async def chat_edit(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: FormAIChatRequest,
        user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> FormAIChatResponse:
        await self._workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )

        form_document = await FormDocument.find_one({"form_id": form_id})
        if not form_document:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")

        # Session: continue or start.
        session = None
        if request.session_id:
            session = await FormAISessionDocument.get(PydanticObjectId(request.session_id))
            if session and (session.form_id != form_id or str(session.workspace_id) != str(workspace_id)):
                raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, content="Session does not belong to this form")
        if session is None:
            session = FormAISessionDocument(
                workspace_id=workspace_id, form_id=form_id, user_id=user.id, messages=[]
            )

        form = StandardForm(**form_document.model_dump())
        profile = await AIProfileService.get_profile_for_prompt(workspace_id)
        memory_entries = await AIMemoryService.get_entries_for_prompt(workspace_id, user.id)
        system = build_chat_system_prompt(project_form(form), profile, memory_entries)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in (session.messages or [])[-MAX_HISTORY_MESSAGES:]
        ]
        messages = history + [{"role": "user", "content": request.message}]

        provider = self._provider_resolver(request.provider)
        raw_reply = await provider.chat(system, messages)

        try:
            parsed = extract_json_object(raw_reply)
            ops = parse_ops(parsed.get("ops") or [])
            reply = str(parsed.get("reply") or "Done.")
        except Exception:
            # The model broke the contract — surface honestly, change nothing.
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                content="The AI returned an unusable reply — nothing was changed. Please try again.",
            )

        new_form, results = await persist_ops_to_form(form_document, form, ops)

        now = dt.datetime.now(dt.timezone.utc).isoformat()
        session.provider = request.provider or session.provider
        session.messages = (session.messages or []) + [
            {"role": "user", "content": request.message, "at": now},
            {
                "role": "assistant",
                "content": reply,
                "ops": [op.model_dump(by_alias=True) for op in ops],
                "results": [r.model_dump(by_alias=True) for r in results],
                "at": now,
            },
        ]
        await session.save()

        # Preference-memory extraction: cheap, best-effort, off the critical
        # path. Async background tasks run on the MAIN loop (single-loop
        # pymongo client — see the OTP lesson), and extraction failures are
        # swallowed inside the service.
        if background_tasks is not None:
            background_tasks.add_task(
                AIMemoryService().extract_from_turn,
                provider,
                workspace_id,
                user.id,
                request.message,
                reply,
            )

        return FormAIChatResponse(
            session_id=str(session.id),
            reply=reply,
            results=results,
            # Camelised — the webapp's form DTOs are camelCase.
            form=StandardFormCamelModel(**new_form.model_dump()).model_dump(mode="json", by_alias=True),
        )
