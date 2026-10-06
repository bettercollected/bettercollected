"""Stamp stored responses with the workspace they belong to (#768).

    uv run python -m scripts.backfill_response_workspaces            # dry run
    uv run python -m scripts.backfill_response_workspaces --apply

Responses (``form_responses``) and deletion requests
(``responses_deletion_requests``) stored before ``workspace_id`` existed carry
none. This attributes each one, in Mongo (``MONGO_URI``/``MONGO_DB``) and, when
``DATABASE_URL`` is set, in the Postgres twin:

* the form is linked to exactly one workspace -> that workspace;
* the form is linked to several workspaces -> the workspace whose key context
  opens the stored ciphertext. ``answers`` (else ``hidden_fields``, else
  ``internal_answers``) are encrypted with an AEAD whose associated data is
  ``workspace_id|form_id``, so exactly one candidate workspace authenticates
  it: the one whose import or submission stored it. Needs
  ``MASTER_ENCRYPTION_KEYSET``. The plaintext is discarded unread;
* nothing to authenticate (no answers, plaintext answers, key unavailable) on a
  form linked to several workspaces -> ambiguous: left unstamped, so it stays
  hidden from every workspace (there is deliberately no option to guess: an
  ambiguous record may be any of the workspaces' respondents' data). While a
  form has such records it cannot be unlinked from one of its workspaces
  (409), so they never pass to the remaining one;
* the form is linked to no workspace -> orphaned, left alone.

A deletion request takes its response's workspace (as stamped, or as this run
attributes it), else the same rules by its form.

Dry run by default: prints counts per store and bucket as JSON, never ids,
answers or identities, and changes nothing. ``--apply`` stamps what can be
attributed; it only ever sets ``workspace_id`` where it is missing, so it is
idempotent and can be interrupted and run again (it resumes by skipping what is
already stamped).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from bson import ObjectId

CIPHERTEXT_PREFIX = b"v1:"
ENCRYPTED_FIELDS = ("answers", "hidden_fields", "internal_answers")


# --------------------------------------------------------------- attribution
def _ciphertext(record: Dict[str, Any]) -> Optional[bytes]:
    for field in ENCRYPTED_FIELDS:
        value = record.get(field)
        if isinstance(value, (bytes, bytearray)) and bytes(value).startswith(
            CIPHERTEXT_PREFIX
        ):
            return bytes(value)
    return None


def default_opener() -> Optional[Callable[[str, str, bytes], bool]]:
    """``opens(workspace_id, form_id, ciphertext)``, or None without a key."""
    if not os.environ.get("MASTER_ENCRYPTION_KEYSET"):
        return None
    from common.services.crypto_service import crypto_service

    def opens(workspace_id: str, form_id: str, ciphertext: bytes) -> bool:
        try:
            crypto_service.decrypt(
                workspace_id=workspace_id, form_id=form_id, data=ciphertext
            )
        except Exception:  # tink: the context does not authenticate it
            return False
        return True  # the plaintext is dropped here, never kept or printed

    return opens


class Attributor:
    """Decides the workspace of one record from the form's links."""

    def __init__(
        self,
        links: Dict[str, List[str]],
        opens: Optional[Callable[[str, str, bytes], bool]],
    ):
        # form_id -> workspace ids, first linked first
        self.links = links
        self.opens = opens

    def by_form(self, form_id: str) -> Tuple[str, Optional[str]]:
        workspaces = self.links.get(str(form_id)) or []
        if not workspaces:
            return "orphaned", None
        if len(workspaces) == 1:
            return "single_workspace", workspaces[0]
        return "ambiguous", None

    def response(self, record: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        form_id = str(record.get("form_id"))
        workspaces = self.links.get(form_id) or []
        if len(workspaces) > 1:
            ciphertext = _ciphertext(record)
            if ciphertext is not None and self.opens is not None:
                matches = [w for w in workspaces if self.opens(w, form_id, ciphertext)]
                if len(matches) == 1:
                    return "attributed_by_encryption", matches[0]
        return self.by_form(form_id)


# --------------------------------------------------------------------- stores
class MongoStore:
    name = "mongo"

    def __init__(self, database):
        self.db = database  # pymongo AsyncDatabase

    async def links(self) -> Dict[str, List[str]]:
        links: Dict[str, List[str]] = defaultdict(list)
        cursor = (
            self.db["workspace_forms"]
            .find({}, {"form_id": 1, "workspace_id": 1})
            .sort("_id", 1)
        )
        async for row in cursor:
            workspace = str(row.get("workspace_id"))
            form_id = str(row.get("form_id"))
            if row.get("workspace_id") and workspace not in links[form_id]:
                links[form_id].append(workspace)
        return links

    async def unstamped(self, collection: str, after, limit: int) -> List[dict]:
        query: Dict[str, Any] = {"workspace_id": None}
        if after is not None:
            query["_id"] = {"$gt": after}
        projection = {"form_id": 1, "response_id": 1}
        if collection == "form_responses":
            projection.update({field: 1 for field in ENCRYPTED_FIELDS})
        cursor = self.db[collection].find(query, projection).sort("_id", 1).limit(limit)
        return [{**row, "key": row["_id"]} async for row in cursor]

    async def response_workspaces(self, response_ids: Iterable[str]) -> Dict[str, str]:
        ids = list(set(response_ids))
        if not ids:
            return {}
        cursor = self.db["form_responses"].find(
            {"response_id": {"$in": ids}, "workspace_id": {"$ne": None}},
            {"response_id": 1, "workspace_id": 1},
        )
        return {row["response_id"]: str(row["workspace_id"]) async for row in cursor}

    async def stamp(self, collection: str, key, workspace_id: str) -> int:
        result = await self.db[collection].update_one(
            {"_id": key, "workspace_id": None},
            {"$set": {"workspace_id": ObjectId(workspace_id)}},
        )
        return result.modified_count


class PostgresStore:
    name = "postgres"

    def __init__(self, engine):
        self.engine = engine  # SQLAlchemy AsyncEngine

    @staticmethod
    def _row(collection: str):
        from backend.db.models import FormResponseRow, ResponseDeletionRequestRow

        return {
            "form_responses": FormResponseRow,
            "responses_deletion_requests": ResponseDeletionRequestRow,
        }[collection]

    async def links(self) -> Dict[str, List[str]]:
        from sqlalchemy import select

        from backend.db.models import WorkspaceFormRow

        links: Dict[str, List[str]] = defaultdict(list)
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                select(
                    WorkspaceFormRow.form_id, WorkspaceFormRow.workspace_id
                ).order_by(WorkspaceFormRow.id)
            )
            for form_id, workspace in rows:
                if workspace and workspace not in links[str(form_id)]:
                    links[str(form_id)].append(workspace)
        return links

    async def unstamped(self, collection: str, after, limit: int) -> List[dict]:
        from sqlalchemy import select

        from common.db.canonical import from_canonical_document

        row = self._row(collection)
        columns = [row.id, row.form_id, row.response_id]
        if collection == "form_responses":
            columns += [row.doc[field] for field in ENCRYPTED_FIELDS]
        stmt = select(*columns).where(row.workspace_id.is_(None))
        if after is not None:
            stmt = stmt.where(row.id > after)
        stmt = stmt.order_by(row.id).limit(limit)
        records = []
        async with self.engine.connect() as conn:
            for values in await conn.execute(stmt):
                record = {
                    "key": values[0],
                    "form_id": values[1],
                    "response_id": values[2],
                }
                if collection == "form_responses":
                    encrypted = {
                        field: value
                        for field, value in zip(ENCRYPTED_FIELDS, values[3:])
                        if value is not None
                    }
                    record.update(from_canonical_document(encrypted))
                records.append(record)
        return records

    async def response_workspaces(self, response_ids: Iterable[str]) -> Dict[str, str]:
        from sqlalchemy import select

        from backend.db.models import FormResponseRow as r

        ids = list(set(response_ids))
        if not ids:
            return {}
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                select(r.response_id, r.workspace_id).where(
                    r.response_id.in_(ids), r.workspace_id.is_not(None)
                )
            )
            return {response_id: workspace for response_id, workspace in rows}

    async def stamp(self, collection: str, key, workspace_id: str) -> int:
        from sqlalchemy import select, update

        from common.db.canonical import checksum

        table = self._row(collection).__table__
        async with self.engine.begin() as conn:
            doc = (
                await conn.execute(
                    select(table.c.doc)
                    .where(table.c.id == key, table.c.workspace_id.is_(None))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return 0
            # the document as the application would store it, and its checksum
            doc = {**doc, "workspace_id": {"$oid": workspace_id}}
            await conn.execute(
                update(table)
                .where(table.c.id == key)
                .values({"doc": doc, "_bc_checksum": checksum(doc)})
            )
        return 1


# ------------------------------------------------------------------------ run
async def backfill_store(
    store,
    apply: bool,
    opens: Optional[Callable[[str, str, bytes], bool]],
    batch_size: int = 500,
) -> Dict[str, Any]:
    links = await store.links()
    attributor = Attributor(links, opens)
    report: Dict[str, Any] = {
        "forms_linked_to_several_workspaces": sum(
            1 for workspaces in links.values() if len(workspaces) > 1
        )
    }
    planned: Dict[str, str] = {}  # response_id -> workspace, this run

    counts: Counter = Counter()
    after = None
    while True:
        batch = await store.unstamped("form_responses", after, batch_size)
        if not batch:
            break
        after = batch[-1]["key"]
        for record in batch:
            counts["unstamped"] += 1
            bucket, workspace = attributor.response(record)
            counts[bucket] += 1
            if workspace is None:
                continue
            if record.get("response_id"):
                planned[str(record["response_id"])] = workspace
            if apply:
                counts["stamped"] += await store.stamp(
                    "form_responses", record["key"], workspace
                )
    report["responses"] = dict(counts)

    counts = Counter()
    after = None
    while True:
        batch = await store.unstamped("responses_deletion_requests", after, batch_size)
        if not batch:
            break
        after = batch[-1]["key"]
        stored = await store.response_workspaces(
            str(r["response_id"]) for r in batch if r.get("response_id")
        )
        for record in batch:
            counts["unstamped"] += 1
            response_id = str(record.get("response_id"))
            workspace = planned.get(response_id) or stored.get(response_id)
            if workspace is not None:
                bucket = "from_response"
            else:
                bucket, workspace = attributor.by_form(record.get("form_id"))
            counts[bucket] += 1
            if workspace is not None and apply:
                counts["stamped"] += await store.stamp(
                    "responses_deletion_requests", record["key"], workspace
                )
    report["deletion_requests"] = dict(counts)
    return report


async def run(stores, apply: bool, opens=None, batch_size: int = 500) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "encryption_key": opens is not None,
        "stores": {},
    }
    for store in stores:
        report["stores"][store.name] = await backfill_store(
            store, apply, opens, batch_size
        )
    return report


def _parse(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.backfill_response_workspaces",
        description="Stamp stored responses with their workspace (#768).",
    )
    parser.add_argument(
        "--apply", action="store_true", help="write (default: dry run, counts only)"
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
    from pymongo import AsyncMongoClient

    # MONGO_URI / MONGO_DB only: no other backend setting is needed
    from backend.config.database import MongoSettings

    stores, closers = [], []
    if args.store in ("all", "mongo"):
        mongo = MongoSettings()
        client = AsyncMongoClient(mongo.URI)
        stores.append(MongoStore(client[mongo.DB]))
        closers.append(client.close)
    url = os.environ.get("DATABASE_URL")
    if args.store == "postgres" and not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    if url and args.store in ("all", "postgres"):
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url)
        stores.append(PostgresStore(engine))
        closers.append(engine.dispose)
    try:
        report = await run(
            stores,
            apply=args.apply,
            opens=default_opener(),
            batch_size=args.batch_size,
        )
    finally:
        for close in closers:
            await close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
