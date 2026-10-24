"""Preference memory (plan §2.4) — a living document per creator × workspace.

Write path: a cheap extraction pass after each chat turn proposes durable
FORM-STYLE preferences (never one-off instructions, never personal data,
never org policy — that's the profile's job). Best-effort: extraction
failures are logged and swallowed, a turn never fails because memory did.

Read path: rendered by the prompt builder at the LOWEST precedence.
"""

import datetime as dt
import json
import uuid
from http import HTTPStatus
from typing import Any, Dict, List, Optional

import loguru
from common.records import RecordId
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.services.ai.structured import chat_json
from backend.app.services.ai.untrusted import UNTRUSTED_CONTENT_RULES, fence
from backend.app.models.enum.permission import Permission
from backend.config import settings

MAX_ENTRIES = 50
MAX_ENTRY_CHARS = 300

EXTRACTION_SYSTEM_PROMPT = """You maintain a tiny memory of a form creator's DURABLE STYLE PREFERENCES.

From the exchange below, extract 0-2 preferences that would apply to FUTURE
forms this person builds. Only include:
- lasting style/structure preferences (tone, length, field habits, naming)
- stated corrections of the assistant's defaults ("don't add placeholders")

NEVER include:
- one-off instructions specific to this form ("add an email field here")
- personal data, names, emails, or anything about respondents
- organization policy or compliance (that lives elsewhere)

Existing memory (do not repeat anything equivalent):
{existing}

The exchange arrives inside <exchange>. Reply with ONLY a JSON object:
{{"memories": ["...", "..."]}} — empty list if nothing qualifies. Each memory
is one short sentence."""
EXTRACTION_SYSTEM_PROMPT += "\n" + UNTRUSTED_CONTENT_RULES.replace("{", "{{").replace(
    "}", "}}"
)


class _ExtractionReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memories: List[Any] = []


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class MemoryEntryDto(_CamelModel):
    id: str
    text: str
    at: Optional[str] = None
    source: Optional[str] = None


class AddMemoryEntryDto(_CamelModel):
    text: str = Field(..., min_length=1, max_length=MAX_ENTRY_CHARS)


def _c():
    # Resolved at call time: the container imports this module.
    from backend.app.container import container

    return container


class AIMemoryService:
    @staticmethod
    async def _get_document(
        workspace_id: RecordId, user_id: str
    ) -> Optional[UserAIPreferenceMemoryDocument]:
        return await _c().ai_preference_memory_repo().find(workspace_id, user_id)

    async def get_entries(
        self, workspace_id: RecordId, user: User
    ) -> List[MemoryEntryDto]:
        document = await self._get_document(workspace_id, user.id)
        return [MemoryEntryDto(**e) for e in (document.entries if document else [])]

    async def add_entry(
        self, workspace_id: RecordId, user: User, dto: AddMemoryEntryDto
    ) -> List[MemoryEntryDto]:
        await self._append(workspace_id, user.id, [dto.text], source="manual")
        return await self.get_entries(workspace_id, user)

    async def delete_entry(
        self, workspace_id: RecordId, user: User, entry_id: str
    ) -> List[MemoryEntryDto]:
        document = await self._get_document(workspace_id, user.id)
        if not document or not any(e.get("id") == entry_id for e in document.entries):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Memory entry not found"
            )
        document.entries = [e for e in document.entries if e.get("id") != entry_id]
        await _c().ai_preference_memory_repo().save(document)
        return [MemoryEntryDto(**e) for e in document.entries]

    @staticmethod
    async def learns_preferences(workspace_id: RecordId, user_id: str) -> bool:
        """The user's "Learn my preferences" setting (default off)."""
        document = await AIMemoryService._get_document(workspace_id, user_id)
        return bool(document and document.learn_preferences)

    async def set_learn_preferences(
        self, workspace_id: RecordId, user: User, enabled: bool
    ) -> bool:
        """Turn extraction from chat turns on or off for the caller."""
        await _c().authorization_service().authorize(
            user, Permission.FORM_READ, workspace_id
        )
        document = await self._get_document(workspace_id, user.id)
        if document is None:
            document = UserAIPreferenceMemoryDocument(
                workspace_id=workspace_id, user_id=user.id, entries=[]
            )
        document.learn_preferences = bool(enabled)
        document.learn_preferences_at = dt.datetime.now(dt.timezone.utc)
        await _c().ai_preference_memory_repo().save(document)
        return document.learn_preferences

    @staticmethod
    async def get_entries_for_prompt(
        workspace_id: RecordId, user_id: str
    ) -> List[str]:
        """Internal read for prompt building — the surrounding AI action is
        already authorized."""
        document = await AIMemoryService._get_document(workspace_id, user_id)
        return [e["text"] for e in (document.entries if document else [])]

    @staticmethod
    async def _append(
        workspace_id: RecordId, user_id: str, texts: List[str], source: str
    ) -> None:
        document = await AIMemoryService._get_document(workspace_id, user_id)
        if document is None:
            document = UserAIPreferenceMemoryDocument(
                workspace_id=workspace_id, user_id=user_id, entries=[]
            )

        existing_normalized = {e["text"].strip().lower() for e in document.entries}
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        for text in texts:
            text = (text or "").strip()[:MAX_ENTRY_CHARS]
            if not text or text.lower() in existing_normalized:
                continue
            document.entries.append(
                {"id": str(uuid.uuid4()), "text": text, "at": now, "source": source}
            )
            existing_normalized.add(text.lower())

        # Living document, not a landfill: oldest entries fall off first.
        if len(document.entries) > MAX_ENTRIES:
            document.entries = document.entries[-MAX_ENTRIES:]
        await _c().ai_preference_memory_repo().save(document)

    async def extract_from_turn(
        self,
        provider,
        workspace_id: RecordId,
        user_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> None:
        """Best-effort background extraction after a chat turn. Runs only
        when the user turned on "Learn my preferences" and the workspace
        still has AI enabled (#715)."""
        try:
            if not await self.learns_preferences(workspace_id, user_id):
                return
            if not await _c().ai_consent_service().consented_provider(workspace_id):
                return
            existing = await self.get_entries_for_prompt(workspace_id, user_id)
            system = EXTRACTION_SYSTEM_PROMPT.format(
                existing=fence(
                    "existing_memory",
                    "\n".join(f"- {t}" for t in existing) or "(empty)",
                )
            )
            parsed = await chat_json(
                provider,
                system,
                [
                    {
                        "role": "user",
                        "content": fence(
                            "exchange",
                            f"Creator said: {user_message}\n"
                            f"Assistant did: {assistant_reply}",
                        ),
                    }
                ],
                _ExtractionReply,
                max_output_tokens=settings.ai.MAX_OUTPUT_TOKENS_MEMORY,
            )
            memories = [m for m in parsed.memories if isinstance(m, str)][:2]
            if memories:
                await self._append(workspace_id, user_id, memories, source="extracted")
        except Exception as e:  # noqa: BLE001 — memory must never break a turn
            # the error's type only: its message can quote the exchange
            loguru.logger.warning("AI memory extraction skipped ({})", type(e).__name__)
