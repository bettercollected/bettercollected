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
and left for the next run). Which stores it covers follows the store rule of
the keyset tasks (docs/response-keyset-rotation.md, "The store rule"): with
``--store auto`` (the default), every store the services write for the
target's group (``DB_WRITE_MODE__RESPONSES`` / ``DB_WRITE_MODE__GOOGLE``, else
``DB_WRITE_MODE``), primary first, then any other store configured here
(``MONGO_URI``; ``DATABASE_URL``, or ``GOOGLE_DATABASE_URL`` for the Google
credentials). An unset or unknown write mode is refused
(``write_mode_unknown``), never guessed; ``--store mongo|postgres|both``
names the stores instead and needs no write mode. The primary store's new
ciphertext is copied unchanged to the other, so the stores stay identical.
``--dry-run`` counts only.

``reencrypt`` (apart from ``--dry-run``) and ``drop-old`` only work with the
keyset the services run with: the primary key of ``--keyset-file`` must be the
primary of ``MASTER_ENCRYPTION_KEYSET`` in the environment, so nothing is ever
re-encrypted under a key the services do not have.

``drop-old`` always scans every target in every store of that rule
(``--target`` / ``--store`` are refused). It refuses, writing nothing, while
any value still uses a key other than the primary, or while a store the
services write holds no records at all: a wrong or empty database would
otherwise pass as clean (``--allow-empty`` when that is really so). Otherwise
it writes a keyset holding the primary key only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.impl.keyset_core import (  # noqa: F401 - re-exported
    GOOGLE_CREDENTIALS,
    RESPONSES,
    TARGETS,
    MongoStore,
    PostgresStore,
    Rotation,
    Target,
    run_reencrypt,
    scan,
)
from backend.admin.tasks.impl.responses_common import (
    plan_task_stores,
    written_stores,
)
from backend.admin.tasks.spec import Refusal
from common.services.keyset import (
    KEYSET_ENV,
    KeysetError,
    add_primary_key,
    describe_keyset,
    encode_keyset,
    only_primary,
    parse_keyset,
    published_key_ids,
)

logger = logging.getLogger("rotate_response_keyset")


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
            help="auto = every store the services write (DB_WRITE_MODE*; refused "
            "when unset), then any other configured store",
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
    """Mongo URI, Mongo database and Postgres URL a target lives in (an empty
    URI or URL: that store is not configured here)."""
    uri = (env.get("MONGO_URI") or "").strip()
    if target is GOOGLE_CREDENTIALS:
        database = env.get("GOOGLE_MONGO_DB", "bettercollected_googleform")
        url = env.get("GOOGLE_DATABASE_URL") or env.get("DATABASE_URL") or ""
    else:
        database = env.get("MONGO_DB", "bettercollected_backend")
        url = env.get("DATABASE_URL") or ""
    return uri, database, url.strip()


STORE_REFUSALS = {
    "write_mode_unknown": (
        "no write mode for {group}: set DB_WRITE_MODE__{GROUP} or DB_WRITE_MODE "
        "to the value the services run with (mongo, dual, postgres_primary_dual "
        "or postgres), or name the stores with --store"
    ),
    "store_not_configured": (
        "a store it needs is not configured here (MONGO_URI, or {url_setting} "
        "for Postgres)"
    ),
}


def plan_stores(target: Target, store_choice: str, env=os.environ) -> List[str]:
    """Store names for ``target``, primary first, by the keyset tasks' store
    rule (``responses_common.plan_task_stores``). Raises ``Refusal``
    (``write_mode_unknown`` / ``store_not_configured``)."""
    uri, _, url = _target_settings(target, env)
    configured = [name for name, ok in (("mongo", uri), ("postgres", url)) if ok]
    return plan_task_stores(StoreChoice(store_choice), configured, target.group, env)


def store_refusal_message(refusal: Refusal, target: Target) -> str:
    """The reason, naming settings only (never their values)."""
    url_setting = (
        "GOOGLE_DATABASE_URL / DATABASE_URL"
        if target is GOOGLE_CREDENTIALS
        else "DATABASE_URL"
    )
    template = STORE_REFUSALS.get(refusal.code, "")
    return f"{target.name}: refused ({refusal.code}): " + template.format(
        group=target.group, GROUP=target.group.upper(), url_setting=url_setting
    )


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
    # every target's stores are planned before anything is opened or written
    plans: Dict[str, List[str]] = {}
    written: Dict[str, List[str]] = {}
    for target in targets:
        try:
            plans[target.name] = plan_stores(target, args.store)
            if args.command == "drop-old":
                written[target.name] = written_stores(target.group, os.environ)
        except Refusal as refusal:
            print(store_refusal_message(refusal, target), file=sys.stderr)
            return 2
    report: Dict[str, Any] = {
        "command": args.command,
        "keyset": describe_keyset(keyset),
        "targets": {},
    }
    closers: list = []
    try:
        for target in targets:
            stores = await _open_stores(target, plans[target.name], closers)
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
        # a store the services write must hold records; another configured
        # store (one they no longer write) may be empty
        empty = [
            f"{target} in {store}"
            for target, stores in report["records"].items()
            for store, records in stores.items()
            if records == 0 and store in written[target]
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
