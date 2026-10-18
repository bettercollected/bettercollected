"""``selftest_slow``: a mutating, batch-wise task used only to test the runner
(locks, cancel, resume, takeover, caps, dry runs)."""

import enum

from backend.admin.tasks.spec import Params, Result, TaskMeta


class Events(str, enum.Enum):
    batch_done = "batch_done"
    note = "note"


class Refusals(str, enum.Enum):
    declined = "declined"


class SlowParams(Params):
    items: int = 10
    batch_size: int = 5
    emit_events: int = 0
    fail_at: int = -1
    decline: bool = False
    write_probe: bool = False


class SlowResult(Result):
    changed: int
    unchanged: int
    batches: int


META = TaskMeta(
    name="selftest_slow",
    version=1,
    params=SlowParams,
    result=SlowResult,
    events=Events,
    mutating=True,
    resources=("selftest_resource",),
    resumable=True,
    requires_prior_dry_run=False,
    title="Runner self-test (slow, mutating)",
    refusals=Refusals,
    internal=True,
)

# same behaviour, but a real change needs a recent dry run (tests the gate)
GUARDED_META = TaskMeta(
    name="selftest_guarded",
    version=1,
    params=SlowParams,
    result=SlowResult,
    events=Events,
    mutating=True,
    resumable=False,
    requires_prior_dry_run=True,
    title="Runner self-test (needs a dry run)",
    internal=True,
)
