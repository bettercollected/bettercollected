"""python -m backend.migrate_builtins preflight | apply | verify | rollback

Moves the built-in actions (send a webhook, Slack, Discord, the two mail copies,
Google Sheets) onto the backend's own webhooks, email actions and Sheets runner
(``services/builtin_actions/migrate.py`` says what and how). Runs as the app
role in the backend image, against Postgres, one form at a time.

    preflight [--workspace ID] [--form ID] [--temporal-drained]   read-only: what would move, what blocks it
    apply [--workspace ID] [--form ID] [--wait-queue SECONDS] [--temporal-drained]
    verify [--workspace ID] [--form ID]    every moved action has its target and every target its mark
    rollback [--workspace ID] [--form ID]  give the old actions back, switch the new ones off

``apply`` moves what it can and reports the rest; it never turns a switch on,
never sends anything, and refuses a form that still has runs queued for the
executor (``--wait-queue`` waits for them). When the executor's ``run_action``
runs on Temporal (``JOBS_BACKEND``), ``preflight`` and ``apply`` ask the Temporal
server (the backend's own ``TEMPORAL_*`` settings) for the open
``run_action_code`` workflows: ``apply`` refuses a form while any of its runs are
open, and both refuse (``blocked.temporal_unreachable``) when Temporal cannot be
asked. ``--temporal-drained`` is only for that case: it skips the check, with a
WARNING in the log, on the operator's word that nothing is open.

Output is counts only, as JSON: no id, address, recipient or secret. Exit status:
0 done and nothing blocked (``verify``: nothing wrong), 1 something is blocked or
wrong, 2 usage, 3 Temporal could not be asked (nothing is moved or assumed).
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
        command.add_argument("--form", help="only this form (a staged move)")
        if name == "apply":
            command.add_argument("--wait-queue", type=int, default=0, metavar="SECONDS")
        if name in ("preflight", "apply"):
            command.add_argument(
                "--temporal-drained",
                action="store_true",
                help="only when Temporal cannot be reached: skip the open-workflow check",
            )
    return parser


def migration_of(container, temporal: bool = False, override: bool = False):
    """``temporal``: the executor's ``run_action`` is on Temporal, so its open
    workflows are asked of the Temporal server; ``override``: the operator's word
    for a Temporal that cannot be reached (``--temporal-drained``)."""
    from backend.app.services.builtin_actions.migrate import BuiltinMigration

    open_runs = container.temporal_service().open_action_workflows if temporal else None

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
        temporal_open_runs=open_runs,
        temporal_override=override,
    )


def temporal_runs_actions(container) -> bool:
    """Whether the executor's ``run_action`` jobs are on Temporal (not on the
    Postgres queue this command can look at)."""
    return not container.temporal_service()._on_postgres("run_action")


TEMPORAL_UNREACHABLE = 3


def exit_code(report) -> int:
    """3 when Temporal could not be asked (nothing was checked, so nothing is
    claimed), 1 when anything else is blocked, else 0."""
    if report.counts.get("blocked.temporal_unreachable"):
        print(
            "refused: Temporal could not be asked for the open run_action_code "
            "workflows, so none are assumed to be closed. Fix the connection, or, "
            "if you know nothing is open, pass --temporal-drained (it is logged and "
            "recorded with every moved action).",
            file=sys.stderr,
        )
        return TEMPORAL_UNREACHABLE
    return 1 if report.blocked() else 0


async def run(args, migration=None, temporal=None) -> int:
    async with open_container() as container:
        if migration is None:
            on_temporal = temporal_runs_actions(container) if temporal is None else temporal
            migration = migration_of(
                container,
                temporal=on_temporal,
                override=bool(getattr(args, "temporal_drained", False)),
            )
        if args.command == "preflight":
            report = await migration.preflight(args.workspace, args.form)
            print(report.as_json())
            return exit_code(report)
        if args.command == "apply":
            report = await migration.apply(
                args.workspace, args.form, wait_queue_seconds=args.wait_queue
            )
            print(report.as_json())
            return exit_code(report)
        if args.command == "verify":
            report = await migration.verify(args.workspace, args.form)
            print(report.as_json())
            return 1 if any(k.startswith("problem.") for k in report.counts) else 0
        report = await migration.rollback(args.workspace, args.form)
        print(report.as_json())
        return 0


def main(argv=None) -> int:
    return asyncio.run(run(build_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
