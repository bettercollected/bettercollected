"""Static deployment properties of the task runner (no Docker needed)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.deployment.yml").read_text())
DEPLOY = (ROOT / "deploy.sh").read_text()
ROLES = (ROOT / "postgres" / "ensure-admin-roles.sh").read_text()


def test_task_runner_service_is_locked_down():
    svc = COMPOSE["services"]["task-runner"]
    assert svc["command"][-2:] == ["-m", "backend.admin.runner"]
    assert "ports" not in svc and "expose" not in svc
    assert "env_file" not in svc
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]
    assert str(svc["user"]).split(":")[0] not in ("0", "root")
    assert "/tmp" in json.dumps(svc["tmpfs"])
    assert "networks" not in svc  # default (internal) network only, never admin-edge
    assert "docker.sock" not in json.dumps(svc)
    assert "volumes" not in svc


def test_task_runner_environment_is_limited_to_what_it_needs():
    env = COMPOSE["services"]["task-runner"]["environment"]
    # the data-store settings are optional (empty: the responses tasks refuse
    # with store_not_configured / keyset_missing)
    assert sorted(env) == [
        "ADMIN_TASKS_API_KEY",
        "ADMIN_TASKS_BACKEND_URL",
        "DATABASE_URL",
        "DB_WRITE_MODE",
        "DB_WRITE_MODE__RESPONSES",
        "GOOGLE_DATABASE_URL",
        "GOOGLE_MONGO_DB",
        "MASTER_ENCRYPTION_KEYSET",
        "MONGO_DB",
        "MONGO_URI",
        "SETTINGS_MASTER_KEY",
        "TASKS_DATABASE_URL",
    ]
    # the services' write mode: Postgres unless the root .env says otherwise (4.1)
    assert env["DB_WRITE_MODE"] == "${DB_WRITE_MODE:-postgres}"
    for name in (
        "ADMIN_TASKS_API_KEY",
        "DB_WRITE_MODE__RESPONSES",
        "GOOGLE_MONGO_DB",
        "MASTER_ENCRYPTION_KEYSET",
        "MONGO_DB",
        "MONGO_URI",
    ):
        assert env[name].startswith("${") and env[name].endswith(":-}")
    # the data stores: by default the narrow data roles, one per owning schema,
    # each built from its own password; never the backend's or Google's role
    app_url, google_url = env["DATABASE_URL"], env["GOOGLE_DATABASE_URL"]
    assert app_url.startswith("${TASK_RUNNER_DATABASE_URL:-postgresql+asyncpg://bc_tasks_data_app:")
    assert "${BC_TASKS_DATA_APP_PASSWORD}" in app_url and "@app-postgres:" in app_url
    assert google_url.startswith(
        "${TASK_RUNNER_GOOGLE_DATABASE_URL:-postgresql+asyncpg://bc_tasks_data_google:"
    )
    assert "${BC_TASKS_DATA_GOOGLE_PASSWORD}" in google_url and "@app-postgres:" in google_url
    for url in (app_url, google_url):
        for broad in ("bc_app", "bc_google:", "bc_auth", "bc_admin", "bc_jobs_exec", "bc_tasks:"):
            assert broad not in url
    # the case-duplicates task reaches the API's internal routes only
    assert env["ADMIN_TASKS_API_KEY"] == "${ADMIN_TASKS_API_KEY:-}"
    assert env["ADMIN_TASKS_BACKEND_URL"] == (
        "${TASK_RUNNER_BACKEND_URL:-http://backend:8001/api/v1}"
    )
    assert env["TASKS_DATABASE_URL"].startswith("postgresql+asyncpg://bc_tasks:")
    assert "@app-postgres:" in env["TASKS_DATABASE_URL"]
    assert "ADMIN_TASKS_SELFTEST" not in json.dumps(COMPOSE)


def test_only_the_admin_service_is_on_the_edge_network():
    attached = [
        n for n, s in COMPOSE["services"].items() if "admin-edge" in (s.get("networks") or [])
    ]
    assert attached == ["admin"]


def test_the_runner_password_is_generated_once_and_passed_to_the_roles_script():
    assert re.search(r"for var in [^;\n]*\bBC_TASKS_PASSWORD\b", DEPLOY)
    assert 'file_assigns .env "$var"' in DEPLOY  # existing values are kept
    app_pg = COMPOSE["services"]["app-postgres"]["environment"]
    assert "BC_TASKS_PASSWORD" in app_pg
    assert "BC_TASKS_PASSWORD" in ROLES and "bc.tasks_pw" in ROLES
    # never echoed
    for line in DEPLOY.splitlines():
        if "BC_TASKS_PASSWORD" in line and "echo" in line:
            assert "$BC_TASKS_PASSWORD" not in line and "${BC_TASKS_PASSWORD" not in line


def test_the_roles_script_declares_the_runner_role_and_its_schema():
    assert "['bc_tasks', 'bc.tasks_pw']" in ROLES
    assert "CREATE SCHEMA tasks AUTHORIZATION bc_admin_mig" in ROLES
    assert "REVOKE ALL ON SCHEMA tasks FROM PUBLIC" in ROLES
    assert "ALTER DEFAULT PRIVILEGES" not in ROLES.upper()
    assert "RESET bc.tasks_pw" in ROLES


def test_the_data_role_passwords_are_generated_checked_and_never_printed():
    for name in ("BC_TASKS_DATA_APP_PASSWORD", "BC_TASKS_DATA_GOOGLE_PASSWORD"):
        assert re.search(rf"for var in [^;\n]*\b{name}\b", DEPLOY)
        assert re.search(
            rf"for var in BC_APP_PASSWORD[^;\n]*\bBC_ADMIN_PASSWORD[^;\n]*\b{name}\b[^;\n]*; do\n", DEPLOY
        )  # the URL-safe check covers it
        assert name in COMPOSE["services"]["app-postgres"]["environment"]
        for line in DEPLOY.splitlines():
            if name in line and "echo" in line:
                assert f"${name}" not in line and f"${{{name}" not in line
    # the roles script runs again after the services' migrations, so a first
    # deploy also grants on the tables they just created
    runs = [m.start() for m in re.finditer(r"< postgres/ensure-admin-roles\.sh", DEPLOY)]
    assert len(runs) == 2
    first, second = runs
    assert first < DEPLOY.index("alembic -c /api/auth/alembic.ini upgrade head") < second
    assert DEPLOY.index("/api/integrations/google/alembic.ini upgrade head") < second


def test_the_roles_script_declares_one_data_role_per_owning_schema_without_broad_grants():
    for name in ("BC_TASKS_DATA_APP_PASSWORD", "BC_TASKS_DATA_GOOGLE_PASSWORD"):
        assert name in ROLES
    for var in ("bc.tasks_data_app_pw", "bc.tasks_data_google_pw"):
        assert var in ROLES and f"RESET {var}" in ROLES
    assert "'bc_tasks_data_app', 'bc.tasks_data_app_pw'" in ROLES
    assert "'bc_tasks_data_google', 'bc.tasks_data_google_pw'" in ROLES
    assert "SET search_path = pg_catalog" in ROLES
    # not in the list of roles that get the admin, tasks and settings schemas
    assert "['bc_tasks_data" not in ROLES.split("data_roles text[][]")[0]
    # grants on the other services' tables are column-level, never table-level or ALL,
    # and each role holds only its own schema's
    grants = [
        l.strip()
        for l in ROLES.splitlines()
        if re.search(r"TO bc_tasks_data_(app|google);", l) and l.strip().startswith("GRANT")
    ]
    assert grants
    # the one function the Google data role may execute: the purge of
    # credentials without a user id (a definer function; the role itself never
    # gets DELETE)
    purge = "GRANT EXECUTE ON FUNCTION google.purge_unencrypted_credentials(boolean) TO bc_tasks_data_google;"
    assert purge in grants
    grants.remove(purge)
    for line in grants:
        assert re.match(
            r"GRANT (USAGE ON SCHEMA (app|google)|SELECT \([a-z_, ]+\) ON|UPDATE \((doc, _bc_checksum)\) ON)",
            line,
        ), line
        assert "ALL" not in line and "INSERT" not in line and "DELETE" not in line
        role = "app" if line.endswith("bc_tasks_data_app;") else "google"
        assert f" {role}." in line or f"SCHEMA {role} " in line, line
    assert not re.search(r"GRANT TEMPORARY[^;]*bc_tasks_data", ROLES)
