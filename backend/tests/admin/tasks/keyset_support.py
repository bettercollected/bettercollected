"""Helpers for the keyset tests: a generated keyset, the keyset imported into
the settings store (as the admin importer does), and service heartbeats."""

from __future__ import annotations

import base64
import io

import tink
from sqlalchemy import text
from tink import aead, cleartext_keyset_handle

from backend.admin.services.settings_store import Actor, SettingsService, store_registry
from common.services.keyset import KEYSET_ENV, parse_keyset
from common.settings.keys import SectionKeys
from common.settings.loader import keyset_fingerprint
from tests.admin.conftest import MASTER_KEY

KEY = KEYSET_ENV


def generated_keyset() -> str:
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    buffer = io.StringIO()
    cleartext_keyset_handle.write(tink.JsonKeysetWriter(buffer), handle)
    return base64.b64encode(buffer.getvalue().encode()).decode()


def admin_keys() -> SectionKeys:
    return SectionKeys(MASTER_KEY, sections={s.section for s in store_registry()})


def settings_service(engine) -> SettingsService:
    return SettingsService(engine, store_registry(), admin_keys())


async def import_keyset(engine, value: str):
    """The first write of the keyset (an import), as the admin CLI does it."""
    change = await settings_service(engine).import_once(KEY, value, Actor("cli"))
    assert change is not None
    return change


async def heartbeat(
    owner,
    service: str,
    keyset_value: str,
    *,
    instance: str = "i1",
    revision: int = 0,
    restart_pending: bool = False,
    env: tuple = (),
    age_seconds: float = 0,
    fp: str | None = None,
    write_stores: str | None = None,
) -> None:
    """A row in settings.service_state as a service's ``report_state`` leaves it.
    ``write_stores`` defaults to what a service with this process's
    ``DB_WRITE_MODE*`` reports."""
    import os

    from common.settings.write_stores import write_stores_report

    if write_stores is None:
        write_stores = write_stores_report(os.environ)
    ids = [k.key_id for k in parse_keyset(keyset_value).key]
    async with owner.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, reported_at, "
                "revision_applied, env_overrides, restart_pending, keyset_fp, write_stores) "
                "VALUES (:s, :i, now() - make_interval(secs => :age), :r, "
                "CAST(:e AS text[]), :p, :fp, :w) "
                "ON CONFLICT (service, instance) DO UPDATE SET reported_at = excluded.reported_at, "
                "revision_applied = excluded.revision_applied, env_overrides = excluded.env_overrides, "
                "restart_pending = excluded.restart_pending, keyset_fp = excluded.keyset_fp, "
                "write_stores = excluded.write_stores"
            ),
            {
                "s": service,
                "i": instance,
                "age": age_seconds,
                "r": revision,
                "e": list(env),
                "p": restart_pending,
                "fp": fp if fp is not None else keyset_fingerprint(ids),
                "w": write_stores,
            },
        )
