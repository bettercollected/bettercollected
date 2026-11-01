"""A form's published versions for staff: the list, a comparison of two, and
restoring one into the draft. Behind ``FORM_REVISIONS_UI_ENABLED``
(``mode.py``). Nothing here reads an answer, and restoring never writes or
deletes a version: it replaces the draft, and only a later publish makes a
new version.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Optional, Tuple, Union

from common.form_spec import SpecConversionError, form_to_spec_dict
from common.ids import RecordId
from common.models.standard_form import StandardForm
from common.models.user import User
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.form_versions_dto import (
    FormDraftStateDto,
    FormVersionListDto,
    FormVersionSummaryDto,
    RestoreVersionRequest,
    RestoreVersionResponse,
    VersionAuthorDto,
    VersionChangeDto,
    VersionCompareDto,
)
from backend.app.models.enum.permission import Permission
from backend.app.services.form_versions.compare import compare_specs
from backend.app.services.form_versions.mode import ensure_enabled
from backend.app.services.form_writes import FORM_PARTS, persist_form

#: the draft, as a side of a comparison
DRAFT = "draft"
#: most versions listed
LIST_LIMIT = 200

DRAFT_HAS_CHANGES_CODE = "draft_has_changes"
DRAFT_HAS_CHANGES_MESSAGE = (
    "The draft holds changes that are not published yet. Restoring a version "
    "replaces them."
)


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": code, "message": message},
    )


#: the highest version number any call takes: beyond it the version cannot exist
MAX_VERSION = 1_000_000
_VERSION = re.compile(r"[0-9]{1,7}")


def parse_side(value: Optional[str]) -> Union[int, str]:
    """``draft`` or a version number (ASCII digits only, at most
    ``MAX_VERSION``); 422 otherwise. Never an unhandled error: ``int()`` also
    refuses what ``str.isdigit`` accepts (superscripts, other scripts)."""
    text = (value or "").strip().lower()
    if text == DRAFT:
        return DRAFT
    if _VERSION.fullmatch(text) and 0 < int(text) <= MAX_VERSION:
        return int(text)
    raise _unprocessable(
        "invalid_version", "A version is a number, or draft."
    )


class FormVersionsService:
    def __init__(
        self,
        authorization_service,
        workspace_form_repo,
        form_repo,
        form_service,
        member_directory,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo
        self._form_service = form_service
        self._members = member_directory

    # -- reads ----------------------------------------------------------------
    async def list_versions(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> FormVersionListDto:
        """``form.read``."""
        ensure_enabled()
        await self._authorization.authorize(
            user, Permission.FORM_READ, workspace_id, form_id=form_id
        )
        summaries = await self._form_repo.list_version_summaries(
            form_id, limit=LIST_LIMIT + 1
        )
        truncated = len(summaries) > LIST_LIMIT
        summaries = summaries[:LIST_LIMIT]
        roles, names = await self._members.lookup(
            workspace_id, [by for _, _, by in summaries if by]
        )

        def author(user_id: Optional[str]) -> Optional[VersionAuthorDto]:
            if not user_id:
                return None
            if user_id not in roles:
                return VersionAuthorDto(former=True)
            return VersionAuthorDto(name=names.get(user_id), role=roles[user_id])

        newest = summaries[0][0] if summaries else None
        draft = await self._form_repo.get_form_document_by_id(str(form_id))
        latest = await self._form_repo.get_latest_version_of_form(form_id)
        return FormVersionListDto(
            truncated=truncated,
            versions=[
                FormVersionSummaryDto(
                    version=version,
                    published_at=created_at,
                    published_by=author(by),
                    current=version == newest,
                )
                for version, created_at, by in summaries
            ],
            draft=(
                FormDraftStateDto(
                    updated_at=draft.updated_at,
                    has_unpublished_changes=self._form_service.has_form_been_updated(
                        draft, latest
                    ),
                )
                if draft is not None
                else None
            ),
        )

    async def _side(self, form_id: str, side: Union[int, str]) -> StandardForm:
        if side == DRAFT:
            document = await self._form_repo.get_form_document_by_id(str(form_id))
        else:
            document = await self._form_repo.get_form_by_by_version(
                RecordId(form_id), side
            )
        if document is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Version not found")
        return StandardForm(**document.model_dump())

    @staticmethod
    def _spec(form: StandardForm) -> dict:
        try:
            return form_to_spec_dict(form, None)
        except SpecConversionError:
            raise _unprocessable(
                "not_comparable",
                "This version has no comparable form (it was made before page-based forms).",
            )

    async def compare(
        self,
        workspace_id: RecordId,
        form_id: str,
        from_version: Optional[str],
        to_version: Optional[str],
        user: User,
    ) -> VersionCompareDto:
        """``form.read``: what changed going from one version (or the
        draft) to another."""
        ensure_enabled()
        await self._authorization.authorize(
            user, Permission.FORM_READ, workspace_id, form_id=form_id
        )
        older, newer = parse_side(from_version), parse_side(to_version)
        before = await self._side(form_id, older)
        after = await self._side(form_id, newer)

        def work():
            return compare_specs(self._spec(before), self._spec(after))

        # CPU-bound on a large form: off the event loop
        result = await run_in_threadpool(work)
        return VersionCompareDto(
            from_version=str(older),
            to_version=str(newer),
            changed=result["changed"],
            entries=[VersionChangeDto(**e) for e in result["entries"]],
            truncated=result["truncated"],
        )

    # -- restore --------------------------------------------------------------
    async def restore(
        self,
        workspace_id: RecordId,
        form_id: str,
        version: int,
        body: RestoreVersionRequest,
        user: User,
    ) -> RestoreVersionResponse:
        """``form.edit``: the version's content replaces the draft's through
        the one form write (the switch gates and the conflict check of a
        builder save apply). History is not touched."""
        ensure_enabled()
        await self._authorization.authorize(
            user, Permission.FORM_EDIT, workspace_id, form_id=form_id
        )
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        )
        if association is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Form not found")
        if (association.settings.provider if association.settings else None) != "self":
            raise _unprocessable(
                "not_restorable", "Only a form made here can be restored."
            )
        if not 0 < version <= MAX_VERSION:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Version not found")
        target = await self._form_repo.get_form_by_by_version(
            RecordId(form_id), version
        )
        draft = await self._form_repo.get_form_document_by_id(str(form_id))
        if target is None or draft is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Version not found")
        latest = await self._form_repo.get_latest_version_of_form(form_id)
        if not body.replace_draft and self._form_service.has_form_been_updated(
            draft, latest
        ):
            raise HTTPException(
                HTTPStatus.CONFLICT,
                content={
                    "code": DRAFT_HAS_CHANGES_CODE,
                    "message": DRAFT_HAS_CHANGES_MESSAGE,
                },
            )
        stored = await persist_form(
            self._form_repo,
            draft,
            StandardForm(**target.model_dump()),
            parts=FORM_PARTS,
            expected_updated_at=body.expected_updated_at,
        )
        if not stored:
            from backend.app.services.form_concurrency import form_changed

            raise form_changed()
        return RestoreVersionResponse(
            restored_version=version, updated_at=draft.updated_at
        )
