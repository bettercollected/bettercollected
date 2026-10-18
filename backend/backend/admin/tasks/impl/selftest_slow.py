"""Mutating test task. The "world" it changes is an in-process set, so a second
run finds everything done (changed == 0): the idempotency contract in miniature.
Tests hook ``HOOKS.before_batch`` to hold a run between batches."""

import uuid

from sqlalchemy import text

from backend.admin.tasks.catalog.selftest_slow import (
    GUARDED_META,
    META,
    Events,
    SlowParams,
    SlowResult,
)
from backend.admin.tasks.spec import Refusal, TaskError


class Hooks:
    async def before_batch(self, ctx, index: int) -> None:  # replaced by tests
        return None


HOOKS = Hooks()
WORLD: set[int] = set()  # items already applied (tests clear it)


class SelfTestSlow:
    META = META

    async def precheck(self, ctx, params: SlowParams) -> None:
        if params.decline:
            raise Refusal("declined")

    async def run(self, ctx, params: SlowParams) -> SlowResult:
        start = 0
        cursor = await ctx.load_checkpoint()
        if cursor:
            start = int(cursor.get("next", 0))
        if params.write_probe:
            # a write through the task's own connection: refused in a dry run
            async with ctx.connection() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO tasks.locks (name, run_id, runner_id) "
                        "VALUES ('probe', :id, 'probe')"
                    ),
                    {"id": uuid.UUID(ctx.run_id)},
                )
        changed = unchanged = batches = 0
        size = max(1, params.batch_size)
        for lo in range(start, params.items, size):
            if await ctx.cancelled():
                break
            await HOOKS.before_batch(ctx, lo // size)
            for item in range(lo, min(lo + size, params.items)):
                if item == params.fail_at:
                    raise TaskError("planted_failure")
                if item in WORLD:
                    unchanged += 1
                elif not ctx.dry_run:
                    WORLD.add(item)
                    changed += 1
                else:
                    changed += 1  # would change
            batches += 1
            await ctx.checkpoint({"next": min(lo + size, params.items)})
            await ctx.progress(min(lo + size, params.items), params.items)
            await ctx.emit(Events.batch_done, {"batch": batches, "changed": changed})
        for _ in range(params.emit_events):
            await ctx.emit(Events.note, {"n": 1})
        return SlowResult(changed=changed, unchanged=unchanged, batches=batches)


class SelfTestGuarded(SelfTestSlow):
    META = GUARDED_META
