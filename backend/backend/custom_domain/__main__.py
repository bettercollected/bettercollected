"""python -m backend.custom_domain {export-reference-map,adopt,subscribe,sweep}

Operator steps for moving BetterCollected's custom domains to the
custom-domain service (docs/custom-domain.md):

  export-reference-map  {hostname: workspace id} for every enabled custom
                        domain, the input of `custom-domain legacy import`.
  adopt                 after the import: store each imported domain's id and
                        status on its workspace (via the routed repository, so
                        both stores see it).
  subscribe --url URL   create the webhook subscription; prints the secret
                        once (put it in CUSTOM_DOMAIN_WEBHOOK_SECRETS).
  sweep                 delete domains in the service that no workspace
                        references any more (replacements whose old domain
                        could not be deleted at the time).
"""

import argparse
import asyncio
import json
import sys

from bson import ObjectId
from dependency_injector import providers
from pymongo import AsyncMongoClient

from backend.app.container import container
from backend.app.handlers.database import init_db
from backend.app.services.custom_domain_service import domain_fields
from backend.config import settings

DOMAIN_FILTER = {
    "custom_domain": {"$nin": [None, ""]},
    "custom_domain_disabled": {"$ne": True},
}


async def _open():
    client = AsyncMongoClient(settings.mongo_settings.URI)
    container.database_client.override(providers.Object(client))
    await init_db(settings.mongo_settings.DB, client)
    return client


async def export_reference_map(out: str) -> int:
    client = await _open()
    workspaces = client[settings.mongo_settings.DB]["workspaces"]
    references = {}
    async for doc in workspaces.find(DOMAIN_FILTER, {"custom_domain": 1}):
        references[doc["custom_domain"].strip().lower().rstrip(".")] = str(doc["_id"])
    with open(out, "w") as handle:
        json.dump(references, handle, indent=1, sort_keys=True)
    print(f"{len(references)} hostnames written to {out}")
    await client.close()
    return 0


async def adopt(dry_run: bool) -> int:
    client = await _open()
    service = container.custom_domain_service()
    repo = container.workspace_repo()
    counts = {
        "adopted": 0,
        "unchanged": 0,
        "hostname_mismatch": 0,
        "unknown_workspace": 0,
    }
    for domain in service.client().iter_domains():
        try:
            workspace = await repo.find_by_id(ObjectId(domain.reference))
        except Exception:  # noqa: BLE001 — a reference that is not an ObjectId
            workspace = None
        if workspace is None:
            counts["unknown_workspace"] += 1
            print(
                f"  {domain.hostname}: reference {domain.reference} is not a workspace"
            )
            continue
        if (workspace.custom_domain or "").strip().lower() != domain.hostname:
            counts["hostname_mismatch"] += 1
            print(f"  {domain.hostname}: workspace {workspace.id} has another hostname")
            continue
        if (
            workspace.custom_domain_id == domain.id
            and workspace.custom_domain_status == domain.status
        ):
            counts["unchanged"] += 1
            continue
        counts["adopted"] += 1
        if not dry_run:
            await repo.set_fields(workspace, domain_fields(domain))
    print(json.dumps(counts))
    await client.close()
    return 0 if not (counts["hostname_mismatch"] or counts["unknown_workspace"]) else 1


async def subscribe(url: str) -> int:
    hook = await container.custom_domain_service().subscribe(url)
    print(f"webhook {hook.id} for {', '.join(hook.events)}")
    print("secret (shown once):", hook.secret)
    return 0


async def sweep(dry_run: bool) -> int:
    client = await _open()
    service = container.custom_domain_service()
    repo = container.workspace_repo()
    orphans = []
    for domain in service.client().iter_domains():
        workspace = await repo.find_by_custom_domain_id(domain.id)
        if workspace is None:
            orphans.append(domain)
    for domain in orphans:
        print(f"  orphan {domain.hostname} ({domain.id}, {domain.status})")
        if not dry_run:
            await service.delete(domain.id)
    print(f"{len(orphans)} orphan domains {'found' if dry_run else 'deleted'}")
    await client.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.custom_domain")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export-reference-map")
    p.add_argument("--out", default="bc-domains.json")
    p = sub.add_parser("adopt")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("subscribe")
    p.add_argument("--url", required=True)
    p = sub.add_parser("sweep")
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command != "export-reference-map" and not settings.custom_domain.enabled:
        print(
            "CUSTOM_DOMAIN_API_URL and CUSTOM_DOMAIN_API_CREDENTIAL are not set",
            file=sys.stderr,
        )
        return 2
    if args.command == "export-reference-map":
        return asyncio.run(export_reference_map(args.out))
    if args.command == "adopt":
        return asyncio.run(adopt(args.dry_run))
    if args.command == "subscribe":
        return asyncio.run(subscribe(args.url))
    return asyncio.run(sweep(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
