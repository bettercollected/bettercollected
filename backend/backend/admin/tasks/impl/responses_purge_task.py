"""``responses.purge_orphaned_forms``: delete the forms in no workspace, with
their responses, deletion requests, versions and responder-group links, in
every store the run covers (primary first, as the services write).

Scope and order: :mod:`responses_purge`. Guards:

* the scope is evaluated at run time against EVERY configured store (a link
  or a stamped response in a store the run does not cover still keeps a form);
* an apply run deletes only when the forms and responses it finds equal
  ``expected_forms`` and ``expected_responses`` (the dry run's numbers), and
  only when the covered stores hold the same responses for them;
* each batch is checked again just before it is deleted (a form that gained a
  link or a stamped response is skipped and reported);
* a checkpoint names the batch in progress before it is deleted, so a resume
  finishes it and the expected counts still add up.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from backend.admin.tasks.catalog.responses_purge import (
    META,
    Events,
    PurgeParams,
    PurgeResult,
)
from backend.admin.tasks.impl.responses_common import StoreConfig, open_stores
from backend.admin.tasks.impl.responses_purge import (
    KINDS,
    STORE_CLASSES,
    Plan,
    find_orphans,
    still_orphans,
)
from backend.admin.tasks.spec import ID_RE, Refusal, TaskError

_EVENT = {"mongo": Events.purged_mongo, "postgres": Events.purged_postgres}


def _ids(forms) -> List[str]:
    """Form ids as an event may carry them (the id pattern; at most 20)."""
    return [f for f in forms if ID_RE.match(f)][:20]


def _day(value) -> Optional[str]:
    return value.date().isoformat() if value is not None else None


def _zero() -> Dict[str, int]:
    return {kind: 0 for kind in KINDS}


def _store_result(counts: Dict[str, int]) -> Dict[str, int]:
    return {
        "form_documents": counts["forms"],
        "responses": counts["responses"],
        "deletion_requests": counts["deletion_requests"],
        "versions": counts["versions"],
        "group_links": counts["group_links"],
    }


class PurgeOrphanedForms:
    META = META

    async def precheck(self, ctx, params: PurgeParams) -> None:
        if not ctx.dry_run and (
            params.expected_forms is None or params.expected_responses is None
        ):
            raise Refusal("expected_counts_missing")
        config = StoreConfig.from_env()
        targets = config.resolve(params.stores)
        async with open_stores(
            config, config.configured(), STORE_CLASSES, read_only=True
        ) as stores:
            for store in stores:
                try:
                    await store.ping()
                    count = await store.count_responses()
                except Exception:  # noqa: BLE001 - never surface a driver message
                    raise Refusal("store_unreachable") from None
                # a wrong or empty database must not look like "nothing to do"
                if store.name in targets and count == 0:
                    raise Refusal("store_empty")

    async def run(self, ctx, params: PurgeParams) -> PurgeResult:
        config = StoreConfig.from_env()
        targets = config.resolve(params.stores)
        others = [n for n in config.configured() if n not in targets]
        cursor = None if ctx.dry_run else await ctx.load_checkpoint()

        async with AsyncExitStack() as stack:
            # the covered stores (written by an apply run), then the configured
            # stores it only reads (their links and stamps still count)
            written = await stack.enter_async_context(
                open_stores(config, targets, STORE_CLASSES, read_only=ctx.dry_run)
            )
            read = await stack.enter_async_context(
                open_stores(config, others, STORE_CLASSES, read_only=True)
            )
            every = [*written, *read]
            plan = await find_orphans(every, targets, params.newest_response_before)
            if ctx.dry_run:
                return await self._dry_run(ctx, params, plan, written, targets)
            return await self._apply(ctx, params, plan, written, every, targets, cursor)

    # ----------------------------------------------------------------- dry run
    async def _dry_run(self, ctx, params, plan: Plan, written, targets) -> PurgeResult:
        primary = targets[0]
        responses = plan.store_responses(primary)
        await self._found(ctx, plan, responses)
        per_store: Dict[str, Dict[str, int]] = {}
        size = params.forms_per_batch
        for store in written:
            totals = _zero()
            for start in range(0, len(plan.forms), size):
                counts = await store.count(plan.forms[start : start + size])
                for kind in KINDS:
                    totals[kind] += counts[kind]
            per_store[store.name] = _store_result(totals)
            await ctx.emit(_EVENT[store.name], per_store[store.name])
        match = None
        if params.expected_forms is not None and params.expected_responses is not None:
            match = (
                params.expected_forms == len(plan.forms)
                and params.expected_responses == responses
                and plan.stores_agree()
            )
        return PurgeResult(
            complete=True,
            forms=len(plan.forms),
            responses=responses,
            skipped_stamped=plan.skipped_stamped,
            skipped_newer=plan.skipped_newer,
            stores_agree=plan.stores_agree(),
            expected_counts_match=match,
            oldest_response=_day(plan.oldest),
            newest_response=_day(plan.newest),
            **per_store,
        )

    async def _found(self, ctx, plan: Plan, responses: int) -> None:
        await ctx.emit(
            Events.orphans_found,
            {
                "forms": len(plan.forms),
                "responses": responses,
                "skipped_stamped": plan.skipped_stamped,
                "skipped_newer": plan.skipped_newer,
            },
        )

    # ------------------------------------------------------------------- apply
    async def _apply(
        self, ctx, params, plan: Plan, written, every, targets, cursor
    ) -> PurgeResult:
        primary = targets[0]
        state: Dict[str, Any] = {
            "handled_forms": 0,
            "handled_responses": 0,
            "skipped_changed": 0,
            "batch": [],
            "batch_responses": 0,
            "oldest": _day(plan.oldest),
            "newest": _day(plan.newest),
            "stores": {name: _zero() for name in targets},
        }
        if cursor:
            if set(cursor.get("stores", {})) != set(targets):
                raise TaskError("resume_mismatch")  # another set of stores
            state.update(cursor)
        in_flight: List[str] = list(state["batch"])
        remaining = [f for f in plan.forms if f not in set(in_flight)]
        remaining_responses = plan.store_responses(primary, remaining)
        found_forms = state["handled_forms"] + len(in_flight) + len(remaining)
        found_responses = (
            state["handled_responses"] + state["batch_responses"] + remaining_responses
        )
        await self._found(ctx, plan, remaining_responses)
        # a batch an earlier run had started may be gone from one store already
        if not plan.stores_agree(remaining):
            raise Refusal("stores_disagree")
        if (found_forms, found_responses) != (
            params.expected_forms,
            params.expected_responses,
        ):
            raise Refusal("expected_counts_mismatch")

        batches: List[List[str]] = []
        if in_flight:
            batches.append(in_flight)  # the batch an earlier run had started
        size = params.forms_per_batch
        batches += [remaining[i : i + size] for i in range(0, len(remaining), size)]
        complete = True
        for number, batch in enumerate(batches):
            resumed = number == 0 and bool(in_flight)
            batch_responses = (
                state["batch_responses"] if resumed else plan.store_responses(primary, batch)
            )
            state["batch"], state["batch_responses"] = batch, batch_responses
            await ctx.checkpoint(state)  # before anything of the batch goes
            keep = await still_orphans(every, batch)
            changed = [f for f in batch if f not in keep]
            if changed:
                state["skipped_changed"] += len(changed)
                await ctx.emit(Events.skipped_changed, {"forms": len(changed)}, _ids(changed))
            deleted = _zero()
            if keep:
                for store in written:  # primary first
                    counts = await store.delete(keep)
                    for kind in KINDS:
                        state["stores"][store.name][kind] += counts[kind]
                        if store.name == primary:
                            deleted[kind] += counts[kind]
                await ctx.emit(Events.purged_batch, _store_result(deleted), _ids(keep))
            state["handled_forms"] += len(batch)
            state["handled_responses"] += batch_responses
            state["batch"], state["batch_responses"] = [], 0
            await ctx.checkpoint(state)
            await ctx.progress(state["handled_forms"], found_forms)
            if number < len(batches) - 1 and await ctx.cancelled():
                complete = False
                break

        per_store = {name: _store_result(state["stores"][name]) for name in targets}
        for name in targets:
            await ctx.emit(_EVENT[name], per_store[name])
        return PurgeResult(
            complete=complete,
            forms=found_forms,
            responses=found_responses,
            skipped_stamped=plan.skipped_stamped,
            skipped_newer=plan.skipped_newer,
            skipped_changed=state["skipped_changed"],
            stores_agree=True,
            oldest_response=state["oldest"],
            newest_response=state["newest"],
            **per_store,
        )
