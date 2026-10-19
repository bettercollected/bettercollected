"""The host CLI of the settings store, on real Postgres: import from compose
config, drift, prune, break-glass export, key bootstrap, host set/restore, the
setup token, the master-key fingerprint and the admin mail guard."""

from __future__ import annotations

import base64
import json
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from backend.admin.services import host_settings as host
from backend.admin.services import setup_token
from backend.admin.services.settings_store import Actor, SettingsError
from tests.admin.test_settings_store import (  # noqa: F401  (fixtures)
    ADMIN,
    CLI,
    MASTER_KEY,
    PLANT,
    SECRET,
    T1,
    T2,
    T3,
    T4,
    make_keys,
    put,
    run_cli,
    scalar,
    superuser,
    svc,
)
from tests.admin.conftest import needs_postgres

pytestmark = needs_postgres

STRONG = "stable-strong-secret-value-0123456789abcdef"
JWT_OTHER = "another-strong-secret-value-fedcba9876543210"


async def empty_counts():
    return {"users": {"total": 0}, "responses": {"total": 0}}


def compose(**services: dict) -> str:
    return json.dumps({"services": {name: {"environment": env} for name, env in services.items()}})


async def audit_actions(service) -> list[tuple[str, str]]:
    async with service._engine.connect() as conn:
        rows = await conn.execute(text("SELECT action, actor_kind FROM admin.audit_log ORDER BY seq"))
        return [tuple(r) for r in rows]


# ------------------------------------------------------------------ import


async def test_import_plan_classifies_every_name_and_dry_run_changes_nothing(svc, superuser):
    await put(svc, "API_FLOW_EVENTS_WINDOW_SECONDS", 30)
    config = host.parse_compose_config(
        compose(
            backend={
                T1: "33",
                "API_FLOW_EVENTS_WINDOW_SECONDS": "30",
                T4: STRONG,
                "AUTH_BASE_URL": "http://auth:8000",
                "NOT_A_THING": "x",
                "OPENAI_API_KEY": "",
                "API_DOCS_ENABLED": "true",
            },
            auth={T4: STRONG, "STRIPE_SECRET": "weak"},
            typeform={"AUTH_JWT_SECRET": "ignored"},
        )
    )
    assert "typeform" not in config
    plan = await host.plan_import(svc, config)
    assert plan.counts() == {
        "would_import": 4,  # T1, API_DOCS_ENABLED, STRIPE_SECRET and T4 (the same value in two readers)
        "already_in_store": 1,
        "empty": 1,
        "unknown": 1,
        "env_only": 1,
        "conflict": 0,
        "refused": 0,
    }
    assert set(plan.would_import) == {T1, T4, "API_DOCS_ENABLED", "STRIPE_SECRET"}
    assert await scalar(superuser, "SELECT count(*) FROM settings.entries") == 1  # only the one put above
    assert "STRIPE_SECRET" not in repr(plan) and STRONG not in repr(plan)


async def test_conflicting_values_import_neither_until_a_service_is_preferred(svc):
    config = host.parse_compose_config(
        compose(backend={T4: STRONG}, auth={T4: JWT_OTHER}, **{"jobs-worker": {T4: STRONG}})
    )
    plan = await host.plan_import(svc, config)
    assert plan.conflict == {T4: ["auth", "backend", "jobs-worker"]}
    assert T4 not in plan.would_import
    done = await host.import_config(svc, plan, CLI)
    assert done.imported == []
    preferred = await host.plan_import(svc, config, prefer="auth")
    assert preferred.conflict == {} and preferred.would_import[T4] == JWT_OTHER
    done = await host.import_config(svc, preferred, CLI)
    assert done.imported == [T4]
    stored = await svc.stored()
    assert stored.values[T4] == JWT_OTHER
    again = await host.plan_import(svc, config)
    assert again.already_in_store == [T4] and not again.conflict


async def test_equal_values_that_spell_differently_are_not_a_conflict(svc):
    config = host.parse_compose_config(
        compose(backend={"API_DOCS_ENABLED": "true"}, auth={"API_DOCS_ENABLED": "True"})
    )
    plan = await host.plan_import(svc, config)
    assert not plan.conflict and set(plan.would_import) == {"API_DOCS_ENABLED"}


async def test_a_shipped_or_invalid_value_is_refused_with_a_reason_only(svc):
    config = host.parse_compose_config(compose(backend={T1: "not-a-number", "API_TRUSTED_PROXIES": "0.0.0.0/0"}))
    plan = await host.plan_import(svc, config)
    assert dict(plan.refused) == {T1: "not_number", "API_TRUSTED_PROXIES": "too_wide"}
    assert plan.would_import == {}


def test_a_bad_compose_document_is_refused():
    for raw in ("not json", "[]", json.dumps({"services": []})):
        with pytest.raises(host.HostError):
            host.parse_compose_config(raw)


async def test_import_from_compose_config_cli_dry_run_then_apply(svc, server, migrated):
    url = server.url(migrated, "runtime")
    stdin = compose(backend={SECRET: PLANT, T1: "44"}, auth={"MAIL_PASSWORD": PLANT + "x"})
    import subprocess
    import sys

    from tests.admin.test_settings_store import BACKEND_ROOT

    def cli(*args):
        env = {k: v for k, v in os.environ.items() if k not in ("SETTINGS_MASTER_KEY", "ADMIN_DATABASE_URL")}
        env.update({"ADMIN_DATABASE_URL": url, "SETTINGS_MASTER_KEY": MASTER_KEY})
        return subprocess.run(
            [sys.executable, "-m", "backend.admin", *args],
            cwd=BACKEND_ROOT, env=env, input=stdin, capture_output=True, text=True, timeout=120,
        )

    dry = cli("settings-import", "--from-compose-config", "--dry-run")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert "would_import=3" in dry.stdout and f"would_import {T1}" in dry.stdout
    assert PLANT not in dry.stdout + dry.stderr
    assert await scalar(svc._engine, "SELECT count(*) FROM settings.entries") == 0
    applied = cli("settings-import", "--from-compose-config")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert f"imported {T1}" in applied.stdout and PLANT not in applied.stdout + applied.stderr
    assert (await svc.stored()).values[T1] == 44
    kinds = {kind for _, kind in await audit_actions(svc)}
    assert kinds == {"cli"}


# ------------------------------------------------------------------- drift


async def test_drift_reports_equal_differs_env_only_and_store_only_by_name(svc):
    await put(svc, T1, 33)
    await put(svc, SECRET, PLANT)
    await put(svc, "API_FLOW_EVENTS_WINDOW_SECONDS", 61)
    await svc.import_once("TEMPORAL_API_KEY", STRONG, CLI)
    await svc.import_once("AUTH_AES_HEX_KEY", host.Fernet.generate_key().decode(), CLI)
    stored = await svc.stored()
    config = host.parse_compose_config(
        compose(
            backend={
                T1: "33",  # equal, spelled as text
                SECRET: PLANT + "-stale",  # differs
                "API_DOCS_ENABLED": "true",  # env only
                "TEMPORAL_API_KEY": STRONG,
            },
            worker={"API_KEY": STRONG, "AES_HEX_KEY": "not-the-stored-key"},
        )
    )
    report = await host.plan_drift(svc, config)
    assert set(report.equal) == {T1, "TEMPORAL_API_KEY"}
    assert report.differs == {SECRET: ["backend"], "AUTH_AES_HEX_KEY": ["worker"]}
    assert report.env_only == ["API_DOCS_ENABLED"]
    assert report.store_only == ["API_FLOW_EVENTS_WINDOW_SECONDS"]
    assert not report.clean
    assert PLANT not in repr(report) and PLANT not in repr(stored)


async def test_drift_flags_a_keyset_that_lacks_a_key_id_of_the_environment(svc):
    from common.services import keyset as keyset_module
    from tink.proto import tink_pb2

    one = keyset_module.add_primary_key(tink_pb2.Keyset())
    two = keyset_module.add_primary_key(one)  # a rotation: one's key plus a new primary
    other = keyset_module.add_primary_key(tink_pb2.Keyset())
    await svc.import_once("MASTER_ENCRYPTION_KEYSET", keyset_module.encode_keyset(two), CLI)

    def drift(env_keyset):
        return host.plan_drift(svc, host.parse_compose_config(compose(backend={"MASTER_ENCRYPTION_KEYSET": env_keyset})))

    same = await drift(keyset_module.encode_keyset(two))
    older = await drift(keyset_module.encode_keyset(one))  # the store has every id of the older env keyset
    assert same.equal == older.equal == ["MASTER_ENCRYPTION_KEYSET"]
    stale = await drift(keyset_module.encode_keyset(other))
    assert stale.differs == {"MASTER_ENCRYPTION_KEYSET": ["backend"]} and not stale.clean
    garbage = await drift("not-a-keyset")
    assert garbage.differs == {"MASTER_ENCRYPTION_KEYSET": ["backend"]}


async def test_an_empty_env_value_is_not_drift(svc):
    await put(svc, T1, 33)
    report = await host.plan_drift(svc, host.parse_compose_config(compose(backend={T1: ""})))
    assert report.store_only == [T1] and report.clean


async def test_drift_cli_exit_codes_and_output(svc, server, migrated, tmp_path):
    await put(svc, T1, 33)
    url = server.url(migrated, "runtime")
    equal = tmp_path / "equal.env"
    equal.write_text(f"{T1}=33\n")
    ok = run_cli(url, "settings-drift", "--env-file", str(equal))
    assert ok.returncode == 0 and "equal=1" in ok.stdout
    stale = tmp_path / "stale.env"
    stale.write_text(f"{T1}=34\n")
    bad = run_cli(url, "settings-drift", "--env-file", str(stale))
    assert bad.returncode == 1 and f"differs {T1} env-file" in bad.stdout


# ------------------------------------------------------------------- prune


def private(path) -> bool:
    return stat.S_IMODE(os.stat(path).st_mode) == 0o600


async def test_prune_removes_only_what_the_store_holds_and_keeps_everything_else(svc, tmp_path):
    await put(svc, T1, 33)
    await put(svc, SECRET, PLANT)
    await svc.import_once("TEMPORAL_API_KEY", STRONG, CLI)
    env = tmp_path / ".env"
    original = (
        "# comment\n"
        f"{T1}=33\n"
        f"export {SECRET}='{PLANT}'\n"
        "API_FLOW_EVENTS_WINDOW_SECONDS=\n"
        "UNRELATED=1\n"
        f"TEMPORAL_API_KEY={STRONG}\n"
        "API_DOCS_ENABLED=true\n"
        "\n"
    )
    env.write_text(original)
    dry = await host.prune_env_files(svc, [str(env)], apply=False, actor=CLI)
    assert dry[0].pruned == [T1, SECRET, "TEMPORAL_API_KEY"] and env.read_text() == original
    assert not (tmp_path / ".env.pruned").exists()
    done = await host.prune_env_files(svc, [str(env)], apply=True, keep=["TEMPORAL_API_KEY"], actor=CLI, clock=lambda: 0)
    assert done[0].pruned == [T1, SECRET]
    pruned = tmp_path / ".env.pruned"
    assert pruned.read_text() == (
        "# comment\nAPI_FLOW_EVENTS_WINDOW_SECONDS=\nUNRELATED=1\n"
        f"TEMPORAL_API_KEY={STRONG}\nAPI_DOCS_ENABLED=true\n\n"
    )
    backup = tmp_path / ".env.pre-v4.19700101000000"
    assert backup.read_text() == original and private(backup) and private(pruned)
    assert env.read_text() == original  # no swap: the original stays
    actions = await audit_actions(svc)
    assert ("cli.settings_prune", "cli") in actions
    async with svc._engine.connect() as conn:
        detail = (await conn.execute(text("SELECT detail::text FROM admin.audit_log WHERE action = 'cli.settings_prune'"))).scalar()
    assert PLANT not in detail and STRONG not in detail


async def test_prune_never_removes_a_differing_value_and_never_overwrites(svc, tmp_path):
    await put(svc, T1, 33)
    env = tmp_path / "env"
    env.write_text(f"{T1}=99\nAPI_FLOW_EVENTS_WINDOW_SECONDS=1\n")
    reports = await host.prune_env_files(svc, [str(env)], apply=True, actor=CLI)
    assert reports[0].refused == {T1: "differs"} and reports[0].pruned == []
    assert not (tmp_path / "env.pruned").exists()
    # an env value that equals the store but sits next to a stale one in another file
    await put(svc, "API_FLOW_EVENTS_WINDOW_SECONDS", 1)
    env.write_text("API_FLOW_EVENTS_WINDOW_SECONDS=1\n")
    (tmp_path / "env.pruned").write_text("someone's file")
    with pytest.raises(host.HostError) as err:
        await host.prune_env_files(svc, [str(env)], apply=True, actor=CLI)
    assert err.value.code == "file_exists"
    assert (tmp_path / "env.pruned").read_text() == "someone's file"
    assert env.read_text() == "API_FLOW_EVENTS_WINDOW_SECONDS=1\n"
    assert not [p for p in tmp_path.iterdir() if ".pre-v4." in p.name]  # the backup was rolled back
    assert ("cli.settings_prune", "cli") not in await audit_actions(svc)


async def test_prune_swap_replaces_the_original_privately(svc, tmp_path):
    await put(svc, T1, 33)
    env = tmp_path / "env"
    env.write_text(f"{T1}=33\nKEEP=1\n")
    os.chmod(env, 0o644)
    await host.prune_env_files(svc, [str(env)], apply=True, swap=True, actor=CLI)
    assert env.read_text() == "KEEP=1\n" and private(env)
    assert not (tmp_path / "env.pruned").exists()


async def test_prune_refuses_while_the_store_has_unverified_rows(svc, superuser, tmp_path):
    await put(svc, T1, 33)
    async with superuser.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(text("UPDATE settings.entries SET value = '5'::jsonb WHERE key = :k"), {"k": T1})
    env = tmp_path / "env"
    env.write_text(f"{T1}=5\n")
    with pytest.raises(host.HostError) as err:
        await host.prune_env_files(svc, [str(env)], apply=True, actor=CLI)
    assert err.value.code == "store_unverified"


async def test_prune_cli_exit_code_signals_a_differing_key(svc, server, migrated, tmp_path):
    await put(svc, T1, 33)
    url = server.url(migrated, "runtime")
    env = tmp_path / "env"
    env.write_text(f"{T1}=34\n")
    result = run_cli(url, "settings-prune", "--env-file", str(env))
    assert result.returncode == 1 and f"refused {T1} differs" in result.stdout
    assert "dry run" in result.stdout


# ------------------------------------------------------------------ export


async def test_env_export_is_private_audited_and_never_overwrites(svc, tmp_path):
    await put(svc, T1, 33)
    await put(svc, SECRET, PLANT)
    out = tmp_path / "break-glass.env"
    assert await host.export_env(svc, [T1, SECRET], str(out), CLI) == 2
    assert private(out)
    assert out.read_text() == f"{T1}=33\n{SECRET}={PLANT}\n"
    with pytest.raises(host.HostError) as err:
        await host.export_env(svc, [T1], str(out), CLI)
    assert err.value.code == "file_exists"
    async with svc._engine.connect() as conn:
        rows = (await conn.execute(text("SELECT detail::text FROM admin.audit_log WHERE action = 'cli.settings_env_export'"))).all()
    assert len(rows) == 1 and T1 in rows[0][0] and PLANT not in rows[0][0]


async def test_env_export_refuses_unknown_and_unset_keys_and_writes_nothing(svc, tmp_path):
    await put(svc, T1, 33)
    out = tmp_path / "x.env"
    for names, code in (([T1, "NOPE"], "unknown_key"), ([T1, T2], "not_in_store"), ([], "no_keys")):
        with pytest.raises(host.HostError) as err:
            await host.export_env(svc, names, str(out), CLI)
        assert err.value.code == code
    assert not out.exists()


async def test_env_export_quotes_what_compose_would_misread(svc, tmp_path):
    await svc.set(T3, "https://a.example.org/v1?x=1&y=2", CLI, confirmation=T3)
    out = tmp_path / "q.env"
    await host.export_env(svc, [T3], str(out), CLI)
    assert out.read_text() == f"{T3}='https://a.example.org/v1?x=1&y=2'\n"
    assert host.env_line("A", "has space") == "A='has space'\n"
    with pytest.raises(host.HostError):
        host.env_line("A", "it's\n")


async def test_env_export_cli_prints_no_value(svc, server, migrated, tmp_path):
    await put(svc, SECRET, PLANT)
    out = tmp_path / "b.env"
    result = run_cli(server.url(migrated, "runtime"), "settings-env-export", "--keys", SECRET, "--out", str(out))
    assert result.returncode == 0 and PLANT not in result.stdout + result.stderr
    assert PLANT in out.read_text() and private(out)
    again = run_cli(server.url(migrated, "runtime"), "settings-env-export", "--keys", SECRET, "--out", str(out))
    assert again.returncode == 1 and "file_exists" in again.stderr


# ------------------------------------------------------------- bootstrap


async def test_bootstrap_generates_every_key_valid_and_prints_nothing(svc, server, migrated, superuser, tmp_path):
    await seed_stack(server, migrated, superuser)
    from common.configs import shipped_secrets
    from common.services import keyset

    url = server.url(migrated, "runtime")
    worker = tmp_path / ".env"
    result = run_cli(url, "bootstrap-keys", "--export-worker", str(worker), extra={**{k: "" for k in host.GENERATED_KEYS}, "MONGO_URI": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    stored = (await svc.stored()).values
    assert set(host.GENERATED_KEYS) <= set(stored)
    for value in (stored[k] for k in host.GENERATED_KEYS):
        assert value not in result.stdout + result.stderr
    assert shipped_secrets.is_fernet_key(stored["AUTH_AES_HEX_KEY"])
    assert len(keyset.parse_keyset(stored["MASTER_ENCRYPTION_KEYSET"]).key) == 1
    assert "generated=5" in result.stdout and "master_key_fingerprint " in result.stdout
    from common.settings.loader.runtime import keyset_fingerprint

    ids = [k.key_id for k in keyset.parse_keyset(stored["MASTER_ENCRYPTION_KEYSET"]).key]
    assert f"keyset_fingerprint {keyset_fingerprint(ids)}" in result.stdout
    assert private(worker)
    assert worker.read_text() == f"API_KEY={stored['TEMPORAL_API_KEY']}\nAES_HEX_KEY={stored['AUTH_AES_HEX_KEY']}\n"
    assert await svc.verify() == []
    assert {kind for _, kind in await audit_actions(svc)} == {"cli"}


async def seed_stack(server, migrated, superuser, *, users=0, responses=0):
    """The application tables behind ``admin.platform_counts()``, with some rows."""
    from backend.db.startup import MIGRATIONS as APP
    from common.db.ddl import helper_function_ddl
    from common.db.schema_guard import upgrade_schema
    from tests.admin.conftest import roles_sql
    from tests.app.db.test_auto_migrate import _execute

    await upgrade_schema(server.url(migrated), APP)
    async with superuser.begin() as conn:
        for statement in helper_function_ddl("auth"):
            await conn.execute(text(statement))
        await conn.execute(text(
            "CREATE TABLE auth.users (id text PRIMARY KEY, doc jsonb NOT NULL, "
            "plan text GENERATED ALWAYS AS (auth.bc_text(doc -> 'plan')) STORED)"))
        for n in range(users):
            await conn.execute(text("INSERT INTO auth.users (id, doc) VALUES (:i, CAST('{}' AS jsonb))"), {"i": f"u{n}"})
        for n in range(responses):
            await conn.execute(
                text("INSERT INTO app.form_responses (id, doc, created_at, _bc_checksum) "
                     "VALUES (:i, CAST('{\"answers\": {}}' AS jsonb), now(), 'x')"),
                {"i": str(__import__("bson").ObjectId())},
            )
    await _execute(server.url(migrated), roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw))


@pytest.mark.parametrize("users,responses", [(0, 1), (1, 0)])
async def test_bootstrap_refuses_a_stack_that_holds_data_whatever_the_flags(
    svc, server, migrated, superuser, users, responses
):
    await seed_stack(server, migrated, superuser, users=users, responses=responses)
    url = server.url(migrated, "runtime")
    clean = {k: "" for k in host.GENERATED_KEYS}
    for flags in ((), ("--fill-missing",)):
        result = run_cli(url, "bootstrap-keys", *flags, extra=clean)
        assert result.returncode == 1 and "stack_has_data" in result.stderr and "settings-import" in result.stderr
    assert (await svc.stored()).values == {}


async def test_bootstrap_fails_closed_when_the_counts_cannot_be_read(svc, server, migrated):
    # no application tables in this database: platform_counts() fails
    result = run_cli(server.url(migrated, "runtime"), "bootstrap-keys", extra={**{k: "" for k in host.GENERATED_KEYS}, "MONGO_URI": ""})
    assert result.returncode == 1 and "stack_unknown" in result.stderr
    assert (await svc.stored()).values == {}

    async def broken():
        raise RuntimeError("password=hunter2")

    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=broken)
    assert err.value.code == "stack_unknown" and "hunter2" not in str(err.value)
    assert (await svc.stored()).values == {}


async def test_bootstrap_checks_the_document_store_when_one_is_configured(svc):
    seen = []

    async def full(uri):
        seen.append(uri)
        return True

    async def down(uri):
        raise ConnectionError(uri)

    env = {"MONGO_URI": "mongodb://u:pw@db/"}
    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ=env, existing_stack=False, counts=empty_counts, mongo_check=full)
    assert err.value.code == "stack_has_data" and seen
    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ=env, existing_stack=False, counts=empty_counts, mongo_check=down)
    assert err.value.code == "stack_unknown" and "pw" not in str(err.value)
    assert (await svc.stored()).values == {}

    async def empty(uri):
        return False

    done = await host.bootstrap_keys(svc, CLI, environ=env, existing_stack=False, counts=empty_counts, mongo_check=empty)
    assert len(done.generated) == 5 and done.keyset_fp.startswith("ks-")


async def test_bootstrap_refuses_an_existing_stack_existing_keys_and_env_keys(svc):
    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=True, counts=empty_counts)
    assert err.value.code == "existing_stack"
    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ={"MASTER_ENCRYPTION_KEYSET": "x"}, existing_stack=False, counts=empty_counts)
    assert err.value.code == "keys_in_environment"
    assert (await svc.stored()).values == {}
    first = await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts)
    assert first.generated == list(host.GENERATED_KEYS)
    before = (await svc.stored()).values
    with pytest.raises(host.HostError) as err:
        await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts)
    assert err.value.code == "keys_exist"
    assert (await svc.stored()).values == before


async def test_bootstrap_fill_missing_adds_only_the_missing_keys(svc):
    await svc.import_once("AUTH_JWT_SECRET", STRONG, CLI)
    done = await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts, fill_missing=True)
    assert "AUTH_JWT_SECRET" not in done.generated and len(done.generated) == 4
    assert (await svc.stored()).values["AUTH_JWT_SECRET"] == STRONG


async def test_worker_export_appends_to_a_private_env_file_but_not_twice(svc, tmp_path):
    await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts)
    env = tmp_path / ".env"
    env.write_text("EXISTING=1")
    os.chmod(env, 0o600)
    await host.export_worker(svc, str(env), CLI)
    lines = env.read_text().splitlines()
    assert lines[0] == "EXISTING=1" and lines[1].startswith("API_KEY=") and lines[2].startswith("AES_HEX_KEY=")
    with pytest.raises(host.HostError) as err:
        await host.export_worker(svc, str(env), CLI)
    assert err.value.code == "worker_keys_present"
    loose = tmp_path / "loose.env"
    loose.write_text("A=1\n")
    os.chmod(loose, 0o644)
    with pytest.raises(host.HostError) as err:
        await host.export_worker(svc, str(loose), CLI)
    assert err.value.code == "file_not_private" and loose.read_text() == "A=1\n"


async def test_worker_export_never_follows_a_symlink(svc, tmp_path):
    await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts)
    target = tmp_path / "other-private.env"
    target.write_text("KEEP=1\n")
    os.chmod(target, 0o600)
    link = tmp_path / "link.env"
    link.symlink_to(target)
    with pytest.raises(host.HostError) as err:
        await host.export_worker(svc, str(link), CLI)
    assert err.value.code == "file_not_private"
    assert target.read_text() == "KEEP=1\n"  # nothing was appended through the link
    dangling = tmp_path / "dangling.env"
    dangling.symlink_to(tmp_path / "created-by-attacker.env")
    with pytest.raises(host.HostError):
        await host.export_worker(svc, str(dangling), CLI)
    assert not (tmp_path / "created-by-attacker.env").exists()


def test_append_private_checks_the_opened_file_not_the_path(tmp_path):
    good = tmp_path / "good.env"
    good.write_text("A=1")
    os.chmod(good, 0o600)
    host._append_private(str(good), "B=2\n")
    assert good.read_text() == "A=1\nB=2\n"
    other = tmp_path / "other.env"
    other.write_text("A=1\n")
    os.chmod(other, 0o600)
    link = tmp_path / "link.env"
    link.symlink_to(other)
    with pytest.raises(host.HostError):
        host._append_private(str(link), "B=2\n")
    assert other.read_text() == "A=1\n"
    fifo = tmp_path / "fifo.env"
    os.mkfifo(fifo, 0o600)  # not a regular file
    with pytest.raises(host.HostError):
        host._append_private(str(fifo), "B=2\n")


async def test_worker_export_needs_the_keys_in_the_store(svc, tmp_path):
    with pytest.raises(host.HostError) as err:
        await host.export_worker(svc, str(tmp_path / "w.env"), CLI)
    assert err.value.code == "not_in_store" and not (tmp_path / "w.env").exists()


# -------------------------------------------------------------- set/restore


async def test_host_set_needs_no_step_up_but_a_typed_confirmation_for_t3(svc, server, migrated):
    url = server.url(migrated, "runtime")
    ok = run_cli(url, "settings-set", T2, "--value", "google", "--yes")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert (await svc.stored()).values[T2] == "google"
    no_confirm = run_cli(url, "settings-set", T3, "--value", "https://a.example.org/v1", "--yes")
    assert no_confirm.returncode == 1 and "confirmation_required" in no_confirm.stderr
    confirmed = run_cli(url, "settings-set", T3, "--value", "https://a.example.org/v1", "--confirm", T3, "--yes")
    assert confirmed.returncode == 0, confirmed.stdout + confirmed.stderr
    # the portal's actors are unchanged: an admin still needs a step-up
    with pytest.raises(SettingsError) as err:
        await svc.set(T2, "openai", ADMIN, expected_version=1)
    assert err.value.code == "step_up_required"
    assert {kind for _, kind in await audit_actions(svc)} == {"cli"}


async def test_host_set_refuses_secrets_on_the_command_line_t4_t5_and_missing_yes(svc, server, migrated):
    url = server.url(migrated, "runtime")
    argv = run_cli(url, "settings-set", SECRET, "--value", PLANT, "--confirm", SECRET, "--yes")
    assert argv.returncode == 2 and PLANT not in argv.stdout + argv.stderr
    assert (await svc.stored()).values == {}
    assert run_cli(url, "settings-set", T1, "--value", "5").returncode == 2  # no --yes
    with pytest.raises(SettingsError) as err:  # key material is rotated by a task, not set by hand
        await svc.set(T4, STRONG, CLI)
    assert err.value.code == "managed_by_task"
    t5 = run_cli(url, "settings-set", "DATABASE_URL", "--value", "x", "--yes")
    assert t5.returncode == 1 and "env_only" in t5.stderr
    assert (await svc.stored()).values == {}


async def test_host_set_reads_a_secret_from_standard_input(svc, server, migrated):
    import subprocess
    import sys

    from tests.admin.test_settings_store import BACKEND_ROOT

    env = {k: v for k, v in os.environ.items() if k not in ("SETTINGS_MASTER_KEY", "ADMIN_DATABASE_URL")}
    env.update({"ADMIN_DATABASE_URL": server.url(migrated, "runtime"), "SETTINGS_MASTER_KEY": MASTER_KEY})
    done = subprocess.run(
        [sys.executable, "-m", "backend.admin", "settings-set", SECRET, "--stdin", "--confirm", SECRET, "--yes"],
        cwd=BACKEND_ROOT, env=env, input=PLANT + "\n", capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert PLANT not in done.stdout + done.stderr
    assert (await svc.stored()).values[SECRET] == PLANT


async def test_host_restore_and_history(svc, server, migrated):
    url = server.url(migrated, "runtime")
    await svc.set(T2, "openai", CLI)
    await svc.set(T2, "google", CLI)
    history = run_cli(url, "settings-history", T2)
    assert history.returncode == 0 and "versions=2" in history.stdout
    assert run_cli(url, "settings-restore", T2, "--version", "1").returncode == 2  # no --yes
    restored = run_cli(url, "settings-restore", T2, "--version", "1", "--yes")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert (await svc.stored()).values[T2] == "openai"
    missing = run_cli(url, "settings-restore", T2, "--version", "9", "--yes")
    assert missing.returncode == 1 and "no_such_version" in missing.stderr
    assert await svc.verify() == []


# ------------------------------------------------------------- setup token


async def issue(engine, replace=False):
    async with engine.begin() as conn:
        return await setup_token.issue(conn, bytes(range(48)), "operator", replace=replace)


async def redeem(engine, token):
    async with engine.begin() as conn:
        return await setup_token.redeem(conn, bytes(range(48)), token)


async def test_setup_token_is_160_bits_hashed_at_rest_single_use_and_replaceable(svc):
    engine = svc._engine
    token, replaced = await issue(engine)
    assert not replaced and len(token) == 32 and token.isalnum() and token == token.upper()
    dump = " ".join(
        str(v) for row in (await _rows(engine)) for v in row
    )
    assert token not in dump and setup_token.display(token) not in dump
    with pytest.raises(setup_token.SetupTokenError) as err:
        await issue(engine)
    assert err.value.code == "token_active"
    newer, replaced = await issue(engine, replace=True)
    assert replaced and newer != token
    assert await redeem(engine, token) is False  # revoked
    assert await redeem(engine, setup_token.display(newer).lower()) is True  # grouping and case do not matter
    assert await redeem(engine, newer) is False  # single use
    async with engine.connect() as conn:
        assert await setup_token.active(conn) is None


async def _rows(engine):
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT token_mac, issued_by, failed_attempts FROM admin.setup_tokens"))).all()


async def test_setup_token_lives_for_60_minutes(svc):
    await issue(svc._engine)
    async with svc._engine.connect() as conn:
        window = (await conn.execute(text("SELECT expires_at - created_at FROM admin.setup_tokens"))).scalar()
    assert timedelta(minutes=60) <= window < timedelta(minutes=60, seconds=5)


async def test_twenty_wrong_tries_lock_the_token_for_good(svc):
    engine = svc._engine
    token, _ = await issue(engine)
    for _ in range(20):
        assert await redeem(engine, "WRONG") is False
    assert await redeem(engine, token) is False
    async with engine.connect() as conn:
        assert await setup_token.active(conn) is None
    again, _ = await issue(engine)  # a locked token does not block a new one
    assert await redeem(engine, again) is True


async def test_an_expired_token_cannot_be_redeemed_and_does_not_block_a_new_one(svc, superuser):
    engine = svc._engine
    token, _ = await issue(engine)
    async with superuser.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_tokens SET expires_at = now() - interval '1 second'"))
    assert await redeem(engine, token) is False
    fresh, _ = await issue(engine)
    assert await redeem(engine, fresh) is True


async def test_setup_closes_once_an_admin_has_a_second_factor(svc):
    engine = svc._engine
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO admin.factors (email, secret_blob, key_id, confirmed_at) "
                "VALUES ('a@example.org', 'x', 'k', now())"
            )
        )
    with pytest.raises(setup_token.SetupTokenError) as err:
        await issue(engine, replace=True)
    assert err.value.code == "setup_closed"


async def test_setup_token_cli_console_only_audited_and_hashed(svc, server, migrated):
    url = server.url(migrated, "runtime")
    refused = run_cli(url, "setup-token")
    assert refused.returncode == 2 and "console" in refused.stderr
    assert await scalar(svc._engine, "SELECT count(*) FROM admin.setup_tokens") == 0
    first = run_cli(url, "setup-token", "--allow-non-tty")
    assert first.returncode == 0, first.stdout + first.stderr
    token = first.stdout.strip().splitlines()[-1]
    assert len(token.replace("-", "")) == 32
    second = run_cli(url, "setup-token", "--allow-non-tty")
    assert second.returncode == 1 and "token_active" in second.stderr and token not in second.stdout + second.stderr
    third = run_cli(url, "setup-token", "--allow-non-tty", "--new")
    assert third.returncode == 0
    async with svc._engine.connect() as conn:
        audit_text = " ".join(
            r[0] for r in (await conn.execute(text("SELECT coalesce(detail::text, '') FROM admin.audit_log"))).all()
        )
        actions = [r[0] for r in (await conn.execute(text("SELECT action FROM admin.audit_log ORDER BY seq"))).all()]
    assert actions == ["cli.setup_token_issue", "cli.setup_token_issue"]
    assert token.replace("-", "") not in audit_text and "replaced" in audit_text
    assert token not in third.stdout


# ------------------------------------------------------------- fingerprint


async def test_the_fingerprint_is_offline_stable_and_shown_by_verify(server, migrated):
    import re

    offline = run_cli("postgresql://nobody@127.0.0.1:1/none", "master-key-fingerprint")
    assert offline.returncode == 0, offline.stderr
    value = offline.stdout.split()[-1]
    assert re.fullmatch(r"[0-9a-f]{4}(-[0-9a-f]{4}){2}", value)
    assert MASTER_KEY not in offline.stdout
    verify = run_cli(server.url(migrated, "runtime"), "settings-verify")
    assert f"master_key_fingerprint {value}" in verify.stdout
    other = run_cli("postgresql://nobody@127.0.0.1:1/none", "master-key-fingerprint", master=base64.b64encode(bytes(range(1, 49))).decode())
    assert other.stdout.split()[-1] != value


# --------------------------------------------------------------- admin mail

MAIL = {
    "ADMIN_MAIL_SMTP_SERVER": "smtp.example.org",
    "ADMIN_MAIL_SENDER": "admin@example.org",
    "ADMIN_MAIL_USER": "admin@example.org",
    "ADMIN_MAIL_PASSWORD": PLANT,
}


def make_sender(sent: list, fail: bool = False):
    async def send(config, to, subject, body):
        if fail:
            raise ConnectionError(f"cannot reach {config.smtp_server} as {config.user}")
        sent.append((config, to, subject, body))

    return send


def mail_config(candidate):
    from backend.admin.security.mailer import MailConfig

    return MailConfig(
        user=candidate.get("ADMIN_MAIL_USER", ""),
        password=candidate.get("ADMIN_MAIL_PASSWORD", ""),
        smtp_server=candidate.get("ADMIN_MAIL_SMTP_SERVER", ""),
        sender=candidate.get("ADMIN_MAIL_SENDER", ""),
    )


async def test_admin_mail_settings_are_refused_without_a_delivered_test_mail(svc):
    for key, value in (("ADMIN_MAIL_SMTP_SERVER", "smtp.example.org"), ("ADMIN_MAIL_SMTP_PORT", 2525)):
        with pytest.raises(SettingsError) as err:
            await svc.set(key, value, CLI, confirmation=key)
        assert err.value.code == "mail_test_required"
        with pytest.raises(SettingsError) as err:
            await svc.import_once(key, value, CLI)
        assert err.value.code == "mail_test_required"
    assert (await svc.stored()).values == {}
    # other sections are unaffected, and so is the public mail section
    await svc.set("MAIL_SMTP_PORT", 2525, CLI, confirmation="MAIL_SMTP_PORT")


async def test_apply_mail_saves_only_after_the_code_from_the_mail_is_typed(svc):
    sent: list = []
    codes: list = []

    def ask():
        body = sent[-1][3]
        code = body.split("code is ")[1].strip()
        codes.append(code)
        return code + "\n"

    saved = await host.apply_mail(
        svc, MAIL, CLI, test_to="me@example.org", send=make_sender(sent), ask_code=ask, config_factory=mail_config
    )
    assert saved == sorted(MAIL) and len(sent) == 1 and sent[0][1] == "me@example.org"
    assert sent[0][0].smtp_server == "smtp.example.org" and sent[0][0].password == PLANT
    stored = (await svc.stored()).values
    assert stored["ADMIN_MAIL_SMTP_SERVER"] == "smtp.example.org" and stored["ADMIN_MAIL_PASSWORD"] == PLANT
    assert await svc.verify() == []
    # a later change overlays the stored settings: the test mail uses the saved password
    sent.clear()
    await host.apply_mail(
        svc, {"ADMIN_MAIL_SMTP_PORT": "2525"}, CLI, test_to="me@example.org",
        send=make_sender(sent), ask_code=ask, config_factory=mail_config,
    )
    assert sent[0][0].password == PLANT and sent[0][0].smtp_server == "smtp.example.org"


async def test_apply_mail_writes_nothing_on_a_failed_send_or_a_wrong_code(svc):
    sent: list = []
    with pytest.raises(host.HostError) as err:
        await host.apply_mail(
            svc, MAIL, CLI, test_to="me@example.org", send=make_sender(sent, fail=True),
            ask_code=lambda: "000000", config_factory=mail_config,
        )
    assert err.value.code == "test_mail_failed" and "smtp.example.org" not in str(err.value)
    with pytest.raises(host.HostError) as err:
        await host.apply_mail(
            svc, MAIL, CLI, test_to="me@example.org", send=make_sender(sent),
            ask_code=lambda: "not-the-code", config_factory=mail_config,
        )
    assert err.value.code == "code_mismatch"
    assert (await svc.stored()).values == {}


async def test_apply_mail_refuses_other_sections_and_bad_values_before_sending(svc):
    sent: list = []
    for pairs, code in (
        ({T1: "5"}, "not_mail_settings"),
        ({"ADMIN_MAIL_SMTP_PORT": "99999"}, "invalid_value"),
        ({}, "no_keys"),
    ):
        with pytest.raises(host.HostError) as err:
            await host.apply_mail(
                svc, pairs, CLI, test_to="me@example.org", send=make_sender(sent),
                ask_code=lambda: "", config_factory=mail_config,
            )
        assert err.value.code == code
    assert sent == []


async def test_host_set_and_import_cannot_bypass_the_mail_guard_but_clear_and_restore_work(svc, server, migrated, tmp_path):
    url = server.url(migrated, "runtime")
    blocked = run_cli(url, "settings-set", "ADMIN_MAIL_SMTP_SERVER", "--value", "smtp.example.org", "--confirm",
                      "ADMIN_MAIL_SMTP_SERVER", "--yes")
    assert blocked.returncode == 1 and "mail_test_required" in blocked.stderr
    env = tmp_path / "mail.env"
    env.write_text("ADMIN_MAIL_SMTP_SERVER=smtp.example.org\n")
    dry = run_cli(url, "settings-import", "--env-file", str(env), "--dry-run")
    assert dry.returncode == 1 and "refused ADMIN_MAIL_SMTP_SERVER mail_test_required" in dry.stdout
    applied = run_cli(url, "settings-import", "--env-file", str(env))
    assert applied.returncode == 1 and "refused=1" in applied.stdout
    assert (await svc.stored()).values == {}
    sent: list = []
    await host.apply_mail(
        svc, {"ADMIN_MAIL_SMTP_SERVER": "smtp.example.org", "ADMIN_MAIL_SENDER": "a@example.org"}, CLI,
        test_to="me@example.org", send=make_sender(sent),
        ask_code=lambda: sent[-1][3].split("code is ")[1].strip(), config_factory=mail_config,
    )
    await svc.clear("ADMIN_MAIL_SMTP_SERVER", CLI, confirmation="ADMIN_MAIL_SMTP_SERVER")
    await svc.restore("ADMIN_MAIL_SMTP_SERVER", 1, CLI, confirmation="ADMIN_MAIL_SMTP_SERVER")
    assert (await svc.stored()).values["ADMIN_MAIL_SMTP_SERVER"] == "smtp.example.org"


async def test_mail_apply_cli_refuses_when_the_test_mail_cannot_be_sent(svc, server, migrated, tmp_path):
    env = tmp_path / "mail.env"
    env.write_text(
        "ADMIN_MAIL_SMTP_SERVER=smtp.invalid\nADMIN_MAIL_SMTP_PORT=1\nADMIN_MAIL_SENDER=a@example.org\n"
        "ADMIN_MAIL_STARTTLS=false\nADMIN_MAIL_USE_CREDENTIALS=false\n"
        f"ADMIN_MAIL_PASSWORD={PLANT}\n"
    )
    result = run_cli(server.url(migrated, "runtime"), "settings-mail-apply", "--env-file", str(env), "--test-to", "me@example.org")
    assert result.returncode == 1 and "test_mail_failed" in result.stderr
    assert PLANT not in result.stdout + result.stderr
    assert (await svc.stored()).values == {}


async def test_no_host_command_leaves_a_secret_in_the_audit_log_or_the_outbox(svc, tmp_path):
    await host.bootstrap_keys(svc, CLI, environ={}, existing_stack=False, counts=empty_counts)
    await svc.set(SECRET, PLANT, CLI, confirmation=SECRET)
    await host.export_env(svc, [SECRET, T4], str(tmp_path / "x.env"), CLI)
    await host.export_worker(svc, str(tmp_path / "w.env"), CLI)
    env = tmp_path / "e.env"
    env.write_text(f"{SECRET}={PLANT}\n")
    await host.prune_env_files(svc, [str(env)], apply=True, actor=CLI)
    async with svc._engine.connect() as conn:
        dump = " ".join(
            r[0]
            for r in (
                await conn.execute(
                    text(
                        "SELECT coalesce(before::text, '') || coalesce(after::text, '') || coalesce(detail::text, '') "
                        "FROM admin.audit_log UNION ALL SELECT payload::text FROM admin.notifications"
                    )
                )
            ).all()
        )
    secrets_ = [PLANT, *[v for k, v in (await svc.stored()).values.items() if k in host.GENERATED_KEYS]]
    assert len(secrets_) == 6
    for value in secrets_:
        assert value not in dump
