"""Stamp stored responses with the workspace they belong to (#768).

    uv run python -m scripts.backfill_response_workspaces            # dry run
    uv run python -m scripts.backfill_response_workspaces --apply
    uv run python -m scripts.backfill_response_workspaces --workspace-id W --form-id F

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

``--workspace-id`` / ``--form-id`` (repeatable) limit a run to the records of
forms linked to that workspace / of those forms. The logic lives in
``backend.admin.tasks.impl.responses_backfill``, shared with the admin task
runner (``responses.backfill_workspaces``); this script stays as the
break-glass CLI.

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
from typing import List

from backend.admin.tasks.impl.responses_backfill import (  # noqa: F401 - the CLI's public names
    ENCRYPTED_FIELDS,
    Attributor,
    MongoStore,
    PostgresStore,
    backfill_store,
    default_opener,
    run,
)


def _non_empty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


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
    parser.add_argument(
        "--workspace-id",
        type=_non_empty,
        default=argparse.SUPPRESS,
        help="only records of forms linked to this workspace",
    )
    parser.add_argument(
        "--form-id",
        action="append",
        type=_non_empty,
        dest="form_ids",
        default=argparse.SUPPRESS,
        help="only records of this form (repeatable)",
    )
    return parser.parse_args(argv)


async def _main(argv: List[str]) -> int:
    args = _parse(argv)
    from pymongo import AsyncMongoClient

    # MONGO_URI / MONGO_DB only: no other backend setting is needed
    from backend.config.database import MongoSettings

    url = os.environ.get("DATABASE_URL")
    if args.store == "postgres" and not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    stores, closers = [], []
    if args.store in ("all", "mongo"):
        mongo = MongoSettings()
        client = AsyncMongoClient(mongo.URI)
        stores.append(MongoStore(client[mongo.DB]))
        closers.append(client.close)
    if url:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url)
        closers.append(engine.dispose)
        postgres = PostgresStore(engine)
        for store in stores:  # Mongo reads the forms' links from Postgres (4.1)
            store.links_source = postgres
        if args.store in ("all", "postgres"):
            stores.append(postgres)
    try:
        report = await run(
            stores,
            apply=args.apply,
            opens=default_opener(),
            batch_size=args.batch_size,
            workspace_id=getattr(args, "workspace_id", None),
            form_ids=getattr(args, "form_ids", None),
        )
    finally:
        for close in closers:
            await close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
