"""``google.purge_unencrypted_credentials`` (metadata and filters:
``catalog/google_purge.py``).

Postgres goes through the runner's Google data role, which holds no DELETE: it
may only execute ``google.purge_unencrypted_credentials``, a SECURITY DEFINER
function made by ``postgres/ensure-admin-roles.sh`` that holds the filter and
returns a count. A dry run opens the store read-only. Mongo is never touched
(``store_retired``). An apply is refused (``import_incomplete``) until the import
from 4.0 is over: while the runner has a Mongo connection configured, or while
``google.migration_progress`` (when the role can read it) records an unfinished
backfill; running the import again would copy the rows still held in Mongo back.

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
                if apply:
                    # Rows left in Mongo (4.0's copy) would come back if the import
                    # ran again: only once it is over (state.check_import_finished)
                    # may rows be purged from Postgres alone. Mongo is not touched,
                    # and no manual step is needed while the import is not re-run.
                    await state.check_import_finished(store, config.mongo_configured)
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
