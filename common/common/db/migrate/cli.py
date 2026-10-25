"""Command line for the migration engine; each service wraps it with its Target."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from types import ModuleType
from typing import Callable, Mapping, Optional, Sequence

from common.db.groups import (
    SERVICE_GROUPS,
    UnknownGroup,
    parse_groups,
    validate_groups,
)
from common.db.flags import FlagError, ReadSource, WriteMode, load_flags
from common.db.migrate.engine import Runner, Target
from common.db.schema_guard import MigrationTarget


def build_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Mongo → Postgres migration for one service: preflight, backfill, verify, reconcile, status.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--collections", help="comma-separated subset (default: all)"
    )
    selection.add_argument(
        "--group",
        action="append",
        metavar="GROUP",
        help="only the collections of this repository group (repeatable or "
        "comma-separated); verify then records the group as verified",
    )
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight", help="counts, invalid ids, duplicate unique keys")
    backfill = sub.add_parser("backfill", help="copy Mongo → Postgres, resumable")
    backfill.add_argument("--dry-run", action="store_true")
    backfill.add_argument(
        "--max-minutes",
        type=float,
        help="stop at the next checkpoint after this budget",
    )
    backfill.add_argument(
        "--max-batches", type=int, help="stop after N batches (tests, smoke runs)"
    )
    backfill.add_argument(
        "--restart", action="store_true", help="ignore checkpoints and start over"
    )
    backfill.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="initial batch size (adapts while running)",
    )
    verify = sub.add_parser(
        "verify", help="counts + checksum merge-join + sampled deep compare"
    )
    verify.add_argument(
        "--sample-every", type=int, default=1, help="check every k-th batch"
    )
    reconcile = sub.add_parser(
        "reconcile", help="fix what verify finds; drain outboxes"
    )
    reconcile.add_argument(
        "--direction",
        choices=["mongo->postgres", "postgres->mongo"],
        default="mongo->postgres",
    )
    reconcile.add_argument("--dry-run", action="store_true")
    status = sub.add_parser(
        "status",
        help="counts, checkpoints, stalls, outbox, mirror failures, last verify, marker",
    )
    status.add_argument(
        "--json",
        action="store_true",
        help="one machine-readable JSON document instead of the summary",
    )
    sweep = sub.add_parser(
        "jobs-sweep", help="(re)create scheduled deletions on a jobs backend"
    )
    sweep.add_argument(
        "--backend", choices=["postgres", "temporal"], default="postgres"
    )
    return parser


def _print(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def code_version(package: ModuleType, schema: str) -> str:
    """What the marker records as the code that verified: the package version
    and the schema's Alembic head(s) this code carries."""
    heads, _ = MigrationTarget.for_package(package, schema).code_revisions()
    version = getattr(package, "__version__", "") or "unknown"
    return f"{version}+schema.{'.'.join(heads) or 'none'}"


def valid_groups(target: Target) -> list[str]:
    return list(SERVICE_GROUPS.get(target.service) or target.group_names())


def select_collections(args: argparse.Namespace, target: Target) -> Optional[list[str]]:
    """The collections ``--collections`` or ``--group`` select; ``None`` = all.
    Raises :class:`UnknownGroup` for a group the service does not have."""
    if args.group:
        groups = validate_groups(parse_groups(args.group), valid_groups(target))
        if not groups:
            raise UnknownGroup(
                f"--group needs a group name; valid groups: {', '.join(valid_groups(target))}"
            )
        selected = [c for c in target.tables if target.group_of(c) in groups]
        if not selected:
            raise UnknownGroup(f"group(s) {', '.join(groups)} have no collections")
        return selected
    return [c for c in (args.collections or "").split(",") if c] or None


def format_status(report: dict) -> str:
    """The human summary of ``status_report`` (``status --json`` prints it whole)."""
    lines = [f"service {report['service'] or '-'} (schema {report['schema']})"]
    marker = report["marker"]
    if marker:
        how = "combined from group verifies" if marker["combined"] else "full verify"
        lines.append(
            f"marker: verified {marker['verified_at']} ({how}, run {marker['run_id']}, "
            f"code {marker['code_version'] or '-'})"
        )
    else:
        lines.append("marker: none")
    outbox = report["outbox"]
    lines.append(f"outbox: mongo={outbox['mongo']} postgres={outbox['postgres']}")
    for group, info in report["groups"].items():
        last = info["last_verify"]
        lines.append(
            f"group {group}: last clean verify "
            + (f"{last['verified_at']} (run {last['run_id']})" if last else "never")
        )
        for name in info["collections"]:
            c = report["collections"][name]
            backfill = c["backfill"] or {}
            state = backfill.get("state", "not started")
            if backfill.get("stalled"):
                state += " (stalled)"
            lines.append(
                f"  {name}: mongo={c['mongo']} postgres={c['postgres']} backfill={state}"
            )
    return "\n".join(lines)


async def run(
    args: argparse.Namespace, target: Target, mongo_primary: Sequence[str] = ()
) -> int:
    collections = select_collections(args, target)
    async with Runner(target) as runner:
        if args.command == "preflight":
            reports = await runner.preflight(collections)
            _print([r.as_dict() for r in reports])
            return 1 if any(r.invalid_ids or r.duplicates for r in reports) else 0
        if args.command == "backfill":
            results = await runner.backfill(
                collections,
                dry_run=args.dry_run,
                max_minutes=args.max_minutes,
                max_batches=args.max_batches,
                restart=args.restart,
                batch_size=args.batch_size,
            )
            _print(results)
            return 1 if any(r.get("state") == "error" for r in results.values()) else 0
        if args.command == "verify":
            reports = await runner.verify(collections, sample_every=args.sample_every)
            _print([r.as_dict() for r in reports])
            await runner.record_verify(
                reports,
                sample_every=args.sample_every,
                subset=bool(args.collections),
            )
            return 0 if all(r.clean for r in reports) else 1
        if args.command == "reconcile":
            _print(
                await runner.reconcile(
                    collections,
                    direction=args.direction,
                    dry_run=args.dry_run,
                    mongo_primary=mongo_primary,
                )
            )
            return 0
        if args.command == "status":
            report = await runner.status_report(collections)
            if args.json:
                _print(report)
            else:
                print(format_status(report))
            return 0
        if args.command == "jobs-sweep":
            sweep: Callable | None = target.extras.get("jobs_sweep")
            if sweep is None:
                print("this service has no scheduled jobs to sweep", file=sys.stderr)
                return 2
            _print(await sweep(args.backend))
            return 0
    return 2


def mongo_primary_groups(target: Target, env: Mapping[str, str]) -> list[str]:
    """The groups the services write to Mongo first (``mongo``/``dual``):
    there Mongo is authoritative and ``reconcile`` copies its version over a
    newer Postgres row too. None when the flags do not parse: reconcile then
    keeps every newer row, as before."""
    try:
        flags = load_flags(env)
    except FlagError:
        return []
    return [
        g for g in target.group_names() if flags.primary_store(g) is ReadSource.MONGO
    ]


def reconcile_to_mongo_refusal(
    args: argparse.Namespace, target: Target, env: Mapping[str, str]
) -> Optional[str]:
    """Why ``reconcile --direction postgres->mongo`` must not run now, or None.

    It copies Postgres rows into Mongo, which is only safe while Postgres is
    the primary for every group it covers (``postgres_primary_dual``): a
    delete then reaches Postgres first, with its tombstone, and reconcile's
    re-check after each Mongo insert sees it. Under ``dual`` Mongo deletes
    first and records no tombstone for a document that is not there, so a
    delete racing an insert could bring the record back. A dry run writes
    nothing and is always allowed."""
    if args.command != "reconcile" or args.direction != "postgres->mongo":
        return None
    if args.dry_run:
        return None
    try:
        flags = load_flags(env)
    except FlagError as exc:
        return f"the write-mode flags do not parse: {exc}"
    collections = select_collections(args, target) or list(target.tables)
    groups = sorted({target.group_of(c) for c in collections})
    wrong = {
        g: flags.write_mode(g).value
        for g in groups
        if flags.write_mode(g) is not WriteMode.POSTGRES_PRIMARY_DUAL
    }
    if not wrong:
        return None
    named = ", ".join(f"{g} ({mode})" for g, mode in wrong.items())
    return (
        "reconcile --direction postgres->mongo runs only while every group it "
        f"covers is on DB_WRITE_MODE=postgres_primary_dual; not: {named}. Run it "
        "with the services' flags (see docs/postgres-cutover-runbook.md), or "
        "--dry-run to see what it would do"
    )


def main(
    argv: Sequence[str],
    target: Target,
    prog: str,
    env: Mapping[str, str] = os.environ,
) -> int:
    parser = build_parser(prog)
    args = parser.parse_args(argv)
    try:
        select_collections(args, target)
    except UnknownGroup as exc:
        parser.error(str(exc))  # exits 2
    refusal = reconcile_to_mongo_refusal(args, target, env)
    if refusal:
        parser.error(refusal)  # exits 2
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    return asyncio.run(run(args, target, mongo_primary_groups(target, env)))
