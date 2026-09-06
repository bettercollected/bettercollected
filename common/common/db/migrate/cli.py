"""Command line for the migration engine; each service wraps it with its Target."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Callable, Sequence

from common.db.migrate.engine import Runner, Target


def build_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Mongo → Postgres migration for one service: preflight, backfill, verify, reconcile, status.",
    )
    parser.add_argument("--collections", help="comma-separated subset (default: all)")
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
    sub.add_parser("status", help="checkpoints, stalls, outbox backlog")
    sweep = sub.add_parser(
        "jobs-sweep", help="(re)create scheduled deletions on a jobs backend"
    )
    sweep.add_argument(
        "--backend", choices=["postgres", "temporal"], default="postgres"
    )
    return parser


def _print(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


async def run(args: argparse.Namespace, target: Target) -> int:
    collections = [c for c in (args.collections or "").split(",") if c] or None
    async with Runner(target) as runner:
        if args.command == "preflight":
            reports = await runner.preflight(collections)
            _print([r.as_dict() for r in reports])
            return 1 if any(r.invalid_ids or r.duplicates for r in reports) else 0
        if args.command == "backfill":
            _print(
                await runner.backfill(
                    collections,
                    dry_run=args.dry_run,
                    max_minutes=args.max_minutes,
                    max_batches=args.max_batches,
                    restart=args.restart,
                    batch_size=args.batch_size,
                )
            )
            return 0
        if args.command == "verify":
            reports = await runner.verify(collections, sample_every=args.sample_every)
            _print([r.as_dict() for r in reports])
            return 0 if all(r.clean for r in reports) else 1
        if args.command == "reconcile":
            _print(
                await runner.reconcile(
                    collections, direction=args.direction, dry_run=args.dry_run
                )
            )
            return 0
        if args.command == "status":
            _print(await runner.status())
            return 0
        if args.command == "jobs-sweep":
            sweep: Callable | None = target.extras.get("jobs_sweep")
            if sweep is None:
                print("this service has no scheduled jobs to sweep", file=sys.stderr)
                return 2
            _print(await sweep(args.backend))
            return 0
    return 2


def main(argv: Sequence[str], target: Target, prog: str) -> int:
    args = build_parser(prog).parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    return asyncio.run(run(args, target))
