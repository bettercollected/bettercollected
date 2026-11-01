"""The lookup route's rules (``POST /workspaces/{id}/forms/{form_id}/address-lookup``).

The route is public, like the respondent's form, so what it accepts is held to
what a respondent of a published form can send:

- it answers only while ``ADDRESS_QUESTION_ENABLED`` and ``ADDRESS_LOOKUP_ENABLED``
  are on, for a form of this workspace that has a published version, and a
  question of that version that is an address question asking for a lookup
  (Dutch addresses allowed, its own switch not off), not internal. The form
  must also be one a respondent without an account may fill in right now, as
  the submit gate reads it (``services/form_availability.py`` and the
  workspace form's own flags): not hidden, open (not before its open date, not
  from its close date), not full (its response limit) and, when it is private
  (restricted to responder groups), asked by a signed-in respondent one of the
  form's groups admits (the submit gate's own check; the signed-in user is read
  only for a private form, never for a public one). Everything else is one and
  the same 404;
- the input is a postcode and a house number, strictly validated (422
  ``invalid_input``); the house number addition is never sent;
- 30 requests per client and form and 600 per form per window (429);
- the provider call is one attempt, at most ``MAX_IN_FLIGHT`` at a time per
  process (the next one is "unavailable" at once), switched off for
  ``BREAKER_OPEN_S`` after ``BREAKER_FAILURES`` failures in a row, and its
  answers are cached in memory (found ``FOUND_TTL_S``, not found
  ``NOT_FOUND_TTL_S``, ``CACHE_SIZE`` entries, errors never) under the two
  validated values; the calls themselves are capped per process by rate
  (``CALLS_PER_SECOND`` / ``CALLS_PER_MINUTE``), and per form
  (``FORM_CALLS_PER_MINUTE``, inside the process's) so that one form cannot use
  up the process's share: over either the answer is "unavailable" without a
  call (a refusal by the budget still counts as one of the client's lookups:
  the limiter counts before the call, and it has no refund);
- what costs a database query before a form is known to be servable is
  bounded: a form that is not servable is remembered for ``FORM_CACHE_S`` too,
  and one client may make at most ``COARSE_FACTOR`` times the per-client limit
  of requests per window to this process, whatever form they name (in memory,
  no query). Every in-memory table is a bounded LRU: the entry that was used
  longest ago goes first, so a flood of new keys cannot reset the counters of
  the clients that are active;
- nothing is stored and nothing that was asked is logged: counts and our own
  failure codes only.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from http import HTTPStatus
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    FrozenSet,
    Iterator,
    Optional,
    Tuple,
)

from bson.errors import InvalidId
from common.address import canonical_nl_postcode, is_nl_house_number
from common.ids import RecordId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.response_scope import response_scope
from backend.app.services import form_availability
from backend.app.services.address_lookup import provider
from backend.app.services.address_lookup.mode import (
    ADDRESS_TYPE,
    address_lookup_enabled,
    question_looks_up,
)
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.utils.client_ip import rate_limit_key
from common.settings.loader import live

CLIENT_SCOPE = "address-lookup"
FORM_SCOPE = "address-lookup-form"
FORM_CACHE_S = 30.0
FORM_CACHE_SIZE = 2048
NEGATIVE_CACHE_SIZE = 2048
COARSE_FACTOR = 4
COARSE_SIZE = 4096
FOUND_TTL_S = 6 * 3600.0
NOT_FOUND_TTL_S = 600.0
CACHE_SIZE = 2048
MAX_IN_FLIGHT = 8
# outbound calls to the provider per process, over a second and over a minute
CALLS_PER_SECOND = 10
CALLS_PER_MINUTE = 300
# the share of one form, inside the process's
FORM_CALLS_PER_MINUTE = 60
FORM_BUDGET_SIZE = 2048
BUDGET_LOG_EVERY_S = 60.0
ACCESS_CACHE_SIZE = 2048
BREAKER_FAILURES = 5
BREAKER_OPEN_S = 30.0
RETRY_AFTER_S = 30
FIELD_ID_MAX = 64

UNAVAILABLE_CODE = "lookup_unavailable"


@dataclass(frozen=True)
class _Servable:
    form_id: str
    fields: FrozenSet[str]
    loaded_at: float
    # (open date, close date) as stored: judged at every call, not at load
    dates: Tuple[Any, Any] = (None, None)
    # restricted to responder groups: who asks decides, never this entry
    private: bool = False

    def is_open(self) -> bool:
        opens, closes = self.dates
        return (
            form_availability.date_unavailability(
                {"form_open_date": opens, "form_close_date": closes}
            )
            is None
        )


def _put(table: "OrderedDict[Any, Any]", key: Any, value: Any, size: int) -> None:
    """Store ``value`` as the most recently used entry; over ``size`` the
    least recently used entries go."""
    table[key] = value
    table.move_to_end(key)
    while len(table) > size:
        table.popitem(last=False)


class _CallBudget:
    """How many provider calls may be made: at most ``per_second`` in any
    second and ``per_minute`` in any minute (a sliding window over the times of
    the calls that were made; None: no limit of that kind)."""

    def __init__(self) -> None:
        self._made: Deque[float] = deque()

    def allows(self, now: float, per_second: Optional[int], per_minute: Optional[int]) -> bool:
        made = self._made
        while made and now - made[0] >= 60.0:
            made.popleft()
        if per_minute is not None and len(made) >= per_minute:
            return False
        if per_second is not None:
            recent = 0
            for stamp in reversed(made):
                if now - stamp >= 1.0:
                    break
                recent += 1
            if recent >= per_second:
                return False
        return True

    def record(self, now: float) -> None:
        self._made.append(now)

    def take(self, now: float, per_second: Optional[int] = None, per_minute: Optional[int] = None) -> bool:
        """``allows`` and, when it does, ``record``. The limits default to the
        process's (``CALLS_PER_SECOND`` / ``CALLS_PER_MINUTE``)."""
        if per_second is None and per_minute is None:
            per_second, per_minute = CALLS_PER_SECOND, CALLS_PER_MINUTE
        if not self.allows(now, per_second, per_minute):
            return False
        self.record(now)
        return True


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={"code": UNAVAILABLE_CODE, "message": "Lookup is not available right now."},
        headers={"Retry-After": str(RETRY_AFTER_S)},
    )


def _invalid() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": "invalid_input", "message": "Enter a postcode and a house number."},
    )


def _walk(fields: Any) -> Iterator[Any]:
    for field in fields or []:
        yield field
        properties = getattr(field, "properties", None)
        yield from _walk(getattr(properties, "fields", None))


def lookup_fields(form: Any) -> FrozenSet[str]:
    """The ids of the questions of ``form`` a lookup may be asked for."""
    found = set()
    for field in _walk(getattr(form, "fields", None)):
        kind = getattr(getattr(field, "type", None), "value", getattr(field, "type", None))
        if (
            kind == ADDRESS_TYPE
            and getattr(field, "id", None)
            and not getattr(field, "internal", None)
            and question_looks_up(field)
        ):
            found.add(str(field.id))
    return frozenset(found)


class AddressLookupService:
    def __init__(
        self,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        form_repo: PostgresFormRepository,
        rate_limiter: FixedWindowRateLimiter,
        response_repo: Any,
        transport: Optional[provider.Transport] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._limiter = rate_limiter
        self._responses = response_repo
        self._transport = transport
        self._monotonic = monotonic
        self._forms_cache: "OrderedDict[Tuple[str, str], _Servable]" = OrderedDict()
        # (workspace, form) that were not servable -> when that was found out
        self._unservable: "OrderedDict[Tuple[str, str], float]" = OrderedDict()
        # client key -> (window start, requests in it): in memory, no query
        self._coarse: "OrderedDict[str, Tuple[float, int]]" = OrderedDict()
        self._budget = _CallBudget()
        # form id -> its share of the budget (a bounded LRU)
        self._form_budgets: "OrderedDict[str, _CallBudget]" = OrderedDict()
        self._budget_logged_at: Optional[float] = None
        # (workspace, form id, user) -> (may the user submit, when it was read)
        self._access: "OrderedDict[Tuple[str, str, str], Tuple[bool, float]]" = OrderedDict()
        # "1015CS 12" -> (street, city) or None, with the time it expires
        self._results: "OrderedDict[str, Tuple[Optional[provider.Place], float]]" = OrderedDict()
        self._in_flight = 0
        self._failures = 0
        self._open_until = 0.0
        # outcome -> count, for tests and a health look; never what was asked
        self.counts: Dict[str, int] = {}

    # ------------------------------------------------------------ the route

    async def lookup(
        self,
        workspace_id: RecordId,
        form_ref: str,
        field_id: str,
        postcode: str,
        house_number: str,
        client: Optional[str],
        user_loader: Optional[Callable[[], Awaitable[Any]]] = None,
    ) -> Dict[str, str]:
        """``user_loader``: reads the signed-in user (None when there is
        none); called only for a private form."""
        if not address_lookup_enabled():
            raise _not_found()
        self._coarse_limit(client)
        form = await self._servable(workspace_id, form_ref)
        if form is None or field_id not in form.fields or not form.is_open():
            raise _not_found()
        if form.private and not await self._may_submit(
            workspace_id, form_ref, form, user_loader
        ):
            raise _not_found()
        key = self._key(postcode, house_number)
        if key is None:
            raise self._count("invalid", _invalid())
        await self._limit(form.form_id, client)
        place = self._cached(key)
        if place is _MISS:
            place = await self._ask(key, form.form_id)
        if place is None:
            self._count("not_found")
            return {"status": "not_found"}
        self._count("found")
        return {"status": "found", "street": place.street, "city": place.city}

    # ------------------------------------------------------------- helpers

    def _count(self, outcome: str, result: Any = None) -> Any:
        self.counts[outcome] = self.counts.get(outcome, 0) + 1
        return result

    @staticmethod
    def _key(postcode: Any, house_number: Any) -> Optional[str]:
        canonical = canonical_nl_postcode(postcode if isinstance(postcode, str) else None)
        number = house_number.strip() if isinstance(house_number, str) else ""
        if canonical is None or not is_nl_house_number(number):
            return None
        return canonical.replace(" ", "") + " " + number

    def _coarse_limit(self, client: Optional[str]) -> None:
        """Before anything is read from the database: a client that sends far
        more than the per-client limit allows is answered 429 from memory. The
        per-process counters are a bounded LRU and hold only the rate-limit
        key, never what was asked."""
        api = live().api
        window = float(api.ADDRESS_LOOKUP_WINDOW_SECONDS)
        limit = max(1, int(api.ADDRESS_LOOKUP_PER_WINDOW)) * COARSE_FACTOR
        now = self._monotonic()
        who = rate_limit_key(client)
        started, used = self._coarse.get(who, (now, 0))
        if now - started >= window:
            started, used = now, 0
        if used >= limit:
            self._coarse.move_to_end(who)
            self._count("limited")
            raise HTTPException(
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                content="Too many lookups; try again later.",
                headers={"Retry-After": str(max(1, int(window - (now - started))))},
            )
        _put(self._coarse, who, (started, used + 1), COARSE_SIZE)

    async def _limit(self, form_id: str, client: Optional[str]) -> None:
        api = live().api
        window = api.ADDRESS_LOOKUP_WINDOW_SECONDS
        for scope, who, limit in (
            (CLIENT_SCOPE, f"{form_id}\n{rate_limit_key(client)}", api.ADDRESS_LOOKUP_PER_WINDOW),
            (FORM_SCOPE, form_id, api.ADDRESS_LOOKUP_FORM_PER_WINDOW),
        ):
            verdict = await self._limiter.hit(scope, who, limit, window)
            if not verdict.allowed:
                self._count("limited")
                raise HTTPException(
                    status_code=HTTPStatus.TOO_MANY_REQUESTS,
                    content="Too many lookups; try again later.",
                    headers={"Retry-After": str(verdict.retry_after)},
                )

    def _cached(self, key: str) -> Any:
        entry = self._results.get(key)
        if entry is None:
            return _MISS
        place, expires = entry
        if self._monotonic() >= expires:
            self._results.pop(key, None)
            return _MISS
        self._results.move_to_end(key)
        return place

    def _remember(self, key: str, place: Optional[provider.Place]) -> None:
        ttl = FOUND_TTL_S if place is not None else NOT_FOUND_TTL_S
        self._results[key] = (place, self._monotonic() + ttl)
        self._results.move_to_end(key)
        while len(self._results) > CACHE_SIZE:
            self._results.popitem(last=False)

    async def _ask(self, key: str, form_id: str = "") -> Optional[provider.Place]:
        now = self._monotonic()
        if now < self._open_until:
            self._count("unavailable")
            raise _unavailable()
        if self._in_flight >= MAX_IN_FLIGHT:
            self._count("unavailable")
            raise _unavailable()
        if not self._take_budget(form_id, now):
            self._count("budget")
            self._warn_budget(now)
            raise _unavailable()
        postcode, number = key.split(" ")
        transport = self._transport or provider.http_transport
        self._in_flight += 1
        try:
            body = await transport(provider.build_query(postcode, number))
            place = provider.parse_reply(body, postcode, number)
        except provider.LookupUnavailable as failed:
            self._failed(failed.code)
            raise _unavailable()
        except asyncio.CancelledError:
            raise
        except Exception as error:  # a bug or a library: never its text
            self._failed(type(error).__name__)
            raise _unavailable()
        finally:
            self._in_flight -= 1
        self._failures = 0
        self._remember(key, place)
        return place

    def _take_budget(self, form_id: str, now: float) -> bool:
        """One provider call from the form's share and the process's: both
        have room, then both are charged."""
        mine = self._form_budgets.get(form_id)
        if mine is None:
            mine = _CallBudget()
        elif form_id:
            self._form_budgets.move_to_end(form_id)
        if not mine.allows(now, None, FORM_CALLS_PER_MINUTE):
            return False
        if not self._budget.allows(now, CALLS_PER_SECOND, CALLS_PER_MINUTE):
            return False
        mine.record(now)
        self._budget.record(now)
        _put(self._form_budgets, form_id, mine, FORM_BUDGET_SIZE)
        return True

    def _warn_budget(self, now: float) -> None:
        """At most one line a minute: that the budget refused calls, counts
        only (never a form, a client or what was asked)."""
        last = self._budget_logged_at
        if last is not None and now - last < BUDGET_LOG_EVERY_S:
            return
        self._budget_logged_at = now
        logger.warning(
            "address lookup call budget reached: {n} refused so far",
            n=self.counts.get("budget", 0),
        )

    def _failed(self, code: str) -> None:
        self._failures += 1
        self._count("unavailable")
        if self._failures >= BREAKER_FAILURES:
            self._open_until = self._monotonic() + BREAKER_OPEN_S
            self._failures = 0
        logger.warning("address lookup unavailable: {code}", code=code)

    # ---------------------------------------------------------------- forms

    async def _servable(self, workspace_id: RecordId, form_ref: str) -> Optional[_Servable]:
        if not isinstance(form_ref, str) or not 0 < len(form_ref) <= 64:
            return None
        key = (str(workspace_id), form_ref)
        now = self._monotonic()
        cached = self._forms_cache.get(key)
        if cached is not None and now - cached.loaded_at < FORM_CACHE_S:
            self._forms_cache.move_to_end(key)
            return cached
        self._forms_cache.pop(key, None)
        missed = self._unservable.get(key)
        if missed is not None and now - missed < FORM_CACHE_S:
            self._unservable.move_to_end(key)
            return None
        self._unservable.pop(key, None)
        form = await self._load(workspace_id, form_ref, now)
        if form is not None:
            _put(self._forms_cache, key, form, FORM_CACHE_SIZE)
        else:
            _put(self._unservable, key, now, NEGATIVE_CACHE_SIZE)
        return form

    async def _load(
        self, workspace_id: RecordId, form_ref: str, now: float
    ) -> Optional[_Servable]:
        workspace_form = (
            await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_ref
            )
        )
        if workspace_form is None:
            return None
        settings = workspace_form.settings
        # A hidden form answers nobody (as the submit gate); a private one
        # (restricted to responder groups) answers the signed-in respondents
        # its groups admit, decided per user in ``_may_submit``.
        if settings is not None and settings.hidden:
            return None
        try:
            form_id = RecordId(workspace_form.form_id)
        except (InvalidId, TypeError, ValueError):
            return None
        # A form that holds as many responses as its limit takes no more:
        # counted once per cache lifetime, and only for a form with a limit.
        if form_availability.response_limit(settings) is not None:
            scope = await response_scope(
                self._workspace_forms, workspace_id, [str(workspace_form.form_id)]
            )
            count = await self._responses.count_responses_for_form_ids(scope)
            if form_availability.is_full(settings, count):
                return None
        published = await self._forms.get_latest_version_of_form(form_id)
        if published is None:
            return None
        fields = lookup_fields(published)
        if not fields:
            return None
        return _Servable(
            form_id=str(workspace_form.form_id),
            fields=fields,
            loaded_at=now,
            dates=(
                getattr(settings, "form_open_date", None),
                getattr(settings, "form_close_date", None),
            ),
            private=bool(getattr(settings, "private", False)),
        )

    async def _may_submit(
        self,
        workspace_id: RecordId,
        form_ref: str,
        form: _Servable,
        user_loader: Optional[Callable[[], Awaitable[Any]]],
    ) -> bool:
        """May the signed-in user fill in this private form? The submit gate's
        own question (``get_form_ids_in_workspace`` with the user: the groups
        of this workspace that admit them). No user, no lookup. The answer is
        kept per user (and form) for ``FORM_CACHE_S``: one user's access never
        serves another's."""
        user = await user_loader() if user_loader is not None else None
        sub = getattr(user, "sub", None)
        if not sub or not isinstance(sub, str):
            return False
        key = (str(workspace_id), form.form_id, sub)
        now = self._monotonic()
        known = self._access.get(key)
        if known is not None and now - known[1] < FORM_CACHE_S:
            self._access.move_to_end(key)
            return known[0]
        admitted = await self._workspace_forms.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=True,
            user=user,
            form_id_or_slug=form_ref,
        )
        allowed = form.form_id in {str(found) for found in admitted}
        _put(self._access, key, (allowed, now), ACCESS_CACHE_SIZE)
        return allowed


class _Miss:
    pass


_MISS = _Miss()
