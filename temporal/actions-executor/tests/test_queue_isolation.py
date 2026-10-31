"""The executor starts only where the database keeps its role to its own queue."""

import asyncio

import pytest

from utilities import queue_isolation


class Connector:
    def __init__(self, isolated):
        self.isolated = isolated
        self.asked = []

    async def execute_query_one_async(self, query):
        self.asked.append(query)
        return {"exists": self.isolated}


def test_it_starts_when_the_policy_is_in_place():
    connector = Connector(True)
    asyncio.run(queue_isolation.require_isolated_queue(connector))
    assert connector.asked == [queue_isolation.ISOLATION_SQL]


def test_it_refuses_to_start_without_the_policy_and_says_how_to_apply_it():
    with pytest.raises(SystemExit) as stopped:
        asyncio.run(queue_isolation.require_isolated_queue(Connector(False)))
    message = str(stopped.value)
    assert "backend.jobs.schema" in message and queue_isolation.POLICY in message


def test_the_check_asks_only_the_catalog_and_changes_nothing():
    import re

    # outside the quoted names (a privilege list reads 'INSERT,UPDATE,DELETE')
    sql = re.sub(r"'[^']*'", "''", queue_isolation.ISOLATION_SQL).upper()
    assert sql.lstrip().startswith("SELECT")
    for word in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"):
        assert not re.search(rf"\b{word}\b", sql), word


def test_the_check_names_the_definer_role_and_its_search_path():
    sql = queue_isolation.isolation_sql("bc_other_def")
    assert "'bc_other_def'" in sql
    # pg_temp last: the temporary schema is searched first otherwise
    assert queue_isolation.DEFINER_SEARCH_PATH.endswith("pg_temp")
    assert queue_isolation.DEFINER_SEARCH_PATH in sql
