"""Static properties of the deployment (compose file, deploy.sh): the settings
store wiring, the internal-only ports and credentials, and the small set of
values an operator has to provide. No Docker needed, except the one test that
renders the file with `docker compose config` (skipped without it)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_TEXT = (ROOT / "docker-compose.deployment.yml").read_text()
COMPOSE = yaml.safe_load(COMPOSE_TEXT)
SERVICES = COMPOSE["services"]
DEPLOY = (ROOT / "deploy.sh").read_text()

# services that read their settings from the store (they get the master key)
STORE_SERVICES = ("backend", "jobs-worker", "auth", "integrations-googleform")
# services that carry the master key for another reason (admin: the store's owner;
# task-runner: the keyset tasks)
MASTER_KEY_HOLDERS = sorted(STORE_SERVICES + ("admin", "task-runner"))
# the generated values compose may require (`${NAME:?...}`): database passwords
# and the master key, everything else is optional so a new stack can be read
# before its keys exist
REQUIRED = {
    "APP_POSTGRES_PASSWORD",
    "BC_APP_PASSWORD",
    "BC_AUTH_PASSWORD",
    "BC_GOOGLE_PASSWORD",
    "BC_JOBS_EXEC_PASSWORD",
    "BC_ADMIN_PASSWORD",
    "BC_ADMIN_MIG_PASSWORD",
    "BC_TASKS_PASSWORD",
    "BC_TASKS_DATA_APP_PASSWORD",
    "BC_TASKS_DATA_GOOGLE_PASSWORD",
    "SETTINGS_MASTER_KEY",
}
# stored settings and keys: never required by compose
OPTIONAL_KEYS = (
    "AUTH_JWT_SECRET",
    "AUTH_AES_HEX_KEY",
    "AUTH_INTERNAL_NOTIFY_KEY",
    "TEMPORAL_API_KEY",
    "MASTER_ENCRYPTION_KEYSET",
    "API_KEY",
    "AES_HEX_KEY",
)


def _env(service: str) -> dict:
    env = SERVICES[service].get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    return {k: str(v) for k, v in env.items()}


# ------------------------------------------------------------- ports


def test_published_ports_are_the_intended_ones():
    published = {
        name: [str(p) for p in svc["ports"]] for name, svc in SERVICES.items() if svc.get("ports")
    }
    assert sorted(published) == ["admin", "backend", "nginx", "umami", "webapp"]
    # admin on loopback only; the rest are the public edge of the stack
    assert all(p.startswith("127.0.0.1:") for p in published["admin"])
    assert published["backend"] == ["8000:8000"]
    assert published["webapp"] == ["3000:3000"]
    assert published["umami"] == ["3003:3000"]  # respondents' browsers load its script
    assert sorted(published["nginx"]) == ["3001:3001", "3002:3002"]


@pytest.mark.parametrize(
    "service",
    [
        "temporal",
        "postgresql",
        "app-postgres",
        "mongodb",
        "umami-postgresql",
        "worker",
        "task-runner",
        "document-sandbox",
        "jobs-worker",
        "auth",
        "integrations-googleform",
        "integrations-typeform",
        "mongo-seed",
    ],
)
def test_internal_services_publish_no_port(service):
    assert not SERVICES[service].get("ports"), service
    assert not SERVICES[service].get("expose") or service in ("temporal",), service


def test_temporal_is_not_published_on_any_port():
    # its frontend has no authentication
    assert "7234" not in COMPOSE_TEXT and "7233:7233" not in COMPOSE_TEXT
    assert "ports" not in SERVICES["temporal"]


# ----------------------------------------------------- credentials


def test_no_default_credentials_on_new_volumes():
    # Temporal's and Umami's databases take a generated password on a new volume;
    # an old volume keeps the one it was created with (the variable is unset)
    assert _env("postgresql")["POSTGRES_PASSWORD"] == "${BC_TEMPORAL_DB_PASSWORD:-temporal}"
    temporal_env = SERVICES["temporal"]["environment"]
    assert "POSTGRES_PWD=${BC_TEMPORAL_DB_PASSWORD:-temporal}" in temporal_env
    assert "POSTGRES_PWD=temporal" not in temporal_env
    assert _env("umami-postgresql")["POSTGRES_PASSWORD"] == "${BC_UMAMI_DB_PASSWORD:-umami}"
    assert _env("umami")["DATABASE_URL"] == (
        "postgresql://umami:${BC_UMAMI_DB_PASSWORD:-umami}@umami-postgresql:5432/umami"
    )
    assert "umami:umami@" not in COMPOSE_TEXT


def test_mongo_takes_a_generated_root_password_on_a_new_volume():
    assert _env("mongodb")["MONGO_INITDB_ROOT_PASSWORD"] == "${BC_MONGO_ROOT_PASSWORD:-root}"
    assert _env("mongo-seed")["MONGO_ROOT_PASSWORD"] == "${BC_MONGO_ROOT_PASSWORD:-root}"
    seed = (ROOT / "Dockerfile.deployment.mongo-seed").read_text()
    assert "root:root@" not in seed and "${MONGO_ROOT_PASSWORD:-root}" in seed
    # the services' MONGO_URI is a store setting seeded by deploy.sh, not a file value
    assert not re.search(r"^MONGO_URI=", (ROOT / ".env.deployment").read_text(), re.M)
    assert "BC_MONGO_ROOT_PASSWORD" in DEPLOY and "seed_setting MONGO_URI" in DEPLOY


def test_no_literal_credential_is_left_in_the_compose_file():
    """Every password, secret or key in an environment is a substitution; the
    ones with a default (`:-root`, `:-temporal`, `:-umami`) keep the password an
    old volume was created with. Documented in docs/admin-service.md."""
    literal = []
    for name, svc in SERVICES.items():
        env = svc.get("environment") or {}
        pairs = (
            [item.split("=", 1) for item in env] if isinstance(env, list) else list(env.items())
        )
        for key, value in pairs:
            if re.search(r"(PASSWORD|PWD|SECRET|API_KEY|TOKEN)", key) and isinstance(value, str):
                if value and not value.startswith("${") and not value.endswith(":-}"):
                    literal.append((name, key))
    assert literal == []


def test_umami_default_login_is_replaced_by_deploy_sh():
    assert (ROOT / "deploy" / "umami-rotate.js").is_file()
    assert "umami_credentials" in DEPLOY and "default_login=yes" in (
        ROOT / "deploy" / "umami-rotate.js"
    ).read_text()
    # the password reaches the container by name only, never in a command line
    assert "-e UMAMI_NEW_PASSWORD umami" in DEPLOY
    assert "UMAMI_NEW_PASSWORD=$" not in DEPLOY.replace('UMAMI_NEW_PASSWORD="$password"', "")


# ------------------------------------------------ settings store wiring


def test_store_services_read_the_store_and_hold_the_master_key():
    for name in STORE_SERVICES:
        env = _env(name)
        assert env["SETTINGS_STORE"] == "${SETTINGS_STORE:-required}", name
        assert env["SETTINGS_MASTER_KEY"].startswith("${SETTINGS_MASTER_KEY:?"), name
        assert env["SETTINGS_SNAPSHOT_DIR"] == "/var/lib/bc-settings", name
    # each reading service keeps its own snapshot volume
    volumes = {
        n: [v for v in SERVICES[n]["volumes"] if "/var/lib/bc-settings" in v] for n in STORE_SERVICES
    }
    assert len({v[0] for v in volumes.values()}) == len(STORE_SERVICES)
    assert all(len(v) == 1 for v in volumes.values())


def test_the_master_key_is_in_no_other_service():
    holders = sorted(
        name for name in SERVICES if "SETTINGS_MASTER_KEY" in json.dumps(SERVICES[name])
    )
    assert holders == MASTER_KEY_HOLDERS


@pytest.mark.parametrize("service", ["worker", "webapp", "integrations-typeform", "nginx"])
def test_services_outside_the_store_get_no_store_variables(service):
    env = _env(service)
    for name in ("SETTINGS_MASTER_KEY", "SETTINGS_STORE", "SETTINGS_SNAPSHOT_DIR", "DATABASE_URL"):
        assert name not in env, (service, name)
    assert "settings-snapshots" not in json.dumps(SERVICES[service])


def test_the_worker_keeps_two_keys_in_env_and_never_the_master_key():
    env = _env("worker")
    assert env["API_KEY"] == "${API_KEY:-}"
    assert env["AES_HEX_KEY"] == "${AES_HEX_KEY:-}"
    for forbidden in (
        "SETTINGS_MASTER_KEY",
        "MASTER_ENCRYPTION_KEYSET",
        "AUTH_JWT_SECRET",
        "AUTH_INTERNAL_NOTIFY_KEY",
        "ADMIN_DATABASE_URL",
    ):
        assert forbidden not in json.dumps(SERVICES["worker"])
    # its environment file never carries the master key either
    assert "SETTINGS_MASTER_KEY" not in (ROOT / ".env.deployment").read_text()
    assert "worker" not in COMPOSE["networks"]  # default network only, no database role
    assert "volumes" not in SERVICES["worker"]


def test_typeform_keeps_its_keys_in_env():
    assert sorted(_env("integrations-typeform")) == [
        "AUTH_AES_HEX_KEY",
        "AUTH_JWT_SECRET",
        "MASTER_ENCRYPTION_KEYSET",
    ]


def test_no_service_pins_debug_or_api_docs():
    assert not re.search(r"^\s+(DEBUG|API_DOCS_ENABLED)\s*:", COMPOSE_TEXT, re.M)


def test_stored_keys_are_optional_in_compose():
    required = set(re.findall(r"\$\{([A-Z_]+):\?", COMPOSE_TEXT))
    assert required == REQUIRED
    for name in OPTIONAL_KEYS:
        assert not re.search(rf"\$\{{{name}:\?", COMPOSE_TEXT), name
    # every stored key a store service still passes is an empty-by-default
    # passthrough (an empty value means "read the store")
    for name in STORE_SERVICES:
        env = _env(name)
        for key in OPTIONAL_KEYS:
            if key in env:
                assert env[key] == "${" + key + ":-}", (name, key)


def test_wiring_pins_that_would_beat_the_portal_are_gone():
    backend = _env("backend")
    jobs = _env("jobs-worker")
    for env in (backend, jobs):
        assert "UMAMI_URL" not in env  # seeded into the store by deploy.sh
        assert "AUTH_CALLBACK_URI" not in env  # the code default is the auth address
    auth = _env("auth")
    assert "TYPEFORM_REDIRECT_URI" not in auth and "TYPEFORM_SCOPE" not in auth


# ----------------------------------------------------------- deploy.sh


def _position(text: str, needle: str) -> int:
    idx = text.find(needle)
    assert idx >= 0, needle
    return idx


def test_deploy_runs_bootstrap_keys_before_the_services_start():
    up = DEPLOY[DEPLOY.index("function dockerup()") :]
    assert _position(up, "stack_keys || exit 1") < _position(up, 'up --build -d "$@"')
    keys = DEPLOY[DEPLOY.index("function stack_keys()") :]
    assert "bootstrap-keys" in keys and "--export-worker /out/worker.env" in keys
    # the migrations (which create the store's tables) come first
    assert _position(up, "alembic.ini upgrade head") < _position(up, "stack_keys || exit 1")


def test_deploy_generates_the_operator_free_secrets_and_not_the_store_keys():
    for var in (
        "SETTINGS_MASTER_KEY",
        "APP_POSTGRES_PASSWORD",
        "BC_TASKS_DATA_GOOGLE_PASSWORD",
        "UMAMI_APP_SECRET",
        "BC_TEMPORAL_DB_PASSWORD",
        "BC_UMAMI_DB_PASSWORD",
    ):
        assert var in DEPLOY
    before = DEPLOY[: DEPLOY.index("function stack_keys()")]
    loop = re.search(r"for var in (APP_POSTGRES_PASSWORD[^;]*); do", before).group(1)
    assert "AUTH_INTERNAL_NOTIFY_KEY" not in loop and "TEMPORAL_API_KEY" not in loop
    # generate-secrets.sh (copies and checks the old keys) runs for an upgrade only
    assert "bash deploy/generate-secrets.sh" not in before
    assert "bash deploy/generate-secrets.sh" in DEPLOY[DEPLOY.index("function stack_keys()") :]


def test_the_upgrade_imports_then_checks_and_prunes_only_on_request():
    keys = DEPLOY[DEPLOY.index("function stack_keys()") :]
    assert _position(keys, "settings-import --from-compose-config") < _position(keys, "settings_drift")
    # prune is a separate, explicit command, never part of the deploy run
    assert "settings_prune" not in DEPLOY[DEPLOY.index("function stack_keys()") :]
    prune = DEPLOY[DEPLOY.index("settings_prune() {") : DEPLOY.index("# ./deploy.sh settings-env-export")]
    assert "typeform_keys=(AUTH_JWT_SECRET AUTH_AES_HEX_KEY MASTER_ENCRYPTION_KEYSET)" in DEPLOY
    assert '--keep "$name"' in prune and "${typeform_keys[@]}" in prune


def test_the_setup_token_goes_to_the_console_only():
    token = DEPLOY[DEPLOY.index("setup_token() {") : DEPLOY.index("# --- host commands")]
    assert "[ ! -t 0 ] || [ ! -t 1 ]" in token  # refuses without a terminal
    assert " -T " not in token and "setup-token" in token
    # never captured into a variable, a file or a pipe
    for line in DEPLOY.splitlines():
        if "setup-token" in line and "run --rm" in line:
            assert not re.search(r"\$\(|>|\|", line.split("setup-token", 1)[1]), line


def test_deploy_never_prints_a_secret():
    secrets = ("password", "value", "line", "UMAMI_NEW_PASSWORD", "AUTH_JWT_SECRET", "SETTINGS_MASTER_KEY")
    for number, line in enumerate(DEPLOY.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith(("echo ", "printf ")):
            continue
        # writing to a file or a pipe is not printing
        if re.search(r">>?\s*\S|\|", stripped):
            continue
        for name in secrets:
            assert f"${name}" not in stripped and f"${{{name}}}" not in stripped, (number, stripped)


def test_the_one_off_admin_container_has_no_generated_key():
    admin = _env("admin")
    for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY", "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET"):
        assert key not in admin  # `bootstrap-keys` refuses an environment that carries one
    assert "env_file" not in SERVICES["admin"]


def test_env_is_ignored_in_every_backup_form():
    ignore = (ROOT / ".gitignore").read_text()
    for pattern in (".env.pre-v4.*", ".env.deployment.pre-v4.*", ".env.*.pruned", ".env.deployment.pre-umami.*"):
        assert pattern in ignore


# ------------------------------------------------ the rendered config


def _compose_works() -> bool:
    if not shutil.which("docker"):
        return False
    done = subprocess.run(["docker", "compose", "version"], capture_output=True)
    return done.returncode == 0


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
def test_a_minimal_env_renders_a_bootable_config(tmp_path):
    """What an operator provides (the four) plus what deploy.sh generates into
    .env, and nothing else: compose renders, the stored keys are not needed."""
    env = tmp_path / "minimal.env"
    lines = [
        # the operator's
        "PLATFORM_ADMIN_EMAILS=ops@example.test",
        "ADMIN_ALLOWED_IPS=127.0.0.1/32",
        # generated by deploy.sh
        "SETTINGS_MASTER_KEY=" + "A" * 64,
    ] + [f"{name}=pw{n}" for n, name in enumerate(sorted(REQUIRED - {"SETTINGS_MASTER_KEY"}))]
    lines.append("UMAMI_APP_SECRET=x")
    env.write_text("\n".join(lines) + "\n")
    # the shell's own variables would win over the env file
    names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", COMPOSE_TEXT))
    hermetic = {k: v for k, v in os.environ.items() if k not in names}
    done = subprocess.run(
        [
            "docker", "compose", "--env-file", str(env), "-f", str(ROOT / "docker-compose.deployment.yml"),
            "config", "--format", "json",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=hermetic,
    )
    assert done.returncode == 0, done.stderr[-800:]
    rendered = json.loads(done.stdout)["services"]
    # the services that read the store boot from this: master key, own role URL, store required
    for name in STORE_SERVICES:
        e = rendered[name]["environment"]
        assert e["SETTINGS_STORE"] == "required" and e["SETTINGS_MASTER_KEY"] == "A" * 64
        assert e["DATABASE_URL"].startswith("postgresql+asyncpg://bc_")
    # the stored keys render empty, which means "read the store"
    for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET"):
        assert rendered["backend"]["environment"][key] == ""
    worker = rendered["worker"]["environment"]
    assert "SETTINGS_MASTER_KEY" not in worker
    assert rendered["admin"]["environment"]["PLATFORM_ADMIN_EMAILS"] == "ops@example.test"
    assert rendered["temporal"].get("ports") in (None, [])
    assert not any("7233" in str(p) or "7234" in str(p) for p in rendered["temporal"].get("ports") or [])
