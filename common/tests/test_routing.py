import asyncio

import pytest

from common.db import ReadSource, RoutingError, RoutingRepository, load_flags, write_op


class FakeStore:
    """A repository double: records calls, can fail or stall, returns tagged results."""

    def __init__(self, tag, fail_on=(), slow=()):
        self.tag, self.calls, self.fail_on, self.slow = tag, [], set(fail_on), set(slow)

    async def _go(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        if name in self.slow:
            await asyncio.sleep(5)
        if name in self.fail_on:
            raise RuntimeError(f"{self.tag} {name} failed")
        return f"{self.tag}:{name}"

    async def find(self, key):
        return await self._go("find", key)

    @write_op
    async def save(self, doc):
        return await self._go("save", doc)

    @write_op
    async def delete(self, key):
        return await self._go("delete", key)

    def query(self, key):  # a sync method that returns a query object
        self.calls.append(("query", (key,), {}))
        return f"{self.tag}:query"

    plain_attribute = "value"


def repo(env, mongo=None, postgres=None, **kw):
    return RoutingRepository(
        group="forms", flags=load_flags(env), mongo=mongo, postgres=postgres, **kw
    )


async def test_mongo_only_is_a_pass_through():
    m = FakeStore("mongo")
    r = repo({}, mongo=m)
    assert await r.find("a") == "mongo:find"
    assert await r.save("d") == "mongo:save"
    assert r.query("q") == "mongo:query"
    assert r.plain_attribute == "value"
    assert [c[0] for c in m.calls] == ["find", "save", "query"]


async def test_dual_write_mirrors_writes_to_postgres_and_returns_the_primary_result():
    m, p = FakeStore("mongo"), FakeStore("postgres")
    r = repo({"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p)
    assert await r.save("doc") == "mongo:save"
    assert m.calls == [("save", ("doc",), {})]
    assert p.calls == [("save", ("doc",), {})]
    # reads stay on the read source (mongo) and do not touch postgres without sampling
    assert await r.find("k") == "mongo:find"
    assert len(p.calls) == 1


async def test_mirror_failure_never_reaches_the_caller_and_is_reported():
    seen = []
    m, p = FakeStore("mongo"), FakeStore("postgres", fail_on={"save"})
    r = repo(
        {"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p, on_mirror_failure=seen.append
    )
    assert await r.save("doc") == "mongo:save"
    assert r.metrics.mirror_failures[("forms", "save")] == 1
    assert (
        len(seen) == 1
        and seen[0].method == "save"
        and seen[0].store is ReadSource.POSTGRES
    )
    assert isinstance(seen[0].error, RuntimeError)


async def test_mirror_is_bounded_by_the_timeout():
    m, p = FakeStore("mongo"), FakeStore("postgres", slow={"delete"})
    r = repo({"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p, mirror_timeout_s=0.05)
    result = await asyncio.wait_for(r.delete("k"), timeout=1.0)
    assert result == "mongo:delete"
    assert r.metrics.mirror_failures[("forms", "delete")] == 1


async def test_postgres_primary_dual_writes_postgres_first_and_mirrors_to_mongo():
    m, p = FakeStore("mongo"), FakeStore("postgres")
    r = repo(
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres_primary_dual"},
        mongo=m,
        postgres=p,
    )
    assert await r.save("doc") == "postgres:save"
    assert p.calls == [("save", ("doc",), {})] and m.calls == [("save", ("doc",), {})]
    assert await r.find("k") == "postgres:find"


async def test_shadow_reads_compare_and_report_differences():
    diffs = []
    m, p = FakeStore("mongo"), FakeStore("postgres")
    r = repo(
        {"DB_WRITE_MODE": "dual", "DB_SHADOW_READ_SAMPLE": "1.0"},
        mongo=m,
        postgres=p,
        on_shadow_diff=diffs.append,
    )
    assert await r.find("k") == "mongo:find"  # results are tagged differently -> a diff
    assert r.metrics.shadow_reads[("forms", "find")] == 1
    assert r.metrics.shadow_diffs[("forms", "find")] == 1
    assert diffs[0].method == "find" and diffs[0].other is ReadSource.POSTGRES


async def test_shadow_read_agreement_is_not_a_diff_and_errors_are_swallowed():
    class Same(FakeStore):
        async def find(self, key):
            self.calls.append(("find", (key,), {}))
            return {"id": key}

    m, p = Same("mongo"), Same("postgres")
    r = repo(
        {"DB_WRITE_MODE": "dual", "DB_SHADOW_READ_SAMPLE": "1.0"}, mongo=m, postgres=p
    )
    assert await r.find("k") == {"id": "k"}
    assert r.metrics.shadow_diffs[("forms", "find")] == 0
    broken = FakeStore("postgres", fail_on={"find"})
    r2 = repo(
        {"DB_WRITE_MODE": "dual", "DB_SHADOW_READ_SAMPLE": "1.0"},
        mongo=m,
        postgres=broken,
    )
    assert await r2.find("k") == {"id": "k"}
    assert r2.metrics.shadow_errors[("forms", "find")] == 1


def test_flags_that_need_a_missing_store_fail_at_construction():
    with pytest.raises(RoutingError, match="postgres store"):
        repo({"DB_WRITE_MODE": "dual"}, mongo=FakeStore("mongo"))
    with pytest.raises(RoutingError, match="mongo store"):
        repo(
            {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres_primary_dual"},
            postgres=FakeStore("postgres"),
        )
    with pytest.raises(RoutingError):
        repo({})
    repo(
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        postgres=FakeStore("postgres"),
    )  # mongo gone: fine


async def test_per_group_flags_apply_to_the_repository_group():
    m, p = FakeStore("mongo"), FakeStore("postgres")
    r = RoutingRepository(
        group="forms",
        flags=load_flags({"DB_WRITE_MODE": "dual", "DB_WRITE_MODE__forms": "mongo"}),
        mongo=m,
        postgres=p,
    )
    await r.save("doc")
    assert (
        p.calls == []
    )  # the forms group is mongo-only even though the default is dual


class Doc:
    """Stands in for a Beanie document: has an id and an upserting save()."""

    saved = []

    def __init__(self, id, body):
        self.id, self.body = id, body

    async def save(self):
        Doc.saved.append((self.id, self.body))
        return self


class MintingStore(FakeStore):
    """A repository whose ``create`` mints an id and a token — non-deterministic
    in its arguments, so the mirror must replay the result, not the call."""

    def __init__(self, tag, **kw):
        super().__init__(tag, **kw)
        self.replayed = []
        self.counter = 0

    @write_op(replay=True)
    async def create(self, body):
        await self._go("create", body)
        self.counter += 1
        return Doc(f"{self.tag}-{self.counter}", body)

    @write_op(replay=True)
    async def create_many(self, n):
        await self._go("create_many", n)
        return [Doc(f"{self.tag}-{i}", i) for i in range(n)]

    @write_op(replay=True)
    async def touch(self, key):
        await self._go("touch", key)
        return None  # replay-marked but nothing persisted to hand over

    async def replay_write(self, documents):
        self.replayed.append([d.id for d in documents])


class BeanieLikeStore(MintingStore):
    replay_write = None  # a Mongo repository: no hook, documents save() themselves


async def test_replayed_write_stores_the_primary_result_on_the_mirror():
    m, p = MintingStore("mongo"), MintingStore("postgres")
    r = repo({"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p)
    doc = await r.create({"a": 1})
    assert doc.id == "mongo-1"
    assert [c[0] for c in p.calls] == []  # the call itself was not re-executed
    assert p.replayed == [["mongo-1"]]
    assert (await r.create_many(2))[1].id == "mongo-1"
    assert p.replayed[-1] == ["mongo-0", "mongo-1"]


async def test_replay_falls_back_to_re_execution_when_nothing_was_persisted():
    m, p = MintingStore("mongo"), MintingStore("postgres")
    r = repo({"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p)
    await r.touch("k")
    assert [c[0] for c in p.calls] == ["touch"]
    assert p.replayed == []


async def test_replay_onto_a_beanie_repository_saves_each_document():
    Doc.saved.clear()
    m, p = BeanieLikeStore("mongo"), MintingStore("postgres")
    r = repo({"DB_WRITE_MODE": "postgres_primary_dual"}, mongo=m, postgres=p)
    doc = await r.create({"b": 2})
    assert doc.id == "postgres-1"
    assert Doc.saved == [("postgres-1", {"b": 2})]
    assert [c[0] for c in m.calls] == []


async def test_replay_failure_is_reported_with_the_documents():
    class Broken(MintingStore):
        async def replay_write(self, documents):
            raise RuntimeError("down")

    failures = []
    m, p = MintingStore("mongo"), Broken("postgres")
    r = repo(
        {"DB_WRITE_MODE": "dual"},
        mongo=m,
        postgres=p,
        on_mirror_failure=failures.append,
    )
    doc = await r.create({"c": 3})
    assert doc.id == "mongo-1"
    assert len(failures) == 1
    assert [d.id for d in failures[0].documents] == ["mongo-1"]
    assert failures[0].method == "create"


def test_write_op_marks_replay():
    from common.db import is_replayed, is_write_op

    assert is_write_op(MintingStore.create) and is_replayed(MintingStore.create)
    assert is_write_op(FakeStore.save) and not is_replayed(FakeStore.save)
    assert not is_write_op(FakeStore.find)


async def test_write_result_replays_the_persisted_documents_and_returns_the_value():
    from common.db import WriteResult

    class Store(MintingStore):
        @write_op(replay=True)
        async def rotate(self, key):
            await self._go("rotate", key)
            return WriteResult(
                value={"plain": key}, documents=[Doc(f"{self.tag}-enc", "ciphertext")]
            )

    m, p = Store("mongo"), Store("postgres")
    r = repo({"DB_WRITE_MODE": "dual"}, mongo=m, postgres=p)
    assert await r.rotate("k") == {"plain": "k"}  # the caller never sees the wrapper
    assert p.replayed == [["mongo-enc"]]  # the mirror stores the encrypted copy
    assert [c[0] for c in p.calls] == []


def test_outbox_row_ids_redact_addresses_and_keep_ids():
    from common.db import MirrorFailure, ReadSource, redact
    from common.db.runtime import failure_ids

    assert redact("6a9d7c30c3a01cadfd948543") == "6a9d7c30c3a01cadfd948543"
    assert redact("someone@example.com").startswith("email:") and "@" not in redact(
        "a@b.c"
    )
    failure = MirrorFailure(
        "responses",
        "ResponderGroupsRepository",
        "add_emails_to_group",
        ReadSource.POSTGRES,
        ("6a9d7c30c3a01cadfd948543", ["a@x.com", "b@x.com"]),
        {},
        RuntimeError("down"),
    )
    ids = failure_ids(failure)
    assert ids.startswith("6a9d7c30c3a01cadfd948543,email:") and "@" not in ids
