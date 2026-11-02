"""Importing submissions from a CSV file (docs/response-import.md).

The flow: ``start`` reads an upload and keeps it encrypted; ``check`` and ``run``
queue a background job (the same code, a dry run or the import); ``rollback``
deletes what an import created; the hourly sweep deletes uploads that outlived
their hour and finds jobs that never ran or whose worker died.

* **Who may.** ``response.import`` on the workspace (Owner and Admin), asked
  again by the job. The switch ``CSV_IMPORT_ENABLED`` off: every route is a 404.
* **The file.** Never stored in clear and never past the job: encrypted for the
  workspace, form and import, deleted when the job ends (any outcome), on
  discard, with the form and at the latest ``FILE_TTL`` after the upload.
* **Rows.** Converted and checked by the respondent rules
  (``validation.check_submission``) 100 at a time off the event loop; stored
  through the submission's own encryption. All or nothing: the job checks every
  row first and stores nothing when one fails (unless the importer chose to
  skip invalid rows), and deletes what it stored if it fails half way.
* **Nothing fires.** An import never touches actions, webhooks, registration,
  email actions or notifications.
* **Audit.** The import row: who, form, counts, state, mapping, problems as
  ``{row, column, field, code}``. Never an answer, a file name or a question title.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.response_imports import (
    ImportBusy,
    PostgresResponseImportRepository,
    WorkspaceBusy,
)
from backend.app.schemas.response_import import (
    ImportMode,
    ImportStatus,
    ResponseImportDocument,
    ResponseImportFileDocument,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.form_availability import response_limit
from backend.app.services.internal_fields import validate_internal_answer
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.services.response_import import limits
from backend.app.services.response_import.convert import (
    CellProblem,
    clean,
    convert_cell,
    parse_submitted_at,
)
from backend.app.services.response_import.mode import csv_import_enabled
from backend.app.services.response_import.parser import CsvRefused, ParsedCsv, parse
from backend.app.services.response_import.targets import (
    STATUS_OK,
    Target,
    build_targets,
    group_key,
    suggest_mapping,
)
from backend.app.services.response_import.validation import (
    GROUP_INVALID,
    Problem,
    check_submission,
    known_ids_of,
)
from backend.app.services.retention import submission_expiry
from common.clock import utcnow
from common.ids import RecordId
from common.models.standard_form import StandardFormResponse
from common.models.user import User

FORM_NOT_FOUND = "Form not found in the workspace."
HIDDEN_VALUE_MAX = 1000
# the codes of the problems that belong to the row as a whole
EXTRA_CELLS = "extra_cells"
PAST_RETENTION = "past_retention"
INVALID_ANSWER = "invalid_answer"


def _error(status: HTTPStatus, code: str, message: str, **headers) -> HTTPException:
    return HTTPException(
        status_code=status,
        content={"code": code, "message": message},
        headers=headers or None,
    )


class _Superseded(Exception):
    """Another claim of the job took over (or the import is gone): this run
    stops without touching anything."""


class _Stopped(Exception):
    """The importer's account was deleted while the job ran."""


class _OverBudget(Exception):
    """The job ran past ``limits.JOB_MAX_SECONDS``."""


class _Expired(Exception):
    """The upload's hour is over: the file is held no longer."""


class _Problems:
    """The problems of a run: exact totals per code, the first ``PROBLEMS_LISTED``
    kept as they come (a file of nothing but problems never fills memory)."""

    def __init__(self) -> None:
        self.listed: List[Dict[str, Any]] = []
        self.counts: Dict[str, int] = {}
        self.total = 0

    def add(self, problems: List[Dict[str, Any]]) -> None:
        for problem in problems:
            self.total += 1
            self.counts[problem["code"]] = self.counts.get(problem["code"], 0) + 1
            if len(self.listed) < limits.PROBLEMS_LISTED:
                self.listed.append(problem)

    @property
    def truncated(self) -> bool:
        return self.total > len(self.listed)


def disabled_error() -> HTTPException:
    """A switched-off import answers like a route that does not exist."""
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not Found")


# ------------------------------------------------------------------ one batch


@dataclass
class RowOutcome:
    number: int
    problems: List[Dict[str, Any]] = field(default_factory=list)
    answers: Dict[str, Any] = field(default_factory=dict)
    hidden: Dict[str, str] = field(default_factory=dict)
    internal: Dict[str, Any] = field(default_factory=dict)
    submitted_at: Optional[dt.datetime] = None
    ending_id: Optional[str] = None
    expiration: Optional[Tuple[str, Any]] = None

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class Plan:
    """A validated mapping applied to a form: what each used column fills."""

    columns: List[Tuple[int, Target]]
    published: Any
    draft: Any
    form_id: str
    known_ids: set
    workspace_form_settings: Any = None
    # a comma in a number is a decimal point only in a file separated by ";"
    decimal_comma: bool = False
    # field id (or group key) -> CSV column, to say which cell a problem is in
    column_of_field: Dict[str, int] = field(default_factory=dict)
    column_of_key: Dict[str, int] = field(default_factory=dict)
    group_of_child: Dict[str, str] = field(default_factory=dict)
    first_column_of_group: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def make(
        cls, columns, published, draft, form_id, workspace_form_settings=None, decimal_comma: bool = False
    ) -> "Plan":
        plan = cls(
            columns=columns,
            published=published,
            draft=draft,
            form_id=str(form_id),
            known_ids=known_ids_of(draft, published),
            workspace_form_settings=workspace_form_settings,
            decimal_comma=decimal_comma,
        )
        for index, target in columns:
            plan.column_of_key[target.key] = index
            if target.group_id is not None:
                plan.group_of_child[str(target.field_id)] = target.group_id
                plan.first_column_of_group.setdefault(target.group_id, index)
            elif target.kind == "question" and target.field_id:
                plan.column_of_field[target.field_id] = index
        return plan


def _cell_problem(number: int, column: int, target: Target, code: str) -> Dict[str, Any]:
    problem: Dict[str, Any] = {"row": number, "column": column, "code": code}
    if target.field_id:
        problem["field"] = target.field_id
    return problem


def _column_for(plan: Plan, problem: Problem) -> Optional[int]:
    field_id = problem.field_id
    if field_id is None:
        return None
    group = plan.group_of_child.get(field_id)
    if group is not None and problem.item is not None:
        found = plan.column_of_key.get(group_key(group, problem.item, field_id))
        if found is not None:
            return found
    if field_id in plan.column_of_field:
        return plan.column_of_field[field_id]
    return plan.first_column_of_group.get(field_id)


def process_row(
    number: int,
    cells: List[str],
    plan: Plan,
    now: dt.datetime,
    ragged: bool = False,
) -> RowOutcome:
    """One row: read every mapped cell as an answer, then run the respondent
    checks on the answers. A row with an unreadable cell is not checked further:
    one reported problem per cell is enough."""
    outcome = RowOutcome(number)
    now_iso = now.isoformat()
    if ragged:
        outcome.problems.append({"row": number, "column": None, "code": EXTRA_CELLS})
    groups: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for index, target in plan.columns:
        raw = cells[index] if index < len(cells) else ""
        try:
            if target.key == "submitted_at":
                outcome.submitted_at = parse_submitted_at(raw, now)
                continue
            if target.kind == "hidden":
                text = clean(raw)
                if len(text) > HIDDEN_VALUE_MAX:
                    raise CellProblem("too_long")
                if text:
                    outcome.hidden[target.key.split(":", 1)[1]] = text
                continue
            answer = convert_cell(target.definition, raw, now_iso, plan.decimal_comma)
            if answer is None:
                continue
            if target.kind == "internal":
                try:
                    answer = validate_internal_answer(target.definition, answer)
                except HTTPException:
                    raise CellProblem("invalid_internal") from None
                outcome.internal[str(target.field_id)] = answer
            elif target.group_id is not None:
                groups.setdefault(target.group_id, {}).setdefault(target.item or 0, {})[
                    str(target.field_id)
                ] = answer
            else:
                outcome.answers[str(target.field_id)] = answer
        except CellProblem as problem:
            outcome.problems.append(_cell_problem(number, index, target, problem.code))
    for group_id, items in groups.items():
        listed = [items[i] for i in sorted(items) if items[i]]
        if listed:
            outcome.answers[group_id] = {
                "field": {"id": group_id},
                "type": "group",
                "items": listed,
            }
    if outcome.problems:
        return outcome
    submitted = outcome.submitted_at or now
    expiry = submission_expiry(plan.workspace_form_settings, submitted.astimezone(dt.timezone.utc).replace(tzinfo=None))
    if expiry is not None:
        due = dt.datetime.strptime(expiry[0], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc)
        if due <= now:
            # stored, it would be deleted at once: refused instead
            outcome.problems.append({"row": number, "column": None, "code": PAST_RETENTION})
            return outcome
        outcome.expiration = expiry
    checked = check_submission(
        plan.published,
        plan.draft,
        outcome.answers,
        outcome.hidden,
        form_id=plan.form_id,
        known_ids=plan.known_ids,
    )
    for problem in checked.problems:
        found: Dict[str, Any] = {
            "row": number,
            "column": _column_for(plan, problem),
            "code": problem.rule,
        }
        if problem.field_id:
            found["field"] = problem.field_id
        if problem.item is not None:
            found["item"] = problem.item
        outcome.problems.append(found)
    if not outcome.problems:
        try:
            # the answers must also fit the stored shape (a group item's
            # answers are models: a decimal number is not one)
            StandardFormResponse(answers=checked.answers)
        except ValidationError:
            outcome.problems.append({"row": number, "column": None, "code": INVALID_ANSWER})
            return outcome
        outcome.answers = checked.answers
        outcome.ending_id = checked.ending_id
    return outcome


def process_batch(batch, plan: Plan, now: dt.datetime, ragged) -> List[RowOutcome]:
    return [process_row(number, cells, plan, now, number in ragged) for number, cells in batch]


# ----------------------------------------------------------------- the service


class ResponseImportService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        form_service,
        workspace_form_repo,
        form_response_service,
        response_repo,
        import_repo: PostgresResponseImportRepository,
        crypto,
        rate_limiter: FixedWindowRateLimiter,
        export_service=None,
        schedule_deletion: Optional[Callable[[StandardFormResponse], Awaitable[None]]] = None,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
        enabled: Callable[[], bool] = csv_import_enabled,
    ):
        self._authorization = authorization_service
        self._forms = form_service
        self._workspace_forms = workspace_form_repo
        self._responses = form_response_service
        self._response_repo = response_repo
        self._imports = import_repo
        self._crypto = crypto
        self._limiter = rate_limiter
        self._export_service = export_service
        self._schedule_deletion = schedule_deletion
        self._defer = defer or _defer_job
        self._clock = clock
        self._enabled = enabled

    # ------------------------------------------------------------------ helpers
    def _ensure_enabled(self) -> None:
        if not self._enabled():
            raise disabled_error()

    async def _authorize(self, user: User, workspace_id: RecordId, form_id: Optional[str] = None) -> None:
        """403 without ``response.import``; with ``form_id``, 404 unless that exact
        id is a form of the workspace (never a custom URL: the export's rule)."""
        await self._authorization.authorize(user, Permission.RESPONSE_IMPORT, workspace_id, form_id=form_id)

    async def ensure_allowed(self, workspace_id: RecordId, user: User, form_id: Optional[str] = None) -> None:
        """The switch and the permission, before a body is read."""
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)

    async def _context(self, workspace_id: RecordId, form_id: str):
        """The form an import goes into: ``(workspace form, published version,
        draft)``. 404 for a form of another workspace, 409 for one that is not
        collected here or has never been published."""
        # by the form's own id only: the lookup by id or custom URL would let a
        # custom URL equal to another workspace's form id reach that form
        workspace_form = await self._workspace_forms.find_workspace_form(workspace_id, str(form_id))
        if workspace_form is None or str(workspace_form.form_id) != str(form_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, FORM_NOT_FOUND)
        form_id = str(workspace_form.form_id)
        draft = await self._forms.get_form_document_by_id(form_id)
        if draft is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, FORM_NOT_FOUND)
        provider = getattr(getattr(workspace_form, "settings", None), "provider", None)
        if provider != "self":
            raise _error(
                HTTPStatus.CONFLICT,
                "form_not_importable",
                "Responses can only be imported into a form collected here.",
            )
        published = await self._forms.get_latest_version_of_form(form_id=RecordId(form_id))
        if published is None:
            raise _error(
                HTTPStatus.CONFLICT,
                "form_not_published",
                "Publish the form before importing responses.",
            )
        return workspace_form, published, draft

    @staticmethod
    def _dump(form) -> Dict[str, Any]:
        return form.model_dump(mode="json", exclude_none=True)

    def _targets(self, published, draft) -> List[Target]:
        return build_targets(self._dump(published), self._dump(draft))

    @staticmethod
    def _context_bytes(import_id) -> bytes:
        """The extra context both ciphertexts of an import are bound to. It names
        only the import: the workspace and the form are bound by the crypto
        service's own arguments (the key is derived from them), so a row copied
        to another import, workspace or form does not decrypt."""
        return b"import-file|" + str(import_id).encode()

    def _seal(self, document: ResponseImportDocument, data: bytes) -> str:
        sealed = self._crypto.encrypt(
            document.workspace_id,
            document.form_id,
            data,
            context=self._context_bytes(document.id),
        )
        return base64.b64encode(sealed).decode()

    def _unseal(self, document: ResponseImportDocument, sealed: str) -> bytes:
        return self._crypto.decrypt(
            document.workspace_id,
            document.form_id,
            base64.b64decode(sealed),
            context=self._context_bytes(document.id),
        )

    def _seal_headers(self, document: ResponseImportDocument, headers: List[str]) -> str:
        sealed = self._crypto.encrypt(
            document.workspace_id,
            document.form_id,
            json.dumps(headers).encode(),
            context=b"import-headers|" + str(document.id).encode(),
        )
        return base64.b64encode(sealed).decode()

    async def _headers_of(self, document: ResponseImportDocument) -> List[str]:
        """The file's heading cells while its file waits, read from the encrypted
        file (never kept on the import row); none once the file is gone."""
        if not document.status.has_file:
            return []
        file = await self._imports.get_file(document.id)
        if file is None or not file.headers_sealed:
            return []
        try:
            plain = self._crypto.decrypt(
                document.workspace_id,
                document.form_id,
                base64.b64decode(file.headers_sealed),
                context=b"import-headers|" + str(document.id).encode(),
            )
            found = json.loads(plain)
        except Exception:  # noqa: BLE001 - the screens show "column N" instead
            return []
        return [h for h in found if isinstance(h, str)] if isinstance(found, list) else []

    async def _mine(self, workspace_id, form_id, import_id) -> ResponseImportDocument:
        found = await self._imports.get(workspace_id, str(form_id), import_id)
        if found is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Import not found.")
        return await self._expire_if_due(found)

    async def _expire_if_due(self, document: ResponseImportDocument) -> ResponseImportDocument:
        if (
            document.status in (ImportStatus.UPLOADED, ImportStatus.CHECKED)
            and document.expires_at is not None
            and document.expires_at <= self._clock()
        ):
            updated = await self._end_waiting(document.id, ImportStatus.EXPIRED)
            return updated or document
        return document

    async def _end_waiting(self, import_id, status: ImportStatus) -> Optional[ResponseImportDocument]:
        """End an import that waits for the importer (uploaded or checked):
        its file goes with it."""

        def change(document: ResponseImportDocument):
            if document.status not in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
                return None
            document.status = status
            document.finished_at = self._clock()
            document.expires_at = None
            return document

        updated = await self._imports.update_locked(import_id, change)
        if updated is not None:
            await self._imports.delete_file(import_id)
        return updated

    # ----------------------------------------------------------------- presenting
    def present(
        self,
        document: ResponseImportDocument,
        user: User,
        targets: Optional[List[Target]] = None,
        headers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """The import as the API shows it (camelCase)."""
        window_end = (
            document.finished_at + limits.ROLLBACK_WINDOW
            if document.status == ImportStatus.COMPLETED and document.finished_at
            else None
        )
        view: Dict[str, Any] = {
            "id": str(document.id),
            "formId": document.form_id,
            "status": document.status.value,
            "mode": document.mode.value if document.mode else None,
            "fileSize": document.file_size,
            "encoding": document.encoding,
            "separator": document.separator,
            "rowCount": document.row_count,
            "columnCount": document.column_count,
            "headers": headers or [],
            "mapping": document.mapping,
            "options": document.options,
            "rowsValid": document.rows_valid,
            "rowsInvalid": document.rows_invalid,
            "rowsImported": document.rows_imported,
            "rowsSkipped": document.rows_skipped,
            "problems": document.problems,
            "problemCounts": document.problem_counts,
            "problemsTruncated": document.problems_truncated,
            "notes": document.notes,
            "progress": document.progress,
            "errorCode": document.error_code,
            "byMe": str(document.actor_id) == str(user.id),
            "createdAt": document.created_at,
            "checkedAt": document.checked_at,
            "finishedAt": document.finished_at,
            "expiresAt": document.expires_at,
            "rolledBackAt": document.rolled_back_at,
            "rolledBackCount": document.rolled_back_count,
            "canRollback": bool(window_end and window_end > self._clock()),
            "rollbackUntil": window_end,
        }
        if targets is not None:
            view["targets"] = [
                {
                    "key": t.key,
                    "label": t.label,
                    "kind": t.kind,
                    "status": t.status,
                    "reason": t.reason,
                    "fieldId": t.field_id,
                    "type": (t.definition or {}).get("type") if t.kind != "hidden" else None,
                    "groupId": t.group_id,
                    "item": t.item,
                }
                for t in targets
            ]
        return view

    # ---------------------------------------------------------------------- routes
    async def start(self, workspace_id: RecordId, form_id: str, user: User, data: bytes) -> Dict[str, Any]:
        """Take an upload: read it, keep it encrypted and answer with what was
        found and the mapping suggested. 404 while the switch is off, 403
        without ``response.import``, 413/415/422 for a file that cannot be
        imported (a code, never a value from it), 429 over the rate limit."""
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        _, published, draft = await self._context(workspace_id, form_id)
        await self._take_rate_limit(workspace_id, form_id, str(user.id))
        await self._take_workspace_upload_limit(workspace_id)
        try:
            parsed = await run_in_threadpool(parse, data)
        except CsvRefused as refused:
            raise self._refusal(refused) from None
        # an upload the importer left unused is replaced by this one; one a
        # worker is on blocks it (one live import per form)
        for waiting in await self._imports.waiting_files_of_form(workspace_id, form_id):
            if str(waiting.actor_id) == str(user.id):
                await self._end_waiting(waiting.id, ImportStatus.DISCARDED)
        targets = self._targets(published, draft)
        mapping, notes = suggest_mapping(parsed.headers, targets)
        now = self._clock()
        document = ResponseImportDocument(
            workspace_id=workspace_id,
            form_id=str(form_id),
            actor_id=str(user.id),
            status=ImportStatus.UPLOADED,
            file_size=len(data),
            encoding=parsed.encoding,
            separator=parsed.separator,
            row_count=len(parsed.rows),
            column_count=len(parsed.headers),
            form_version=getattr(published, "version", None),
            mapping=mapping,
            notes=notes,
            expires_at=now + limits.FILE_TTL,
        ).ensure_id()
        await self._imports.save(document)
        try:
            await self._imports.save_file(
                ResponseImportFileDocument(
                    import_id=str(document.id),
                    workspace_id=workspace_id,
                    form_id=str(form_id),
                    data=await run_in_threadpool(self._seal, document, data),
                    headers_sealed=self._seal_headers(document, parsed.headers),
                )
            )
        except BaseException:
            await self._imports.delete_by_id(document.id)
            raise
        return self.present(document, user, targets, parsed.headers)

    def _refusal(self, refused: CsvRefused) -> HTTPException:
        status = {
            "too_large": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "too_many_rows": HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "unsupported_format": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        }.get(refused.code, HTTPStatus.UNPROCESSABLE_ENTITY)
        content: Dict[str, Any] = {"code": refused.code, "message": "This file cannot be imported."}
        if refused.row:
            content["row"] = refused.row
        return HTTPException(status_code=status, content=content)

    async def _take_rate_limit(self, workspace_id: RecordId, form_id: str, actor_id: str) -> None:
        verdict = await self._limiter.admit(
            f"response-import:{workspace_id}:{form_id}",
            actor_id,
            limits.UPLOADS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                f"Too many imports of this form. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )

    async def _take_workspace_upload_limit(self, workspace_id: RecordId) -> None:
        """Uploads are limited per workspace too, whoever uploads."""
        verdict = await self._limiter.admit(
            f"response-import-workspace:{workspace_id}",
            "workspace",
            limits.WORKSPACE_UPLOADS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "workspace_rate_limited",
                f"Too many imports in this workspace. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )

    async def _take_run_limit(self, workspace_id: RecordId, form_id: str, actor_id: str) -> None:
        """Checks and runs of a form's imports are limited per person too."""
        verdict = await self._limiter.admit(
            f"response-import-run:{workspace_id}:{form_id}",
            actor_id,
            limits.RUNS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                f"Too many checks of this form's imports. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )

    async def get(self, workspace_id: RecordId, form_id: str, import_id: str, user: User) -> Dict[str, Any]:
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        document = await self._mine(workspace_id, form_id, import_id)
        targets = None
        if document.status in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
            _, published, draft = await self._context(workspace_id, form_id)
            targets = self._targets(published, draft)
        return self.present(document, user, targets, await self._headers_of(document))

    async def recent(self, workspace_id: RecordId, form_id: str, user: User) -> List[Dict[str, Any]]:
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        rows = await self._imports.list_for_form(workspace_id, str(form_id))
        out = []
        for row in rows:
            if row.status == ImportStatus.DISCARDED:
                continue
            out.append(self.present(await self._expire_if_due(row), user))
        return out

    def _validated_mapping(self, raw: Dict[str, str], targets: List[Target], column_count: int) -> Dict[str, str]:
        by_key = {t.key: t for t in targets}
        mapping: Dict[str, str] = {}
        used: set = set()
        for column, key in (raw or {}).items():
            if key in (None, ""):
                continue
            if not str(column).isdigit() or int(column) >= column_count:
                raise _error(HTTPStatus.UNPROCESSABLE_ENTITY, "unknown_column", "A mapped column is not in the file.")
            target = by_key.get(key)
            if target is None:
                raise _error(HTTPStatus.UNPROCESSABLE_ENTITY, "unknown_target", "A mapped target is not in this form.")
            if target.status != STATUS_OK:
                raise _error(
                    HTTPStatus.UNPROCESSABLE_ENTITY, "target_not_importable", "A mapped target cannot be imported."
                )
            if key in used:
                raise _error(HTTPStatus.UNPROCESSABLE_ENTITY, "duplicate_target", "Two columns are mapped to one question.")
            used.add(key)
            mapping[str(int(column))] = key
        if not any(by_key[k].kind in ("question", "internal", "hidden") for k in used):
            raise _error(HTTPStatus.UNPROCESSABLE_ENTITY, "no_mapping", "Map at least one column to a question.")
        return mapping

    async def _start_job(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        user: User,
        mapping: Dict[str, str],
        options: Dict[str, Any],
        mode: ImportMode,
        confirmed: bool,
    ) -> Dict[str, Any]:
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        document = await self._mine(workspace_id, form_id, import_id)
        if document.status not in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
            if document.status.busy:
                raise _error(HTTPStatus.CONFLICT, "import_in_progress", "This import is already being processed.")
            raise _error(HTTPStatus.CONFLICT, "not_ready", "This import can no longer be run.")
        if mode == ImportMode.IMPORT and not confirmed:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "needs_confirmation",
                "Confirm that you may store this data before importing it.",
            )
        _, published, draft = await self._context(workspace_id, form_id)
        targets = self._targets(published, draft)
        checked_mapping = self._validated_mapping(mapping, targets, document.column_count)
        await self._take_run_limit(workspace_id, form_id, str(user.id))
        now = self._clock()

        def change(row: ResponseImportDocument):
            if row.status not in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
                return None
            row.status = ImportStatus.CHECKING if mode == ImportMode.CHECK else ImportStatus.QUEUED
            row.mode = mode
            row.mapping = checked_mapping
            row.options = {"skipInvalidRows": bool(options.get("skipInvalidRows"))}
            row.form_version = getattr(published, "version", None)
            if mode == ImportMode.IMPORT:
                row.confirmed_at = now
                row.confirmed_by = str(user.id)
            row.rows_valid = row.rows_invalid = row.rows_imported = row.rows_skipped = None
            row.problems, row.problem_counts, row.problems_truncated = [], {}, False
            row.progress = 0
            row.attempts = 0
            row.started_at = row.heartbeat_at = row.finished_at = None
            row.error_code = None
            # the file's hour runs from the upload (set once there): a check or a
            # run never extends it
            return row

        try:
            admitted = await self._imports.admit(import_id, change, limits.WORKSPACE_MAX_JOBS)
        except ImportBusy:
            raise _error(HTTPStatus.CONFLICT, "import_in_progress", "An import of this form is already being processed.") from None
        except WorkspaceBusy:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "workspace_busy",
                "Several imports of this workspace are being processed. Try again in a few minutes.",
                **{"Retry-After": "60"},
            ) from None
        if admitted is None:
            raise _error(HTTPStatus.CONFLICT, "not_ready", "This import can no longer be run.")
        await self._queue(admitted)
        return self.present(admitted, user, headers=await self._headers_of(admitted))

    async def check(self, workspace_id, form_id, import_id, user, mapping, options=None) -> Dict[str, Any]:
        """Queue a dry run: every row is read and checked, nothing is stored."""
        return await self._start_job(
            workspace_id, form_id, import_id, user, mapping, options or {}, ImportMode.CHECK, False
        )

    async def run(
        self, workspace_id, form_id, import_id, user, mapping, options=None, confirmed: bool = False
    ) -> Dict[str, Any]:
        """Queue the import. ``confirmed``: the importer said they may store this data."""
        return await self._start_job(
            workspace_id, form_id, import_id, user, mapping, options or {}, ImportMode.IMPORT, confirmed
        )

    async def discard(self, workspace_id, form_id, import_id, user) -> None:
        """Throw an upload away before an import ran (its file is deleted)."""
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        document = await self._mine(workspace_id, form_id, import_id)
        if document.status.busy:
            raise _error(HTTPStatus.CONFLICT, "import_in_progress", "This import is being processed.")
        if document.status in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
            await self._end_waiting(document.id, ImportStatus.DISCARDED)

    async def rollback(self, workspace_id, form_id, import_id, user) -> Dict[str, Any]:
        """Delete the responses an import created, within ``ROLLBACK_WINDOW`` of
        its end: a completed import, or a failed or cancelled one whose own
        cleanup could not delete what it had stored (``undo_pending``). 409
        ``not_rollbackable`` for any other, ``rollback_expired`` past the window.
        The delete comes first and is idempotent, the status flips after it: a
        failure in between leaves the import as it was, to be undone again."""
        self._ensure_enabled()
        await self._authorize(user, workspace_id, form_id)
        document = await self._mine(workspace_id, form_id, import_id)
        stray = document.status in (ImportStatus.FAILED, ImportStatus.CANCELLED) and document.undo_pending
        if document.status != ImportStatus.COMPLETED and not stray:
            raise _error(HTTPStatus.CONFLICT, "not_rollbackable", "Only a completed import can be undone.")
        if document.finished_at is None or document.finished_at + limits.ROLLBACK_WINDOW <= self._clock():
            raise _error(HTTPStatus.CONFLICT, "rollback_expired", "This import can no longer be undone.")
        now = self._clock()
        deleted = await self._delete_rows(workspace_id, form_id, document.id, forget_exports=True)

        def done(row: ResponseImportDocument):
            if row.status == ImportStatus.COMPLETED:
                row.status = ImportStatus.ROLLED_BACK
                row.rolled_back_by = str(user.id)
                row.rolled_back_at = now
                row.rolled_back_count = deleted
                return row
            if row.status in (ImportStatus.FAILED, ImportStatus.CANCELLED) and row.undo_pending:
                # the failed import stays failed; its stray rows are gone
                row.undo_pending = False
                row.rolled_back_by = str(user.id)
                row.rolled_back_at = now
                row.rolled_back_count = deleted
                return row
            return None

        final = await self._imports.update_locked(document.id, done)
        if final is None:
            raise _error(HTTPStatus.CONFLICT, "not_rollbackable", "Only a completed import can be undone.")
        logger.info("response import {} rolled back ({} responses)", document.id, deleted)
        return self.present(final, user)

    # ------------------------------------------------------------------- queueing
    async def _queue(self, document: ResponseImportDocument) -> bool:
        try:
            await self._defer(str(document.id))
            return True
        except Exception as error:  # noqa: BLE001 - the sweep queues it again
            logger.warning("could not queue response import {} ({})", document.id, type(error).__name__)
            return False

    # ------------------------------------------------------------------------ job
    async def run_job(self, import_id: str) -> str:
        """The job: a dry run or the import, as the row says. Returns the
        status the import ended in. Never raises for a failed run: the row says
        so. A run owns the import only while its claim (``attempts``) is current."""
        claimed = await self._imports.update_locked(import_id, self._claim)
        if claimed is None:
            found = await self._imports.get_by_id(import_id)
            return found.status.value if found else "missing"
        try:
            outcome = await self._process(claimed)
        except _Superseded:
            found = await self._imports.get_by_id(import_id)
            return found.status.value if found else "missing"
        except _Expired:
            logger.warning("response import {} ran past its file's hour", import_id)
            outcome = await self._fail(claimed, "expired", rollback=True)
        except _OverBudget:
            logger.warning("response import {} ran past its time budget", import_id)
            outcome = await self._fail(claimed, "time_budget", rollback=True)
        except Exception as error:  # noqa: BLE001
            logger.warning("response import {} failed ({})", import_id, type(error).__name__)
            outcome = await self._fail(claimed, "build_failed", rollback=True)
        return outcome.value

    def _claim(self, document: ResponseImportDocument):
        stale = self._clock() - limits.STALE_RUNNING_AFTER
        now = self._clock()
        if document.status == ImportStatus.QUEUED:
            document.status = ImportStatus.RUNNING
        elif document.status == ImportStatus.CHECKING and document.started_at is None:
            pass
        elif document.status in (ImportStatus.RUNNING, ImportStatus.CHECKING) and (
            (document.heartbeat_at or document.started_at) is not None
            and (document.heartbeat_at or document.started_at) < stale
        ):
            pass
        else:
            return None
        document.started_at = now
        document.heartbeat_at = now
        document.attempts += 1
        return document

    def _owned(self, document: ResponseImportDocument, attempt: int) -> bool:
        return (
            document.status in (ImportStatus.RUNNING, ImportStatus.CHECKING)
            and document.attempts == attempt
        )

    async def _beat(self, import_id, attempt: int, progress: int) -> None:
        """Show the run is alive (and how far it is); stops it when it no
        longer owns the import or the importer's account was deleted."""
        stopped: List[str] = []

        def change(document: ResponseImportDocument):
            if not self._owned(document, attempt):
                stopped.append("lost")
                return None
            if document.invalidated_at is not None:
                stopped.append("invalidated")
                return None
            document.heartbeat_at = self._clock()
            document.progress = progress
            return document

        updated = await self._imports.update_locked(import_id, change)
        if updated is None:
            if stopped and stopped[0] == "invalidated":
                raise _Stopped()
            raise _Superseded()

    async def _finish_file(self, import_id) -> None:
        await self._imports.delete_file(import_id)

    async def _end(
        self,
        document: ResponseImportDocument,
        status: ImportStatus,
        error_code: Optional[str] = None,
        keep_file: bool = False,
        **fields: Any,
    ) -> ImportStatus:
        """End the run as ``status`` if it still owns the import; the upload goes
        with it unless the import goes on (a finished dry run)."""
        attempt = document.attempts

        def change(row: ResponseImportDocument):
            if not self._owned(row, attempt):
                return None
            row.status = status
            row.error_code = error_code
            row.finished_at = self._clock()
            if status == ImportStatus.CHECKED:
                row.checked_at = row.finished_at
                row.finished_at = None
            for key, value in fields.items():
                setattr(row, key, value)
            if not keep_file:
                row.expires_at = None
            return row

        updated = await self._imports.update_locked(document.id, change)
        if updated is None:
            raise _Superseded()
        if not keep_file:
            await self._finish_file(document.id)
        return updated.status

    def _check_budget(self, started: dt.datetime, expires_at: Optional[dt.datetime] = None) -> None:
        now = self._clock()
        # the file's hour is absolute: a job running past it stops, whatever its state
        if expires_at is not None and now >= expires_at:
            raise _Expired()
        if now - started > dt.timedelta(seconds=limits.JOB_MAX_SECONDS):
            raise _OverBudget()

    async def _fail(self, document: ResponseImportDocument, code: str, rollback: bool = False, **fields) -> ImportStatus:
        if rollback and document.mode == ImportMode.IMPORT:
            await self._undo(document)
        try:
            return await self._end(document, ImportStatus.FAILED, code, **fields)
        except _Superseded:
            found = await self._imports.get_by_id(document.id)
            return found.status if found else ImportStatus.FAILED

    async def _delete_rows(self, workspace_id, form_id, import_id, forget_exports: bool = False) -> int:
        """Delete the responses an import created, in the form and workspace only
        (the one place that does: an undo, a retry's clean start, a failed job's
        cleanup, an expiry). Idempotent. ``forget_exports``: stored export files
        of the form go too (responses of it were deleted). Raises on failure."""
        scope = await self._responses.scope(workspace_id, [str(form_id)])
        deleted = await self._response_repo.delete_imported(scope, str(import_id))
        if forget_exports and self._export_service is not None:
            await self._export_service.forget_files_of_form(workspace_id, str(form_id))
        return deleted

    async def _undo(self, document: ResponseImportDocument) -> bool:
        """Delete whatever this import stored (it stores all or nothing). When
        the delete fails the import is marked ``undo_pending``: the sweep and the
        undo try again, so rows never stay behind unseen. True when it worked."""
        try:
            await self._delete_rows(document.workspace_id, document.form_id, document.id)
            return True
        except Exception as error:  # noqa: BLE001 - the failure is recorded either way
            logger.error("could not undo response import {} ({})", document.id, type(error).__name__)

            def mark(row: ResponseImportDocument):
                row.undo_pending = True
                return row

            try:
                await self._imports.update_locked(document.id, mark, touch=False)
            except Exception:  # noqa: BLE001 - the log line above is all that is left
                logger.error("could not mark response import {} as needing an undo", document.id)
            return False

    async def retry_pending_undos(self) -> int:
        """Delete again the rows of failed or cancelled imports whose cleanup
        failed. Counts only."""
        done = 0
        for row in await self._imports.list_undo_pending():
            try:
                await self._delete_rows(row.workspace_id, row.form_id, row.id, forget_exports=True)
            except Exception as error:  # noqa: BLE001 - the next sweep tries again
                logger.error("could not undo response import {} again ({})", row.id, type(error).__name__)
                continue

            def clear(document: ResponseImportDocument):
                if not document.undo_pending:
                    return None
                document.undo_pending = False
                return document

            await self._imports.update_locked(row.id, clear, touch=False)
            done += 1
        return done

    def _check_budget(self, started: dt.datetime, expires_at: Optional[dt.datetime] = None) -> None:
        now = self._clock()
        # the file's hour is absolute: a job running past it stops, whatever its state
        if expires_at is not None and now >= expires_at:
            raise _Expired()
        if now - started > dt.timedelta(seconds=limits.JOB_MAX_SECONDS):
            raise _OverBudget()

    async def _fail(self, document: ResponseImportDocument, code: str, rollback: bool = False, **fields) -> ImportStatus:
        if rollback and document.mode == ImportMode.IMPORT:
            await self._undo(document)
        try:
            return await self._end(document, ImportStatus.FAILED, code, **fields)
        except _Superseded:
            found = await self._imports.get_by_id(document.id)
            return found.status if found else ImportStatus.FAILED

    async def _process(self, document: ResponseImportDocument) -> ImportStatus:
        import_id, workspace_id, form_id = document.id, document.workspace_id, document.form_id
        attempt = document.attempts
        started = self._clock()
        if document.mode == ImportMode.IMPORT and attempt > 1:
            # a run presumed dead may have stored rows: this run starts clean,
            # before it can end any other way (a cancelled retry would leave them)
            await self._undo(document)
        if not self._enabled():
            return await self._end(document, ImportStatus.CANCELLED, "switched_off")
        # an import runs on its confirmer's permission (who pressed Import, not
        # who uploaded the file); a dry run on the uploader's
        who = (document.confirmed_by if document.mode == ImportMode.IMPORT else None) or document.actor_id
        actor = User(id=who, sub=who)
        # who asked may no longer be allowed (a role removed since)
        if not await self._authorization.has_permission(actor, Permission.RESPONSE_IMPORT, workspace_id):
            return await self._end(document, ImportStatus.CANCELLED, "permission_removed")
        file = await self._imports.get_file(import_id)
        if file is None:
            return await self._end(document, ImportStatus.FAILED, "file_gone")
        try:
            workspace_form, published, draft = await self._context(workspace_id, form_id)
        except HTTPException:
            return await self._end(document, ImportStatus.CANCELLED, "form_gone")
        data = await run_in_threadpool(self._unseal, document, file.data)
        try:
            parsed = await run_in_threadpool(parse, data)
        except CsvRefused:
            return await self._end(document, ImportStatus.FAILED, "file_unreadable")
        targets = self._targets(published, draft)
        by_key = {t.key: t for t in targets}
        columns: List[Tuple[int, Target]] = []
        for column, key in sorted(document.mapping.items(), key=lambda kv: int(kv[0])):
            target = by_key.get(key)
            if target is None or target.status != STATUS_OK or int(column) >= len(parsed.headers):
                # the form changed since the mapping was made
                return await self._end(document, ImportStatus.FAILED, "form_changed")
            columns.append((int(column), target))
        plan = Plan.make(
            columns,
            published,
            draft,
            form_id,
            getattr(workspace_form, "settings", None),
            decimal_comma=parsed.separator == ";",
        )
        skip = bool(document.options.get("skipInvalidRows"))
        now = self._clock()

        log = _Problems()
        valid = 0
        invalid_rows = 0
        total = len(parsed.rows)
        last_beat = self._clock()
        for start in range(0, total, limits.BATCH_SIZE):
            batch = parsed.rows[start : start + limits.BATCH_SIZE]
            outcomes = await run_in_threadpool(process_batch, batch, plan, now, parsed.ragged)
            for outcome in outcomes:
                if outcome.ok:
                    valid += 1
                else:
                    invalid_rows += 1
                    log.add(outcome.problems)
            self._check_budget(started, document.expires_at)
            if self._clock() - last_beat >= limits.HEARTBEAT_EVERY:
                last_beat = self._clock()
                await self._beat(import_id, attempt, start + len(batch))
        listed, counts, truncated = log.listed, log.counts, log.truncated

        if document.mode == ImportMode.CHECK:
            return await self._end(
                document,
                ImportStatus.CHECKED,
                None,
                keep_file=True,
                rows_valid=valid,
                rows_invalid=invalid_rows,
                problems=listed,
                problem_counts=counts,
                problems_truncated=truncated,
                progress=total,
            )
        if invalid_rows and not skip:
            return await self._end(
                document,
                ImportStatus.FAILED,
                "validation_failed",
                rows_valid=valid,
                rows_invalid=invalid_rows,
                rows_imported=0,
                problems=listed,
                problem_counts=counts,
                problems_truncated=truncated,
            )
        if valid == 0:
            return await self._end(
                document,
                ImportStatus.FAILED,
                "nothing_to_import",
                rows_valid=0,
                rows_invalid=invalid_rows,
                rows_imported=0,
                problems=listed,
                problem_counts=counts,
                problems_truncated=truncated,
            )
        return await self._store(
            document, parsed, plan, workspace_form, published, now, valid, invalid_rows, listed, counts, truncated, started
        )

    async def _store(
        self, document, parsed: ParsedCsv, plan: Plan, workspace_form, published, now, valid, invalid_rows,
        listed, counts, truncated, started,
    ) -> ImportStatus:
        import_id, workspace_id, form_id = document.id, document.workspace_id, document.form_id
        attempt = document.attempts
        settings = getattr(workspace_form, "settings", None)
        limit = response_limit(settings)
        scope = await self._responses.scope(workspace_id, [form_id])
        version = getattr(published, "version", None)
        stored = 0
        skipped = 0
        scheduled: List[StandardFormResponse] = []
        try:
            for start in range(0, len(parsed.rows), limits.BATCH_SIZE):
                batch = parsed.rows[start : start + limits.BATCH_SIZE]
                outcomes = await run_in_threadpool(process_batch, batch, plan, now, parsed.ragged)
                self._check_budget(started, document.expires_at)
                await self._beat(import_id, attempt, start)
                for outcome in outcomes:
                    if not outcome.ok:
                        if document.options.get("skipInvalidRows"):
                            skipped += 1
                            continue
                        # the form changed since the check, between two passes
                        await self._undo(document)
                        return await self._end(document, ImportStatus.FAILED, "validation_failed")
                    response = self._build_response(outcome, document, version, now)
                    saved = await self._response_repo.save_form_response(
                        form_id=RecordId(form_id),
                        response=response,
                        workspace_id=workspace_id,
                        response_limit=limit,
                        scope=scope if limit is not None else None,
                        submitted_at=outcome.submitted_at or now,
                        internal_answers=outcome.internal or None,
                    )
                    stored += 1
                    if outcome.expiration is not None:
                        saved_copy = StandardFormResponse(
                            response_id=saved.response_id, expiration=outcome.expiration[0]
                        )
                        scheduled.append(saved_copy)
        except HTTPException as refused:
            await self._undo(document)
            body = getattr(refused, "content", None)
            code = body.get("code") if isinstance(body, dict) else None
            return await self._end(
                document,
                ImportStatus.FAILED,
                "form_full" if code == "form_full" else "store_failed",
                rows_valid=valid,
                rows_imported=0,
            )
        except _Stopped:
            await self._undo(document)
            raise
        # (a run that lost its claim, ``_Superseded``, deletes nothing: the run
        # that took over starts by clearing what the earlier one stored, and
        # the check below catches a late write of the earlier one)
        # exactly what this run stored must be what is there: a run that lost
        # its claim may still have written a batch after the new run cleared
        if await self._response_repo.count_imported(scope, str(import_id)) != stored:
            await self._undo(document)
            return await self._end(document, ImportStatus.FAILED, "store_failed")
        # expiry timers go only once everything is stored, so an undone import
        # leaves none behind
        if self._schedule_deletion is not None:
            for item in scheduled:
                try:
                    await self._schedule_deletion(item)
                except Exception as error:  # noqa: BLE001 - never fail a stored import
                    logger.error("could not schedule an expiry ({})", type(error).__name__)
        return await self._end(
            document,
            ImportStatus.COMPLETED,
            None,
            rows_valid=valid,
            rows_invalid=invalid_rows,
            rows_imported=stored,
            rows_skipped=skipped,
            problems=listed,
            problem_counts=counts,
            problems_truncated=truncated,
            progress=len(parsed.rows),
        )

    def _build_response(self, outcome: RowOutcome, document, version, now) -> StandardFormResponse:
        response = StandardFormResponse(
            response_id=str(RecordId()),
            form_id=document.form_id,
            answers=outcome.answers,
            hidden_fields=outcome.hidden or None,
            form_version=version,
            ending_id=outcome.ending_id,
            csv_import_id=str(document.id),
            internal_answers_meta=(
                {
                    key: {
                        "updated_by": str(document.confirmed_by or document.actor_id),
                        "updated_by_email": None,
                        "updated_at": now,
                    }
                    for key in outcome.internal
                }
                or None
            ),
        )
        if outcome.expiration is not None:
            response.expiration, response.expiration_type = outcome.expiration
        return response

    # ------------------------------------------------------------------- the sweep
    async def _expire_waiting(self) -> int:
        """End the uploads nobody used within their hour (uploaded or checked):
        their file goes with them."""
        expired = 0
        now = self._clock()
        for row in await self._imports.list_by_status([ImportStatus.UPLOADED, ImportStatus.CHECKED]):
            if row.expires_at is not None and row.expires_at <= now:
                if await self._end_waiting(row.id, ImportStatus.EXPIRED) is not None:
                    expired += 1
        return expired

    async def purge_expired(self) -> Dict[str, int]:
        """Hourly: uploads that outlived their hour (the importer left, or a
        job died) are deleted, and imports no worker took or whose worker died
        are queued again or failed (the 5-minute redefer does the same). Counts only."""
        counts = {"expired": 0, "orphans": 0, "queued": 0, "failed": 0, "undone": 0}
        now = self._clock()
        # an upload whose row is gone or ended (a crash between the two writes)
        cutoff = now - limits.FILE_TTL - dt.timedelta(minutes=5)
        for import_id in await self._imports.file_ids_older_than(cutoff):
            row = await self._imports.get_by_id(import_id)
            if row is None or not row.status.has_file:
                await self._imports.delete_file(import_id)
                counts["orphans"] += 1
        redo = await self.redefer_pending()
        counts.update({k: redo[k] for k in ("expired", "queued", "failed", "undone")})
        return counts

    async def redefer_pending(self) -> Dict[str, int]:
        """Every 5 minutes: unused uploads past their hour are deleted, busy
        imports past it are failed and undone, imports no worker took are queued
        again, those whose worker died are queued or failed, and cleanups that
        failed are tried again. Counts only."""
        queued = failed = 0
        expired = await self._expire_waiting()
        undone = await self.retry_pending_undos()
        now = self._clock()
        for row in await self._imports.list_by_status([ImportStatus.QUEUED, ImportStatus.CHECKING, ImportStatus.RUNNING]):
            # the file's hour is absolute: a busy import past it is failed, its rows
            # undone and its file deleted
            if row.expires_at is not None and row.expires_at <= now:
                if await self._expire_job(row, "expired"):
                    failed += 1
                continue
            age = now - (row.updated_at or row.created_at or now)
            claimed = row.started_at is not None
            beat = row.heartbeat_at or row.started_at
            if row.status in (ImportStatus.QUEUED,) or (row.status == ImportStatus.CHECKING and not claimed):
                if age >= limits.QUEUED_MAX_AGE:
                    if await self._expire_job(row, "queue_timeout"):
                        failed += 1
                elif age >= limits.REDEFER_AFTER and await self._queue(row):
                    queued += 1
            elif beat is not None and beat < now - limits.STALE_RUNNING_AFTER:
                if row.attempts >= limits.MAX_ATTEMPTS:
                    if await self._expire_job(row, "worker_lost"):
                        failed += 1
                elif await self._queue(row):
                    queued += 1
        return {"queued": queued, "failed": failed, "expired": expired, "undone": undone}

    async def _expire_job(self, row: ResponseImportDocument, code: str) -> bool:
        """End a job nobody runs: what it stored is undone, its file deleted."""

        def change(document: ResponseImportDocument):
            if not document.status.busy:
                return None
            document.status = ImportStatus.FAILED
            document.error_code = code
            document.finished_at = self._clock()
            document.expires_at = None
            return document

        updated = await self._imports.update_locked(row.id, change)
        if updated is None:
            return False
        if row.mode == ImportMode.IMPORT and (row.status != ImportStatus.QUEUED or row.attempts > 0):
            await self._undo(row)
        await self._finish_file(row.id)
        return True

    # ----------------------------------------------------------------- erasure hooks
    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        await self._imports.delete_for_form(workspace_id, str(form_id))

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        await self._imports.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[str]) -> None:
        await self._imports.delete_by_workspace_ids(workspace_ids)

    async def forget_actor(self, user_id: str) -> int:
        return await self._imports.forget_actor(user_id)


async def _defer_job(import_id: str) -> None:
    """Queue ``run_response_import``: the id is the only argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.run_response_import.configure(
            queueing_lock=f"run_response_import:{import_id}"
        ).defer_async(import_id=import_id)
    except AlreadyEnqueued:
        pass
