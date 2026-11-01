"""A workspace's option lists: reference data a choice question can take its
options from. See ``docs/option-sources.md``.

Every call names the workspace and every read and write goes through it: a
list of another workspace is a 404. Reading needs ``form.read``, writing
``form.edit``. A list is stored as one document (items inside), saved under an
optimistic revision. Nothing here reads an answer.
"""

import csv
import datetime as dt
import io
import re
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Sequence, Tuple

from common.models.user import User
from common.records import RecordId
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.option_lists import (
    NameTaken,
    RevisionChanged,
)
from backend.app.schemas.option_list import OptionListDocument, OptionListItem
from backend.app.services.option_sources import ids, text
from backend.app.services.option_sources.mode import (
    DISABLED_CODE,
    DISABLED_MESSAGE,
    option_sources_enabled,
)

CSV_BYTES_MAX = 1_000_000
# a spreadsheet's neutralised formula cell (response_export.table.formula_safe_cell)
_GUARDED = re.compile(r"'([\t\r]|\s*[=+\-@])")
PAGE_MAX = text.ITEMS_PER_LIST


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class ItemDto(_Camel):
    id: Optional[str] = Field(None, max_length=64)
    label: str = Field(..., max_length=1000)
    group: Optional[str] = Field(None, max_length=1000)


class OptionListCreateDto(_Camel):
    name: str = Field(..., max_length=1000)
    order: str = Field("manual", pattern="^(manual|alphabetical)$")
    items: List[ItemDto] = Field(default_factory=list, max_length=text.ITEMS_PER_LIST)


class OptionListUpdateDto(_Camel):
    name: Optional[str] = Field(None, max_length=1000)
    order: Optional[str] = Field(None, pattern="^(manual|alphabetical)$")
    items: Optional[List[ItemDto]] = Field(None, max_length=text.ITEMS_PER_LIST)
    # the revision the editor read: another save since is a 409 (list_changed)
    expected_revision: Optional[int] = Field(None, ge=1)


class OptionListSummaryDto(_Camel):
    id: str
    name: str
    order: str
    item_count: int
    revision: int
    forms_using: int = 0
    updated_at: Optional[dt.datetime] = None


class UsedByDto(_Camel):
    form_id: str
    title: Optional[str] = None


class OptionListDto(OptionListSummaryDto):
    items: List[ItemDto]
    total_items: int
    used_by: List[UsedByDto] = Field(default_factory=list)


def _refuse(status: HTTPStatus, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status, content={"code": code, "message": message, **extra}
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="List not found")


def clean_items(
    rows: Sequence[Any], known_ids: Optional[Dict[str, OptionListItem]] = None
) -> List[OptionListItem]:
    """Items as stored: text rules applied, a (label, group) pair once, an id
    kept only when the list already has it (``known_ids``; None means no id may
    be supplied), a new item given a new id. Raises a 422 naming the row."""
    if len(rows) > text.ITEMS_PER_LIST:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "limit_reached",
            f"A list holds at most {text.ITEMS_PER_LIST} items.",
        )
    items: List[OptionListItem] = []
    seen: set = set()
    used_ids: set = set()
    for index, row in enumerate(rows):
        label = text.clean(row.label, text.LABEL_MAX)
        group = row.group
        group_clean = (
            text.clean(group, text.GROUP_MAX) if group not in (None, "") else None
        )
        if label is None or (group not in (None, "") and group_clean is None):
            raise _refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_item",
                f"Item {index + 1} needs a label of 1 to {text.LABEL_MAX} characters "
                f"(a group of at most {text.GROUP_MAX}) without control characters.",
                row=index + 1,
            )
        pair = (text.fold(label), text.fold(group_clean) if group_clean else "")
        if pair in seen:
            raise _refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "duplicate_item",
                f"Item {index + 1} repeats an earlier item with the same group.",
                row=index + 1,
            )
        seen.add(pair)
        item_id = row.id
        if item_id:
            if known_ids is None or item_id not in known_ids or item_id in used_ids:
                raise _refuse(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "unknown_item",
                    f"Item {index + 1} names an id this list does not have.",
                    row=index + 1,
                )
        else:
            item_id = ids.new_item_id()
        used_ids.add(item_id)
        items.append(OptionListItem(id=item_id, label=label, group=group_clean))
    return items


def _name(value: str) -> Tuple[str, str]:
    cleaned = text.clean(value, text.NAME_MAX)
    if cleaned is None:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_name",
            f"A list needs a name of 1 to {text.NAME_MAX} characters.",
        )
    return cleaned, text.fold(cleaned)


class OptionListService:
    def __init__(
        self, list_repo, authorization_service, usage_repo, source_service=None
    ):
        self._repo = list_repo
        self._authorization = authorization_service
        self._usage = usage_repo
        self._sources = source_service

    # ------------------------------------------------------------------ reads

    async def list_lists(
        self, workspace_id: RecordId, user: User
    ) -> List[OptionListSummaryDto]:
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        documents = await self._repo.list_for_workspace(workspace_id)
        usage = await self._usage.forms_by_list(workspace_id)
        return [
            self._summary(document, len(usage.get(str(document.id), ())))
            for document in documents
        ]

    async def get_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        user: User,
        limit: int = PAGE_MAX,
        offset: int = 0,
    ) -> OptionListDto:
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        document = await self._get(workspace_id, list_id)
        usage = (await self._usage.forms_by_list(workspace_id)).get(
            str(document.id), []
        )
        limit = max(1, min(int(limit), PAGE_MAX))
        offset = max(0, int(offset))
        return self._detail(document, document.items[offset : offset + limit], usage)

    async def _get(self, workspace_id, list_id: str) -> OptionListDocument:
        if not isinstance(list_id, str) or not re.fullmatch(r"[0-9a-f]{24}", list_id):
            raise _not_found()
        document = await self._repo.get(workspace_id, list_id)
        if document is None:
            raise _not_found()
        return document

    # ----------------------------------------------------------------- writes

    async def create_list(
        self, workspace_id: RecordId, body: OptionListCreateDto, user: User
    ) -> OptionListDto:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        if not option_sources_enabled():
            raise _refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY, DISABLED_CODE, DISABLED_MESSAGE
            )
        name, name_key = _name(body.name)
        items = clean_items(body.items, None)
        if (
            await self._repo.count_for_workspace(workspace_id)
            >= text.LISTS_PER_WORKSPACE
        ):
            raise _refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "limit_reached",
                f"A workspace holds at most {text.LISTS_PER_WORKSPACE} lists.",
            )
        document = OptionListDocument(
            workspace_id=RecordId(workspace_id),
            name=name,
            name_key=name_key,
            order=body.order,
            items=items,
            revision=1,
            created_by=str(user.id) if getattr(user, "id", None) else None,
            updated_by=str(user.id) if getattr(user, "id", None) else None,
        )
        try:
            document = await self._repo.create(document)
        except NameTaken:
            raise _name_taken()
        self._log("created", workspace_id, document, user)
        return self._detail(document, document.items[:PAGE_MAX], [])

    async def update_list(
        self,
        workspace_id: RecordId,
        list_id: str,
        body: OptionListUpdateDto,
        user: User,
    ) -> OptionListDto:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, list_id)
        if body.name is not None:
            document.name, document.name_key = _name(body.name)
        if body.order is not None:
            document.order = body.order
        if body.items is not None:
            # replacing the items is made against a revision somebody read
            _require_revision(body.expected_revision)
            known = {item.id: item for item in document.items}
            document.items = clean_items(body.items, known)
        return await self._save(workspace_id, document, body.expected_revision, user)

    async def _save(
        self,
        workspace_id,
        document: OptionListDocument,
        expected: Optional[int],
        user: User,
    ) -> OptionListDto:
        document.updated_by = str(user.id) if getattr(user, "id", None) else None
        try:
            document = await self._repo.replace(document, expected)
        except NameTaken:
            raise _name_taken()
        except RevisionChanged:
            raise _refuse(
                HTTPStatus.CONFLICT,
                "list_changed",
                "Someone else changed this list since you opened it. Reload it and "
                "make your change again.",
            )
        except LookupError:
            raise _not_found()
        if self._sources is not None:
            self._sources.forget(workspace_id, str(document.id))
        self._log("updated", workspace_id, document, user)
        usage = (await self._usage.forms_by_list(workspace_id)).get(
            str(document.id), []
        )
        return self._detail(document, document.items[:PAGE_MAX], usage)

    async def delete_list(
        self, workspace_id: RecordId, list_id: str, user: User
    ) -> None:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, list_id)
        usage = (await self._usage.forms_by_list(workspace_id)).get(
            str(document.id), []
        )
        if usage:
            raise _refuse(
                HTTPStatus.CONFLICT,
                "list_in_use",
                "Forms still take their options from this list. Change them first.",
                forms=[
                    {"formId": form_id, "title": title} for form_id, title in usage[:20]
                ],
            )
        await self._repo.delete(workspace_id, document.id)
        if self._sources is not None:
            self._sources.forget(workspace_id, str(document.id))
        self._log("deleted", workspace_id, document, user)

    # -------------------------------------------------------------------- CSV

    async def import_csv(
        self,
        workspace_id: RecordId,
        list_id: str,
        body: bytes,
        user: User,
        expected_revision: Optional[int] = None,
    ) -> OptionListDto:
        """Replace the items with the rows of a CSV (``label``, optional
        ``group`` and ``id``). A row with an id of this list keeps it; a row
        without one that matches an item (same label and group) keeps that
        item's id; the rest are new."""
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, list_id)
        _require_revision(expected_revision)
        if len(body) > CSV_BYTES_MAX:
            raise _refuse(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "file_too_large",
                "The file is larger than 1 MB.",
            )
        rows = parse_csv(body)
        by_pair = {
            (text.fold(i.label), text.fold(i.group) if i.group else ""): i.id
            for i in document.items
        }
        known = {item.id: item for item in document.items}
        dtos = []
        for label, group, item_id in rows:
            if not item_id:
                cleaned = text.clean(label, text.LABEL_MAX)
                group_clean = text.clean(group, text.GROUP_MAX) if group else None
                if cleaned is not None:
                    item_id = by_pair.get(
                        (
                            text.fold(cleaned),
                            text.fold(group_clean) if group_clean else "",
                        )
                    )
            dtos.append(ItemDto(id=item_id or None, label=label, group=group or None))
        document.items = clean_items(dtos, known)
        return await self._save(workspace_id, document, expected_revision, user)

    async def export_csv(self, workspace_id: RecordId, list_id: str, user: User) -> str:
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        document = await self._get(workspace_id, list_id)
        from backend.app.services.response_export.table import csv_line

        lines = [csv_line(["label", "group", "id"])]
        lines.extend(csv_line([i.label, i.group or "", i.id]) for i in document.items)
        return "\r\n".join(lines) + "\r\n"

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _summary(
        document: OptionListDocument, forms_using: int = 0
    ) -> OptionListSummaryDto:
        return OptionListSummaryDto(
            id=str(document.id),
            name=document.name,
            order=document.order,
            item_count=len(document.items),
            revision=document.revision,
            forms_using=forms_using,
            updated_at=document.updated_at,
        )

    def _detail(
        self,
        document: OptionListDocument,
        items: Sequence[OptionListItem],
        usage: Sequence[Tuple[str, Optional[str]]],
    ) -> OptionListDto:
        summary = self._summary(document, len(usage))
        return OptionListDto(
            **summary.model_dump(),
            items=[ItemDto(id=i.id, label=i.label, group=i.group) for i in items],
            total_items=len(document.items),
            used_by=[UsedByDto(form_id=f, title=t) for f, t in usage[:20]],
        )

    @staticmethod
    def _log(
        action: str, workspace_id, document: OptionListDocument, user: User
    ) -> None:
        # ids and counts only, never a label
        logger.info(
            "option list {}: workspace={} list={} actor={} items={} revision={}",
            action,
            workspace_id,
            document.id,
            getattr(user, "id", None),
            len(document.items),
            document.revision,
        )


def _require_revision(expected: Optional[int]) -> None:
    """A change of the items names the revision it was made against: another
    save since is a 409 (``list_changed``), never an overwrite."""
    if expected is None:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "revision_required",
            "Say which revision of the list you changed (expectedRevision).",
        )


def _name_taken() -> HTTPException:
    return _refuse(
        HTTPStatus.CONFLICT, "name_taken", "A list with this name already exists."
    )


def parse_csv(body: bytes) -> List[Tuple[str, str, str]]:
    """``(label, group, id)`` of each data row. UTF-8 (a byte order mark is
    fine); a header row naming ``label`` (and ``group``, ``id``) picks the
    columns, else the columns are label, group, id in that order. At most
    ``ITEMS_PER_LIST`` data rows; empty rows are skipped."""
    try:
        content = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_file",
            "The file is not UTF-8 text.",
        )
    try:
        table = [
            row
            for row in csv.reader(io.StringIO(content, newline=""))
            if any(c.strip() for c in row)
        ]
    except csv.Error:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_file", "The file is not a CSV."
        )
    columns = {"label": 0, "group": 1, "id": 2}
    if table:
        header = [c.strip().lower() for c in table[0]]
        if "label" in header:
            columns = {
                name: header.index(name)
                for name in ("label", "group", "id")
                if name in header
            }
            table = table[1:]
    if len(table) > text.ITEMS_PER_LIST:
        raise _refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "limit_reached",
            f"A list holds at most {text.ITEMS_PER_LIST} items.",
        )

    def cell(row: List[str], name: str) -> str:
        index = columns.get(name)
        value = row[index] if index is not None and index < len(row) else ""
        # a cell an export neutralised (leading apostrophe) reads as it was
        return (
            _GUARDED.sub(lambda m: m.group(1), value, count=1)
            if _GUARDED.match(value)
            else value
        )

    return [
        (cell(row, "label"), cell(row, "group"), cell(row, "id").strip())
        for row in table
    ]
