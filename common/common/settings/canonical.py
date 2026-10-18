"""The bytes that are signed for one settings row.

Length-prefixed fields under a domain tag, so no two different rows (or a row
and a manifest) can encode to the same bytes. Signed: key, section, readers
(sorted), is_secret, reload_class, the value (canonical JSON) or the encrypted
blob, version and update time. Enums are encoded by their ``value``.

Not signed: who made the change. ``SettingRow`` has no ``changed_by``; the
store keeps it in its audit log (a tamper-evident chain). If the row model
gains such a field it must be added here under a new domain tag.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, replace
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple

ROW_DOMAIN = b"bc-settings-row-v1"
MANIFEST_DOMAIN = b"bc-settings-manifest-v1"


class CanonicalError(ValueError):
    """A row cannot be encoded. Messages never contain the value."""


@dataclass(frozen=True)
class SettingRow:
    """One stored setting. Exactly one of ``value`` (plain, JSON-able) and
    ``blob`` (envelope v2 text, for secrets) is set. ``sig`` is the hex HMAC."""

    key: str
    section: str
    readers: Tuple[str, ...]
    is_secret: bool
    reload_class: str
    version: int
    updated_at: datetime
    value: Any = None
    blob: Optional[str] = None
    sig: str = ""

    def with_sig(self, sig: str) -> "SettingRow":
        return replace(self, sig=sig)

    def __repr__(self) -> str:  # never show the value or blob
        return f"SettingRow(key={self.key!r}, version={self.version})"


RELOAD_CLASSES = ("B", "H", "R")


def text_of(value: Any, what: str) -> str:
    """A plain string for ``value``: an Enum by its ``value``, a str as is.
    Never ``str(enum)``, which would encode ``"Reload.R"``."""
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise CanonicalError(f"{what} must be text")
    return value


def lp(data: bytes) -> bytes:
    """Length prefix: 4 bytes big endian, then the data."""
    return struct.pack(">I", len(data)) + data


def u64(number: int) -> bytes:
    if not isinstance(number, int) or isinstance(number, bool) or number < 0:
        raise CanonicalError("number must be a non-negative integer")
    return struct.pack(">Q", number)


def canonical_json(value: Any) -> str:
    """Sorted keys, no whitespace, ASCII only, no NaN: one text per value."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise CanonicalError("value is not canonical JSON") from None


def format_timestamp(moment: datetime) -> str:
    """RFC 3339 in UTC with fixed microsecond precision."""
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise CanonicalError("timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_row(row: SettingRow) -> bytes:
    if row.is_secret:
        if row.blob is None or row.value is not None:
            raise CanonicalError("a secret row carries a blob and no value")
    elif row.blob is not None:
        raise CanonicalError("only a secret row carries a blob")
    readers = tuple(text_of(r, "reader") for r in row.readers)
    if len(set(readers)) != len(readers) or not readers:
        raise CanonicalError("readers must be non-empty and unique")
    reload_class = text_of(row.reload_class, "reload class")
    if reload_class not in RELOAD_CLASSES:
        raise CanonicalError("unknown reload class")
    if not isinstance(row.is_secret, bool):
        raise CanonicalError("is_secret must be a boolean")
    if row.blob is not None:
        kind, payload = b"b", row.blob
    else:
        kind, payload = b"v", canonical_json(row.value)
    parts = [
        lp(ROW_DOMAIN),
        lp(text_of(row.key, "key").encode("utf-8")),
        lp(text_of(row.section, "section").encode("utf-8")),
        struct.pack(">I", len(readers)),
        *[lp(r.encode("utf-8")) for r in sorted(readers)],
        lp(b"1" if row.is_secret else b"0"),
        lp(reload_class.encode("utf-8")),
        lp(kind),
        lp(payload.encode("utf-8")),
        u64(row.version),
        lp(format_timestamp(row.updated_at).encode("ascii")),
    ]
    return b"".join(parts)


def normalize_entry(entry: Any) -> Tuple[int, str, Tuple[str, ...]]:
    """``(version, sig, readers)`` from a tuple or a JSON list; readers sorted."""
    try:
        version, sig, readers = entry
        readers = tuple(sorted(text_of(r, "reader") for r in readers))
        sig = text_of(sig, "signature")
    except (TypeError, ValueError):
        raise CanonicalError("malformed manifest entry") from None
    u64(version)
    return version, sig, readers


def canonical_manifest(revision: int, entries: Mapping[str, Any]) -> bytes:
    """``entries`` maps key to ``(version, sig_hex, readers)``; encoded sorted
    by key as ``key:version:sig_hex:reader,reader`` after the revision."""
    lines = []
    for key in sorted(entries):
        if ":" in key or "," in key:
            raise CanonicalError("key must not contain ':' or ','")
        version, sig, readers = normalize_entry(entries[key])
        if any("," in r or ":" in r for r in readers):
            raise CanonicalError("reader must not contain ':' or ','")
        lines.append(f"{key}:{version}:{sig}:{','.join(readers)}")
    return b"".join(
        [lp(MANIFEST_DOMAIN), u64(revision), struct.pack(">I", len(lines))]
        + [lp(line.encode("utf-8")) for line in lines]
    )
