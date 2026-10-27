"""Registration in an Objects API (docs/open-formulieren.md, "Objects API").

Pure functions: the checks of a form's Objects API settings, the record we
create, the lookup that stops a retry from creating a second object, and
the two small readings of the API's replies. The network calls live in
``client.py``, the delivery logic in ``service.py``.

Format reference (Open Formulieren 4.0.6, read only):
``contrib/objects_api/clients/objects.py:5-18`` (the ``Content-Crs`` header and
``POST objects``), ``contrib/objects_api/typing.py:6-15`` (the body).

What is deliberately not sent: ``geometry`` (never), files (no Documents API
here), and answers that are not mapped.
"""

from __future__ import annotations

import datetime as dt
import functools
import re
import uuid
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from backend.app.services import safe_http

SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
MAX_SEGMENTS = 8
DEFAULT_REFERENCE_PATH = ("bettercollected_reference",)
MAX_OBJECT_TYPE_URL = 1000
MIN_VERSION, MAX_VERSION = 1, 10000
# the records endpoint, relative to the service's base address
RECORDS_PATH = "objects"
CRS = "EPSG:4326"
# the filter the Objects API documents as current (``data_attrs`` is deprecated
# there): one ``key__operator__value`` expression per parameter. See the docs.
FILTER_PARAMETER = "data_attr"
# how many results of a lookup we look through (we ask for one; a server that
# ignores ``pageSize`` is not trusted to stop there)
MAX_LOOKED_AT = 50

# all of these are used with ``fullmatch``: ``$`` would let a trailing newline through
_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_OBJECT_TYPE_TAIL = re.compile(
    r".*/objecttypes/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    re.DOTALL,
)
_URL_SEGMENT = re.compile(r"[A-Za-z0-9_~-][A-Za-z0-9._~-]*")
# a fixed namespace: the reference of a delivery is derived from its id, so
# it is stable across attempts without being stored anywhere else
_REFERENCE_NAMESPACE = uuid.UUID("7d0c1c2e-6b0a-5c0e-9a52-1d7f3a9b4e61")


class LookupUnreadable(Exception):
    """The answer to a lookup could not be read (or is not an answer to our
    question). Never carries the answer."""


# ----------------------------------------------------------------- paths


def segment_problem(segment: Any) -> bool:
    """True when ``segment`` may not be a key in ``record.data``: letters,
    digits and ``_``, starting with a letter, at most 64, no ``__`` and no
    trailing ``_`` (the Objects API's filter joins segments with ``__``)."""
    return (
        not isinstance(segment, str)
        or not SEGMENT.fullmatch(segment)
        or "__" in segment
        or segment.endswith("_")
    )


def path_problem(path: Any) -> bool:
    return (
        not isinstance(path, (list, tuple))
        or not 1 <= len(path) <= MAX_SEGMENTS
        or any(segment_problem(s) for s in path)
    )


def paths_conflict(a: Sequence[str], b: Sequence[str]) -> bool:
    """Equal, or one is a prefix of the other (one value would sit inside the
    other)."""
    short = min(len(a), len(b))
    return list(a[:short]) == list(b[:short])


# ------------------------------------------------------------ object type


class ObjectTypeRefused(Exception):
    """``code``: ``invalid_object_type_url`` or ``object_type_outside_base``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def checked_object_type(url: Any, base: Optional[str]) -> str:
    """The normalised ``url``, an object type URL under ``base`` (the service's
    object types address), or raises :class:`ObjectTypeRefused`.

    Both are compared after normalisation: https, the default port, no
    credentials, query or fragment, an ASCII host, and a path of plain
    segments (no ``.``/``..``, no empty segment, no percent-encoding, no
    ``;``), so ``..`` and encoded tricks cannot move the URL out from under
    the base. ``base`` must be a prefix up to a path boundary. The URL is
    never fetched by us."""
    invalid = ObjectTypeRefused("invalid_object_type_url")
    if not isinstance(url, str) or len(url.strip()) > MAX_OBJECT_TYPE_URL:
        raise invalid
    try:
        normal, _host = safe_http.checked_https_url(
            url, max_length=MAX_OBJECT_TYPE_URL, allow_query=False
        )
    except safe_http.UrlRefused:
        raise invalid
    if "%" in normal or ";" in normal or "#" in url:
        raise invalid
    path = urlsplit(normal).path
    segments = path.split("/")[1:]
    if (
        not segments
        or any(not _URL_SEGMENT.fullmatch(s) for s in segments)
        or not _OBJECT_TYPE_TAIL.fullmatch(path)
    ):
        raise invalid
    if not base:
        raise ObjectTypeRefused("object_type_outside_base")
    prefix = base if base.endswith("/") else base + "/"
    if not normal.startswith(prefix):
        raise ObjectTypeRefused("object_type_outside_base")
    return normal


# -------------------------------------------------------------- reference


def reference_for(delivery_id: Any) -> str:
    """The reference of a delivery: a UUID derived from its id, the same on
    every attempt, and no personal data."""
    return str(uuid.uuid5(_REFERENCE_NAMESPACE, f"delivery:{delivery_id}"))


# --------------------------------------------------------------- the record


def _utc(moment: dt.datetime) -> dt.datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


@functools.lru_cache(maxsize=1)
def _amsterdam() -> ZoneInfo:
    return ZoneInfo("Europe/Amsterdam")


def amsterdam_date(moment: dt.datetime) -> str:
    """``YYYY-MM-DD`` of ``moment`` in Europe/Amsterdam (a naive ``moment`` is
    UTC)."""
    return _utc(moment).astimezone(_amsterdam()).date().isoformat()


def nest(values: Dict[Tuple[str, ...], Any]) -> Dict[str, Any]:
    """``{("a", "b"): 1}`` -> ``{"a": {"b": 1}}``. Raises ``ValueError`` when
    two paths clash (stored configuration is checked again here)."""
    data: Dict[str, Any] = {}
    for path, value in values.items():
        if path_problem(path):
            raise ValueError("path")
        node = data
        for segment in path[:-1]:
            child = node.setdefault(segment, {})
            if not isinstance(child, dict):
                raise ValueError("conflict")
            node = child
        if path[-1] in node:
            raise ValueError("conflict")
        node[path[-1]] = value
    return data


def build_record(
    *,
    object_type_url: str,
    version: int,
    values: Dict[Tuple[str, ...], Any],
    reference_path: Sequence[str],
    reference: str,
    start_at: str,
) -> bytes:
    """The body of ``POST objects``. ``values`` are the mapped answers by
    target path; the reference sits at ``reference_path``. Unanswered
    questions (``None`` or an empty text) are left out so an optional field
    never fails a schema that expects its format."""
    kept = {
        tuple(path): value
        for path, value in values.items()
        if value is not None and value != ""
    }
    kept[tuple(reference_path)] = reference
    body = {
        "type": object_type_url,
        "record": {
            "typeVersion": version,
            "data": nest(kept),
            "startAt": start_at,
        },
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def record_headers() -> List[Tuple[bytes, bytes]]:
    return [
        (b"Content-Crs", CRS.encode()),
        (b"Accept-Crs", CRS.encode()),
    ]


# --------------------------------------------------------------- the lookup


def filter_expression(reference_path: Sequence[str], reference: str) -> str:
    return "__".join([*reference_path, "exact", reference])


def lookup_query(
    object_type_url: str,
    reference_path: Sequence[str],
    reference: str,
    start_at: str,
) -> List[Tuple[str, str]]:
    """The query of the duplicate check. Built from validated configuration
    and our own ids only; ``date`` is the record's own ``startAt`` (the
    Objects API otherwise shows only records that already started today)."""
    return [
        ("type", object_type_url),
        (FILTER_PARAMETER, filter_expression(reference_path, reference)),
        ("date", start_at),
        ("pageSize", "1"),
    ]


def malformed_filter_query(object_type_url: str) -> List[Tuple[str, str]]:
    """A lookup whose filter is deliberately not of the form
    ``key__operator__value``: an Objects API that checks its filters refuses
    it (400); one that ignores them answers 200 (connection check only)."""
    return [
        ("type", object_type_url),
        (FILTER_PARAMETER, "not-a-filter"),
        ("pageSize", "1"),
    ]


def _loads(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise LookupUnreadable()


def _at(data: Any, path: Sequence[str]) -> Any:
    for segment in path:
        if not isinstance(data, dict) or segment not in data:
            return None
        data = data[segment]
    return data


def _uuid_or_none(value: Any) -> Optional[str]:
    if isinstance(value, str) and _UUID.fullmatch(value):
        try:
            return str(uuid.UUID(value))
        except ValueError:
            return None
    return None


def read_lookup(
    body: bytes, reference_path: Sequence[str], reference: str
) -> Optional[str]:
    """What a lookup answer says: ``None`` when no object has our reference
    (an empty list), else the UUID of the object that carries it (``""`` when
    that object has no readable UUID).

    Raises :class:`LookupUnreadable` for an answer that is not a list of
    objects, and for a list in which no object carries our reference at the
    reference path: the server did not apply our filter, or the data cannot
    be read, and an object we cannot show to be ours is never taken for ours.
    """
    answer = _loads(body)
    if not isinstance(answer, dict) or not isinstance(answer.get("results"), list):
        raise LookupUnreadable()
    results = answer["results"]
    if not results:
        count = answer.get("count")
        if count not in (None, 0):
            raise LookupUnreadable()
        return None
    for item in results[:MAX_LOOKED_AT]:
        record = item.get("record") if isinstance(item, dict) else None
        data = record.get("data") if isinstance(record, dict) else None
        found = _at(data, reference_path)
        if isinstance(found, str) and found == reference:
            return _uuid_or_none(item.get("uuid")) or ""
    raise LookupUnreadable()


def read_created(body: bytes) -> Optional[str]:
    """The UUID of the object that was created, from the reply to our POST,
    or ``None`` when the reply does not carry a readable one (the object was
    created all the same: the reply is not part of what we keep)."""
    try:
        answer = _loads(body)
    except LookupUnreadable:
        return None
    return _uuid_or_none(answer.get("uuid")) if isinstance(answer, dict) else None


def check_reply_empty(body: bytes) -> bool:
    """For the connection check: the lookup of a reference that cannot exist
    answered with an empty list. Anything else is unreadable or ignores the
    filter."""
    try:
        answer = _loads(body)
    except LookupUnreadable:
        return False
    return (
        isinstance(answer, dict)
        and answer.get("results") == []
        and answer.get("count") in (None, 0)
    )
