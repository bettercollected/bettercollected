"""The keyset rotation core: what is encrypted with the keyset and where it
lives (the targets and their stores), and the walk that re-encrypts or counts
it. Shared by the ``keyset.*`` tasks of the admin task runner and by
``scripts/rotate_response_keyset.py`` (the break-glass command line).

Runbook with the order across services: docs/response-keyset-rotation.md.

What is encrypted with the keyset (``common.services.crypto_service``):

* ``responses``: in each stored response, ``answers``, ``hidden_fields``,
  ``internal_answers`` and every ``respondent_feedback[].message``, with the
  associated data ``<workspace_id>|<form_id>|``. Mongo ``form_responses`` /
  Postgres ``app.form_responses``.
* ``google-credentials``: the Google Forms integration's OAuth credentials
  (``personal|<user_id>|``). Mongo ``Oauth2CredentialDocument`` / Postgres
  ``google.oauth_credentials``.

Nothing else is encrypted with it (the Fernet-encrypted values use another key).
Never prints or returns a value or the keyset: counts and key ids only.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from common.services.keyset import (
    CryptoService,
    UnreadableCiphertext,
    ciphertext_key_id,
    encode_keyset,
    is_ciphertext,
    parse_keyset,
)

logger = logging.getLogger("rotate_response_keyset")

Path = Tuple[
    Any, ...
]  # into a document: ("answers",), ("respondent_feedback", 2, "message")


# ------------------------------------------------------------------- targets
@dataclass(frozen=True)
class Target:
    """One kind of record holding values encrypted with the keyset."""

    name: str
    group: str  # the repository group whose write mode applies
    collection: str  # Mongo collection
    schema: str  # Postgres schema
    table: str  # Postgres table
    fields: Tuple[str, ...]  # the document fields read
    values: Callable[[Dict[str, Any]], List[Tuple[Path, bytes]]]
    contexts: Callable[[Dict[str, Any], Dict[str, List[str]]], List[Tuple[str, str]]]
    needs_links: bool = False


def _response_values(record: Dict[str, Any]) -> List[Tuple[Path, bytes]]:
    found: List[Tuple[Path, bytes]] = []
    for field in ("answers", "hidden_fields", "internal_answers"):
        if is_ciphertext(record.get(field)):
            found.append(((field,), bytes(record[field])))
    for index, entry in enumerate(record.get("respondent_feedback") or []):
        message = entry.get("message") if isinstance(entry, dict) else None
        if is_ciphertext(message):
            found.append((("respondent_feedback", index, "message"), bytes(message)))
    return found


def _response_contexts(
    record: Dict[str, Any], links: Dict[str, List[str]]
) -> List[Tuple[str, str]]:
    form_id = str(record.get("form_id"))
    workspaces: List[str] = []
    if record.get("workspace_id"):
        workspaces.append(str(record["workspace_id"]))
    for workspace in links.get(form_id, []):
        if workspace not in workspaces:
            workspaces.append(workspace)
    return [(workspace, form_id) for workspace in workspaces]


def _credential_values(record: Dict[str, Any]) -> List[Tuple[Path, bytes]]:
    value = record.get("credentials")
    return [(("credentials",), bytes(value))] if is_ciphertext(value) else []


def _credential_contexts(record: Dict[str, Any], _links) -> List[Tuple[str, str]]:
    # OauthCredentialRepository.encrypt_token
    return [("personal", str(record.get("user_id")))]


RESPONSES = Target(
    name="responses",
    group="responses",
    collection="form_responses",
    schema="app",
    table="form_responses",
    fields=(
        "form_id",
        "workspace_id",
        "answers",
        "hidden_fields",
        "internal_answers",
        "respondent_feedback",
    ),
    values=_response_values,
    contexts=_response_contexts,
    needs_links=True,
)
GOOGLE_CREDENTIALS = Target(
    name="google-credentials",
    group="google",
    collection="Oauth2CredentialDocument",
    schema="google",
    table="oauth_credentials",
    fields=("user_id", "credentials"),
    values=_credential_values,
    contexts=_credential_contexts,
)
TARGETS = {target.name: target for target in (RESPONSES, GOOGLE_CREDENTIALS)}


# -------------------------------------------------------------------- stores
def _dotted(path: Path) -> str:
    return ".".join(str(part) for part in path)


def _get(document: Any, path: Path) -> Any:
    for part in path:
        document = document[part]
    return document


def _set(document: Any, path: Path, value: Any) -> None:
    for part in path[:-1]:
        document = document[part]
    document[path[-1]] = value


Update = Tuple[Path, bytes, bytes]  # path, the value read, its replacement


class MongoStore:
    name = "mongo"

    def __init__(self, database, target: Target, links=None):
        self.db = database  # pymongo AsyncDatabase
        self.target = target
        # where the workspace links of forms are read (a PostgresStore): the
        # forms group is in Postgres only since 4.1, so ``workspace_forms`` in
        # Mongo is a frozen 4.0 copy, read only where no Postgres is
        # configured (a 4.0 database not imported yet)
        self.links_source = links

    def key(self, record_id: str):
        from bson import ObjectId

        return ObjectId(record_id) if ObjectId.is_valid(record_id) else record_id

    async def links(self) -> Dict[str, List[str]]:
        """form_id -> the workspaces it is linked to: from Postgres, or with
        none configured from the 4.0 ``workspace_forms`` in Mongo."""
        if self.links_source is not None:
            return await self.links_source.links()
        links: Dict[str, List[str]] = {}
        cursor = (
            self.db["workspace_forms"]
            .find({}, {"form_id": 1, "workspace_id": 1})
            .sort("_id", 1)
        )
        async for row in cursor:
            if not row.get("workspace_id"):
                continue
            workspaces = links.setdefault(str(row.get("form_id")), [])
            if str(row["workspace_id"]) not in workspaces:
                workspaces.append(str(row["workspace_id"]))
        return links

    async def batch(self, after: Optional[str], limit: int) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if after is not None:
            query["_id"] = {"$gt": self.key(after)}
        projection = {field: 1 for field in self.target.fields}
        cursor = (
            self.db[self.target.collection]
            .find(query, projection)
            .sort("_id", 1)
            .limit(limit)
        )
        return [{**row, "id": str(row["_id"])} async for row in cursor]

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        projection = {field: 1 for field in self.target.fields}
        row = await self.db[self.target.collection].find_one(
            {"_id": self.key(record_id)}, projection
        )
        return None if row is None else {**row, "id": str(row["_id"])}

    async def write(self, record_id: str, updates: Sequence[Update]) -> bool:
        """Compare-and-set: only if every value is still the one read."""
        query: Dict[str, Any] = {"_id": self.key(record_id)}
        query.update({_dotted(path): old for path, old, _ in updates})
        result = await self.db[self.target.collection].update_one(
            query, {"$set": {_dotted(path): new for path, _, new in updates}}
        )
        return result.modified_count == 1


class PostgresStore:
    name = "postgres"

    def __init__(self, engine, target: Target):
        from sqlalchemy import Column, MetaData, Table, Text
        from sqlalchemy.dialects.postgresql import JSONB

        self.engine = engine  # SQLAlchemy AsyncEngine
        self.target = target
        metadata = MetaData(schema=target.schema)
        self.table = Table(
            target.table,
            metadata,
            Column("id", Text, primary_key=True),
            Column("doc", JSONB),
            Column("_bc_checksum", Text),
        )
        self.links_table = Table(
            "workspace_forms",
            metadata,
            Column("id", Text, primary_key=True),
            Column("doc", JSONB),
        )

    async def links(self) -> Dict[str, List[str]]:
        from sqlalchemy import select

        from common.db.canonical import from_canonical_document

        links: Dict[str, List[str]] = {}
        table = self.links_table
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                select(table.c.doc["form_id"], table.c.doc["workspace_id"]).order_by(
                    table.c.id
                )
            )
            for form_id, workspace in rows:
                restored = from_canonical_document(
                    {"form_id": form_id, "workspace_id": workspace}
                )
                if not restored.get("workspace_id"):
                    continue
                workspaces = links.setdefault(str(restored["form_id"]), [])
                if str(restored["workspace_id"]) not in workspaces:
                    workspaces.append(str(restored["workspace_id"]))
        return links

    async def batch(self, after: Optional[str], limit: int) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        from common.db.canonical import from_canonical_document

        table = self.table
        stmt = select(table.c.id, *[table.c.doc[f] for f in self.target.fields])
        if after is not None:
            stmt = stmt.where(table.c.id > after)
        stmt = stmt.order_by(table.c.id).limit(limit)
        records = []
        async with self.engine.connect() as conn:
            for values in await conn.execute(stmt):
                document = {
                    field: value
                    for field, value in zip(self.target.fields, values[1:])
                    if value is not None
                }
                records.append({**from_canonical_document(document), "id": values[0]})
        return records

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select

        from common.db.canonical import from_canonical_document

        table = self.table
        stmt = select(table.c.id, *[table.c.doc[f] for f in self.target.fields]).where(
            table.c.id == record_id
        )
        async with self.engine.connect() as conn:
            values = (await conn.execute(stmt)).first()
        if values is None:
            return None
        document = {
            field: value
            for field, value in zip(self.target.fields, values[1:])
            if value is not None
        }
        return {**from_canonical_document(document), "id": values[0]}

    async def write(self, record_id: str, updates: Sequence[Update]) -> bool:
        """Compare-and-set under a row lock; the checksum follows the document."""
        from sqlalchemy import select, update

        from common.db.canonical import canonical_document, checksum

        def stored(value: bytes):
            return canonical_document({"v": value})["v"]

        table = self.table
        async with self.engine.begin() as conn:
            document = (
                await conn.execute(
                    select(table.c.doc).where(table.c.id == record_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                return False
            for path, old, new in updates:
                try:
                    if _get(document, path) != stored(old):
                        return False
                except (KeyError, IndexError, TypeError):
                    return False
                _set(document, path, stored(new))
            await conn.execute(
                update(table)
                .where(table.c.id == record_id)
                .values({"doc": document, "_bc_checksum": checksum(document)})
            )
        return True


# ---------------------------------------------------------------- the work
class Rotation:
    """Re-encrypts with the primary key of ``keyset`` (which must also hold
    every key the stored values were encrypted with)."""

    def __init__(self, keyset_value: str):
        self.keyset = parse_keyset(keyset_value)
        self.cipher = CryptoService(encode_keyset(self.keyset))
        self.primary = self.keyset.primary_key_id

    def stale(self, values: Iterable[Tuple[Path, bytes]]) -> List[Tuple[Path, bytes]]:
        return [(p, v) for p, v in values if ciphertext_key_id(v) != self.primary]

    def _encrypt(self, context: Tuple[str, str], plaintext: bytes) -> bytes:
        # always encrypts, even a plaintext that starts with "v1:"
        return self.cipher.encrypt(*context, plaintext)

    def _open(self, contexts, value: bytes):
        """The first candidate context that decrypts ``value``, and the plaintext."""
        for context in contexts:
            try:
                return context, self.cipher.decrypt(*context, value)
            except UnreadableCiphertext:  # this context does not authenticate it
                continue
        return None, None

    def reencrypt(
        self, target: Target, record: Dict[str, Any], links: Dict[str, List[str]]
    ) -> Tuple[List[Update], List[Path]]:
        """The updates that put a record's stale values under the primary key,
        and the paths of the stale values no candidate context opens. Each
        value finds its own context: a record stored before responses carried
        their workspace may hold values from more than one."""
        contexts = target.contexts(record, links)
        updates: List[Update] = []
        unopenable: List[Path] = []
        for path, old in self.stale(target.values(record)):
            context, plaintext = self._open(contexts, old)
            if context is None:
                unopenable.append(path)
                continue
            new = self._encrypt(context, plaintext)
            if (
                ciphertext_key_id(new) != self.primary
                or self.cipher.decrypt(*context, new) != plaintext
            ):
                raise RuntimeError("a re-encrypted value did not read back")
            updates.append((path, old, new))
        return updates, unopenable


def _count_values(counts: Counter, rotation: Rotation, values) -> None:
    for _, value in values:
        key_id = ciphertext_key_id(value)
        counts["values"] += 1
        counts[f"values_key_{key_id if key_id is not None else 'unknown'}"] += 1
        if key_id != rotation.primary:
            counts["values_stale"] += 1


async def scan(
    store,
    target: Target,
    rotation: Rotation,
    batch_size: int,
    on_batch: Optional[Callable[[int], Any]] = None,
) -> Dict:
    """Counts only: records, values per key id, stale values. ``on_batch(records
    so far)`` is awaited after each batch; a true result stops the scan early
    and the counts then carry ``stopped``."""
    counts: Counter = Counter(records=0, values_stale=0)
    after = None
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        after = batch[-1]["id"]
        for record in batch:
            counts["records"] += 1
            values = target.values(record)
            _count_values(counts, rotation, values)
            if rotation.stale(values):
                counts["records_stale"] += 1
        if on_batch is not None and await on_batch(counts["records"]):
            counts["stopped"] = 1
            break
    return dict(counts)


async def verify_store(
    store,
    target: Target,
    rotation: Rotation,
    batch_size: int,
    on_batch: Optional[Callable[[int], Any]] = None,
) -> Dict:
    """Read-only: every value must open with the keyset (under some candidate
    context). Counts only: records, values, values per key id, values that do
    not open. Never keeps a plaintext."""
    counts: Counter = Counter(records=0, values_stale=0, values_unopenable=0)
    links = await store.links() if target.needs_links else {}
    after = None
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        after = batch[-1]["id"]
        for record in batch:
            counts["records"] += 1
            values = target.values(record)
            _count_values(counts, rotation, values)
            contexts = target.contexts(record, links)
            for _, value in values:
                context, _plain = rotation._open(contexts, value)
                counts[
                    "values_openable" if context is not None else "values_unopenable"
                ] += 1
        if on_batch is not None and await on_batch(counts["records"]):
            counts["stopped"] = 1
            break
    return dict(counts)


async def reencrypt_store(
    store,
    target: Target,
    rotation: Rotation,
    mirror=None,
    batch_size: int = 200,
    limit: Optional[int] = None,
    start_after: Optional[str] = None,
    on_batch: Optional[Callable[[str, Dict], Any]] = None,
    readback: bool = False,
) -> Tuple[Dict, Optional[str]]:
    """Re-encrypt one store (and copy each new value to ``mirror``); returns
    the counts and the last id walked. ``readback``: read each record again
    after writing it and count it re-encrypted only if the stored values are
    the ones written. ``on_batch(last id walked, counts so far)`` is awaited
    after each batch; a true result stops the walk (counts carry ``stopped``)."""
    counts: Counter = Counter()
    links = await store.links() if target.needs_links else {}
    after = start_after
    while limit is None or counts["records_reencrypted"] < limit:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        for record in batch:
            after = record["id"]  # the last id walked, for --start-after
            counts["records"] += 1
            updates, unopenable = rotation.reencrypt(target, record, links)
            if unopenable:
                counts["records_unopenable"] += 1
                counts["values_unopenable"] += len(unopenable)
                logger.warning(
                    "%s %s %s: no candidate context decrypts %d value(s); "
                    "left as they are",
                    target.name,
                    store.name,
                    record["id"],
                    len(unopenable),
                )
            if not updates:
                if not unopenable:
                    counts["records_current"] += 1
                continue
            if not await store.write(record["id"], updates):
                counts["records_changed_concurrently"] += 1
                logger.info(
                    "%s %s %s changed while it was read; left for the next run",
                    target.name,
                    store.name,
                    record["id"],
                )
                continue
            if readback and not await _read_back(store, record["id"], updates):
                counts["records_readback_failed"] += 1
                logger.warning(
                    "%s %s %s did not read back as written; not counted",
                    target.name,
                    store.name,
                    record["id"],
                )
                continue
            counts["records_reencrypted"] += 1
            counts["values_reencrypted"] += len(updates)
            if mirror is not None:
                # the same ciphertext, where the mirror holds the same old value
                if await mirror.write(record["id"], updates):
                    counts["mirror_records_copied"] += 1
            if limit is not None and counts["records_reencrypted"] >= limit:
                break
        logger.info(
            "%s %s: walked to %s; %s",
            target.name,
            store.name,
            after,
            json.dumps(dict(counts), sort_keys=True),
        )
        if on_batch is not None and await on_batch(after, dict(counts)):
            counts["stopped"] = 1
            break
    return dict(counts), after


async def _read_back(store, record_id: str, updates: Sequence[Update]) -> bool:
    """Whether the store now holds, for each path, the value that was written."""
    fresh = await store.read(record_id)
    if fresh is None:
        return False
    for path, _, new in updates:
        try:
            if bytes(_get(fresh, path)) != new:
                return False
        except (KeyError, IndexError, TypeError):
            return False
    return True


async def run_reencrypt(
    target: Target,
    stores: Sequence,
    rotation: Rotation,
    dry_run: bool,
    batch_size: int = 200,
    limit: Optional[int] = None,
    start_after: Optional[str] = None,
) -> Dict[str, Any]:
    """``stores``: primary first, then the mirror (if any)."""
    report: Dict[str, Any] = {}
    if dry_run:
        for store in stores:
            report[store.name] = await scan(store, target, rotation, batch_size)
        return report
    primary, mirror = stores[0], (stores[1] if len(stores) > 1 else None)
    report[primary.name], last = await reencrypt_store(
        primary, target, rotation, mirror, batch_size, limit, start_after
    )
    if mirror is not None and limit is None:
        # what the copy could not cover: rows only the mirror holds, or whose
        # value differed from the primary's
        report[mirror.name], _ = await reencrypt_store(
            mirror, target, rotation, None, batch_size, None, start_after
        )
    report["last_id"] = last
    return report
