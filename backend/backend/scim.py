"""SCIM directory sync from the command line (docs/sso.md, "Directory sync").

    python -m backend.scim resync --workspace <workspace id>
    python -m backend.scim resync --all
    python -m backend.scim resync --workspace <workspace id> --force

Pulls each directory's users and groups from Polis and applies them, the same
as the admin page's "Resync now" and the nightly job. Prints counts only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from beanie import PydanticObjectId
from dependency_injector import providers
from pymongo import AsyncMongoClient

from backend.app.container import container
from backend.app.handlers.database import close_db, init_db
from backend.app.utils import AiohttpClient
from backend.config import settings
from backend.db.startup import check_postgres_at_startup, dispose_postgres


async def _resync(workspace_id: str | None, force: bool = False) -> dict:
    service = container.scim_directory_service()
    if workspace_id is None:
        return await service.resync_all("cli")
    directory = await container.scim_directory_repo().find_by_workspace(
        PydanticObjectId(workspace_id)
    )
    if directory is None:
        raise SystemExit("This workspace has no directory.")
    summary = await service.resync_directory(directory, "cli", force=force)
    fresh = await container.scim_directory_repo().get(directory.id)
    if fresh is not None and fresh.last_resync_error:
        raise SystemExit(f"Resync failed: {fresh.last_resync_error}")
    return summary


async def main(argv) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.scim")
    commands = parser.add_subparsers(dest="command", required=True)
    resync = commands.add_parser("resync", help="pull and apply directories")
    which = resync.add_mutually_exclusive_group(required=True)
    which.add_argument("--workspace", help="one workspace's directory")
    which.add_argument("--all", action="store_true", help="every directory")
    resync.add_argument(
        "--force",
        action="store_true",
        help="with --workspace: apply even when the safety stop refuses",
    )
    args = parser.parse_args(argv)

    AiohttpClient.get_aiohttp_client()
    client = AsyncMongoClient(settings.mongo_settings.URI)
    container.database_client.override(providers.Object(client))
    await init_db(settings.mongo_settings.DB, client)
    await check_postgres_at_startup(container)
    try:
        result = await _resync(
            None if args.all else args.workspace, force=args.force and not args.all
        )
        print(json.dumps(result, sort_keys=True))
    finally:
        await close_db(client)
        await dispose_postgres(container)
        await AiohttpClient.close_aiohttp_client()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
