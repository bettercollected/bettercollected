"""python -m backend.migrate_builtins preflight | apply | verify | rollback

Moves the built-in actions (send a webhook, Slack, Discord, the two mail copies,
Google Sheets) onto the backend's own webhooks, email actions and Sheets runner
(``services/builtin_actions/migrate.py`` says what and how). Runs as the app
role in the backend image, against Postgres, one form at a time.

    preflight [--workspace ID]            read-only: what would move, what blocks it
    apply [--workspace ID] [--wait-queue SECONDS] [--temporal-drained]
    verify [--workspace ID]               every moved action has its target
    rollback [--workspace ID]             give the old actions back, switch the new ones off

``apply`` moves what it can and reports the rest; it never turns a switch on,
never sends anything, and refuses a form that still has runs queued for the
executor (``--wait-queue`` waits for them). When the executor's ``run_action``
runs on Temporal, queued runs cannot be seen from here: confirm there are no
open ``run_action_code`` workflows and pass ``--temporal-drained``.

Output is counts only, as JSON: no id, address, recipient or secret. Exit status:
0 done and nothing blocked (``verify``: nothing wrong), 1 something is blocked or
wrong, 2 usage, 3 refused (Temporal not confirmed drained).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from backend.cli_store import open_container


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.migrate_builtins")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "apply", "verify", "rollback"):
        command = sub.add_parser(name)
        command.add_argument("--workspace", help="only this workspace's forms")
        if name == "apply":
            command.add_argument("--wait-queue", type=int, default=0, metavar="SECONDS")
            command.add_argument("--temporal-drained", action="store_true")
    return parser


def migration_of(container):
    from backend.app.services.builtin_actions.migrate import BuiltinMigration

    return BuiltinMigration(
        form_repo=container.form_repo(),
        action_repo=container.action_repository(),
        workspace_repo=container.workspace_repo(),
        workspace_form_repo=container.workspace_form_repo(),
        webhook_repo=container.form_webhook_repo(),
        email_repo=container.form_email_action_repo(),
        audit_repo=container.webhook_audit_repo(),
        copy_recipient_service=container.copy_recipient_service(),
        crypto=container.crypto(),
    )


def temporal_runs_actions(container) -> bool:
    """Whether the executor's ``run_action`` jobs are on Temporal (not on the
    Postgres queue this command can look at)."""
    return not container.temporal_service()._on_postgres("run_action")


async def run(args, migration=None, temporal=None) -> int:
    async with open_container() as container:
        migration = migration or migration_of(container)
        if args.command == "preflight":
            report = await migration.preflight(args.workspace)
            print(report.as_json())
            return 1 if report.blocked() else 0
        if args.command == "apply":
            on_temporal = temporal_runs_actions(container) if temporal is None else temporal
            if on_temporal and not args.temporal_drained:
                print(
                    '{"refused": "run_action_on_temporal: confirm no open '
                    'run_action_code workflows, then pass --temporal-drained"}'
                )
                return 3
            report = await migration.apply(
                args.workspace, wait_queue_seconds=args.wait_queue
            )
            print(report.as_json())
            return 1 if report.blocked() else 0
        if args.command == "verify":
            report = await migration.verify(args.workspace)
            print(report.as_json())
            return 1 if any(k.startswith("problem.") for k in report.counts) else 0
        report = await migration.rollback(args.workspace)
        print(report.as_json())
        return 0


def main(argv=None) -> int:
    return asyncio.run(run(build_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
