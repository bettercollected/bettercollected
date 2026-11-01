"""``python -m backend.admin settings-grant-runner``: the host command that lets the
task runner read the auth key rings stored before it was a reader of them
(docs/auth-key-rotation.md). Dry run by default; prints ``ok`` / ``would_grant`` /
``granted`` and never a value."""

from __future__ import annotations

import secrets
from dataclasses import replace

from cryptography.fernet import Fernet
from sqlalchemy import text

from backend.admin.repositories import settings as repo
from backend.admin.services.settings_store import Actor
from tests.admin.conftest import needs_postgres
from tests.admin.test_settings_store import run_cli, superuser, svc  # noqa: F401 - fixtures

pytestmark = needs_postgres

JWT = secrets.token_hex(32)
AES = Fernet.generate_key().decode()


async def legacy_row(service, key: str, value: str) -> None:
    """The row as an earlier release wrote it: no ``tasks`` among the readers."""
    spec = service.registry.get(key)
    legacy = replace(spec, readers=tuple(r for r in spec.readers if r != "tasks"))
    async with service._engine.begin() as conn:
        revision = await repo.lock(conn)
        await service._write(conn, legacy, None, value, Actor("cli"), "import", revision)


async def versions(superuser):
    async with superuser.connect() as conn:
        rows = await conn.execute(
            text("SELECT key, version, readers FROM settings.entries "
                 "WHERE key IN ('AUTH_JWT_SECRET', 'AUTH_AES_HEX_KEY') ORDER BY key")
        )
        return {r.key: (r.version, "tasks" in r.readers) for r in rows}


async def test_dry_run_apply_and_idempotence(server, migrated, svc, superuser):  # noqa: F811
    url = server.url(migrated, "runtime")
    await legacy_row(svc, "AUTH_JWT_SECRET", JWT)
    await legacy_row(svc, "AUTH_AES_HEX_KEY", AES)
    assert await versions(superuser) == {
        "AUTH_AES_HEX_KEY": (1, False), "AUTH_JWT_SECRET": (1, False),
    }

    dry = run_cli(url, "settings-grant-runner")
    assert dry.returncode == 0, dry.stderr
    assert "would_grant AUTH_JWT_SECRET" in dry.stdout and "would_grant AUTH_AES_HEX_KEY" in dry.stdout
    assert "nothing written" in dry.stdout
    assert await versions(superuser) == {
        "AUTH_AES_HEX_KEY": (1, False), "AUTH_JWT_SECRET": (1, False),
    }

    one = run_cli(url, "settings-grant-runner", "AUTH_JWT_SECRET", "--apply")
    assert one.returncode == 0, one.stderr
    assert "granted AUTH_JWT_SECRET version=2" in one.stdout
    assert await versions(superuser) == {
        "AUTH_AES_HEX_KEY": (1, False), "AUTH_JWT_SECRET": (2, True),
    }

    both = run_cli(url, "settings-grant-runner", "--apply")
    assert both.returncode == 0, both.stderr
    assert "ok AUTH_JWT_SECRET" in both.stdout and "granted AUTH_AES_HEX_KEY version=2" in both.stdout
    again = run_cli(url, "settings-grant-runner", "--apply")
    assert again.stdout.count("ok ") == 2 and "granted" not in again.stdout
    # the value is unchanged, the rows verify, and nothing printed carries a key
    assert await svc.verify() == []
    stored = await svc.stored()
    assert stored.values["AUTH_JWT_SECRET"] == JWT and stored.values["AUTH_AES_HEX_KEY"] == AES
    for output in (dry, one, both, again):
        assert JWT not in output.stdout + output.stderr and AES not in output.stdout + output.stderr
    async with superuser.connect() as conn:
        audited = (
            await conn.execute(
                text("SELECT actor_kind FROM admin.audit_log WHERE action = 'settings.grant_readers'")
            )
        ).scalars().all()
    assert audited == ["cli", "cli"]


async def test_only_the_two_rings_may_be_granted(server, migrated):
    url = server.url(migrated, "runtime")
    refused = run_cli(url, "settings-grant-runner", "API_ALLOWED_WORKSPACES")
    assert refused.returncode == 2 and "only the auth key rings" in refused.stderr
    absent = run_cli(url, "settings-grant-runner", "--apply")  # nothing stored in this database
    assert absent.returncode != 0 and "not_set" in absent.stderr
