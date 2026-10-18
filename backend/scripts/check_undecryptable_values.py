"""Count stored response values that carry the ciphertext prefix but do not
decrypt. Read-only.

    uv run python -m scripts.check_undecryptable_values
    uv run python -m scripts.check_undecryptable_values --store mongo

Until ``CryptoService.encrypt`` stopped doing so, a plaintext starting with
``v1:`` (the ciphertext prefix) was stored as is, unencrypted. Such a value
looks like ciphertext and does not decrypt; reads now return it as unreadable
instead of failing. This finds out whether any exist, in Mongo
(``MONGO_URI``/``MONGO_DB``) and, when ``DATABASE_URL`` is set, in the
Postgres twin. Needs ``MASTER_ENCRYPTION_KEYSET``.

Checked on each response (``form_responses``): ``answers``, ``hidden_fields``,
``internal_answers`` and every ``respondent_feedback`` message. Each value is
tried under its response's workspace, or under every workspace the form is
linked to when the response has none (stored before #768).

Prints counts per store and field as JSON: values with the prefix, how many
decrypt, how many don't and, of those, how many read as UTF-8 text (likely a
plaintext stored unencrypted) rather than binary (corrupted, or another key).
Never prints ids, values or plaintext, and never writes. Answers, hidden fields
and internal answers are always stored as JSON (``{...}``), so only feedback
messages can be plaintext that happened to start with the prefix.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

CIPHERTEXT_PREFIX = b"v1:"
FIELDS = ("answers", "hidden_fields", "internal_answers")
FEEDBACK = "respondent_feedback.message"

Opener = Callable[[str, str, bytes], bool]


def default_opener() -> Opener:
    """``opens(workspace_id, form_id, value)``: whether ``value`` decrypts."""
    from common.services.crypto_service import UnreadableCiphertext, crypto_service

    def opens(workspace_id: str, form_id: str, value: bytes) -> bool:
        try:
            crypto_service.decrypt(
                workspace_id=workspace_id, form_id=form_id, data=value
            )
        except UnreadableCiphertext:
            return False
        return True  # the plaintext is dropped here, never kept or printed

    return opens


def _prefixed(value: Any) -> Optional[bytes]:
    if isinstance(value, (bytes, bytearray)) and bytes(value).startswith(
        CIPHERTEXT_PREFIX
    ):
        return bytes(value)
    return None


def _looks_like_text(value: bytes) -> bool:
    try:
        text = value[len(CIPHERTEXT_PREFIX) :].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return all(c.isprintable() or c in "\n\r\t" for c in text)


def values_of(record: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
    """(field, stored value) of each encrypted value of one response."""
    for field in FIELDS:
        yield field, record.get(field)
    for entry in record.get("respondent_feedback") or []:
        if isinstance(entry, dict):
            yield FEEDBACK, entry.get("message")


def check_record(
    record: Dict[str, Any],
    links: Dict[str, List[str]],
    opens: Opener,
    counts: Dict[str, Counter],
) -> None:
    form_id = str(record.get("form_id"))
    workspace = record.get("workspace_id")
    candidates = [str(workspace)] if workspace else links.get(form_id) or []
    for field, raw in values_of(record):
        value = _prefixed(raw)
        if value is None:
            continue
        tally = counts[field]
        tally["prefixed"] += 1
        if not candidates:
            tally["no_workspace_to_try"] += 1
            continue
        if any(opens(w, form_id, value) for w in candidates):
            tally["decrypts"] += 1
            continue
        tally["does_not_decrypt"] += 1
        tally["of_which_text" if _looks_like_text(value) else "of_which_binary"] += 1


# --------------------------------------------------------------------- stores
class MongoStore:
    name = "mongo"

    def __init__(self, database):
        self.db = database  # pymongo AsyncDatabase

    async def links(self) -> Dict[str, List[str]]:
        from scripts.backfill_response_workspaces import MongoStore as Links

        return await Links(self.db).links()

    async def batch(self, after, limit: int) -> List[dict]:
        query: Dict[str, Any] = {}
        if after is not None:
            query["_id"] = {"$gt": after}
        projection = {
            "form_id": 1,
            "workspace_id": 1,
            "respondent_feedback.message": 1,
            **{field: 1 for field in FIELDS},
        }
        cursor = (
            self.db["form_responses"]
            .find(query, projection)
            .sort("_id", 1)
            .limit(limit)
        )
        return [{**row, "key": row["_id"]} async for row in cursor]


class PostgresStore:
    name = "postgres"

    def __init__(self, engine):
        self.engine = engine  # SQLAlchemy AsyncEngine

    async def links(self) -> Dict[str, List[str]]:
        from scripts.backfill_response_workspaces import PostgresStore as Links

        return await Links(self.engine).links()

    async def batch(self, after, limit: int) -> List[dict]:
        from sqlalchemy import select, text

        from backend.db.models import FormResponseRow as row
        from common.db.canonical import from_canonical_document

        keys = (*FIELDS, "respondent_feedback")
        stmt = select(
            row.id, row.form_id, row.workspace_id, *(row.doc[k] for k in keys)
        )
        if after is not None:
            stmt = stmt.where(row.id > after)
        stmt = stmt.order_by(row.id).limit(limit)
        records = []
        async with self.engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            for values in await conn.execute(stmt):
                stored = {k: v for k, v in zip(keys, values[3:]) if v is not None}
                records.append(
                    {
                        "key": values[0],
                        "form_id": values[1],
                        "workspace_id": values[2],
                        **from_canonical_document(stored),
                    }
                )
        return records


# ------------------------------------------------------------------------ run
async def check_store(store, opens: Opener, batch_size: int = 500) -> Dict[str, Any]:
    links = await store.links()
    counts: Dict[str, Counter] = defaultdict(Counter)
    responses = 0
    after = None
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        after = batch[-1]["key"]
        for record in batch:
            responses += 1
            check_record(record, links, opens, counts)
    return {
        "responses": responses,
        "fields": {field: dict(tally) for field, tally in sorted(counts.items())},
        "does_not_decrypt": sum(t["does_not_decrypt"] for t in counts.values()),
    }


async def run(stores, opens: Opener, batch_size: int = 500) -> Dict[str, Any]:
    return {
        "stores": {
            store.name: await check_store(store, opens, batch_size) for store in stores
        }
    }


def _parse(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.check_undecryptable_values",
        description="Count stored values with the ciphertext prefix that do not "
        "decrypt (read-only, counts only).",
    )
    parser.add_argument(
        "--store",
        choices=("all", "mongo", "postgres"),
        default="all",
        help="all = Mongo, plus Postgres when DATABASE_URL is set",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args(argv)


async def _main(argv: List[str]) -> int:
    args = _parse(argv)
    if not os.environ.get("MASTER_ENCRYPTION_KEYSET"):
        print("MASTER_ENCRYPTION_KEYSET is not set.", file=sys.stderr)
        return 2
    url = os.environ.get("DATABASE_URL")
    if args.store == "postgres" and not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    from pymongo import AsyncMongoClient

    # MONGO_URI / MONGO_DB only: no other backend setting is needed
    from backend.config.database import MongoSettings

    stores, closers = [], []
    if args.store in ("all", "mongo"):
        mongo = MongoSettings()
        client = AsyncMongoClient(mongo.URI)
        stores.append(MongoStore(client[mongo.DB]))
        closers.append(client.close)
    if url and args.store in ("all", "postgres"):
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url)
        stores.append(PostgresStore(engine))
        closers.append(engine.dispose)
    try:
        report = await run(stores, default_opener(), args.batch_size)
    finally:
        for close in closers:
            await close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
