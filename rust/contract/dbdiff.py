"""What a write case did to the database, so Python's rows and Rust's rows can be
compared.

Every table of schema ``app`` has the same shape (``common/common/db/base.py``):
``id``, ``created_at``, ``updated_at``, ``doc`` (JSONB, BSON Extended JSON),
``_bc_source``, ``_bc_checksum`` and a few typed "spine" columns GENERATED from
``doc``. A write case names the tables it may touch; the runner then

1. snapshots them (``snapshot``),
2. sends the case to Python and snapshots again,
3. puts the tables back (``restore``),
4. sends the case to Rust and snapshots again, and
5. compares the two changes (``compare_deltas``): the ``doc`` and the spine
   columns of every row added, removed or changed.

A row Python added and a row Rust added have different ids and timestamps, so
those are normalised first (``normalise``): the new id becomes ``<id:N>``
wherever it occurs, and any BSON date becomes ``<date>``. The rules are the
constants below; nothing else is ignored. ``bad_checksums`` also checks the
invariant every writer must keep: ``_bc_checksum`` is ``sha256:`` plus the hex
SHA-256 of the canonical JSON of ``doc`` (sorted keys, compact, not ASCII-only).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Optional

# columns that differ between two runs of the same case, by nature
DEFAULT_IGNORED_COLUMNS = {"created_at", "updated_at"}
# the checksum follows from doc (which is compared) and is checked on its own
CHECKSUM_COLUMN = "_bc_checksum"
DATE_PLACEHOLDER = "<date>"


# ---------------------------------------------------------------- pure parts

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def checksum_of(doc: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(doc).encode("utf-8")).hexdigest()


def bad_checksums(snapshot: dict) -> list:
    """``table/id`` of every row whose stored checksum is not the checksum of its doc."""
    bad = []
    for table, rows in snapshot.items():
        for row_id, row in rows.items():
            if CHECKSUM_COLUMN in row and row[CHECKSUM_COLUMN] != checksum_of(row["doc"]):
                bad.append(f"{table}/{row_id}")
    return bad


def diff(before: dict, after: dict) -> dict:
    """The change from one snapshot to the next: per table the ids added and
    removed (with their rows) and, for the rows that stayed, the columns that
    changed as ``{column: [old, new]}``."""
    delta = {}
    for table in sorted(set(before) | set(after)):
        old, new = before.get(table, {}), after.get(table, {})
        added = {i: new[i] for i in new if i not in old}
        removed = {i: old[i] for i in old if i not in new}
        changed = {}
        for row_id in old:
            if row_id in new and old[row_id] != new[row_id]:
                cols = {
                    c: [old[row_id].get(c), new[row_id].get(c)]
                    for c in sorted(set(old[row_id]) | set(new[row_id]))
                    if old[row_id].get(c) != new[row_id].get(c)
                }
                changed[row_id] = cols
        if added or removed or changed:
            delta[table] = {"added": added, "removed": removed, "changed": changed}
    return delta


def _scrub(value: Any, ids: dict) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$date"}:
            return DATE_PLACEHOLDER
        return {k: _scrub(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, ids) for v in value]
    if isinstance(value, str):
        return ids.get(value, value)
    return value


def normalise(delta: dict, ignored_columns: Optional[Iterable[str]] = None) -> dict:
    """``delta`` with timestamps, new ids and dates made comparable (see the module text)."""
    ignored = set(DEFAULT_IGNORED_COLUMNS if ignored_columns is None else ignored_columns)
    ignored.add(CHECKSUM_COLUMN)
    out = {}
    for table, parts in delta.items():
        # new ids get a stable name by the order of their (id-free) content
        added = parts["added"]
        keyed = sorted(
            added,
            key=lambda i: canonical_json(_scrub({c: v for c, v in added[i].items() if c not in ignored | {"id"}}, {})),
        )
        ids = {row_id: f"<id:{n}>" for n, row_id in enumerate(keyed)}

        def clean(row: dict) -> dict:
            return {c: _scrub(v, ids) for c, v in row.items() if c not in ignored}

        out[table] = {
            "added": sorted((clean(r) for r in added.values()), key=canonical_json),
            "removed": sorted((clean(r) for r in parts["removed"].values()), key=canonical_json),
            "changed": {
                ids.get(i, i): {c: [_scrub(v, ids) for v in pair] for c, pair in cols.items() if c not in ignored}
                for i, cols in parts["changed"].items()
            },
        }
    return out


def compare_deltas(python: dict, rust: dict, ignored_columns: Optional[Iterable[str]] = None) -> list:
    """Human-readable differences between the change Python made and the change Rust made."""
    a, b = normalise(python, ignored_columns), normalise(rust, ignored_columns)
    problems = []
    for table in sorted(set(a) | set(b)):
        if a.get(table) != b.get(table):
            problems.append(
                f"rows of {table}: python {json.dumps(a.get(table), sort_keys=True)[:300]} "
                f"!= rust {json.dumps(b.get(table), sort_keys=True)[:300]}"
            )
    return problems


# ------------------------------------------------------- database (asyncpg)

def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _generated_columns(conn, table: str) -> set:
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'app' AND table_name = $1 AND is_generated = 'ALWAYS'",
        table,
    )
    return {r["column_name"] for r in rows}


def _table(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"not a table name: {name!r}")
    return f'app."{name}"'


async def snapshot(conn, tables: Iterable[str]) -> dict:
    """``{table: {id: {column: value}}}``; ``doc`` parsed, timestamps as text."""
    out = {}
    for table in tables:
        rows = await conn.fetch(f"SELECT * FROM {_table(table)}")
        out[table] = {}
        for row in rows:
            data = {k: _plain(v) for k, v in dict(row).items()}
            if isinstance(data.get("doc"), str):
                data["doc"] = json.loads(data["doc"])
            out[table][data["id"]] = data
    return out


async def restore(conn, before: dict) -> None:
    """Puts the tables of ``before`` back exactly: rows that were added are
    deleted, changed and removed rows are written again (generated columns are
    left to the database)."""
    for table, rows in before.items():
        generated = await _generated_columns(conn, table)
        await conn.execute(f"DELETE FROM {_table(table)} WHERE id <> ALL($1::text[])", list(rows))
        for row in rows.values():
            columns = [c for c in row if c not in generated]
            names = ", ".join(f'"{c}"' for c in columns)
            marks = ", ".join(f"${i + 1}" + ("::jsonb" if c == "doc" else "") for i, c in enumerate(columns))
            updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c != "id")
            values = [json.dumps(row[c]) if c == "doc" else _restore_value(c, row[c]) for c in columns]
            await conn.execute(
                f"INSERT INTO {_table(table)} ({names}) VALUES ({marks}) "
                f"ON CONFLICT (id) DO UPDATE SET {updates}",
                *values,
            )


def _restore_value(column: str, value: Any) -> Any:
    if column in ("created_at", "updated_at") and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value
