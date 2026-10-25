"""``google.purge_unencrypted_credentials`` (metadata and filters:
``catalog/google_purge.py``).

Mongo goes through the runner's Google Mongo connection (``MONGO_URI`` and
``GOOGLE_MONGO_DB``), with ``count_documents`` / ``delete_many`` limited to
:data:`MONGO_FILTER`. Postgres goes through the runner's Google data role, which
holds no DELETE: it may only execute ``google.purge_unencrypted_credentials``, a
SECURITY DEFINER function made by ``postgres/ensure-admin-roles.sh`` that holds
the same filter and returns a count. A dry run opens both stores read-only.

Counts only, in the result, the events and the audit log: never an id, an
email or a token.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text

from backend.admin.tasks.catalog import google_purge as catalog
from backend.admin.tasks.catalog.google_purge import Events
from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.spec import Refusal

TARGET = core.GOOGLE_CREDENTIALS
# docs/postgres-cutover-runbook.md ("Google credentials without a user id")
MONGO_FILTER = {
    "$or": [
        {"user_id": {"$in": [None, ""]}},
        {"credentials.token": {"$exists": True}},
        {"credentials.refresh_token": {"$exists": True}},
    ]
}
FUNCTION = "google.purge_unencrypted_credentials(boolean)"
AUDIT_ACTION = "task.google.purged"
# the id an event or audit row names the target by ("credential" would be blanked)
TARGET_ID = state.event_target("google_credentials")


def _ordered(names: List[str]) -> List[str]:
    """Mongo first, then Postgres, whatever the write mode's primary: a store
    deleted second can never copy a row back into the first."""
    return sorted(names, key=lambda name: name != "mongo")


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


async def _purge_mongo(store, apply: bool) -> Dict[str, int]:
    collection = store.db[TARGET.collection]
    matched = await collection.count_documents(MONGO_FILTER)
    deleted = 0
    if apply and matched:
        deleted = (await collection.delete_many(MONGO_FILTER)).deleted_count
    return {"matched": int(matched), "deleted": int(deleted)}


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

    async def _gate(self, params) -> tuple:
        config = state.DataConfig.from_env()
        names = _ordered(config.stores_for(TARGET, params.stores))
        async with state.open_target_stores(config, TARGET, names, read_only=True) as stores:
            for store in stores:
                try:
                    await state.ping(store)
                except Exception:  # noqa: BLE001 - never surface a driver message
                    raise Refusal("store_unreachable") from None
                if store.name == "postgres":
                    try:
                        ready = await _function_ready(store)
                    except Exception:  # noqa: BLE001
                        raise Refusal("store_unreachable") from None
                    if not ready:
                        raise Refusal("purge_function_missing")
        return config, names

    async def precheck(self, ctx, params: catalog.PurgeParams) -> None:
        await self._gate(params)

    async def run(self, ctx, params: catalog.PurgeParams) -> catalog.PurgeResult:
        config, names = await self._gate(params)
        apply = not ctx.dry_run
        out: Dict[str, catalog.StorePurge] = {}
        async with state.open_target_stores(
            config, TARGET, names, read_only=ctx.dry_run
        ) as stores:
            for store in stores:
                purge = _purge_mongo if store.name == "mongo" else _purge_postgres
                counts = await purge(store, apply)
                out[store.name] = catalog.StorePurge(**counts)
                await ctx.emit(
                    Events.purged if apply else Events.counted,
                    counts,
                    [TARGET_ID, store.name],
                )
                if apply:
                    # one row per store, right after its delete: a run that stops
                    # between Mongo and Postgres still leaves Mongo's counts
                    await ctx.audit(
                        AUDIT_ACTION,
                        target_type=TARGET_ID,
                        target_id=store.name,
                        detail={"store": store.name, **counts},
                    )
        matched = sum(s.matched for s in out.values())
        deleted = sum(s.deleted for s in out.values())
        return catalog.PurgeResult(matched=matched, deleted=deleted, **out)
