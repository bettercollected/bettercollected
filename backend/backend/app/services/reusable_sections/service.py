"""A workspace's library of reusable sections. See ``docs/reusable-sections.md``.

Every call names the workspace and every read and write goes through it: a
section of another workspace is a 404, never a 403. Reading needs ``form.read``,
writing, inserting and updating a copy ``form.edit``. While
``REUSABLE_SECTIONS_ENABLED`` is off every call is a 404.

A section holds its questions and layout containers as a form spec fragment
(``fragment.py``), under a version that every content save raises; the
previous versions stay readable (at most ``limits.VERSIONS_KEPT``). Inserting
is a **copy**: ``instantiate`` gives the fragment fresh ids, references remapped
and a marker on each question; the form is then saved by the ordinary builder
save, which applies every server check to the copy. ``update_plan`` matches a
copy's questions to the latest version by the marker's key and keeps the form's
question id where the question is the same and its type unchanged.

Nothing here reads an answer. Logs carry ids and counts, never a title.
"""

import copy
import datetime as dt
import json
import secrets
import uuid
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple, Union

from common.models.user import User
from common.records import RecordId
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.reusable_sections import (
    LimitReached,
    NameTaken,
    VersionChanged,
)
from backend.app.schemas.reusable_section import (
    ReusableSectionDocument,
    SectionVersion,
)
from backend.app.services.option_sources import text
from backend.app.services.reusable_sections import fragment, limits, refs
from backend.app.services.reusable_sections.mode import ensure_enabled

COUNT_CODE = "limit_reached"


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class WarningDto(_Camel):
    code: str
    field_id: Optional[str] = None
    title: Optional[str] = None


class SectionSummaryDto(_Camel):
    id: str
    name: str
    description: Optional[str] = None
    version: int
    question_count: int
    updated_at: Optional[dt.datetime] = None


class SectionDto(SectionSummaryDto):
    """A section with its questions in the builder's shape (a preview, and what
    "Save a copy to the library" is checked against). ``warnings`` is only set
    on the answer to a save."""

    fields: List[Dict[str, Any]] = Field(default_factory=list)
    containers: List[Dict[str, Any]] = Field(default_factory=list)
    versions: List[int] = Field(default_factory=list)
    warnings: List[WarningDto] = Field(default_factory=list)


class SectionCreateDto(_Camel):
    name: str = Field(..., max_length=1000)
    description: Optional[str] = Field(None, max_length=5000)
    fields: List[Dict[str, Any]] = Field(..., max_length=200)
    containers: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)


class SectionContentDto(_Camel):
    fields: List[Dict[str, Any]] = Field(..., max_length=200)
    containers: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    expected_version: Optional[int] = Field(None, ge=1)


class SectionDetailsDto(_Camel):
    name: Optional[str] = Field(None, max_length=1000)
    description: Optional[str] = Field(None, max_length=5000)


class FragmentDto(_Camel):
    """What to put on a page: the questions (marked, with new ids) and the
    containers that group them."""

    section_id: str
    version: int
    instance: str
    fields: List[Dict[str, Any]]
    containers: List[Dict[str, Any]]


class PlanRequestDto(_Camel):
    instance: str = Field(..., min_length=1, max_length=64)
    # the instance's questions as the builder holds them (the page's questions
    # whose marker names this instance, in page order)
    fields: List[Dict[str, Any]] = Field(..., max_length=200)


class ChangeDto(_Camel):
    key: str
    # the question's id in the form (None for one the update adds)
    id: Optional[str] = None
    title: Optional[str] = None
    status: str  # added | removed | changed | unchanged
    # what differs: title, type, required, options, logic, rules, settings
    what: List[str] = Field(default_factory=list)
    # the copy's own question differs from the version it came from
    modified_in_copy: bool = False


class PlanDto(_Camel):
    section_id: str
    version: int
    base_version: Optional[int] = None
    # whether the version the copy came from is still kept (so "changed in the
    # copy" is known)
    base_known: bool = False
    instance: str
    changes: List[ChangeDto]
    fields: List[Dict[str, Any]]
    containers: List[Dict[str, Any]]


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Section not found")


def new_section_id() -> str:
    """An id of a question inside a section: its own, never a form's."""
    return "s" + secrets.token_hex(8)


def _layout_id(kind: str, old: str) -> str:
    return ("t" if kind == "tab" else "c") + secrets.token_hex(6)


def _rule_id(old: str) -> str:
    return "r" + secrets.token_hex(6)


def _details(name: Any, description: Any) -> Tuple[str, str, Optional[str]]:
    cleaned = text.clean(name, limits.NAME_MAX)
    if cleaned is None:
        raise fragment.refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_name",
            f"A section needs a name of 1 to {limits.NAME_MAX} characters.",
        )
    note = None
    if description not in (None, ""):
        note = text.clean(description, limits.DESCRIPTION_MAX)
        if note is None:
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_description",
                f"A description is at most {limits.DESCRIPTION_MAX} characters.",
            )
    return cleaned, text.fold(cleaned), note


# --------------------------------------------------------------- pure helpers


def markers(fields: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``{question id: library marker}`` of the questions that carry one."""
    return {
        str(f["id"]): f["library"]
        for f in refs.questions(fields)
        if isinstance(f.get("library"), dict) and f.get("id")
    }


def _strip_markers(fields: List[Dict[str, Any]]) -> None:
    for field in refs.questions(fields):
        field.pop("library", None)


def _list_ids(fields: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], str]]:
    return [
        (f, str(f["optionSource"]["listId"]))
        for f in refs.questions(fields)
        if isinstance(f.get("optionSource"), dict)
        and f["optionSource"].get("kind") == "list"
        and f["optionSource"].get("listId")
    ]


def instantiate_fragment(
    fields: List[Dict[str, Any]],
    containers: List[Dict[str, Any]],
    *,
    section_id: str,
    version: int,
    instance: str,
    keep: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    """A stored fragment as a copy for a form (pure; the inputs are not
    changed): isolated against its own ids, every question given a new id
    (``keep`` names the ids to give some questions instead: key to form id),
    references remapped, a marker on each question, and checked closed. Returns
    ``(fields, containers, {section id: new id})`` in the spec's shape."""
    work_fields = copy.deepcopy(fields)
    work_containers = copy.deepcopy(containers)
    work_fields, work_containers, _ = refs.isolate(work_fields, work_containers)
    keep = keep or {}
    mapping = {
        old: keep.get(old) or str(uuid.uuid4()) for old in refs.question_ids(work_fields)
    }
    for field in refs.questions(work_fields):
        field["library"] = {
            "sectionId": section_id,
            "version": version,
            "key": str(field["id"]),
            "instance": instance,
        }
    try:
        work_fields, work_containers = refs.remap(
            work_fields,
            work_containers,
            mapping,
            fresh_rule_id=_rule_id,
            layout_id=_layout_id,
        )
        refs.assert_closed(work_fields, work_containers)
    except refs.EscapeError:
        raise fragment.refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "section_reference_escapes",
            "This section refers to something outside itself and cannot be "
            "inserted. Save it to the library again.",
        )
    return work_fields, work_containers, mapping


_SETTINGS_SKIP = {"id", "library", "fields"}


def _rule_content(rules: Any) -> Any:
    """Rules without their ids: a rule's id is made up on every insert (ids are
    unique per form), so two copies of one rule differ only by it."""
    if not isinstance(rules, list):
        return rules
    return [{k: v for k, v in r.items() if k != "id"} if isinstance(r, dict) else r for r in rules]


def _comparable(field: Dict[str, Any]) -> Dict[str, Any]:
    """A question as two versions of it are compared: no ids of its own, no
    marker, no children (those are questions of their own), rules by content."""
    out = {k: v for k, v in field.items() if k not in _SETTINGS_SKIP}
    if "rules" in out:
        out["rules"] = _rule_content(out["rules"])
    return out


def answer_shape(field: Dict[str, Any]) -> Tuple[Any, ...]:
    """What decides how a question's stored answer is shaped: its type, whether
    a group repeats (an answer per item), whether a choice takes several options
    and whether it takes an "other" text. Two questions with the same shape can
    share a question id (answers stored under it stay readable); with another
    shape they cannot."""
    return (
        field.get("type"),
        field.get("repeat") is not None,
        bool(field.get("allowMultipleSelection")),
        bool(field.get("allowOtherChoice")),
    )


def _what_differs(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    """What differs between two questions (ids normalised to section keys)."""
    a, b = _comparable(old), _comparable(new)
    if a == b:
        return []
    what: List[str] = []
    if answer_shape(old) != answer_shape(new):
        what.append("type")
    if a.get("title") != b.get("title"):
        what.append("title")
    if (a.get("validations") or {}).get("required") != (b.get("validations") or {}).get(
        "required"
    ):
        what.append("required")
    if a.get("choices") != b.get("choices") or a.get("optionSource") != b.get(
        "optionSource"
    ):
        what.append("options")
    if a.get("logic") != b.get("logic"):
        what.append("logic")
    if a.get("rules") != b.get("rules") or a.get("expression") != b.get("expression"):
        what.append("rules")
    named = {"type", "title", "validations", "choices", "optionSource", "logic", "rules", "expression"}
    rest_a = {k: v for k, v in a.items() if k not in named}
    rest_b = {k: v for k, v in b.items() if k not in named}
    if rest_a != rest_b or (
        (a.get("validations") or {}).keys() != (b.get("validations") or {}).keys()
        and "required" not in what
    ):
        what.append("settings")
    if not what:
        what.append("settings")
    return what


def _flat(fields: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(f["id"]): f for f in refs.questions(fields) if f.get("id")}


def _in_keys(
    fields: List[Dict[str, Any]],
    containers: List[Dict[str, Any]],
    to_key: Dict[str, str],
) -> List[Dict[str, Any]]:
    """The copy's questions with ids and references rewritten to section keys
    (a deep copy), so they can be compared with a version."""
    work = copy.deepcopy(fields)
    refs.isolate(work, [])  # a reference outside the copy is dropped
    mapping = {i: to_key.get(i, i) for i in refs.question_ids(work)}
    refs.remap(work, [], mapping)
    _strip_markers(work)
    return work


def build_plan(
    document: ReusableSectionDocument,
    instance: str,
    copy_fields: List[Dict[str, Any]],
) -> PlanDto:
    """The diff of a copy against the latest version of the section, and the
    fragment that replaces the copy. ``copy_fields`` are the copy's questions in
    the **spec** shape (ids are the form's)."""
    own = markers(copy_fields)
    if not own:
        raise fragment.refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "not_a_copy",
            "These questions are not a copy of this section.",
        )
    keys: Dict[str, str] = {}  # form id -> key
    form_ids: Dict[str, str] = {}  # key -> form id
    versions = set()
    for form_id, marker in own.items():
        if marker.get("sectionId") != str(document.id) or marker.get("instance") != instance:
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "not_a_copy",
                "These questions are not one copy of this section.",
            )
        key = str(marker["key"])
        if key in form_ids:
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "copy_ambiguous",
                "This copy has a part twice. Remove the extra one, then update.",
            )
        keys[form_id] = key
        form_ids[key] = form_id
        versions.add(int(marker.get("version") or 0))
    base_version = min(versions) if versions else None
    base = None
    if base_version == document.version:
        base = {"fields": document.fields}
    else:
        for entry in document.history:
            if entry.version == base_version:
                base = {"fields": entry.fields}
                break

    library = _flat(document.fields)
    copy_questions = _flat(copy_fields)
    # the copy as section keys, to compare with the versions
    copy_in_keys = _flat(_in_keys(copy_fields, [], keys))
    base_flat = _flat(base["fields"]) if base else {}

    keep: Dict[str, str] = {}
    changes: List[ChangeDto] = []
    for key, library_question in library.items():
        mine = copy_in_keys.get(key)
        if mine is None:
            changes.append(
                ChangeDto(key=key, title=refs.plain_title(library_question), status="added")
            )
            continue
        if answer_shape(mine) != answer_shape(library_question):
            # the id is not kept for another answer shape (a retyped question, a
            # group that now repeats, a choice that now takes several options):
            # answers stored under it were given to a question of another shape
            changes.append(
                ChangeDto(
                    key=key,
                    id=form_ids[key],
                    title=refs.plain_title(copy_questions[form_ids[key]]),
                    status="changed",
                    what=["type"],
                    modified_in_copy=_differs_from_base(mine, base_flat.get(key), base),
                )
            )
            continue
        keep[key] = form_ids[key]
        what = _what_differs(mine, library_question)
        changes.append(
            ChangeDto(
                key=key,
                id=form_ids[key],
                title=refs.plain_title(library_question),
                status="changed" if what else "unchanged",
                what=what,
                modified_in_copy=_differs_from_base(mine, base_flat.get(key), base),
            )
        )
    kept_keys = set(library)
    for key, form_id in form_ids.items():
        if key not in kept_keys:
            changes.append(
                ChangeDto(
                    key=key,
                    id=form_id,
                    title=refs.plain_title(copy_questions[form_id]),
                    status="removed",
                    modified_in_copy=_differs_from_base(
                        copy_in_keys.get(key), base_flat.get(key), base
                    ),
                )
            )
    new_fields, new_containers, _ = instantiate_fragment(
        document.fields,
        document.containers,
        section_id=str(document.id),
        version=document.version,
        instance=instance,
        keep=keep,
    )
    # a retyped question is removed and re-added under a new id: it is in
    # ``replace_ids`` (its old id is not among the kept ones)
    return PlanDto(
        section_id=str(document.id),
        version=document.version,
        base_version=base_version,
        base_known=base is not None,
        instance=instance,
        changes=changes,
        fields=new_fields,
        containers=new_containers,
    )


def _differs_from_base(
    mine: Optional[Dict[str, Any]], base: Optional[Dict[str, Any]], known: Any
) -> bool:
    """Did the copy's creator change this question since it was inserted? Only
    knowable while the version it came from is kept."""
    if known is None or mine is None or base is None:
        return False
    return bool(_what_differs(base, mine))


# -------------------------------------------------------------------- service


class ReusableSectionService:
    def __init__(self, repo, authorization_service, list_repo=None):
        self._repo = repo
        self._authorization = authorization_service
        self._lists = list_repo

    # ------------------------------------------------------------- internals

    async def _get(self, workspace_id, section_id) -> ReusableSectionDocument:
        try:
            RecordId(str(section_id))
        except Exception:  # noqa: BLE001 - not an id: no such section
            raise _not_found()
        document = await self._repo.get(workspace_id, section_id)
        if document is None:
            raise _not_found()
        return document

    def _summary(self, document: ReusableSectionDocument) -> SectionSummaryDto:
        return SectionSummaryDto(
            id=str(document.id),
            name=document.name,
            description=document.description,
            version=document.version,
            question_count=document.question_count,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _summary_row(row: Dict[str, Any]) -> SectionSummaryDto:
        return SectionSummaryDto(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            version=row["version"],
            question_count=row["question_count"],
            updated_at=row["updated_at"],
        )

    def _detail(
        self,
        document: ReusableSectionDocument,
        *,
        version: Optional[int] = None,
        warnings: Optional[List[refs.SectionWarning]] = None,
    ) -> SectionDto:
        fields, containers, number = document.fields, document.containers, document.version
        if version is not None and version != document.version:
            entry = next((v for v in document.history if v.version == version), None)
            if entry is None:
                raise _not_found()
            fields, containers, number = entry.fields, entry.containers, entry.version
        try:
            shown_fields, shown_containers = fragment.to_builder(fields, containers)
        except ValueError:
            # stored content a later change of the form model no longer accepts
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "section_invalid",
                "This section can no longer be shown: it was saved in a shape this "
                "version does not read. Save it again from a form.",
            )
        summary = self._summary(document).model_dump()
        summary["version"] = number
        summary["question_count"] = len(refs.question_ids(fields))
        return SectionDto(
            **summary,
            fields=shown_fields,
            containers=shown_containers,
            versions=sorted(
                [document.version] + [v.version for v in document.history], reverse=True
            ),
            warnings=[WarningDto(**w.as_dict()) for w in warnings or []],
        )

    async def _drop_foreign_lists(
        self,
        workspace_id,
        fields: List[Dict[str, Any]],
        warnings: List[refs.SectionWarning],
    ) -> None:
        """A list source stays only when the list is one of this workspace."""
        known: Dict[str, bool] = {}
        for field, list_id in _list_ids(fields):
            if list_id not in known:
                known[list_id] = (
                    self._lists is not None
                    and await self._lists.revision(workspace_id, list_id) is not None
                )
            if not known[list_id]:
                field["optionSource"] = None
                warnings.append(
                    refs.SectionWarning(
                        refs.LIST_SOURCE_DROPPED,
                        str(field.get("id")),
                        refs.plain_title(field),
                    )
                )

    async def _prepare(
        self,
        workspace_id,
        builder_fields: List[Dict[str, Any]],
        builder_containers: List[Dict[str, Any]],
        *,
        section: Optional[ReusableSectionDocument] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[refs.SectionWarning]]:
        """The builder's questions as the content of a section: the spec
        fragment, references to the outside dropped, ids made the section's own
        (a question that is a copy of this section keeps its key), the shared
        validation applied. Returns the content and the warnings. The size and
        count of what was sent are checked before anything is converted, and the
        conversion runs off the event loop."""
        fragment.precheck(builder_fields, builder_containers)

        def first():
            fields, containers = fragment.from_builder(builder_fields, builder_containers)
            # the marker is a pointer to a library, never part of one's content
            own = markers(fields)
            _strip_markers(fields)
            fields, containers, warnings = refs.isolate(fields, containers)
            return fields, containers, warnings, own

        fields, containers, warnings, own = await run_in_threadpool(first)
        await self._drop_foreign_lists(workspace_id, fields, warnings)

        def second():
            existing = set(refs.question_ids(section.fields)) if section else set()
            mapping: Dict[str, str] = {}
            used: set = set()
            for old in refs.question_ids(fields):
                marker = own.get(old)
                key = str(marker["key"]) if marker else None
                if (
                    section is not None
                    and marker is not None
                    and marker.get("sectionId") == str(section.id)
                    and key in existing
                    and key not in used
                ):
                    mapping[old] = key
                    used.add(key)
            for old in refs.question_ids(fields):
                if old not in mapping:
                    fresh = new_section_id()
                    while fresh in used:
                        fresh = new_section_id()
                    mapping[old] = fresh
                    used.add(fresh)
            # rule ids are the section's own too (a form's are unique per form)
            refs.remap(fields, containers, mapping, fresh_rule_id=_rule_id)
            refs.assert_closed(fields, containers)
            fragment.check_limits(fields, containers)
            fragment.validate(fields, containers)

        await run_in_threadpool(second)
        return fields, containers, warnings

    async def _check_budget(self, workspace_id, fields, containers) -> None:
        """A workspace's library takes at most ``limits.WORKSPACE_BYTES_MAX`` of
        stored content (versions included)."""
        added = len(json.dumps([fields, containers], separators=(",", ":")).encode())
        if await self._repo.content_bytes(workspace_id) + added > limits.WORKSPACE_BYTES_MAX:
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                COUNT_CODE,
                "The library of this workspace is full. Delete a section you no "
                "longer use.",
            )

    # ----------------------------------------------------------------- reads

    async def list_sections(
        self, workspace_id: RecordId, user: User
    ) -> List[SectionSummaryDto]:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        # the columns of the list only: never the questions or the versions
        return [
            self._summary_row(row)
            for row in await self._repo.list_summaries(workspace_id)
        ]

    async def get_section(
        self,
        workspace_id: RecordId,
        section_id: str,
        user: User,
        version: Optional[int] = None,
    ) -> SectionDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        document = await self._get(workspace_id, section_id)
        return self._detail(document, version=version)

    # ---------------------------------------------------------------- writes

    async def create_section(
        self, workspace_id: RecordId, body: SectionCreateDto, user: User
    ) -> SectionDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        name, name_key, description = _details(body.name, body.description)
        fields, containers, warnings = await self._prepare(
            workspace_id, body.fields, body.containers
        )
        document = ReusableSectionDocument(
            workspace_id=workspace_id,
            name=name,
            name_key=name_key,
            description=description,
            version=1,
            fields=fields,
            containers=containers,
            question_count=len(refs.question_ids(fields)),
            created_by=str(user.id),
            updated_by=str(user.id),
        )
        await self._check_budget(workspace_id, fields, containers)
        try:
            saved = await self._repo.create(
                document, max_count=limits.SECTIONS_PER_WORKSPACE
            )
        except NameTaken:
            raise _name_taken()
        except LimitReached:
            raise fragment.refuse(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                COUNT_CODE,
                f"A workspace holds at most {limits.SECTIONS_PER_WORKSPACE} sections.",
            )
        logger.info(
            "reusable section created: workspace={} section={} actor={} questions={} warnings={}",
            workspace_id,
            saved.id,
            user.id,
            saved.question_count,
            len(warnings),
        )
        return self._detail(saved, warnings=warnings)

    async def save_content(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: SectionContentDto,
        user: User,
    ) -> SectionDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, section_id)
        if body.expected_version is not None and body.expected_version != document.version:
            raise _changed()
        fields, containers, warnings = await self._prepare(
            workspace_id, body.fields, body.containers, section=document
        )
        await self._check_budget(workspace_id, fields, containers)
        previous = SectionVersion(
            version=document.version,
            saved_at=document.updated_at,
            saved_by=document.updated_by,
            name=document.name,
            fields=document.fields,
            containers=document.containers,
        )
        expected = document.version
        document.history = ([previous] + list(document.history))[: limits.VERSIONS_KEPT - 1]
        document.version = expected + 1
        document.fields = fields
        document.containers = containers
        document.question_count = len(refs.question_ids(fields))
        document.updated_by = str(user.id)
        try:
            saved = await self._repo.replace(document, expected, bump=True)
        except VersionChanged:
            raise _changed()
        logger.info(
            "reusable section saved: workspace={} section={} actor={} version={} questions={} warnings={}",
            workspace_id,
            saved.id,
            user.id,
            saved.version,
            saved.question_count,
            len(warnings),
        )
        return self._detail(saved, warnings=warnings)

    async def update_details(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: SectionDetailsDto,
        user: User,
    ) -> SectionSummaryDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, section_id)
        sent = body.model_fields_set
        name, name_key, description = _details(
            body.name if "name" in sent and body.name is not None else document.name,
            body.description if "description" in sent else document.description,
        )
        document.name, document.name_key, document.description = name, name_key, description
        document.updated_by = str(user.id)
        try:
            saved = await self._repo.replace(document, None, bump=False)
        except NameTaken:
            raise _name_taken()
        except VersionChanged:  # pragma: no cover - no expected version given
            raise _changed()
        logger.info(
            "reusable section renamed: workspace={} section={} actor={}",
            workspace_id,
            saved.id,
            user.id,
        )
        return self._summary(saved)

    async def delete_section(
        self, workspace_id: RecordId, section_id: str, user: User
    ) -> None:
        """Forms that copied the section are not touched: a copy is ordinary
        questions."""
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        await self._get(workspace_id, section_id)
        await self._repo.delete(workspace_id, section_id)
        logger.info(
            "reusable section deleted: workspace={} section={} actor={}",
            workspace_id,
            section_id,
            user.id,
        )

    # ------------------------------------------------------- insert and update

    async def instantiate(
        self, workspace_id: RecordId, section_id: str, user: User
    ) -> FragmentDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        return await self._fragment(workspace_id, section_id)

    async def fragments_for_ops(
        self, workspace_id: RecordId, wanted: Dict[int, str]
    ) -> Dict[int, Union[FragmentDto, str]]:
        """For the edit operations (``wanted``: op index to section id): a copy
        for each, or the plain reason it cannot be made. The caller has already
        been authorised to edit forms of the workspace (the write path of the
        ops); every section is still read through the workspace, once per
        section however many ops name it, and the copies are made off the event
        loop. A section that is not there (unknown, another workspace's, switch
        off) gets one message that says which of those it is not."""
        gone = (
            "That library section could not be inserted: it does not exist in this "
            "workspace, or reusable sections are not available here."
        )
        try:
            ensure_enabled()
        except HTTPException:
            return {index: gone for index in wanted}
        documents: Dict[str, Optional[ReusableSectionDocument]] = {}
        for section_id in set(wanted.values()):
            try:
                documents[section_id] = await self._get(workspace_id, section_id)
            except HTTPException:
                documents[section_id] = None

        def build() -> Dict[int, Union[FragmentDto, str]]:
            found: Dict[int, Union[FragmentDto, str]] = {}
            checked: Dict[str, Optional[str]] = {}
            for index, section_id in wanted.items():
                document = documents[section_id]
                if document is None:
                    found[index] = gone
                    continue
                try:
                    # the check does not depend on the new ids: once per section
                    found[index] = self._make_fragment(
                        document, validate=section_id not in checked
                    )
                    checked.setdefault(section_id, None)
                except HTTPException as error:
                    # the section is there and the caller may edit forms: say why
                    content = error.content
                    reason = content.get("message") if isinstance(content, dict) else None
                    found[index] = (
                        f"That library section cannot be inserted: {reason}"
                        if reason
                        else gone
                    )
                    checked[section_id] = found[index]  # type: ignore[assignment]
            return found

        return await run_in_threadpool(build)

    async def _fragment(self, workspace_id, section_id: str) -> FragmentDto:
        document = await self._get(workspace_id, section_id)
        return await run_in_threadpool(self._make_fragment, document, True)

    @staticmethod
    def _make_fragment(document: ReusableSectionDocument, validate: bool = True) -> FragmentDto:
        instance = str(uuid.uuid4())
        fields, containers, _ = instantiate_fragment(
            document.fields,
            document.containers,
            section_id=str(document.id),
            version=document.version,
            instance=instance,
        )
        if validate:
            fragment.validate(fields, containers)
        built_fields, built_containers = fragment.to_builder(fields, containers)
        return FragmentDto(
            section_id=str(document.id),
            version=document.version,
            instance=instance,
            fields=built_fields,
            containers=built_containers,
        )

    async def update_plan(
        self,
        workspace_id: RecordId,
        section_id: str,
        body: PlanRequestDto,
        user: User,
    ) -> PlanDto:
        ensure_enabled()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        document = await self._get(workspace_id, section_id)
        fragment.precheck(body.fields, [])

        def compute() -> PlanDto:
            copy_fields, _ = fragment.from_builder(body.fields, [])
            plan = build_plan(document, body.instance, copy_fields)
            fragment.validate(plan.fields, plan.containers)
            plan.fields, plan.containers = fragment.to_builder(plan.fields, plan.containers)
            return plan

        return await run_in_threadpool(compute)


def _name_taken() -> HTTPException:
    return fragment.refuse(
        HTTPStatus.CONFLICT, "name_taken", "A section with this name already exists."
    )


def _changed() -> HTTPException:
    return fragment.refuse(
        HTTPStatus.CONFLICT,
        "section_changed",
        "Someone saved this section since you opened it. Reload it and try again.",
    )
