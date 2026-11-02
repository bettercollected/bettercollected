"""The history of a response, read: who edited it, when, which questions
(``list_revisions``), and on demand the values they had before
(``previous_values``). Behind ``RESPONSE_REVISIONS_ENABLED`` and
``response.read`` (with the form's scope); writing is in the response
repository's edit transaction, never here.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Dict, Optional

from common.constants import MESSAGE_NOT_FOUND
from common.ids import RecordId
from common.models.user import User
from common.services.crypto_service import UnreadableCiphertext, crypto_service
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_revisions_dto import (
    RevisionActorDto,
    RevisionChangedDto,
    RevisionEntryDto,
    RevisionListDto,
    RevisionValuesDto,
)
from backend.app.models.enum.permission import Permission
from backend.app.schemas.response_revision import (
    DELETED_ACTOR,
    ActorKind,
    seal_context,
)
from backend.app.services.form_versions.compare import plain
from backend.app.services.response_revisions.mode import ensure_enabled


def question_titles(form: Any) -> Dict[str, str]:
    """Question id -> title (plain text) over a form's page and group tree."""
    titles: Dict[str, str] = {}

    def walk(fields):
        for field in fields or []:
            field_id = getattr(field, "id", None)
            if field_id:
                titles[str(field_id)] = plain(
                    getattr(field, "title", None) or getattr(field, "value", None), 160
                )
            walk(getattr(getattr(field, "properties", None), "fields", None))

    walk(getattr(form, "fields", None))
    return titles


def without_links(answer: Any) -> Any:
    """An answer with no way to a stored file: a file's link, a drawn
    signature's image id (the history shows what was answered, never opens
    a file)."""
    if not isinstance(answer, dict):
        return answer
    cleaned = dict(answer)
    metadata = cleaned.get("file_metadata")
    if isinstance(metadata, dict):
        cleaned["file_metadata"] = {k: v for k, v in metadata.items() if k != "url"}
    cleaned.pop("file_url", None)
    signature = cleaned.get("signature")
    if isinstance(signature, dict):
        cleaned["signature"] = {k: v for k, v in signature.items() if k != "file_id"}
    return cleaned


class ResponseRevisionService:
    def __init__(
        self,
        authorization_service,
        form_response_service,
        revision_repo,
        form_repo,
        member_directory,
    ):
        self._authorization = authorization_service
        self._responses = form_response_service
        self._revisions = revision_repo
        self._form_repo = form_repo
        self._members = member_directory

    async def _response(
        self, workspace_id: RecordId, form_id: str, response_id: str, user: User
    ):
        """``response.read`` on the form (404 for another workspace's form),
        then this workspace's copy of the response (404 when it is gone or
        belongs to another form)."""
        ensure_enabled()
        await self._authorization.authorize(
            user, Permission.RESPONSE_READ, workspace_id, form_id=form_id
        )
        response = await self._responses.workspace_response(workspace_id, response_id)
        if response is None or str(response.form_id) != str(form_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        return response

    async def list_revisions(
        self, workspace_id: RecordId, form_id: str, response_id: str, user: User
    ) -> RevisionListDto:
        response = await self._response(workspace_id, form_id, response_id, user)
        entries = await self._revisions.list_for_response(response.id)
        form = None
        if response.form_version:
            form = await self._form_repo.get_form_by_by_version(
                RecordId(form_id), response.form_version
            )
        form = form or await self._form_repo.get_latest_version_of_form(
            RecordId(form_id)
        )
        titles = question_titles(form) if form is not None else {}
        roles, names = await self._members.lookup(
            workspace_id,
            [e.actor_id for e in entries if e.actor_kind == ActorKind.STAFF],
        )

        def actor(entry) -> RevisionActorDto:
            if entry.actor_kind == ActorKind.RESPONDENT:
                return RevisionActorDto(kind=ActorKind.RESPONDENT.value)
            if entry.actor_kind == ActorKind.API_KEY:
                # a workspace API key: neither its id nor a user is shown
                return RevisionActorDto(kind=ActorKind.API_KEY.value)
            member = entry.actor_id in roles and entry.actor_id != DELETED_ACTOR
            return RevisionActorDto(
                kind=ActorKind.STAFF.value,
                name=names.get(entry.actor_id) if member else None,
                # the role they held when they edited
                role=entry.actor_role,
                former=not member,
            )

        return RevisionListDto(
            revisions=[
                RevisionEntryDto(
                    seq=entry.seq,
                    at=entry.created_at,
                    actor=actor(entry),
                    changed=[
                        RevisionChangedDto(id=q, title=titles.get(q) or None)
                        for q in entry.changed
                    ],
                )
                for entry in entries
            ]
        )

    async def previous_values(
        self,
        workspace_id: RecordId,
        form_id: str,
        response_id: str,
        seq: int,
        user: User,
    ) -> RevisionValuesDto:
        """One entry's values before the edit, unsealed (``response.read``):
        what the response held, not a new place to keep it: the call is not
        stored and the values are not cached."""
        response = await self._response(workspace_id, form_id, response_id, user)
        entry = await self._revisions.get(response.id, seq)
        if entry is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        values: Dict[str, Optional[Dict[str, Any]]] = {}
        if entry.previous_values:
            try:
                sealed = json.loads(
                    crypto_service.decrypt(
                        workspace_id=workspace_id,
                        form_id=form_id,
                        data=bytes(entry.previous_values),
                        context=seal_context(entry.response_pk, entry.seq),
                    )
                )
            except (UnreadableCiphertext, ValueError):
                logger.warning(
                    "revision {} of response {} could not be read", seq, response.id
                )
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content="The previous values of this edit can't be read.",
                )
            values = {q: without_links(v) for q, v in sealed.items()}
        return RevisionValuesDto(seq=entry.seq, values=values)
