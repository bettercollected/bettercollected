"""deploy.sh against a stand-in for docker compose: the order of the steps and
what ends up in the root .env, for a new install and for an upgrade. No Docker
needed. The stand-in records every call, answers `settings-history` from a small
state directory, and writes what `bootstrap-keys --export-worker` would write."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import os, sys, pathlib, secrets, json
    state = pathlib.Path(os.environ["STUB_STATE"])
    argv = sys.argv[1:]
    with (state / "calls.log").open("a") as log:
        log.write(" ".join(argv) + "\\n")
    with (state / "project.log").open("a") as log:
        log.write(os.environ.get("COMPOSE_PROJECT_NAME", "") + "\\n")
    store = state / "store"
    store.mkdir(exist_ok=True)

    def has(key):
        return (store / key).exists()

    if "run" in argv and "backend.admin" in argv:
        cmd = argv[argv.index("backend.admin") + 1:]
        verb = cmd[0]
        stdin = "" if sys.stdin.isatty() else sys.stdin.read()
        if verb == "settings-history":
            print("versions=%d" % (1 if has(cmd[1]) else 0))
        elif verb == "bootstrap-keys":
            if os.environ.get("STUB_PG_RESPONSES"):
                # the real refusal (and its wording) from the host commands, with the
                # database counts faked: a Postgres that already holds data
                import asyncio
                from backend.admin.__main__ import _refuse
                from backend.admin.services import host_settings as host

                async def counts():
                    return {"users": {"total": 0},
                            "responses": {"total": int(os.environ["STUB_PG_RESPONSES"])}}

                try:
                    asyncio.run(host.refuse_if_stack_has_data(None, counts=counts))
                except host.HostError as error:
                    sys.exit(_refuse(error))
            if "--fill-missing" not in cmd and has("AUTH_JWT_SECRET"):
                print("refused: keys_exist", file=sys.stderr); sys.exit(1)
            for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY",
                        "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET"):
                (store / key).write_text("x")
            print("generated=5 (values are not shown)")
            if "--export-worker" in cmd:
                target = cmd[cmd.index("--export-worker") + 1]
                mounts = [a for a in argv if a.endswith(":/out")]
                host = mounts[0].rsplit(":", 1)[0]
                out = pathlib.Path(host) / pathlib.Path(target).name
                fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write("API_KEY=%s\\nAES_HEX_KEY=%s\\n" % (secrets.token_hex(24), secrets.token_hex(24)))
                print("worker_keys_written file=%s mode=600" % out.name)
            print("master_key_fingerprint abcd-ef01-2345")
        elif verb == "settings-set":
            (store / cmd[1]).write_text(stdin)
            print("set %s version=1 changed=yes" % cmd[1])
        elif verb == "settings-import":
            for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY",
                        "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET"):
                (store / key).write_text("x")
            print("would_import=0 imported=5")
            if os.environ.get("STUB_IMPORT_FAILS"):
                sys.exit(1)
            if os.environ.get("STUB_IMPORT_REFUSES"):
                print("refused " + os.environ["STUB_IMPORT_REFUSES"])
                sys.exit(1)
            if os.environ.get("STUB_IMPORT_CONFLICT"):
                print("conflict STRIPE_SECRET backend,auth")
                sys.exit(1)
        elif verb == "settings-drift":
            print("equal=5 differs=0")
            if os.environ.get("STUB_DRIFT_DIFFERS"):
                print("differs AUTH_JWT_SECRET backend"); sys.exit(1)
        elif verb == "master-key-fingerprint":
            print("master_key_fingerprint abcd-ef01-2345")
        elif verb == "setup-token":
            print("TOKEN-SHOWN")
        sys.exit(0)
    if "config" in argv:
        print("{}")
        sys.exit(0)
    if "ps" in argv and "admin" in argv:
        print("stub-admin-container")
        sys.exit(0)
    if "exec" in argv and "umami" in argv:
        sys.stdin.read()
        if os.environ.get("STUB_UMAMI_FAILS"):
            if "-e" in argv:  # the rotation itself (carries the new password by name)
                sys.exit(1)
            print("default_login=yes")
        else:
            print("default_login=no")
        sys.exit(0)
    if "exec" in argv:
        sys.stdin.read()
    sys.exit(0)
    '''
)
DOCKER_STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import os, sys
    argv = sys.argv[1:]
    # STUB_VOLUMES: comma separated; "vol" lives in the project named "stack" (the
    # fixture's directory and COMPOSE_PROJECT_NAME), "project:vol" in that project
    items = []
    for item in os.environ.get("STUB_VOLUMES", "").split(","):
        if not item:
            continue
        project, _, vol = item.rpartition(":")
        items.append((project or "stack") + "_" + vol)
    if argv[:2] == ["volume", "inspect"]:
        sys.exit(0 if argv[2] in items else 1)
    if argv[:2] == ["volume", "ls"]:
        label = [a for a in argv if a.startswith("label=com.docker.compose.project=")]
        prefix = label[0].split("=", 2)[2] + "_" if label else ""
        print("\\n".join(i for i in items if i.startswith(prefix)))
        sys.exit(0)
    if argv[:1] == ["inspect"]:
        print(os.environ.get("STUB_ADMIN_HEALTH", "healthy"))
        sys.exit(0)
    sys.exit(0)
    '''
)


@pytest.fixture
def site(tmp_path):
    """A copy of the deployment files and a PATH with the stand-ins in front."""
    work = tmp_path / "stack"
    work.mkdir()
    shutil.copy(ROOT / "deploy.sh", work / "deploy.sh")
    shutil.copytree(ROOT / "deploy", work / "deploy", ignore=shutil.ignore_patterns("seccomp"))
    (work / "postgres").mkdir()
    shutil.copy(ROOT / "postgres" / "ensure-admin-roles.sh", work / "postgres" / "ensure-admin-roles.sh")
    (work / "docker-compose.deployment.yml").write_text("services: {}\n")
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("docker-compose", STUB), ("docker", DOCKER_STUB)):
        path = bin_dir / name
        # the stand-in imports the real host-command code for the refusal
        path.write_text(body.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "state"
    state.mkdir()
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "STUB_STATE": str(state),
        "COMPOSE_PROJECT_NAME": "stack",
        "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT / "common")]),
    }
    return work, state, env


def _run(site, *args, volumes="", extra=None, drop=()):
    work, state, env = site
    env = {**env, "STUB_VOLUMES": volumes, "BC_DEPLOY_ADMIN_WAIT_SECONDS": "2", "BC_DEPLOY_RETRY_SLEEP": "0", **(extra or {})}
    for name in drop:
        env.pop(name, None)
    done = subprocess.run(
        ["bash", "deploy.sh", *args], cwd=work, env=env, capture_output=True, text=True, timeout=120
    )
    calls = (state / "calls.log").read_text().splitlines() if (state / "calls.log").exists() else []
    return done, calls


def _dotenv(work: Path) -> dict:
    values = {}
    for line in (work / ".env").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _temp_leftovers(work: Path) -> list:
    """mktemp leftovers (.env.XXXXXX): not the per-service env files."""
    return [p for p in work.glob(".env.??????") if p.name not in (".env.worker", ".env.webapp")]


def _index(calls, needle, start=0):
    for number, call in enumerate(calls[start:], start):
        if needle in call:
            return number
    raise AssertionError(f"no call with {needle!r}")


def test_new_install_bootstraps_keys_before_any_service_starts(site):
    work, state, _ = site
    done, calls = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    boot = _index(calls, "bootstrap-keys")
    assert _index(calls, "alembic") < boot < _index(calls, "up --build")
    assert "--export-worker /out/worker.env" in calls[boot]
    # no import on a new stack, and Umami's login is checked after the start
    assert not any("settings-import" in c for c in calls)
    assert _index(calls, "up --build") < _index(calls, "exec -T umami")

    values = _dotenv(work)
    for name in (
        "SETTINGS_MASTER_KEY", "APP_POSTGRES_PASSWORD", "BC_ADMIN_PASSWORD", "UMAMI_APP_SECRET",
        "BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD", "API_KEY", "AES_HEX_KEY",
    ):
        assert values.get(name), name
    # the stack's keys are in the store, not in the file
    for name in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET",
                 "TEMPORAL_API_KEY", "AUTH_INTERNAL_NOTIFY_KEY"):
        assert name not in values, name
    assert stat.S_IMODE((work / ".env").stat().st_mode) == 0o600
    # UMAMI_URL seeded into the store; so is the Mongo connection, with the generated
    # root password (which is in .env but never printed)
    assert (state / "store" / "UMAMI_URL").read_text() == "http://umami:3000"
    assert values["BC_MONGO_ROOT_PASSWORD"]
    assert (state / "store" / "MONGO_URI").read_text() == (
        f"mongodb://root:{values['BC_MONGO_ROOT_PASSWORD']}@mongodb:27017"
    )
    # nothing generated is printed
    shown = done.stdout + done.stderr
    for name, value in values.items():
        if len(value) >= 16:
            assert value not in shown, name
    assert "abcd-ef01-2345" in shown  # the fingerprint is
    # no temp directory with keys is left behind
    assert not _temp_leftovers(work)


def test_a_second_run_does_not_bootstrap_again(site):
    work, state, _ = site
    done, _ = _run(site)
    assert done.returncode == 0
    before = _dotenv(work)
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("bootstrap-keys" in c for c in calls)
    assert not any("settings-import" in c for c in calls)
    assert _dotenv(work) == before


def test_an_interrupted_new_install_continues_where_it_stopped(site):
    work, state, _ = site
    store = state / "store"
    store.mkdir()
    (store / "AUTH_JWT_SECRET").write_text("x")  # one key made, the rest missing
    done, calls = _run(site, volumes="app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "--fill-missing" in calls[_index(calls, "bootstrap-keys")]


def test_an_upgrade_imports_and_checks_before_the_services_start(site):
    work, state, _ = site
    (work / ".env").write_text(
        "AUTH_JWT_SECRET=" + "j" * 64 + "\nAUTH_AES_HEX_KEY=" + "A" * 43 + "=\n"
        "MASTER_ENCRYPTION_KEYSET=" + "k" * 40 + "\nTEMPORAL_API_KEY=" + "t" * 48 + "\n"
        "AUTH_INTERNAL_NOTIFY_KEY=" + "n" * 48 + "\nPLATFORM_ADMIN_EMAILS=ops@example.test\n"
        "SETTINGS_MASTER_KEY=" + "m" * 64 + "\nUMAMI_APP_SECRET=u\n"
    )
    done, calls = _run(
        site, volumes="mongo-data,app-postgres-data,temporal-postgres-data,umami-db-data"
    )
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("bootstrap-keys" in c for c in calls)
    imp = _index(calls, "settings-import --from-compose-config")
    drift = _index(calls, "settings-drift --from-compose-config")
    assert _index(calls, "alembic") < imp < drift < _index(calls, "up --build")
    values = _dotenv(work)
    # the worker's two copies come from the keys the stack already has
    assert values["API_KEY"] == "t" * 48
    assert values["AES_HEX_KEY"] == "A" * 43 + "="
    # the old values stay in the file until the operator prunes
    assert values["AUTH_JWT_SECRET"] == "j" * 64
    shown = done.stdout + done.stderr
    for secret in ("j" * 64, "t" * 48, "m" * 64):
        assert secret not in shown
    assert "settings-prune" in shown
    # an existing database keeps its internal passwords: nothing is generated for them
    assert "BC_TEMPORAL_DB_PASSWORD" not in values and "BC_UMAMI_DB_PASSWORD" not in values
    assert "BC_MONGO_ROOT_PASSWORD" not in values
    # no MONGO_URI in the files: the original default is seeded, never a new password
    assert (state / "store" / "MONGO_URI").read_text() == "mongodb://root:root@mongodb:27017"


def test_an_upgrade_stops_when_the_import_or_the_comparison_fails(site):
    work, state, _ = site
    (work / ".env").write_text(
        "AUTH_JWT_SECRET=" + "j" * 64 + "\nAUTH_AES_HEX_KEY=" + "A" * 43 + "=\n"
        "MASTER_ENCRYPTION_KEYSET=" + "k" * 40 + "\nSETTINGS_MASTER_KEY=" + "m" * 64 + "\n"
    )
    for flag in ("STUB_IMPORT_FAILS", "STUB_DRIFT_DIFFERS"):
        shutil.rmtree(state / "store", ignore_errors=True)
        (state / "calls.log").unlink(missing_ok=True)
        done, calls = _run(site, volumes="mongo-data", extra={flag: "1"})
        assert done.returncode != 0, flag
        assert not any("up --build" in c for c in calls), flag


def test_a_stack_with_data_and_no_keyset_anywhere_is_refused(site):
    work, state, _ = site
    (work / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    done, calls = _run(site, volumes="mongo-data")
    assert done.returncode != 0
    assert "MASTER_ENCRYPTION_KEYSET is not set" in done.stderr
    assert not any("up --build" in c for c in calls)
    assert not any("bootstrap-keys" in c for c in calls)


def test_a_stack_that_ran_before_without_its_master_key_is_refused(site):
    work, state, _ = site
    (work / ".env").write_text("UMAMI_APP_SECRET=u\nAPP_POSTGRES_PASSWORD=p\n")
    done, calls = _run(site, volumes="mongo-data")
    assert done.returncode != 0
    assert "SETTINGS_MASTER_KEY is not set" in done.stderr
    assert not any("up " in c for c in calls)


def test_subcommands_run_the_host_command_and_generate_nothing(site):
    work, state, _ = site
    (work / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    done, calls = _run(site, "settings-drift")
    assert done.returncode == 0
    assert any("settings-drift --from-compose-config" in c for c in calls)
    assert (work / ".env").read_text() == "SETTINGS_MASTER_KEY=" + "m" * 64 + "\n"
    done, calls = _run(site, "master-key-fingerprint")
    assert done.returncode == 0 and "abcd-ef01-2345" in done.stdout


def test_prune_keeps_what_something_outside_the_store_reads(site):
    work, state, _ = site
    (work / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\nAUTH_JWT_SECRET=x\n")
    done, calls = _run(site, "settings-prune")
    prune = calls[_index(calls, "settings-prune")]
    for name in ("SSO_ENABLED", "MAIL_PASSWORD", "SSO_POLIS_API_KEY"):
        assert f"--keep {name}" in prune
    assert "--keep AUTH_JWT_SECRET" not in prune  # no Typeform deployed
    (state / "calls.log").unlink()
    done, calls = _run(site, "settings-prune", "--typeform")
    prune = calls[_index(calls, "settings-prune")]
    for name in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET"):
        assert f"--keep {name}" in prune


def _upgrade_env(work):
    (work / ".env").write_text(
        "AUTH_JWT_SECRET=" + "j" * 64 + "\nAUTH_AES_HEX_KEY=" + "A" * 43 + "=\n"
        "MASTER_ENCRYPTION_KEYSET=" + "k" * 40 + "\nSETTINGS_MASTER_KEY=" + "m" * 64 + "\n"
    )


def test_a_refused_ordinary_value_is_a_warning_not_a_stop(site):
    """The shipped .env.deployment has http://localhost URLs, which the registry
    refuses: they stay environment values, as they always were."""
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(
        site, volumes="mongo-data", extra={"STUB_IMPORT_REFUSES": "CLIENT_ADMIN_URL bad_scheme"}
    )
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "refused CLIENT_ADMIN_URL bad_scheme" in done.stdout
    assert "stay environment values" in done.stdout
    assert any("up --build" in c for c in calls)


@pytest.mark.parametrize(
    "extra",
    [
        {"STUB_IMPORT_REFUSES": "AUTH_AES_HEX_KEY bad_fernet"},
        {"STUB_IMPORT_REFUSES": "MASTER_ENCRYPTION_KEYSET weak_secret"},
        {"STUB_IMPORT_REFUSES": "STRIPE_SECRET weak_secret"},
        {"STUB_IMPORT_CONFLICT": "1"},
    ],
)
def test_a_refused_key_a_weak_secret_or_a_conflict_stops_the_deploy(site, extra):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes="mongo-data", extra=extra)
    assert done.returncode != 0
    assert "The import stopped" in done.stderr
    assert not any("up --build" in c for c in calls)


def test_a_postgres_that_holds_data_stops_the_deploy_at_the_real_refusal(site):
    """No Mongo volume, no key files, but one response in Postgres: bootstrap-keys
    refuses (stack_has_data); the deploy stops before any service starts, stores
    no keyset, and points at the import. The refusal text is the real one."""
    work, state, _ = site
    done, calls = _run(site, volumes="app-postgres-data", extra={"STUB_PG_RESPONSES": "1"})
    assert done.returncode != 0
    shown = done.stdout + done.stderr
    assert "refused: stack_has_data" in shown  # not hidden
    assert "settings-import" in shown
    assert "STOPPED before any service started" in done.stderr
    assert not any("up --build" in c for c in calls)
    for key in ("MASTER_ENCRYPTION_KEYSET", "AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY"):
        assert not (state / "store" / key).exists(), key
    values = _dotenv(work)
    assert "API_KEY" not in values and "AES_HEX_KEY" not in values
    # nothing was left behind by the one-off export directory
    assert not _temp_leftovers(work)
    # a second run still stops: nothing was recorded that would let it through
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="app-postgres-data", extra={"STUB_PG_RESPONSES": "1"})
    assert done.returncode != 0 and not any("up --build" in c for c in calls)


# --------------------------------------------------------------------------------
# the security-review hardening of the deployment script


def _tail(work, name=".env"):
    return (work / name).read_text()


def test_every_always_on_service_is_started_for_every_preference(site):
    """`up -d NAME...` starts only what it names: the admin service, the jobs worker,
    the document sandbox and the task runner have to be on the list, whatever the
    preference (a docker-compose `up --dry-run` version of this runs in
    test_deployment_config.py)."""
    required = {"admin", "jobs-worker", "document-sandbox", "task-runner", "backend", "auth", "worker", "webapp"}
    for preference, extra in (("", set()), ("both", {"integrations-typeform", "integrations-googleform"}),
                              ("typeform", {"integrations-typeform"}), ("googleform", {"integrations-googleform"})):
        done, calls = _run(site, "print-services", preference)
        assert done.returncode == 0, done.stderr
        listed = set(done.stdout.split())
        assert required <= listed, (preference, required - listed)
        assert extra <= listed
        assert ("integrations-typeform" in listed) == ("integrations-typeform" in extra)
    # and the real start passes exactly that list to `up`
    done, calls = _run(site, "both")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    up = calls[_index(calls, "up --build")]
    for name in required | {"integrations-typeform", "integrations-googleform"}:
        assert f" {name}" in up, name


@pytest.mark.parametrize("value", ['true', '"true"', "'True'", "1", "yes", "on"])
def test_sso_is_read_from_the_root_env_the_way_compose_reads_it(site, value):
    work, _, _ = site
    (work / ".env").write_text(f"export SSO_ENABLED={value}  # on\n")
    done, _ = _run(site, "print-services")
    assert {"polis", "polis-postgres"} <= set(done.stdout.split()), value
    for value in ("false", "", "no"):
        (work / ".env").write_text(f"SSO_ENABLED={value}\n")
        done, _ = _run(site, "print-services")
        assert "polis" not in done.stdout.split()


def test_an_interrupted_first_run_shows_the_fingerprint_and_the_token_notice_later(site):
    work, state, _ = site
    (work / ".env").write_text("PLATFORM_ADMIN_EMAILS=ops@example.test\n")
    done, calls = _run(site, extra={"STUB_ADMIN_HEALTH": "starting"})
    assert done.returncode == 0, done.stderr[-800:]
    assert "First sign-in" not in done.stdout and "did not become healthy" in done.stderr
    assert _dotenv(work)["BC_FIRST_RUN_PENDING"] == "1"
    # the next run finds the keys complete, but still owes the notice
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert not any("bootstrap-keys" in c for c in calls)
    assert "abcd-ef01-2345" in done.stdout and "First sign-in" in done.stdout
    assert "BC_FIRST_RUN_PENDING" not in _dotenv(work)
    # and once shown it is not shown again
    done, _ = _run(site, volumes="mongo-data,app-postgres-data")
    assert "First sign-in" not in done.stdout


def test_an_unreplaced_umami_login_is_fatal_on_a_new_install_and_a_warning_on_an_upgrade(site):
    work, state, _ = site
    done, calls = _run(site, extra={"STUB_UMAMI_FAILS": "1"})
    assert done.returncode != 0
    assert "Umami's built-in login could not be replaced" in done.stderr
    assert sum("exec -T -e UMAMI_NEW_PASSWORD" in c for c in calls) == 3  # tried, then given up
    assert "First sign-in" not in done.stdout
    assert _dotenv(work)["BC_FIRST_RUN_PENDING"] == "1"  # the rerun still owes the notice
    # an upgrade of a running stack only warns
    shutil.rmtree(state / "store", ignore_errors=True)
    _upgrade_env(work)
    done, calls = _run(site, volumes="mongo-data", extra={"STUB_UMAMI_FAILS": "1"})
    assert done.returncode == 0, done.stderr[-800:]
    assert "could not be replaced" in done.stderr


def test_a_stack_found_under_another_project_name_is_refused_not_regenerated(site):
    """COMPOSE_PROJECT_NAME in the root .env is what compose uses (the shell has none
    here): the stack's volumes are looked up under that name, and the passwords of a
    stack that exists are never regenerated."""
    work, state, _ = site
    _upgrade_env(work)
    with open(work / ".env", "a") as fh:
        fh.write("COMPOSE_PROJECT_NAME=Prod_Stack\n")
    volumes = ",".join(f"prod_stack:{v}" for v in ("mongo-data", "app-postgres-data", "temporal-postgres-data", "umami-db-data"))
    done, calls = _run(site, volumes=volumes, drop=("COMPOSE_PROJECT_NAME",))
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    values = _dotenv(work)
    for name in ("BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD", "BC_MONGO_ROOT_PASSWORD"):
        assert name not in values, name
    # compose is told the same name this script used
    assert set((state / "project.log").read_text().split()) == {"prod_stack"}
    assert (state / "store" / "MONGO_URI").read_text() == "mongodb://root:root@mongodb:27017"

    # volumes only under the directory's name while .env names another project: refused
    shutil.rmtree(state / "store")
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="stack:mongo-data,stack:app-postgres-data", drop=("COMPOSE_PROJECT_NAME",))
    assert done.returncode != 0
    assert "Volumes of a stack named 'stack' exist" in done.stderr
    assert not calls or not any("up " in c for c in calls)  # refused before anything ran


def test_no_database_password_is_generated_while_any_volume_of_the_stack_exists(site):
    work, state, _ = site
    done, calls = _run(site, volumes="app-postgres-data")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    values = _dotenv(work)
    for name in ("BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD", "BC_MONGO_ROOT_PASSWORD"):
        assert name not in values, name
        assert f"NOTE: {name} is not set" in done.stdout
    # the Mongo of a stack that has volumes keeps the original default, and the store
    # is told so (no new password that would not match)
    assert (state / "store" / "MONGO_URI").read_text() == "mongodb://root:root@mongodb:27017"
    # a stack with no volume at all gets all three
    other = site[0].parent / "stack2"
    other.mkdir()
    for item in ("deploy.sh", "docker-compose.deployment.yml", ".env.deployment"):
        shutil.copy(work / item, other / item)
    shutil.copytree(work / "deploy", other / "deploy")
    shutil.copytree(work / "postgres", other / "postgres")
    state2 = site[0].parent / "state2"
    state2.mkdir()
    done, _ = _run((other, state2, {**site[2], "STUB_STATE": str(state2)}), drop=("COMPOSE_PROJECT_NAME",))
    assert done.returncode == 0
    for name in ("BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD", "BC_MONGO_ROOT_PASSWORD"):
        assert _dotenv(other).get(name), name


@pytest.mark.parametrize("where", [".env", ".env.deployment"])
def test_a_new_stack_is_refused_when_a_mongo_the_script_cannot_look_into_is_configured(site, where):
    """bootstrap-keys' one-off container has no Mongo credentials, so the Mongo half of
    'does this stack hold data' is decided by deploy.sh: a configured MONGO_URI (an
    external Mongo) with no keys anywhere is refused before any key is generated."""
    work, state, _ = site
    path = work / where
    path.write_text(path.read_text() + "MONGO_URI=mongodb://u:p@db.example.test:27017\n" if path.exists() else "MONGO_URI=mongodb://u:p@db.example.test:27017\n")
    done, calls = _run(site)
    assert done.returncode != 0
    assert "may hold data" in done.stderr and "cannot look" in done.stderr
    assert not any("bootstrap-keys" in c or "up --build" in c for c in calls)
    assert not (state / "store" / "MASTER_ENCRYPTION_KEYSET").exists()


def test_a_mongo_volume_without_keys_is_refused_before_bootstrap(site):
    work, state, _ = site
    (work / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    done, calls = _run(site, volumes="mongo-data")
    assert done.returncode != 0 and not any("bootstrap-keys" in c for c in calls)


def test_the_service_env_files_hold_only_what_each_service_reads(site):
    work, state, _ = site
    (work / ".env.deployment").write_text(
        "STRIPE_SECRET=sk_live_dummy\nGOOGLE_CLIENT_SECRET=gsecret\nMAIL_PASSWORD=mailpw\n"
        "OAUTHLIB_RELAX_TOKEN_SCOPE=1\nSTRIPE_WEBHOOK_SECRET=whsec\nMASTER_ENCRYPTION_KEYSET=\n"
        "UNSPLASH_ACCESS_KEY=unsplash\nGOOGLE_CLIENT_ID=gid\nGOOGLE_PICKER_API_KEY=\n"
        "export UMAMI_SCRIPT_URL=http://host:3003/script.js\nNEXT_PUBLIC_API_ENDPOINT_HOST=http://api\n"
        "ELASTIC_APM_SERVER_URL=http://apm\nCUSTOM_DOMAIN_ASSERTION_KEYS='k1,k2'\n"
        "SERVER_URL=http://backend:8000/api/v1\nCOOKIE_DOMAIN=example.test\nNAMESPACE=default\n"
        "TYPEFORM_CLIENT_ID=tid\nTYPEFORM_CLIENT_SECRET=tsecret\nUMAMI_PASSWORD=\n"
    )
    done, _ = _run(site, "typeform")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    webapp = _tail(work, ".env.webapp")
    worker = _tail(work, ".env.worker")
    typeform = _tail(work, ".env.typeform")
    for text, name in ((webapp, "webapp"), (worker, "worker"), (typeform, "typeform")):
        for secret in ("sk_live_dummy", "gsecret", "mailpw", "whsec"):
            assert secret not in text, (name, secret)
        assert "MASTER_ENCRYPTION_KEYSET" not in text and "AUTH_JWT_SECRET" not in text
        assert stat.S_IMODE((work / f".env.{name}").stat().st_mode) == 0o600
    # what the webapp reads, empty values left out, `export` dropped, quotes kept
    assert "UNSPLASH_ACCESS_KEY=unsplash" in webapp and "GOOGLE_CLIENT_ID=gid" in webapp
    assert "UMAMI_SCRIPT_URL=http://host:3003/script.js" in webapp and "GOOGLE_PICKER_API_KEY" not in webapp
    assert "NEXT_PUBLIC_API_ENDPOINT_HOST=http://api" in webapp and "ELASTIC_APM_SERVER_URL=http://apm" in webapp
    assert "CUSTOM_DOMAIN_ASSERTION_KEYS='k1,k2'" in webapp
    assert "TYPEFORM_CLIENT" not in webapp
    assert not any(line.startswith(("SERVER_URL=", "COOKIE_DOMAIN=")) for line in webapp.splitlines())
    assert "COOKIE_DOMAIN=example.test" in worker and "SERVER_URL=http://backend:8000/api/v1" in worker
    assert "NAMESPACE=default" in worker and "UNSPLASH" not in worker and "TYPEFORM" not in worker
    assert "TYPEFORM_CLIENT_SECRET=tsecret" in typeform and "UNSPLASH" not in typeform
    # a new stack's Mongo connection is written for the Typeform service (it needs it)
    assert _dotenv(work)["BC_MONGO_ROOT_PASSWORD"] in typeform
    # never overwritten by a later run
    (work / ".env.webapp").write_text("MINE=1\n")
    (work / ".env.worker").chmod(0o644)
    _run(site, volumes="mongo-data,app-postgres-data")
    assert (work / ".env.webapp").read_text() == "MINE=1\n"
    assert stat.S_IMODE((work / ".env.worker").stat().st_mode) == 0o600


def test_a_symlinked_service_env_file_is_refused(site):
    work, _, _ = site
    (work / "elsewhere").write_text("")
    (work / ".env.webapp").symlink_to(work / "elsewhere")
    done, calls = _run(site)
    assert done.returncode != 0 and "symbolic link" in done.stderr
    assert (work / "elsewhere").read_text() == ""
    assert not any("up --build" in c for c in calls)


def test_env_files_are_owner_only_before_anything_is_added(site):
    work, state, _ = site
    (work / ".env").write_text("PLATFORM_ADMIN_EMAILS=ops@example.test")  # 644, no newline
    (work / ".env").chmod(0o644)
    (work / ".env.deployment").chmod(0o644)
    done, _ = _run(site)
    assert done.returncode == 0
    assert stat.S_IMODE((work / ".env").stat().st_mode) == 0o600
    assert stat.S_IMODE((work / ".env.deployment").stat().st_mode) == 0o600
    # the last line had no newline: the first generated value is on a line of its own
    assert _dotenv(work)["PLATFORM_ADMIN_EMAILS"] == "ops@example.test"


def test_an_export_prefix_and_quotes_do_not_hide_a_value_from_the_checks(site):
    work, state, _ = site
    (work / ".env").write_text('export SETTINGS_MASTER_KEY="' + "m" * 64 + '"\n')
    done, _ = _run(site)
    assert done.returncode == 0
    assert _tail(work).count("SETTINGS_MASTER_KEY") == 1  # not a second, winning line


@pytest.mark.parametrize("name", ["BC_APP_PASSWORD", "BC_AUTH_PASSWORD", "BC_GOOGLE_PASSWORD", "BC_UMAMI_DB_PASSWORD", "BC_MONGO_ROOT_PASSWORD"])
def test_a_password_that_would_break_a_url_is_refused(site, name):
    work, _, _ = site
    (work / ".env").write_text(f"{name}=pa@ss/word\n")
    done, calls = _run(site)
    assert done.returncode != 0 and name in done.stderr
    assert not any("up --build" in c for c in calls)


def test_settings_env_export_refuses_an_existing_file_and_a_dangling_link(site):
    work, state, _ = site
    (work / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    target = work / "nowhere" / "stolen.env"
    (work / "link.env").symlink_to(target)
    (work / "nowhere").mkdir()
    done, _ = _run(site, "settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "link.env")
    assert done.returncode != 0 and "refused" in done.stderr
    assert not target.exists()  # nothing was written through the link
    (work / "taken.env").write_text("x")
    done, _ = _run(site, "settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "taken.env")
    assert done.returncode != 0 and (work / "taken.env").read_text() == "x"


def test_admin_settings_in_env_deployment_are_flagged_as_ineffective(site):
    work, _, _ = site
    (work / ".env.deployment").write_text("ADMIN_ALLOWED_IPS=10.0.0.0/8\n")
    done, _ = _run(site)
    assert "ADMIN_ALLOWED_IPS is set in .env.deployment but the admin service ignores it" in done.stdout
    (work / ".env").write_text("ADMIN_TRUSTED_PROXIES=10.0.0.1\n")
    done, _ = _run(site)
    assert "reverse proxy in front of the admin portal" in done.stdout


def test_volumes_under_both_names_are_not_a_mismatch(site):
    """The name compose uses has its own volumes: a second, older stack under the
    directory's name is none of this run's business."""
    work, state, _ = site
    _upgrade_env(work)
    with open(work / ".env", "a") as fh:
        fh.write("COMPOSE_PROJECT_NAME=prod_stack\n")
    volumes = "prod_stack:mongo-data,prod_stack:app-postgres-data,stack:mongo-data"
    done, _ = _run(site, volumes=volumes, drop=("COMPOSE_PROJECT_NAME",))
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert "Volumes of a stack named" not in done.stderr


PLUGIN_PREFIX = textwrap.dedent(
    '''\
    import os, sys
    if sys.argv[1:2] == ["compose"]:
        # `docker compose` (the plugin): the same stand-in as `docker-compose`
        if sys.argv[2:3] == ["--help"]:
            sys.exit(0)
        os.execv(sys.executable, [sys.executable, os.environ["STUB_COMPOSE"], *sys.argv[2:]])
    '''
)
HOST_TOOLS = (
    "bash", "sh", "openssl", "grep", "egrep", "sed", "awk", "tail", "head", "tr", "cat", "cp", "chmod", "mv", "rm",
    "mktemp", "date", "seq", "sleep", "id", "basename", "dirname", "wc", "sort", "uniq", "env", "stat", "cut", "ls",
    "tee", "readlink", "mkdir", "touch", "printf", "true", "false", "test", "expr", "xargs", "find", "ln",
)


def test_a_host_with_only_the_compose_plugin_deploys(site, tmp_path):
    """`docker compose` is two words: a quoted "$cmd" of it is one command name and was
    never found, so deploy.sh did nothing on a host without the standalone `docker-compose`
    binary. Here that binary does not exist and the plugin is a stand-in for it."""
    work, state, env = site
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    plugin = tmp_path / "compose-stub"
    (bin_dir / "docker-compose").rename(plugin)
    docker = bin_dir / "docker"
    head, _, rest = docker.read_text().partition("\n")
    docker.write_text(head + "\n" + PLUGIN_PREFIX + rest)
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in HOST_TOOLS:
        found = shutil.which(name)
        if found:
            (tools / name).symlink_to(found)
    assert not shutil.which("docker-compose", path=f"{bin_dir}{os.pathsep}{tools}")
    env = {**env, "PATH": f"{bin_dir}{os.pathsep}{tools}", "STUB_COMPOSE": str(plugin)}
    done, calls = _run((work, state, env))
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "command not found" not in done.stderr
    assert any("bootstrap-keys" in c for c in calls)
    assert any("up --build" in c for c in calls)
