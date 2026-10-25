"""``responses.check_undecryptable``: read-only count of stored response values
that carry the ciphertext prefix but do not decrypt (counts per store and
field; never ids, values or plaintext)."""

from __future__ import annotations

from backend.admin.tasks.catalog.responses_check import (
    META,
    CheckParams,
    CheckResult,
    Events,
)
from backend.admin.tasks.impl.responses_common import (
    StoreConfig,
    load_task_keyset,
    make_opener,
    open_stores,
    preflight,
)
from backend.admin.tasks.impl.responses_scan import STORE_CLASSES, check_store
from backend.admin.tasks.spec import Refusal, TaskError

_FIELD_NAMES = {
    "answers": "answers",
    "hidden_fields": "hidden_fields",
    "internal_answers": "internal_answers",
    "respondent_feedback.message": "feedback_message",
}
_EVENT = {"postgres": Events.scanned_postgres}


class CheckUndecryptable:
    META = META

    async def precheck(self, ctx, params: CheckParams) -> None:
        await preflight(
            params.stores, STORE_CLASSES, read_only=True, keyset=await load_task_keyset(ctx)
        )

    async def run(self, ctx, params: CheckParams) -> CheckResult:
        config = StoreConfig.from_env()
        names = config.resolve(params.stores)
        keyset = await load_task_keyset(ctx)
        if keyset is None:
            raise Refusal("keyset_missing")
        opens = make_opener(keyset)
        scanned = 0
        out: dict = {}
        complete = True

        async with open_stores(config, names, STORE_CLASSES, read_only=True) as stores:
            for store in stores:
                base = scanned

                async def on_batch(_name: str, responses: int, base=base) -> bool:
                    await ctx.progress(base + responses)
                    return await ctx.cancelled()

                report = await check_store(store, opens, params.batch_size, on_batch)
                scanned = base + report["responses"]
                tallies = {
                    _FIELD_NAMES[field]: tally for field, tally in report["fields"].items()
                }
                out[store.name] = {
                    "responses": report["responses"],
                    "does_not_decrypt": report["does_not_decrypt"],
                    **tallies,
                }
                await ctx.emit(
                    _EVENT[store.name],
                    {
                        "responses": report["responses"],
                        "does_not_decrypt": report["does_not_decrypt"],
                    },
                )
                if report.get("complete") is False:
                    complete = False
                    break
        if not out:
            raise TaskError("nothing_scanned")
        return CheckResult(complete=complete, **out)
