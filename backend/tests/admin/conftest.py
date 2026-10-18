"""Throw-away Postgres for the admin service's tests.

A session-scoped template database is laid out like production: the init
script's schemas and roles, then ``postgres/ensure-admin-roles.sh``'s SQL, then
the admin migrations run as the migration role. Each test gets a copy
(``CREATE DATABASE ... TEMPLATE``). Role names carry a random suffix because
roles are server-global; the migrations learn the runtime role's name from
``ADMIN_DB_RUNTIME_ROLE``. Database names contain "test" (the suite's guard),
and everything is dropped afterwards. Skipped when DATABASE_URL is unset.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.config import MASTER_KEY_KEY
from backend.admin.db import MIGRATIONS
from common.db.engine import normalise_url
from common.db.schema_guard import upgrade_schema
from tests.app.db.test_auto_migrate import _execute, _with_database, init_sql

ROOT = Path(__file__).resolve().parents[3]
ROLES_SCRIPT = ROOT / "postgres" / "ensure-admin-roles.sh"
INIT_ROLES = ("app", "auth", "google", "jobs_exec")
# the settings store's reader roles, see backend.admin.migration_support
# (READER_SERVICES); "tasks" is the task runner's role, created by the roles script
READER_ROLES = ("app", "auth", "google", "tasks")
MASTER_KEY = base64.b64encode(bytes(range(48))).decode()

needs_postgres = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (start app-postgres from docker-compose.local.yml)",
)


def roles_sql(
    suffix: str,
    admin_pw: str,
    mig_pw: str,
    tasks_pw: str = "unused-tasks-pw",
    tasks_data_app_pw: str = "unused-tasks-data-app-pw",
    tasks_data_google_pw: str = "unused-tasks-data-google-pw",
) -> str:
    """The roles script's SQL with psql variables bound and role names suffixed."""
    script = ROLES_SCRIPT.read_text()
    sql = script.split("<<'SQL'\n", 1)[1].rsplit("\nSQL", 1)[0]
    sql = re.sub(r"\bbc_admin_mig\b", f"bc_admin_mig_{suffix}", sql)
    sql = re.sub(r"\bbc_admin_counts\b", f"bc_admin_counts_{suffix}", sql)
    sql = re.sub(r"\bbc_admin\b", f"bc_admin_{suffix}", sql)
    sql = re.sub(r"\bbc_(app|auth|google|tasks_data_app|tasks_data_google|tasks|jobs_exec)\b", rf"bc_\1_{suffix}", sql)
    return (
        sql.replace(":'admin_pw'", f"'{admin_pw}'")
        .replace(":'mig_pw'", f"'{mig_pw}'")
        .replace(":'tasks_pw'", f"'{tasks_pw}'")
        .replace(":'tasks_data_app_pw'", f"'{tasks_data_app_pw}'")
        .replace(":'tasks_data_google_pw'", f"'{tasks_data_google_pw}'")
    )


# The suite-wide autouse fixtures (Mongo cleaning, the app's rate-limit clock,
# mirror-failure checks) need the whole application. Nothing here does, so they
# are replaced with no-ops for every test in this directory, database or not.
@pytest.fixture(autouse=True)
def _clean_db():
    yield


@pytest.fixture(autouse=True)
def rate_limit_clock():
    yield {}


@pytest.fixture(autouse=True)
def no_silent_mirror_failures():
    yield


@pytest.fixture(autouse=True)
def master_key(monkeypatch):
    monkeypatch.setenv(MASTER_KEY_KEY, MASTER_KEY)
    return MASTER_KEY


@dataclass
class Server:
    admin_url: str  # the suite's superuser URL (any database)
    suffix: str
    admin_pw: str
    mig_pw: str
    reader_pw: str
    template: str  # bootstrapped and migrated
    boot: str  # bootstrapped only

    @property
    def runtime_role(self) -> str:
        return f"bc_admin_{self.suffix}"

    @property
    def owner_role(self) -> str:
        return f"bc_admin_mig_{self.suffix}"

    @property
    def tasks_role(self) -> str:
        return self.reader_role("tasks")

    @property
    def tasks_pw(self) -> str:
        # the runner role is also a settings reader: one password for all readers
        return self.reader_pw

    def reader_role(self, logical: str) -> str:
        return f"bc_{logical}_{self.suffix}"

    def url(self, database: str, role: str = "superuser") -> str:
        if role.startswith("reader:"):
            return _with_database(
                self.admin_url,
                database,
                self.reader_role(role.split(":", 1)[1]),
                self.reader_pw,
            )
        if role == "runtime":
            return _with_database(
                self.admin_url, database, self.runtime_role, self.admin_pw
            )
        if role == "data_app":
            return _with_database(self.admin_url, database, self.data_app_role, self.data_app_pw)
        if role == "data_google":
            return _with_database(
                self.admin_url, database, self.data_google_role, self.data_google_pw
            )
        if role == "owner":
            return _with_database(
                self.admin_url, database, self.owner_role, self.mig_pw
            )
        return _with_database(self.admin_url, database)

    async def create_database(self, *, template: str | None = None) -> str:
        name = f"bc_admin_test_{uuid.uuid4().hex[:10]}"
        postgres = _with_database(self.admin_url, "postgres")
        if template:
            await _create_from_template(postgres, name, template)
        else:
            await _execute(postgres, f'CREATE DATABASE "{name}"')
        self.created.append(name)
        return name

    created: list = None  # set in the fixture
    data_app_pw: str = ""  # the task runner's data roles, set in the fixture
    data_google_pw: str = ""

    @property
    def data_app_role(self) -> str:
        return f"bc_tasks_data_app_{self.suffix}"

    @property
    def data_google_role(self) -> str:
        return f"bc_tasks_data_google_{self.suffix}"


async def _create_from_template(postgres_url: str, name: str, template: str) -> None:
    """``CREATE DATABASE name TEMPLATE template``, retried while the template still
    has a lingering connection (Postgres refuses to copy a database that is in
    use; the previous connection's backend can take a moment to go away,
    especially with several xdist workers sharing the server)."""
    last = None
    for _ in range(40):
        try:
            await _execute(postgres_url, f'CREATE DATABASE "{name}" TEMPLATE "{template}"')
            return
        except asyncpg.exceptions.ObjectInUseError as exc:
            last = exc
            await asyncio.sleep(0.25)
    raise last


async def _bootstrap(server: Server, database: str) -> None:
    """Init script + roles script SQL in ``database``."""
    init_passwords = {role: secrets.token_hex(12) for role in INIT_ROLES}
    await _execute(
        server.url(database), init_sql(database, server.suffix, init_passwords)
    )
    # bc_tasks is created by the roles script itself (the runner's login role)
    await _execute(
        server.url(database),
        roles_sql(
            server.suffix,
            server.admin_pw,
            server.mig_pw,
            server.tasks_pw,
            server.data_app_pw,
            server.data_google_pw,
        ),
    )
    for logical in READER_ROLES:
        await _execute(
            server.url(database),
            f"ALTER ROLE \"{server.reader_role(logical)}\" PASSWORD '{server.reader_pw}'",
        )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def server():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    admin_url = normalise_url(os.environ["DATABASE_URL"])
    suffix = f"t{uuid.uuid4().hex[:8]}"
    boot = f"bc_admin_test_boot_{uuid.uuid4().hex[:8]}"
    template = f"bc_admin_test_tpl_{uuid.uuid4().hex[:8]}"
    srv = Server(
        admin_url,
        suffix,
        secrets.token_hex(12),
        secrets.token_hex(12),
        secrets.token_hex(12),
        template,
        boot,
    )
    srv.created = [template, boot]
    srv.data_app_pw = secrets.token_hex(12)
    srv.data_google_pw = secrets.token_hex(12)
    role_vars = {
        "ADMIN_DB_RUNTIME_ROLE": srv.runtime_role,
        **{f"ADMIN_DB_ROLE_{r.upper()}": srv.reader_role(r) for r in READER_ROLES},
    }
    previous = {k: os.environ.get(k) for k in role_vars}
    os.environ.update(role_vars)
    postgres = _with_database(admin_url, "postgres")
    await _execute(postgres, f'CREATE DATABASE "{boot}"')
    try:
        await _bootstrap(srv, boot)
        await _create_from_template(postgres, template, boot)
        await upgrade_schema(srv.url(template, "owner"), MIGRATIONS)
        yield srv
    finally:
        for name, old in previous.items():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old
        for name in srv.created:
            await _execute(postgres, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        for role in (
            srv.runtime_role,
            srv.owner_role,
            srv.data_app_role,
            srv.data_google_role,
            *(f"bc_{r}_{suffix}" for r in {*INIT_ROLES, *READER_ROLES}),
            f"bc_admin_counts_{suffix}",
        ):
            await _execute(postgres, f'DROP ROLE IF EXISTS "{role}"')


async def _drop(server: Server, name: str) -> None:
    try:
        await _execute(
            _with_database(server.admin_url, "postgres"),
            f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)',
        )
        server.created.remove(name)
    except Exception:  # noqa: BLE001 - the session teardown drops what is left
        pass


@pytest_asyncio.fixture(loop_scope="session")
async def migrated(server):
    """A fresh migrated copy of the template; yields its name and drops it
    afterwards (a run would otherwise keep one copy per test until it ends)."""
    name = await server.create_database(template=server.template)
    yield name
    await _drop(server, name)


@pytest_asyncio.fixture(loop_scope="session")
async def unmigrated(server):
    """A fresh database with the init and roles scripts applied, no migrations."""
    name = await server.create_database(template=server.boot)
    yield name
    await _drop(server, name)


@pytest_asyncio.fixture(loop_scope="session")
async def owner_engine(server, migrated):
    engine = create_async_engine(server.url(migrated, "owner"), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def runtime_engine(server, migrated):
    engine = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def tasks_engine(server, migrated):
    engine = create_async_engine(server.url(migrated, "reader:tasks"), poolclass=NullPool)
    yield engine
    await engine.dispose()


from tests.admin.portal_fixtures import (  # noqa: E402,F401
    app,
    browser,
    clock,
    make_portal,
    portal,
    transport,
)
