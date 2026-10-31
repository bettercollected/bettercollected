"""Whether a form still accepts responses: its open date, its close date and
its response limit, read one way.

A form's close date (``WorkspaceFormSettings.form_close_date``) is an instant.
The form is closed from that instant on (``now >= close``); before it, or
without a date, it is open. The open date (``form_open_date``) is the same
kind of instant the other way round: the form is not open yet before it
(``now < open``) and open from that instant on. The server's clock decides,
never the respondent's.

The response limit (``response_limit``) is a number of stored responses: a
form that holds that many takes no more (``form_full``). Deleting a response
frees its slot. The count is the server's: the submit gate checks it first and
the insert checks it again under a lock (``save_form_response``), so
concurrent submissions never pass the limit. Edits of an existing response and
deletion requests are never affected by any of the three.

A submission is judged at the time the backend received the request
(``request.state.received_at``, stamped before the body is read by
``middlewares/received_at.py``), so an upload that started before the close
still counts. Behind a proxy that buffers request bodies (nginx's default
``proxy_request_buffering on``) the backend only sees the request once the
upload has finished, so there the stamp is "upload finished". The stamp
counts for at most ``MAX_ARRIVAL_WINDOW``: a request still being handled
longer than that after it arrived is judged at the current time, so a
client cannot keep a request open past the close and still get in.

Stored values come in several spellings: the browser's ``...Z`` with
milliseconds, an offset such as ``+02:00``, a value without an offset (read
as UTC, as the webapp reads it), a ``datetime``, and ``""`` for "no date".
Anything that does not parse as an ISO 8601 instant also counts as no date:
values written before the settings were validated must never close a form
nor break the listing. New values are checked on the way in
(``normalized_close_date``, used by the settings PATCH).

Used by the submit gate (``ensure_accepting_responses``), the respondent's
read of the published form and the public listing, so all three agree.
"""

from __future__ import annotations

import datetime as dt
from http import HTTPStatus
from typing import Any, Mapping, Optional

from common import clock

from backend.app.exceptions import HTTPException

FORM_CLOSED = "form_closed"
FORM_CLOSED_MESSAGE = "This form is closed and no longer accepts responses."
FORM_NOT_OPEN = "form_not_open"
FORM_NOT_OPEN_MESSAGE = "This form is not open yet."
FORM_FULL = "form_full"
FORM_FULL_MESSAGE = "This form has received all the responses it accepts."
# The read of an unavailable form's published version for a respondent: a stub
# with one of these markers instead of the questions (services/form_service.py).
UNAVAILABLE_CLOSED = "closed"
UNAVAILABLE_NOT_OPEN = "not_yet_open"
UNAVAILABLE_FULL = "full"
UNAVAILABLE_REASONS = (UNAVAILABLE_CLOSED, UNAVAILABLE_NOT_OPEN, UNAVAILABLE_FULL)
# The most responses a limit can name (a sanity bound, well inside int4).
MAX_RESPONSE_LIMIT = 1_000_000
# How long after it arrived a submission is still judged at its arrival time.
MAX_ARRIVAL_WINDOW = dt.timedelta(minutes=10)


def now() -> dt.datetime:
    """The server's current time (aware UTC), read through ``common.clock``
    so a test fixes it in one place."""
    return clock.utcnow()


def parse_instant(value: Any) -> Optional[dt.datetime]:
    """``value`` as an aware UTC instant, or None for no (usable) date."""
    if isinstance(value, dt.datetime):
        instant = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            instant = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if instant.tzinfo is None or instant.utcoffset() is None:
        instant = instant.replace(tzinfo=dt.timezone.utc)
    try:
        return instant.astimezone(dt.timezone.utc)
    except (OverflowError, ValueError):
        return None


def _setting(settings: Any, key: str) -> Any:
    if settings is None:
        return None
    if isinstance(settings, Mapping):
        return settings.get(key)
    return getattr(settings, key, None)


def _close_value(settings: Any) -> Any:
    return _setting(settings, "form_close_date")


def closes_at(settings: Any) -> Optional[dt.datetime]:
    """The instant the form closes (aware UTC), or None when it has none.
    ``settings`` is a ``WorkspaceFormSettings`` or its stored dict."""
    return parse_instant(_close_value(settings))


def opens_at(settings: Any) -> Optional[dt.datetime]:
    """The instant the form opens (aware UTC), or None when it has none."""
    return parse_instant(_setting(settings, "form_open_date"))


def response_limit(settings: Any) -> Optional[int]:
    """The number of responses the form accepts, or None for no limit. A
    stored value that is not a positive whole number counts as no limit:
    nothing writes one (``normalized_response_limit``), and a stray value must
    never close a form."""
    value = _setting(settings, "response_limit")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def is_full(settings: Any, count: int) -> bool:
    """Whether ``count`` stored responses use up the form's limit."""
    limit = response_limit(settings)
    return limit is not None and count >= limit


def is_closed(settings: Any, now: Optional[dt.datetime] = None) -> bool:
    """Whether the form no longer accepts responses at ``now`` (default: the
    current time). Closed on the close instant itself."""
    close = closes_at(settings)
    if close is None:
        return False
    return (now or clock.utcnow()) >= close


def decision_time(
    received_at: Optional[dt.datetime], now: Optional[dt.datetime] = None
) -> dt.datetime:
    """The time a submission is judged at: when it arrived, unless that was
    more than ``MAX_ARRIVAL_WINDOW`` ago (then the current time)."""
    current = now or clock.utcnow()
    if received_at is None or current - received_at > MAX_ARRIVAL_WINDOW:
        return current
    return received_at


def date_unavailability(
    settings: Any, now: Optional[dt.datetime] = None
) -> Optional[str]:
    """Why the form's dates keep respondents out at ``now``:
    ``"closed"``, ``"not_yet_open"``, or None. Closed wins (only a stored pair
    with the open date after the close date can be both)."""
    current = now or clock.utcnow()
    close = closes_at(settings)
    if close is not None and current >= close:
        return UNAVAILABLE_CLOSED
    opens = opens_at(settings)
    if opens is not None and current < opens:
        return UNAVAILABLE_NOT_OPEN
    return None


def is_unavailable_by_date(settings: Any, now: Optional[dt.datetime] = None) -> bool:
    """Closed or not open yet: the public listing and the search leave the
    form out (a full form is left out by ``is_full``, which needs a count)."""
    return date_unavailability(settings, now) is not None


def _refusal(code: str, message: str, **extra: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.CONFLICT,
        content={"code": code, "message": message, **extra},
    )


def form_full_error() -> HTTPException:
    """409 ``form_full``: the refusal of a submission over the limit. The
    body names no number (the count and the limit are the creator's)."""
    return _refusal(FORM_FULL, FORM_FULL_MESSAGE)


def ensure_accepting_responses(
    settings: Any,
    now: Optional[dt.datetime] = None,
    received_at: Optional[dt.datetime] = None,
) -> None:
    """Refuse a new response to a closed form (409 ``form_closed``) or one
    that has not opened yet (409 ``form_not_open``), in the shape of the other
    refusals of a submission (``invalid_answers``). Judged at
    ``decision_time(received_at, now)``. The response limit needs a count and
    is checked by ``ensure_not_full``."""
    judged_at = decision_time(received_at, now)
    reason = date_unavailability(settings, judged_at)
    if reason == UNAVAILABLE_CLOSED:
        raise _refusal(
            FORM_CLOSED, FORM_CLOSED_MESSAGE, closesAt=closes_at(settings).isoformat()
        )
    if reason == UNAVAILABLE_NOT_OPEN:
        raise _refusal(
            FORM_NOT_OPEN, FORM_NOT_OPEN_MESSAGE, opensAt=opens_at(settings).isoformat()
        )


def ensure_not_full(settings: Any, count: int) -> None:
    """Refuse a new response to a form that holds as many as its limit:
    409 ``form_full``."""
    if is_full(settings, count):
        raise form_full_error()


def normalized_close_date(value: Any) -> Optional[str]:
    """A close date as the settings PATCH stores it: None (no change), ``""``
    (no date) or a UTC ISO 8601 instant (``...+00:00``). A value without an
    offset is UTC. Raises ValueError for anything else (a 422)."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return ""
    if not isinstance(value, (str, dt.datetime)):
        raise ValueError("The close date must be a date and time (ISO 8601).")
    if isinstance(value, str) and len(value) > 64:
        raise ValueError("The close date must be a date and time (ISO 8601).")
    instant = parse_instant(value)
    if instant is None:
        raise ValueError("The close date must be a date and time (ISO 8601).")
    return instant.isoformat()


def normalized_open_date(value: Any) -> Optional[str]:
    """An open date as the settings PATCH stores it: as ``normalized_close_date``
    (None = no change, ``""`` = no date, else a UTC ISO 8601 instant)."""
    try:
        return normalized_close_date(value)
    except ValueError:
        raise ValueError("The open date must be a date and time (ISO 8601).") from None


def ensure_dates_in_order(open_value: Any, close_value: Any) -> None:
    """Refuse an open date that is not before the close date (both, once
    normalised, may be None or ``""`` for "none"). Raises ValueError."""
    opens = parse_instant(open_value)
    close = parse_instant(close_value)
    if opens is not None and close is not None and opens >= close:
        raise ValueError("The open date must be before the close date.")


def normalized_response_limit(value: Any) -> Optional[int]:
    """A response limit as the settings PATCH stores it: None (no change), 0
    (no limit) or a whole number from 1 to ``MAX_RESPONSE_LIMIT``. Raises
    ValueError for anything else (a 422): a fraction, text, a boolean, a
    negative number."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("The response limit must be a whole number.")
    if value < 0 or value > MAX_RESPONSE_LIMIT:
        raise ValueError(
            f"The response limit must be between 1 and {MAX_RESPONSE_LIMIT} "
            "(0 removes it)."
        )
    return value
