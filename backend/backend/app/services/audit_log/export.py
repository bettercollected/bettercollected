"""Taking the audit log out as a file (docs/audit-log.md): the filtered view as
CSV or JSON, for staff holding ``audit.read``.

Rules this module keeps:

* The same decisions as the list: the switch, the filters, the catalogue, who may
  read, a form of this workspace. They are made by ``AuditLogReader.scope`` before
  anything else happens here.
* Every row is built from ``AuditEntryDto`` (the list's own field-by-field
  reply), never from the stored entry. So a Privacy officer's file withholds
  exactly what their screen withholds (no session id, no response id), and
  nothing stored but not shown can reach a file. The names beside the ids are the
  labels the list resolves: current members' display names (never an address),
  current form titles and team names, empty for anyone or anything gone.
* An export is itself recorded, and **before** it starts: ``audit_log_exported``
  holds the format, the number of rows, and the names of the filters used (never
  their values). When the entry cannot be stored the export is refused (503
  ``audit_unavailable``) and nothing is sent. Reading the list is not recorded.
* Bounded: at most ``MAX_ROWS`` rows (413 ``too_many_rows`` before anything is
  recorded or sent: narrow the filters), a few exports per person per window
  (429 ``rate_limited``), and the file is streamed in batches, never built in
  memory. A request refused after the bounded scan (413, 503) has used its
  slot, so repeating it cannot scan for free; only a failure of the scan itself
  gives the slot back.
* CSV cells are neutralised against spreadsheet formulas (names are text staff
  typed), through the response export's own guard.
"""

import datetime as dt
import json
from dataclasses import dataclass, replace
from http import HTTPStatus
from typing import AsyncIterator, Dict, List, Optional, Sequence

from common.ids import RecordId
from common.models.user import User
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.audit_log_dto import AuditEntryDto, AuditLabelsDto
from backend.app.schemas.workspace_audit_event import AUDIT_LOG_EXPORTED
from backend.app.services.audit_log.mode import refuse_when_off
from backend.app.services.audit_log.reader import AuditLogReader, AuditScope
from backend.app.services.form_access import audit
from backend.app.services.response_export.table import csv_line
from backend.app.services.response_export.writer import BOM, LINE_BREAK

FORMATS = ("csv", "json")
MAX_ROWS = 100_000
BATCH = 500
# per person and workspace: this many exports in this many seconds
EXPORTS_PER_WINDOW = 5
WINDOW_SECONDS = 600

# the names resolved beside the ids, and the ids they belong to
NAME_COLUMNS = (
    ("actor_name", "actor_id", "member"),
    ("target_name", "target_user_id", "member"),
    ("to_name", "to_user_id", "member"),
    ("form_title", "form_id", "form"),
    ("team_name", "group_id", "team"),
)
CSV_COLUMNS: List[str] = list(AuditEntryDto.model_fields) + [c[0] for c in NAME_COLUMNS]


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


JSON_KEYS: Dict[str, str] = {name: _camel(name) for name in CSV_COLUMNS}


def _error(status: HTTPStatus, code: str, message: str, **headers) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message}, headers=headers or None)


def _aware(moment: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=dt.timezone.utc)
    return moment


def _utc(moment: dt.datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _name(kind: str, ident: Optional[str], labels: AuditLabelsDto) -> Optional[str]:
    """The current name of an id, or None when it is gone, a former member's,
    or could not be looked up."""
    if not ident:
        return None
    if kind == "member":
        label = labels.members.get(str(ident))
        return label.name if label and label.status == "member" else None
    if kind == "form":
        label = labels.forms.get(str(ident))
        return label.title if label and label.status == "available" else None
    label = labels.teams.get(str(ident))
    return label.name if label and label.status == "available" else None


def flat_row(entry: AuditEntryDto, labels: AuditLabelsDto) -> Dict[str, object]:
    """One entry as a flat record: the DTO's fields, then the resolved names.
    Times are UTC; a list is one value."""
    values = entry.model_dump()
    values["at"] = _utc(entry.at)
    for column, source, kind in NAME_COLUMNS:
        values[column] = _name(kind, values.get(source), labels)
    return {column: values.get(column) for column in CSV_COLUMNS}


def _cell(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return value


def csv_text(batches: AsyncIterator) -> AsyncIterator[str]:
    async def run() -> AsyncIterator[str]:
        yield BOM + csv_line(CSV_COLUMNS)
        async for entries, labels in batches:
            for entry in entries:
                row = flat_row(entry, labels)
                yield LINE_BREAK + csv_line([_cell(row[c]) for c in CSV_COLUMNS])
        yield LINE_BREAK

    return run()


def json_text(batches: AsyncIterator, exported_at: dt.datetime) -> AsyncIterator[str]:
    async def run() -> AsyncIterator[str]:
        yield '{"exportedAt":' + json.dumps(_utc(exported_at)) + ',"entries":['
        first = True
        async for entries, labels in batches:
            for entry in entries:
                row = flat_row(entry, labels)
                item = json.dumps(
                    {JSON_KEYS[c]: row[c] for c in CSV_COLUMNS}, ensure_ascii=False
                )
                yield item if first else "," + item
                first = False
        yield "]}"

    return run()


@dataclass
class ExportStart:
    file_name: str
    media_type: str
    body: AsyncIterator[bytes]
    rows: int


class AuditLogExport:
    def __init__(self, reader: AuditLogReader, audit_repo, rate_limiter, clock=None):
        self._reader = reader
        self._audit = audit_repo
        self._limiter = rate_limiter
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    @staticmethod
    def _limiter_scope(workspace_id) -> str:
        return f"audit-export:{workspace_id}"

    async def start(
        self,
        workspace_id: RecordId,
        user: User,
        format: str,
        *,
        form_id: Optional[str] = None,
        areas: Sequence[str] = (),
        events: Sequence[str] = (),
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        filter_form: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ) -> ExportStart:
        """Everything that can refuse, in order, then the entry, then the body.
        Nothing is read for a caller who may not, and nothing is recorded for an
        export that is refused."""
        refuse_when_off()
        if format not in FORMATS:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_format",
                "Choose csv or json.",
            )
        scope = await self._reader.scope(
            workspace_id,
            user,
            form_id=form_id,
            areas=areas,
            events=events,
            actor=actor,
            target=target,
            involving=involving,
            filter_form=filter_form,
            since=since,
            until=until,
        )
        limiter_scope = self._limiter_scope(workspace_id)
        verdict = await self._limiter.admit(
            limiter_scope, str(user.id), EXPORTS_PER_WINDOW, WINDOW_SECONDS
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                f"Too many exports. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )
        # the file holds what existed when the request came: not the entry that
        # records this export, nor anything written while it streams
        now = self._clock()
        scope = replace(scope, until=min(_aware(scope.until) or now, now))
        try:
            rows = await self._reader.count_up_to(scope, MAX_ROWS + 1)
        except Exception:
            # the scan itself failed (the store, not the caller): nothing was
            # counted, so the request keeps no budget
            await self._give_back(limiter_scope, str(user.id))
            raise
        # from here the scan has run: a request that is refused after it (too
        # many entries, the entry not stored) has used its slot, so repeating it
        # cannot scan for free
        if rows > MAX_ROWS:
            raise _error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "too_many_rows",
                f"That is more than {MAX_ROWS} entries. Narrow the filters "
                "(a date range, a type or a person) and export again.",
            )
        await audit.record_or_refuse(
            self._audit,
            AUDIT_LOG_EXPORTED,
            workspace_id,
            user,
            export_format=format,
            count=rows,
            export_filters=self._filter_names(
                areas, events, actor, target, involving, scope.form_id, since, until
            ),
            # the form's id only for a form's own export (its route); a form
            # filter on the workspace's export is recorded as a filter name
            form_id=str(form_id) if form_id else None,
        )
        batches = self._limited(self._reader.batches(scope, BATCH), rows)
        if format == "csv":
            text, media = csv_text(batches), "text/csv; charset=utf-8"
        else:
            text, media = json_text(batches, now), "application/json"
        return ExportStart(
            file_name=self._file_name(format, now, form_id is not None),
            media_type=media,
            body=self._bytes(text, workspace_id),
            rows=rows,
        )

    @staticmethod
    def _filter_names(areas, events, actor, target, involving, form, since, until):
        names = []
        for name, used in (
            ("area", areas),
            ("event", events),
            ("actor", actor),
            ("target", target),
            ("involving", involving),
            ("form", form),
            ("from", since),
            ("to", until),
        ):
            if used:
                names.append(name)
        return names

    @staticmethod
    def _file_name(format: str, now: dt.datetime, of_form: bool) -> str:
        scope = "form-" if of_form else ""
        return f"audit-log-{scope}{now.strftime('%Y-%m-%d')}.{format}"

    async def _give_back(self, scope: str, client: str) -> None:
        try:
            await self._limiter.release(scope, client, WINDOW_SECONDS)
        except Exception as error:  # noqa: BLE001 - only the budget is lost
            logger.warning("could not give back an audit export request ({})", type(error).__name__)

    @staticmethod
    async def _limited(batches: AsyncIterator, rows: int) -> AsyncIterator:
        """Never more than the cap, whatever arrived since the count."""
        sent = 0
        async for entries, labels in batches:
            entries = entries[: MAX_ROWS - sent]
            sent += len(entries)
            if entries:
                yield entries, labels
            if sent >= MAX_ROWS:
                return

    @staticmethod
    async def _bytes(text: AsyncIterator[str], workspace_id) -> AsyncIterator[bytes]:
        try:
            async for part in text:
                yield part.encode("utf-8")
        except Exception as error:  # noqa: BLE001 - the stream has begun: log, then end it
            logger.error(
                "audit log export of workspace {} stopped early ({})",
                workspace_id,
                type(error).__name__,
            )
            raise
