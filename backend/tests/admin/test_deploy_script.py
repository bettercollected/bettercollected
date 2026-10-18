"""deploy.sh against a stand-in for docker compose: the order of the steps and
what ends up in the root .env, for a new install and for an upgrade. No Docker
needed. The stand-in records every call, answers `settings-history` from a small
state directory, and writes what `bootstrap-keys --export-worker` would write."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
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
    if "exec" in argv and "umami" in argv:
        sys.stdin.read()
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
    if argv[:2] == ["volume", "inspect"]:
        name = argv[2]
        sys.exit(0 if any(name.endswith("_" + v) for v in os.environ.get("STUB_VOLUMES", "").split(",") if v) else 1)
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
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "state"
    state.mkdir()
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "STUB_STATE": str(state),
        "COMPOSE_PROJECT_NAME": "stack",
    }
    return work, state, env


def _run(site, *args, volumes="", extra=None):
    work, state, env = site
    env = {**env, "STUB_VOLUMES": volumes, **(extra or {})}
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
    # UMAMI_URL seeded into the store
    assert (state / "store" / "UMAMI_URL").read_text() == "http://umami:3000"
    # nothing generated is printed
    shown = done.stdout + done.stderr
    for name, value in values.items():
        if len(value) >= 16:
            assert value not in shown, name
    assert "abcd-ef01-2345" in shown  # the fingerprint is
    # no temp directory with keys is left behind
    assert not list(work.glob(".env.??????"))


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
