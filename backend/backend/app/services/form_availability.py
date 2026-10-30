"""Whether a form still accepts responses: its close date, read one way.

A form's close date (``WorkspaceFormSettings.form_close_date``) is an instant.
The form is closed from that instant on (``now >= close``); before it, or
without a date, it is open. The server's clock decides, never the
respondent's.

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
# The read of a closed form's published version for a respondent: a stub with
# this marker instead of the questions (services/form_service.py).
UNAVAILABLE_CLOSED = "closed"
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


def _close_value(settings: Any) -> Any:
    if settings is None:
        return None
    if isinstance(settings, Mapping):
        return settings.get("form_close_date")
    return getattr(settings, "form_close_date", None)


def closes_at(settings: Any) -> Optional[dt.datetime]:
    """The instant the form closes (aware UTC), or None when it has none.
    ``settings`` is a ``WorkspaceFormSettings`` or its stored dict."""
    return parse_instant(_close_value(settings))


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


def ensure_accepting_responses(
    settings: Any,
    now: Optional[dt.datetime] = None,
    received_at: Optional[dt.datetime] = None,
) -> None:
    """Refuse a new response to a closed form: 409 ``form_closed``, in the
    shape of the other refusals of a submission (``invalid_answers``).
    Judged at ``decision_time(received_at, now)``."""
    close = closes_at(settings)
    if close is None or decision_time(received_at, now) < close:
        return
    raise HTTPException(
        status_code=HTTPStatus.CONFLICT,
        content={
            "code": FORM_CLOSED,
            "message": FORM_CLOSED_MESSAGE,
            "closesAt": close.isoformat(),
        },
    )


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
