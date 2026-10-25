"""google.purge_user_credentials (revision 0005) on a database laid out like
production.

Each test module run creates a throw-away database (its name contains "test")
on the server DATABASE_URL points at, runs postgres/init/01-roles-schemas.sh's
SQL in it with uniquely suffixed role names (roles are server-global), migrates
the google schema as its own role and then exercises the function as the
backend's role and as others. Database and roles are dropped afterwards.
Skipped when DATABASE_URL is unset.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = [
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"),
    pytest.mark.asyncio,
]

SERVICE_DIR = Path(__file__).resolve().parents[2]
INIT_SCRIPT = SERVICE_DIR.parents[1] / "postgres" / "init" / "01-roles-schemas.sh"
ROLES = ("app", "auth", "google", "jobs_exec")
COLLECTION = "Oauth2CredentialDocument"


def _url(base_url: str, database: str, user: str | None = None, pw: str = "") -> str:
    base, _, _ = base_url.rpartition("/")
    if user is not None:
        scheme, _, rest = base.partition("://")
        base = f"{scheme}://{user}:{pw}@{rest.rpartition('@')[2]}"
    return f"{base}/{database}"


def _init_sql(database: str, suffix: str, passwords: dict) -> str:
    sql = INIT_SCRIPT.read_text().split("<<'SQL'\n", 1)[1].rsplit("\nSQL", 1)[0]
    sql = re.sub(r"^\\getenv .*\n", "", sql, flags=re.M)
    sql = re.sub(r"\bbc_(app|auth|google|jobs_exec)\b", rf"bc_\1_{suffix}", sql)
    for role, var in zip(ROLES, ("app_pw", "auth_pw", "google_pw", "jobs_pw")):
        sql = sql.replace(f":'{var}'", f"'{passwords[role]}'")
    return sql.replace(':"DBNAME"', f'"{database}"')


async def _execute(url: str, statement: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(statement)
    finally:
        await engine.dispose()


async def _scalar(url: str, statement: str, **params):
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            return (await conn.execute(text(statement), params)).scalar()
    finally:
        await engine.dispose()


def _alembic(url: str, action: str, revision: str) -> None:
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    getattr(command, action)(config, revision)


class Stack:
    def __init__(self, admin: str, name: str, suffix: str, passwords: dict):
        self.admin, self.name, self.suffix, self.passwords = admin, name, suffix, passwords

    def role(self, role: str) -> str:
        return f"bc_{role}_{self.suffix}"

    def url(self, role: str) -> str:
        return _url(self.admin, self.name, self.role(role), self.passwords[role])


@pytest_asyncio.fixture
async def stack():
    admin = os.environ["DATABASE_URL"]
    name = f"bc_purge_test_{uuid.uuid4().hex[:10]}"
    suffix = f"t{uuid.uuid4().hex[:8]}"
    passwords = {role: secrets.token_hex(12) for role in ROLES}
    await _execute(_url(admin, "postgres"), f'CREATE DATABASE "{name}"')
    try:
        await _execute(_url(admin, name), _init_sql(name, suffix, passwords))
        stack = Stack(admin, name, suffix, passwords)
        # migrated as the google service's own role, as deploy.sh does
        await asyncio.to_thread(_alembic, stack.url("google"), "upgrade", "head")
        yield stack
    finally:
        await _execute(_url(admin, "postgres"), f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        for role in ROLES:
            await _execute(_url(admin, "postgres"), f'DROP ROLE IF EXISTS "bc_{role}_{suffix}"')


def _oid() -> str:
    return uuid.uuid4().hex[:24]


async def _add_credential(stack: Stack, user_id: str, email: str) -> str:
    row_id = _oid()
    doc = (
        '{"_id": {"$oid": "%s"}, "user_id": "%s", "email": "%s", "provider": "google",'
        ' "credentials": {"token": "t", "refresh_token": "r"}}' % (row_id, user_id, email)
    )
    await _scalar(
        stack.url("google"),
        "INSERT INTO google.oauth_credentials (id, doc, _bc_checksum) "
        "VALUES (:id, CAST(:doc AS jsonb), 'x') RETURNING id",
        id=row_id,
        doc=doc,
    )
    return row_id


async def _remaining(stack: Stack) -> set:
    engine = create_async_engine(stack.url("google"), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(text("SELECT user_id, email FROM google.oauth_credentials"))
            return {(r.user_id, r.email) for r in rows}
    finally:
        await engine.dispose()


async def test_the_backend_role_purges_only_rows_matching_both_user_and_email(stack):
    gone = await _add_credential(stack, "u1", "a@example.com")
    await _add_credential(stack, "u1", "other@example.com")  # same user, other email
    await _add_credential(stack, "u2", "a@example.com")  # other user, same email

    deleted = await _scalar(
        stack.url("app"),
        "SELECT google.purge_user_credentials(:u, :e)",
        u="u1",
        e="a@example.com",
    )

    assert deleted == 1
    assert await _remaining(stack) == {
        ("u1", "other@example.com"),
        ("u2", "a@example.com"),
    }
    # the delete is tombstoned like every other delete in this schema
    stone = await _scalar(
        stack.url("google"),
        "SELECT count(*) FROM google.deletion_tombstones WHERE collection = :c AND row_id = :r",
        c=COLLECTION,
        r=gone,
    )
    assert stone == 1


@pytest.mark.parametrize("user_id,email", [("", "a@example.com"), ("u1", ""), (None, None)])
async def test_blank_arguments_delete_nothing(stack, user_id, email):
    await _add_credential(stack, "u1", "a@example.com")
    deleted = await _scalar(
        stack.url("app"), "SELECT google.purge_user_credentials(:u, :e)", u=user_id, e=email
    )
    assert deleted == 0
    assert await _remaining(stack) == {("u1", "a@example.com")}


@pytest.mark.parametrize("role", ["auth", "jobs_exec"])
async def test_other_roles_cannot_execute_it(stack, role):
    await _add_credential(stack, "u1", "a@example.com")
    with pytest.raises(DBAPIError) as raised:
        await _scalar(
            stack.url(role),
            "SELECT google.purge_user_credentials(:u, :e)",
            u="u1",
            e="a@example.com",
        )
    assert "permission denied" in str(raised.value).lower()
    assert await _remaining(stack) == {("u1", "a@example.com")}


async def test_the_backend_role_gets_no_table_access(stack):
    await _add_credential(stack, "u1", "a@example.com")
    for statement in (
        "SELECT count(*) FROM google.oauth_credentials",
        "DELETE FROM google.oauth_credentials",
    ):
        with pytest.raises(DBAPIError) as raised:
            await _scalar(stack.url("app"), statement)
        assert "permission denied" in str(raised.value).lower()


async def test_definer_owner_search_path_and_grants(stack):
    engine = create_async_engine(stack.url("google"), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner, "
                        "has_function_privilege('public', p.oid, 'EXECUTE') AS public_exec "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                        "WHERE n.nspname = 'google' AND p.proname = 'purge_user_credentials'"
                    )
                )
            ).one()
    finally:
        await engine.dispose()
    assert row.prosecdef is True
    assert row.proconfig == ["search_path=pg_catalog, pg_temp"]
    assert row.owner == stack.role("google")
    assert row.public_exec is False


async def test_the_downgrade_drops_it_and_the_upgrade_restores_it(stack):
    exists = "SELECT to_regprocedure('google.purge_user_credentials(text, text)') IS NOT NULL"
    assert await _scalar(stack.url("google"), exists) is True

    await asyncio.to_thread(_alembic, stack.url("google"), "downgrade", "0004")
    assert await _scalar(stack.url("google"), exists) is False
    usage = "SELECT has_schema_privilege(:r, 'google', 'USAGE')"
    assert await _scalar(stack.url("google"), usage, r=stack.role("app")) is False

    await asyncio.to_thread(_alembic, stack.url("google"), "upgrade", "head")
    assert await _scalar(stack.url("google"), exists) is True
    assert await _scalar(stack.url("google"), usage, r=stack.role("app")) is True
