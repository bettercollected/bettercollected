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
from backend.app.repositories.form_ai_session_repository import FormAISessionRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.ai.memory import AIMemoryService
from backend.app.models.dtos.response_dtos import WorkspaceFormSettingsCamelModal
from backend.app.services.ai.ops import (
    OpResult,
    UpdateFormSettingsOp,
    apply_form_ops,
    parse_ops,
)
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
    # Present when a turn changed form settings (purpose/retention/…) — the
    # Form tab's metadata lives on the workspace-form association, not the
    # form body, so the client updates it from here.
    settings: Optional[dict] = None


def _clear_or_set(value: Optional[str]) -> Optional[str]:
    """Trust-layer text semantics (mirrors patch_settings): '' clears."""
    return value or None


def _c():
    # Resolved at call time: the container imports this module.
    from backend.app.container import container

    return container


async def _persist_settings_ops(
    form_id: str, ops, results: List[OpResult]
) -> Optional[dict]:
    """Write applied update_form_settings ops to the association document.

    Returns the camelised updated settings, or None when no settings op
    applied."""
    patches = [
        op.patch
        for op, result in zip(ops, results)
        if result.ok and isinstance(op, UpdateFormSettingsOp)
    ]
    if not patches:
        return None
    workspace_form = await _c().workspace_form_repo().find_first_by_form_id(form_id)
    if not workspace_form:
        return None
    settings = workspace_form.settings
    for patch in patches:
        if patch.purpose is not None:
            settings.purpose = _clear_or_set(patch.purpose.strip())
        if patch.retention_text is not None:
            settings.retention_text = _clear_or_set(patch.retention_text.strip())
        if patch.privacy_policy_url is not None:
            settings.privacy_policy_url = _clear_or_set(
                patch.privacy_policy_url.strip()
            )
        if patch.require_verified_identity is not None:
            settings.require_verified_identity = patch.require_verified_identity
        if patch.allow_editing_response is not None:
            settings.allow_editing_response = patch.allow_editing_response
        if patch.show_submission_number is not None:
            settings.show_submission_number = patch.show_submission_number
    await _c().workspace_form_repo().save(workspace_form)
    return WorkspaceFormSettingsCamelModal(**settings.model_dump()).model_dump(
        mode="json", by_alias=True
    )


async def persist_ops_to_form(
    form_document: FormDocument, form: StandardForm, ops
) -> tuple:
    """Apply ops and persist when anything applied.

    The ONE write path for AI form mutation — the chat turn, review fixes and
    MCP's update_form all go through here; never two ways to mutate a form.
    Returns (new_form, results, updated_settings_or_none).
    """
    new_form, results = apply_form_ops(form, ops)
    if any(r.ok for r in results):
        form_document.title = new_form.title
        form_document.description = new_form.description
        form_document.fields = new_form.fields
        form_document.theme = new_form.theme
        form_document.welcome_page = new_form.welcome_page
        form_document.thankyou_page = new_form.thankyou_page
        await _c().form_repo().save_form(form_document)
    settings = await _persist_settings_ops(form_document.form_id, ops, results)
    return new_form, results, settings


class FormAIChatService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        provider_resolver: Callable,
        workspace_form_repo: WorkspaceFormRepository,
        form_repo: FormRepository,
        session_repo: FormAISessionRepository,
    ):
        self._workspace_user_service = workspace_user_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo
        self._session_repo = session_repo
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

        # The form must belong to THIS workspace — access to workspace A must
        # not allow editing workspace B's forms by id (MCP has the same rule).
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, form_id
        )
        form_document = (
            await self._form_repo.get_form_document_by_id(form_id)
            if association
            else None
        )
        if not form_document:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )

        # Session: continue or start.
        session = None
        if request.session_id:
            session = await self._session_repo.get_or_404(
                PydanticObjectId(request.session_id)
            )
            if session and (
                session.form_id != form_id
                or str(session.workspace_id) != str(workspace_id)
            ):
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    content="Session does not belong to this form",
                )
        if session is None:
            session = FormAISessionDocument(
                workspace_id=workspace_id, form_id=form_id, user_id=user.id, messages=[]
            )

        form = StandardForm(**form_document.model_dump())
        profile = await AIProfileService.get_profile_for_prompt(workspace_id)
        memory_entries = await AIMemoryService.get_entries_for_prompt(
            workspace_id, user.id
        )
        system = build_chat_system_prompt(
            project_form(form, settings=association.settings), profile, memory_entries
        )

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

        new_form, results, updated_settings = await persist_ops_to_form(
            form_document, form, ops
        )

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
        await self._session_repo.save(session)

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
            form=StandardFormCamelModel(**new_form.model_dump()).model_dump(
                mode="json", by_alias=True
            ),
            settings=updated_settings,
        )
