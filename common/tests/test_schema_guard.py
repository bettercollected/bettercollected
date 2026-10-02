"""The startup schema guard without a database: the revision comparison, the
flag gating, and the messages an operator sees."""

from __future__ import annotations

from pathlib import Path

import pytest

from common.db import load_flags
from common.db.schema_guard import (
    AUTO_MIGRATE_KEY,
    AuxiliarySchema,
    MigrationTarget,
    RevisionState,
    SchemaNotReady,
    auto_migrate_enabled,
    compare_revisions,
    ensure_schema_ready,
    lock_key,
)

KNOWN = {"0001", "0002", "0003"}


@pytest.mark.parametrize(
    "current, state",
    [
        (("0003",), RevisionState.CURRENT),
        (("0002",), RevisionState.BEHIND),
        (("0001",), RevisionState.BEHIND),
        (("0004",), RevisionState.AHEAD),
        (None, RevisionState.MISSING),
        ((), RevisionState.MISSING),
    ],
)
def test_compare_revisions(current, state):
    check = compare_revisions("app", current, ["0003"], KNOWN, service="backend")
    assert check.state is state
    assert check.ok is (state is RevisionState.CURRENT)


def test_compare_revisions_with_branches():
    heads = ["0003a", "0003b"]
    known = KNOWN | {"0003a", "0003b"}
    assert compare_revisions("app", ["0003b", "0003a"], heads, known).ok
    assert (
        compare_revisions("app", ["0003a"], heads, known).state is RevisionState.BEHIND
    )


def test_messages_name_schema_revisions_and_fix():
    behind = compare_revisions("auth", ["0001"], ["0002"], {"0001", "0002"}, "auth")
    text = behind.message()
    assert "'auth'" in text and "0001" in text and "0002" in text
    assert "alembic -c auth/alembic.ini upgrade head" in text
    assert f"{AUTO_MIGRATE_KEY}=true" in text

    missing = compare_revisions("google", None, ["0002"], {"0001", "0002"}).message()
    assert "never migrated" in missing and f"{AUTO_MIGRATE_KEY}=true" in missing

    ahead = compare_revisions("app", ["0009"], ["0002"], {"0001", "0002"}).message()
    assert "ahead" in ahead and "0009" in ahead


def test_auto_migrate_is_opt_in():
    assert auto_migrate_enabled({}) is False
    assert auto_migrate_enabled({AUTO_MIGRATE_KEY: ""}) is False
    assert auto_migrate_enabled({AUTO_MIGRATE_KEY: "false"}) is False
    assert auto_migrate_enabled({AUTO_MIGRATE_KEY: "true"}) is True
    assert auto_migrate_enabled({AUTO_MIGRATE_KEY: "1"}) is True


def test_lock_keys_are_stable_per_schema_and_fit_bigint():
    assert lock_key("app") == lock_key("app")
    assert len({lock_key(s) for s in ("app", "auth", "google", "jobs")}) == 4
    assert all(-(2**63) <= lock_key(s) < 2**63 for s in ("app", "jobs"))


# -- ensure_schema_ready over a fake revision source and a tiny script dir --------
REVISION = """revision = "{rev}"
down_revision = {down}
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
"""


@pytest.fixture
def target(tmp_path: Path) -> MigrationTarget:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_a.py").write_text(REVISION.format(rev="0001", down="None"))
    (versions / "0002_b.py").write_text(REVISION.format(rev="0002", down='"0001"'))
    return MigrationTarget("app", str(tmp_path / "migrations"), service="backend")


class FakeRevisions:
    def __init__(self, revisions):
        self.revisions = revisions
        self.calls = 0

    async def current_revisions(self, schema):
        self.calls += 1
        return self.revisions


def test_code_revisions(target):
    heads, known = target.code_revisions()
    assert heads == ("0002",)
    assert known == {"0001", "0002"}


async def test_mongo_only_flags_check_nothing(target):
    source = FakeRevisions(None)  # would fail the check if it were consulted
    await ensure_schema_ready(
        load_flags({}),
        None,
        target,
        env={AUTO_MIGRATE_KEY: "true"},
        revision_source=source,
    )
    assert source.calls == 0


@pytest.mark.parametrize(
    "env",
    [
        {"DB_WRITE_MODE": "dual"},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_WRITE_MODE__responses": "dual"},
    ],
)
async def test_postgres_flags_refuse_a_schema_behind(target, env):
    with pytest.raises(SchemaNotReady) as raised:
        await ensure_schema_ready(
            load_flags(env),
            None,
            target,
            env={},
            revision_source=FakeRevisions(("0001",)),
        )
    assert "'app' is behind" in str(raised.value)


async def test_postgres_flags_accept_head(target):
    await ensure_schema_ready(
        load_flags({"DB_WRITE_MODE": "dual"}),
        None,
        target,
        env={},
        revision_source=FakeRevisions(("0002",)),
    )


async def test_jobs_only_flags_skip_the_table_schema(target):
    """Jobs on Postgres touch only the jobs schema; the app schema is not checked."""
    source = FakeRevisions(None)
    aux = AuxiliarySchema(
        name="jobs",
        needed=lambda flags: False,
        present=None,  # type: ignore[arg-type]
        apply=None,  # type: ignore[arg-type]
    )
    await ensure_schema_ready(
        load_flags({"JOBS_BACKEND": "postgres"}),
        None,
        target,
        (aux,),
        env={},
        revision_source=source,
    )
    assert source.calls == 0
