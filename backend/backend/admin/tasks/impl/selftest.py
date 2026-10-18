from backend.admin.tasks.catalog.selftest import (
    META,
    Events,
    SelfTestParams,
    SelfTestResult,
)
from backend.admin.tasks.spec import Refusal


class SelfTest:
    META = META

    async def precheck(self, ctx, params: SelfTestParams) -> None:
        if params.decline:
            raise Refusal("declined")

    async def run(self, ctx, params: SelfTestParams) -> SelfTestResult:
        rounds = max(0, params.rounds)
        for i in range(rounds):
            await ctx.emit(Events.checked, {"round": i})
            await ctx.progress(i + 1, rounds)
        return SelfTestResult(ok=True, checked=rounds)
