"""The only way anything a task reports reaches the database.

``emit`` accepts a code from the task's declared enum, integer counters and at
most 20 ids matching an id pattern, nothing else, so there is no free-text
channel. A final pass (:func:`scrub`) then redacts what still looks like a
secret: hex or base64 runs of 24 or more characters and any value the audit
mask's deny-list matches. Exceptions are recorded as a class name only (never
the message, which may quote data).

Two judgement calls, both about ids:

* UUIDs are recognised first and kept (hyphenated hex would otherwise look like
  a url-safe base64 run).
* an id that is exactly 24 hex characters (a Mongo ObjectId, the form and
  response ids of the legacy store) is kept in ``ids`` only. Everywhere else, and
  for any longer run, 24+ hex characters are redacted.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from backend.admin.tasks.spec import (
    CODE_RE,
    COUNTER_RE,
    DENY_FIELD_NAME,
    ID_RE,
    MAX_EVENT_COUNTERS,
    MAX_EVENT_IDS,
)

REDACTED = "[redacted]"
MAX_EVENTS_PER_RUN = 5_000
MAX_BYTES_PER_RUN = 1024 * 1024
MAX_EVENT_BYTES = 2048
MAX_COUNTER = 2**53

_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")
_HEX_RUN = re.compile(r"[0-9a-fA-F]{24,}")
_B64_RUN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
_B64URL_RUN = re.compile(r"[A-Za-z0-9_-]{24,}")
_DOTTED_TOKEN = re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_CLASS_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class EventRejected(ValueError):
    """``emit`` was called with something outside the contract. The message names
    the rule, never the offending value."""


def scrub(value: str, *, allow_object_id: bool = False) -> str:
    """``value`` with secret-shaped content redacted (whole value if the audit
    deny-list matches)."""
    if _UUID.match(value) or (allow_object_id and _OBJECT_ID.match(value)):
        return value
    if DENY_FIELD_NAME.search(value):
        return REDACTED
    out = _DOTTED_TOKEN.sub(REDACTED, value)  # JWT-shaped
    out = _HEX_RUN.sub(REDACTED, out)
    out = _B64_RUN.sub(REDACTED, out)

    def url_safe(match: re.Match) -> str:
        run = match.group(0)
        # prose-like snake_case words (no digit) are not key material
        if any(c.isdigit() for c in run) and any(c.isalpha() for c in run):
            return REDACTED
        return run

    return _B64URL_RUN.sub(url_safe, out)


@dataclass(frozen=True)
class Event:
    seq: int
    code: str
    counts: Optional[dict]
    ids: Optional[list]
    error_class: Optional[str] = None

    def size(self) -> int:
        return (
            len(self.code)
            + len(json.dumps(self.counts) if self.counts else "")
            + len(json.dumps(self.ids) if self.ids else "")
            + len(self.error_class or "")
        )


def _code_text(events: type[enum.Enum], code: Any) -> str:
    if isinstance(code, events):
        return str(code.value)
    if isinstance(code, str) and code in {str(m.value) for m in events}:
        return code
    raise EventRejected("event code is not declared by the task")


def clean_counts(counts: Optional[Mapping[str, int]]) -> Optional[dict]:
    if not counts:
        return None
    if len(counts) > MAX_EVENT_COUNTERS:
        raise EventRejected("too many counters")
    out: dict[str, int] = {}
    for name, value in counts.items():
        if not isinstance(name, str) or not COUNTER_RE.match(name):
            raise EventRejected("counter name must be short snake_case")
        if isinstance(value, bool) or not isinstance(value, int):
            raise EventRejected("counters are integers")
        if abs(value) > MAX_COUNTER:
            raise EventRejected("counter out of range")
        out[scrub(name)] = value
    return out


def clean_ids(ids: Optional[Sequence[str]]) -> Optional[list]:
    if not ids:
        return None
    ids = list(ids)
    if len(ids) > MAX_EVENT_IDS:
        raise EventRejected("too many ids")
    out = []
    for item in ids:
        if not isinstance(item, str) or not ID_RE.match(item):
            raise EventRejected("id does not match the id pattern")
        out.append(scrub(item, allow_object_id=True))
    return out


def exception_class_name(exc: BaseException) -> str:
    """The exception's class name when it is a plain identifier, else a fixed
    placeholder. Never ``str(exc)``."""
    name = type(exc).__name__
    return name if _CLASS_NAME.match(name) else "Exception"


@dataclass
class EventSink:
    """Builds the rows of one run's ``run_events`` and applies the per-run caps:
    5,000 events or 1 MB, then one ``truncated`` marker and silence."""

    events: type[enum.Enum]
    seq: int = 0
    bytes_used: int = 0
    truncated: bool = False
    dropped: int = 0
    max_events: int = MAX_EVENTS_PER_RUN
    max_bytes: int = MAX_BYTES_PER_RUN
    _marker_sent: bool = field(default=False, repr=False)

    def build(
        self,
        code: Any,
        counts: Optional[Mapping[str, int]] = None,
        ids: Optional[Sequence[str]] = None,
    ) -> Optional[Event]:
        """The event to store, the ``truncated`` marker (once), or ``None`` after
        the cap. Rule violations raise :class:`EventRejected` first, so a buggy
        task fails loudly even when its events would have been dropped."""
        text = _code_text(self.events, code)
        event = Event(0, text, clean_counts(counts), clean_ids(ids))
        return self._admit(event)

    def build_system(self, code: str, *, error_class: Optional[str] = None) -> Optional[Event]:
        """Runner-originated events (``failed``, ``cancelled``): fixed codes."""
        if not CODE_RE.match(code):
            raise EventRejected("bad system code")
        return self._admit(Event(0, code, None, None, error_class))

    def _admit(self, event: Event) -> Optional[Event]:
        size = event.size()
        # an over-long id list is shortened rather than dropped: row <= 2 KB
        while size > MAX_EVENT_BYTES and event.ids:
            event = Event(0, event.code, event.counts, event.ids[:-1] or None, event.error_class)
            size = event.size()
        if size > MAX_EVENT_BYTES:
            raise EventRejected("event too large")
        if self.truncated:
            self.dropped += 1
            return None
        if self.seq + 1 > self.max_events - 1 or self.bytes_used + size > self.max_bytes:
            self.truncated = True
            self.dropped += 1
            self.seq += 1
            return Event(self.seq, "truncated", None, None)
        self.seq += 1
        self.bytes_used += size
        return Event(self.seq, event.code, event.counts, event.ids, event.error_class)
