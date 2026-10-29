"""deploy.sh against a stand-in for docker compose: the order of the steps and
what ends up in the root .env, for a new install and for an upgrade. No Docker
needed. The stand-in records every call, answers `settings-history` from a small
state directory, and writes the keys `bootstrap-keys` would store."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import time
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

    def terminate_deploy_once():
        # STUB_SIGNAL_PIDFILE: send TERM to the deploy.sh process (not its group), once, as
        # soon as the key's file exists in STUB_SIGNAL_SCRATCH: a signal at a chosen point
        import signal, time
        pidfile, scratch = os.environ.get("STUB_SIGNAL_PIDFILE"), os.environ.get("STUB_SIGNAL_SCRATCH")
        marker = state / "signalled"
        if pidfile and scratch and not marker.exists() and list(pathlib.Path(scratch).rglob("identity.env")):
            marker.write_text("")
            os.kill(int(pathlib.Path(pidfile).read_text()), signal.SIGTERM)
            time.sleep(0.3)

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
                        "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET", "RESPONDENT_IDENTITY_KEY"):
                (store / key).write_text("x")
            print("generated=6 (values are not shown)")
            print("master_key_fingerprint abcd-ef01-2345")
        elif verb == "settings-set":
            (store / cmd[1]).write_text(stdin)
            print("set %s version=1 changed=yes" % cmd[1])
        elif verb == "settings-clear":
            # the store keeps the versions: the value stays, marked cleared
            (store / (cmd[1] + ".cleared")).write_text("")
            print("cleared %s version=2" % cmd[1])
        elif verb == "settings-import" and "--env-file" in cmd:
            # the import of one generated value from a private file the host mounted at /work
            terminate_deploy_once()
            if os.environ.get("STUB_IMPORT_ENV_HANGS"):
                import time
                time.sleep(60)
            if os.environ.get("STUB_IMPORT_ENV_FAILS"):
                print("refused RESPONDENT_IDENTITY_KEY weak_secret SECRETVALUE-must-not-be-echoed")
                sys.exit(1)
            mounts = [a for a in argv if a.endswith(":/work")]
            path = pathlib.Path(mounts[0].rsplit(":", 1)[0]) / pathlib.Path(cmd[cmd.index("--env-file") + 1]).name
            for line in path.read_text().splitlines():
                name, _, value = line.partition("=")
                (store / name).write_text(value)
            print("imported=1 existing=0 empty=0 unknown=0 refused=0")
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
    if "backend.seed_refdata" in argv and os.environ.get("STUB_SEED_FAILS"):
        sys.exit(1)
    if "backend.identity_rekey" in argv:
        # the one-time conversion: its exit status and report come from STUB_IDENTITY_RC
        # (0 done, 1 values remain, 2 another process holds the lock, 3/4 wrong key)
        rc = int(os.environ.get("STUB_IDENTITY_RC", "0"))
        print("2026-10-26 12:00:00 | INFO | respondent identity pass: key fingerprint=0a1b2c3d", file=sys.stderr)
        if rc not in (3,):
            left = 0 if rc == 0 else 4
            print(json.dumps({"converted": {"app.form_responses": 2}, "changed_meanwhile": {}, "key_check": "written",
                              "key_fingerprint": "0a1b2c3d", "locked": rc == 2,
                              "remaining": {"app.form_responses": left}}, sort_keys=True))
        sys.exit(rc)
    if "backend.migrate" in argv and "jobs-sweep" in argv:
        if os.environ.get("STUB_SWEEP_FAILS"):
            print("Traceback: boom", file=sys.stderr)
            sys.exit(1)
        print(json.dumps({"backend": "postgres", "read_from": "postgres", "scheduled": 7}, indent=2))
        sys.exit(0)
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
        if "psql" in argv:
            # the key check rows of the respondent identity (0 on a database never started on 4.1)
            print(os.environ.get("STUB_IDENTITY_CHECK_ROWS", "0"))
    sys.exit(0)
    '''
)
DOCKER_STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import os, sys, pathlib
    argv = sys.argv[1:]
    state = pathlib.Path(os.environ["STUB_STATE"])
    with (state / "docker.log").open("a") as log:
        log.write(" ".join(argv) + "\\n")
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
        # the old Temporal stack (STUB_TEMPORAL=1): its containers' name, state and mounts
        template = argv[2] if len(argv) > 2 else ""
        if argv[-1].startswith("old-"):
            if ".Mounts" in template:
                print("stack_temporal-postgres-data " if argv[-1] == "old-postgresql" else "")
            elif ".State.Running" in template:
                print(os.environ.get("STUB_TEMPORAL_RUNNING_STATE", "true"))
            elif ".Name" in template:
                print("/stack-" + argv[-1][4:] + "-1")
            sys.exit(0)
        print(os.environ.get("STUB_ADMIN_HEALTH", "healthy"))
        sys.exit(0)
    if argv[:1] == ["exec"] and "temporal" in argv and "workflow" in argv:
        # `temporal workflow list`: STUB_TEMPORAL_RUNNING is how many workflows run; the count
        # drops to 0 after STUB_TEMPORAL_POLLS asks. A header, a schedule (not counted) and the rows.
        polls = state / "temporal.polls"
        asked = int(polls.read_text()) if polls.exists() else 0
        polls.write_text(str(asked + 1))
        if os.environ.get("STUB_TEMPORAL_CLI_FAILS"):
            print("Error: unknown flag", file=sys.stderr)
            sys.exit(1)
        running = int(os.environ.get("STUB_TEMPORAL_RUNNING", "0"))
        if asked >= int(os.environ.get("STUB_TEMPORAL_POLLS", "999999")):
            running = 0
        print("  Status   WorkflowId   Type   StartTime")
        print("  Running  temporal-sys-scheduler:delete_response_x   temporal-sys-scheduler-workflow   1 hour ago")
        for n in range(running):
            print("  Running  delete_user_%d   delete_user_workflow   1 minute ago" % n)
        sys.exit(0)
    if argv[:1] == ["ps"] and os.environ.get("STUB_TEMPORAL") and any(
        a == "label=com.docker.compose.project=stack" for a in argv
    ):
        # the containers of the old stack: Temporal, its worker, and the database named "postgresql"
        for a in argv:
            if a.startswith("label=com.docker.compose.service="):
                service = a.split("=", 2)[2]
                if service in ("temporal", "worker", "postgresql"):
                    print("old-" + service)
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


# `id` as deploy.sh calls it: it passes through, but it can also send TERM to deploy.sh
# (the same hook as the compose stand-in) at the moment it is called with the key's file
# in place, which is where the real script once evaluated `$(id -u):$(id -g)`.
ID_STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import os, sys, pathlib, signal, time
    pidfile, scratch = os.environ.get("STUB_SIGNAL_PIDFILE"), os.environ.get("STUB_SIGNAL_SCRATCH")
    marker = pathlib.Path(os.environ["STUB_STATE"]) / "signalled"
    if pidfile and scratch and not marker.exists() and list(pathlib.Path(scratch).rglob("identity.env")):
        marker.write_text("")
        os.kill(int(pathlib.Path(pidfile).read_text()), signal.SIGTERM)
        time.sleep(0.3)
    os.execv(os.environ["STUB_REAL_ID"], ["id"] + sys.argv[1:])
    '''
)


# `cp` and `cat` as deploy.sh calls them: they pass through, but they can send TERM to deploy.sh
# first, when the one named in STUB_SIGNAL_CMD is called with a path inside the scratch
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
    # the Temporal worker is not part of the stack any more: no copies of its two keys are exported
    assert "--export-worker" not in calls[boot]
    # the respondent identity key came from bootstrap-keys: nothing is generated or imported for it
    assert not any("settings-import" in c for c in calls)
    assert "Generated a new RESPONDENT_IDENTITY_KEY" not in done.stdout
    # the identity pass runs once the new backend is up, and prints the key's fingerprint only
    assert _index(calls, "up --build") < _index(calls, "backend.identity_rekey")
    assert "Respondent identity key fingerprint: 0a1b2c3d" in done.stdout
    # no import on a new stack, and Umami's login is checked after the start
    assert not any("settings-import" in c for c in calls)
    assert _index(calls, "up --build") < _index(calls, "exec -T umami")

    values = _dotenv(work)
    for name in ("SETTINGS_MASTER_KEY", "APP_POSTGRES_PASSWORD", "BC_ADMIN_PASSWORD", "UMAMI_APP_SECRET",
                 "BC_UMAMI_DB_PASSWORD"):
        assert values.get(name), name
    # Temporal's database password and the worker's two key copies are not generated any more
    for name in ("BC_TEMPORAL_DB_PASSWORD", "API_KEY", "AES_HEX_KEY"):
        assert name not in values, name
    assert not (work / ".env.worker").exists()
    # the stack's keys are in the store, not in the file
    for name in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "MASTER_ENCRYPTION_KEYSET",
                 "TEMPORAL_API_KEY", "AUTH_INTERNAL_NOTIFY_KEY", "RESPONDENT_IDENTITY_KEY"):
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
    # the respondent identity key is new in 4.1: generated once into the store, after the import
    # (bootstrap-keys is refused on a stack that holds data) and before any service starts
    single = _index(calls, "settings-import --env-file")
    assert imp < single < _index(calls, "up --build")
    assert "Generated a new RESPONDENT_IDENTITY_KEY in the settings store and in .env" in done.stdout
    # in the store and, like the other keys of an upgrade, in .env (SETTINGS_STORE=off still has it)
    assert values["RESPONDENT_IDENTITY_KEY"] == (state / "store" / "RESPONDENT_IDENTITY_KEY").read_text()
    assert re.fullmatch(r"[0-9a-f]{64}", values["RESPONDENT_IDENTITY_KEY"])
    assert values["RESPONDENT_IDENTITY_KEY"] not in done.stdout + done.stderr
    assert _index(calls, "up --build") < _index(calls, "backend.identity_rekey")
    # no copies of the key for a Temporal worker: it is not part of the stack any more
    assert "API_KEY" not in values and "AES_HEX_KEY" not in values
    assert "Copied TEMPORAL_API_KEY" not in done.stdout
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
    required = {"admin", "jobs-worker", "document-sandbox", "task-runner", "backend", "auth", "webapp"}
    for preference, extra in (("", set()), ("googleform", {"integrations-googleform"})):
        done, calls = _run(site, "print-services", preference)
        assert done.returncode == 0, done.stderr
        listed = set(done.stdout.split())
        assert required <= listed, (preference, required - listed)
        assert extra <= listed
        assert "integrations-typeform" not in listed
        # Temporal, its database and its worker are not part of a 4.1 stack
        assert not {"temporal", "worker", "postgresql"} & listed
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
    for name in ("BC_UMAMI_DB_PASSWORD",):
        assert name not in values, name
        assert f"NOTE: {name} is not set" in done.stdout
    # Temporal's database is not part of the stack: its password is neither generated nor mentioned
    assert "BC_TEMPORAL_DB_PASSWORD" not in values and "BC_TEMPORAL_DB_PASSWORD" not in done.stdout
    # a stack without a Mongo volume has no MongoDB at all (4.1): no password, no
    # MONGO_URI, no note about either
    assert "BC_MONGO_ROOT_PASSWORD" not in values and "BC_MONGO_ROOT_PASSWORD" not in done.stdout
    assert not (state / "store" / "MONGO_URI").exists()
    # a stack with no volume at all gets its Umami password
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
    assert _dotenv(other).get("BC_UMAMI_DB_PASSWORD")
    assert "BC_TEMPORAL_DB_PASSWORD" not in _dotenv(other)
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
    assert not (work / ".env.typeform").exists()  # Typeform was removed in 4.1
    assert not (work / ".env.worker").exists()  # so was the Temporal worker's file
    for secret in ("sk_live_dummy", "gsecret", "mailpw", "whsec"):
        assert secret not in webapp, secret
    assert "MASTER_ENCRYPTION_KEYSET" not in webapp and "AUTH_JWT_SECRET" not in webapp
    assert stat.S_IMODE((work / ".env.webapp").stat().st_mode) == 0o600
    # what the webapp reads, empty values left out, `export` dropped, quotes kept
    assert "UNSPLASH_ACCESS_KEY=unsplash" in webapp and "GOOGLE_CLIENT_ID=gid" in webapp
    assert "UMAMI_SCRIPT_URL=http://host:3003/script.js" in webapp and "GOOGLE_PICKER_API_KEY" not in webapp
    assert "NEXT_PUBLIC_API_ENDPOINT_HOST=http://api" in webapp and "ELASTIC_APM_SERVER_URL=http://apm" in webapp
    assert "CUSTOM_DOMAIN_ASSERTION_KEYS='k1,k2'" in webapp
    assert "TYPEFORM_CLIENT" not in webapp
    assert not any(line.startswith(("SERVER_URL=", "COOKIE_DOMAIN=")) for line in webapp.splitlines())
    # never overwritten by a later run
    (work / ".env.webapp").write_text("MINE=1\n")
    (work / ".env.webapp").chmod(0o644)
    _run(site, volumes="mongo-data,app-postgres-data")
    assert (work / ".env.webapp").read_text() == "MINE=1\n"
    assert stat.S_IMODE((work / ".env.webapp").stat().st_mode) == 0o600


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
    assert not (work / ".env.worker").exists()
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


# --- the operator's own MONGO_URI comes first; key names, never values -----------------

LOCAL_MONGO = "mongodb://root:root@mongodb:27017"
UPGRADE_VOLUMES = "mongo-data,app-postgres-data,temporal-postgres-data,umami-db-data"
EXTERNAL_URI = "mongodb://u:DUMMY-external-pw@db.example.test:27017"


def test_the_local_mongo_uri_is_seeded_with_the_volumes_own_password(site):
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write("BC_MONGO_ROOT_PASSWORD=volpw123\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert (state / "store" / "MONGO_URI").read_text() == "mongodb://root:volpw123@mongodb:27017"
    assert "volpw123" not in done.stdout + done.stderr


@pytest.mark.parametrize("store_complete", [False, True])
def test_an_operator_mongo_uri_in_env_deployment_is_never_replaced_by_the_local_one(site, store_complete):
    """An external Mongo configured in .env.deployment: the stack's own Mongo URI is not
    seeded, on the run that imports the files into the store and on one that does not."""
    work, state, _ = site
    _upgrade_env(work)
    (work / ".env.deployment").write_text(f"UMAMI_PASSWORD=\nMONGO_URI={EXTERNAL_URI}\n")
    if store_complete:
        store = state / "store"
        store.mkdir()
        for key in ("AUTH_JWT_SECRET", "AUTH_AES_HEX_KEY", "AUTH_INTERNAL_NOTIFY_KEY",
                    "TEMPORAL_API_KEY", "MASTER_ENCRYPTION_KEYSET"):
            (store / key).write_text("x")
        with (work / ".env").open("a") as env:
            env.write("TEMPORAL_API_KEY=" + "t" * 48 + "\n")
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not (state / "store" / "MONGO_URI").exists()
    assert not any("settings-set MONGO_URI" in c for c in calls)
    assert "NOTE: MONGO_URI is set in .env.deployment: that value is the operator's own and is kept" in done.stdout
    assert "move it to .env.deployment" not in done.stdout
    assert "DUMMY-external-pw" not in done.stdout + done.stderr
    # the import itself still runs, from the operator's value
    assert _index(calls, "backend.migrate verify") < _index(calls, "up --build")


def test_a_mongo_uri_only_in_the_root_env_stops_the_deploy_before_any_service_is_stopped(site):
    """No service reads MONGO_URI from the root .env: the import could not reach that Mongo,
    and the services would already be stopped by then. Stopped first, with what to do."""
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write(f"MONGO_URI={EXTERNAL_URI}\n")
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 1
    assert "STOPPED before any service was stopped: MONGO_URI is set in the root .env only" in done.stderr
    assert "Move the MONGO_URI line from .env to .env.deployment, then run ./deploy.sh again. Nothing was changed." in done.stderr
    # nothing stopped, no import, no start, the local URI not stored over the operator's
    assert not any(" stop " in c or c.startswith("stop ") or ".migrate" in c or "up --build" in c or "legacy-mongo" in c for c in calls)
    assert not (state / "store" / "MONGO_URI").exists()
    assert not any("settings-set MONGO_URI" in c for c in calls)
    assert "BC_LEGACY_MONGO_IMPORTED" not in _dotenv(work)
    assert "DUMMY-external-pw" not in done.stdout + done.stderr


def test_a_mongo_uri_in_the_root_env_and_in_the_store_uses_the_stored_one(site):
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write(f"MONGO_URI={EXTERNAL_URI}\n")
    store = state / "store"
    store.mkdir()
    (store / "MONGO_URI").write_text(EXTERNAL_URI)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "the settings store holds one too: the stored value is used" in done.stdout
    assert (store / "MONGO_URI").read_text() == EXTERNAL_URI
    assert not any("settings-set MONGO_URI" in c for c in calls)
    assert _index(calls, "backend.migrate verify") < _index(calls, "up --build")
    assert "DUMMY-external-pw" not in done.stdout + done.stderr


def test_a_stored_mongo_uri_is_never_overwritten(site):
    work, state, _ = site
    _upgrade_env(work)
    store = state / "store"
    store.mkdir()
    (store / "MONGO_URI").write_text(EXTERNAL_URI)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert (store / "MONGO_URI").read_text() == EXTERNAL_URI
    assert not any("settings-set MONGO_URI" in c for c in calls)


def test_a_blank_mongo_uri_is_no_operator_value(site):
    """The line a finished import leaves behind (blanked) is not an operator value."""
    work, state, _ = site
    _upgrade_env(work)
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nMONGO_URI=\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert (state / "store" / "MONGO_URI").read_text() == LOCAL_MONGO
    assert "that value is the operator's own" not in done.stdout


def test_a_new_stack_never_seeds_a_mongo_uri(site):
    work, state, _ = site
    done, calls = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("MONGO_URI" in c for c in calls)
    assert not (state / "store" / "MONGO_URI").exists()


def test_the_names_of_the_settings_copied_into_each_service_file_are_printed_never_values(site):
    work, state, _ = site
    (work / ".env.deployment").write_text(
        "STRIPE_SECRET=sk_live_dummy\nUNSPLASH_ACCESS_KEY=unsplash-secret-value\nGOOGLE_CLIENT_ID=gid-value\n"
        "export UMAMI_SCRIPT_URL=http://host:3003/script.js\nGOOGLE_PICKER_API_KEY=\n"
        "COOKIE_DOMAIN=cookie.example.test\nNAMESPACE=ns-value\nCOOKIE_DOMAIN=again.example.test\n"
    )
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    out = done.stdout
    # names in file order, once each, empty values left out (they are not copied either)
    assert "Created .env.webapp from .env.deployment with: UNSPLASH_ACCESS_KEY, GOOGLE_CLIENT_ID, UMAMI_SCRIPT_URL\n" in out
    assert ".env.worker" not in out  # the Temporal worker is not part of the stack any more
    shown = out + done.stderr
    for value in ("sk_live_dummy", "unsplash-secret-value", "gid-value", "cookie.example.test",
                  "again.example.test", "ns-value", "script.js"):
        assert value not in shown
    # a file that already exists is left alone, and nothing is reported as copied
    (state / "calls.log").unlink()
    done, _ = _run(site, volumes="mongo-data,app-postgres-data")
    assert "Created .env.webapp" not in done.stdout


def test_a_service_file_with_nothing_to_copy_says_so(site):
    work, _, _ = site
    (work / ".env.deployment").write_text("STRIPE_SECRET=sk_live_dummy\n")
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "Created .env.webapp: .env.deployment has none of the settings this service reads." in done.stdout
    assert "sk_live_dummy" not in done.stdout + done.stderr


def test_no_copies_of_the_keys_are_made_for_a_temporal_worker(site):
    """Temporal and its worker are not part of the stack any more: an upgrade keeps the old
    API_KEY / AES_HEX_KEY lines it may have, copies nothing and exports nothing."""
    work, _, _ = site
    (work / ".env").write_text(
        "AUTH_JWT_SECRET=" + "j" * 64 + "\nAUTH_AES_HEX_KEY=" + "A" * 43 + "=\n"
        "MASTER_ENCRYPTION_KEYSET=" + "k" * 40 + "\nTEMPORAL_API_KEY=" + "t" * 48 + "\n"
        "SETTINGS_MASTER_KEY=" + "m" * 64 + "\n"
    )
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "API_KEY in .env" not in done.stdout and "AES_HEX_KEY in .env" not in done.stdout
    assert not any("--export-worker" in c for c in calls)
    assert not (work / ".env.worker").exists()
    shown = done.stdout + done.stderr
    for secret in ("t" * 48, "A" * 43, "j" * 64, "m" * 64):
        assert secret not in shown
    values = _dotenv(work)
    assert "API_KEY" not in values and "AES_HEX_KEY" not in values


# --------------------------------------------------------------------------------
# the respondent identity key and the identity pass (docs/respondent-identity.md)


def _docker_calls(state):
    path = state / "docker.log"
    return path.read_text().splitlines() if path.exists() else []


def test_an_upgrade_generates_the_identity_key_once_and_a_second_run_keeps_it(site, tmp_path):
    work, state, _ = site
    # a TMPDIR of its own: tests running in parallel use the shared one
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    own_tmp = {"TMPDIR": str(scratch)}
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra=own_tmp)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    # generated before the start, into the store and .env, never printed: only the fingerprint is
    assert _index(calls, "settings-import --env-file") < _index(calls, "up --build")
    assert done.stdout.count("Generated a new RESPONDENT_IDENTITY_KEY in the settings store and in .env") == 1
    assert done.stdout.count("Respondent identity key fingerprint: 0a1b2c3d") == 1
    # the pass runs after the roll, in a one-off container of the new backend, with no extra argument
    assert calls[_index(calls, "backend.identity_rekey")].endswith("backend.identity_rekey")
    assert "Stored respondent identities are all converted" in done.stdout
    key = _dotenv(work)["RESPONDENT_IDENTITY_KEY"]
    assert (state / "store" / "RESPONDENT_IDENTITY_KEY").read_text() == key
    # recorded as a hash, so a later run can tell that .env and the store hold the same key
    import hashlib
    assert _dotenv(work)["BC_IDENTITY_KEY_SHA256"] == hashlib.sha256(key.encode()).hexdigest()
    assert key not in done.stdout + done.stderr
    assert not any(key in c for c in calls)  # not an argument of any command
    assert oct((work / ".env").stat().st_mode & 0o777) == "0o600"
    # a second deploy finds .env's key: nothing generated or imported, the same key and fingerprint
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra=own_tmp)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "Generated a new RESPONDENT_IDENTITY_KEY" not in done.stdout
    assert not any("settings-import --env-file" in c for c in calls)
    assert done.stdout.count("Respondent identity key fingerprint: 0a1b2c3d") == 1
    assert _dotenv(work)["RESPONDENT_IDENTITY_KEY"] == key
    assert (state / "store" / "RESPONDENT_IDENTITY_KEY").read_text() == key
    # the scratch directory that held the value for the import is gone
    assert not _temp_leftovers(work) and not list(scratch.rglob("identity.env"))


@pytest.mark.parametrize("where", ["env", "env_deployment", "shell"])
def test_an_identity_key_the_operator_set_is_used_as_it_is(site, where):
    """In the shell or the root .env: as it is. Only in .env.deployment: copied into .env, because compose
    passes the backend only the root .env's (its `environment:` entry overrides the env file)."""
    work, state, _ = site
    _upgrade_env(work)
    extra = {}
    line = "RESPONDENT_IDENTITY_KEY=" + "ab" * 32
    if where == "env":
        with (work / ".env").open("a") as env:
            env.write(line + "\n")
    elif where == "env_deployment":
        (work / ".env.deployment").write_text("UMAMI_PASSWORD=\n" + line + "\n")
    else:
        extra = {"RESPONDENT_IDENTITY_KEY": "ab" * 32}
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra=extra)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert not any("settings-import --env-file" in c for c in calls)
    assert not (state / "store" / "RESPONDENT_IDENTITY_KEY").exists()
    assert "RESPONDENT_IDENTITY_KEY is set in" in done.stdout
    assert "ab" * 32 not in done.stdout + done.stderr
    if where == "env":
        assert _dotenv(work)["RESPONDENT_IDENTITY_KEY"] == "ab" * 32  # untouched
    elif where == "env_deployment":
        assert _dotenv(work)["RESPONDENT_IDENTITY_KEY"] == "ab" * 32
        assert "copied into .env" in done.stdout
        assert (work / ".env.deployment").read_text().count("RESPONDENT_IDENTITY_KEY") == 1  # the operator's file is left alone
    else:
        assert "RESPONDENT_IDENTITY_KEY" not in _dotenv(work)


def test_no_identity_key_is_generated_for_a_database_that_was_already_used_with_one(site):
    """A key check row says a 4.1 backend started with some key: a new key would not match what
    that one converted, so with no key found anywhere the deploy stops before anything starts."""
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={"STUB_IDENTITY_CHECK_ROWS": "1"})
    assert done.returncode == 1
    assert "STOPPED before any service started" in done.stderr and "RESPONDENT_IDENTITY_KEY" in done.stderr
    assert not any("settings-import --env-file" in c or "up --build" in c for c in calls)
    assert not (state / "store" / "RESPONDENT_IDENTITY_KEY").exists()
    assert "RESPONDENT_IDENTITY_KEY" not in _dotenv(work)
    # with the key stored the same database passes
    (state / "store").mkdir(exist_ok=True)
    (state / "store" / "RESPONDENT_IDENTITY_KEY").write_text("x")
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={"STUB_IDENTITY_CHECK_ROWS": "1"})
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert "Generated a new RESPONDENT_IDENTITY_KEY" not in done.stdout


def test_a_refused_identity_key_stops_the_deploy_before_any_service_starts_and_leaves_no_trace(site):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={"STUB_IMPORT_ENV_FAILS": "1"})
    assert done.returncode == 1
    assert "Could not store a new RESPONDENT_IDENTITY_KEY" in done.stderr
    assert "SECRETVALUE" not in done.stdout + done.stderr  # the command's own wording after the name is dropped
    assert not any("up --build" in c for c in calls)
    assert "RESPONDENT_IDENTITY_KEY" not in _dotenv(work)  # not in .env without the store holding it
    assert not (state / "store" / "RESPONDENT_IDENTITY_KEY").exists()


@pytest.mark.parametrize("rc", ["3", "4"])
def test_a_wrong_or_missing_identity_key_fails_the_deploy_after_the_pass(site, rc):
    work, state, _ = site
    done, calls = _run(site, extra={"STUB_IDENTITY_RC": rc})
    assert done.returncode == 1
    assert f"exit {rc} of backend.identity_rekey" in done.stderr
    assert sum("backend.identity_rekey" in c for c in calls) == 1  # not retried


@pytest.mark.parametrize("rc,tries", [("2", 3), ("1", 2)])
def test_a_pass_that_does_not_finish_is_retried_a_bounded_number_of_times_and_only_warns(site, rc, tries):
    work, state, _ = site
    done, calls = _run(site, extra={"STUB_IDENTITY_RC": rc, "BC_DEPLOY_IDENTITY_PASS_TRIES": "3"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert sum("backend.identity_rekey" in c for c in calls) == tries
    assert f"WARNING: the respondent identity pass did not finish in this run (exit {rc})" in done.stderr
    assert "Key fingerprint: 0a1b2c3d" in done.stderr
    assert "Stored respondent identities are all converted" not in done.stdout


# --------------------------------------------------------------------------------
# Temporal is not part of the stack since 4.1 (retire_temporal)


TEMPORAL_ENV = {"STUB_TEMPORAL": "1", "BC_TEMPORAL_DRAIN_POLL": "0"}


def _removed(state):
    return [c for c in _docker_calls(state) if c.startswith("rm ")]


def test_a_new_stack_has_no_temporal_to_retire(site):
    work, state, _ = site
    done, calls = _run(site)
    assert done.returncode == 0
    assert not any("jobs-sweep" in c for c in calls)
    assert "TEMPORAL" not in done.stdout and not _removed(state)
    up = calls[_index(calls, "up --build")]
    assert not {" temporal", " worker", " postgresql"} & {f" {w}" for w in up.split() if w in ("temporal", "worker", "postgresql")}


def test_an_upgrade_moves_the_schedules_onto_the_queue_then_removes_temporal_and_keeps_its_volume(site):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra=TEMPORAL_ENV)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    # after the roll (nothing new goes to Temporal), the sweep, the wait, the removal
    sweep = _index(calls, "backend.migrate jobs-sweep --backend postgres")
    assert _index(calls, "up --build") < sweep
    # the sweep reads Postgres only: no MONGO_URI is handed to it, placeholder or otherwise
    assert "MONGO_URI" not in calls[sweep]
    assert "Scheduled response deletions on the job queue: 7" in done.stdout
    assert "Temporal runs no workflow." in done.stdout
    removed = _removed(state)
    # the worker, then Temporal, then its database (the one holding the temporal volume), never anything else
    assert removed == ["rm -f old-worker", "rm -f old-temporal", "rm -f old-postgresql"]
    assert not any(c.startswith("volume rm") for c in _docker_calls(state))
    assert "stack_temporal-postgres-data is kept" in done.stdout
    # the old worker still calls the new backend until it is removed, so the services run first
    assert done.stdout.index("TEMPORAL:") > done.stdout.index("Respondent identity key fingerprint")


def test_the_deploy_waits_for_running_workflows_but_not_for_schedules(site):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={**TEMPORAL_ENV, "STUB_TEMPORAL_RUNNING": "2", "STUB_TEMPORAL_POLLS": "3"})
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert done.stdout.count("Waiting for Temporal: 2 workflow(s) still running") == 3  # the schedule is not counted
    assert len(_removed(state)) == 3


def test_workflows_that_do_not_finish_stop_the_deploy_with_the_old_containers_in_place(site):
    work, state, _ = site
    _upgrade_env(work)
    extra = {**TEMPORAL_ENV, "STUB_TEMPORAL_RUNNING": "1", "BC_TEMPORAL_DRAIN_SECONDS": "0"}
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra=extra)
    assert done.returncode == 1
    assert "STOPPED: Temporal still runs 1 workflow(s) after 0 s." in done.stderr
    assert "BC_TEMPORAL_DRAIN=skip" in done.stderr and "stack-temporal-1 temporal workflow list" in done.stderr
    assert not _removed(state)
    # skipping the wait removes it anyway
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={**extra, "BC_TEMPORAL_DRAIN": "skip"})
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert len(_removed(state)) == 3 and "NOTE: BC_TEMPORAL_DRAIN=skip" in done.stdout


def test_a_temporal_that_cannot_be_asked_is_not_removed(site):
    work, state, _ = site
    _upgrade_env(work)
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra={**TEMPORAL_ENV, "STUB_TEMPORAL_CLI_FAILS": "1", "BC_TEMPORAL_DRAIN_SECONDS": "0"})
    assert done.returncode == 1
    assert "STOPPED: Temporal could not be asked" in done.stderr
    assert not _removed(state)


def test_a_failed_sweep_stops_before_anything_of_temporal_is_touched(site):
    work, state, _ = site
    _upgrade_env(work)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={**TEMPORAL_ENV, "STUB_SWEEP_FAILS": "1"})
    assert done.returncode == 1
    assert "could not be put on the job queue" in done.stderr
    assert not _removed(state) and not any("temporal workflow" in c for c in _docker_calls(state))


@pytest.mark.parametrize("line", ["JOBS_BACKEND=temporal", "export JOBS_BACKEND__delete_user='Temporal'", "JOBS_BACKEND__run_action=temporal # keep"])
def test_a_job_kind_pinned_to_temporal_is_refused_before_anything_changes(site, line):
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\n" + line + "\n")
    done, calls = _run(site)
    assert done.returncode == 1
    assert "routes background jobs to Temporal" in done.stderr and "Nothing was changed." in done.stderr
    assert calls == []
    # the queue (or no line) is fine
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nJOBS_BACKEND=postgres\nJOBS_BACKEND__run_action=\n")
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]


@pytest.mark.parametrize(
    "line, named",
    [
        ("DB_WRITE_MODE=dual", "DB_WRITE_MODE"),
        ("export DB_READ_SOURCE='Mongo'", "DB_READ_SOURCE"),
        ("DB_WRITE_MODE__forms=postgres_primary_dual # from the cutover", "DB_WRITE_MODE__forms"),
        ("  DB_READ_SOURCE__responses = mongo", "DB_READ_SOURCE__responses"),
    ],
)
def test_a_retired_store_switch_is_refused_before_anything_changes(site, line, named):
    work, state, _ = site
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\n" + line + "\n")
    done, calls = _run(site)
    assert done.returncode == 1
    assert f"refused: .env.deployment still sets {named}." in done.stderr and "Nothing was changed." in done.stderr
    assert calls == []
    # names only: the value is not echoed
    assert f"{named}=" not in done.stderr
    refusal = done.stderr[done.stderr.index("refused: .env.deployment") :]
    value = line.split("=", 1)[1].split("#")[0].strip().strip("'\"")
    assert value.lower() not in refusal.lower()


def test_a_store_switch_that_says_postgres_or_nothing_is_fine(site):
    work, state, _ = site
    (work / ".env.deployment").write_text(
        "UMAMI_PASSWORD=\nDB_READ_SOURCE=postgres\nDB_WRITE_MODE=\nDB_WRITE_MODE__forms=\"Postgres\"\n# DB_WRITE_MODE=dual\n"
    )
    done, _ = _run(site)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]


def test_a_leftover_worker_env_file_is_reported_and_kept(site):
    work, state, _ = site
    (work / ".env.worker").write_text("COOKIE_DOMAIN=example.test\n")
    done, _ = _run(site)
    assert done.returncode == 0
    assert ".env.worker from an earlier release still exists" in done.stderr
    assert (work / ".env.worker").read_text() == "COOKIE_DOMAIN=example.test\n"


def _store_key(state, value="x"):
    (state / "store").mkdir(exist_ok=True)
    (state / "store" / "RESPONDENT_IDENTITY_KEY").write_text(value)


def test_an_env_key_and_a_stored_key_that_cannot_be_shown_equal_stop_the_deploy(site):
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write("RESPONDENT_IDENTITY_KEY=" + "cd" * 32 + "\n")
    _store_key(state)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 1
    assert "holds one too" in done.stderr and "BC_IDENTITY_KEY_SOURCE=env" in done.stderr
    assert "cd" * 32 not in done.stdout + done.stderr
    assert not any("up --build" in c for c in calls)
    # a hash that does not belong to the key in .env is no better
    with (work / ".env").open("a") as env:
        env.write("BC_IDENTITY_KEY_SHA256=" + "0" * 64 + "\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 1
    # the operator says .env's key is the intended one
    (state / "calls.log").unlink()
    done, calls = _run(site, volumes=UPGRADE_VOLUMES, extra={"BC_IDENTITY_KEY_SOURCE": "env"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert any("up --build" in c for c in calls)
    assert _dotenv(work)["RESPONDENT_IDENTITY_KEY"] == "cd" * 32


def test_with_the_store_off_a_key_only_in_the_store_is_refused_and_a_new_one_goes_to_both(site):
    work, state, _ = site
    _upgrade_env(work)
    with (work / ".env").open("a") as env:
        env.write("SETTINGS_STORE=off\n")
    _store_key(state)
    done, calls = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 1
    assert "SETTINGS_STORE=off" in done.stderr and "only in the settings store" in done.stderr
    assert not any("up --build" in c for c in calls)
    # the shell's value counts the way compose reads it
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra={"SETTINGS_STORE": "required"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    # no key anywhere: the generated one is in .env too, which is what the store-off services read
    shutil.rmtree(state / "store")
    (state / "calls.log").unlink()
    done, _ = _run(site, volumes=UPGRADE_VOLUMES)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    assert re.fullmatch(r"[0-9a-f]{64}", _dotenv(work)["RESPONDENT_IDENTITY_KEY"])


def test_the_scratch_directory_of_the_key_is_removed_on_success_failure_and_a_signal(site, tmp_path):
    import signal
    work, state, env = site
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    base = {"TMPDIR": str(scratch)}
    _upgrade_env(work)
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra=base)
    assert done.returncode == 0 and not [p for p in scratch.rglob("identity.env")]
    shutil.rmtree(state / "store")
    (work / ".env").write_text((work / ".env").read_text().replace("RESPONDENT_IDENTITY_KEY=", "X_UNUSED=", 1))
    with open(work / ".env") as f:
        kept = [l for l in f.read().splitlines() if not l.startswith(("RESPONDENT_IDENTITY_KEY", "X_UNUSED", "BC_IDENTITY_KEY_SHA256"))]
    (work / ".env").write_text("\n".join(kept) + "\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra={**base, "STUB_IMPORT_ENV_FAILS": "1"})
    assert done.returncode == 1 and not [p for p in scratch.rglob("identity.env")]
    # a signal while the import runs: the stand-in hangs, the whole process group is terminated
    (state / "calls.log").unlink(missing_ok=True)
    full = {**env, "STUB_VOLUMES": UPGRADE_VOLUMES, "BC_DEPLOY_RETRY_SLEEP": "0", "STUB_IMPORT_ENV_HANGS": "1", **base}
    proc = subprocess.Popen(["bash", "deploy.sh"], cwd=work, env=full, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    import time
    for _ in range(100):
        if list(scratch.rglob("identity.env")):
            break
        time.sleep(0.1)
    assert list(scratch.rglob("identity.env")), "the import never started"
    os.killpg(proc.pid, signal.SIGTERM)
    proc.communicate(timeout=30)
    assert not list(scratch.rglob("identity.env"))
    assert not [d for d in scratch.iterdir()]


def _key_import_site(site, tmp_path):
    """The state of an upgrade that has no identity key anywhere: deploy.sh generates one."""
    work, state, env = site
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    _upgrade_env(work)
    kept = [l for l in (work / ".env").read_text().splitlines()
            if not l.startswith(("RESPONDENT_IDENTITY_KEY", "BC_IDENTITY_KEY_SHA256"))]
    (work / ".env").write_text("\n".join(kept) + "\n")
    shutil.rmtree(state / "store", ignore_errors=True)
    (state / "calls.log").unlink(missing_ok=True)
    return scratch


def _deploy_terminated_by_a_stand_in(site, scratch, extra=None, wait=20):
    """Run deploy.sh until the key's file exists, where a stand-in sends it TERM (only the
    script's own process, as `kill <pid>` does). Returns (exit status, stdout, stderr), or
    (None, ...) when the script was still running `wait` seconds later."""
    import signal
    work, state, env = site
    pidfile = state / "deploy.pid"
    real_id = shutil.which("id")
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    (bin_dir / "id").write_text(ID_STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    (bin_dir / "id").chmod(0o755)
    full = {**env, "STUB_VOLUMES": UPGRADE_VOLUMES, "BC_DEPLOY_ADMIN_WAIT_SECONDS": "2", "BC_DEPLOY_RETRY_SLEEP": "0",
            "TMPDIR": str(scratch), "STUB_SIGNAL_PIDFILE": str(pidfile), "STUB_SIGNAL_SCRATCH": str(scratch),
            "STUB_REAL_ID": real_id, **(extra or {})}
    proc = subprocess.Popen(["bash", "-c", 'echo $$ > "$STUB_SIGNAL_PIDFILE"; exec bash deploy.sh'], cwd=work, env=full,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=wait)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return None, out, err


def test_a_term_while_the_script_runs_id_for_the_container_user_still_runs_the_trap(site, tmp_path):
    """`"$(id -u):$(id -g)"` is parsed again each time it is evaluated, and bash runs a trap
    that arrived meanwhile in the middle of that parse: the handler failed with `trap: line
    2: unexpected EOF while looking for matching `)'`, the signal was swallowed, and the
    deploy carried on (importing the key it had been told to stop for). No command
    substitution may be evaluated while the key's traps are armed."""
    scratch = _key_import_site(site, tmp_path)
    status, out, err = _deploy_terminated_by_a_stand_in(site, scratch)
    assert "unexpected EOF" not in err and "trap:" not in err, err[-500:]
    assert status == 143, (status, out[-500:], err[-500:])
    assert not list(scratch.rglob("identity.env")) and not list(scratch.iterdir())
    assert "RESPONDENT_IDENTITY_KEY" not in (site[0] / ".env").read_text(), "the deploy went on after the signal"


def test_a_term_to_the_script_alone_while_the_import_runs_ends_it_at_once(site, tmp_path):
    """A signal that reaches only deploy.sh (`kill <pid>`, a service manager), not the
    process group: bash does not run a trap while a foreground command is still running, so
    the import runs as a background job the script waits for, and the trap stops it."""
    scratch = _key_import_site(site, tmp_path)
    started = time.monotonic()
    status, out, err = _deploy_terminated_by_a_stand_in(site, scratch, extra={"STUB_IMPORT_ENV_HANGS": "1"}, wait=20)
    assert status == 143, (status, out[-500:], err[-500:])
    assert time.monotonic() - started < 15
    assert not list(scratch.rglob("identity.env")) and not list(scratch.iterdir())
    # nothing of the key: not in the output, not in the stand-in's argv log
    assert "RESPONDENT_IDENTITY_KEY=" not in out + err
    assert "identity.env" not in (site[1] / "calls.log").read_text().replace("--env-file /work/identity.env", "")


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


def _trace_of(site, tmp_path, args=(), extra=None, volumes=UPGRADE_VOLUMES):
    work, state, env = site
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    full = {**env, "STUB_VOLUMES": volumes, "BC_DEPLOY_ADMIN_WAIT_SECONDS": "2", "BC_DEPLOY_RETRY_SLEEP": "0",
            "TMPDIR": str(scratch), "PS4": "+${BASH_SUBSHELL}+ ", **(extra or {})}
    done = subprocess.run(["bash", "-x", "deploy.sh", *args], cwd=work, env=full, capture_output=True, text=True, timeout=120)
    return done


def _nested(region):
    """Commands run in a substitution (`++N+`) or in a subshell (`+N+`, N > 0): the container job is the one
    asynchronous command the guard starts on purpose."""
    return [l for l in region if re.match(r"^\++[1-9]\+ |^\+\+", l) and "docker-compose" not in l]


def test_no_command_substitution_runs_while_the_key_traps_are_armed(site, tmp_path):
    """The rule behind the two tests above, read off an execution trace: between arming the
    traps and disarming them, every traced command runs at the top level (a command
    substitution would show as `++`)."""
    _key_import_site(site, tmp_path)
    done = _trace_of(site, tmp_path)
    assert done.returncode == 0, done.stdout[-500:]
    regions = _armed_regions(done.stderr)
    [key_region] = [r for r in regions if any("identity.env" in l for l in r)]
    for region in regions:
        assert not _nested(region), _nested(region)
    assert any("guard_run" in l for l in key_region)


def _prune_trace(site, tmp_path):
    (site[0] / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\nAUTH_JWT_SECRET=DUMMY-jwt\n")
    return _trace_of(site, tmp_path, ["settings-prune", "--apply", "--swap"], volumes="")


def _export_trace(site, tmp_path):
    (site[0] / ".env").write_text("SETTINGS_MASTER_KEY=" + "m" * 64 + "\n")
    return _trace_of(site, tmp_path, ["settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env"], volumes="")


def _upgrade_env_with_identity_key(work):
    """An upgrade that has its identity key already, so no step but the one under test holds a scratch path."""
    _upgrade_env(work)
    with open(work / ".env", "a") as env:
        env.write("RESPONDENT_IDENTITY_KEY=" + "a" * 64 + "\n")


def _umami_trace(site, tmp_path):
    (site[0] / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\n")
    return _trace_of(site, tmp_path, extra={"STUB_UMAMI_ROTATES": "1"}, volumes="")


def _legacy_trace(site, tmp_path):
    _upgrade_env_with_identity_key(site[0])
    (site[0] / ".env.deployment").write_text("UMAMI_PASSWORD=\nexport MONGO_URI=mongodb://u:DUMMY-external@db.example.test:27017\n")
    return _trace_of(site, tmp_path, volumes="app-postgres-data")


@pytest.mark.parametrize("scenario, minimum", [(_prune_trace, 1), (_export_trace, 1), (_umami_trace, 1), (_legacy_trace, 1)])
def test_no_command_substitution_runs_while_any_secret_scratch_path_is_guarded(site, tmp_path, scenario, minimum):
    """The same rule for every step that holds a secret in a scratch file or directory (the
    settings prune and export, the Umami and Mongo blanking, the .env copies), read off an
    execution trace, and off the source for what a trace cannot show (a pipeline)."""
    done = scenario(site, tmp_path)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-800:]
    regions = _armed_regions(done.stderr)
    assert len(regions) >= minimum
    for region in regions:
        assert not _nested(region), _nested(region)


def test_a_new_install_guards_every_scratch_copy_it_makes_and_substitutes_nothing_meanwhile(site, tmp_path):
    done = _trace_of(site, tmp_path, volumes="")
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-800:]
    regions = _armed_regions(done.stderr)
    # the webapp's env file and the .env edits of a first run
    assert len(regions) >= 2 and all(any("+ mv .env." in l for l in r) for r in regions)
    for region in regions:
        assert not _nested(region), _nested(region)


def test_the_guarded_source_has_no_pipeline_substitution_or_subshell_and_one_background_job():
    """What an execution trace cannot show: between `guard_arm "` and the next `guard_disarm` the
    source has no command substitution, process substitution, pipe or subshell, and the guard's
    job is the only background job the script starts (guard_cleanup's `$!` fallback depends on it)."""
    source = (ROOT / "deploy.sh").read_text().splitlines()
    inside, checked = False, 0
    for number, raw in enumerate(source, 1):
        line = raw.split("#", 1)[0] if not re.search(r"['\"].*#.*['\"]", raw) else raw
        if re.search(r'guard_arm "\$', line):
            assert not inside, f"deploy.sh:{number}: armed twice"
            inside = True
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
    assert not inside and checked > 20
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
    for secret in ("DUMMY-jwt-secret", "DUMMY-exported-secret", "DUMMY-old-umami", "DUMMY-external", "m" * 64):
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
    assert not [p for p in work.glob(".env.*") if p.name != ".env.deployment"]
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


def _umami_flow(work):
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=DUMMY-old-umami\n")
    return {"STUB_UMAMI_ROTATES": "1"}, "", "UMAMI_PASSWORD=\n"


def _legacy_flow(work):
    _upgrade_env_with_identity_key(work)
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nexport MONGO_URI=mongodb://u:DUMMY-external@db.example.test:27017\n")
    return {}, "app-postgres-data", "UMAMI_PASSWORD=\nexport MONGO_URI=\n"


@pytest.mark.parametrize("flow", [_umami_flow, _legacy_flow])
def test_a_term_while_a_copy_of_env_deployment_is_blanked_still_runs_the_trap_and_removes_it(site, tmp_path, flow):
    """The Umami and Mongo blanking edit a copy of .env.deployment in a private directory: a
    signal while it exists must remove the copy, not leave the file behind."""
    work, state, _ = site
    extra, volumes, blanked = flow(work)
    scratch = _scratch(tmp_path)
    status, out, err, seconds = _term_the_script_alone(
        site, scratch, [], extra={**extra, "STUB_SIGNAL_CMD": "cat"}, volumes=volumes)
    assert status == 143, (status, out[-500:], err[-500:])
    assert "trap:" not in err and "unexpected EOF" not in err
    assert not list(scratch.iterdir()), list(scratch.rglob("*"))
    assert (state / "signalled").exists() and (work / ".env.deployment").read_text() == blanked  # it landed there
    _nothing_secret_shown(site, out, err)


# --- the guard around the .env edits, run on the functions alone ---------------------------

GUARDED_FUNCTIONS = ("guard_cleanup", "guard_arm", "guard_disarm", "file_assigns", "env_unset", "env_put",
                     "dotenv_unquote", "service_env_file")


def _functions(*names):
    """The source of deploy.sh's functions NAMES (and the guard's variables), to run them alone."""
    text = (ROOT / "deploy.sh").read_text()
    out = ['guard_path=""\nguard_pid=""\nguard_started=""\n']
    for name in names:
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.S | re.M)
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
    """service_env_file used to swallow a failed `mv` and report the file as created; it now fails."""
    work, _, _ = site
    _stand_in(site, "mv", "#!/bin/sh\nexit 1\n")
    (work / ".env.deployment").write_text("FOO=1\n")
    done = _functions_run(site, 'service_env_file .env.webapp FOO; echo "rc=$?"\n')
    assert "rc=1" in done.stdout and "Created" not in done.stdout and "Could not create .env.webapp" in done.stderr
    assert not (work / ".env.webapp").exists() and not _temp_leftovers(work)


def test_a_chmod_that_fails_does_not_stop_service_env_file(site):
    """Some bind mounts (vfat, CIFS) refuse chmod; the file is already 600 from the umask, so the
    deploy carries on (a failed write or rename still stops it, see the failing-mv test)."""
    work, _, _ = site
    _stand_in(site, "chmod", "#!/bin/sh\nexit 1\n")
    (work / ".env.deployment").write_text("FOO=1\n")
    done = _functions_run(site, 'service_env_file .env.webapp FOO; echo "rc=$?"\n')
    assert "rc=0" in done.stdout and "Could not create" not in done.stderr, (done.stdout, done.stderr)
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
    assert not _temp_leftovers(work) and not _temp_leftovers(work)


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
    # an assignment appended to a file that does not end in a newline, value taken literally
    (work / ".env").write_bytes(b"X=1")
    done = _functions_run(site, "env_put NEW 'a=b $c \"d\" \\e'\n")
    assert done.returncode == 0, done.stderr
    assert (work / ".env").read_bytes() == b'X=1\nNEW=a=b $c "d" \\e\n'
    # replacing an existing assignment
    done = _functions_run(site, "env_put X two\n")
    assert (work / ".env").read_bytes() == b'NEW=a=b $c "d" \\e\nX=two\n'


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
    assert "Created .env.webapp from .env.deployment with: FOO, NEXT_PUBLIC_A, NEXT_PUBLIC_B, NEXT_PUBLIC_C, NEXT_PUBLIC_LAST\n" in done.stdout
    assert (work / ".env.webapp").read_bytes() == (
        b"FOO=1\r\n"
        b"NEXT_PUBLIC_A='single quoted'\n"
        b"NEXT_PUBLIC_B = with=equals $dollar \\ back\n"
        b"NEXT_PUBLIC_C=exported # trailing\n"
        b"FOO=dup\n"
        b"NEXT_PUBLIC_LAST=nonl\n"
    )
    assert stat.S_IMODE((work / ".env.webapp").stat().st_mode) == 0o600 and not _temp_leftovers(work)
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


def test_a_failed_export_removes_its_directory_and_writes_nothing(site, tmp_path):
    work, state, _ = site
    (work / ".env").write_text(SECRET_ENV)
    scratch = _scratch(tmp_path)
    done, calls = _run(site, "settings-env-export", "--keys", "UMAMI_PASSWORD", "--out", "out.env",
                       extra={"TMPDIR": str(scratch), "STUB_EXPORT_FAILS": "1"})
    assert done.returncode == 1 and not (work / "out.env").exists()
    assert not list(scratch.iterdir())
    _nothing_secret_shown(site, done.stdout, done.stderr)


def test_the_temporal_namespace_of_the_old_stack_is_asked(site):
    work, state, _ = site
    _upgrade_env(work)
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\nTEMPORAL_NAMESPACE=custom-ns\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra=TEMPORAL_ENV)
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
    asked = [c for c in _docker_calls(state) if "temporal workflow list" in c]
    assert asked and all("--namespace custom-ns" in c for c in asked)
    shutil.rmtree(state / "store", ignore_errors=True)
    (state / "docker.log").unlink()
    (work / ".env.deployment").write_text("UMAMI_PASSWORD=\n")
    (work / ".env.worker").write_text("NAMESPACE=worker-ns\n")
    done, _ = _run(site, volumes=UPGRADE_VOLUMES, extra=TEMPORAL_ENV)
    assert done.returncode == 0
    assert all("--namespace worker-ns" in c for c in _docker_calls(state) if "temporal workflow list" in c)
