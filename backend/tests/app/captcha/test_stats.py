"""The buffered daily counts (``services/captcha/stats.py``): counted in memory,
written in batches, bounded, a failing database keeps them (bounded), swept after
the retention, and nothing but ids and numbers in them."""

import asyncio

import pytest

from backend.app.repositories.postgres.analytics import captcha_count_id
from backend.app.services.captcha import stats as st


class Repo:
    def __init__(self):
        self.written = []
        self.swept = []
        self.fail = False

    async def add_counts(self, counts):
        if self.fail:
            raise RuntimeError("down")
        self.written.append(dict(counts))

    async def delete_before(self, day):
        self.swept.append(day)
        return 0

    async def totals(self, **kwargs):
        merged = {}
        for batch in self.written:
            for (day, ws, form, purpose, outcome), n in batch.items():
                merged[(purpose, outcome)] = merged.get((purpose, outcome), 0) + n
        return merged


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def make(retention=395):
    clock, repo = Clock(), Repo()
    return st.CaptchaStats(repo, clock, lambda: retention), repo, clock


async def test_a_count_is_in_memory_until_a_batch_is_due():
    stats, repo, clock = make()
    for _ in range(10):
        stats.record("verified", "submit", "w1", "f1")
    await asyncio.sleep(0)
    assert repo.written == [] and sum(stats._waiting.values()) == 10
    clock.now += st.FLUSH_SECONDS + 1
    stats.record("verified", "submit", "w1", "f1")  # due: one flush, off the request
    await asyncio.sleep(0.01)
    assert len(repo.written) == 1
    assert sum(repo.written[0].values()) == 11 and stats._waiting == {}


async def test_many_keys_start_a_batch_at_the_threshold():
    stats, repo, _ = make()
    for index in range(st.FLUSH_KEYS):
        stats.record("missing", "submit", "w1", f"form{index}")
    await asyncio.sleep(0.01)
    assert len(repo.written) == 1 and len(repo.written[0]) == st.FLUSH_KEYS


async def test_refusal_codes_are_counted_without_their_prefix_and_no_person():
    stats, repo, _ = make()
    stats.record("captcha_replayed", "submit", "w1", "f1")
    stats.record("rate_limited", "mail")
    await stats.flush()
    keys = set(repo.written[0])
    assert {k[3:] for k in keys} == {("submit", "replayed"), ("mail", "rate_limited")}
    for day, ws, form, purpose, outcome in keys:
        assert len(day) == 10 and ws in ("w1", "") and form in ("f1", "")


async def test_a_failing_database_keeps_the_counts_and_is_bounded():
    stats, repo, _ = make()
    repo.fail = True
    stats.record("verified", "submit", "w1", "f1")
    await stats.flush()
    assert sum(stats._waiting.values()) == 1
    repo.fail = False
    await stats.flush()
    assert sum(repo.written[0].values()) == 1
    # waiting keys never grow past the cap, a known key still counts
    repo.fail = True
    for index in range(st.MAX_KEYS + 50):
        stats.record("missing", "submit", "w1", f"form{index}")
    assert len(stats._waiting) == st.MAX_KEYS
    stats.record("missing", "submit", "w1", "form0")
    assert stats._waiting[next(k for k in stats._waiting if k[2] == "form0")] == 2


async def test_the_sweep_runs_once_a_day_and_zero_keeps_everything():
    stats, repo, clock = make(retention=30)
    stats.record("verified", "submit", "w1", "f1")
    await stats.flush()
    assert len(repo.swept) == 1
    stats.record("verified", "submit", "w1", "f1")
    await stats.flush()
    assert len(repo.swept) == 1
    clock.now += st.SWEEP_SECONDS + 1
    stats.record("verified", "submit", "w1", "f1")
    await stats.flush()
    assert len(repo.swept) == 2
    kept, repo2, _ = make(retention=0)
    kept.record("verified", "submit", "w1", "f1")
    await kept.flush()
    assert repo2.swept == []


async def test_the_summary_reads_what_this_process_has_not_written_yet():
    stats, repo, _ = make()
    stats.record("verified", "submit", "w1", "f1")
    stats.record("verified", "submit", "w1", "f1")
    stats.record("invalid", "submit", "w1", "f1")
    stats.record("captcha_missing", "mail", "w1")
    summary = await stats.summary(form_id="f1")
    assert summary == {
        "days": 30,
        "submit": {"passed": 2, "blocked": 1},
        "mail": {"passed": 0, "blocked": 1},
    }


async def test_nothing_ever_raises_into_a_request():
    stats, _, _ = make()
    stats.record(None, None)  # type: ignore[arg-type]
    stats.record("verified", "submit", object(), object())


def test_a_row_id_is_the_same_for_the_same_key_and_an_object_id():
    key = ("2026-11-14", "w1", "f1", "submit", "verified")
    assert captcha_count_id(key) == captcha_count_id(key)
    assert captcha_count_id(key) != captcha_count_id(key[:4] + ("missing",))
    assert len(captcha_count_id(key)) == 24 and int(captcha_count_id(key), 16) >= 0


@pytest.mark.parametrize("purpose", st.PURPOSES)
async def test_the_summary_has_both_purposes(purpose):
    stats, _, _ = make()
    assert (await stats.summary(workspace_id="w1"))[purpose] == {
        "passed": 0,
        "blocked": 0,
    }


class BlockingRepo(Repo):
    """A repository whose write waits (a slow database), and counts the attempts."""

    def __init__(self):
        super().__init__()
        self.attempts = 0
        self.gate = asyncio.Event()

    async def add_counts(self, counts):
        self.attempts += 1
        await self.gate.wait()
        await super().add_counts(counts)


async def test_one_flush_at_a_time_however_many_requests_arrive_meanwhile():
    clock, repo = Clock(), BlockingRepo()
    stats = st.CaptchaStats(repo, clock, lambda: 395)
    for index in range(st.FLUSH_KEYS):
        stats.record("missing", "submit", "w1", f"form{index}")
    await asyncio.sleep(0.01)
    assert repo.attempts == 1
    # the write is slow: more refused requests, new keys and old, start nothing
    for index in range(st.FLUSH_KEYS, st.FLUSH_KEYS + 300):
        stats.record("missing", "submit", "w1", f"form{index}")
    clock.now += st.FLUSH_SECONDS * 5
    for _ in range(50):
        stats.record("missing", "submit", "w1", "form0")
    await asyncio.sleep(0.01)
    assert repo.attempts == 1
    repo.gate.set()
    await asyncio.sleep(0.02)
    assert len(repo.written) == 1
    # done: the next due flush may start again
    stats.record("missing", "submit", "w1", "form0")
    await asyncio.sleep(0.02)
    assert repo.attempts == 2


async def test_a_failed_write_backs_off_for_flush_seconds_whatever_is_waiting():
    clock, repo = Clock(), Repo()
    stats = st.CaptchaStats(repo, clock, lambda: 395)
    repo.fail = True
    attempts = []
    real = repo.add_counts

    async def counting(counts):
        attempts.append(len(counts))
        await real(counts)

    repo.add_counts = counting  # type: ignore[method-assign]
    for index in range(st.FLUSH_KEYS):
        stats.record("missing", "submit", "w1", f"form{index}")
    await asyncio.sleep(0.01)
    assert len(attempts) == 1
    # 500 or more keys are waiting again after the failure, and every request counts
    # another one: no attempt before the back-off has passed
    for index in range(st.FLUSH_KEYS, st.FLUSH_KEYS + 100):
        stats.record("missing", "submit", "w1", f"form{index}")
        await asyncio.sleep(0)
    clock.now += st.FLUSH_SECONDS - 1
    stats.record("missing", "submit", "w1", "form0")
    await asyncio.sleep(0.01)
    assert len(attempts) == 1
    # after the back-off the next request tries again (and succeeds)
    repo.fail = False
    clock.now += 2
    stats.record("missing", "submit", "w1", "form0")
    await asyncio.sleep(0.02)
    assert len(attempts) == 2 and sum(sum(b.values()) for b in repo.written) >= st.FLUSH_KEYS + 100
    assert stats._waiting == {}
