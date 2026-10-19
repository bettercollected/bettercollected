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
import uuid
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
    # Umami's dashboard and login: loopback only. Respondents' browsers load its
    # tracker script and post events through nginx on 3003, which passes nothing else
    assert published["umami"] == ["127.0.0.1:3004:3000"]
    assert sorted(published["nginx"]) == ["3001:3001", "3002:3002", "3003:3003"]


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
    seed_js = (ROOT / "seed-data-deployment.js").read_text()
    # the password reaches mongosh through its environment, never its command line
    assert "root:root@" not in seed and "MONGO_ROOT_PASSWORD" not in seed.replace("# ", "").split("CMD")[1]
    assert "--nodb" in seed and "process.env.MONGO_ROOT_PASSWORD" in seed_js and "mongodb://root" not in seed_js
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
    # every other .env.* file is ignored too (.env.pruned, .env.XXXXXX leftovers, the
    # per-service env files), except the shipped example and the tracked template
    lines = ignore.splitlines()
    assert ".env.*" in lines and "!.env.example" in lines and "!.env.deployment" in lines
    assert lines.index(".env.*") < lines.index("!.env.example")


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_generated_secret_files_are_git_ignored_and_the_templates_are_not():
    def ignored(name):
        return subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0

    for name in (".env", ".env.pruned", ".env.XXXXXX", ".env.deployment.pruned", ".env.deployment.AbC123",
                 ".env.webapp", ".env.worker", ".env.typeform", ".env.pre-v4.20260101"):
        assert ignored(name), name
    for name in (".env.example", "webapp/.env.example", ".env.deployment"):
        assert not ignored(name), name


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


# ------------------------------------------------ what each service receives


# the services that read the settings store (they hold the master key, so they can read
# every stored value anyway): the only ones that get the shared .env.deployment
ENV_DEPLOYMENT_READERS = ("backend", "jobs-worker", "auth", "integrations-googleform")
# the services with an env file of their own, written by deploy.sh from .env.deployment
OWN_ENV_FILE = {
    "webapp": ".env.webapp",
    "worker": ".env.worker",
    "integrations-typeform": ".env.typeform",
}


def _env_files(service: str) -> list:
    out = []
    for item in SERVICES[service].get("env_file") or []:
        out.append(item["path"] if isinstance(item, dict) else item)
    return out


def test_only_the_store_readers_get_the_shared_env_file():
    users = sorted(n for n in SERVICES if ".env.deployment" in _env_files(n))
    assert users == sorted(ENV_DEPLOYMENT_READERS)
    # the others read an env file of their own, optional (compose renders without it),
    # or none at all
    for name, path in OWN_ENV_FILE.items():
        entries = SERVICES[name]["env_file"]
        assert entries == [{"path": path, "required": False}], name
    for name in SERVICES:
        if name not in ENV_DEPLOYMENT_READERS and name not in OWN_ENV_FILE:
            assert not _env_files(name), name


def _inventory_readers() -> dict:
    """{setting name: readers} from docs/settings-inventory.md."""
    readers = {}
    for line in (ROOT / "docs" / "settings-inventory.md").read_text().splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 4 and re.fullmatch(r"`[A-Z][A-Z0-9_]+`", cells[1]):
            readers[cells[1].strip("`")] = {r.strip() for r in cells[3].split(",")}
    return readers


def _deploy_list(name: str) -> list:
    body = re.search(rf"^{name}=\((.*)\)$", DEPLOY, re.M).group(1)
    return [item.strip("'") for item in body.split()]


def _covered(key: str, items: list) -> bool:
    return any(key.startswith(i[:-1]) if i.endswith("*") else key == i for i in items)


def test_the_webapp_and_worker_env_files_cover_what_those_services_read():
    """Every setting the inventory says the webapp or the Temporal worker reads reaches
    it (from its own env file or from the compose file), and the lists name nothing
    that is a secret of another service."""
    inventory = _inventory_readers()
    for service, reader, keys, skip in (
        ("webapp", "webapp", _deploy_list("webapp_env_keys"), set()),
        # AUTH_AES_HEX_KEY is listed for the worker only because its AES_HEX_KEY is a copy
        ("worker", "temporal_worker", _deploy_list("worker_env_keys"), {"AUTH_AES_HEX_KEY"}),
    ):
        provided = list(keys) + list(_env(service))
        for name, who in inventory.items():
            if reader in who and name not in skip:
                assert _covered(name, provided), (service, name)
    never = (
        "STRIPE_", "GOOGLE_CLIENT_SECRET", "MAIL_", "MONGO_URI", "MASTER_ENCRYPTION_KEYSET", "AUTH_JWT_SECRET",
        "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY", "TEMPORAL_API_KEY", "SETTINGS_MASTER_KEY", "TYPEFORM_",
        "UMAMI_PASSWORD", "DATABASE_URL",
    )
    for name in ("webapp_env_keys", "worker_env_keys"):
        for item in _deploy_list(name):
            assert not item.startswith(never), (name, item)


def test_first_party_services_cannot_gain_privileges():
    for name in ("webapp", "worker", "backend", "jobs-worker", "auth", "integrations-googleform", "integrations-typeform"):
        assert "no-new-privileges:true" in SERVICES[name]["security_opt"], name
    # the services that need no capability at all drop every one (the backend and jobs
    # worker keep root's file access: they open the document sandbox's socket directory)
    for name in ("webapp", "worker", "integrations-typeform"):
        assert SERVICES[name]["cap_drop"] == ["ALL"], name
    assert "cap_add" not in COMPOSE_TEXT
    assert SERVICES["nginx"]["image"] == "nginx:1.28-alpine"


def test_the_worker_image_does_not_resolve_dependencies_at_start():
    dockerfile = (ROOT / "temporal" / "worker" / "Dockerfile").read_text()
    cmd = [line for line in dockerfile.splitlines() if line.startswith("CMD")][-1]
    assert "uv" not in cmd and "python" in cmd


def test_umami_dashboard_is_private_and_nginx_passes_only_the_tracker():
    conf = (ROOT / "nginx-deployment.conf").read_text()
    block = conf[conf.index("listen 3003;") :]
    assert "location = /script.js" in block and "location ~ ^/api/(send|batch)$" in block
    assert "return 404" in block and "umami:3000" in block
    # nothing but those three locations proxies to Umami
    assert block.count("proxy_pass") == 2
    assert "3000:3000" not in COMPOSE_TEXT.split("umami:", 1)[1]


def test_the_shipped_env_template_is_free_of_insecure_and_inert_settings():
    template = (ROOT / ".env.deployment").read_text()
    active = [l for l in template.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    assert not any(l.startswith("OAUTHLIB_INSECURE_TRANSPORT") for l in active)
    assert not any(l.startswith("ADMIN_") for l in active)  # compose reads those from the root .env
    assert "ADMIN_ALLOWED_IPS" in template  # but the comment says where they go


def test_dev_compose_publishes_every_port_on_loopback_only():
    local = yaml.safe_load((ROOT / "docker-compose.local.yml").read_text())["services"]
    published = [str(p) for svc in local.values() for p in svc.get("ports") or []]
    assert published
    assert all(p.startswith("127.0.0.1:") for p in published), published


def test_secrets_are_not_passed_to_psql_or_mongosh_as_arguments():
    init = (ROOT / "postgres" / "init" / "01-roles-schemas.sh").read_text()
    assert "-v app_pw" not in init and "\\getenv app_pw BC_APP_PASSWORD" in init
    assert "createUser" not in (ROOT / "seed-data-deployment.js").read_text()
    assert "pwd:" not in (ROOT / "seed-data-deployment.js").read_text()
    assert "dropUser('seeduser')" in (ROOT / "seed-data-deployment.js").read_text()


def test_the_deploy_workflow_is_pinned_and_takes_no_untrusted_context_in_its_scripts():
    workflows = ROOT / ".github" / "workflows"
    for path in workflows.glob("*.yml"):
        for line in path.read_text().splitlines():
            m = re.search(r"uses:\s*(\S+)", line)
            if m and not m.group(1).startswith("./"):
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", m.group(1)), (path.name, m.group(1))
    deploy = yaml.safe_load((workflows / "deploy.yml").read_text())
    for job in deploy["jobs"].values():
        for step in job["steps"]:
            run = step.get("run", "")
            # context values reach scripts only through env
            assert "${{" not in run, (step.get("name"), run)
    tags = deploy[True]["push"]["tags"]
    assert tags and all(t.startswith("v[0-9]+") for t in tags)


# --------------------------------------------- rendered with a populated .env.deployment

DUMMY = {
    "STRIPE_SECRET": "DUMMY-stripe-secret-1",
    "STRIPE_WEBHOOK_SECRET": "DUMMY-stripe-webhook-2",
    "GOOGLE_CLIENT_SECRET": "DUMMY-google-secret-3",
    "MAIL_PASSWORD": "DUMMY-mail-password-4",
    "MONGO_URI": "mongodb://root:DUMMY-mongo-root-5@mongodb:27017",
    "MASTER_ENCRYPTION_KEYSET": "DUMMY-response-keyset-6",
    "AUTH_JWT_SECRET": "DUMMY-jwt-secret-7",
    "AUTH_AES_HEX_KEY": "DUMMY-aes-key-8",
    "TYPEFORM_CLIENT_SECRET": "DUMMY-typeform-secret-9",
}
NEVER_TO_PUBLIC_OR_BROWSER_SERVICES = ("worker", "webapp")


def _render(workdir: Path, extra_env: dict | None = None) -> dict:
    env = workdir / "skeleton.env"
    lines = [f"{name}=pw{n}" for n, name in enumerate(sorted(REQUIRED))] + ["UMAMI_APP_SECRET=x"]
    env.write_text("\n".join(lines) + "\n")
    names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", COMPOSE_TEXT)) | set(DUMMY)
    hermetic = {k: v for k, v in os.environ.items() if k not in names}
    done = subprocess.run(
        ["docker", "compose", "--env-file", str(env), "-f", str(workdir / "docker-compose.deployment.yml"),
         "config", "--format", "json"],
        capture_output=True, text=True, cwd=workdir, env={**hermetic, **(extra_env or {})},
    )
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)["services"]


def _holders(rendered: dict) -> dict:
    """{secret name: [services whose rendered config carries its dummy value]}"""
    return {
        name: sorted(svc for svc, body in rendered.items() if value in json.dumps(body))
        for name, value in DUMMY.items()
    }


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
def test_a_populated_env_deployment_reaches_only_the_store_readers(tmp_path):
    """The rendered configuration, with every secret an operator may keep in
    .env.deployment filled in (as an upgraded stack has them): the Chromium worker and the
    public webapp hold none of them, and neither does any service outside the four that read
    the settings store. The Typeform service gets only its own env file's contents."""
    shutil.copy(ROOT / "docker-compose.deployment.yml", tmp_path / "docker-compose.deployment.yml")
    (tmp_path / ".env.deployment").write_text("".join(f"{k}={v}\n" for k, v in DUMMY.items()))
    holders = _holders(_render(tmp_path))
    for name, services in holders.items():
        assert set(services) <= set(ENV_DEPLOYMENT_READERS), (name, services)
        for service in NEVER_TO_PUBLIC_OR_BROWSER_SERVICES + ("integrations-typeform", "nginx", "mongo-seed",
                                                              "admin", "task-runner", "document-sandbox",
                                                              "umami", "temporal", "mongodb"):
            assert service not in services, (name, service)


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
def test_the_service_env_files_deploy_sh_writes_are_the_only_extra_input(tmp_path):
    shutil.copy(ROOT / "docker-compose.deployment.yml", tmp_path / "docker-compose.deployment.yml")
    (tmp_path / ".env.deployment").write_text("".join(f"{k}={v}\n" for k, v in DUMMY.items()))
    (tmp_path / ".env.webapp").write_text("UNSPLASH_ACCESS_KEY=DUMMY-unsplash\n")
    (tmp_path / ".env.worker").write_text("COOKIE_DOMAIN=example.test\n")
    (tmp_path / ".env.typeform").write_text("TYPEFORM_CLIENT_ID=DUMMY-tid\n")
    rendered = _render(tmp_path)
    assert rendered["webapp"]["environment"]["UNSPLASH_ACCESS_KEY"] == "DUMMY-unsplash"
    assert rendered["worker"]["environment"]["COOKIE_DOMAIN"] == "example.test"
    assert rendered["integrations-typeform"]["environment"]["TYPEFORM_CLIENT_ID"] == "DUMMY-tid"
    # the worker's whole environment: its own file plus the compose file's few values
    assert set(rendered["worker"]["environment"]) == {"API_KEY", "AES_HEX_KEY", "TEMPORAL_SERVER_URL", "COOKIE_DOMAIN"}
    for name, services in _holders(rendered).items():
        for service in NEVER_TO_PUBLIC_OR_BROWSER_SERVICES:
            assert service not in services, (name, service)
        if name != "AUTH_JWT_SECRET" and name != "AUTH_AES_HEX_KEY" and name != "MASTER_ENCRYPTION_KEYSET":
            assert "integrations-typeform" not in services, name
    # the typeform service keeps exactly its three documented keys from the compose file
    assert {"AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET"} <= set(
        rendered["integrations-typeform"]["environment"]
    )


@pytest.mark.skipif(not _compose_works(), reason="needs docker compose v2")
@pytest.mark.parametrize("preference", ["", "both", "typeform", "googleform"])
def test_up_starts_every_required_service_for_every_preference(tmp_path, preference):
    """What `./deploy.sh [preference]` hands to `docker compose up -d`, run through
    `up --dry-run`: every service the stack needs is created. A service that is not named
    (and is not a dependency of one that is) is silently left stopped."""
    shutil.copy(ROOT / "docker-compose.deployment.yml", tmp_path / "docker-compose.deployment.yml")
    shutil.copy(ROOT / "docker-compose.sso-deployment.yml", tmp_path / "docker-compose.sso-deployment.yml")
    shutil.copy(ROOT / "deploy.sh", tmp_path / "deploy.sh")
    (tmp_path / "nginx-deployment.conf").write_text("")
    (tmp_path / ".env.deployment").write_text("")
    (tmp_path / "postgres" / "init").mkdir(parents=True)
    (tmp_path / "deploy" / "seccomp").mkdir(parents=True)
    (tmp_path / "deploy" / "seccomp" / "document-sandbox.json").write_text("{}")
    _render(tmp_path)  # writes skeleton.env
    (tmp_path / ".env").write_text((tmp_path / "skeleton.env").read_text())
    project = "bcdry" + uuid.uuid4().hex[:8]  # parallel workers never share a project
    listed = subprocess.run(
        ["bash", "deploy.sh", "print-services", preference], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "COMPOSE_PROJECT_NAME": project},
    )
    assert listed.returncode == 0, listed.stderr
    names = listed.stdout.split()
    for _ in range(4):
        done = subprocess.run(
            ["docker", "compose", "-p", project, "--env-file", str(tmp_path / ".env"), "-f", "docker-compose.deployment.yml",
             "up", "--dry-run", "-d", *names],
            cwd=tmp_path, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "COMPOSE_PROJECT_NAME"},
        )
        # Compose 2.24's dry run now and then reports "X is missing dependency Y" for a
        # dependency it has just planned; the real `up` does not. Run it again.
        if done.returncode == 0 or "is missing dependency" not in done.stderr:
            break
    assert done.returncode == 0, (done.stderr[:1200], done.stderr[-600:])
    output = done.stdout + done.stderr
    created = set(re.findall(rf"Container {project}-([a-z-]+?)-\d+\s+(?:Creat|Recreat|Start|Runn)", output))
    required = {
        "mongodb", "mongo-seed", "webapp", "nginx", "backend", "auth", "postgresql", "temporal", "worker",
        "umami-postgresql", "umami", "app-postgres", "admin", "jobs-worker", "document-sandbox", "task-runner",
    }
    assert required <= created, (sorted(required - created), output[-1500:])
    extra = {"both": {"integrations-typeform", "integrations-googleform"}, "typeform": {"integrations-typeform"},
             "googleform": {"integrations-googleform"}, "": set()}[preference]
    assert extra <= created
    assert ("integrations-typeform" in created) == ("integrations-typeform" in extra)
