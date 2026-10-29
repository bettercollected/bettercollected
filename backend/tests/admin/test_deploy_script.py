"""deploy.sh against a stand-in for docker compose: the order of the steps and
what ends up in the root .env, for a new install and for an upgrade. No Docker
needed. The stand-in records every call, answers `settings-history` from a small
state directory, and writes what `bootstrap-keys --export-worker` would write."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import time
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

    def term_deploy_on(verb):
        # STUB_SIGNAL_ON=<verb>: TERM to the deploy.sh process alone (not its group), once, when
        # the container for that verb starts; STUB_HANG_ON=<verb>: the container then keeps running
        import signal, time
        pidfile = os.environ.get("STUB_SIGNAL_PIDFILE")
        marker = state / "signalled"
        if os.environ.get("STUB_SIGNAL_ON") == verb and pidfile and not marker.exists():
            marker.write_text("")
            os.kill(int(pathlib.Path(pidfile).read_text()), signal.SIGTERM)
            time.sleep(0.3)
        if os.environ.get("STUB_HANG_ON") == verb:
            time.sleep(60)

    def mount(suffix):
        return pathlib.Path([a for a in argv if a.endswith(suffix)][0].rsplit(":", 1)[0])

    if "run" in argv and "backend.admin" in argv:
        cmd = argv[argv.index("backend.admin") + 1:]
        verb = cmd[0]
        stdin = "" if sys.stdin.isatty() else sys.stdin.read()
        if verb == "settings-history":
            print("versions=%d" % (1 if has(cmd[1]) else 0))
        elif verb == "bootstrap-keys":
            term_deploy_on(verb)
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
            if "--fill-missing" not in cmd and "--export-worker-only" not in cmd and has("AUTH_JWT_SECRET"):
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
                    if "STUB_WORKER_ENV_TEXT" in os.environ:
                        f.write(os.environ["STUB_WORKER_ENV_TEXT"])
                    else:
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
        elif verb == "settings-prune":
            # the container reads copies of .env and .env.deployment mounted at /work
            term_deploy_on(verb)
            if os.environ.get("STUB_PRUNE_FAILS"):
                print("refused: stand-in failure", file=sys.stderr); sys.exit(1)
            print("prune=1 keep=0")
            if "--apply" in cmd and "--swap" in cmd:
                work = mount(":/work")
                for name in (".env", ".env.deployment"):
                    if (work / name).exists():
                        text = (work / name).read_text()
                        (work / (name + ".pre-v4.stub")).write_text(text)
                        (work / name).write_text("".join(l for l in text.splitlines(True) if not l.startswith("AUTH_JWT_SECRET")))
        elif verb == "settings-env-export":
            term_deploy_on(verb)
            if os.environ.get("STUB_EXPORT_FAILS"):
                print("refused: stand-in failure", file=sys.stderr); sys.exit(1)
            (mount(":/out") / "export.env").write_text("UMAMI_PASSWORD=DUMMY-exported-secret\\n")
            print("exported=1 (values are not shown)")
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
        if os.environ.get("STUB_UMAMI_ROTATES"):
            # the built-in login is there, and the rotation (which carries the new password by name) works
            if "-e" not in argv:
                print("default_login=yes")
        elif os.environ.get("STUB_UMAMI_FAILS"):
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


# `cp`, `cat` and `chmod` as deploy.sh calls them: they pass through, but they can send TERM to
# deploy.sh first, when the one named in STUB_SIGNAL_CMD is called with a path inside the scratch
# directory (a signal at a chosen point of a step that holds a secret copy).
HOOK_STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import os, sys, pathlib, signal, time
    name = pathlib.Path(sys.argv[0]).name
    pidfile, scratch = os.environ.get("STUB_SIGNAL_PIDFILE"), os.environ.get("STUB_SIGNAL_SCRATCH")
    marker = pathlib.Path(os.environ["STUB_STATE"]) / "signalled"
    if (os.environ.get("STUB_SIGNAL_CMD") == name and pidfile and scratch and not marker.exists()
            and any(a.startswith(scratch) for a in sys.argv[1:])):
        marker.write_text("")
        os.kill(int(pathlib.Path(pidfile).read_text()), signal.SIGTERM)
        time.sleep(0.3)
    os.execv(os.environ["STUB_REAL_" + name.upper()], [name] + sys.argv[1:])
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
    """The shipped .env.deployment.example has http://localhost URLs, which the registry
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


def test_a_fresh_checkout_gets_env_deployment_from_the_template(site):
    """.env.deployment is not tracked: on a fresh checkout deploy.sh creates it from
    .env.deployment.example (owner-only, said on the console), and the per-service env
    files are written from it."""
    work, state, _ = site
    (work / ".env.deployment").unlink()
    shutil.copy(ROOT / ".env.deployment.example", work / ".env.deployment.example")
    (work / ".env.deployment.example").chmod(0o644)
    done, calls = _run(site)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert "Created .env.deployment from .env.deployment.example" in done.stdout
    created = work / ".env.deployment"
    assert created.read_text() == (ROOT / ".env.deployment.example").read_text()
    assert stat.S_IMODE(created.stat().st_mode) == 0o600
    assert stat.S_IMODE((work / ".env.deployment.example").stat().st_mode) == 0o644  # left alone
    assert "SERVER_URL=http://backend:8000/api/v1" in _tail(work, ".env.worker")
    assert "UMAMI_PASSWORD" not in _tail(work, ".env.webapp")  # empty values are left out
    assert any("up --build" in c for c in calls)
    # never overwritten afterwards, and not announced again
    created.write_text("MINE=1\n")
    done, _ = _run(site, volumes="mongo-data,app-postgres-data")
    assert created.read_text() == "MINE=1\n"
    assert "Created .env.deployment" not in done.stdout


def test_print_services_creates_no_env_deployment(site):
    work, _, _ = site
    (work / ".env.deployment").unlink()
    shutil.copy(ROOT / ".env.deployment.example", work / ".env.deployment.example")
    done, _ = _run(site, "print-services")
    assert done.returncode == 0 and "backend" in done.stdout.split()
    assert not (work / ".env.deployment").exists()


def test_a_missing_template_or_a_dangling_env_deployment_link_is_refused(site):
    work, state, _ = site
    (work / ".env.deployment").unlink()
    done, calls = _run(site)
    assert done.returncode != 0 and ".env.deployment.example" in done.stderr
    assert calls == [] and not (work / ".env.deployment").exists()
    shutil.copy(ROOT / ".env.deployment.example", work / ".env.deployment.example")
    (work / ".env.deployment").symlink_to(work / "nowhere" / "env")
    done, calls = _run(site)
    assert done.returncode != 0 and "symbolic link" in done.stderr
    assert calls == [] and not (work / "nowhere").exists()


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


# --- the secret-scratch guard (guard_arm / guard_run / guard_disarm) --------------------------


def _armed_regions(trace: str):
    """The traced lines between each `trap guard_cleanup EXIT` and the next `trap - EXIT INT TERM HUP`
    (PS4 is `+<subshell level>+ `, the first character repeated for a command substitution)."""
    lines = trace.splitlines()
    regions, start = [], None
    for number, line in enumerate(lines):
        if line.endswith("+ trap guard_cleanup EXIT"):
            assert start is None, "armed twice"
            start = number
        elif line.endswith("+ trap - EXIT INT TERM HUP"):
            assert start is not None, "disarmed without arming"
            regions.append(lines[start:number])
            start = None
    assert start is None, "armed and never disarmed"
    return regions


def _trace_of(site, tmp_path, args=(), extra=None, volumes=""):
    work, state, env = site
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    full = {**env, "STUB_VOLUMES": volumes, "BC_DEPLOY_ADMIN_WAIT_SECONDS": "2", "BC_DEPLOY_RETRY_SLEEP": "0",
            "TMPDIR": str(scratch), "PS4": "+${BASH_SUBSHELL}+ ", **(extra or {})}
    return subprocess.run(["bash", "-x", "deploy.sh", *args], cwd=work, env=full, capture_output=True, text=True,
                          timeout=120)


def _nested(region):
    """Commands run in a substitution (`++N+`) or in a subshell (`+N+`, N > 0): the container job is the one
    asynchronous command the guard starts on purpose."""
    return [l for l in region if re.match(r"^\++[1-9]\+ |^\+\+", l) and "docker-compose" not in l]


def _prune_trace(site, tmp_path):
    (site[0] / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\nAUTH_JWT_SECRET=DUMMY-jwt\n")
    return _trace_of(site, tmp_path, ["settings-prune", "--apply", "--swap"])


def _export_trace(site, tmp_path):
    (site[0] / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    return _trace_of(site, tmp_path, ["settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env"])


def _umami_trace(site, tmp_path):
    (site[0] / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\n")
    return _trace_of(site, tmp_path, extra={"STUB_UMAMI_ROTATES": "1"})


def _new_install_trace(site, tmp_path):
    return _trace_of(site, tmp_path)


def _worker_keys_trace(site, tmp_path):
    """A stack whose store is complete but whose .env lost the Temporal worker's two keys."""
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    _drop_worker_keys(site[0])
    return _trace_of(site, tmp_path, volumes="mongo-data,app-postgres-data")


def _drop_worker_keys(work):
    kept = [l for l in (work / ".env").read_text().splitlines(True) if not l.startswith(("API_KEY=", "AES_HEX_KEY="))]
    (work / ".env").write_text("".join(kept))


@pytest.mark.parametrize("scenario", [_prune_trace, _export_trace, _umami_trace, _new_install_trace, _worker_keys_trace])
def test_no_command_substitution_runs_while_any_secret_scratch_path_is_guarded(site, tmp_path, scenario):
    """Between arming the guard and disarming it, every traced command runs at the top level (a
    command substitution would show as `++`): for every step that holds a secret in a scratch file or
    directory (the settings prune and export, the Umami blanking, the worker keys, the .env copies)."""
    done = scenario(site, tmp_path)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-800:]
    regions = _armed_regions(done.stderr)
    assert regions
    for region in regions:
        assert not _nested(region), _nested(region)


def test_a_new_install_guards_the_bootstrap_directory_and_every_env_copy(site, tmp_path):
    done = _new_install_trace(site, tmp_path)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-800:]
    regions = _armed_regions(done.stderr)
    [boot] = [r for r in regions if any("--export-worker /out/worker.env" in l for l in r)]
    assert any("guard_run" in l for l in boot) and any("read_worker_env" in l for l in boot)
    # the three service env files and the .env edits of a first run
    assert sum(any("+ mv .env." in l for l in r) for r in regions) >= 4


def test_the_worker_keys_export_is_guarded_and_merged_after_the_directory_is_gone(site, tmp_path):
    done = _worker_keys_trace(site, tmp_path)
    assert done.returncode == 0, done.stderr[-800:]
    regions = _armed_regions(done.stderr)
    [export] = [r for r in regions if any("--export-worker-only" in l for l in r)]
    assert any("guard_run" in l for l in export)
    assert not any("env_put" in l or "merge_worker_env" in l for l in export)
    values = _dotenv(site[0])
    assert values.get("API_KEY") and values.get("AES_HEX_KEY")
    assert not list((tmp_path / "scratch").iterdir())


def test_the_guarded_source_has_no_pipeline_substitution_or_subshell_and_one_background_job():
    """What an execution trace cannot show: between `guard_arm "` and the next `guard_disarm` the
    source has no command substitution, process substitution, pipe or subshell, and the guard's
    job is the only background job the script starts (guard_cleanup's `$!` fallback depends on it)."""
    source = (ROOT / "deploy.sh").read_text().splitlines()
    inside, checked, armed = False, 0, 0
    for number, raw in enumerate(source, 1):
        line = raw.split("#", 1)[0] if not re.search(r"['\"].*#.*['\"]", raw) else raw
        if re.search(r'guard_arm "\$', line):
            assert not inside, f"deploy.sh:{number}: armed twice"
            inside = True
            armed += 1
            continue
        if re.search(r"^\s*guard_disarm\b", line):
            inside = False
            continue
        if not inside or not line.strip():
            continue
        checked += 1
        assert not re.search(r"\$\((?!\()|`|<\(|>\(", line), f"deploy.sh:{number}: {raw.strip()}"
        assert not re.search(r"(?<![|])\|(?![|])", line), f"deploy.sh:{number}: {raw.strip()}"
        assert not re.search(r"^\s*\(|[;&|]\s*\(", line), f"deploy.sh:{number}: {raw.strip()}"
    # env_unset, service_env_file, the worker keys, bootstrap, Umami, prune, export
    assert not inside and armed == 7 and checked > 40
    background = [n for n, l in enumerate(source, 1) if re.search(r"[^&]&\s*$", l.split("#", 1)[0])]
    assert len(background) == 1, background


def _term_the_script_alone(site, scratch, args, extra=None, volumes="", wait=20):
    """Run `deploy.sh ARGS` with a stand-in that sends TERM to the script's own process (as
    `kill <pid>` does) at a chosen point. Returns (status, stdout, stderr, seconds); the status
    is None when the script was still running `wait` seconds later."""
    import signal
    work, state, env = site
    pidfile = state / "deploy.pid"
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    for name in ("cp", "cat"):
        (bin_dir / name).write_text(HOOK_STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        (bin_dir / name).chmod(0o755)
    full = {**env, "STUB_VOLUMES": volumes, "BC_DEPLOY_ADMIN_WAIT_SECONDS": "2", "BC_DEPLOY_RETRY_SLEEP": "0",
            "TMPDIR": str(scratch), "STUB_SIGNAL_PIDFILE": str(pidfile), "STUB_SIGNAL_SCRATCH": str(scratch),
            "STUB_REAL_CP": shutil.which("cp"), "STUB_REAL_CAT": shutil.which("cat"), **(extra or {})}
    started = time.monotonic()
    proc = subprocess.Popen(["bash", "-c", 'echo $$ > "$STUB_SIGNAL_PIDFILE"; exec bash deploy.sh "$@"', "x", *args],
                            cwd=work, env=full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=wait)
        return proc.returncode, out, err, time.monotonic() - started
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return None, out, err, time.monotonic() - started


SECRET_ENV = "SETTINGS_MASTER_KEY=" + "m" * 64 + "\nAUTH_JWT_SECRET=DUMMY-jwt-secret\n"


def _scratch(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    return scratch


def _nothing_secret_shown(site, out, err):
    seen = out + err + (site[1] / "calls.log").read_text()
    for secret in ("DUMMY-jwt-secret", "DUMMY-exported-secret", "DUMMY-old-umami", "m" * 64):
        assert secret not in seen


SETTINGS_STEPS = {
    "prune": (["settings-prune", "--apply", "--swap"], "settings-prune"),
    "export": (["settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env"], "settings-env-export"),
}


@pytest.mark.parametrize("step", ["prune", "export"])
def test_a_term_to_the_script_alone_while_the_settings_container_runs_ends_it_at_once(site, tmp_path, step):
    """The container reads (prune) or writes (export) secrets in a private directory. A signal
    that reaches only deploy.sh must end it at once, stop the container and remove the directory:
    bash runs a trap only after a foreground command ends, so the container is a background job."""
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    args, verb = SETTINGS_STEPS[step]
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, args, extra={"STUB_SIGNAL_ON": verb, "STUB_HANG_ON": verb})
    assert status == 143, (status, out[-500:], err[-500:])
    assert seconds < 15
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert not (work / "out.env").exists() and (work / ".env").read_text() == SECRET_ENV
    assert not _temp_leftovers(work)
    _nothing_secret_shown(site, out, err)


def test_a_term_while_the_prune_copies_the_secret_files_still_runs_the_trap(site, tmp_path):
    """TERM lands during the part before the container (the copy of .env into the private
    directory): the handler must run, not be dropped, and the directory must go."""
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, ["settings-prune", "--apply", "--swap"], extra={"STUB_SIGNAL_CMD": "cp"})
    assert status == 143, (status, out[-500:], err[-500:])
    assert "trap:" not in err and "unexpected EOF" not in err
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert (work / ".env").read_text() == SECRET_ENV  # the container never ran
    assert not (state / "calls.log").exists() or "settings-prune" not in (state / "calls.log").read_text()


def test_a_term_while_a_copy_of_env_deployment_is_blanked_still_runs_the_trap_and_removes_it(site, tmp_path):
    """The Umami blanking edits a copy of .env.deployment in a private directory: a signal while it
    exists must remove the copy, not leave the file behind."""
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\n")
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, [], extra={"STUB_UMAMI_ROTATES": "1", "STUB_SIGNAL_CMD": "cat"})
    assert status == 143, (status, out[-500:], err[-500:])
    assert "trap:" not in err and "unexpected EOF" not in err
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert (state / "signalled").exists() and (work / ".env.deployment").read_text() == "UMAMI_PASSWORD=\n"
    _nothing_secret_shown(site, out, err)


def test_a_term_to_the_script_alone_while_the_new_stacks_keys_are_generated_ends_it_at_once(site, tmp_path):
    """bootstrap-keys writes the worker's keys into a private directory: the container is a guarded
    background job, so the signal ends the script at once, stops it and removes the directory."""
    work, state, _ = site
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, [], extra={"STUB_SIGNAL_ON": "bootstrap-keys", "STUB_HANG_ON": "bootstrap-keys"})
    assert status == 143, (status, out[-500:], err[-500:])
    assert seconds < 15
    assert "trap:" not in err and "unexpected EOF" not in err
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert not _temp_leftovers(work)
    values = _dotenv(work)
    assert "API_KEY" not in values and "AES_HEX_KEY" not in values and "BC_FIRST_RUN_PENDING" not in values
    assert "up --build" not in (state / "calls.log").read_text()


def test_a_term_to_the_script_alone_while_the_worker_keys_are_exported_ends_it_at_once(site, tmp_path):
    work, state, _ = site
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    _drop_worker_keys(work)
    (state / "calls.log").unlink()
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, [], volumes="mongo-data,app-postgres-data",
        extra={"STUB_SIGNAL_ON": "bootstrap-keys", "STUB_HANG_ON": "bootstrap-keys"})
    assert status == 143, (status, out[-500:], err[-500:])
    assert seconds < 15
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert "--export-worker-only" in (state / "calls.log").read_text()
    assert "API_KEY" not in _dotenv(work)


def test_the_worker_keys_are_merged_into_env_as_grep_found_them(site):
    """The exported file is read without grep now (no pipeline while the guard is armed): the last
    non-empty assignment of each key, the value after the first `=`, and a missing key fails as before
    (the key that was found is kept)."""
    work, state, _ = site
    text = "API_KEY=first\nAPI_KEY=\nAPI_KEY=a=b==\nOTHER=x\nAES_HEX_KEY=\nAES_HEX_KEY=aes value\nAES_HEX_KEY="
    done, _ = _run(site, extra={"STUB_WORKER_ENV_TEXT": text})
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    values = _dotenv(work)
    assert values["API_KEY"] == "a=b==" and values["AES_HEX_KEY"] == "aes value"

    shutil.rmtree(state / "store")
    (work / ".env").unlink()
    done, _ = _run(site, extra={"STUB_WORKER_ENV_TEXT": "API_KEY=only-this\nAES_HEX_KEY=\n"})
    assert done.returncode != 0
    assert "The worker key AES_HEX_KEY is missing from the bootstrap output." in done.stderr
    assert "Generating the stack's keys failed" in done.stderr
    assert _dotenv(work)["API_KEY"] == "only-this" and "AES_HEX_KEY" not in _dotenv(work)
    assert not _temp_leftovers(work)


# --- the guard around the .env edits, run on the functions alone ---------------------------

GUARDED_FUNCTIONS = ("guard_cleanup", "guard_arm", "guard_disarm", "file_assigns", "env_unset", "env_put",
                     "dotenv_unquote", "service_env_file")


def _functions(*names):
    """The source of deploy.sh's functions NAMES (and the guard's variables), to run them alone."""
    text = (ROOT / "deploy.sh").read_text()
    out = ['guard_path=""\nguard_pid=""\nguard_started=""\n']
    for name in names:
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.S | re.M)
        if not found and name.startswith("guard_"):
            continue  # a deploy.sh without the guard: its functions then run unguarded
        assert found, name
        out.append(found.group(0))
    return "".join(out)


def _functions_run(site, script, extra=None, popen=False):
    work, state, env = site
    full = {**env, **(extra or {})}
    argv = ["bash", "-c", 'echo $$ > "${STUB_SIGNAL_PIDFILE:-/dev/null}"\numask 077\n' + _functions(*GUARDED_FUNCTIONS) + script]
    if popen:
        return subprocess.Popen(argv, cwd=work, env=full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
    return subprocess.run(argv, cwd=work, env=full, capture_output=True, text=True, timeout=60)


def _stand_in(site, name, body):
    bin_dir = Path(site[2]["PATH"].split(os.pathsep)[0])
    (bin_dir / name).write_text(body)
    (bin_dir / name).chmod(0o755)


def test_a_failing_mv_makes_env_unset_and_env_put_fail_and_still_removes_the_copy(site):
    """The guard's own disarm must not hide the step's status: with `mv` failing, env_unset
    returns non-zero, `env_put ... || return 1` propagates it, and the copy of .env is gone."""
    work, _, _ = site
    _stand_in(site, "mv", "#!/bin/sh\nexit 1\n")
    (work / ".env").write_text("A=1\nB=2\n")
    done = _functions_run(site, 'env_unset A; echo "unset=$?"\nenv_put B 3 || echo "put failed"\n')
    assert "unset=1" in done.stdout and "put failed" in done.stdout, (done.stdout, done.stderr)
    assert (work / ".env").read_text() == "A=1\nB=2\n"
    assert not _temp_leftovers(work)


def test_a_failing_mv_makes_service_env_file_fail_and_removes_its_scratch_file(site):
    work, _, _ = site
    _stand_in(site, "mv", "#!/bin/sh\nexit 1\n")
    (work / ".env.deployment").write_text("FOO=1\n")
    done = _functions_run(site, 'service_env_file .env.webapp FOO; echo "rc=$?"\n')
    assert "rc=1" in done.stdout, (done.stdout, done.stderr)
    assert not (work / ".env.webapp").exists() and not _temp_leftovers(work)


def test_a_chmod_that_fails_does_not_stop_service_env_file(site):
    """Some bind mounts (vfat, CIFS) refuse chmod; the file is already 600 from the umask, so the
    deploy carries on as it did before the guard (a failed write or rename still stops it, see
    the failing-mv test)."""
    work, _, _ = site
    _stand_in(site, "chmod", "#!/bin/sh\nexit 1\n")
    (work / ".env.deployment").write_text("FOO=1\n")
    done = _functions_run(site, 'service_env_file .env.webapp FOO; echo "rc=$?"\n')
    assert "rc=0" in done.stdout, (done.stdout, done.stderr)
    assert (work / ".env.webapp").read_text() == "FOO=1\n"
    assert oct((work / ".env.webapp").stat().st_mode & 0o777) == "0o600"
    assert not _temp_leftovers(work)


def _term_during_chmod(site, script):
    """Run the functions with a `chmod` stand-in that sends TERM to the script's own process when
    it touches a `.env.*` scratch file; returns (status, stdout, stderr)."""
    import signal
    work, state, env = site
    _stand_in(site, "chmod", HOOK_STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    proc = _functions_run(site, script, popen=True, extra={
        "STUB_SIGNAL_PIDFILE": str(state / "pid"), "STUB_SIGNAL_SCRATCH": ".env.", "STUB_SIGNAL_CMD": "chmod",
        "STUB_REAL_CHMOD": shutil.which("chmod")})
    try:
        out, err = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return None, out, err
    return proc.returncode, out, err


def test_a_term_while_env_unset_holds_its_copy_of_env_runs_the_trap_and_leaves_env_alone(site):
    work, _, _ = site
    (work / ".env").write_text("A=1\nSECRET=DUMMY-secret\n")
    status, out, err = _term_during_chmod(site, "env_unset A\necho survived\n")
    assert status == 143 and "survived" not in out, (status, out, err)
    assert "trap:" not in err and "unexpected EOF" not in err
    assert (work / ".env").read_text() == "A=1\nSECRET=DUMMY-secret\n"
    assert not _temp_leftovers(work)


def test_a_term_while_service_env_file_holds_its_scratch_file_runs_the_trap_and_creates_nothing(site):
    work, _, _ = site
    (work / ".env.deployment").write_text("FOO=DUMMY-secret\n")
    status, out, err = _term_during_chmod(site, "service_env_file .env.webapp FOO\necho survived\n")
    assert status == 143 and "survived" not in out, (status, out, err)
    assert not (work / ".env.webapp").exists() and not _temp_leftovers(work)


def test_env_unset_and_env_put_rewrite_an_awkward_env_byte_for_byte(site):
    work, _, _ = site
    (work / ".env").write_bytes(
        b"# comment A=1\n"
        b"A=1\r\n"
        b'export A = "two words"\n'
        b"  A =x\n"
        b"B=has=equals and $dollar and \\back\\slash\n"
        b"C=\n"
        b'D="quoted # not comment"\n'
        b"A_B=keep\n"
        b"E=crlf\r\n"
        b"B=again\n"
        b"A=last of the duplicates\n"
        b"tail=no newline at the end"
    )
    done = _functions_run(site, "env_unset A && echo ok\n")
    assert done.returncode == 0 and "ok" in done.stdout, done.stderr
    expected = (
        b"# comment A=1\n"
        b"B=has=equals and $dollar and \\back\\slash\n"
        b"C=\n"
        b'D="quoted # not comment"\n'
        b"A_B=keep\n"
        b"E=crlf\r\n"
        b"B=again\n"
        b"tail=no newline at the end\n"
    )
    assert (work / ".env").read_bytes() == expected
    assert stat.S_IMODE((work / ".env").stat().st_mode) == 0o600 and not _temp_leftovers(work)
    # an assignment appended, value taken literally, replacing an earlier one
    done = _functions_run(site, "env_put NEW 'a=b $c \"d\" \\e'\nenv_put B two\n")
    assert done.returncode == 0, done.stderr
    assert (work / ".env").read_bytes() == expected.replace(b"B=has=equals and $dollar and \\back\\slash\n", b"").replace(
        b"B=again\n", b"") + b'NEW=a=b $c "d" \\e\nB=two\n'
    # nothing to drop: the file is not touched
    before = (work / ".env").read_bytes()
    done = _functions_run(site, "env_unset NOPE && echo ok\n")
    assert done.returncode == 0 and (work / ".env").read_bytes() == before


def test_service_env_file_copies_awkward_lines_byte_for_byte(site):
    work, _, _ = site
    (work / ".env.deployment").write_bytes(
        b"# comment FOO=0\n"
        b"FOO=1\r\n"
        b'export FOO2 = "not wanted"\n'
        b"NEXT_PUBLIC_A='single quoted'\n"
        b"  NEXT_PUBLIC_B = with=equals $dollar \\ back\n"
        b"NEXT_PUBLIC_EMPTY=\n"
        b'NEXT_PUBLIC_QEMPTY=""\n'
        b"export NEXT_PUBLIC_C=exported # trailing\n"
        b"FOO=dup\n"
        b"OTHER=secret\n"
        b"NEXT_PUBLIC_LAST=nonl"
    )
    done = _functions_run(site, "service_env_file .env.webapp FOO 'NEXT_PUBLIC_*'; echo \"rc=$?\"\n")
    assert "rc=0" in done.stdout, done.stderr
    assert (work / ".env.webapp").read_bytes() == (
        b"FOO=1\r\n"
        b"NEXT_PUBLIC_A='single quoted'\n"
        b"NEXT_PUBLIC_B = with=equals $dollar \\ back\n"
        b"NEXT_PUBLIC_C=exported # trailing\n"
        b"FOO=dup\n"
        b"NEXT_PUBLIC_LAST=nonl\n"
    )
    assert stat.S_IMODE((work / ".env.webapp").stat().st_mode) == 0o600 and not _temp_leftovers(work)
    # nothing it reads: an empty file, as before
    done = _functions_run(site, "service_env_file .env.worker NOTHING_HERE; echo \"rc=$?\"\n")
    assert "rc=0" in done.stdout and (work / ".env.worker").read_bytes() == b""
    # an existing file is never changed
    (work / ".env.webapp").write_text("MINE=1\n")
    _functions_run(site, "service_env_file .env.webapp FOO\n")
    assert (work / ".env.webapp").read_text() == "MINE=1\n"


def test_the_only_traps_in_deploy_sh_are_the_guards():
    """guard_disarm clears every trap outright instead of restoring an earlier one: that is only
    sound while no other trap exists."""
    text = (ROOT / "deploy.sh").read_text()
    inside = set()
    for name in ("guard_arm", "guard_disarm"):
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.S | re.M)
        start = text[: found.start()].count("\n") + 1
        inside |= set(range(start, start + found.group(0).count("\n")))
    stray = [n for n, line in enumerate(text.splitlines(), 1)
             if re.search(r"(^|[;&|{(]|\s)trap\s", line.split("#", 1)[0]) and n not in inside]
    assert not stray, stray


def test_a_successful_prune_removes_its_directory_keeps_the_backups_private_and_shows_no_secret(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-prune", "--apply", "--swap", extra={"TMPDIR": str(scratch)})
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert (work / ".env").read_text() == "SETTINGS_MASTER_KEY=" + "m" * 64 + "\n"
    [backup] = work.glob(".env.pre-v4.*")
    assert "DUMMY-jwt-secret" in backup.read_text() and stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE((work / ".env").stat().st_mode) == 0o600
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_a_prune_without_swap_leaves_the_files_and_passes_the_arguments_on(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-prune", "--apply", extra={"TMPDIR": str(scratch)})
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert (work / ".env").read_text() == SECRET_ENV
    assert calls[_index(calls, "settings-prune")].endswith("--apply")
    assert not list(scratch.iterdir())


def test_a_failed_prune_removes_its_directory_and_leaves_the_files_alone(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-prune", "--apply", "--swap", extra={"TMPDIR": str(scratch), "STUB_PRUNE_FAILS": "1"})
    assert done.returncode == 1
    assert (work / ".env").read_text() == SECRET_ENV and not list(work.glob(".env.pre-v4.*"))
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_a_successful_export_removes_its_directory_writes_a_private_file_and_shows_no_secret(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env",
                       extra={"TMPDIR": str(scratch)})
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert (work / "out.env").read_text() == "UMAMI_PASSWORD=DUMMY-exported-secret\n"
    assert stat.S_IMODE((work / "out.env").stat().st_mode) == 0o600
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_an_export_is_created_owner_only_even_under_a_permissive_umask(site, tmp_path):
    """The file is created, not chmod-ed after the fact: no moment at which it is readable by others."""
    work, state, env = site
    (work / ".env").write_text(SECRET_ENV)
    _stand_in(site, "chmod", "#!/bin/sh\nexit 0\n")  # a chmod that does nothing: the mode is the umask's
    done = subprocess.run(["bash", "-c", "umask 000; exec bash deploy.sh \"$@\"", "x", "settings-env-export",
                           "--keys", "UMAMI_PASSWORD", "--out", "out.env"],
                          cwd=work, env={**env, "STUB_VOLUMES": "", "TMPDIR": str(_scratch(tmp_path))},
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-500:]
    assert stat.S_IMODE((work / "out.env").stat().st_mode) == 0o600


def test_a_failed_export_removes_its_directory_and_writes_nothing(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env",
                       extra={"TMPDIR": str(scratch), "STUB_EXPORT_FAILS": "1"})
    assert done.returncode == 1 and not (work / "out.env").exists()
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_the_umami_blanking_removes_its_directory_and_blanks_the_value_keeping_a_private_backup(site, tmp_path):
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\nOTHER=1\n")
    scratch = _scratch(tmp_path)
    done, _ = _run(site, extra={"STUB_UMAMI_ROTATES": "1", "TMPDIR": str(scratch)})
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert (work / ".env.deployment").read_text() == "UMAMI_PASSWORD=\nOTHER=1\n"
    [backup] = work.glob(".env.deployment.pre-umami.*")
    assert backup.read_text() == "UMAMI_PASSWORD=DUMMY-old-umami\nOTHER=1\n" and stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert "Blanked UMAMI_PASSWORD in .env.deployment" in done.stdout
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_a_failed_umami_blanking_is_reported_not_announced_as_done(site, tmp_path):
    """`cat` into .env.deployment fails (a stand-in): the step used to print that the value was
    blanked; it now says it was not, and the scratch directory is removed all the same."""
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\n")
    _stand_in(site, "cat", "#!/bin/sh\nexit 1\n")
    scratch = _scratch(tmp_path)
    done, _ = _run(site, extra={"STUB_UMAMI_ROTATES": "1", "TMPDIR": str(scratch)})
    assert "Blanked UMAMI_PASSWORD" not in done.stdout
    assert "WARNING: could not blank UMAMI_PASSWORD in .env.deployment" in done.stderr
    assert not list(scratch.iterdir())
