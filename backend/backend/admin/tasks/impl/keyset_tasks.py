"""The keyset rotation tasks (``keyset.add_key``, ``promote``, ``reencrypt``,
``verify``, ``drop_old``). Metadata: ``catalog/keyset.py``; the walk:
``keyset_core.py``; the keyset's store, the readiness check and the data stores:
``keyset_state.py``. Every guard of ``scripts/rotate_response_keyset.py`` and
docs/response-keyset-rotation.md is carried over:

* a key is only added as a secondary and only then promoted, and a service is
  only asked to hold a key every consumer has confirmed (heartbeats);
* nothing is re-encrypted under a published key, or under a primary other than
  the stored keyset's;
* values are re-encrypted with a compare-and-swap write, checked to decrypt
  back before the write and read back after it before they are counted;
* the old key is dropped only after a full scan of EVERY target in EVERY store
  the services write found no value on it, and no store empty (no target or
  store selection exists for it); with a scan that did not finish it refuses.

The keyset is never printed, logged, put in an event or a result: key ids and
counts only.
"""

from __future__ import annotations

from typing import Dict, List

from backend.admin.config import AdminConfigError
from backend.admin.tasks.catalog import keyset as catalog
from backend.admin.tasks.catalog.keyset import Events
from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.impl.responses_common import (
    keyset_fingerprint,
    load_keyset,
)
from backend.admin.tasks.spec import Refusal, TaskError
from common.services.keyset import (
    add_secondary_key,
    encode_keyset,
    key_ids,
    only_primary,
    promote,
    published_key_ids,
)

BASE_COUNTERS = (
    "records",
    "values",
    "values_stale",
    "records_stale",
    "values_unopenable",
    "records_reencrypted",
    "values_reencrypted",
    "records_changed_concurrently",
    "records_readback_failed",
    "mirror_records_copied",
)


def _event_counts(counts: Dict[str, int]) -> dict:
    picked = {
        k: v
        for k, v in counts.items()
        if k in BASE_COUNTERS or k.startswith("values_key_")
    }
    return state.event_counts(picked, keep=5)


def _counts_model(counts: Dict[str, int]) -> catalog.TargetCounts:
    known = catalog.TargetCounts.model_fields
    return catalog.TargetCounts(**{k: v for k, v in counts.items() if k in known})


class _Base:
    """Gates shared by the five tasks."""

    async def _keyset(self, ctx, *, allow_env: bool = False):
        """(keys, stored or None, keyset value, parsed): from the settings store
        (the only source a task that writes or re-encrypts accepts), else, for
        a read-only task, the runner's environment."""
        try:
            keys = state.runner_keys()
        except AdminConfigError:
            raise Refusal("keyset_missing") from None
        async with ctx.connection() as conn:
            stored = await state.read_stored(conn, keys)
        if stored is not None:
            return keys, stored, stored.value, state.parsed(stored.value)
        if not allow_env:
            raise Refusal("keyset_not_in_store")
        value = load_keyset()
        if value is None:
            raise Refusal("keyset_missing")
        return keys, None, value, state.parsed(value)

    @staticmethod
    def _typeform(params) -> None:
        if not params.typeform_acknowledged:
            raise Refusal("typeform_not_acknowledged")

    async def _ready(self, ctx, params, parsed, stored) -> int:
        async with ctx.connection() as conn:
            return await state.check_consumers(
                conn,
                ids=key_ids(parsed),
                min_revision=stored.revision,
                google_in_use=params.google_in_use,
            )

    async def _ping_all(self, config, targets, choice) -> Dict[str, List[str]]:
        plans: Dict[str, List[str]] = {}
        for target in targets:
            names = config.stores_for(target, choice)
            plans[target.name] = names
            async with state.open_target_stores(
                config, target, names, read_only=True
            ) as stores:
                for store in stores:
                    try:
                        await state.ping(store)
                    except Exception:  # noqa: BLE001 - never surface a driver message
                        raise Refusal("store_unreachable") from None
        return plans

    async def _write(self, ctx, keys, stored, new_keyset, action, extra=None):
        async with ctx.connection() as conn:
            return await state.write_stored(
                conn,
                keys,
                stored,
                encode_keyset(new_keyset),
                requested_by=ctx.requested_by,
                run_id=ctx.run_id,
                task=ctx.task,
                action=action,
                extra=extra,
            )


# --------------------------------------------------------------- add_key
class AddKey(_Base):
    META = catalog.ADD_KEY

    async def _gate(self, ctx):
        keys, stored, _value, parsed = await self._keyset(ctx)
        if len(parsed.key) > 1:  # a rotation is under way: finish or drop first
            raise Refusal("rotation_in_progress")
        return keys, stored, parsed

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx)

    async def run(self, ctx, params) -> catalog.KeyChange:
        keys, stored, parsed = await self._gate(ctx)
        if ctx.dry_run:
            return catalog.KeyChange(
                changed=False,
                primary_id=parsed.primary_key_id,
                key_count=len(parsed.key),
                version=stored.version,
                revision=stored.revision,
            )
        added = add_secondary_key(parsed)
        new_id = (set(key_ids(added)) - set(key_ids(parsed))).pop()
        version, revision = await self._write(
            ctx, keys, stored, added, "add_key", {"added_key_id": new_id}
        )
        await ctx.emit(
            Events.key_added, {"key_count": len(added.key)}, [str(new_id)]
        )
        return catalog.KeyChange(
            changed=True,
            primary_id=added.primary_key_id,
            key_count=len(added.key),
            added_key_id=new_id,
            version=version,
            revision=revision,
        )


# --------------------------------------------------------------- promote
class Promote(_Base):
    META = catalog.PROMOTE

    async def _gate(self, ctx, params):
        self._typeform(params)
        keys, stored, _value, parsed = await self._keyset(ctx)
        if params.new_primary_id not in key_ids(parsed):
            raise Refusal("key_not_in_keyset")
        if params.new_primary_id in published_key_ids(parsed):
            raise Refusal("published_key_to_promote")
        if parsed.primary_key_id != params.new_primary_id:
            # every consumer must already hold the key as a secondary
            await self._ready(ctx, params, parsed, stored)
        return keys, stored, parsed

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.KeyChange:
        keys, stored, parsed = await self._gate(ctx, params)
        previous = parsed.primary_key_id
        if previous == params.new_primary_id or ctx.dry_run:
            return catalog.KeyChange(
                changed=False,
                primary_id=previous,
                previous_primary_id=previous,
                key_count=len(parsed.key),
                version=stored.version,
                revision=stored.revision,
            )
        promoted = promote(parsed, params.new_primary_id)
        version, revision = await self._write(
            ctx, keys, stored, promoted, "promote", {"primary_id": params.new_primary_id}
        )
        await ctx.emit(
            Events.key_promoted, {"key_count": len(promoted.key)}, [str(params.new_primary_id)]
        )
        return catalog.KeyChange(
            changed=True,
            primary_id=params.new_primary_id,
            previous_primary_id=previous,
            key_count=len(promoted.key),
            version=version,
            revision=revision,
        )


# -------------------------------------------------------------- reencrypt
class Reencrypt(_Base):
    META = catalog.REENCRYPT

    async def _gate(self, ctx, params):
        self._typeform(params)
        keys, stored, value, parsed = await self._keyset(ctx)
        if parsed.primary_key_id != params.primary_id:
            raise Refusal("primary_mismatch")
        if not ctx.dry_run and parsed.primary_key_id in published_key_ids(parsed):
            raise Refusal("published_primary")
        await self._ready(ctx, params, parsed, stored)
        config = state.DataConfig.from_env()
        targets = state.selected_targets(params.targets)
        plans = await self._ping_all(config, targets, params.stores)
        return value, config, targets, plans

    async def precheck(self, ctx, params) -> None:
        value, *_ = await self._gate(ctx, params)

        async def fingerprint():  # a resume must see the same keyset
            return keyset_fingerprint(value)

        ctx.fingerprint = fingerprint

    async def run(self, ctx, params) -> catalog.ScanResult:
        value, config, targets, plans = await self._gate(ctx, params)
        rotation = core.Rotation(value)
        cursor = None if ctx.dry_run else await ctx.load_checkpoint()
        resume_target = cursor.get("t") if cursor else None
        done = int(cursor.get("d", 0)) if cursor else 0
        skipping = resume_target is not None
        out: dict = {}
        tallies: List[dict] = []
        complete = True

        for target in targets:
            name = state.field_name(target)
            resume_phase, resume_after = "primary", None
            if skipping:
                if name != resume_target:
                    continue  # finished by the earlier run
                skipping = False
                resume_phase, resume_after = cursor["p"], cursor.get("a")
            names = plans[target.name]
            per_store: dict = {}
            base = done
            async with state.open_target_stores(
                config, target, names, read_only=ctx.dry_run
            ) as stores:

                async def stop(_records, base=base) -> bool:
                    await ctx.progress(base + _records)
                    return await ctx.cancelled()

                if ctx.dry_run:
                    for store in stores:
                        counts = await core.scan(
                            store, target, rotation, params.batch_size, stop
                        )
                        per_store[store.name] = counts
                        await ctx.emit(
                            Events.counted, _event_counts(counts), [state.event_target(name), store.name]
                        )
                        if counts.get("stopped"):
                            complete = False
                            break
                else:
                    primary, mirror = stores[0], (stores[1] if len(stores) > 1 else None)

                    def walker(phase, store):
                        async def on_batch(after, counts) -> bool:
                            await ctx.checkpoint(
                                {
                                    "t": name,
                                    "p": phase,
                                    "a": str(after),
                                    "d": base + counts.get("records", 0),
                                }
                            )
                            await ctx.progress(base + counts.get("records", 0))
                            return await ctx.cancelled()

                        return on_batch

                    if resume_phase == "primary":
                        counts, _last = await core.reencrypt_store(
                            primary,
                            target,
                            rotation,
                            mirror=mirror,
                            batch_size=params.batch_size,
                            start_after=resume_after,
                            on_batch=walker("primary", primary),
                            readback=True,
                        )
                        per_store[primary.name] = counts
                        await ctx.emit(
                            Events.reencrypted, _event_counts(counts), [state.event_target(name), primary.name]
                        )
                        if counts.get("stopped"):
                            complete = False
                    if complete and mirror is not None:
                        # what the copy could not cover: rows only the mirror
                        # holds, or whose value differed from the primary's
                        after = resume_after if resume_phase == "mirror" else None
                        counts, _last = await core.reencrypt_store(
                            mirror,
                            target,
                            rotation,
                            batch_size=params.batch_size,
                            start_after=after,
                            on_batch=walker("mirror", mirror),
                            readback=True,
                        )
                        per_store[mirror.name] = counts
                        await ctx.emit(
                            Events.reencrypted, _event_counts(counts), [state.event_target(name), mirror.name]
                        )
                        if counts.get("stopped"):
                            complete = False
            tallies.extend(per_store.values())
            out[name] = catalog.StoreCounts(
                **{n: _counts_model(c) for n, c in per_store.items()}
            )
            done = base + max((c.get("records", 0) for c in per_store.values()), default=0)
            if not complete:
                break
        if skipping:  # the checkpoint names a target this run does not cover
            raise TaskError("resume_mismatch")
        left = sum(
            c.get("values_unopenable", 0) + (c.get("values_stale", 0) if ctx.dry_run else 0)
            for c in tallies
        )
        return catalog.ScanResult(
            complete=complete,
            primary_id=rotation.primary,
            values_stale=left,
            values_unopenable=left if not ctx.dry_run else 0,
            **out,
        )


# ----------------------------------------------------------------- verify
class Verify(_Base):
    META = catalog.VERIFY

    async def _gate(self, ctx, params):
        _keys, _stored, value, parsed = await self._keyset(ctx, allow_env=True)
        config = state.DataConfig.from_env()
        targets = state.selected_targets(params.targets)
        plans = await self._ping_all(config, targets, params.stores)
        return value, parsed, config, targets, plans

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.ScanResult:
        value, parsed, config, targets, plans = await self._gate(ctx, params)
        rotation = core.Rotation(value)
        out: dict = {}
        complete = True
        base = 0
        stale = unopenable = 0
        for target in targets:
            name = state.field_name(target)
            per_store: dict = {}
            async with state.open_target_stores(
                config, target, plans[target.name], read_only=True
            ) as stores:
                for store in stores:

                    async def stop(records, base=base) -> bool:
                        await ctx.progress(base + records)
                        return await ctx.cancelled()

                    counts = await core.verify_store(
                        store, target, rotation, params.batch_size, stop
                    )
                    per_store[store.name] = counts
                    stale += counts.get("values_stale", 0)
                    unopenable += counts.get("values_unopenable", 0)
                    base += counts.get("records", 0)
                    await ctx.emit(
                        Events.verified, _event_counts(counts), [state.event_target(name), store.name]
                    )
                    if counts.get("stopped"):
                        complete = False
                        break
            out[name] = catalog.StoreCounts(
                **{n: _counts_model(c) for n, c in per_store.items()}
            )
            if not complete:
                break
        return catalog.ScanResult(
            complete=complete,
            primary_id=parsed.primary_key_id,
            values_stale=stale,
            values_unopenable=unopenable,
            **out,
        )


# --------------------------------------------------------------- drop_old
class DropOld(_Base):
    META = catalog.DROP_OLD

    async def _gate(self, ctx, params):
        self._typeform(params)
        keys, stored, value, parsed = await self._keyset(ctx)
        if parsed.primary_key_id in published_key_ids(parsed):
            raise Refusal("published_primary")
        # every service must already encrypt with the primary: otherwise one
        # could still write a value under a key about to be dropped
        await self._ready(ctx, params, parsed, stored)
        config = state.DataConfig.from_env()
        targets = state.selected_targets([])  # always every target
        plans = await self._ping_all(config, targets, StoreChoice.auto)
        return keys, stored, value, parsed, config, targets, plans

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.DropOldResult:
        keys, stored, value, parsed, config, targets, plans = await self._gate(ctx, params)
        rotation = core.Rotation(value)
        out: dict = {}
        base = 0
        stale = 0
        empty: List[str] = []
        stopped = False
        for target in targets:
            name = state.field_name(target)
            per_store: dict = {}
            async with state.open_target_stores(
                config, target, plans[target.name], read_only=True
            ) as stores:
                for store in stores:

                    async def stop(records, base=base) -> bool:
                        await ctx.progress(base + records)
                        return await ctx.cancelled()

                    counts = await core.scan(store, target, rotation, params.batch_size, stop)
                    per_store[store.name] = counts
                    base += counts.get("records", 0)
                    stale += counts.get("values_stale", 0)
                    await ctx.emit(Events.counted, _event_counts(counts), [state.event_target(name), store.name])
                    if counts.get("stopped"):
                        stopped = True
                        break
                    if counts.get("records", 0) == 0 and not (
                        target is core.GOOGLE_CREDENTIALS and params.allow_empty_google
                    ):
                        empty.append(f"{name}.{store.name}")
            out[name] = catalog.StoreCounts(
                **{n: _counts_model(c) for n, c in per_store.items()}
            )
            if stopped:
                break
        if stopped:
            raise Refusal("scan_incomplete")
        if stale:
            raise Refusal("values_on_old_key")
        if empty:
            raise Refusal("store_empty")
        old = [k for k in key_ids(parsed) if k != parsed.primary_key_id]
        if not old:
            return catalog.DropOldResult(
                complete=True,
                changed=False,
                nothing_to_drop=True,
                primary_id=parsed.primary_key_id,
                key_count=len(parsed.key),
                version=stored.version,
                revision=stored.revision,
                **out,
            )
        if ctx.dry_run:
            return catalog.DropOldResult(
                complete=True,
                changed=False,
                primary_id=parsed.primary_key_id,
                dropped_count=len(old),
                key_count=len(parsed.key),
                version=stored.version,
                revision=stored.revision,
                **out,
            )
        version, revision = await self._write(
            ctx, keys, stored, only_primary(parsed), "drop_old", {"dropped_count": len(old)}
        )
        await ctx.emit(Events.key_dropped, {"key_count": 1}, [str(k) for k in old][:20])
        return catalog.DropOldResult(
            complete=True,
            changed=True,
            primary_id=parsed.primary_key_id,
            dropped_count=len(old),
            key_count=1,
            version=version,
            revision=revision,
            **out,
        )


TASKS = (AddKey, Promote, Reencrypt, Verify, DropOld)
