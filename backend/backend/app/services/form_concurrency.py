"""Optimistic concurrency for the builder's whole-form saves.

The builder sends the ``updatedAt`` of the draft it last loaded or saved.
When the stored draft is newer (another tab, another person, or an API
client saved since), the save is refused with 409 instead of overwriting
those changes. Callers that send nothing keep the old behaviour.

The service checks first, for an early answer; the form repositories then
write conditionally (``update_form_if_unchanged``: only while the stored
``updated_at`` is still the one that passed the check), so two saves landing
at the same moment cannot both pass.
"""

from __future__ import annotations

import datetime as dt
from http import HTTPStatus
from typing import Optional

from pydantic import TypeAdapter, ValidationError

from backend.app.exceptions import HTTPException

FORM_CHANGED_CODE = "form_changed"
FORM_CHANGED_MESSAGE = (
    "This form was changed somewhere else since you opened it. "
    "Reload to get the latest version."
)

_datetime = TypeAdapter(dt.datetime)
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def parse_expected_updated_at(value: Optional[str]) -> Optional[dt.datetime]:
    """The client's ``updatedAt`` (ISO 8601), or None when not sent."""
    if value is None or not str(value).strip():
        return None
    try:
        return _datetime.validate_python(str(value).strip())
    except ValidationError:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content="expected_updated_at is not a valid date and time.",
        )


def _in_ms(value: dt.datetime) -> int:
    """Epoch milliseconds, naive values read as UTC. Milliseconds because
    MongoDB stores no finer, so the value a save returns and the one read
    back later must compare equal."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    # integer arithmetic: float timestamps can round a millisecond down
    delta = value - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def is_changed_since(
    stored: Optional[dt.datetime], expected: Optional[dt.datetime]
) -> bool:
    if stored is None or expected is None:
        return False
    return _in_ms(stored) > _in_ms(expected)


def form_changed() -> HTTPException:
    """The 409 a save based on an older draft gets."""
    return HTTPException(
        status_code=HTTPStatus.CONFLICT,
        content={"code": FORM_CHANGED_CODE, "message": FORM_CHANGED_MESSAGE},
    )


def ensure_not_changed_since(
    stored: Optional[dt.datetime], expected: Optional[dt.datetime]
) -> None:
    if is_changed_since(stored, expected):
        raise form_changed()


def next_updated_at(previous: Optional[dt.datetime]) -> dt.datetime:
    """The ``updated_at`` a conditional save stores: now, in whole
    milliseconds (what every store keeps and every client sends back) and
    always at least a millisecond after ``previous``, so each save is a
    change for :func:`is_changed_since`, however close two saves are."""
    now_ms = _in_ms(dt.datetime.now(dt.timezone.utc))
    if previous is not None:
        now_ms = max(now_ms, _in_ms(previous) + 1)
    return _EPOCH + dt.timedelta(milliseconds=now_ms)
