"""``resolve-outbox``: the per-row rule, the entry parsing, the repository map
and the CLI's guards (no database: the store-driven parts run in the backend
suite, tests/app/migrate/test_resolve_outbox.py)."""

import datetime as dt
import os
import stat
from types import SimpleNamespace

import pytest
from bson import ObjectId
from sqlalchemy import Column, MetaData, Table, Text

from common.db.base import SOURCE_APP, SOURCE_BACKFILL
from common.db.canonical import canonical_document, checksum
from common.db.migrate.cli import main, open_ids_file
from common.db.migrate.engine import Target
from common.db.migrate.outbox import (
    DELETE_PENDING,
    EXPIRED_ONE_SIDE,
    GROUP_DIFFERS,
    MISSING_IN_MONGO,
    MISSING_IN_POSTGRES,
    OLDER_IN_MONGO,
    SUPERSEDED,
    Entry,
    GroupScan,
    Plan,
    decide,
    mongo_holds,
    object_ids,
    repository_group,
    routed_repository_groups,
)
from common.db.routing import RoutingRepository

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
T1 = T0 + dt.timedelta(minutes=1)
T2 = T0 + dt.timedelta(minutes=2)
NOW = T0 + dt.timedelta(days=1)


def document(updated_at=T0, **extra):
    return {
        "_id": ObjectId("0123456789abcdef01234567"),
        "updated_at": updated_at,
        **extra,
    }


def row(doc, *, updated_at=T1, source=SOURCE_APP):
    canonical = canonical_document(doc)
    return (checksum(canonical), updated_at, source, canonical)


def holds(row_, doc, deleted_at=None, since=None, ttl=None):
    return mongo_holds(row_, doc, deleted_at, ttl, NOW, since)


# -- the per-row rule: proof only -------------------------------------------------
def test_the_same_version_in_mongo_is_proof():
    doc = document(name="a")
    assert holds(row(doc), dict(doc)) is None


def test_a_row_missing_in_mongo_is_kept():
    assert holds(row(document(name="a")), None) == MISSING_IN_MONGO


def test_a_later_mongo_copy_is_superseded_never_proof():
    """A Mongo save built from a copy that never got the Postgres write stamps
    a later time too: a later stamp is classed ``superseded`` (the opt-in),
    never resolved by default."""
    pg = row(document(name="written in postgres"), updated_at=T1)
    assert holds(pg, document(T2, name="later in mongo"), since=T1) == SUPERSEDED
    # older than the Postgres row, or the same time
    assert holds(pg, document(T0, name="x"), since=T0) == OLDER_IN_MONGO
    assert holds(pg, document(T1, name="x")) == OLDER_IN_MONGO
    # later than the row, but older than the entry's time
    assert (
        holds(pg, document(T2, name="x"), since=T2 + dt.timedelta(seconds=1))
        == OLDER_IN_MONGO
    )


def test_a_missing_timestamp_is_never_superseded():
    pg = row(document(name="a"), updated_at=None)
    assert holds(pg, document(T2, name="b")) == OLDER_IN_MONGO
    pg = row(document(name="a"))
    assert holds(pg, {"_id": ObjectId(), "name": "b"}) == OLDER_IN_MONGO


def test_a_row_copied_from_mongo_holds_no_postgres_write():
    pg = row(document(name="a"), source=SOURCE_BACKFILL)
    assert holds(pg, None) is None
    assert holds(pg, document(T0, name="other")) is None


def test_absent_in_both_stores_is_proof():
    assert holds(None, None) is None


def test_a_mongo_only_copy_is_kept():
    """Postgres lacks a copy Mongo holds: without a tombstone it is no proof
    of anything (an unnamed delete would look the same)."""
    assert holds(None, document(T0)) == MISSING_IN_POSTGRES
    assert holds(None, document(T0), deleted_at=T1) == DELETE_PENDING
    # written again after the delete: still a copy Postgres lacks
    assert holds(None, document(T2), deleted_at=T1) == MISSING_IN_POSTGRES


def test_a_row_deleted_since_needs_no_mongo_copy():
    pg = row(document(name="a"), updated_at=T0)
    assert holds(pg, None, deleted_at=T1) is None
    assert holds(pg, document(T0, name="old"), deleted_at=T1) == DELETE_PENDING
    # a row written after the tombstone is a live write Mongo lacks
    assert holds(row(document(name="a"), updated_at=T2), None, deleted_at=T1) == (
        MISSING_IN_MONGO
    )


def test_ttl_counts_only_when_both_sides_are_expired_or_absent():
    ttl = ("expires_at", 60)
    gone = T0 - dt.timedelta(days=1)
    live_at = NOW + dt.timedelta(days=1)
    expired_row = row(document(name="a", expires_at=gone))
    assert holds(expired_row, None, ttl=ttl) is None
    assert holds(expired_row, document(T2, name="b", expires_at=gone), ttl=ttl) is None
    # expired on one side only: kept
    live_row = row(document(name="a", expires_at=live_at))
    assert holds(live_row, document(T2, expires_at=gone), ttl=ttl) == EXPIRED_ONE_SIDE
    assert (
        holds(expired_row, document(T2, name="b", expires_at=live_at), ttl=ttl)
        == EXPIRED_ONE_SIDE
    )


def test_an_entry_is_resolved_on_proof_or_with_the_opt_in_only():
    entry = lambda rows=(): Entry(  # noqa: E731
        1, "R", [], T1, group="g", rows=list(rows)
    )
    clean = GroupScan()
    e = entry()
    decide(e, clean, accept_superseded=False)
    assert e.reason is None and not e.superseded
    named = [{"collection": "c", "id": "x", "reason": SUPERSEDED}]
    e = entry(named)
    decide(e, clean, accept_superseded=False)
    assert e.reason == SUPERSEDED
    e = entry(named)
    decide(e, clean, accept_superseded=True)
    assert e.reason is None and e.superseded
    # an unnamed superseded row: only when its Mongo copy is not older than the entry
    e = entry()
    decide(e, GroupScan(superseded=1, superseded_since=T2), accept_superseded=True)
    assert e.reason is None and e.superseded
    e = entry()
    decide(e, GroupScan(superseded=1, superseded_since=T0), accept_superseded=True)
    assert e.reason == GROUP_DIFFERS
    # anything not proven and not superseded keeps it, flag or not
    e = entry()
    decide(e, GroupScan(differing=1), accept_superseded=True)
    assert e.reason == GROUP_DIFFERS
    e = entry([{"collection": "c", "id": "x", "reason": MISSING_IN_MONGO}] + named)
    decide(e, clean, accept_superseded=True)
    assert e.reason == MISSING_IN_MONGO


# -- entries --------------------------------------------------------------------
def test_object_ids_keeps_only_object_ids_once_each():
    a, b = "0123456789abcdef01234567", "89abcdef0123456789abcdef"
    assert object_ids(f"{a},slug,email:abc123,{b},{a}") == [a, b]
    assert object_ids("-") == []
    assert object_ids(None) == []
    assert object_ids("0123456789ABCDEF01234567") == []  # not an ObjectId's form


def _table(name):
    return Table(name, MetaData(), Column("id", Text, primary_key=True))


def _target(groups):
    return Target(
        schema="app",
        tables={c: _table(c) for c in groups},
        progress=_table("migration_progress"),
        mongo_uri="mongodb://unused",
        mongo_db="unused",
        database_url="postgresql+asyncpg://unused/unused",
        service="backend",
        groups=groups,
    )


def test_an_unknown_repository_has_a_group_only_in_a_single_group_service():
    many = _target({"workspaces": "identity", "forms": "forms"})
    assert (
        repository_group(many, "FormRepository", {"FormRepository": "forms"}) == "forms"
    )
    assert repository_group(many, "Unknown", {}) is None
    single = _target({"users": "auth"})
    assert repository_group(single, "UserRepository", {}) == "auth"


def test_the_repository_map_reads_the_routed_repositories():
    class MongoRepo:
        ...

    class TwinRepo:
        ...

    def postgres_repository(*args):  # stands in for common.db.runtime's
        ...

    class Provider(SimpleNamespace):
        pass

    def routed(group, mongo=None, postgres=None):
        kwargs = {"group": group}
        if mongo is not None:
            kwargs["mongo"] = Provider(provides=mongo, args=(), kwargs={})
        if postgres is not None:
            kwargs["postgres"] = Provider(
                provides=postgres_repository, args=(postgres, "sessions"), kwargs={}
            )
        return Provider(provides=RoutingRepository, args=(), kwargs=kwargs)

    class Clash:
        ...

    container = SimpleNamespace(
        providers={
            "a": routed("forms", mongo=MongoRepo, postgres=TwinRepo),
            "b": routed("refdata", postgres=TwinRepo),
            "c": routed("forms", mongo=Clash),
            "d": routed("ai", mongo=Clash),
            "other": Provider(provides=dict, args=(), kwargs={"group": "x"}),
        }
    )
    assert routed_repository_groups(container) == {
        "MongoRepo": "forms",
        "TwinRepo": "refdata",
    }


def test_the_summary_holds_counts_only():
    secret_id = "0123456789abcdef01234567"
    plan = Plan(groups=["identity"], open=3, out_of_scope=1)
    plan.entries = [
        Entry(1, "SessionRepository", [secret_id], T0, group="identity"),
        Entry(
            2,
            "SessionRepository",
            [secret_id],
            T0,
            group="identity",
            reason=MISSING_IN_MONGO,
            rows=[
                {"collection": "sessions", "id": secret_id, "reason": MISSING_IN_MONGO}
            ],
        ),
    ]
    plan.scans = {
        "identity": GroupScan(
            compared=4,
            listed=[{"collection": "sessions", "id": secret_id, "reason": "x"}],
        )
    }
    summary = plan.summary()
    assert secret_id not in repr(summary)
    assert summary["resolvable"] == 1 and summary["in_scope"] == 2
    assert summary["kept"][MISSING_IN_MONGO] == 1
    assert summary["groups"]["identity"] == {
        "entries": 2,
        "resolvable": 1,
        "rows_compared": 4,
        "rows_differing": 0,
        "rows_superseded": 0,
    }
    assert plan.resolvable == [1]
    assert secret_id in repr(plan.details())


# -- the CLI's guards -----------------------------------------------------------
def test_the_ids_file_is_new_and_private(tmp_path):
    path = tmp_path / "ids.json"
    with open_ids_file(str(path)) as handle:
        handle.write("{}")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    with pytest.raises(FileExistsError):
        open_ids_file(str(path))


def test_a_symlink_at_the_ids_file_path_is_refused(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep me")
    link = tmp_path / "ids.json"
    link.symlink_to(victim)
    with pytest.raises(FileExistsError):
        open_ids_file(str(link))
    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "nowhere")
    with pytest.raises(FileExistsError):
        open_ids_file(str(dangling))
    assert not (tmp_path / "nowhere").exists()
    assert victim.read_text() == "keep me"
    target = _target({"workspaces": "identity"})
    for path in (link, dangling):
        with pytest.raises(SystemExit) as exc:
            main(["resolve-outbox", "--ids-file", str(path)], target, prog="m", env={})
        assert exc.value.code == 2


def test_the_cli_refuses_collections_and_an_existing_ids_file(tmp_path, capsys):
    target = _target({"workspaces": "identity", "forms": "forms"})
    with pytest.raises(SystemExit) as exc:
        main(["--collections", "forms", "resolve-outbox"], target, prog="m", env={})
    assert exc.value.code == 2
    assert "--group" in capsys.readouterr().err
    existing = tmp_path / "ids.json"
    existing.write_text("keep me")
    with pytest.raises(SystemExit) as exc:
        main(["resolve-outbox", "--ids-file", str(existing)], target, prog="m", env={})
    assert exc.value.code == 2
    assert existing.read_text() == "keep me"
    with pytest.raises(SystemExit) as exc:
        main(["--group", "nope", "resolve-outbox"], target, prog="m", env={})
    assert exc.value.code == 2
