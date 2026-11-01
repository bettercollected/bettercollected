"""The responses group's repositories: Postgres only (its Mongo collections are
read only by the import from 4.0, ``python -m backend.migrate``).

Form responses and their deletion requests, workspace responders and tags,
responder groups with their members and form links. Queries use the spine
columns of the rows in :mod:`backend.db.models`; the documents are
:class:`common.records.Record` classes, encoded and decoded by
:mod:`common.records.codec`. Answers are stored encrypted (``save_form_response``)
and are never decrypted, logged or queried here.

Within the group (form_responses, responses_deletion_requests,
workspace_responder, workspace_tags, responder_group and its members and
links) the 4.0 Mongo ``$lookup``s are SQL joins. Into the forms group (a
form's title, the workspace that imported it) they *compose* through the
forms repositories (:mod:`backend.app.repositories.response_scope`), restricted
to the form ids those repositories know, because the 4.0 ``$unwind`` dropped
responses whose form is gone.

Every read-then-write that depends on what it read runs in one transaction on
the stored row, locked (``SELECT ... FOR UPDATE``) or, where no row exists yet
to lock, under a transaction-scoped advisory lock on the natural key: a write
applies its change to the stored copy, never to one read earlier.
"""

import datetime as dt
import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import re
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from fastapi_pagination import Page
from loguru import logger
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import EmailStr
from starlette.concurrency import run_in_threadpool
from sqlalchemy import (
    Text,
    and_,
    cast,
    exists,
    extract,
    func,
    literal,
    literal_column,
    not_,
    or_,
    select,
    tuple_,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import aliased

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.response_list import (
    COUNT_CAP,
    SORT_VERSION,
    DeletionStatusFilter,
    RespondentFilter,
    ResponseListFilters,
    ResponseListQuery,
)
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.repositories.metric_periods import postgres_counts_per_period, utc
from backend.app.repositories.postgres.forms import (
    LOCK_NOT_AVAILABLE,
    _contains,
    _fold,
    _oid,
    _sort_terms,
    _sqlstate,
    _text,
)
from backend.app.services import form_availability
from backend.app.services.response_cursor import Anchor
from backend.app.services.response_paging import Seek, plan
from backend.app.repositories.response_scope import (
    ResponseScope,
    form_importers,
    form_titles,
)
from backend.app.utils.respondent_identity import identity_of
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupFormDocument,
    ResponderGroupMemberDocument,
)
from backend.app.schemas.standard_form_response import (
    DeclineReason,
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
    import_closure,
    staff_closure,
)
from backend.app.schemas.workspace_responder import (
    WorkspaceResponderDocument,
    WorkspaceTags,
)
from backend.db.models import (
    ResponseDeletionRequestRow,
    FormResponseRow,
    ResponderGroupFormRow,
    ResponderGroupMemberRow,
    ResponderGroupRow,
    WorkspaceResponderRow,
    WorkspaceTagRow,
)
from common.constants import MESSAGE_FORBIDDEN, MESSAGE_NOT_FOUND
from common.records import (
    RecordId,
    decode,
    derived_id,
    from_canonical_document,
    row_values,
    to_bson,
)
from common.records.repository import RecordRepository
from common.models.standard_form import (
    RespondentFeedback,
    StandardFormResponse,
    StandardFormResponseAnswer,
)
from common.models.user import User
from common.services.crypto_service import UnreadableCiphertext, crypto_service
from common.clock import utcnow
from camel_converter import to_camel, to_snake


def _filter_terms(doc, filter_query) -> list:
    """``create_filter_pipeline(filter_object=...)``: each set field is
    literal text its camelCase or snake_case key contains, ignoring case."""
    if not filter_query:
        return []
    matching = filter_query.model_dump(exclude_unset=True, exclude_none=True)
    return [
        or_(
            _contains(_text(doc[to_camel(key)]), value),
            _contains(_text(doc[to_snake(key)]), value),
        )
        for key, value in matching.items()
    ]


def _in_scope(row, scope: ResponseScope):
    """``ResponseScope.mongo_filter`` for ``form_responses`` or
    ``responses_deletion_requests`` rows."""
    return or_(
        and_(
            row.workspace_id == str(scope.workspace_id),
            row.form_id.in_(list(scope.form_ids)),
        ),
        and_(
            row.workspace_id.is_(None),  # stored before #768
            row.form_id.in_(list(scope.legacy_form_ids)),
        ),
    )


@contextmanager
def _busy_on_lock_timeout():
    """A lock wait that ran past the session's ``lock_timeout`` (a write of
    the same record is holding it) is a 409 the caller may retry, not a
    server error."""
    try:
        yield
    except DBAPIError as error:
        if _sqlstate(error) != LOCK_NOT_AVAILABLE:
            raise
        raise HTTPException(
            HTTPStatus.CONFLICT,
            content={
                "code": "busy",
                "message": "Another change to this record is in progress; try again.",
            },
        ) from None


async def _advisory_lock(session, *parts: Any) -> None:
    """Hold a transaction-scoped advisory lock named by ``parts`` until the
    transaction ends: serialises a read-then-write on a natural key (a tag's
    title, a responder's email) that has no row to lock yet and no unique
    index to fall back on."""
    digest = hashlib.sha1("\x00".join(str(p) for p in parts).encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    with _busy_on_lock_timeout():
        await session.execute(select(func.pg_advisory_xact_lock(key)))


async def _locked_doc(session, row, *where: Any, document=None):
    """The first row matching ``where`` (in the order the 4.0 ``find_one``
    returned them), locked for the rest of ``session``'s transaction, decoded
    as ``document``; None when there is none. A write applies its change to
    this copy, never to one read earlier."""
    with _busy_on_lock_timeout():
        doc = (
            await session.execute(
                select(row.doc)
                .where(*where)
                .order_by(row.created_at, row.id)
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
    return None if doc is None else decode(document, doc)


@dataclass
class ListedPage:
    """One page of a form's responses from :meth:`list_form_page`."""

    items: List[dict]
    total: int
    total_exact: bool
    has_next: bool
    # where this page begins (None for an empty page): the next cursor's anchor
    first: Optional[Anchor]


# ``doc ? 'answers'`` with the key written into the statement (not bound), so
# the planner can match it against the partial index of revision 0025.
_HAS_ANSWERS = FormResponseRow.doc.op("?")(literal_column("'answers'"))


def _version_expr():
    # the 0 is written into the statement (not bound) to match the expression
    # of the index ``ix_form_responses_list_version``
    return func.coalesce(FormResponseRow.form_version, literal_column("0"))


def _first_request():
    """$arrayElemAt [deletion_request.status, 0]: the first request, in natural
    order, of this copy's workspace (or stored before requests had one)."""
    r, dr = FormResponseRow, ResponseDeletionRequestRow
    return (
        select(dr.doc)
        .where(
            dr.response_id == r.response_id,
            or_(dr.workspace_id == r.workspace_id, dr.workspace_id.is_(None)),
        )
        .order_by(dr.created_at, dr.id)
        .limit(1)
        .correlate(r)
        .scalar_subquery()
    )


def _instant(moment: dt.datetime) -> dt.datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


def _requests_of(r, dr):
    """The deletion requests a response row shows (those of this copy's
    workspace, or stored before requests had one)."""
    return and_(
        dr.response_id == r.response_id,
        or_(dr.workspace_id == r.workspace_id, dr.workspace_id.is_(None)),
    )


def _list_filters(filters: ResponseListFilters) -> list:
    """The SQL conditions of the list filters (plaintext columns only; every
    value is bound)."""
    r, dr = FormResponseRow, ResponseDeletionRequestRow
    where = []
    # the instants as given, to the microsecond (``utc`` truncates to the second)
    if filters.submitted_from is not None:
        where.append(r.created_at >= _instant(filters.submitted_from))
    if filters.submitted_to is not None:
        where.append(r.created_at < _instant(filters.submitted_to))
    if filters.respondent == RespondentFilter.ANONYMOUS:
        where.append(
            or_(r.data_owner_identifier.is_(None), r.data_owner_identifier == "")
        )
    elif filters.respondent == RespondentFilter.KNOWN:
        where.append(
            and_(r.data_owner_identifier.is_not(None), r.data_owner_identifier != "")
        )
    if filters.form_version:
        # a response without a stored version is version 0, as the sort reads it
        where.append(_version_expr().in_(sorted(set(filters.form_version))))
    if filters.status:
        # the status the row shows is that of its first request
        # (``_first_request``): "none" is no request at all; any other is a
        # request with that status that no earlier request of the row
        # precedes. Written as (anti-)semi-joins, so a rare status is found
        # from the requests, not by probing every response.
        wanted = sorted(
            s.value for s in filters.status if s != DeletionStatusFilter.NONE
        )
        terms = []
        if DeletionStatusFilter.NONE in filters.status:
            terms.append(not_(exists().where(_requests_of(r, dr)).correlate(r)))
        if wanted:
            earlier = aliased(ResponseDeletionRequestRow)
            terms.append(
                exists()
                .where(
                    _requests_of(r, dr),
                    dr.status.in_(wanted),
                    not_(
                        exists()
                        .where(
                            _requests_of(r, earlier),
                            tuple_(earlier.created_at, earlier.id)
                            < tuple_(dr.created_at, dr.id),
                        )
                        .correlate(r, dr)
                    ),
                )
                .correlate(r)
            )
        where.append(or_(*terms))
    if filters.search:
        where.extend(
            _filter_terms(
                FormResponseRow.doc,
                FormResponseFilterQuery(data_owner_identifier=filters.search),
            )
        )
    return where


class PostgresFormResponseRepository(RecordRepository):
    row = FormResponseRow
    document = FormResponseDocument

    def __init__(self, session_factory, form_repo, workspace_form_repo):
        super().__init__(session_factory)
        self._forms = form_repo  # PostgresFormRepository
        self._workspace_forms = workspace_form_repo  # PostgresWorkspaceFormRepository

    # -- erasure of answers that were offered as options --------------------
    # Per task, not per repository: a delete runs ``_delete_recorded`` and then
    # ``_prune_tombstones_if_due`` in one task, and another delete running at
    # the same time (the repository is shared) must not see or clear its count.
    _options_noted: ContextVar[int] = ContextVar("options_noted", default=0)

    async def _delete_recorded(self, session, row, *where):
        if row is FormResponseRow:
            noted = await self._note_erased_options(session, where)
            self._options_noted.set(self._options_noted.get() + noted)
        return await super()._delete_recorded(session, row, *where)

    async def _prune_tombstones_if_due(self, row):
        await super()._prune_tombstones_if_due(row)
        if row is FormResponseRow and self._options_noted.get() > 0:
            # a delete that noted erased options committed: start redacting
            # the choices made from them (the jobs worker repeats it)
            self._options_noted.set(0)
            try:
                from backend.app.container import container

                container.option_source_service().schedule_redaction()
            except Exception as error:  # noqa: BLE001 - the erasure is done
                logger.warning(
                    "option sources: redaction not started ({})", type(error).__name__
                )

    async def _note_erased_options(self, session, where) -> int:
        """In the transaction that deletes responses: note, per source
        question, the option ids the responses about to go offered to other
        forms (only responses that shared an answer are read). A response that
        cannot be read is skipped; a database error fails the erasure so it
        can be repeated, never leaving a choice unredacted unseen."""
        r = FormResponseRow
        stored = (
            (
                await session.execute(
                    select(r.doc).where(
                        *where,
                        func.coalesce(func.jsonb_typeof(r.doc["shared_as_choices"]), "null")
                        == "array",
                        # (not jsonb_array_length: the planner may evaluate it
                        # on a row that holds no array)
                        cast(r.doc["shared_as_choices"], Text) != "[]",
                    )
                )
            )
            .scalars()
            .all()
        )
        if not stored:
            return 0
        from backend.app.schemas.option_source_erasure import (
            OptionSourceErasureDocument,
        )
        from backend.app.services.option_sources import erasure
        from backend.app.services.option_sources.ids import NoIdKey
        from backend.db.models import OptionSourceErasureRow

        # the versions the responses were filled on (reads), then the decryption
        # and hashing of every answer off the event loop (a large delete)
        versions: Dict[Tuple[str, Any], Any] = {}
        documents = []
        for raw in stored:
            document = decode(FormResponseDocument, raw)
            if not document.shared_as_choices:
                continue
            key = (str(document.form_id), document.form_version)
            if key not in versions:
                try:
                    versions[key] = await self._filled_version(
                        key[0], document.form_version
                    )
                except Exception:  # noqa: BLE001 - one response never blocks an erasure
                    versions[key] = None
            documents.append((document, versions[key]))

        def offered_by(items):
            found: Dict[Tuple[str, str, str], Set[str]] = {}
            unreadable = 0
            for document, version in items:
                workspace_id, form_id = document.workspace_id, str(document.form_id)
                try:
                    if workspace_id is None or version is None:
                        raise ValueError("no workspace or form")
                    answers = document.answers
                    if not isinstance(answers, dict):
                        answers = json.loads(
                            crypto_service.decrypt(
                                workspace_id=workspace_id,
                                form_id=form_id,
                                data=answers,
                            )
                        )
                    offered = erasure.offered_option_ids(
                        workspace_id,
                        form_id,
                        version,
                        answers,
                        document.shared_as_choices,
                    )
                except NoIdKey:
                    raise
                except Exception:  # noqa: BLE001 - one response never blocks an erasure
                    unreadable += 1
                    continue
                for question_id, option_ids in offered.items():
                    found.setdefault(
                        (str(workspace_id), form_id, question_id), set()
                    ).update(option_ids)
            return found, unreadable

        found, unreadable = await run_in_threadpool(offered_by, documents)
        for (workspace_id, form_id, question_id), option_ids in found.items():
            note = OptionSourceErasureDocument(
                workspace_id=workspace_id,
                form_id=form_id,
                question_id=question_id,
                option_ids=sorted(option_ids),
            )
            note.touch()
            await session.execute(
                self._upsert_statement(row_values(note), OptionSourceErasureRow)
            )
        if unreadable:
            logger.warning(
                "option sources: {} erased response(s) could not be read for redaction",
                unreadable,
            )
        return len(found)

    async def _filled_version(self, form_id: str, version: Optional[int]):
        """The published version a response was filled on (else the latest, else
        the draft): what tells which of its answers were questions to share."""
        found = None
        if version is not None:
            found = await self._forms.get_form_by_by_version(form_id, int(version))
        if found is None:
            found = await self._forms.get_latest_version_of_form(form_id)
        if found is None:
            found = await self._forms.get_form_document_by_id(form_id)
        return found

    async def redaction_batch(
        self, scope: ResponseScope, after_id: Optional[str], limit: int
    ) -> List[FormResponseDocument]:
        """The next responses of ``scope`` that carry answers (a keyset)."""
        where = [
            _in_scope(FormResponseRow, scope),
            func.coalesce(func.jsonb_typeof(FormResponseRow.doc["answers"]), "null")
            != "null",
        ]
        if after_id is not None:
            where.append(FormResponseRow.id > after_id)
        return await self.many(*where, order_by=(FormResponseRow.id,), limit=limit)

    async def redact_option_labels(
        self,
        document_id: str,
        workspace_id: RecordId,
        form_id: str,
        field_ids: Iterable[str],
        option_ids: Set[str],
    ) -> int:
        """Replace the label snapshots of ``option_ids`` in the answers to
        ``field_ids`` of one stored response, decrypting and re-encrypting
        under its row lock (an edit made at once keeps its answers). Touches
        nothing else, not even ``updated_at``. Returns the snapshots changed."""
        from backend.app.services.option_sources import erasure

        async with self._session() as session, session.begin():
            stored = await _locked_doc(
                session,
                FormResponseRow,
                FormResponseRow.id == str(document_id),
                document=FormResponseDocument,
            )
            if stored is None:
                return 0
            answers = stored.answers
            try:
                if not isinstance(answers, dict):
                    answers = json.loads(
                        crypto_service.decrypt(
                            workspace_id=workspace_id, form_id=form_id, data=answers
                        )
                    )
            except UnreadableCiphertext:
                return 0
            changed = erasure.redact_answers(answers, field_ids, option_ids)
            if changed:
                stored.answers = crypto_service.encrypt(
                    workspace_id=workspace_id,
                    form_id=form_id,
                    data=json.dumps(answers),
                )
                await session.execute(self._upsert_statement(row_values(stored)))
        return changed

    # -- composition over the forms group ---------------------------------
    async def _form_titles(self, form_ids: List[str]) -> Dict[str, Any]:
        """form_id -> title for the forms that exist (``$lookup forms`` + ``$unwind``)."""
        return await form_titles(self._forms, form_ids)

    async def _form_importers(
        self, form_ids: List[str], workspace_id: RecordId
    ) -> Dict[str, str]:
        """form_id -> the user who imported it into ``workspace_id``
        (``$lookup workspace_forms`` of that workspace + ``$unwind``)."""
        return await form_importers(self._workspace_forms, form_ids, workspace_id)

    # -- listings -----------------------------------------------------------
    async def get_form_responses(
        self,
        scope: ResponseScope,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ) -> Page:
        titles = await self._form_titles(list(scope.form_ids))
        where = [
            _in_scope(FormResponseRow, scope),
            FormResponseRow.form_id.in_(list(titles)),
            FormResponseRow.doc.has_key("answers"),
            *_filter_terms(FormResponseRow.doc, filter_query),
        ]
        if data_owner_identifier is not None:
            where.append(FormResponseRow.data_owner_identifier == data_owner_identifier)
        stmt = (
            select(FormResponseRow.doc, _first_request())
            .where(*where)
            .order_by(
                *_sort_terms(
                    FormResponseRow.doc,
                    sort,
                    (FormResponseRow.created_at.desc(), FormResponseRow.id),
                )
            )
        )

        async def transform(items):
            responses = []
            for doc, request_doc in items:
                response = from_canonical_document(doc)
                response["form_title"] = titles[response["form_id"]]
                if request_doc is not None:  # $arrayElemAt: unset without a request
                    response["status"] = from_canonical_document(request_doc).get(
                        "status"
                    )
                responses.append(response)
            return responses

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def list_form_page(
        self,
        scope: ResponseScope,
        query: ResponseListQuery,
        anchor: Optional[Anchor] = None,
    ) -> ListedPage:
        """One page of one form's responses, filtered and sorted on plaintext
        columns, reached by a seek on the sort index (``response_paging``)
        instead of counting every row before it. The total is exact up to
        ``COUNT_CAP`` rows. Answers stay encrypted: this reads and returns the
        stored documents as ``get_form_responses`` does."""
        (form_id,) = scope.form_ids
        titles = await self._form_titles([form_id])
        if form_id not in titles:
            return ListedPage([], 0, True, False, None)
        r, dr = FormResponseRow, ResponseDeletionRequestRow
        # this workspace's copies of the form's responses (or, stored before
        # #768 and with the form linked here alone, those without a workspace):
        # ``form_id`` is the one leading condition, so the sort indexes, which
        # start with it, apply whatever the workspace condition is
        in_workspace = r.workspace_id == str(scope.workspace_id)
        if form_id in scope.legacy_form_ids:
            in_workspace = or_(in_workspace, r.workspace_id.is_(None))
        here = and_(r.form_id == form_id, in_workspace)
        # a response without a stored submission time cannot be placed in the
        # order (none is expected); it is left out of the list and of its count
        where = [
            here,
            _HAS_ANSWERS,
            r.created_at.is_not(None),
            *_list_filters(query.filters),
        ]

        async with self._session() as session:
            counted = (
                await session.execute(
                    select(func.count()).select_from(
                        # in index order: the scan stops at the cap instead of
                        # reading the form to find enough rows
                        select(literal(1))
                        .where(*where)
                        .order_by(r.created_at)
                        .limit(COUNT_CAP + 1)
                        .subquery()
                    )
                )
            ).scalar_one()
        total_exact = counted <= COUNT_CAP
        total = min(counted, COUNT_CAP)

        seek = plan(
            query.page,
            query.size,
            total,
            total_exact,
            anchor.page if anchor is not None else None,
        )
        if seek.empty:
            return ListedPage([], total, total_exact, False, None)

        by_version = query.sort_by == SORT_VERSION
        keys = [*([_version_expr()] if by_version else []), r.created_at, r.id]
        # forward = along the requested order; a reverse seek scans against it
        ascending = (not query.descending) != seek.reverse
        order = [k.asc() if ascending else k.desc() for k in keys]
        stmt_where = list(where)
        if seek.anchor is not None:
            # row comparison on the index columns: after (or from) the anchor
            # in the scan direction; the anchor's values are bound parameters
            bound = tuple_(
                *[literal(v, type_=k.type) for v, k in zip(anchor.key(), keys)]
            )
            mine = tuple_(*keys)
            inclusive = seek.anchor == "inclusive"
            if ascending:
                stmt_where.append(mine >= bound if inclusive else mine > bound)
            else:
                stmt_where.append(mine <= bound if inclusive else mine < bound)

        stmt = (
            select(r.doc, _first_request(), _version_expr(), r.created_at, r.id)
            .where(*stmt_where)
            .order_by(*order)
            .offset(seek.offset)
            .limit(seek.limit)
        )
        async with self._session() as session:
            rows = (await session.execute(stmt)).all()
        if seek.reverse:
            rows.reverse()

        if seek.source == "end":
            has_next = query.page * query.size < total
        elif seek.reverse:
            has_next = True  # the anchor row follows this page
        else:
            has_next = len(rows) > query.size
        rows = rows[: query.size]

        items = []
        for doc, request_doc, _, _, _ in rows:
            response = from_canonical_document(doc)
            response["form_title"] = titles[response["form_id"]]
            if request_doc is not None:  # $arrayElemAt: unset without a request
                response["status"] = from_canonical_document(request_doc).get("status")
            items.append(response)
        first = None
        if rows:
            _, _, version, created_at, row_id = rows[0]
            first = Anchor(
                page=query.page,
                version=version if by_version else None,
                created_at=created_at,
                row_id=row_id,
            )
        return ListedPage(items, total, total_exact, has_next, first)

    async def get_workspace_responders(
        self,
        scope: ResponseScope,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
    ):
        r, dr, wr = FormResponseRow, ResponseDeletionRequestRow, WorkspaceResponderRow
        grouped = (
            select(
                r.data_owner_identifier.label("email"),
                func.count().label("responses"),
                func.array_agg(r.response_id).label("response_ids"),
            )
            .where(_in_scope(r, scope), r.data_owner_identifier.is_not(None))
            .group_by(r.data_owner_identifier)
            .subquery("grouped")
        )
        deletion_requests = (
            select(func.count())
            .where(
                dr.response_id == func.any(grouped.c.response_ids),
                # this workspace's requests (or stored before they had one)
                or_(
                    dr.workspace_id == str(scope.workspace_id),
                    dr.workspace_id.is_(None),
                ),
            )
            .correlate(grouped)
            .scalar_subquery()
        )
        # this workspace's record only, the oldest if it has several
        responder = (
            select(wr.doc)
            .where(
                wr.workspace_id == str(scope.workspace_id),
                wr.email == grouped.c.email,
            )
            .order_by(wr.id)
            .limit(1)
            .correlate(grouped)
            .scalar_subquery()
        )
        stmt = select(
            grouped.c.email,
            grouped.c.responses,
            deletion_requests.label("deletion_requests"),
            responder.label("responder"),
        ).order_by(grouped.c.email)
        # create_filter_pipeline(..., default_sort=False): filters only, no sort
        matching = (
            filter_query.model_dump(exclude_unset=True, exclude_none=True)
            if filter_query
            else {}
        )
        for key, value in matching.items():
            keys = {to_camel(key), to_snake(key)}
            if "email" in keys:
                stmt = stmt.where(_contains(grouped.c.email, value))
            else:  # the projected document has no such field
                stmt = stmt.where(literal(False))

        async def transform(items):
            responders = []
            tag_ids: Set[str] = set()
            for email, responses, deletions, responder_doc in items:
                responder = {
                    "email": email,
                    "responses": responses,
                    "deletion_requests": deletions,
                }
                if responder_doc is not None:
                    raw = from_canonical_document(responder_doc)
                    _fold(responder, raw, {"tags": "tags", "metadata": "metadata"})
                responders.append(responder)
                for tag in responder.get("tags") or []:
                    tag_ids.add(_oid(tag))
            tags = {}
            if tag_ids:
                async with self._session() as session:
                    docs = (
                        (
                            await session.execute(
                                select(WorkspaceTagRow.doc).where(
                                    WorkspaceTagRow.id.in_(tag_ids),
                                    WorkspaceTagRow.workspace_id
                                    == str(scope.workspace_id),
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                for doc in docs:
                    tag = from_canonical_document(doc)
                    tags[_oid(tag["_id"])] = tag
            for responder in responders:  # $lookup workspace_tags: docs, [] when none
                responder["tags"] = [
                    tags[_oid(t)]
                    for t in (responder.get("tags") or [])
                    if _oid(t) in tags
                ]
            return responders

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def get_deletion_requests(
        self,
        scope: ResponseScope,
        data_owner_identifier: Optional[str] = None,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
        anonymous_identity: Optional[str] = None,
    ):
        """DeletionRequestsRepository.get_deletion_requests, composed."""
        titles = await self._form_titles(list(scope.form_ids))
        importers = await self._form_importers(list(titles), scope.workspace_id)
        known = [f for f in titles if f in importers]  # both $unwinds must match
        dr, r = ResponseDeletionRequestRow, FormResponseRow
        where = [
            _in_scope(dr, scope),
            dr.form_id.in_(known),
            *_filter_terms(dr.doc, filter_query),
        ]
        owner = []
        if data_owner_identifier is not None:
            owner.append(dr.data_owner_identifier == data_owner_identifier)
        if anonymous_identity is not None:
            owner.append(dr.anonymous_identity == anonymous_identity)
        if owner:
            where.append(or_(*owner))
        # the copy in the request's workspace (any for a request without one)
        response_doc = (
            select(r.doc)
            .where(
                r.response_id == dr.response_id,
                or_(dr.workspace_id.is_(None), r.workspace_id == dr.workspace_id),
            )
            .order_by(r.created_at, r.id)
            .limit(1)
            .correlate(dr)
            .scalar_subquery()
        )
        stmt = (
            select(dr.doc, response_doc)
            .where(*where)
            .order_by(*_sort_terms(dr.doc, sort, (dr.created_at, dr.id)))
        )

        async def transform(items):
            requests = []
            for doc, response in items:
                request = from_canonical_document(doc)
                request["form_title"] = titles[request["form_id"]]
                request["form_imported_by"] = importers[request["form_id"]]
                if response is not None:  # $arrayElemAt: unset without a response
                    request["submission_uuid"] = from_canonical_document(response).get(
                        "submission_uuid"
                    )
                requests.append(request)
            return requests

        async with self._session() as session:
            return await apaginate(session, stmt, transformer=transform, unique=False)

    async def list(
        self,
        scope: ResponseScope,
        request_for_deletion: bool,
        filter_query: FormResponseFilterQuery = None,
        sort: SortRequest = None,
        data_subjects: bool = None,
    ) -> Page:
        if data_subjects:
            return await self.get_workspace_responders(
                scope, filter_query=filter_query, sort=sort
            )
        elif request_for_deletion:
            return await self.get_deletion_requests(
                scope, filter_query=filter_query, sort=sort
            )
        else:
            return await self.get_form_responses(
                scope, filter_query=filter_query, sort=sort
            )

    async def get_user_submissions(
        self, scope: ResponseScope, user: User, request_for_deletion: bool = False
    ):
        # the 4.0 get_user_submissions
        if request_for_deletion:
            return await self.get_deletion_requests(
                scope,
                data_owner_identifier=user.sub,
                anonymous_identity=identity_of(user.sub),
            )
        else:
            return await self.get_form_responses(scope, data_owner_identifier=user.sub)

    # -- counts -------------------------------------------------------------
    async def _counts_by_form(self, row, *where) -> Dict[str, int]:
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(row.form_id, func.count())
                    .where(*where)
                    .group_by(row.form_id)
                )
            ).all()
        return {form_id: n for form_id, n in rows}

    async def count_responses_with_answers_by_form_ids(
        self, scope: ResponseScope
    ) -> Dict[str, int]:
        return await self._counts_by_form(
            FormResponseRow,
            _in_scope(FormResponseRow, scope),
            FormResponseRow.doc.has_key("answers"),
        )

    async def count_responses_by_form_ids(self, scope: ResponseScope) -> Dict[str, int]:
        """form_id -> the stored responses in scope (what a response limit
        counts: every stored response, deletions already gone)."""
        return await self._counts_by_form(
            FormResponseRow, _in_scope(FormResponseRow, scope)
        )

    async def count_deletion_requests_by_form_ids(
        self, scope: ResponseScope
    ) -> Dict[str, int]:
        return await self._counts_by_form(
            ResponseDeletionRequestRow,
            _in_scope(ResponseDeletionRequestRow, scope),
        )

    async def count_responses_for_form_ids(self, scope: ResponseScope) -> int:
        return await self.count(_in_scope(FormResponseRow, scope))

    # -- platform metrics (admin dashboard) ------------------------------------
    @staticmethod
    def _with_answers():
        return FormResponseRow.doc.has_key("answers")

    async def count_responses(
        self, submitted_since: Optional[dt.datetime] = None
    ) -> int:
        where = [self._with_answers()]
        if submitted_since is not None:
            where.append(FormResponseRow.created_at >= utc(submitted_since))
        return await self.count(*where)

    async def count_anonymous_responses(self) -> int:
        owner = FormResponseRow.data_owner_identifier
        return await self.count(self._with_answers(), or_(owner.is_(None), owner == ""))

    async def count_identified_responders(self) -> int:
        owner = FormResponseRow.data_owner_identifier
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count(owner.distinct())).where(
                        self._with_answers(), owner.is_not(None), owner != ""
                    )
                )
            ).scalar_one()

    async def count_responses_per_period(
        self, boundaries: List[dt.datetime]
    ) -> List[int]:
        return await postgres_counts_per_period(
            self,
            FormResponseRow.created_at,
            [utc(b) for b in boundaries],
            self._with_answers(),
        )

    async def get_deletion_requests_count_in_workspace(self, scope: ResponseScope):
        dr = ResponseDeletionRequestRow
        in_forms = _in_scope(dr, scope)

        async def count_where(*where):
            async with self._session() as session:
                return (
                    await session.execute(
                        select(func.count()).select_from(dr).where(*where)
                    )
                ).scalar_one()

        counts = {
            "success": await count_where(
                in_forms, dr.status == DeletionRequestStatus.SUCCESS.value
            ),
            "pending": await count_where(
                in_forms, dr.status == DeletionRequestStatus.PENDING.value
            ),
            "total": await count_where(in_forms),
        }
        # $count emits no document for zero matches; $arrayElemAt then unsets the field
        return {k: v for k, v in counts.items() if v}

    # -- BaseRepository stubs ---------------------------------------------
    async def get(self, form_id: str, response_id: str):
        pass

    async def add(self, item: FormResponseDocument):
        pass

    async def update(self, item_id: str, item: FormResponseDocument):
        pass

    async def delete(self, item_id: str, provider):
        pass

    # -- plain reads and writes ------------------------------------------------
    async def list_recent_by_form_id(
        self, scope: ResponseScope, limit: int, skip: int = 0
    ) -> List[FormResponseDocument]:
        async with self._session() as session:
            stmt = (
                select(FormResponseRow.doc)
                .where(_in_scope(FormResponseRow, scope))
                .order_by(FormResponseRow.created_at.desc(), FormResponseRow.id)
                .offset(skip)
                .limit(limit)
            )
            docs = (await session.execute(stmt)).scalars().all()
        return [decode(FormResponseDocument, d) for d in docs]

    @staticmethod
    def _ai_notice_where(
        scope: ResponseScope, provider_name: str, shown_since: dt.datetime
    ):
        # to the second (utc truncates), like the Mongo store's ISO strings
        since = utc(shown_since)
        return (
            _in_scope(FormResponseRow, scope),
            FormResponseRow.provider == "self",
            FormResponseRow.ai_notice_provider_name == provider_name,
            FormResponseRow.ai_notice_shown_at >= since,
        )

    async def list_recent_with_ai_notice(
        self,
        scope: ResponseScope,
        provider_name: str,
        shown_since: dt.datetime,
        limit: int,
    ) -> List[FormResponseDocument]:
        return await self.many(
            *self._ai_notice_where(scope, provider_name, shown_since),
            order_by=(FormResponseRow.created_at.desc(), FormResponseRow.id),
            limit=limit,
        )

    async def count_with_ai_notice(
        self, scope: ResponseScope, provider_name: str, shown_since: dt.datetime
    ) -> int:
        return await self.count(
            *self._ai_notice_where(scope, provider_name, shown_since)
        )

    async def list_deletion_requests_for_form_ids(
        self, scope: ResponseScope
    ) -> List[FormResponseDeletionRequest]:
        return await self.many(
            _in_scope(ResponseDeletionRequestRow, scope),
            row=ResponseDeletionRequestRow,
            document=FormResponseDeletionRequest,
        )

    async def list_by_form_id(
        self, scope: ResponseScope, limit: Optional[int] = None
    ) -> List[FormResponseDocument]:
        """Every response in ``scope``; with ``limit``, the first that many in
        the same order (``created_at``, ``id``), so a bounded read is the start of
        the unbounded one."""
        return await self.many(_in_scope(FormResponseRow, scope), limit=limit)

    # -- export (services/response_export) ------------------------------------
    @staticmethod
    def _export_where(scope: ResponseScope, filters) -> list:
        """The responses an export holds: those of ``scope`` that carry
        answers (deletion-only stubs are not responses), narrowed by the list's
        filters (``_list_filters``: plaintext columns and deletion-request
        status only; every value is bound)."""
        row = FormResponseRow
        where = [
            _in_scope(row, scope),
            # a stub kept for a deletion request has no answers (or a null one)
            func.coalesce(func.jsonb_typeof(row.doc["answers"]), "null") != "null",
        ]
        if filters is not None:
            where.extend(_list_filters(filters))
        return where

    async def count_for_export(self, scope: ResponseScope, filters=None) -> int:
        """How many responses an export would hold, without reading an answer."""
        return await self.count(*self._export_where(scope, filters))

    async def export_batch(
        self,
        scope: ResponseScope,
        filters=None,
        after_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[FormResponseDocument]:
        """The next ``limit`` responses an export holds after ``after_id``, in
        id order (the order they were stored in): a keyset, so a response
        deleted meanwhile is simply not met and nothing is read twice."""
        where = self._export_where(scope, filters)
        if after_id is not None:
            where.append(FormResponseRow.id > after_id)
        return await self.many(*where, order_by=(FormResponseRow.id,), limit=limit)

    # -- another form's answers as options (services/option_sources) ----------
    @staticmethod
    def _option_source_where(
        scope: ResponseScope, now_iso: str, question_id: str
    ) -> list:
        """The responses whose answer to ``question_id`` may become a choice of
        another form: those of ``scope`` that carry answers, that gave the
        answer while the version they filled said it may be shown as a choice
        (``shared_as_choices``), with **no deletion request of any status** (a
        respondent who asked to be erased is not shown), not submitted with the
        anonymous choice (``anonymous_identity`` set), and not past their
        retention (``expiration``, ISO text)."""
        r, dr = FormResponseRow, ResponseDeletionRequestRow
        return [
            _in_scope(r, scope),
            func.coalesce(func.jsonb_typeof(r.doc["answers"]), "null") != "null",
            func.coalesce(func.jsonb_typeof(r.doc["shared_as_choices"]), "null")
            == "array",
            func.jsonb_exists(r.doc["shared_as_choices"], question_id),
            not_(exists().where(_requests_of(r, dr)).correlate(r)),
            or_(r.anonymous_identity.is_(None), r.anonymous_identity == ""),
            or_(r.expiration.is_(None), r.expiration == "", r.expiration > now_iso),
        ]

    async def option_source_token(
        self, scope: ResponseScope, now_iso: str, question_id: str
    ) -> Tuple[int, int]:
        """``(count, hash sum)`` of the eligible responses
        (``_option_source_where``): one aggregate, no answer read. The sum is
        over a hash of each response's id and last change, so a response that
        is new, edited, deleted, expired or deletion-requested changes it
        whatever its place in the order (and a clock cannot hide an edit)."""
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
                    ).where(*self._option_source_where(scope, now_iso, question_id))
                )
            ).one()
        return int(row[0]), int(row[1])

    async def option_source_batch(
        self,
        scope: ResponseScope,
        now_iso: str,
        question_id: str,
        after_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[FormResponseDocument]:
        """The next ``limit`` eligible responses after ``after_id``, in id
        order (a keyset)."""
        where = self._option_source_where(scope, now_iso, question_id)
        if after_id is not None:
            where.append(FormResponseRow.id > after_id)
        return await self.many(*where, order_by=(FormResponseRow.id,), limit=limit)

    async def list_by_response_id(self, response_id: str) -> List[FormResponseDocument]:
        return await self.many(
            FormResponseRow.response_id == response_id, order_by=(FormResponseRow.id,)
        )

    async def list_by_submission_uuid(
        self, submission_uuid: str
    ) -> List[FormResponseDocument]:
        return await self.many(
            FormResponseRow.submission_uuid == submission_uuid,
            order_by=(FormResponseRow.id,),
        )

    async def count_unstamped(self, form_id: str) -> int:
        responses = await self.count(
            FormResponseRow.form_id == str(form_id),
            FormResponseRow.workspace_id.is_(None),
        )
        dr = ResponseDeletionRequestRow
        async with self._session() as session:
            requests = (
                await session.execute(
                    select(func.count())
                    .select_from(dr)
                    .where(dr.form_id == str(form_id), dr.workspace_id.is_(None))
                )
            ).scalar_one()
        return responses + requests

    async def save(self, response: FormResponseDocument) -> FormResponseDocument:
        return await self.save_document(response)

    @staticmethod
    def _request_of(response: FormResponseDocument):
        """The deletion request of this stored copy: same response and form,
        in its workspace (or stored before #768 without one)."""
        dr = ResponseDeletionRequestRow
        in_workspace = (
            dr.workspace_id.is_(None)
            if response.workspace_id is None
            else or_(
                dr.workspace_id == str(response.workspace_id), dr.workspace_id.is_(None)
            )
        )
        return (
            dr.response_id == response.response_id,
            dr.form_id == str(response.form_id),
            in_workspace,
        )

    async def find_deletion_request_for(
        self, response: FormResponseDocument
    ) -> Optional[FormResponseDeletionRequest]:
        return await self.one_of(
            ResponseDeletionRequestRow,
            FormResponseDeletionRequest,
            *self._request_of(response),
        )

    async def add_deletion_request(
        self, response: FormResponseDocument, response_id: str
    ) -> FormResponseDeletionRequest:
        try:
            return await self.save_document(
                FormResponseDeletionRequest(
                    form_id=response.form_id,
                    response_id=response_id,
                    dataOwnerIdentifier=response.dataOwnerIdentifier,
                    anonymous_identity=response.anonymous_identity,
                    provider=response.provider,
                    workspace_id=response.workspace_id,
                    deleted_at=None,
                ),
                row=ResponseDeletionRequestRow,
            )
        except IntegrityError:
            # one request per response, provider and workspace (the unique
            # index of app revision 0020): a second one filed while the first
            # was being stored
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Error: Deletion request already exists for the response : "
                + str(response_id),
            )

    async def close_deletion_request(
        self,
        request: FormResponseDeletionRequest,
        status: DeletionRequestStatus,
        closed_by: str,
        decline_reason: Optional[DeclineReason] = None,
    ) -> FormResponseDeletionRequest:
        """Staff closed ``request`` by hand: its outcome, who and when, applied
        to the stored request under its row lock. Refused with 409 when
        another close was recorded since ``request`` was read (a second staff
        member, an import that no longer has the response), and a decline is
        refused the same way when the request changed status since (its
        response was deleted meanwhile). Completing a request by deleting its
        response (``delete_form_response``) records no close and is no
        conflict, so a completing close still follows the deletion."""
        async with self._session() as session, session.begin():
            stored = await _locked_doc(
                session,
                ResponseDeletionRequestRow,
                ResponseDeletionRequestRow.id == str(request.id),
                document=FormResponseDeletionRequest,
            )
            if stored is None:
                raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
            if len(stored.closures) > len(request.closures) or (
                # the data was deleted (and the request marked done) after
                # the caller read it: a decline would say "not deleted"
                status is DeletionRequestStatus.DECLINED
                and stored.status != request.status
            ):
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content={
                        "code": "deletion_request_closed",
                        "message": "This deletion request is already closed.",
                    },
                )
            now = utcnow()
            stored.status = status
            stored.closed_by = closed_by
            stored.closed_at = now
            stored.decline_reason = decline_reason
            stored.closures = [
                *stored.closures,
                staff_closure(status, closed_by, now, decline_reason),
            ]
            stored.touch()
            await session.execute(
                self._upsert_statement(row_values(stored), ResponseDeletionRequestRow)
            )
        return stored

    async def delete_by_form_id_except(
        self, scope: ResponseScope, keep_response_ids: List[str]
    ):
        return await self.delete_where(
            _in_scope(FormResponseRow, scope),
            FormResponseRow.response_id.not_in(list(keep_response_ids)),
        )

    async def mark_deletion_requests_success_except(
        self, scope: ResponseScope, provider: str, keep_response_ids: List[str], now
    ) -> int:
        dr = ResponseDeletionRequestRow
        modified = 0
        async with self._session() as session, session.begin():
            # the requests are locked while they are closed: a staff close
            # landing meanwhile is kept, never overwritten
            with _busy_on_lock_timeout():
                docs = (
                    (
                        await session.execute(
                            select(dr.doc)
                            .where(
                                _in_scope(dr, scope),
                                dr.provider == provider,
                                dr.response_id.not_in(list(keep_response_ids)),
                            )
                            .order_by(dr.created_at, dr.id)
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .all()
                )
            for doc in docs:
                request = decode(FormResponseDeletionRequest, doc)
                if (
                    request.status != DeletionRequestStatus.SUCCESS
                    or request.updated_at != now
                ):
                    modified += 1
                if request.status != DeletionRequestStatus.SUCCESS:
                    # a new close; an earlier one (a decline) is kept
                    request.closures = [*request.closures, import_closure(now)]
                request.status = DeletionRequestStatus.SUCCESS
                request.updated_at = now
                await session.execute(
                    self._upsert_statement(row_values(request), dr)
                )
        return modified

    async def delete_in_scope(self, scope: ResponseScope):
        await self.delete_where(
            _in_scope(ResponseDeletionRequestRow, scope),
            row=ResponseDeletionRequestRow,
        )
        return await self.delete_where(_in_scope(FormResponseRow, scope))

    async def delete_by_form_id(self, form_id):
        return await self.delete_where(FormResponseRow.form_id == form_id)

    async def delete_deletion_requests(self, form_id: str):
        return await self.delete_where(
            ResponseDeletionRequestRow.form_id == form_id,
            row=ResponseDeletionRequestRow,
        )

    async def delete_by_form_ids(self, form_ids):
        return await self.delete_where(FormResponseRow.form_id.in_(list(form_ids)))

    async def delete_deletion_requests_by_form_ids(self, form_ids):
        return await self.delete_where(
            ResponseDeletionRequestRow.form_id.in_(list(form_ids)),
            row=ResponseDeletionRequestRow,
        )

    async def save_form_response(
        self,
        form_id: RecordId,
        response: StandardFormResponse,
        workspace_id: RecordId,
        response_limit: Optional[int] = None,
        scope: Optional[ResponseScope] = None,
        submitted_at: Optional[dt.datetime] = None,
        internal_answers: Optional[Dict[str, Any]] = None,
    ):
        """Store a new response. With ``response_limit`` (and the ``scope`` the
        count is taken over) the count and the insert happen in one
        transaction under an advisory lock on the form in this workspace, so
        concurrent submissions queue up and the one that would pass the limit
        is refused: 409 ``form_full``, nothing stored.

        ``submitted_at`` and ``internal_answers`` are for the CSV import only
        (``services/response_import``): the submission time a file states
        (a respondent's submission is always stamped now) and the staff-only
        answers it holds, encrypted here like ``answers``."""
        response_document = FormResponseDocument(**response.model_dump(mode="json"))
        response_document.submission_uuid = str(uuid4())
        if workspace_id:
            for k, v in response_document.answers.items():
                if type(v) == StandardFormResponseAnswer:
                    response_document.answers[k] = v.model_dump(mode="json")
            response_document.answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(response_document.answers),
            )
            if isinstance(response_document.hidden_fields, dict):
                response_document.hidden_fields = crypto_service.encrypt(
                    workspace_id=workspace_id,
                    form_id=form_id,
                    data=json.dumps(response_document.hidden_fields),
                )
        response_document.form_id = str(form_id)
        # collected in this workspace (#768)
        response_document.workspace_id = RecordId(workspace_id)
        response_document.provider = "self"
        # submitted now, whatever the client sent: the time must not be the
        # respondent's to choose (newest-first order, "submitted since")
        now = utcnow()
        if submitted_at is not None:
            now = submitted_at
        response_document.created_at = now
        response_document.updated_at = now
        if internal_answers and workspace_id:
            response_document.internal_answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(internal_answers),
            )
        if response_limit is None:
            return await self.save_document(response_document)
        if scope is None:
            raise ValueError("a response limit needs the scope its count is taken over")
        self._check_collection(response_document, FormResponseRow)
        response_document.touch()
        async with self._session() as session, session.begin():
            await _advisory_lock(session, "response-limit", workspace_id, form_id)
            stored = (
                await session.execute(
                    select(func.count()).where(_in_scope(FormResponseRow, scope))
                )
            ).scalar_one()
            if stored >= response_limit:
                raise form_availability.form_full_error()
            await session.execute(self._upsert_statement(row_values(response_document)))
        return response_document

    async def patch_form_response(
        self,
        form_id: RecordId,
        document_id: RecordId,
        response: StandardFormResponse,
        workspace_id: RecordId,
        user=User,
    ):
        """Merge the sent answers into the stored response, decrypting and
        re-encrypting under the response's row lock: two edits made at once
        both keep their answers, and one landing on top of a respondent
        feedback or an internal-answers write keeps those."""
        async with self._session() as session, session.begin():
            response_document = await _locked_doc(
                session,
                FormResponseRow,
                FormResponseRow.id == str(document_id),
                FormResponseRow.form_id == _oid(form_id),
                document=FormResponseDocument,
            )
            if response_document is None:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Response not found"
                )
            # only the verified respondent who submitted it may edit a response
            if not user or response_document.dataOwnerIdentifier != user.sub:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
                )
            answers = response_document.answers
            if not isinstance(answers, dict):
                try:
                    answers = (
                        json.loads(
                            crypto_service.decrypt(
                                workspace_id=workspace_id, form_id=form_id, data=answers
                            )
                        )
                        if answers
                        else {}
                    )
                except UnreadableCiphertext:
                    # merging into nothing would drop the stored answers
                    raise HTTPException(
                        status_code=HTTPStatus.CONFLICT,
                        content="This submission can't be read, so it can't be edited.",
                    )
            for k, v in (response.answers or {}).items():
                answers[k] = (
                    v.model_dump(mode="json")
                    if isinstance(v, StandardFormResponseAnswer)
                    else v
                )
            response_document.answers = crypto_service.encrypt(
                workspace_id=workspace_id,
                form_id=form_id,
                data=json.dumps(answers),
            )
            # only answers are merged: the AI notice stamp stays as submitted (#752)
            # the workspace it was collected in stays; one stored before #768
            # gets the workspace the caller checked it against
            if response_document.workspace_id is None:
                response_document.workspace_id = RecordId(workspace_id)
            # an edit keeps the submission time and records when it changed
            response_document.touch()
            await session.execute(self._upsert_statement(row_values(response_document)))
        return response_document

    async def delete_form_response(
        self,
        response: FormResponseDocument,
        expected_closures: Optional[int] = None,
    ):
        """Delete the stored copy and mark its deletion request done, in one
        transaction on the locked request: a staff close made meanwhile is
        kept on it (its closures are never rewritten).

        ``expected_closures`` is for completing a request: the number of
        closes the caller saw on it. When another close was recorded since
        (a staff decline), nothing is deleted and the call is refused with 409
        ``deletion_request_closed``, so the data is never deleted under a
        request that stays declined."""
        response_id = response.response_id
        async with self._session() as session, session.begin():
            request = await _locked_doc(
                session,
                ResponseDeletionRequestRow,
                *self._request_of(response),
                document=FormResponseDeletionRequest,
            )
            if (
                request is not None
                and expected_closures is not None
                and len(request.closures) > expected_closures
            ):
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content={
                        "code": "deletion_request_closed",
                        "message": "This deletion request is already closed.",
                    },
                )
            await self._delete_recorded(
                session, FormResponseRow, FormResponseRow.id == str(response.id)
            )
            if request is not None:
                request.status = DeletionRequestStatus.SUCCESS
                request.touch()
                await session.execute(
                    self._upsert_statement(
                        row_values(request), ResponseDeletionRequestRow
                    )
                )
        await self._prune_tombstones_if_due(FormResponseRow)
        return response_id

    async def get_all_expiring_responses(self):
        return await self.many(FormResponseRow.expiration_type.in_(["date", "days"]))

    async def list_expiration_schedules(self) -> List[Tuple[str, str]]:
        expiration = FormResponseRow.doc["expiration"]
        stmt = (
            select(FormResponseRow.response_id, expiration.astext)
            .where(
                FormResponseRow.expiration_type.in_(["date", "days"]),
                func.jsonb_typeof(expiration) == "string",
                FormResponseRow.response_id.is_not(None),
            )
            .order_by(FormResponseRow.response_id)
        )
        async with self._session() as session:
            rows = (await session.execute(stmt)).all()
        return sorted((response_id, value) for response_id, value in rows)

    async def count_imported(self, scope: ResponseScope, import_id: str) -> int:
        """The stored responses a CSV import created (``csv_import_id``)."""
        return await self.count(
            _in_scope(FormResponseRow, scope),
            FormResponseRow.doc["csv_import_id"].astext == str(import_id),
        )

    async def delete_imported(self, scope: ResponseScope, import_id: str) -> int:
        """Delete the responses a CSV import created, in the form and workspace
        of ``scope`` only (the undo of an import, and the cleanup of one that
        failed half way). Returns how many were deleted."""
        return await self.delete_where(
            _in_scope(FormResponseRow, scope),
            FormResponseRow.doc["csv_import_id"].astext == str(import_id),
        )

    async def delete_response(self, response_id: str):
        await self.delete_one_where(FormResponseRow.response_id == response_id)
        return response_id

    async def get_response(self, response_id: str):
        return await self.one(FormResponseRow.response_id == response_id)

    async def save_internal_answers(
        self, response: FormResponseDocument, expected_version: int
    ) -> Optional[FormResponseDocument]:
        """Twin of the Mongo conditional ``$set``: the row is locked while the
        version is compared and the three internal-answer keys are replaced."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormResponseRow.doc)
                    .where(FormResponseRow.id == str(response.id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            stored = decode(FormResponseDocument, doc)
            if (stored.internal_answers_version or 0) != expected_version:
                return None
            stored.internal_answers = response.internal_answers
            stored.internal_answers_meta = response.internal_answers_meta
            stored.internal_answers_version = response.internal_answers_version
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def add_respondent_feedback(
        self, response: FormResponseDocument, entry: RespondentFeedback
    ) -> Optional[FormResponseDocument]:
        """Twin of the Mongo ``$push``: the row is locked while the entry is
        appended to the stored history."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormResponseRow.doc)
                    .where(FormResponseRow.id == str(response.id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            stored = decode(FormResponseDocument, doc)
            stored.respondent_feedback = [*(stored.respondent_feedback or []), entry]
            await session.execute(self._upsert_statement(row_values(stored)))
        return stored

    async def get_by_submission_uuid(self, submission_uuid: str):
        return await self.one(FormResponseRow.submission_uuid == submission_uuid)


class PostgresWorkspaceRespondersRepository(RecordRepository):
    row = WorkspaceResponderRow
    document = WorkspaceResponderDocument

    async def create_workspace_tag(self, workspace_id: RecordId, title: str):
        """The workspace's tag of this title (created when there is none), its
        ``updated_at`` moved: a title is stored once per workspace even when
        two requests create it at once."""
        async with self._session() as session, session.begin():
            await _advisory_lock(session, "workspace_tags", workspace_id, title)
            workspace_tag = await _locked_doc(
                session,
                WorkspaceTagRow,
                WorkspaceTagRow.workspace_id == _oid(workspace_id),
                WorkspaceTagRow.title == title,
                document=WorkspaceTags,
            )
            if not workspace_tag:
                workspace_tag = WorkspaceTags(workspace_id=workspace_id, title=title)
            workspace_tag.touch()
            await session.execute(
                self._upsert_statement(row_values(workspace_tag), WorkspaceTagRow)
            )
        return workspace_tag

    async def get_workspace_tags(self, workspace_id: RecordId):
        return await self.many(
            WorkspaceTagRow.workspace_id == _oid(workspace_id),
            row=WorkspaceTagRow,
            document=WorkspaceTags,
        )

    async def get_responder_by_email_and_workspace_id(
        self, workspace_id: RecordId, email: str
    ):
        return await self._write_responder(workspace_id, email)

    async def patch_responder(
        self,
        workspace_id: RecordId,
        email: str,
        metadata: Optional[Dict[str, str]] = None,
        tags: Optional[List[RecordId]] = None,
    ):
        return await self._write_responder(workspace_id, email, metadata, tags)

    async def _write_responder(
        self,
        workspace_id: RecordId,
        email: str,
        metadata: Optional[Dict[str, str]] = None,
        tags: Optional[List[RecordId]] = None,
    ):
        """The workspace's responder of this email (created when there is
        none) with ``metadata`` and ``tags`` set when given, applied to the
        stored copy: a responder exists once per workspace and email even when
        two requests create it at once, and a write of one field keeps the
        other."""
        async with self._session() as session, session.begin():
            await _advisory_lock(session, "workspace_responder", workspace_id, email)
            workspace_responder = await _locked_doc(
                session,
                WorkspaceResponderRow,
                WorkspaceResponderRow.workspace_id == _oid(workspace_id),
                WorkspaceResponderRow.email == email,
                document=WorkspaceResponderDocument,
            )
            if not workspace_responder:
                workspace_responder = WorkspaceResponderDocument(
                    workspace_id=workspace_id, email=email
                )
            if metadata:
                workspace_responder.metadata = metadata
            if tags:
                workspace_responder.tags = tags
            workspace_responder.touch()
            await session.execute(
                self._upsert_statement(row_values(workspace_responder))
            )
        return workspace_responder


class PostgresResponderGroupsRepository(RecordRepository):
    row = ResponderGroupRow
    document = ResponderGroupDocument

    @staticmethod
    def member(
        group_id: RecordId, identifier: str
    ) -> ResponderGroupMemberDocument:
        return ResponderGroupMemberDocument(
            id=derived_id("responder_group_member", group_id, identifier),
            group_id=group_id,
            identifier=identifier,
        )

    @staticmethod
    def link(group_id: RecordId, form_id: str) -> ResponderGroupFormDocument:
        return ResponderGroupFormDocument(
            id=derived_id("responder_group_form", group_id, form_id),
            group_id=group_id,
            form_id=form_id,
        )

    async def _members(self, *where) -> List[ResponderGroupMemberDocument]:
        return await self.many(
            *where, row=ResponderGroupMemberRow, document=ResponderGroupMemberDocument
        )

    async def _links(self, *where) -> List[ResponderGroupFormDocument]:
        return await self.many(
            *where, row=ResponderGroupFormRow, document=ResponderGroupFormDocument
        )

    async def create_group(
        self,
        workspace_id: RecordId,
        name: str,
        description: Optional[str] = None,
        regex: Optional[str] = None,
    ):
        if description and len(description) > 280:
            return {"message": "description should be less than 280 characters"}
        return await self.save_document(
            ResponderGroupDocument(
                name=name,
                workspace_id=workspace_id,
                description=description,
                regex=regex,
            )
        )

    async def update_group(
        self,
        workspace_id: RecordId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        group_id: RecordId = None,
        regex: Optional[str] = None,
    ):
        """The group's fields (and its members, when ``emails`` are given)
        changed in one transaction on the locked stored group: a failure
        part-way leaves the members as they were, and a concurrent edit of
        another field is kept."""
        async with self._session() as session, session.begin():
            responder_group = await _locked_doc(
                session,
                ResponderGroupRow,
                ResponderGroupRow.workspace_id == _oid(workspace_id),
                ResponderGroupRow.id == _oid(group_id),
                document=ResponderGroupDocument,
            )
            if responder_group is None:
                raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
            if emails and len(emails) != 0:
                await self._delete_recorded(
                    session,
                    ResponderGroupMemberRow,
                    ResponderGroupMemberRow.group_id == _oid(group_id),
                )
                for email in set(emails):
                    await session.execute(
                        self._upsert_statement(
                            row_values(self.member(group_id, email)),
                            ResponderGroupMemberRow,
                        )
                    )
            if name:
                responder_group.name = name
            if description:
                responder_group.description = description
            responder_group.regex = regex
            responder_group.touch()
            await session.execute(self._upsert_statement(row_values(responder_group)))
        await self._prune_tombstones_if_due(ResponderGroupMemberRow)
        return responder_group

    async def get_group_in_workspace(
        self, workspace_id: RecordId, group_id: RecordId
    ):
        return await self.one(
            ResponderGroupRow.workspace_id == _oid(workspace_id),
            ResponderGroupRow.id == _oid(group_id),
        )

    async def add_emails_to_group(
        self, group_id: RecordId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing = {
            member.identifier
            for member in await self._members(
                ResponderGroupMemberRow.group_id == _oid(group_id),
                ResponderGroupMemberRow.identifier.in_(emails),
            )
        }
        new_members = [self.member(group_id, e) for e in emails if e not in existing]
        if new_members:
            await self.upsert_many(new_members, row=ResponderGroupMemberRow)

    async def remove_emails_from_group(
        self, group_id: RecordId, emails: List[EmailStr]
    ):
        await self.delete_where(
            ResponderGroupMemberRow.group_id == _oid(group_id),
            ResponderGroupMemberRow.identifier.in_(list(emails)),
            row=ResponderGroupMemberRow,
        )

    async def _projected(self, groups: List[ResponderGroupDocument]) -> List[dict]:
        """The $project of get_emails_in_group / get_groups_in_workspace."""
        ids = [_oid(g.id) for g in groups]
        members = await self._members(ResponderGroupMemberRow.group_id.in_(ids))
        links = await self._links(ResponderGroupFormRow.group_id.in_(ids))
        out = []
        for group in groups:
            out.append(
                {
                    "_id": group.id,
                    "name": group.name,
                    "workspace_id": group.workspace_id,
                    "emails": [m.identifier for m in members if m.group_id == group.id],
                    "description": group.description,
                    "regex": group.regex,
                    "forms": [l.form_id for l in links if l.group_id == group.id],
                }
            )
        return out

    async def get_emails_in_group(self, group_id: RecordId):
        group = await self.one(ResponderGroupRow.id == _oid(group_id))
        if group is None:
            return None
        return (await self._projected([group]))[0]

    async def remove_responder_group(self, group_id: RecordId):
        """The group, its members and its form links, in one transaction."""
        async with self._session() as session, session.begin():
            await self._delete_recorded(
                session, ResponderGroupRow, ResponderGroupRow.id == _oid(group_id)
            )
            await self._delete_recorded(
                session,
                ResponderGroupMemberRow,
                ResponderGroupMemberRow.group_id == _oid(group_id),
            )
            await self._delete_recorded(
                session,
                ResponderGroupFormRow,
                ResponderGroupFormRow.group_id == _oid(group_id),
            )
        await self._prune_tombstones_if_due(ResponderGroupRow)

    async def get_groups_in_workspace(self, workspace_id: RecordId):
        groups = await self.many(ResponderGroupRow.workspace_id == _oid(workspace_id))
        return [ResponderGroupDto(**row) for row in await self._projected(groups)]

    async def get_groups_by_form_ids(
        self, form_ids: List[str], workspace_id: RecordId
    ) -> Dict[str, List[dict]]:
        """form_id -> the raw responder-group documents of ``workspace_id``
        attached to it. A form held by several workspaces carries each one's
        own groups: another workspace's are never returned."""
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        groups = {
            group.id: to_bson(group)
            for group in await self.many(
                ResponderGroupRow.id.in_([_oid(l.group_id) for l in links] or ["-"]),
                ResponderGroupRow.workspace_id == _oid(workspace_id),
            )
        }
        by_form: Dict[str, List[dict]] = {form_id: [] for form_id in form_ids}
        for link in links:
            if link.group_id in groups:
                by_form.setdefault(link.form_id, []).append(groups[link.group_id])
        return by_form

    async def get_linked_group_owners(
        self, form_id: str
    ) -> Dict[RecordId, Optional[RecordId]]:
        """group id -> the workspace that owns it (None when it has none), for
        every group linked to the form, whatever its workspace. Only the save
        logic that must keep other workspaces' links reads this; nothing
        returned to a caller may be built from it."""
        links = await self._links(ResponderGroupFormRow.form_id == form_id)
        owners = {
            group.id: group.workspace_id
            for group in await self.many(
                ResponderGroupRow.id.in_([_oid(l.group_id) for l in links] or ["-"])
            )
        }
        return {
            link.group_id: owners[link.group_id]
            for link in links
            if link.group_id in owners
        }

    async def get_form_ids_accessible_to(
        self, form_ids: List[str], identifier: str, workspace_id: RecordId
    ) -> Set[str]:
        """The subset of ``form_ids`` whose responder groups of ``workspace_id``
        admit ``identifier``: a member with that identifier, or a group regex it
        matches. Another workspace's groups linked to the same form neither
        admit nor refuse anyone here."""
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        candidates = [_oid(g) for g in {link.group_id for link in links}]
        if not candidates:
            return set()
        own_groups = await self.many(
            ResponderGroupRow.id.in_(candidates),
            ResponderGroupRow.workspace_id == _oid(workspace_id),
        )
        group_ids = [_oid(group.id) for group in own_groups]
        if not group_ids:
            return set()
        member_of = {
            member.group_id
            for member in await self._members(
                ResponderGroupMemberRow.group_id.in_(group_ids),
                ResponderGroupMemberRow.identifier == identifier,
            )
        }
        for group in own_groups:
            if not group.regex:
                continue
            try:
                if re.search(group.regex, identifier):
                    member_of.add(group.id)
            except re.error:
                continue
        return {link.form_id for link in links if link.group_id in member_of}

    async def add_group_to_form(self, form_id: str, group_id: RecordId):
        existing = await self._links(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
        )
        if not existing:
            return await self.save_document(
                self.link(group_id, form_id), row=ResponderGroupFormRow
            )

    async def add_groups_to_form(self, form_id: str, group_ids: List[RecordId]):
        """Set the form's groups to ``group_ids``: the links not listed are
        removed, the missing ones added, in one transaction that holds the
        form's links locked (two saves of one form's groups apply one after
        the other, each against the links the other left)."""
        wanted = list(dict.fromkeys(group_ids))
        async with self._session() as session, session.begin():
            await _advisory_lock(session, "responder_group_form", form_id)
            with _busy_on_lock_timeout():
                locked = (
                    (
                        await session.execute(
                            select(ResponderGroupFormRow.doc)
                            .where(ResponderGroupFormRow.form_id == form_id)
                            .order_by(
                                ResponderGroupFormRow.created_at,
                                ResponderGroupFormRow.id,
                            )
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .all()
                )
            existing = [decode(ResponderGroupFormDocument, doc) for doc in locked]
            linked = {link.group_id for link in existing}
            to_remove = [g for g in linked if g not in wanted]
            if to_remove:
                await self._delete_recorded(
                    session,
                    ResponderGroupFormRow,
                    ResponderGroupFormRow.form_id == form_id,
                    ResponderGroupFormRow.group_id.in_([_oid(g) for g in to_remove]),
                )
            for group_id in wanted:
                if group_id not in linked:
                    link = self.link(group_id, form_id)
                    link.touch()
                    await session.execute(
                        self._upsert_statement(row_values(link), ResponderGroupFormRow)
                    )
            links = (
                await session.execute(
                    select(ResponderGroupFormRow.doc)
                    .where(ResponderGroupFormRow.form_id == form_id)
                    .order_by(ResponderGroupFormRow.created_at, ResponderGroupFormRow.id)
                )
            ).scalars().all()
        await self._prune_tombstones_if_due(ResponderGroupFormRow)
        return [decode(ResponderGroupFormDocument, doc) for doc in links]

    async def remove_group_from_form(self, form_id: str, group_id: RecordId):
        await self.delete_one_where(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
            row=ResponderGroupFormRow,
        )

    async def delete_workspace_form_groups(self, form_id: str):
        await self.delete_where(
            ResponderGroupFormRow.form_id == form_id, row=ResponderGroupFormRow
        )

    async def delete_responder_groups(self, workspace_ids: List[RecordId]):
        """Every group of the workspaces with its members and form links, in
        one transaction."""
        async with self._session() as session, session.begin():
            # in id order: two deletes of overlapping workspaces lock the same
            # groups in the same order and so never deadlock
            with _busy_on_lock_timeout():
                group_ids = (
                    (
                        await session.execute(
                            select(ResponderGroupRow.id)
                            .where(
                                ResponderGroupRow.workspace_id.in_(
                                    [_oid(w) for w in workspace_ids]
                                )
                            )
                            .order_by(ResponderGroupRow.id)
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .all()
                ) or ["-"]
            await self._delete_recorded(
                session,
                ResponderGroupFormRow,
                ResponderGroupFormRow.group_id.in_(group_ids),
            )
            await self._delete_recorded(
                session,
                ResponderGroupMemberRow,
                ResponderGroupMemberRow.group_id.in_(group_ids),
            )
            await self._delete_recorded(
                session, ResponderGroupRow, ResponderGroupRow.id.in_(group_ids)
            )
        await self._prune_tombstones_if_due(ResponderGroupRow)
