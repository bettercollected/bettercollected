"""Count stored response values that carry the ciphertext prefix but do not
decrypt. Read-only.

    uv run python -m scripts.check_undecryptable_values

Until ``CryptoService.encrypt`` stopped doing so, a plaintext starting with
``v1:`` (the ciphertext prefix) was stored as is, unencrypted. Such a value
looks like ciphertext and does not decrypt; reads now return it as unreadable
instead of failing. This finds out whether any exist, in Postgres
(``DATABASE_URL``, the only store since 4.1). Needs ``MASTER_ENCRYPTION_KEYSET``.
``--store mongo`` and ``--store all`` (Mongo and Postgres) are refused
(``store_retired``) before anything connects.

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
from typing import List

from backend.admin.tasks.impl.responses_scan import (  # noqa: F401 - the CLI's public names
    FEEDBACK,
    FIELDS,
    Opener,
    PostgresStore,
    check_record,
    check_store,
    default_opener,
    run,
    values_of,
)


def _parse(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.check_undecryptable_values",
        description="Count stored values with the ciphertext prefix that do not "
        "decrypt (read-only, counts only).",
    )
    parser.add_argument(
        "--store",
        choices=("all", "mongo", "postgres"),
        default="postgres",
        help="postgres; mongo and all (Mongo too) are refused: store_retired",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args(argv)


async def _main(argv: List[str]) -> int:
    args = _parse(argv)
    if args.store != "postgres":
        print(
            "refused (store_retired): Mongo is no longer covered; use --store postgres.",
            file=sys.stderr,
        )
        return 2
    if not os.environ.get("MASTER_ENCRYPTION_KEYSET"):
        print("MASTER_ENCRYPTION_KEYSET is not set.", file=sys.stderr)
        return 2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        report = await run(
            [PostgresStore(engine)], default_opener(), args.batch_size
        )
    finally:
        await engine.dispose()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
