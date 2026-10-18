"""Rotate ``MASTER_ENCRYPTION_KEYSET``, the Tink keyset stored data is encrypted with.

Runbook with the order across services: docs/response-keyset-rotation.md.

    # 1. a new keyset: the current keys plus a new AES-256-GCM primary
    uv run python -m scripts.rotate_response_keyset add-key --out rotated.keyset
    # 2. deploy rotated.keyset to every service, then
    uv run python -m scripts.rotate_response_keyset reencrypt --keyset-file rotated.keyset --dry-run
    uv run python -m scripts.rotate_response_keyset reencrypt --keyset-file rotated.keyset
    # 3. once nothing uses the old keys
    uv run python -m scripts.rotate_response_keyset drop-old --keyset-file rotated.keyset --out final.keyset

The keyset is read from ``--keyset-file`` (the value, optionally as a
``MASTER_ENCRYPTION_KEYSET=...`` line) or else from the environment, and
written only to new files with mode 600. It is never printed: the commands
print key ids and counts as JSON, and log record ids and counts.

What is encrypted with the keyset (``common.services.crypto_service``):

* ``responses``: in each stored response, ``answers``, ``hidden_fields``,
  ``internal_answers`` and every ``respondent_feedback[].message``, with the
  associated data ``<workspace_id>|<form_id>|``. The workspace is the one the
  response is stamped with, else (stored before #768) each workspace its form
  is linked to is tried. Mongo ``form_responses`` / Postgres
  ``app.form_responses``.
* ``google-credentials``: the Google Forms integration's OAuth credentials
  (``personal|<user_id>|``). Mongo ``Oauth2CredentialDocument`` in the
  integration's database / Postgres ``google.oauth_credentials``.

``reencrypt`` walks a target in batches by id. Tink ciphertexts start with
the id of their key, so a value already under the primary key is skipped
without decrypting it: the command is idempotent, and an interrupted run is
resumed by running it again (``--start-after <id>`` skips the ids done). A
value is decrypted with the full keyset, encrypted with the primary key,
checked to decrypt back to the same bytes and written only if the stored value
is still the one read (a value the application changed meanwhile is counted
and left for the next run). Which stores it writes follows the write mode
(``DB_WRITE_MODE``, as the services use it): in a dual mode the primary
store's new ciphertext is copied unchanged to the mirror, so the two stores
stay identical. ``--dry-run`` counts only.

``reencrypt`` (apart from ``--dry-run``) and ``drop-old`` only work with the
keyset the services run with: the primary key of ``--keyset-file`` must be the
primary of ``MASTER_ENCRYPTION_KEYSET`` in the environment, so nothing is ever
re-encrypted under a key the services do not have.

``drop-old`` always scans every target in every store the services write
(``--target`` / ``--store`` are refused). It refuses, writing nothing, while
any value still uses a key other than the primary, or while any store holds no
records at all: a wrong or empty database would otherwise pass as clean
(``--allow-empty`` when that is really so). Otherwise it writes a keyset
holding the primary key only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from common.services.keyset import (
    KEYSET_ENV,
    CryptoService,
    KeysetError,
    UnreadableCiphertext,
    add_primary_key,
    ciphertext_key_id,
    describe_keyset,
    encode_keyset,
    is_ciphertext,
    only_primary,
    parse_keyset,
    published_key_ids,
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

    def __init__(self, database, target: Target):
        self.db = database  # pymongo AsyncDatabase
        self.target = target

    def key(self, record_id: str):
        from bson import ObjectId

        return ObjectId(record_id) if ObjectId.is_valid(record_id) else record_id

    async def links(self) -> Dict[str, List[str]]:
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


async def scan(store, target: Target, rotation: Rotation, batch_size: int) -> Dict:
    """Counts only: records, values per key id, stale values."""
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
    return dict(counts)


async def reencrypt_store(
    store,
    target: Target,
    rotation: Rotation,
    mirror=None,
    batch_size: int = 200,
    limit: Optional[int] = None,
    start_after: Optional[str] = None,
) -> Tuple[Dict, Optional[str]]:
    """Re-encrypt one store (and copy each new value to ``mirror``); returns
    the counts and the last id walked."""
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
    return dict(counts), after


def plan_stores(target: Target, store_choice: str, env=os.environ) -> List[str]:
    """Store names, primary first, as the services write the target's group."""
    if store_choice == "mongo":
        return ["mongo"]
    if store_choice == "postgres":
        return ["postgres"]
    if store_choice == "both":
        return ["mongo", "postgres"]
    from common.db.flags import load_flags

    flags = load_flags(env)
    stores = [flags.primary_store(target.group).value]
    mirror = flags.mirror_store(target.group)
    if mirror is not None:
        stores.append(mirror.value)
    return stores


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


# ----------------------------------------------------------------------- CLI
TYPEFORM_NOTE = (
    "The Typeform integration (a separate image) also receives "
    "MASTER_ENCRYPTION_KEYSET; this script cannot check or re-encrypt what it "
    "stores. If you run it, keep the old key, or reconnect its accounts after "
    "deploying the final keyset."
)


def deployed_keyset_problem(keyset, env=os.environ) -> Optional[str]:
    """Why ``keyset`` must not be used to write: its primary key is not the
    primary of the keyset the services run with (``MASTER_ENCRYPTION_KEYSET``
    here, as in every service's environment). None when it is."""
    value = env.get(KEYSET_ENV, "")
    if not value.strip():
        return (
            f"{KEYSET_ENV} is not set here. Run this where the services' keyset "
            "is set (a backend container), after deploying the new keyset."
        )
    try:
        deployed = parse_keyset(value)
    except KeysetError as error:
        return f"{KEYSET_ENV} here is not usable: {error}"
    if deployed.primary_key_id != keyset.primary_key_id:
        return (
            f"The keyset's primary key ({keyset.primary_key_id}) is not the primary "
            f"of the deployed {KEYSET_ENV} ({deployed.primary_key_id}). Deploy the "
            "keyset to every service first (docs/response-keyset-rotation.md, "
            "step 3) and run this in a container started after that, so nothing "
            "is re-encrypted under a key the services do not have."
        )
    return None


def read_keyset_value(path: Optional[str], env=os.environ) -> str:
    if path:
        with open(path, encoding="utf-8") as handle:
            value = handle.read().strip()
        if value.startswith(KEYSET_ENV + "="):
            value = value[len(KEYSET_ENV) + 1 :]
        return value
    value = env.get(KEYSET_ENV, "")
    if not value.strip():
        raise KeysetError(f"{KEYSET_ENV} is not set; pass --keyset-file")
    return value


def write_keyset_file(path: str, value: str) -> None:
    """A new file, mode 600; never overwrites one."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(value + "\n")
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _parse(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.rotate_response_keyset",
        description="Rotate MASTER_ENCRYPTION_KEYSET (docs/response-keyset-rotation.md).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def keyset_option(command):
        command.add_argument(
            "--keyset-file",
            help=f"file holding the keyset (default: ${KEYSET_ENV})",
        )

    def store_options(command):
        command.add_argument(
            "--target",
            action="append",
            choices=sorted(TARGETS),
            help="what to process (repeatable; default: all)",
        )
        command.add_argument(
            "--store",
            choices=("auto", "mongo", "postgres", "both"),
            default="auto",
            help="auto = as DB_WRITE_MODE has the services write the target",
        )
        command.add_argument("--batch-size", type=int, default=200)

    add_key = commands.add_parser("add-key", help="add a new primary key")
    keyset_option(add_key)
    add_key.add_argument("--out", required=True, help="new file for the keyset")

    reencrypt = commands.add_parser(
        "reencrypt", help="re-encrypt stored values with the primary key"
    )
    keyset_option(reencrypt)
    store_options(reencrypt)
    reencrypt.add_argument(
        "--dry-run", action="store_true", help="count only; change nothing"
    )
    reencrypt.add_argument(
        "--limit", type=int, help="re-encrypt at most this many records per target"
    )
    reencrypt.add_argument(
        "--start-after", help="skip the records up to this id (resume)"
    )

    drop_old = commands.add_parser(
        "drop-old", help="keep only the primary key, once nothing uses the others"
    )
    keyset_option(drop_old)
    store_options(drop_old)
    drop_old.add_argument("--out", required=True, help="new file for the keyset")
    drop_old.add_argument(
        "--allow-empty",
        action="store_true",
        help="accept a store that holds no records (e.g. Google Forms never used)",
    )
    return parser.parse_args(argv)


def _target_settings(target: Target, env=os.environ) -> Tuple[str, str, str]:
    """Mongo URI, Mongo database and Postgres URL a target lives in."""
    uri = env.get("MONGO_URI", "mongodb://localhost")
    if target is GOOGLE_CREDENTIALS:
        database = env.get("GOOGLE_MONGO_DB", "bettercollected_googleform")
        url = env.get("GOOGLE_DATABASE_URL") or env.get("DATABASE_URL", "")
    else:
        database = env.get("MONGO_DB", "bettercollected_backend")
        url = env.get("DATABASE_URL", "")
    return uri, database, url


async def _open_stores(target: Target, names: List[str], closers: list) -> List:
    uri, database, url = _target_settings(target)
    stores = []
    for name in names:
        if name == "mongo":
            from pymongo import AsyncMongoClient

            client = AsyncMongoClient(uri)
            closers.append(client.close)
            stores.append(MongoStore(client[database], target))
        else:
            if not url:
                raise KeysetError(
                    f"{target.name}: Postgres is in use but DATABASE_URL"
                    + (" / GOOGLE_DATABASE_URL" if target is GOOGLE_CREDENTIALS else "")
                    + " is not set"
                )
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            closers.append(engine.dispose)
            stores.append(PostgresStore(engine, target))
    return stores


async def _main(argv: List[str]) -> int:
    args = _parse(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        keyset = parse_keyset(read_keyset_value(args.keyset_file))
    except (KeysetError, OSError) as error:
        print(f"Cannot read the keyset: {error}", file=sys.stderr)
        return 2

    if args.command == "add-key":
        rotated = add_primary_key(keyset)
        try:
            write_keyset_file(args.out, encode_keyset(rotated))
        except FileExistsError:
            print(f"{args.out} exists; choose a new file.", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {"written": args.out, **describe_keyset(rotated)},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    rotation = Rotation(encode_keyset(keyset))
    dry_run = args.command == "reencrypt" and args.dry_run
    if keyset.primary_key_id in published_key_ids(keyset) and not dry_run:
        print(
            "The keyset's primary key is a published one: run add-key first and "
            "deploy its keyset to every service.",
            file=sys.stderr,
        )
        return 2
    if not dry_run:
        problem = deployed_keyset_problem(keyset)
        if problem:
            print(problem, file=sys.stderr)
            return 2
    if args.command == "drop-old" and (args.target or args.store != "auto"):
        print(
            "drop-old always checks every target in every store the services "
            "write: run it without --target and --store. Dropping a key after "
            "checking only part of the data would make the rest unreadable.",
            file=sys.stderr,
        )
        return 2
    targets = [TARGETS[name] for name in (args.target or sorted(TARGETS))]
    report: Dict[str, Any] = {
        "command": args.command,
        "keyset": describe_keyset(keyset),
        "targets": {},
    }
    closers: list = []
    try:
        for target in targets:
            stores = await _open_stores(
                target, plan_stores(target, args.store), closers
            )
            if args.command == "reencrypt":
                report["mode"] = "dry-run" if args.dry_run else "apply"
                report["targets"][target.name] = await run_reencrypt(
                    target,
                    stores,
                    rotation,
                    dry_run=args.dry_run,
                    batch_size=args.batch_size,
                    limit=args.limit,
                    start_after=args.start_after,
                )
            else:
                report["targets"][target.name] = {
                    store.name: await scan(store, target, rotation, args.batch_size)
                    for store in stores
                }
    finally:
        for close in closers:
            await close()

    if args.command == "drop-old":
        report["note"] = TYPEFORM_NOTE
        report["records"] = {
            target: {store: counts["records"] for store, counts in stores.items()}
            for target, stores in report["targets"].items()
        }
        stale = sum(
            counts["values_stale"]
            for stores in report["targets"].values()
            for counts in stores.values()
        )
        report["values_stale"] = stale
        empty = [
            f"{target} in {store}"
            for target, stores in report["records"].items()
            for store, records in stores.items()
            if records == 0
        ]
        if stale:
            report["refused"] = (
                "values still use a key other than the primary: run reencrypt "
                "until it reports none, then drop-old again"
            )
        elif empty and not args.allow_empty:
            report["refused"] = (
                "no records at all in: "
                + ", ".join(empty)
                + ". If the script reads the wrong or an empty database (MONGO_DB, "
                "GOOGLE_MONGO_DB, DATABASE_URL, GOOGLE_DATABASE_URL), dropping the "
                "old key would make the real data unreadable. Pass --allow-empty "
                "only if these really hold nothing (e.g. Google Forms never used)."
            )
        if "refused" in report:
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1
        if len(keyset.key) == 1:
            report["nothing_to_drop"] = True
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        final = only_primary(keyset)
        try:
            write_keyset_file(args.out, encode_keyset(final))
        except FileExistsError:
            print(f"{args.out} exists; choose a new file.", file=sys.stderr)
            return 2
        report["written"] = args.out
        report["dropped_key_ids"] = [
            key.key_id for key in keyset.key if key.key_id != keyset.primary_key_id
        ]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return asyncio.run(_main(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
