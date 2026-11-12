"""Reports on a form's answers: who may ask, the catalogue, the query.

* **Who may.** ``response.read`` and ``analytics.read``, both on the form
  (``authorize(..., form_id=...)``: a restricted form is the 404 of an unknown
  form for a member it is closed to). Not ``analytics.read`` alone: the Privacy
  officer holds it, but nothing derived from answers is theirs to read, so they
  fail the first check. The switch (``mode.refuse_when_off``) is the router's
  first dependency, before this runs.
* **What may be used.** The form's reportable questions (``catalogue``), as the
  caller's field policy lets them see them (``policy.ReportFieldPolicy``): one
  seam, asked on every request; a question that is not visible is refused like
  one that does not exist.
* **How it runs.** ``engine``: cards that read no answer are counted in SQL;
  the others share one bounded pass over the answers, refused above
  ``REPORT_MAX_ROWS`` with the count, never partial. The aggregates of that
  pass are cached in this process against an exact change token (the count and
  a hash of every response's id and last change), so a new, edited, deleted or
  expired response, or a changed form, makes the next query read again. A cache
  entry holds aggregates only.
* **Limits.** ``REQUESTS_PER_WINDOW`` queries per user and form per window
  (429 ``rate_limited``), ``PASSES_AT_ONCE`` passes at once in this process
  (429 ``report_busy``).
* Running a report is not audited (reading the list is not either), and writes
  nothing.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import time
from collections import OrderedDict
from http import HTTPStatus
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.report_queries import PostgresReportRepository
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.services.reporting import definition as defs
from backend.app.services.reporting import limits
from backend.app.services.reporting.catalogue import Catalogue, build_catalogue
from backend.app.services.reporting.engine import ReportEngine, TooManyRows
from backend.app.services.reporting.policy import ReportFieldPolicy
from common.clock import utcnow
from common.ids import RecordId
from common.models.user import User

FORM_NOT_FOUND = "Form not found in the workspace."
TOO_MANY_CODE = "too_many_rows"
RATE_CODE = "rate_limited"
BUSY_CODE = "report_busy"
TIMEOUT_CODE = "report_timeout"
SLOT_SCOPE = "report-passes"
SLOT_CLIENT = "all"


def too_many_rows(count: int) -> HTTPException:
    return HTTPException(
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={
            "code": TOO_MANY_CODE,
            "message": (
                f"This selection has {count} responses; a report reads at most "
                f"{limits.REPORT_MAX_ROWS}. Narrow the dates or the form versions."
            ),
            "count": count,
            "max": limits.REPORT_MAX_ROWS,
        },
    )


class _Entry:
    """One cached pass: its aggregates and what they were computed against."""

    __slots__ = ("token", "revision", "stored", "cards", "scanned", "unreadable", "generated_at")

    def __init__(self, token, revision, cards, scanned, unreadable, generated_at):
        self.token = token
        self.revision = revision
        self.stored = time.monotonic()
        self.cards = cards
        self.scanned = scanned
        self.unreadable = unreadable
        self.generated_at = generated_at


class ReportService:
    def __init__(
        self,
        authorization_service,
        form_response_service,
        form_repo,
        report_repo: PostgresReportRepository,
        rate_limiter: FixedWindowRateLimiter,
        field_policy: Optional[ReportFieldPolicy] = None,
        engine: Optional[ReportEngine] = None,
    ):
        self._authorization = authorization_service
        self._responses = form_response_service
        self._forms = form_repo
        self._repo = report_repo
        self._limiter = rate_limiter
        self._policy = field_policy or ReportFieldPolicy()
        self._engine = engine or ReportEngine(report_repo)
        self._passes = asyncio.Semaphore(limits.PASSES_AT_ONCE)
        self._cache: "OrderedDict[tuple, _Entry]" = OrderedDict()
        self._catalogues: "OrderedDict[tuple, Catalogue]" = OrderedDict()

    # ------------------------------------------------------------------ gate
    async def _authorize(self, user: User, workspace_id: RecordId, form_id: str) -> None:
        """``response.read``, then ``analytics.read``, both on the form: the
        first one the caller lacks decides (a Privacy officer fails the first)."""
        for permission in (Permission.RESPONSE_READ, Permission.ANALYTICS_READ):
            await self._authorization.authorize(
                user, permission, workspace_id, form_id=form_id
            )

    async def _take_rate_limit(self, workspace_id: RecordId, form_id: str, user: User) -> None:
        verdict = await self._limiter.admit(
            f"report:{workspace_id}:{form_id}",
            str(user.id),
            limits.REQUESTS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS,
                content={
                    "code": RATE_CODE,
                    "message": f"Too many report queries. Try again in {verdict.retry_after} seconds.",
                },
                headers={"Retry-After": str(verdict.retry_after)},
            )

    # -------------------------------------------------------------- catalogue
    async def _catalogue(self, form_id: str) -> Tuple[Catalogue, Any]:
        """The form's catalogue and the form's revision it was built at."""
        revision = await self._forms.revision_of(form_id)
        key = (form_id, revision)
        cached = self._catalogues.get(key)
        if cached is not None:
            self._catalogues.move_to_end(key)
            return cached, revision
        current = await self._forms.get_form_document_by_id(form_id)
        if current is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, FORM_NOT_FOUND)
        versions = await self._forms.get_versions_of_form(form_id)
        catalogue = build_catalogue(
            [
                (int(v.version), v.model_dump(mode="json", exclude_none=True))
                for v in versions
                if v.version is not None
            ],
            current.model_dump(mode="json", exclude_none=True),
        )
        self._catalogues[key] = catalogue
        while len(self._catalogues) > limits.CATALOGUE_CACHE_SIZE:
            self._catalogues.popitem(last=False)
        return catalogue, revision

    async def _visible(
        self, user: User, workspace_id: RecordId, form_id: str
    ) -> Tuple[Catalogue, Any, str]:
        """The catalogue as this caller may use it (the field policy), the
        form's revision and the fingerprint of the caller's view."""
        catalogue, revision = await self._catalogue(form_id)
        visible = await self._policy.visible_fields(
            user, workspace_id, form_id, catalogue.keys()
        )
        return catalogue.restricted_to(visible), revision, self._policy.fingerprint(visible)

    # ----------------------------------------------------------------- fields
    async def fields(self, user: User, workspace_id: RecordId, form_id: str) -> Dict[str, Any]:
        """What the caller may build a report from: the reportable questions
        (kind, whether it groups, which aggregates, options) and the built-in
        dimensions."""
        await self._authorize(user, workspace_id, form_id)
        catalogue, _, _ = await self._visible(user, workspace_id, form_id)
        return {
            **catalogue.as_json(),
            "limits": {
                "maxRows": limits.REPORT_MAX_ROWS,
                "maxCards": limits.CARDS_MAX,
                "maxMeasures": limits.MEASURES_MAX,
            },
        }

    # ------------------------------------------------------------------ query
    async def query(
        self, user: User, workspace_id: RecordId, form_id: str, body: bytes
    ) -> Dict[str, Any]:
        await self._authorize(user, workspace_id, form_id)
        await self._take_rate_limit(workspace_id, form_id, user)
        definition = defs.parse(body)
        catalogue, revision, view = await self._visible(user, workspace_id, form_id)
        plan = defs.validate(definition, catalogue)
        scope = await self._responses.scope(workspace_id, [form_id])
        now = utcnow()

        if plan.needs_answers:
            count, digest = await self._repo.token(scope, plan.filters)
            if count > limits.REPORT_MAX_ROWS:
                raise too_many_rows(count)
        else:
            count = await self._repo.count(*self._repo.report_where(scope, plan.filters))
            digest = 0
        cards: Dict[str, Dict[str, Any]] = {}
        scanned = 0
        notices = []
        generated_at = now
        if plan.sql_cards:
            cards.update(await self._engine.count_cards(scope, plan, catalogue, count))
        if plan.needs_answers:
            entry = await self._scan(
                user, workspace_id, form_id, plan, catalogue, revision, view,
                (count, digest), scope,
            )
            cards.update(entry.cards)
            scanned = entry.scanned
            generated_at = entry.generated_at
            if entry.unreadable:
                notices.append("unreadable_answers")
        if any(card["truncated"] for card in cards.values()):
            notices.append("groups_truncated")
        return {
            "definitionHash": definition.digest(),
            "token": _token(count, digest, revision),
            "generatedAt": generated_at.isoformat(),
            "n": count,
            "scanned": scanned,
            "cards": [cards[card.id] for card in plan.cards],
            "notices": notices,
        }

    async def _give_back_slot(self) -> None:
        """Give the pass's place among the replicas' back. Never fails the
        report: the window frees it anyway."""
        try:
            await self._limiter.release(
                SLOT_SCOPE, SLOT_CLIENT, limits.PASS_SLOTS_WINDOW_SECONDS
            )
        except Exception as error:  # noqa: BLE001 - only the place is lost
            logger.warning("report: could not give back a pass place ({})", type(error).__name__)

    async def _scan(
        self, user, workspace_id, form_id, plan, catalogue, revision, view, token, scope
    ) -> _Entry:
        key = (str(workspace_id), form_id, plan.scan_digest(), view)
        # the deletion-request state is in another table than the token reads:
        # an answer card narrowed by it is always computed afresh
        cacheable = not plan.filters.status
        entry = self._cache.get(key) if cacheable else None
        if (
            entry is not None
            and entry.token == token
            and entry.revision == revision
            and time.monotonic() - entry.stored < limits.CACHE_SECONDS
        ):
            self._cache.move_to_end(key)
            return _copy(entry)
        try:
            await asyncio.wait_for(self._passes.acquire(), limits.PASS_WAIT_SECONDS)
        except asyncio.TimeoutError:
            raise _busy() from None
        try:
            # a place among the passes of every replica, not only of this one
            verdict = await self._limiter.admit(
                SLOT_SCOPE,
                SLOT_CLIENT,
                limits.PASSES_ACROSS_REPLICAS,
                limits.PASS_SLOTS_WINDOW_SECONDS,
            )
            if not verdict.allowed:
                raise _busy(min(verdict.retry_after, 5))
            try:
                # a time budget: a pass that is stuck or starved is cancelled
                # (its batch in flight finishes, no more are read) and its
                # places are given back, so it cannot hold a worker
                result = await asyncio.wait_for(
                    self._engine.scan(scope, str(workspace_id), form_id, plan, catalogue),
                    limits.PASS_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning("report: a pass ran over its {} s budget", limits.PASS_SECONDS)
                raise HTTPException(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    content={
                        "code": TIMEOUT_CODE,
                        "message": "This report took too long to compute. Narrow the dates or the form versions, or try again.",
                    },
                ) from None
            except TooManyRows as many:
                raise too_many_rows(many.count) from None
            finally:
                await self._give_back_slot()
        finally:
            self._passes.release()
        entry = _Entry(
            token, revision, result.cards, result.scanned, result.unreadable, utcnow()
        )
        if cacheable:
            self._cache[key] = entry
            self._cache.move_to_end(key)
            while len(self._cache) > limits.CACHE_SIZE:
                self._cache.popitem(last=False)
        return _copy(entry)


def _busy(retry_after: int = 2) -> HTTPException:
    return HTTPException(
        HTTPStatus.TOO_MANY_REQUESTS,
        content={
            "code": BUSY_CODE,
            "message": "Other reports are being computed. Try again in a moment.",
        },
        headers={"Retry-After": str(retry_after)},
    )


def _copy(entry: _Entry) -> _Entry:
    """The entry handed out: its cards copied, so nothing a caller does to a
    result reaches the cache."""
    clone = _Entry(
        entry.token, entry.revision, copy.deepcopy(entry.cards),
        entry.scanned, entry.unreadable, entry.generated_at,
    )
    return clone


def _token(count: int, digest: int, revision: Any) -> str:
    raw = f"{count}:{digest}:{revision}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]
