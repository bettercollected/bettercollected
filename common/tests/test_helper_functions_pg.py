"""The four helper functions, exercised on a live Postgres."""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from common.db import DatabaseSettings, helper_function_ddl, make_engine
from common.db.ddl import drop_helper_function_ddl

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)
SCHEMA = "common_fn_test"


@pytest.fixture
async def conn():
    engine = make_engine(
        DatabaseSettings.from_env(), application_name="common-fn-tests"
    )
    async with engine.begin() as c:
        await c.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        for stmt in helper_function_ddl(SCHEMA):
            await c.execute(text(stmt))
    async with engine.connect() as c:
        yield c
    async with engine.begin() as c:
        for stmt in drop_helper_function_ddl(SCHEMA):
            await c.execute(text(stmt))
        await c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await engine.dispose()


async def call(conn, fn, value_json):
    return (
        await conn.execute(
            text(f"SELECT {SCHEMA}.{fn}(CAST(:v AS jsonb))"), {"v": value_json}
        )
    ).scalar_one_or_none()


async def test_bc_text_unwraps_extended_json_and_scalars(conn):
    assert await call(conn, "bc_text", '"plain"') == "plain"
    assert (
        await call(conn, "bc_text", '{"$oid": "64ae38bcdea80b08417d058a"}')
        == "64ae38bcdea80b08417d058a"
    )
    assert await call(conn, "bc_text", '{"$numberLong": "42"}') == "42"
    assert await call(conn, "bc_text", "7") == "7"
    assert await call(conn, "bc_text", "true") == "true"
    assert await call(conn, "bc_text", "null") is None
    assert await call(conn, "bc_text", '{"nested": 1}') is None
    assert await call(conn, "bc_text", "[1,2]") is None


async def test_bc_ts_handles_every_datetime_shape_the_data_has(conn):
    expected = datetime(2026, 9, 6, 10, 0, 0, 123000, tzinfo=timezone.utc)
    assert (
        await call(conn, "bc_ts", '{"$date": "2026-09-06T10:00:00.123Z"}') == expected
    )
    ms = int(expected.timestamp() * 1000)
    assert (
        await call(conn, "bc_ts", '{"$date": {"$numberLong": "%d"}}' % ms) == expected
    )
    # bare ISO strings (form_responses' bson_encoders): Z, explicit offset, and naive-as-UTC
    assert await call(conn, "bc_ts", '"2026-09-06T10:00:00.123Z"') == expected
    assert await call(conn, "bc_ts", '"2026-09-06T15:45:00.123+05:45"') == expected
    assert await call(conn, "bc_ts", '"2026-09-06T10:00:00.123"') == expected
    assert await call(conn, "bc_ts", '"2026-09-06T10:00:00.123000"') == expected
    assert await call(conn, "bc_ts", '"not a date"') is None
    assert await call(conn, "bc_ts", "null") is None
    assert await call(conn, "bc_ts", "12") is None


async def test_naive_strings_do_not_depend_on_the_session_time_zone(conn):
    await conn.execute(text("SET TIME ZONE 'Asia/Kathmandu'"))
    got = await call(conn, "bc_ts", '"2026-09-06T10:00:00"')
    assert got == datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)


async def test_bc_bool_and_bc_int(conn):
    assert await call(conn, "bc_bool", "true") is True
    assert await call(conn, "bc_bool", '"False"') is False
    assert await call(conn, "bc_bool", '"maybe"') is None
    assert await call(conn, "bc_bool", "1") is None
    assert await call(conn, "bc_int", "3") == 3
    assert await call(conn, "bc_int", "3.9") == 3
    assert (
        await call(conn, "bc_int", '{"$numberLong": "9007199254740993"}')
        == 9007199254740993
    )
    assert await call(conn, "bc_int", '"12"') == 12
    assert await call(conn, "bc_int", '"twelve"') is None


async def test_functions_are_immutable_so_generated_columns_may_use_them(conn):
    rows = (
        await conn.execute(
            text(
                "SELECT p.proname, p.provolatile::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                f"WHERE n.nspname = '{SCHEMA}' ORDER BY 1"
            )
        )
    ).all()
    assert {r[0] for r in rows} == {"bc_bool", "bc_int", "bc_text", "bc_ts"}
    assert all(r[1] == "i" for r in rows)  # 'i' = IMMUTABLE
