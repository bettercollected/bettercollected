"""``responses.backfill_workspaces``: stamp responses and deletion requests with
their workspace. Attributes by the form's only workspace or by the key context
that opens the stored ciphertext; ambiguous and orphaned records stay
unstamped (it never guesses). Resumes by id cursor."""

from __future__ import annotations

from backend.admin.tasks.catalog.responses_backfill import (
    META,
    BackfillParams,
    BackfillResult,
    Events,
)
from backend.admin.tasks.impl.responses_backfill import (
    PHASES,
    STORE_CLASSES,
    backfill_store,
)
from backend.admin.tasks.impl.responses_common import (
    StoreConfig,
    keyset_fingerprint,
    load_task_keyset,
    make_opener,
    open_stores,
    preflight,
)
from backend.admin.tasks.spec import Refusal, TaskError

_EVENT = {"postgres": Events.backfilled_postgres}


class BackfillWorkspaces:
    META = META

    async def precheck(self, ctx, params: BackfillParams) -> None:
        # without the keyset the script would classify every multi-link form as
        # ambiguous; the task refuses instead of silently doing less
        _, _, keyset = await preflight(
            params.stores, STORE_CLASSES, read_only=ctx.dry_run, keyset=await load_task_keyset(ctx)
        )

        async def fingerprint():
            return keyset_fingerprint(keyset)

        ctx.fingerprint = fingerprint  # a resume must see the same keyset

    async def run(self, ctx, params: BackfillParams) -> BackfillResult:
        config = StoreConfig.from_env()
        names = config.resolve(params.stores)
        keyset = await load_task_keyset(ctx)
        if keyset is None:
            raise Refusal("keyset_missing")
        opens = make_opener(keyset, lenient=True)
        # a dry run starts over: what it plans is not stored anywhere to resume
        cursor = None if ctx.dry_run else await ctx.load_checkpoint()
        resume_store = cursor.get("store") if cursor else None
        done = int(cursor.get("done", 0)) if cursor else 0
        skipping = resume_store is not None
        out: dict = {}
        complete = True

        async with open_stores(
            config, names, STORE_CLASSES, read_only=ctx.dry_run
        ) as stores:
            for store in stores:
                resume = None
                if skipping:
                    if store.name != resume_store:
                        continue  # finished by the earlier run
                    skipping = False
                    if cursor["phase"] in PHASES:
                        resume = {
                            "phase": cursor["phase"],
                            "after": store.decode_key(cursor["after"]),
                        }
                base = done

                async def on_batch(phase, after, seen, store=store, base=base) -> bool:
                    await ctx.checkpoint(
                        {
                            "store": store.name,
                            "phase": phase,
                            "after": store.encode_key(after),
                            "done": base + seen,
                        }
                    )
                    await ctx.progress(base + seen)
                    return await ctx.cancelled()

                report = await backfill_store(
                    store,
                    apply=not ctx.dry_run,
                    opens=opens,
                    batch_size=params.batch_size,
                    workspace_id=params.workspace_id,
                    form_ids=params.form_ids,
                    resume=resume,
                    on_batch=on_batch,
                )
                responses = report.get("responses", {})
                requests = report.get("deletion_requests", {})
                done = base + responses.get("unstamped", 0) + requests.get("unstamped", 0)
                out[store.name] = {
                    "forms_linked_to_several_workspaces": report[
                        "forms_linked_to_several_workspaces"
                    ],
                    "responses": responses,
                    "deletion_requests": requests,
                }
                await ctx.emit(
                    _EVENT[store.name],
                    {
                        "responses_stamped": responses.get("stamped", 0),
                        "requests_stamped": requests.get("stamped", 0),
                        "ambiguous": responses.get("ambiguous", 0)
                        + requests.get("ambiguous", 0),
                        "orphaned": responses.get("orphaned", 0)
                        + requests.get("orphaned", 0),
                    },
                )
                if report.get("complete") is False:
                    complete = False
                    break
        if skipping:  # the checkpoint names a store this run does not cover
            raise TaskError("resume_mismatch")
        return BackfillResult(complete=complete, **out)
