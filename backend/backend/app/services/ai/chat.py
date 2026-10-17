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
from typing import Callable, List, Literal, Optional

from fastapi import BackgroundTasks

from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
from pydantic.alias_generators import to_camel
from starlette.concurrency import run_in_threadpool

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
    apply_settings_ops,
    parse_ops,
)
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.ai.proposals import (
    STATUS_ACCEPTED,
    ProposalDto,
    build_proposal,
    dump_op,
    proposal_record,
)
from backend.app.services.ai.structured import chat_json
from backend.app.services.form_writes import persist_form
from backend.app.services.ai.prompt_builder import (
    build_chat_system_prompt,
    project_form,
)
from backend.config import settings
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission

# Context discipline: resend at most this many prior turns.
MAX_HISTORY_MESSAGES = 20


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FormAIChatRequest(_CamelModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    provider: Optional[str] = None
    # "apply": the turn's ops are saved at once (MCP, older clients).
    # "propose": nothing is saved; the reply carries a proposal the person
    # accepts or rejects (services/ai/proposals.py). The editor proposes.
    mode: Literal["apply", "propose"] = "apply"


class FormAIChatResponse(_CamelModel):
    session_id: str
    reply: str
    results: List[OpResult] = []
    # The updated draft, camelised by the controller's response model.
    # Apply mode only.
    form: Optional[dict] = None
    # Propose mode, when an op would change something.
    proposal: Optional[ProposalDto] = None
    # Present when a turn changed form settings (purpose/retention/…) — the
    # Form tab's metadata lives on the workspace-form association, not the
    # form body, so the client updates it from here.
    settings: Optional[dict] = None


class _ChatTurnReply(BaseModel):
    """The model's reply to one chat turn: words for the creator and the
    typed operations, validated here so a reply with an invalid operation
    is retried once like any other unusable reply."""

    model_config = ConfigDict(extra="ignore")

    reply: Optional[str] = None
    ops: List[dict] = []
    _parsed_ops: list = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def _typed_ops(self):
        try:
            self._parsed_ops = parse_ops(self.ops or [])
        except Exception as error:  # noqa: BLE001 — reported back to the model
            errors = getattr(error, "errors", None)
            if callable(errors):
                details = "; ".join(
                    ".".join(str(p) for p in e.get("loc", ())) + ": " + e.get("msg", "")
                    for e in errors(include_input=False, include_url=False)[:10]
                )
            else:
                details = type(error).__name__
            raise ValueError(f"invalid operations: {details}") from None
        return self


UNUSABLE_CHAT_REPLY = (
    "The AI returned an unusable reply — nothing was changed. Please try again."
)


def _history_content(message: dict) -> str:
    """A past turn as the model reads it again: a proposal that was not
    accepted says so, as the form it sees does not have those changes."""
    content = message.get("content") or ""
    record = message.get("proposal")
    if isinstance(record, dict) and record.get("status") != STATUS_ACCEPTED:
        content += "\n(These changes were proposed but not applied.)"
    return content


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
    if not any(
        result.ok and isinstance(op, UpdateFormSettingsOp)
        for op, result in zip(ops, results)
    ):
        return None
    workspace_form = await _c().workspace_form_repo().find_first_by_form_id(form_id)
    if not workspace_form:
        return None
    settings = workspace_form.settings
    apply_settings_ops(settings, ops, results)
    await _c().workspace_form_repo().save(workspace_form)
    return WorkspaceFormSettingsCamelModal(**settings.model_dump()).model_dump(
        mode="json", by_alias=True
    )


async def persist_ops_to_form(
    form_document: FormDocument,
    form: StandardForm,
    ops,
    atomic: bool = False,
    expected_updated_at=None,
) -> tuple:
    """Apply ops and persist when anything applied.

    The ONE write path for AI form mutation — the chat turn, review fixes,
    accepted proposals and MCP's update_form all go through here; never two
    ways to mutate a form.
    ``atomic``: all or nothing — when any op fails, nothing (form or
    settings) is written.
    ``expected_updated_at``: write conditionally (persist_form), 409
    ``form_changed`` when the stored draft is newer; settings are written
    only after the form was.
    Returns (new_form, results, updated_settings_or_none).
    """
    # CPU-bound on a large form: off the event loop
    new_form, results = await run_in_threadpool(
        apply_form_ops, form, ops, atomic=atomic
    )
    if atomic and not all(r.ok for r in results):
        return new_form, results, None
    if any(r.ok for r in results):
        await persist_form(
            _c().form_repo(),
            form_document,
            new_form,
            expected_updated_at=expected_updated_at,
        )
    settings = await _persist_settings_ops(form_document.form_id, ops, results)
    return new_form, results, settings


def camel_form_reply(new_form: StandardForm, form_document: FormDocument) -> dict:
    """The updated draft for the webapp (camelCase), with the stored
    ``updatedAt``: the builder sends it back with its next save, so its own
    AI edit never reads as a change made elsewhere (form_concurrency.py)."""
    reply = StandardFormCamelModel(**new_form.model_dump()).model_dump(
        mode="json", by_alias=True
    )
    updated_at = getattr(form_document, "updated_at", None)
    if updated_at is not None:
        reply["updatedAt"] = updated_at.isoformat()
    return reply


class FormAIChatService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        provider_resolver: Callable,
        workspace_form_repo: WorkspaceFormRepository,
        form_repo: FormRepository,
        session_repo: FormAISessionRepository,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo
        self._session_repo = session_repo
        # Injected so tests (and future per-workspace BYO keys) swap providers
        # without touching this flow. Signature:
        # async (workspace_id, provider_name|None) -> provider, 403 when the
        # workspace has not opted in to AI.
        self._provider_resolver = provider_resolver

    async def chat_edit(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        request: FormAIChatRequest,
        user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> FormAIChatResponse:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)

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

        # The workspace's AI opt-in (#715), before anything is loaded into a
        # prompt: 403 ai_not_enabled when it is off.
        provider = await self._provider_resolver(
            workspace_id, request.provider, user_id=user.id
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
            {"role": m["role"], "content": _history_content(m)}
            for m in (session.messages or [])[-MAX_HISTORY_MESSAGES:]
        ]
        messages = history + [{"role": "user", "content": request.message}]

        # JSON of the turn's shape, retried once; a reply that still breaks
        # the contract is a 502 and changes nothing.
        turn = await chat_json(
            provider,
            system,
            messages,
            _ChatTurnReply,
            max_output_tokens=settings.ai.MAX_OUTPUT_TOKENS_CHAT,
            unusable_message=UNUSABLE_CHAT_REPLY,
        )
        ops = turn._parsed_ops
        reply = str(turn.reply or "Done.")

        proposal = None
        new_form = updated_settings = None
        if request.mode == "propose":
            # The proposal's id names its session: give a new one its id now.
            if session.id is None:
                session.id = PydanticObjectId()
            # a dry run per op, spec and diff: off the event loop
            proposal, results = await run_in_threadpool(
                build_proposal, form, association.settings, ops, reply, session.id
            )
        else:
            new_form, results, updated_settings = await persist_ops_to_form(
                form_document, form, ops
            )

        now = dt.datetime.now(dt.timezone.utc).isoformat()
        assistant_turn = {
            "role": "assistant",
            "content": reply,
            "ops": (
                [dump_op(op) for op in ops]
                if proposal
                else [op.model_dump(by_alias=True) for op in ops]
            ),
            "results": [r.model_dump(by_alias=True) for r in results],
            "at": now,
        }
        if proposal is not None:
            assistant_turn["proposal"] = proposal_record(
                proposal, getattr(form_document, "updated_at", None)
            )
        session.provider = request.provider or session.provider
        session.messages = (session.messages or []) + [
            {"role": "user", "content": request.message, "at": now},
            assistant_turn,
        ]
        await self._session_repo.save(session)

        # Preference-memory extraction: cheap, best-effort, off the critical
        # path. Async background tasks run on the MAIN loop (single-loop
        # pymongo client — see the OTP lesson), and extraction failures are
        # swallowed inside the service.
        if background_tasks is not None and await AIMemoryService.learns_preferences(
            workspace_id, user.id
        ):
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
            form=(
                camel_form_reply(new_form, form_document)
                if new_form is not None
                else None
            ),
            settings=updated_settings,
            proposal=proposal,
        )
