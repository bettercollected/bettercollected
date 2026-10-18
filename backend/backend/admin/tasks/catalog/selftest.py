"""``selftest``: a read-only task that proves the runner works end to end."""

import enum

from backend.admin.tasks.spec import Params, Result, TaskMeta


class Events(str, enum.Enum):
    checked = "checked"


class Refusals(str, enum.Enum):
    declined = "declined"


class SelfTestParams(Params):
    rounds: int = 3
    decline: bool = False


class SelfTestResult(Result):
    ok: bool
    checked: int


META = TaskMeta(
    name="selftest",
    version=1,
    params=SelfTestParams,
    result=SelfTestResult,
    events=Events,
    mutating=False,
    title="Runner self-test",
    refusals=Refusals,
    internal=True,
)
