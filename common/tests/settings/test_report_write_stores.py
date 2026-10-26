"""The heartbeat carries the data stores the service writes (admin revision
0018), and still reports to a store from before that revision (rolling deploy)."""

import pytest

from common.settings.loader.source import PgSnapshotSource
from common.settings.snapshot import ServiceState


class UndefinedFunction(Exception):
    sqlstate = "42883"


class FakeConnection:
    def __init__(self, *, has_new: bool, fail=None):
        self.has_new, self.fail, self.calls = has_new, fail, []

    async def execute(self, sql, *args):
        if self.fail is not None:
            raise self.fail
        self.calls.append((sql, args))
        if sql.count("$") == 7 and not self.has_new:
            raise UndefinedFunction("function settings.report_state(...) does not exist")

    async def close(self):
        pass


def source_with(conn):
    source = PgSnapshotSource("postgresql://u@h/db", "backend")

    async def connect():
        return conn

    source._connect = connect
    return source


STATE = ServiceState(service="backend", revision_applied=3, keyset_fp="ab", write_stores="postgres")


def test_the_report_carries_the_write_stores():
    conn = FakeConnection(has_new=True)
    source_with(conn).report_state("backend:h", STATE)
    ((sql, args),) = conn.calls
    assert "$7" in sql and args[-1] == "postgres"


def test_a_store_from_before_0018_gets_the_old_report():
    conn = FakeConnection(has_new=False)
    source_with(conn).report_state("backend:h", STATE)
    assert [sql.count("$") for sql, _ in conn.calls] == [7, 6]
    assert conn.calls[1][1] == ("backend:h", 3, [], [], False, "ab")


def test_other_errors_are_not_swallowed():
    class Denied(Exception):
        sqlstate = "42501"

    with pytest.raises(Exception):
        source_with(FakeConnection(has_new=True, fail=Denied())).report_state("backend:h", STATE)


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_WRITE_MODE": "postgres"},
        {"DB_WRITE_MODE": "dual"},  # a stale service-wide setting the backend ignores
        {"DB_WRITE_MODE": "mongo", "DB_WRITE_MODE__RESPONSES": "dual"},
        {"DB_WRITE_MODE": "bogus"},
    ],
)
def test_a_41_process_reports_postgres_whatever_its_environment_says(env):
    """Nothing writes Mongo any more, so a setting left from the cutover (or an
    unset one, which used to mean mongo) cannot make the admin keyset task see a
    consumer that writes it."""
    from common.settings.write_stores import write_stores_report

    assert write_stores_report(env) == "postgres"
