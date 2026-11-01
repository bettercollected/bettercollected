"""The auth key rotation tasks (``authkeys.add_key``, ``promote``, ``reencrypt``,
``verify``, ``drop_old``). Metadata: ``catalog/authkeys.py``; the ring and the
gates: ``authkeys_state.py``; the walk over the sealed values:
``authkeys_core.py``. The runbook with the order across services:
docs/auth-key-rotation.md.

The guards of ``keyset.*`` carry over:

* a key is only added as the SECOND member of the ring, and only then promoted;
  nothing signs or encrypts with it before every service has restarted onto the
  ring that holds it (heartbeats);
* values are re-encrypted with a compare-and-swap write, checked to decrypt
  back before the write and read back after it before they are counted;
* the old key is dropped only after a full scan found nothing on it (``aes``) or
  after what it still covers was counted and accepted (``jwt``);
* the ring is written through ``settings.task_write_keyset`` (migration 0020):
  one version up, under the writer lock, with the audit row and the notice for
  all admins in the same transaction.

The ring is never printed, logged, put in an event or a result: ids and counts.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Dict, List

from cryptography.fernet import Fernet

from backend.admin.tasks.catalog import authkeys as catalog
from backend.admin.tasks.catalog.authkeys import Events, Targets, Which
from backend.admin.tasks.impl import authkeys_core as core
from backend.admin.tasks.impl import authkeys_state as ring_state
from backend.admin.tasks.impl import keyset_state as state
from backend.admin.tasks.impl.authkeys_state import member_id
from backend.admin.tasks.spec import Refusal, TaskError
from common.settings import key_ring

TARGET_ORDER = (
    "forms",
    "form_versions",
    "actions",
    "workspace_actions",
    "scim_directories",
    "registration_services",
    "form_webhooks",
)
COUNTERS = (
    "records",
    "values",
    "values_current",
    "values_stale",
    "values_unopenable",
    "values_plain",
    "records_reencrypted",
    "values_reencrypted",
    "records_changed_concurrently",
    "records_readback_failed",
)


def _selected(chosen) -> List[core.Target]:
    wanted = set(chosen) or set(Targets)
    return [core.TARGETS[name] for name in TARGET_ORDER if Targets(name) in wanted]


def _counts_model(counts: Dict[str, int]) -> catalog.TargetCounts:
    known = catalog.TargetCounts.model_fields
    return catalog.TargetCounts(**{k: v for k, v in counts.items() if k in known})


def _event_counts(counts: Dict[str, int]) -> Dict[str, int]:
    return {k: int(v) for k, v in counts.items() if k in COUNTERS}


def _new_member(which: Which) -> str:
    return Fernet.generate_key().decode() if which is Which.aes else secrets.token_hex(32)


class _Base:
    """Gates shared by the five tasks."""

    async def _ring(self, ctx, params):
        return await ring_state.read_ring(ctx, params.which)

    async def _ready(self, ctx, params, stored) -> int:
        async with ctx.connection() as conn:
            return await ring_state.check_ring_consumers(
                conn,
                name=ring_state.SETTING[params.which],
                min_revision=stored.revision,
                google_in_use=params.google_in_use,
            )

    @staticmethod
    def _external(params, ctx=None) -> None:
        """The workers and the actions executor hold copies of the encryption key
        and cannot report: the operator signs that they hold the ring. The JWT
        secret has no copy outside the stack's own services."""
        if params.which is Which.aes and not params.external_consumers_updated:
            raise Refusal("external_consumers_unconfirmed")

    @staticmethod
    def _data():
        """The data role's connection (``DATABASE_URL``): the sealed values live in
        the backend's schema."""
        config = state.DataConfig.from_env()
        if not config.database_url:
            raise Refusal("store_not_configured")
        return config

    @staticmethod
    async def _ping(config, targets) -> None:
        async with _open_stores(config, targets, read_only=True) as stores:
            for store in stores.values():
                try:
                    await state.ping(store)
                except Exception:  # noqa: BLE001 - never surface a driver message
                    raise Refusal("store_unreachable") from None

    async def _write(self, ctx, keys, stored, which, ring_text, action, extra=None):
        async with ctx.connection() as conn:
            return await state.write_stored(
                conn,
                keys,
                stored,
                ring_text,
                requested_by=ctx.requested_by,
                run_id=ctx.run_id,
                task=ctx.task,
                action=action,
                extra=extra,
                name=ring_state.SETTING[which],
            )


@asynccontextmanager
async def _open_stores(config, targets, *, read_only: bool):
    """One engine on the data role (``DATABASE_URL``), a store per target. A dry
    run's connections are read only at the server."""
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = {"statement_timeout": "60000"}
    if read_only:
        settings["default_transaction_read_only"] = "on"
    engine = create_async_engine(
        config.database_url,
        pool_size=2,
        max_overflow=0,
        connect_args={"server_settings": settings},
    )
    try:
        yield {t.name: core.PostgresStore(engine, t) for t in targets}
    finally:
        try:
            await engine.dispose()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------- add_key
class AddKey(_Base):
    META = catalog.ADD_KEY

    async def _gate(self, ctx, params):
        if not params.ring_build_deployed:
            raise Refusal("ring_build_unconfirmed")
        keys, stored, ring = await self._ring(ctx, params)
        if len(ring.members) > 1:  # a rotation is under way: finish it first
            raise Refusal("rotation_in_progress")
        if params.which is Which.jwt and "," in ring.primary:
            # "<secret with a comma>,<new>" could not be told from a ring
            raise Refusal("secret_has_separator")
        await self._ready(ctx, params, stored)
        return keys, stored, ring

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.RingChange:
        keys, stored, ring = await self._gate(ctx, params)
        if ctx.dry_run:
            return catalog.RingChange(
                changed=False,
                primary_id=ring.primary_id,
                key_count=len(ring.members),
                version=stored.version,
                revision=stored.revision,
            )
        new = _new_member(params.which)
        added = key_ring.join([ring.primary, new])
        new_id = member_id(new)
        version, revision = await self._write(
            ctx, keys, stored, params.which, added, "add_key",
            {"added_key_id": new_id, "key_count": 2},
        )
        await ctx.emit(Events.key_added, {"key_count": 2}, [str(new_id)])
        return catalog.RingChange(
            changed=True,
            primary_id=ring.primary_id,
            key_count=2,
            added_key_id=new_id,
            version=version,
            revision=revision,
        )


# --------------------------------------------------------------- promote
class Promote(_Base):
    META = catalog.PROMOTE

    async def _gate(self, ctx, params):
        keys, stored, ring = await self._ring(ctx, params)
        if len(ring.members) < 2:
            raise Refusal("no_rotation_in_progress")
        if params.new_primary_id not in ring.ids:
            raise Refusal("member_not_in_ring")
        if ring.primary_id != params.new_primary_id:
            self._external(params)
            # every service must already hold the new key as the second member
            await self._ready(ctx, params, stored)
        return keys, stored, ring

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.RingChange:
        keys, stored, ring = await self._gate(ctx, params)
        previous = ring.primary_id
        if previous == params.new_primary_id or ctx.dry_run:
            return catalog.RingChange(
                changed=False,
                primary_id=previous,
                previous_primary_id=previous,
                key_count=len(ring.members),
                version=stored.version,
                revision=stored.revision,
            )
        new = ring.member(params.new_primary_id)
        promoted = key_ring.join([new, *ring.others(new)])
        version, revision = await self._write(
            ctx, keys, stored, params.which, promoted, "promote",
            {"primary_id": params.new_primary_id},
        )
        await ctx.emit(Events.key_promoted, {"key_count": len(ring.members)}, [str(params.new_primary_id)])
        return catalog.RingChange(
            changed=True,
            primary_id=params.new_primary_id,
            previous_primary_id=previous,
            key_count=len(ring.members),
            version=version,
            revision=revision,
        )


# -------------------------------------------------------------- reencrypt
class Reencrypt(_Base):
    META = catalog.REENCRYPT

    async def _gate(self, ctx, params):
        if params.which is not Which.aes:
            raise Refusal("nothing_to_reencrypt")  # a signing secret seals nothing
        keys, stored, ring = await self._ring(ctx, params)
        if ring.primary_id != params.primary_id:
            raise Refusal("primary_mismatch")
        if not ctx.dry_run:
            self._external(params)
        await self._ready(ctx, params, stored)
        config = self._data()
        targets = _selected(params.targets)
        await self._ping(config, targets)
        return ring, config, targets

    async def precheck(self, ctx, params) -> None:
        ring, *_ = await self._gate(ctx, params)

        async def fingerprint():  # a resume must see the same ring (ids, never members)
            return ",".join(str(i) for i in ring.ids)

        ctx.fingerprint = fingerprint

    async def run(self, ctx, params) -> catalog.ScanResult:
        ring, config, targets = await self._gate(ctx, params)
        rotation = core.Rotation(ring.text())
        cursor = None if ctx.dry_run else await ctx.load_checkpoint()
        resume_target = cursor.get("t") if cursor else None
        done = int(cursor.get("d", 0)) if cursor else 0
        skipping = resume_target is not None
        out: dict = {}
        tallies: List[dict] = []
        complete = True

        async with _open_stores(config, targets, read_only=ctx.dry_run) as stores:
            for target in targets:
                name = target.name
                resume_after = None
                if skipping:
                    if name != resume_target:
                        continue  # finished by the earlier run
                    skipping = False
                    resume_after = cursor.get("a")
                store = stores[name]
                base = done

                if ctx.dry_run:

                    async def stop(records, base=base) -> bool:
                        await ctx.progress(base + records)
                        return await ctx.cancelled()

                    counts = await core.scan(store, target, rotation, params.batch_size, stop)
                    await ctx.emit(Events.counted, _event_counts(counts), [name, "postgres"])
                else:

                    async def on_batch(after, counts, name=name, base=base) -> bool:
                        await ctx.checkpoint(
                            {"t": name, "a": str(after), "d": base + counts.get("records", 0)}
                        )
                        await ctx.progress(base + counts.get("records", 0))
                        return await ctx.cancelled()

                    counts, _last = await core.reencrypt_store(
                        store, target, rotation,
                        batch_size=params.batch_size,
                        start_after=resume_after,
                        on_batch=on_batch,
                    )
                    await ctx.emit(Events.reencrypted, _event_counts(counts), [name, "postgres"])
                tallies.append(counts)
                out[name] = _counts_model(counts)
                done = base + counts.get("records", 0)
                if counts.get("stopped"):
                    complete = False
                    break
        if skipping:  # the checkpoint names a target this run does not cover
            raise TaskError("resume_mismatch")
        stale = sum(c.get("values_stale", 0) for c in tallies) if ctx.dry_run else 0
        unopenable = sum(c.get("values_unopenable", 0) for c in tallies)
        return catalog.ScanResult(
            complete=complete,
            primary_id=ring.primary_id,
            key_count=len(ring.members),
            values_stale=stale,
            values_unopenable=unopenable,
            **out,
        )


# ----------------------------------------------------------------- verify
class Verify(_Base):
    META = catalog.VERIFY

    async def _gate(self, ctx, params):
        keys, stored, ring = await self._ring(ctx, params)
        config = targets = None
        if params.which is Which.aes:
            config = self._data()
            targets = _selected(params.targets)
            await self._ping(config, targets)
        return stored, ring, config, targets

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def run(self, ctx, params) -> catalog.ScanResult:
        stored, ring, config, targets = await self._gate(ctx, params)
        out: dict = {}
        complete = True
        stale = unopenable = base = 0
        gates = None
        if params.which is Which.aes:
            rotation = core.Rotation(ring.text())
            async with _open_stores(config, targets, read_only=True) as stores:
                for target in targets:

                    async def stop(records, base=base) -> bool:
                        await ctx.progress(base + records)
                        return await ctx.cancelled()

                    counts = await core.scan(
                        stores[target.name], target, rotation, params.batch_size, stop
                    )
                    stale += counts.get("values_stale", 0)
                    unopenable += counts.get("values_unopenable", 0)
                    base += counts.get("records", 0)
                    out[target.name] = _counts_model(counts)
                    await ctx.emit(Events.verified, _event_counts(counts), [target.name, "postgres"])
                    if counts.get("stopped"):
                        complete = False
                        break
        if len(ring.members) > 1 and complete:
            # what a drop of the previous key would cost now (after the promote)
            gates = await _gates(ctx, params.which, stored)
            await ctx.emit(Events.counted, _gate_counts(gates), [params.which.value])
        return catalog.ScanResult(
            complete=complete,
            primary_id=ring.primary_id,
            key_count=len(ring.members),
            values_stale=stale,
            values_unopenable=unopenable,
            gates=gates,
            **out,
        )


async def _gates(ctx, which: Which, stored) -> catalog.Gates:
    """The counts a drop of the previous key depends on, with the time the
    previous key stopped signing (the stored row's write: the promote)."""
    async with ctx.connection() as conn:
        if which is Which.aes:
            return catalog.Gates(checked=True, jobs_pending=await ring_state.jobs_pending(conn))
        at = stored.updated_at
        if at is None:
            raise Refusal("counts_unavailable")
        return catalog.Gates(
            checked=True,
            sessions_on_previous=await ring_state.sessions_on_previous(conn, at),
            drafts_on_previous=await ring_state.drafts_on_previous(conn, at),
        )


def _gate_counts(gates: catalog.Gates) -> Dict[str, int]:
    return {
        "sessions_on_previous": gates.sessions_on_previous,
        "drafts_on_previous": gates.drafts_on_previous,
        "jobs_pending": gates.jobs_pending,
    }


# --------------------------------------------------------------- drop_old
class DropOld(_Base):
    META = catalog.DROP_OLD

    async def _gate(self, ctx, params):
        keys, stored, ring = await self._ring(ctx, params)
        if ring.primary_id != params.keep_id:
            raise Refusal("primary_mismatch")  # also: the promote has not happened
        if len(ring.members) < 2:
            return keys, stored, ring, None, None
        self._external(params)
        # every service must already sign/encrypt with the kept key: otherwise
        # one could still write a value under the key about to be dropped
        await self._ready(ctx, params, stored)
        config = targets = None
        if params.which is Which.aes:
            config = self._data()
            targets = _selected([])  # always every target
            await self._ping(config, targets)
        return keys, stored, ring, config, targets

    async def precheck(self, ctx, params) -> None:
        await self._gate(ctx, params)

    async def _scan(self, ctx, ring, config, targets, params):
        """Every target with the ring: nothing may be on the previous key, nothing
        unopenable, and not every target empty. Returns (per-target models,
        sealed values seen)."""
        rotation = core.Rotation(ring.text())
        out: dict = {}
        base = stale = unopenable = sealed = 0
        stopped = False
        async with _open_stores(config, targets, read_only=True) as stores:
            for target in targets:

                async def stop(records, base=base) -> bool:
                    await ctx.progress(base + records)
                    return await ctx.cancelled()

                counts = await core.scan(stores[target.name], target, rotation, params.batch_size, stop)
                base += counts.get("records", 0)
                stale += counts.get("values_stale", 0)
                unopenable += counts.get("values_unopenable", 0)
                sealed += counts.get("values", 0)
                out[target.name] = _counts_model(counts)
                await ctx.emit(Events.counted, _event_counts(counts), [target.name, "postgres"])
                if counts.get("stopped"):
                    stopped = True
                    break
        if stopped:
            raise Refusal("scan_incomplete")
        if stale:
            raise Refusal("values_on_previous")
        if unopenable:
            raise Refusal("values_not_readable")
        if sealed == 0 and not params.allow_empty:
            # no sealed value at all looks like a wrong or empty database
            raise Refusal("store_empty")
        return out

    async def run(self, ctx, params) -> catalog.DropOldResult:
        keys, stored, ring, config, targets = await self._gate(ctx, params)
        if len(ring.members) < 2:
            return catalog.DropOldResult(
                complete=True,
                changed=False,
                nothing_to_drop=True,
                primary_id=ring.primary_id,
                key_count=len(ring.members),
                version=stored.version,
                revision=stored.revision,
                ready=True,
            )
        out: dict = {}
        if params.which is Which.aes:
            out = await self._scan(ctx, ring, config, targets, params)
        gates = await _gates(ctx, params.which, stored)
        await ctx.emit(Events.counted, _gate_counts(gates), [params.which.value])
        if gates.jobs_pending:
            raise Refusal("jobs_pending")
        accepted = True
        if gates.sessions_on_previous and not params.accept_sign_out:
            accepted = False
        if gates.drafts_on_previous and not params.accept_draft_link_loss:
            accepted = False
        if ctx.dry_run:
            return catalog.DropOldResult(
                complete=True,
                changed=False,
                primary_id=ring.primary_id,
                dropped_count=len(ring.members) - 1,
                key_count=len(ring.members),
                version=stored.version,
                revision=stored.revision,
                gates=gates,
                ready=accepted,
                **out,
            )
        if gates.sessions_on_previous and not params.accept_sign_out:
            raise Refusal("sign_out_not_accepted")
        if gates.drafts_on_previous and not params.accept_draft_link_loss:
            raise Refusal("draft_links_not_accepted")
        # the scan can take a while: the services must still be ready, and the
        # counts must still hold, NOW
        await self._ready(ctx, params, stored)
        again = await _gates(ctx, params.which, stored)
        if again.jobs_pending:
            raise Refusal("jobs_pending")
        dropped = [member_id(m) for m in ring.others(ring.primary)]
        version, revision = await self._write(
            ctx, keys, stored, params.which, ring.primary, "drop_old",
            {"dropped_count": len(dropped)},
        )
        await ctx.emit(Events.key_dropped, {"key_count": 1}, ring_state.event_ids(dropped))
        return catalog.DropOldResult(
            complete=True,
            changed=True,
            primary_id=ring.primary_id,
            dropped_count=len(dropped),
            key_count=1,
            version=version,
            revision=revision,
            gates=again,
            ready=True,
            **out,
        )


TASKS = (AddKey, Promote, Reencrypt, Verify, DropOld)
