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
        "DATABASE_URL",
        "MASTER_ENCRYPTION_KEYSET",
        "MONGO_DB",
        "MONGO_URI",
        "SETTINGS_MASTER_KEY",
        "TASKS_DATABASE_URL",
    ]
    for name in ("DATABASE_URL", "MASTER_ENCRYPTION_KEYSET", "MONGO_DB", "MONGO_URI"):
        assert env[name].startswith("${") and env[name].endswith(":-}")
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
    assert "grep -q \"^${var}=\"" in DEPLOY  # existing values are kept
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
