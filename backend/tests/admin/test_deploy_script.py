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
        elif verb == "settings-clear":
            # the store keeps the versions: the value stays, marked cleared
            (store / (cmd[1] + ".cleared")).write_text("")
            print("cleared %s version=2" % cmd[1])
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
    if "backend.seed_refdata" in argv and os.environ.get("STUB_SEED_FAILS"):
        sys.exit(1)
    # the migration CLIs of the import from before 4.1: STUB_MIGRATE_FAILS="<service> <step>"
    for module, name in (("auth.migrate", "auth"), ("googleform.migrate", "google"),
                         ("backend.migrate", "backend")):
        if module in argv:
            step = argv[argv.index(module) + 1]
            failing = os.environ.get("STUB_MIGRATE_FAILS", "") == name + " " + step
            if step == "status":
                print("service %s (schema x)\\nmarker: none" % name)
                broken = os.environ.get("STUB_MIGRATE_FAILS", "") == name + " backfill"
                print("  %s_things: mongo=3 postgres=%d backfill=%s"
                      % (name, 2 if broken else 3, "error" if broken else "done"))
            elif step in ("preflight", "verify"):
                row = {"collection": name + "_things", "mongo": 3, "postgres": 3, "missing_in_postgres": 0,
                       "missing_in_mongo": 0, "mismatched": 0, "drifted": 0, "tombstoned": 0,
                       "invalid_ids": 0, "duplicates": 0,
                       "samples": {"missing_in_postgres": [], "mismatched": []}}
                bad = dict(row, collection=name + "_others", postgres=1, missing_in_postgres=2,
                           samples={"missing_in_postgres": ["65f0c0ffee0000000000aaaa"], "mismatched": []})
                if failing and step == "preflight":
                    bad = dict(row, collection=name + "_others", duplicates=2, postgres=0)
                print(json.dumps([row] + ([bad] if failing else []), indent=2, sort_keys=True))
            else:
                print(json.dumps({name + "_things": {"state": "error" if failing else "done"}}, indent=2))
            sys.exit(1 if failing else 0)
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
    if argv[:1] == ["ps"]:
        # STUB_TYPEFORM_PROJECT: the project an old integrations-typeform container belongs to
        owner = os.environ.get("STUB_TYPEFORM_PROJECT", "")
        filters = [a for a in argv if a.startswith("label=")]
        if owner and "label=com.docker.compose.service=integrations-typeform" in filters and all(
            f in ("label=com.docker.compose.service=integrations-typeform", "label=com.docker.compose.project=" + owner)
            for f in filters
        ):
            print("0123456789ab")
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
    # UMAMI_URL seeded into the store. A new 4.1 stack has no MongoDB: no root
    # password, no MONGO_URI, no import, and Mongo is never started
    assert (state / "store" / "UMAMI_URL").read_text() == "http://umami:3000"
    assert "BC_MONGO_ROOT_PASSWORD" not in values and "BC_LEGACY_MONGO_IMPORTED" not in values
    assert not (state / "store" / "MONGO_URI").exists()
    assert not any("mongodb" in c or "legacy-mongo" in c or ".migrate" in c for c in calls)
    up = calls[_index(calls, "up --build")]
    assert "mongo" not in up
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
    done, calls = _run(site, volumes="app-postgres-data,temporal-postgres-data,umami-db-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("bootstrap-keys" in c for c in calls)
    assert not any("mongodb" in c or ".migrate" in c for c in calls)
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
    # no MONGO_URI in the files: the original default is seeded for the import (never a
    # new password), and cleared once the data is in Postgres
    assert (state / "store" / "MONGO_URI").read_text() == "mongodb://root:root@mongodb:27017"
    assert (state / "store" / "MONGO_URI.cleared").exists()
    assert values["BC_LEGACY_MONGO_IMPORTED"]


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
    assert "--keep AUTH_JWT_SECRET" not in prune
    # the Typeform flags (Typeform was removed in 4.1) are accepted and ignored
    (state / "calls.log").unlink()
    done, calls = _run(site, "settings-prune", "--typeform")
    prune = calls[_index(calls, "settings-prune")]
    assert "--keep AUTH_JWT_SECRET" not in prune and "--typeform" not in prune
    assert "ignored" in done.stderr


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
    for preference, extra in (("", set()), ("googleform", {"integrations-googleform"})):
        done, calls = _run(site, "print-services", preference)
        assert done.returncode == 0, done.stderr
        listed = set(done.stdout.split())
        assert required <= listed, (preference, required - listed)
        assert extra <= listed
        assert "integrations-typeform" not in listed
        # MongoDB is not part of a 4.1 stack (only the legacy-mongo profile starts it)
        assert not {"mongodb", "mongo-seed"} & listed
        assert ("integrations-googleform" in listed) == ("integrations-googleform" in extra)
    # and the real start passes exactly that list to `up`
    done, calls = _run(site, "googleform")
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    up = calls[_index(calls, "up --build")]
    for name in required | {"integrations-googleform"}:
        assert f" {name}" in up, name
    assert "integrations-typeform" not in up and "TYPEFORM" not in up and "mongo" not in up


@pytest.mark.parametrize("args", [("typeform",), ("both",), ("print-services", "typeform"), ("print-services", "both")])
def test_the_typeform_preferences_are_refused_before_anything_changes(site, args):
    """Typeform was removed in 4.1: `typeform` and `both` are refused with the way
    forward, before a file is written or a container touched."""
    work, state, _ = site
    before = sorted(p.name for p in work.iterdir())
    done, calls = _run(site, *args)
    assert done.returncode == 2
    assert "the Typeform integration was removed in 4.1" in done.stderr
    assert "./deploy.sh googleform" in done.stderr and "Nothing was changed" in done.stderr
    assert done.stdout == ""
    assert calls == []
    assert sorted(p.name for p in work.iterdir()) == before


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
    for name in ("BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD"):
        assert name not in values, name
        assert f"NOTE: {name} is not set" in done.stdout
    # a stack without a Mongo volume has no MongoDB at all (4.1): no password, no
    # MONGO_URI, no note about either
    assert "BC_MONGO_ROOT_PASSWORD" not in values and "BC_MONGO_ROOT_PASSWORD" not in done.stdout
    assert not (state / "store" / "MONGO_URI").exists()
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
    for name in ("BC_TEMPORAL_DB_PASSWORD", "BC_UMAMI_DB_PASSWORD"):
        assert _dotenv(other).get(name), name
    assert "BC_MONGO_ROOT_PASSWORD" not in _dotenv(other)


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
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    webapp = _tail(work, ".env.webapp")
    worker = _tail(work, ".env.worker")
    assert not (work / ".env.typeform").exists()  # Typeform was removed in 4.1
    for text, name in ((webapp, "webapp"), (worker, "worker")):
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
    assert "SERVER_URL=http://backend:8001/api/v1" in _tail(work, ".env.worker")
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


def test_typeform_leftovers_are_reported_never_removed(site):
    # a pre-4.1 .env.typeform holds the Typeform secret and a database URI: say so, keep the file
    work, _, _ = site
    (work / ".env.typeform").write_text("TYPEFORM_CLIENT_SECRET=x\n")
    done, _ = _run(site, extra={"STUB_TYPEFORM_PROJECT": "stack"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert ".env.typeform from an earlier release still exists" in done.stderr
    assert "integrations-typeform container from an earlier release" in done.stderr
    assert (work / ".env.typeform").exists()


def test_another_projects_typeform_container_is_not_reported(site):
    done, _ = _run(site, extra={"STUB_TYPEFORM_PROJECT": "other-stack"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert "integrations-typeform container" not in done.stderr
    assert ".env.typeform" not in done.stderr


# -- reference data (allowed origins, the Google Forms provider) in Postgres ------------


def _seed_calls(calls):
    return [c for c in calls if "backend.seed_refdata" in c]


def test_a_new_stack_seeds_its_reference_data_into_postgres_before_the_start(site):
    work, state, _ = site
    done, calls = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    [seed] = _seed_calls(calls)
    position = calls.index(seed)
    # after the migrations and the keys, before any service starts; a new stack has
    # no MONGO_URI, so Mongo is never started for the import check
    assert _index(calls, "alembic") < _index(calls, "bootstrap-keys") < position < _index(calls, "up --build")
    assert not any("mongodb" in c for c in calls)
    assert "run --rm --no-deps backend" in seed
    assert seed.endswith("--google-enabled false")
    # no public domain configured: the command decides (local ports, or API_CLIENT_URL's origin)
    assert "--origin" not in seed
    assert "DASHBOARD_DOMAIN and FORM_DOMAIN are not set" in done.stdout


def test_the_seeded_origins_are_the_web_apps_public_ones(site):
    work, state, _ = site
    (work / ".env.deployment").write_text(
        "UMAMI_PASSWORD=\nHTTP_SCHEME=https://\nDASHBOARD_DOMAIN=admin.forms.example\n"
        "FORM_DOMAIN=forms.example\nCLIENT_ADMIN_URL=http://localhost:3000\n"
    )
    done, calls = _run(site, "googleform")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    [seed] = _seed_calls(calls)
    assert "--origin https://admin.forms.example --origin https://forms.example" in seed
    assert "localhost" not in seed
    assert seed.endswith("--google-enabled true")


def test_the_web_apps_own_env_file_wins_and_a_scheme_or_path_is_understood(site):
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nFORM_DOMAIN=old.example\n")
    (work / ".env.webapp").write_text(
        "HTTP_SCHEME=http\nDASHBOARD_DOMAIN=https://dash.example:8443/app\nFORM_DOMAIN=forms.example\n"
    )
    done, calls = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    [seed] = _seed_calls(calls)
    assert "--origin http://dash.example:8443 --origin http://forms.example " in seed
    assert "old.example" not in seed


def test_an_upgrade_and_a_second_run_never_seed(site):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not _seed_calls(calls)
    # a new stack seeds once; its next deploys leave the tables to the operator
    shutil.rmtree(state / "store")
    (work / ".env").unlink()
    (state / "calls.log").unlink()
    done, calls = _run(site)
    assert done.returncode == 0 and len(_seed_calls(calls)) == 1
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not _seed_calls(calls)


def test_a_failed_seed_stops_before_the_start_and_the_next_run_seeds(site):
    work, state, _ = site
    done, calls = _run(site, extra={"STUB_SEED_FAILS": "1"})
    assert done.returncode != 0
    assert "Seeding the reference data into Postgres failed" in done.stderr
    assert not any("up --build" in c for c in calls)
    assert _dotenv(work)["BC_FIRST_RUN_PENDING"] == "1"
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("bootstrap-keys" in c for c in calls)
    assert len(_seed_calls(calls)) == 1
    assert _index(calls, "backend.seed_refdata") < _index(calls, "up --build")


# --- the import of a stack from before 4.1 ------------------------------------------------

def mongo_up_index(calls):
    return _index(calls, "--profile legacy-mongo up -d --wait mongodb")


STEPS = [f"{name}.migrate {step}" for name in ("auth", "googleform", "backend")
         for step in ("preflight", "backfill", "verify")]


def test_an_upgrade_imports_its_mongo_data_verified_before_the_services_start(site):
    """A 4.0 stack (Mongo volume, keys in the store): the services that write Mongo
    are stopped, MongoDB starts under the legacy-mongo profile, each service's
    preflight, backfill and verify run in the runbook's order (auth, google, backend),
    then MONGO_URI is cleared, MongoDB is stopped and removed (never its volume), and
    only then do the services of this release start, without MongoDB."""
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes="mongo-data,app-postgres-data,temporal-postgres-data,umami-db-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    stop = _index(calls, "stop backend jobs-worker auth integrations-googleform task-runner")
    # only MongoDB's own commands run under the profile (it would create its volume)
    assert [c for c in calls if "legacy-mongo" in c] == [calls[mongo_up_index(calls)], calls[_index(calls, "rm -s -f mongodb")]]
    mongo_up = _index(calls, "--profile legacy-mongo up -d --wait mongodb")
    positions = [_index(calls, step) for step in STEPS]
    clear = _index(calls, "settings-clear MONGO_URI --confirm MONGO_URI --yes")
    mongo_rm = _index(calls, "--profile legacy-mongo rm -s -f mongodb mongo-seed")
    assert _index(calls, "settings-import") < stop < mongo_up < positions[0]
    assert positions == sorted(positions)
    # the Google integration's schema first, though this stack does not run it
    assert mongo_up < _index(calls, "integrations-googleform alembic") < positions[0]
    assert positions[-1] < clear < mongo_rm < _index(calls, "up --build")
    up = calls[_index(calls, "up --build")]
    assert "mongo" not in up
    assert not any(" down" in c or "volume" in c for c in calls)
    # an upgraded stack is never seeded: its reference data came from Mongo
    assert not _seed_calls(calls)
    values = _dotenv(work)
    assert values["BC_LEGACY_MONGO_IMPORTED"]
    assert (state / "store" / "MONGO_URI.cleared").exists()
    # the counts per collection, per service
    for name in ("auth", "google", "backend"):
        assert f"{name}   {name}_things: mongo=3 postgres=3 backfill=done" in done.stdout
    assert "volume (stack_mongo-data) is kept" in done.stdout
    logs = list(work.glob("legacy-mongo-import.*.log"))
    assert len(logs) == 1 and stat.S_IMODE(logs[0].stat().st_mode) == 0o600


def test_an_imported_stack_is_not_imported_again(site):
    """The next deploy of an upgraded stack (its Mongo volume is kept) and a stack
    the operator marked by hand never start MongoDB or seed a MONGO_URI."""
    work, state, _ = site
    _upgrade_env(work)
    done, _ = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("mongodb" in c or ".migrate" in c or "settings-clear" in c for c in calls)
    assert "UPGRADE TO 4.1" not in done.stdout
    # marked by hand (a stack that already serves everything from Postgres)
    shutil.rmtree(state / "store")
    (state / "calls.log").unlink()
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write("BC_LEGACY_MONGO_IMPORTED=by-hand\n")
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("mongodb" in c or ".migrate" in c for c in calls)
    assert not (state / "store" / "MONGO_URI").exists()


@pytest.mark.parametrize("failing", STEPS)
def test_any_failed_import_step_stops_the_deploy_with_counts_and_keeps_mongo_s_data(site, failing):
    work, state, _ = site
    _upgrade_env(work)
    name, step = failing.split(".migrate ")
    name = "google" if name == "googleform" else name
    done, calls = _run(site, volumes="mongo-data,app-postgres-data", extra={"STUB_MIGRATE_FAILS": f"{name} {step}"})
    assert done.returncode == 1
    assert f"STOPPED before any service of this release started: the {name} {step} failed" in done.stderr
    # no later step, no start, nothing cleared or recorded; Mongo stopped, its volume kept
    assert not any(later in c for later in STEPS[STEPS.index(failing) + 1:] for c in calls)
    assert not any("up --build" in c or "settings-clear" in c for c in calls)
    assert any("--profile legacy-mongo rm -s -f mongodb" in c for c in calls)
    assert "BC_LEGACY_MONGO_IMPORTED" not in _dotenv(work)
    assert not (state / "store" / "MONGO_URI.cleared").exists()
    # the counts of what differs, never a sample id
    expected = {
        "preflight": f"{name}_others: mongo=3 postgres=0 duplicates=2",
        "backfill": f"{name}_things: mongo=3 postgres=2 backfill=error",
        "verify": f"{name}_others: mongo=3 postgres=1 missing_in_postgres=2",
    }[step]
    assert expected in done.stderr
    assert "65f0c0ffee0000000000aaaa" not in done.stdout + done.stderr
    # fixed: the next run imports (resuming) and starts
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert _index(calls, "backend.migrate verify") < _index(calls, "up --build")
    assert _dotenv(work)["BC_LEGACY_MONGO_IMPORTED"]


def test_an_external_mongo_is_imported_and_its_uri_blanked_with_a_backup(site):
    """No Mongo volume, the operator's own MONGO_URI in .env.deployment: imported from
    there (MongoDB of the stack is never started), then the line is blanked."""
    work, state, _ = site
    _upgrade_env(work)
    uri = "mongodb://u:DUMMY-external@db.example.test:27017"
    (work / ".env.deployment").write_text(f"UMAMI_PASSWORD=\nexport MONGO_URI={uri}\nOTHER=1\n")
    done, calls = _run(site, volumes="app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("mongodb" in c for c in calls)
    assert _index(calls, "backend.migrate verify") < _index(calls, "up --build")
    assert (work / ".env.deployment").read_text() == "UMAMI_PASSWORD=\nexport MONGO_URI=\nOTHER=1\n"
    [backup] = work.glob(".env.deployment.pre-4.1.*")
    assert uri in backup.read_text() and stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert "DUMMY-external" not in done.stdout + done.stderr
    assert _dotenv(work)["BC_LEGACY_MONGO_IMPORTED"]


def test_a_mongo_uri_put_back_after_the_import_is_pointed_out_not_imported_again(site):
    """Back from a rollback to 4.0 with its .env.deployment: the import is recorded, so
    it is not repeated, and the MONGO_URI line is named for removal."""
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write("BC_LEGACY_MONGO_IMPORTED=20261025T000000Z\n")
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nMONGO_URI=mongodb://root:root@mongodb:27017\n")
    done, calls = _run(site, volumes="mongo-data,app-postgres-data")
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "NOTE: MONGO_URI is set in .env.deployment, but this stack's Mongo data was imported" in done.stdout
    assert not any(".migrate" in c or "--profile legacy-mongo" in c for c in calls)
    assert "MONGO_URI=mongodb://root:root@mongodb:27017" in (work / ".env.deployment").read_text()
