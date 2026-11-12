"""The report engine: runs a validated plan over a form's responses.

* **Cards that read no answer** (counts by day, form version, ending, status,
  respondent kind, feedback status, source) are counted in SQL: nothing is
  decrypted, and no cap applies.
* **Cards that read answers** share *one* pass: the responses are read in
  keyset batches of ``BATCH_SIZE`` (the export's batching), each batch is
  decrypted and added up on a worker thread and then dropped, so memory is one
  batch and every card is fed from the same read. The caller has already
  refused a set above ``REPORT_MAX_ROWS``: the pass never returns a partial
  result.

What leaves this module is aggregates only: counts, sums and averages per group.
No response id, no answer text and no identity is in a result.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.repositories.postgres.report_queries import (
    PostgresReportRepository,
    ReportRow,
)
from backend.app.repositories.response_scope import ResponseScope
from backend.app.services.reporting import limits
from backend.app.services.reporting.accumulate import (
    ALL_KEY,
    clause_matches,
    CardAccumulator,
    CardTotals,
    GroupTotals,
    ResponseView,
    bucket_key,
    labels_for,
)
from backend.app.services.reporting.catalogue import (
    CHOICE,
    CHOICES,
    COUNT,
    ENDING,
    FORM_VERSION,
    NONE_KEY,
    OTHER_KEY,
    REMOVED_KEY,
    RESPONDENT,
    RESPONDENT_GROUPS,
    SCALE,
    SOURCE,
    SOURCE_GROUPS,
    STATUS,
    STATUS_GROUPS,
    SUBMITTED_AT,
    YES_NO,
    YES_NO_GROUPS,
    CALCULATED,
    Catalogue,
)
from backend.app.services.reporting.definition import CardPlan, ClausePlan, DimensionPlan, Plan
from common.services.crypto_service import UnreadableCiphertext, crypto_service

# every group of these dimensions is listed, also those nobody is in
_FIXED = {
    RESPONDENT: [k for k, _ in RESPONDENT_GROUPS],
    SOURCE: [k for k, _ in SOURCE_GROUPS],
    STATUS: [k for k, _ in STATUS_GROUPS],
}


@dataclass
class ScanResult:
    cards: Dict[str, Dict[str, Any]]
    scanned: int
    unreadable: int
    # the responses that met every condition on an answer (all of them without one)
    matched: int = 0


@dataclass
class DrillPage:
    """A page of the responses in one group of one card: the ones that met the
    definition's conditions and fell in the group, oldest first, where the pass
    stopped, how many it read, and whether it reached the end of the set."""

    rows: List[ReportRow]
    # where to continue (None at the end of the set)
    cursor: Optional[Any]
    scanned: int
    exhausted: bool


class TooManyRows(Exception):
    """The pass met more responses than ``REPORT_MAX_ROWS`` (they arrived while
    it ran): never a partial result."""

    def __init__(self, count: int):
        self.count = count


def stored_answers(
    blob: Any, workspace_id: str, form_id: str
) -> Optional[Dict[str, Any]]:
    """The answers of one stored response as plain data, or None when they
    cannot be read. ``blob`` is ``doc.answers`` as the row holds it: the
    encrypted bytes in BSON extended JSON (``{"$binary": ...}``), or the plain
    dictionary of a response that was never encrypted."""
    try:
        if isinstance(blob, dict) and "$binary" in blob:
            raw = base64.b64decode(blob["$binary"]["base64"])
            plain = crypto_service.decrypt(
                workspace_id=workspace_id, form_id=form_id, data=raw
            )
            decoded = json.loads(plain)
        elif isinstance(blob, dict):
            decoded = blob
        elif isinstance(blob, (str, bytes)):
            decoded = json.loads(blob)
        else:
            return None
    except (UnreadableCiphertext, ValueError, KeyError, TypeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _view(row: ReportRow, answers: Optional[Dict[str, Any]]) -> ResponseView:
    return ResponseView(
        created_at=row.created_at,
        form_version=row.form_version,
        anonymous=row.anonymous,
        ending_id=row.ending_id,
        source=row.source,
        answers=answers,
    )


def _order(dimension: Optional[DimensionPlan], keys: Sequence[str], catalogue: Catalogue) -> List[str]:
    """The groups of a dimension in the order a reader expects: the form's own
    option order, numbers ascending, time forward, fixed words in their order;
    "Other" and the removed option last."""
    if dimension is None:
        return [ALL_KEY]
    present = list(keys)
    if dimension.field is not None:
        found = dimension.field
        if found.kind in (CHOICE, CHOICES):
            options = [option_id for option_id, _ in found.options]
            tail = [k for k in (OTHER_KEY, REMOVED_KEY) if k in present]
            return options + tail
        if found.kind in (YES_NO, CALCULATED):
            return [k for k, _ in YES_NO_GROUPS]
        if found.kind == SCALE:
            return sorted(present, key=int)
        return sorted(present)
    builtin = dimension.builtin
    if builtin in _FIXED:
        return list(_FIXED[builtin])
    if builtin == FORM_VERSION:
        return sorted(present, key=int)
    if builtin == ENDING:
        known = [i for i, _ in catalogue.endings]
        tail = [k for k in (NONE_KEY, REMOVED_KEY) if k in present]
        return [k for k in known if k in present] + tail
    if builtin == SUBMITTED_AT:
        return sorted(present)
    return sorted(present, key=lambda k: (k == NONE_KEY, k))


def _is_ordered_axis(dimension: Optional[DimensionPlan]) -> bool:
    """A time or numeric axis keeps all its groups (a top-N cut would break it)."""
    if dimension is None:
        return False
    if dimension.time:
        return True
    if dimension.field is not None and dimension.field.kind == SCALE:
        return True
    return dimension.builtin == FORM_VERSION


def assemble(card: CardPlan, totals: CardTotals, catalogue: Catalogue) -> Dict[str, Any]:
    """A card's result: its groups ordered and labelled, the biggest ``100``
    kept when the dimension has more, the rest summed."""
    dimension = card.dimension
    labels = labels_for(dimension, catalogue)
    order = _order(dimension, list(totals.groups), catalogue)
    # a fixed or option group nobody is in is listed with zero
    zero_fill = dimension is not None and (
        (dimension.field is not None and dimension.field.kind in (CHOICE, CHOICES, YES_NO, CALCULATED))
        or dimension.builtin in _FIXED
    )
    ordered: List[GroupTotals] = []
    seen = set()
    for key in order:
        group = totals.groups.get(key)
        if group is None:
            if not zero_fill:
                continue
            group = GroupTotals(
                key,
                0,
                [0 if m.agg == COUNT else None for m in card.measures],
                [0] * len(card.measures),
            )
        ordered.append(group)
        seen.add(key)
    # keys the order did not name (a key no option explains is a bug; kept, last)
    ordered.extend(g for k, g in totals.groups.items() if k not in seen)
    other_n, other_count = totals.other_n, totals.other_count
    truncated = totals.truncated
    if not _is_ordered_axis(dimension) and len(ordered) > limits.GROUPS_RETURNED_MAX:
        ranked = sorted(range(len(ordered)), key=lambda i: (-ordered[i].n, i))
        keep = set(ranked[: limits.GROUPS_RETURNED_MAX])
        other_n += sum(g.n for i, g in enumerate(ordered) if i not in keep)
        other_count += len(ordered) - len(keep)
        ordered = [g for i, g in enumerate(ordered) if i in keep]
        truncated = True
    groups = [
        {
            "key": g.key,
            "label": labels.get(g.key, g.key),
            "n": g.n,
            "values": g.values,
            "valueN": g.value_n,
        }
        for g in ordered
    ]
    return {
        "id": card.id,
        "n": totals.n,
        "answered": totals.answered,
        "skipped": totals.skipped,
        "groups": groups,
        "otherGroups": {"n": other_n, "count": other_count},
        "truncated": truncated,
        # a multiple choice card counts a response in each option it chose
        "multiple": bool(
            dimension is not None
            and dimension.field is not None
            and dimension.field.kind == CHOICES
        ),
    }


class ReportEngine:
    def __init__(self, repo: PostgresReportRepository):
        self._repo = repo

    # ------------------------------------------------------------ SQL cards
    async def count_cards(
        self,
        scope: ResponseScope,
        plan: Plan,
        catalogue: Catalogue,
        total: int,
    ) -> Dict[str, Dict[str, Any]]:
        """The cards that read no answer, counted in SQL (``total``: the
        responses in the set)."""
        results: Dict[str, Dict[str, Any]] = {}
        counted: Dict[Tuple[str, Optional[str]], List[Tuple[Any, int]]] = {}
        endings = frozenset(i for i, _ in catalogue.endings)
        for card in plan.sql_cards:
            dimension = card.dimension
            measures = len(card.measures)
            groups: Dict[str, GroupTotals] = {}
            if dimension is None:
                groups[ALL_KEY] = GroupTotals(ALL_KEY, total, [total] * measures, [total] * measures)
            else:
                assert dimension.builtin is not None
                ask = (dimension.builtin, dimension.bucket)
                if ask not in counted:
                    counted[ask] = await self._repo.group_counts(
                        scope,
                        plan.filters,
                        dimension.builtin,
                        dimension.bucket,
                        str(plan.tz),
                    )
                for value, n in counted[ask]:
                    key = _sql_key(dimension, value, endings)
                    if key in groups:
                        # several stored ending ids that no version has any more
                        groups[key].n += n
                        groups[key].values = [groups[key].n] * measures
                        groups[key].value_n = [groups[key].n] * measures
                    else:
                        groups[key] = GroupTotals(key, n, [n] * measures, [n] * measures)
            totals = CardTotals(
                n=total, answered=total, skipped=0, groups=groups
            )
            results[card.id] = assemble(card, totals, catalogue)
        return results

    # ---------------------------------------------------------------- drill-down
    def _drill_batch(
        self,
        batch: Sequence[ReportRow],
        accumulator: CardAccumulator,
        clauses: Sequence[ClausePlan],
        group: str,
        workspace_id: str,
        form_id: str,
        room: int,
    ) -> Tuple[List[ReportRow], int]:
        """The responses of ``batch`` that met the conditions and fell in
        ``group``, in order, stopping at ``room`` of them (on a worker thread);
        and how many of the batch it read."""
        found: List[ReportRow] = []
        read = 0
        for row in batch:
            read += 1
            if row.answers is None:
                continue
            answers = stored_answers(row.answers, workspace_id, form_id)
            if clauses and not all(clause_matches(c, answers) for c in clauses):
                continue
            if group in accumulator.group_keys(_view(row, answers)):
                found.append(row)
                if len(found) >= room:
                    break
        return found, read

    async def drill(
        self,
        scope: ResponseScope,
        workspace_id: str,
        form_id: str,
        plan: Plan,
        card: CardPlan,
        group: str,
        catalogue: Catalogue,
        after: Optional[Any],
        size: int,
    ) -> DrillPage:
        """Fill a page with the responses of ``group`` of ``card``: the same
        keyset pass as a report, from ``after``, stopping when the page is full or
        ``DRILL_SCAN_MAX`` responses were read (the page is then short and the
        pass not ``exhausted``: the caller asks again from the cursor)."""
        endings = frozenset(i for i, _ in catalogue.endings)
        accumulator = CardAccumulator(card, plan.tz, endings)
        found: List[ReportRow] = []
        scanned = 0
        cursor = after
        pending = asyncio.ensure_future(self._repo.batch(scope, plan.filters, cursor, limits.BATCH_SIZE))
        try:
            while True:
                batch = await pending
                pending = None
                if not batch:
                    return DrillPage(found, None, scanned, True)
                room = size - len(found)
                matched, read = await run_in_threadpool(
                    self._drill_batch, batch, accumulator, plan.clauses, group, workspace_id, form_id, room
                )
                scanned += read
                found.extend(matched)
                if len(found) >= size:
                    # where the last response of the page was: the next page starts after it
                    return DrillPage(found, found[-1].cursor, scanned, False)
                cursor = batch[-1].cursor
                if scanned >= limits.DRILL_SCAN_MAX:
                    return DrillPage(found, cursor, scanned, False)
                pending = asyncio.ensure_future(
                    self._repo.batch(scope, plan.filters, cursor, limits.BATCH_SIZE)
                )
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
            elif pending is not None and not pending.cancelled():
                pending.exception()

    # ----------------------------------------------------------- the one pass
    def _consume(
        self,
        batch: Sequence[ReportRow],
        accumulators: Sequence[CardAccumulator],
        workspace_id: str,
        form_id: str,
        clauses: Sequence[ClausePlan] = (),
    ) -> Tuple[int, int]:
        """Decrypt a batch and feed every accumulator the responses that meet the
        conditions on answers (on a worker thread); returns ``(responses that
        could not be read, responses that met the conditions)``."""
        unreadable = 0
        matched = 0
        for row in batch:
            if row.answers is None:
                # a stub with an empty ``answers`` key: not a response
                continue
            answers = stored_answers(row.answers, workspace_id, form_id)
            if answers is None:
                unreadable += 1
            if clauses and not all(clause_matches(c, answers) for c in clauses):
                continue
            matched += 1
            view = _view(row, answers)
            for accumulator in accumulators:
                accumulator.feed(view)
        return unreadable, matched

    async def scan(
        self,
        scope: ResponseScope,
        workspace_id: str,
        form_id: str,
        plan: Plan,
        catalogue: Catalogue,
    ) -> ScanResult:
        """The cards that read answers, from one pass over the responses."""
        endings = frozenset(i for i, _ in catalogue.endings)
        accumulators = [
            CardAccumulator(card, plan.tz, endings) for card in plan.scan_cards
        ]
        scanned = 0
        unreadable = 0
        matched = 0
        # the next batch is read while this one is decrypted and added up (two
        # batches in memory at most)
        pending = asyncio.ensure_future(
            self._repo.batch(scope, plan.filters, None, limits.BATCH_SIZE)
        )
        try:
            while True:
                batch = await pending
                pending = None
                if not batch:
                    break
                scanned += len(batch)
                if scanned > limits.REPORT_MAX_ROWS:
                    # responses arrived while the pass ran: refuse, never cut
                    raise TooManyRows(scanned)
                pending = asyncio.ensure_future(
                    self._repo.batch(
                        scope, plan.filters, batch[-1].cursor, limits.BATCH_SIZE
                    )
                )
                bad, met = await run_in_threadpool(
                    self._consume, batch, accumulators, workspace_id, form_id, plan.clauses
                )
                unreadable += bad
                matched += met
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
            elif pending is not None and not pending.cancelled():
                pending.exception()  # (consumed: nobody awaits it any more)
        # a value too large or strange to add up (``CardAccumulator.finish``)
        results = {
            accumulator.plan.id: assemble(accumulator.plan, accumulator.finish(), catalogue)
            for accumulator in accumulators
        }
        unreadable += sum(accumulator.unreadable for accumulator in accumulators)
        if unreadable:
            logger.warning("report: {} stored answers could not be read", unreadable)
        return ScanResult(
            cards=results,
            scanned=scanned,
            unreadable=unreadable,
            matched=matched,
        )


def _sql_key(dimension: DimensionPlan, value: Any, endings: frozenset) -> str:
    """The group key of a value a plaintext dimension was counted under in SQL."""
    if dimension.builtin == SUBMITTED_AT:
        moment = value if isinstance(value, dt.datetime) else None
        return bucket_key(moment.date(), dimension.bucket or "day") if moment else NONE_KEY
    if dimension.builtin == ENDING:
        if value == NONE_KEY:
            return NONE_KEY
        return value if value in endings else REMOVED_KEY
    return str(value)
