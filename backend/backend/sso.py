"""Single sign-on support commands (docs/sso.md, "Releasing an entity ID").

    python -m backend.sso release-pending
    python -m backend.sso entity-id <entity id>
    python -m backend.sso entity-id <entity id> --apply
    python -m backend.sso entity-id <entity id> --workspace <workspace id> --apply

``release-pending`` runs the daily retry now: it deletes in Polis the
connections of deleted workspaces that a failed Polis call left behind.

``entity-id`` shows which Polis connections hold an identity provider's entity
ID (Polis lets one workspace hold an entity ID; another workspace connecting
the same IdP is refused) and what each is here. With ``--apply`` it releases
the orphaned ones (their workspace is gone, or we keep no connection for
them); a live workspace's connection only when that workspace is named with
``--workspace``, after support has decided that workspace squats the entity
ID. Without ``--apply`` nothing changes. Prints ids and states only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.cli_store import open_container
from backend.config import settings

# the SSO connections and the workspaces live in the identity group
GROUPS = ("identity",)


async def main(argv) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.sso")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "release-pending", help="release deleted workspaces' connections in Polis"
    )
    entity = commands.add_parser(
        "entity-id", help="show (and release) who holds an IdP entity ID"
    )
    entity.add_argument("entity_id")
    entity.add_argument(
        "--workspace",
        help="also release this live workspace's connection holding the entity ID",
    )
    entity.add_argument(
        "--apply", action="store_true", help="release (default: a dry run)"
    )
    args = parser.parse_args(argv)
    if not settings.sso.is_configured:
        print("Single sign-on is not configured here (SSO_ENABLED and SSO_POLIS_*).")
        return 2
    async with open_container() as container:
        service = container.sso_connection_service()
        if args.command == "release-pending":
            result = await service.retry_pending_releases(limit=1000)
        else:
            result = await service.release_entity_id(
                args.entity_id.strip(), workspace_id=args.workspace, apply=args.apply
            )
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
