"""The reads a report makes of a form's responses: Postgres only.

Three kinds of read, all over the same set of responses (``export_where``: the
responses of a scope that carry answers, narrowed by the list's plaintext
filters; a deletion-only stub is not a response):

* ``token``: ``(count, hash sum)`` of the set, one aggregate that reads no
  answer. A new, edited, deleted or expired response changes it, so what is
  cached against it is never stale (the option sources' design).
* ``group_counts``: the response count per value of a plaintext dimension (a
  day, the form version, the ending, ...), grouped in SQL. Nothing is decrypted.
* ``batch``: the next responses after an id, in id order (a keyset, the
  export's), as light rows: the plaintext columns the report groups by, and the
  encrypted answers exactly as stored. The caller decrypts, adds up and drops
  them. No document is built, no identity (not even the responder's account id,
  only whether there is one) leaves the query.

Every value is bound; the answers are never queried, only read back.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from sqlalchemy import (
    Text,
    case,
    cast,
    extract,
    func,
    literal,
    literal_column,
    or_,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.models.filter_queries.response_list import ResponseListFilters
from backend.app.repositories.postgres.responses import (
    _HAS_ANSWERS,
    _in_scope,
    _list_filters,
    _requests_of,
    _version_expr,
)
from backend.app.repositories.response_scope import ResponseScope
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.services.reporting.catalogue import (
    ENDING,
    FEEDBACK_STATUS,
    FORM_VERSION,
    NONE_KEY,
    RESPONDENT,
    SOURCE,
    STATUS,
    SUBMITTED_AT,
)
from backend.db.models import FormResponseRow, ResponseDeletionRequestRow
from common.records.repository import RecordRepository


@dataclass(frozen=True)
class ReportRow:
    """One response as the pass reads it."""

    id: str
    created_at: Optional[dt.datetime]
    form_version: Optional[int]
    anonymous: bool
    ending_id: Optional[str]
    source: str
    # ``doc.answers`` as stored: ``{"$binary": ...}`` for the encrypted blob
    answers: Any
    # which part of the scope it came from (see ``batch``)
    phase: int = 0

    @property
    def cursor(self) -> "Cursor":
        return Cursor(self.phase, self.created_at, self.id)


def _report_row(row, phase: int) -> ReportRow:
    """One response of the pass from its row: the columns the report groups by
    and the stored answers. The rest of the document (the responder's identity,
    hidden fields, feedback) is not read."""
    doc = row[4] if isinstance(row[4], dict) else {}
    ending = doc.get("ending_id")
    if isinstance(doc.get("submission_source"), dict):
        source = "api"
    elif isinstance(doc.get("csv_import_id"), str):
        source = "csv"
    else:
        source = "form"
    return ReportRow(
        id=row[0],
        created_at=row[1],
        form_version=row[2],
        anonymous=bool(row[3]),
        ending_id=ending if isinstance(ending, str) and ending else None,
        source=source,
        answers=doc.get("answers"),
        phase=phase,
    )


@dataclass(frozen=True)
class Cursor:
    """Where a pass stands: the last response it read."""

    phase: int
    created_at: dt.datetime
    id: str


def _source_expr():
    r = FormResponseRow
    return case(
        (func.jsonb_typeof(r.doc["submission_source"]) == "object", "api"),
        (func.jsonb_typeof(r.doc["csv_import_id"]) == "string", "csv"),
        else_="form",
    )


def _anonymous_expr():
    r = FormResponseRow
    return or_(r.data_owner_identifier.is_(None), r.data_owner_identifier == "")


def _first_request_status():
    """The status of the response's first deletion request (the one the list
    shows), or null."""
    r, dr = FormResponseRow, ResponseDeletionRequestRow
    return (
        select(dr.status)
        .where(_requests_of(r, dr))
        .order_by(dr.created_at, dr.id)
        .limit(1)
        .correlate(r)
        .scalar_subquery()
    )


def _dimension_expr(dimension: str, bucket: Optional[str], tz: str):
    """The SQL expression of a plaintext dimension (text, or a timestamp for the
    submission time)."""
    r = FormResponseRow
    if dimension == SUBMITTED_AT:
        # the submission instant as the wall clock of the viewer's zone, cut to
        # the bucket (a week starts on Monday)
        return func.date_trunc(literal(bucket or "day"), func.timezone(literal(tz), r.created_at))
    if dimension == FORM_VERSION:
        return cast(_version_expr(), Text)
    if dimension == RESPONDENT:
        return case((_anonymous_expr(), "anonymous"), else_="known")
    if dimension == ENDING:
        return func.coalesce(r.doc["ending_id"].astext, NONE_KEY)
    if dimension == SOURCE:
        return _source_expr()
    if dimension == STATUS:
        return func.coalesce(_first_request_status(), NONE_KEY)
    if dimension == FEEDBACK_STATUS:
        # the status of the newest feedback entry (the message is encrypted and
        # is never read)
        last = func.jsonb_path_query_first(
            r.doc["respondent_feedback"],
            literal_column("'$[last].status'"),
            type_=JSONB,
        )
        return func.coalesce(
            last.op("#>>", return_type=Text)(literal_column("'{}'")), NONE_KEY
        )
    raise ValueError(f"not a plaintext dimension: {dimension}")


class PostgresReportRepository(RecordRepository):
    row = FormResponseRow
    document = FormResponseDocument

    @staticmethod
    def report_where(scope: ResponseScope, filters: Optional[ResponseListFilters]) -> list:
        """The responses a report is about: those of ``scope`` that carry
        answers (``doc ? 'answers'``, the predicate of the responses list and of
        its partial index: a deletion-only stub is not a response), narrowed by
        the list's plaintext filters.

        The export tests ``jsonb_typeof(doc -> 'answers') <> 'null'`` instead,
        which reads (detoasts) every document: counting 20,000 responses took 345
        ms against 8 ms from the index. The two sets differ only by a response
        whose ``answers`` key holds JSON null, which nothing writes; the pass
        skips such a row when it meets one."""
        where = [_in_scope(FormResponseRow, scope), _HAS_ANSWERS]
        if filters is not None:
            where.extend(_list_filters(filters))
        return where

    async def token(
        self, scope: ResponseScope, filters: Optional[ResponseListFilters]
    ) -> Tuple[int, int]:
        """``(count, hash sum)`` of the set: one aggregate, no answer read."""
        r = FormResponseRow
        stamp = func.coalesce(cast(extract("epoch", r.updated_at), Text), "")
        async with self._session() as session:
            row = (
                await session.execute(
                    select(
                        func.count(),
                        func.coalesce(
                            func.sum(func.hashtextextended(func.concat(r.id, stamp), 0)),
                            0,
                        ),
                    ).where(*self.report_where(scope, filters))
                )
            ).one()
        return int(row[0]), int(row[1])

    async def group_counts(
        self,
        scope: ResponseScope,
        filters: Optional[ResponseListFilters],
        dimension: str,
        bucket: Optional[str],
        tz: str,
    ) -> List[Tuple[Any, int]]:
        """``(value, responses)`` for each value of a plaintext dimension; a
        time dimension gives the bucket's first instant (naive, in ``tz``)."""
        expression = _dimension_expr(dimension, bucket, tz)
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(expression, func.count())
                    .where(*self.report_where(scope, filters))
                    .group_by(literal_column("1"))
                )
            ).all()
        return [(row[0], int(row[1])) for row in rows]

    async def batch(
        self,
        scope: ResponseScope,
        filters: Optional[ResponseListFilters],
        after: Optional["Cursor"],
        limit: int,
    ) -> List[ReportRow]:
        """The next ``limit`` responses after ``after``, a keyset on ``(created
        at, id)`` served by the index of ``(workspace, form, created_at)`` in
        order, so every batch costs its own rows and a pass over N responses
        reads N rows, never N per batch. The responses stamped with the
        workspace come first, then those stored before responses carried one
        (``scope.legacy_form_ids``); a response deleted meanwhile is simply not
        met and nothing is read twice. An empty list ends the pass.

        Only for a scope of one form (a report is of one)."""
        if len(scope.form_ids) != 1:
            raise ValueError("a report reads the responses of one form")
        form_id = scope.form_ids[0]
        phases = [("stamped", FormResponseRow.workspace_id == str(scope.workspace_id))]
        if form_id in scope.legacy_form_ids:
            phases.append(("legacy", FormResponseRow.workspace_id.is_(None)))
        start = 0 if after is None else after.phase
        for phase in range(start, len(phases)):
            r = FormResponseRow
            where = [
                phases[phase][1],
                r.form_id == form_id,
                *self._answers_and_filters(filters),
            ]
            if after is not None and after.phase == phase:
                where.append(r.created_at >= after.created_at)
                where.append(
                    tuple_(r.created_at, r.id) > tuple_(after.created_at, after.id)
                )
            async with self._session() as session:
                # the whole document, not ``doc -> 'x'`` five times: every such
                # expression detoasts and parses the same 3 KB again (measured:
                # 46 ms per 500 responses against 8)
                rows = (
                    await session.execute(
                        select(r.id, r.created_at, r.form_version, _anonymous_expr(), r.doc)
                        .where(*where)
                        .order_by(r.created_at, r.id)
                        .limit(limit)
                    )
                ).all()
            if rows:
                return [_report_row(row, phase) for row in rows]
        return []

    @staticmethod
    def _answers_and_filters(filters: Optional[ResponseListFilters]) -> list:
        """What ``report_where`` adds to one phase of the scope."""
        where = [_HAS_ANSWERS]
        if filters is not None:
            where.extend(_list_filters(filters))
        return where
