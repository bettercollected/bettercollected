"""SQL for the settings store (schema ``settings``) and the notification outbox.

Plain SQLAlchemy Core text statements, schema-qualified. No signing, no
validation and no audit here: ``services/settings_store.py`` does those, in the
same transaction. JSON columns are written through ``text`` and read back as
text, so nothing depends on a driver's JSON codec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from common.settings.canonical import SettingRow

# One writer at a time. Taken before the audit chain's lock, always in that order.
SETTINGS_LOCK_KEY = 7310952481203619855

ENTRY_COLUMNS = (
    "key, section, readers, is_secret, reload_class, tier, value::text AS value, blob, "
    "cleared, version, source, updated_by, updated_at, sig"
)


@dataclass(frozen=True)
class EntryRow:
    key: str
    section: str
    readers: tuple
    is_secret: bool
    reload_class: str
    tier: str
    value: Any
    blob: Optional[str]
    cleared: bool
    version: int
    source: str
    updated_by: str
    updated_at: datetime
    sig: str

    def __repr__(self) -> str:  # never show the value or blob
        return f"EntryRow(key={self.key!r}, version={self.version})"

    def to_setting_row(self) -> SettingRow:
        """The row as it was signed. A tombstone is signed as a plain row with
        no value (never a legal value for a live row), whatever the setting's
        secrecy, so a live row cannot be turned into one by flipping a flag."""
        return SettingRow(
            key=self.key,
            section=self.section,
            readers=tuple(self.readers),
            is_secret=False if self.cleared else self.is_secret,
            reload_class=self.reload_class,
            version=self.version,
            updated_at=self.updated_at,
            value=self.value,
            blob=self.blob,
            sig=self.sig,
        )


@dataclass(frozen=True)
class HistoryRow:
    key: str
    version: int
    section: str
    is_secret: bool
    value: Any
    blob: Optional[str]
    cleared: bool
    action: str

    def __repr__(self) -> str:
        return f"HistoryRow(key={self.key!r}, version={self.version})"


def _entry(row: Any) -> EntryRow:
    m = row._mapping
    return EntryRow(
        key=m["key"],
        section=m["section"],
        readers=tuple(m["readers"]),
        is_secret=m["is_secret"],
        reload_class=m["reload_class"],
        tier=m["tier"],
        value=None if m["value"] is None else json.loads(m["value"]),
        blob=m["blob"],
        cleared=m["cleared"],
        version=m["version"],
        source=m["source"],
        updated_by=m["updated_by"],
        updated_at=m["updated_at"],
        sig=m["sig"],
    )


def _json(value: Any) -> Optional[str]:
    return None if value is None else json.dumps(value, allow_nan=False)


async def lock(conn: AsyncConnection) -> int:
    """Serialise writers until the transaction ends; the manifest revision."""
    await conn.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": SETTINGS_LOCK_KEY}
    )
    return (
        await conn.execute(text("SELECT revision FROM settings.manifest WHERE id = 1 FOR UPDATE"))
    ).scalar_one()


async def db_now(conn: AsyncConnection) -> datetime:
    return (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()


async def get_entry(
    conn: AsyncConnection, key: str, *, for_update: bool = False
) -> Optional[EntryRow]:
    suffix = " FOR UPDATE" if for_update else ""
    row = (
        await conn.execute(
            text(f"SELECT {ENTRY_COLUMNS} FROM settings.entries WHERE key = :k{suffix}"),
            {"k": key},
        )
    ).first()
    return _entry(row) if row else None


async def list_entries(
    conn: AsyncConnection, keys: Optional[Sequence[str]] = None, *, for_update: bool = False
) -> list[EntryRow]:
    suffix = " FOR UPDATE" if for_update else ""
    sql = f"SELECT {ENTRY_COLUMNS} FROM settings.entries"
    params: dict = {}
    if keys is not None:
        sql += " WHERE key = ANY(CAST(:keys AS text[]))"
        params["keys"] = list(keys)
    rows = await conn.execute(text(sql + " ORDER BY key" + suffix), params)
    return [_entry(r) for r in rows]


async def insert_entry(conn: AsyncConnection, e: EntryRow) -> None:
    await conn.execute(
        text(
            "INSERT INTO settings.entries (key, section, readers, is_secret, reload_class, "
            "tier, value, blob, cleared, version, source, updated_by, updated_at, sig) "
            "VALUES (:key, :section, CAST(:readers AS text[]), :is_secret, :reload_class, "
            ":tier, CAST(CAST(:value AS text) AS jsonb), :blob, :cleared, :version, "
            ":source, :updated_by, :updated_at, :sig)"
        ),
        _params(e),
    )


async def update_entry(conn: AsyncConnection, e: EntryRow) -> None:
    await conn.execute(
        text(
            "UPDATE settings.entries SET section = :section, "
            "readers = CAST(:readers AS text[]), is_secret = :is_secret, "
            "reload_class = :reload_class, tier = :tier, "
            "value = CAST(CAST(:value AS text) AS jsonb), blob = :blob, cleared = :cleared, "
            "version = :version, source = :source, updated_by = :updated_by, "
            "updated_at = :updated_at, sig = :sig WHERE key = :key"
        ),
        _params(e),
    )


async def update_blob_sig(conn: AsyncConnection, key: str, blob: Optional[str], sig: str) -> None:
    """Re-wrap or re-sign in place: the one same-version update the guard allows."""
    await conn.execute(
        text("UPDATE settings.entries SET blob = :blob, sig = :sig WHERE key = :key"),
        {"key": key, "blob": blob, "sig": sig},
    )


def _params(e: EntryRow) -> dict:
    return {
        "key": e.key,
        "section": e.section,
        "readers": list(e.readers),
        "is_secret": e.is_secret,
        "reload_class": e.reload_class,
        "tier": e.tier,
        "value": _json(e.value),
        "blob": e.blob,
        "cleared": e.cleared,
        "version": e.version,
        "source": e.source,
        "updated_by": e.updated_by,
        "updated_at": e.updated_at,
        "sig": e.sig,
    }


async def insert_history(
    conn: AsyncConnection, e: EntryRow, *, action: str, actor: str, at: datetime
) -> None:
    await conn.execute(
        text(
            "INSERT INTO settings.history (key, version, section, is_secret, value, blob, "
            "cleared, action, source, actor, at) VALUES (:key, :version, :section, "
            ":is_secret, CAST(CAST(:value AS text) AS jsonb), :blob, :cleared, :action, "
            ":source, :actor, :at)"
        ),
        {
            "key": e.key,
            "version": e.version,
            "section": e.section,
            "is_secret": e.is_secret,
            "value": _json(e.value),
            "blob": e.blob,
            "cleared": e.cleared,
            "action": action,
            "source": e.source,
            "actor": actor,
            "at": at,
        },
    )


def _history(row: Any) -> HistoryRow:
    m = row._mapping
    return HistoryRow(
        key=m["key"],
        version=m["version"],
        section=m["section"],
        is_secret=m["is_secret"],
        value=None if m["value"] is None else json.loads(m["value"]),
        blob=m["blob"],
        cleared=m["cleared"],
        action=m["action"],
    )

HISTORY_COLUMNS = "key, version, section, is_secret, value::text AS value, blob, cleared, action"


async def get_history(conn: AsyncConnection, key: str, version: int) -> Optional[HistoryRow]:
    row = (
        await conn.execute(
            text(f"SELECT {HISTORY_COLUMNS} FROM settings.history WHERE key = :k AND version = :v"),
            {"k": key, "v": version},
        )
    ).first()
    return _history(row) if row else None


async def list_history(conn: AsyncConnection, key: str) -> list[HistoryRow]:
    rows = await conn.execute(
        text(f"SELECT {HISTORY_COLUMNS} FROM settings.history WHERE key = :k ORDER BY version"),
        {"k": key},
    )
    return [_history(r) for r in rows]


async def prune_history(conn: AsyncConnection, key: str, below_version: int) -> int:
    """Delete encrypted versions older than ``below_version`` (never the current one)."""
    result = await conn.execute(
        text(
            "DELETE FROM settings.history WHERE key = :k AND is_secret AND version < :v"
        ),
        {"k": key, "v": below_version},
    )
    return result.rowcount


async def update_history_blob(conn: AsyncConnection, key: str, version: int, blob: str) -> None:
    await conn.execute(
        text("UPDATE settings.history SET blob = :b WHERE key = :k AND version = :v"),
        {"b": blob, "k": key, "v": version},
    )


async def get_manifest(conn: AsyncConnection) -> Optional[Mapping[str, Any]]:
    row = (
        await conn.execute(
            text("SELECT revision, digest, entries::text AS entries, sig FROM settings.manifest WHERE id = 1")
        )
    ).first()
    if row is None:
        return None
    m = row._mapping
    return {
        "revision": m["revision"],
        "digest": m["digest"],
        "entries": json.loads(m["entries"]),
        "sig": m["sig"],
    }


async def write_manifest(
    conn: AsyncConnection, revision: int, digest: str, entries: Mapping[str, Any], sig: str
) -> None:
    await conn.execute(
        text(
            "UPDATE settings.manifest SET revision = :r, digest = :d, "
            "entries = CAST(CAST(:e AS text) AS jsonb), sig = :s WHERE id = 1"
        ),
        {"r": revision, "d": digest, "e": json.dumps(entries, allow_nan=False), "s": sig},
    )


async def enqueue_notification(
    conn: AsyncConnection,
    kind: str,
    payload: Mapping[str, Any],
    audit_seq: Optional[int],
    dedupe_key: Optional[str] = None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO admin.notifications (kind, payload, audit_seq, dedupe_key) "
            "VALUES (:k, CAST(CAST(:p AS text) AS jsonb), :s, :d)"
        ),
        {
            "k": kind,
            "p": json.dumps(payload, allow_nan=False),
            "s": audit_seq,
            "d": dedupe_key,
        },
    )


async def latest_audited_versions(conn: AsyncConnection) -> dict[str, tuple[int, str, str]]:
    """Per setting: version, digest and action of the newest successful audit row that records one."""
    rows = await conn.execute(
        text(
            "SELECT DISTINCT ON (target_id) target_id, after->>'version' AS version, "
            "after->>'digest' AS digest, action FROM admin.audit_log "
            "WHERE target_type = 'setting' AND outcome = 'success' "
            "AND after->>'digest' IS NOT NULL ORDER BY target_id, seq DESC"
        )
    )
    return {r.target_id: (int(r.version), r.digest, r.action) for r in rows}


async def max_audited_revision(conn: AsyncConnection) -> int:
    value = (
        await conn.execute(
            text(
                "SELECT max((detail->>'revision')::bigint) FROM admin.audit_log "
                "WHERE target_type IN ('setting', 'settings_store') "
                "AND outcome = 'success' AND detail->>'revision' ~ '^[0-9]{1,18}$'"
            )
        )
    ).scalar_one()
    return int(value or 0)
