"""``google.purge_unencrypted_credentials`` (metadata and filters:
``catalog/google_purge.py``).

Postgres goes through the runner's Google data role, which holds no DELETE: it
may only execute ``google.purge_unencrypted_credentials``, a SECURITY DEFINER
function made by ``postgres/ensure-admin-roles.sh`` that holds the filter and
returns a count. A dry run opens the store read-only. Mongo is never touched
(``store_retired``); an apply is refused while the runner still has a Mongo
connection configured, because the import from 4.0
(``googleform.migrate backfill``) would copy the rows still held in Mongo back.

Counts only, in the result, the events and the audit log: never an id, an
email or a token.
"""

from __future__ import annotations

from typing import Dict

from sqlalchemy import text

from backend.admin.tasks.catalog import google_purge as catalog
from backend.admin.tasks.catalog.google_purge import Events
from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.spec import Refusal

TARGET = core.GOOGLE_CREDENTIALS
FUNCTION = "google.purge_unencrypted_credentials(boolean)"
AUDIT_ACTION = "task.google.purged"
# the id an event or audit row names the target by ("credential" would be blanked)
TARGET_ID = state.event_target("google_credentials")


async def _function_ready(store) -> bool:
    async with store.engine.connect() as conn:
        return bool(
            (
                await conn.execute(
                    text(
                        "SELECT p IS NOT NULL AND has_function_privilege(p, 'EXECUTE') "
                        "FROM (SELECT to_regprocedure(:f) AS p) f"
                    ),
                    {"f": FUNCTION},
                )
            ).scalar_one()
        )


async def _purge_postgres(store, apply: bool) -> Dict[str, int]:
    async with store.engine.begin() as conn:
        matched = (
            await conn.execute(
                text("SELECT google.purge_unencrypted_credentials(false)")
            )
        ).scalar_one()
        deleted = 0
        if apply and matched:
            deleted = (
                await conn.execute(
                    text("SELECT google.purge_unencrypted_credentials(true)")
                )
            ).scalar_one()
    return {"matched": int(matched), "deleted": int(deleted)}


class PurgeUnencryptedCredentials:
    META = catalog.META

    async def _gate(self, params, *, apply: bool) -> tuple:
        config = state.DataConfig.from_env()
        names = config.stores_for(TARGET, params.stores)
        if apply and config.mongo_configured:
            # A row left readable in Mongo would be copied back into Postgres by
            # the next backfill or reconcile of the import from 4.0 (neither
            # store keeps a deletion tombstone here). Mongo is not touched: run
            # the apply where no Mongo is configured, after purging Mongo's copy
            # as the cutover runbook describes.
            raise Refusal("stores_incomplete")
        async with state.open_target_stores(config, TARGET, names, read_only=True) as stores:
            for store in stores:
                try:
                    await state.ping(store)
                except Exception:  # noqa: BLE001 - never surface a driver message
                    raise Refusal("store_unreachable") from None
                try:
                    ready = await _function_ready(store)
                except Exception:  # noqa: BLE001
                    raise Refusal("store_unreachable") from None
                if not ready:
                    raise Refusal("purge_function_missing")
        return config, names

    async def precheck(self, ctx, params: catalog.PurgeParams) -> None:
        await self._gate(params, apply=not ctx.dry_run)

    async def run(self, ctx, params: catalog.PurgeParams) -> catalog.PurgeResult:
        apply = not ctx.dry_run
        config, names = await self._gate(params, apply=apply)
        out: Dict[str, catalog.StorePurge] = {}
        async with state.open_target_stores(
            config, TARGET, names, read_only=ctx.dry_run
        ) as stores:
            for store in stores:
                counts = await _purge_postgres(store, apply)
                out[store.name] = catalog.StorePurge(**counts)
                await ctx.emit(
                    Events.purged if apply else Events.counted,
                    counts,
                    [TARGET_ID, store.name],
                )
                if apply:
                    await ctx.audit(
                        AUDIT_ACTION,
                        target_type=TARGET_ID,
                        target_id=store.name,
                        detail={"store": store.name, **counts},
                    )
        matched = sum(s.matched for s in out.values())
        deleted = sum(s.deleted for s in out.values())
        return catalog.PurgeResult(matched=matched, deleted=deleted, **out)
