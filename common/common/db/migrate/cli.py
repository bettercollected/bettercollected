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
from common.db.flags import OVERRIDE_SEP, WRITE_KEY
from common.db.migrate.engine import Runner, Target
from common.db.migrate.outbox import OutboxResolver
from common.db.schema_guard import MigrationTarget


# The commands that never read MongoDB: they run without a MONGO_URI (the import
# commands, and the ones that compare or clean up after an import, need it).
NO_MONGO_COMMANDS = frozenset({"jobs-sweep"})


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
    reconcile.add_argument(
        "--mongo-wins",
        action="store_true",
        help="mongo->postgres: copy Mongo's version over a Postgres row the "
        "application wrote later, in the groups whose DB_WRITE_MODE (or "
        "DB_WRITE_MODE__<group>) is explicitly mongo or dual; without it such "
        "rows are kept and counted as newer_in_postgres",
    )
    status = sub.add_parser(
        "status",
        help="counts, checkpoints, stalls, outbox, mirror failures, last verify, marker",
    )
    status.add_argument(
        "--json",
        action="store_true",
        help="one machine-readable JSON document instead of the summary",
    )
    resolve = sub.add_parser(
        "resolve-outbox",
        help="resolve Postgres-side outbox entries whose write Mongo provably holds "
        "(after a rollback to dual); a dry run unless --apply",
    )
    resolve.add_argument(
        "--apply", action="store_true", help="resolve them (default: report only)"
    )
    resolve.add_argument(
        "--accept-superseded",
        action="store_true",
        help="also resolve entries whose rows Mongo holds only in a different, "
        "later-stamped version. Only after confirming the newer Mongo version "
        "should win: the Postgres changes of these entries will be discarded by "
        "reconcile",
    )
    resolve.add_argument(
        "--clear-postgres-only-leftovers",
        action="store_true",
        help="with --apply, also resolve the entries left by the repositories "
        "of groups served from Postgres only since 4.1 (counted as "
        "postgres_only_leftover): mirror failures to a Mongo those groups no "
        "longer read or write",
    )
    resolve.add_argument(
        "--ids-file",
        metavar="PATH",
        help="also write entry and row ids with the reason each entry is kept "
        "to this new local file (created mode 0600; never overwritten)",
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


#: commands that compare or copy between the stores, which a Postgres-only
#: group no longer has: they skip those groups and refuse to be pointed at one
BOTH_STORES_COMMANDS = ("verify", "reconcile", "resolve-outbox")
VERBS = {"verify": "compare", "reconcile": "reconcile", "resolve-outbox": "compare"}


class PostgresOnlyGroup(ValueError):
    """``verify``/``reconcile``/``resolve-outbox`` pointed at a group served
    from Postgres only."""


def _listed(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    names = list(names)
    return " and ".join(n for n in (", ".join(names[:-1]), names[-1]) if n)


def skipped_groups(args: argparse.Namespace, target: Target) -> list[str]:
    """The Postgres-only groups a ``verify``/``reconcile`` without a selection
    leaves out (those that have collections here)."""
    if args.command not in BOTH_STORES_COMMANDS or args.group or args.collections:
        return []
    return [g for g in target.group_names() if g in target.postgres_only_groups]


def select_collections(args: argparse.Namespace, target: Target) -> Optional[list[str]]:
    """The collections ``--collections`` or ``--group`` select; ``None`` = all.
    Raises :class:`UnknownGroup` for a group the service does not have.

    ``verify`` and ``reconcile`` never cover a Postgres-only group
    (``Target.postgres_only_groups``): they select every other collection by
    default and raise :class:`PostgresOnlyGroup` when one is asked for."""
    selected = _select(args, target)
    if args.command not in BOTH_STORES_COMMANDS:
        return selected
    if selected is None:
        if not target.postgres_only_groups:
            return None
        return list(target.migrating_tables())
    named: list[str] = []
    for group in parse_groups(args.group) + [target.group_of(c) for c in selected]:
        if group in target.postgres_only_groups and group not in named:
            named.append(group)
    if named:
        raise PostgresOnlyGroup(
            f"{args.command} does not cover a group served from Postgres only: "
            f"{', '.join(named)}. Such a group has no Mongo store to "
            f"{VERBS[args.command]} with; its "
            "Mongo data from 4.0 is imported with `backfill` (see "
            "docs/postgres-cutover-runbook.md, 'Upgrading to 4.1')"
        )
    return selected


def _select(args: argparse.Namespace, target: Target) -> Optional[list[str]]:
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
    if args.command not in NO_MONGO_COMMANDS and not (target.mongo_uri or "").strip():
        print(
            f"{args.command} reads MongoDB (the data of a stack from before 4.1), "
            "and MONGO_URI is not set.",
            file=sys.stderr,
        )
        return 2
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
        skipped = skipped_groups(args, target)
        if skipped:
            print(
                f"{args.command}: skipping the {_listed(skipped)} group(s), served "
                "from Postgres only (their Mongo data is imported with backfill, "
                "never verified or reconciled)",
                file=sys.stderr,
            )
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
        if args.command == "resolve-outbox":
            return await resolve_outbox(args, target, runner)
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


def selected_groups(args: argparse.Namespace, target: Target) -> Optional[list[str]]:
    """The groups ``--group`` names (validated); ``None`` = every group."""
    if not args.group:
        return None
    return validate_groups(parse_groups(args.group), valid_groups(target))


def open_ids_file(path: str):
    """A new file only the operator can read; an existing one is never
    overwritten (raises ``FileExistsError``)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


async def resolve_outbox(
    args: argparse.Namespace, target: Target, runner: Runner
) -> int:
    """Plan; write the ids file (when asked) before anything changes; then
    resolve with ``--apply``. Prints counts only. Exit 0 when every entry in
    scope is resolvable (or there is none), 1 when some are kept; the
    Postgres-only leftovers are reported apart and never change it."""
    resolver = OutboxResolver(runner)
    plan = await resolver.plan(
        selected_groups(args, target), accept_superseded=args.accept_superseded
    )
    if args.ids_file:
        with open_ids_file(args.ids_file) as handle:
            json.dump(plan.details(), handle, indent=2, sort_keys=True, default=str)
    summary = plan.summary()
    summary["apply"] = bool(args.apply)
    summary["resolved"] = await resolver.apply(plan) if args.apply else 0
    summary["leftover_cleared"] = (
        await resolver.clear_leftovers(plan)
        if args.apply and args.clear_postgres_only_leftovers
        else 0
    )
    _print(summary)
    # leftovers do not count: the proof rule never applies to them
    return 0 if summary["resolvable"] == summary["in_scope"] else 1


def write_mode_in(
    target: Target, env: Mapping[str, str], group: str
) -> Optional[str]:
    """The write mode the 4.0 stack being imported ran ``group`` with, as the
    operator's ``env`` states it: ``DB_WRITE_MODE__<group>`` when the group
    has one, else ``DB_WRITE_MODE``; None when neither is set. A group served
    from Postgres only is always ``postgres``. Only the CLI reads this (a 4.1
    service refuses every value but ``postgres``)."""
    if group in target.postgres_only_groups:
        return "postgres"
    prefix = WRITE_KEY + OVERRIDE_SEP
    for key, value in env.items():
        if key.startswith(prefix) and key[len(prefix) :].lower() == group and value:
            return value.strip().lower()
    value = env.get(WRITE_KEY, "")
    return value.strip().lower() or None


def mongo_primary_groups(target: Target, env: Mapping[str, str]) -> list[str]:
    """The groups whose 4.0 services wrote Mongo first (``mongo``/``dual``) by
    an EXPLICIT setting in ``env``: ``DB_WRITE_MODE__<group>`` when the group
    has one, else ``DB_WRITE_MODE``. A group whose mode is only the default (no
    variable set), or a value that is not a write mode, never counts:
    ``reconcile --mongo-wins`` then keeps every newer Postgres row (fails
    safe)."""
    return [
        g
        for g in target.migrating_groups()
        if write_mode_in(target, env, g) in ("mongo", "dual")
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
    delete racing an insert could bring the record back. A group served from
    Postgres only (4.1) never qualifies: nothing mirrors to Mongo any more. A
    dry run writes nothing and is always allowed."""
    if args.command != "reconcile" or args.direction != "postgres->mongo":
        return None
    if args.dry_run:
        return None
    collections = select_collections(args, target) or list(target.tables)
    groups = sorted({target.group_of(c) for c in collections})
    wrong = {
        g: write_mode_in(target, env, g) or "mongo"
        for g in groups
        if write_mode_in(target, env, g) != "postgres_primary_dual"
    }
    if not wrong:
        return None
    named = ", ".join(f"{g} ({mode})" for g, mode in wrong.items())
    return (
        "reconcile --direction postgres->mongo runs only while every group it "
        f"covers is on DB_WRITE_MODE=postgres_primary_dual; not: {named}. Run it "
        "with the 4.0 stack's flags (see docs/postgres-cutover-runbook.md), or "
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
    except (UnknownGroup, PostgresOnlyGroup) as exc:
        parser.error(str(exc))  # exits 2
    if args.command == "resolve-outbox":
        if args.collections:
            # entries name a repository, so a group at the narrowest
            parser.error("resolve-outbox selects by --group, not --collections")
        if args.ids_file and os.path.lexists(args.ids_file):
            parser.error("--ids-file must name a new file; it is never overwritten")
    refusal = reconcile_to_mongo_refusal(args, target, env)
    if refusal:
        parser.error(refusal)  # exits 2
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    mongo_primary: list[str] = []
    if args.command == "reconcile" and getattr(args, "mongo_wins", False):
        if args.direction != "mongo->postgres":
            parser.error("--mongo-wins applies to --direction mongo->postgres only")
        mongo_primary = mongo_primary_groups(target, env)
        logging.getLogger(__name__).info(
            "reconcile --mongo-wins: Mongo's copy wins in %s",
            ", ".join(mongo_primary) or "no group (none explicitly on mongo/dual)",
        )
    return asyncio.run(run(args, target, mongo_primary))
