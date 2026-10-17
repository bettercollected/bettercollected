"""Optimistic concurrency for the builder's whole-form saves.

The builder sends the ``updatedAt`` of the draft it last loaded or saved.
When the stored draft is newer (another tab, another person, or an API
client saved since), the save is refused with 409 instead of overwriting
those changes. Callers that send nothing keep the old behaviour.
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


def ensure_not_changed_since(
    stored: Optional[dt.datetime], expected: Optional[dt.datetime]
) -> None:
    if is_changed_since(stored, expected):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            content={"code": FORM_CHANGED_CODE, "message": FORM_CHANGED_MESSAGE},
        )
