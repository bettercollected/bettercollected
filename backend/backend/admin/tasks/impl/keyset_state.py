"""What the ``keyset.*`` tasks share besides the rotation walk: the keyset in
the settings store (read, and written through the one narrow function the
runner may call), the heartbeat readiness check, and the data stores.

The keyset (``MASTER_ENCRYPTION_KEYSET``) is a T4 setting: the portal's writer
refuses it. The runner has no write privilege on ``settings.*``; it computes
the new sealed, signed row itself (section ``auth_keys`` only) and hands it to
``settings.task_write_keyset`` (migration 0009), which writes it only for this
key, one version up, under the writer lock, with the audit row for the write
already in the same transaction. See the migration for the exact conditions.

Nothing here prints, logs or returns the keyset except to its caller in memory.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence

from sqlalchemy import text

from backend.admin.config import parse_master_key
from backend.admin.tasks.catalog.keyset import Targets
from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.impl import keyset_core as core
from backend.admin.tasks.impl.responses_common import plan_task_stores
from backend.admin.tasks.spec import Refusal
from common.services.keyset import (
    KEYSET_ENV,
    KeysetError,
    parse_keyset,
)
from common.settings.canonical import SettingRow, canonical_manifest
from common.settings.keys import SectionKeys
from common.settings.loader import keyset_fingerprint
from common.settings.signing import Manifest, sign_manifest

KEY = KEYSET_ENV
SECTION = "auth_keys"
# a heartbeat newer than this is fresh; one between this and RETIRED_AFTER is a
# service that may still be running and has stopped reporting (refuse); older
# than that its container is gone (the store prunes such rows after 7 days)
FRESH_SECONDS = 120
RETIRED_AFTER_SECONDS = 15 * 60
AUDIT_ACTION = "settings.task_set"


# ---------------------------------------------------------------- the keys
def runner_keys() -> SectionKeys:
    """The runner's view of the settings keys: its ONE section (the keyset's),
    so it can neither seal nor open any other setting."""
    master = parse_master_key(os.environ.get("SETTINGS_MASTER_KEY"))
    previous = None
    raw = (os.environ.get("SETTINGS_MASTER_KEY_PREVIOUS") or "").strip()
    if raw:
        previous = parse_master_key(raw)
    return SectionKeys(master, sections={SECTION}, master_previous=previous)


# -------------------------------------------------------------- the store
@dataclass(frozen=True)
class StoredKeyset:
    value: str  # the secret: never leaves this process
    version: int
    revision: int
    manifest_entries: Mapping[str, Any]

    def __repr__(self) -> str:
        return f"StoredKeyset(version={self.version}, revision={self.revision})"


async def read_stored(conn, keys: SectionKeys) -> Optional[StoredKeyset]:
    """The keyset from the settings store, verified: row signature, signed
    manifest (including that it names this exact row), then opened. ``None``
    when the runner's view has no such row. Refuses (``keyset_unverified``)
    anything that does not verify."""
    row = (
        await conn.execute(
            text(
                "SELECT key, section, readers, is_secret, reload_class, blob, version, "
                "updated_at, sig FROM settings.v_tasks WHERE key = :k"
            ),
            {"k": KEY},
        )
    ).first()
    if row is None:
        # A row the runner's view hides is still named in the (unfiltered)
        # signed manifest: it was written before the runner became a reader of
        # the keyset. Only the admin service can re-sign it with the runner in
        # its readers (docs/response-keyset-rotation.md); say so, not "absent".
        listed = (
            await conn.execute(text("SELECT entries::text FROM settings.v_tasks_manifest"))
        ).scalar()
        if listed is not None and KEY in json.loads(listed):
            raise Refusal("keyset_not_readable_by_runner")
        return None
    m = row._mapping
    manifest_row = (
        await conn.execute(
            text("SELECT revision, entries::text AS entries, sig FROM settings.v_tasks_manifest")
        )
    ).first()
    if manifest_row is None:
        raise Refusal("keyset_unverified")
    entries = json.loads(manifest_row._mapping["entries"])
    setting = SettingRow(
        key=m["key"],
        section=m["section"],
        readers=tuple(m["readers"]),
        is_secret=m["is_secret"],
        reload_class=m["reload_class"],
        version=m["version"],
        updated_at=m["updated_at"],
        value=None,
        blob=m["blob"],
        sig=m["sig"],
    )
    try:
        manifest = Manifest(
            int(manifest_row._mapping["revision"]), entries, manifest_row._mapping["sig"]
        )
        listed = manifest.entries.get(KEY)
        ok = (
            keys.verify_row(setting)
            and keys.verify_manifest(manifest)
            and listed is not None
            and listed == (setting.version, setting.sig, tuple(setting.readers))
            and setting.section == SECTION
            and setting.is_secret
            and setting.blob is not None
        )
        if not ok:
            raise Refusal("keyset_unverified")
        value = keys.open(SECTION, KEY, setting.version, setting.blob)
    except Refusal:
        raise
    except Exception:  # noqa: BLE001 - never carry a cause that could quote a value
        raise Refusal("keyset_unverified") from None
    return StoredKeyset(value, setting.version, manifest.revision, entries)


async def write_stored(
    conn,
    keys: SectionKeys,
    current: StoredKeyset,
    new_value: str,
    *,
    requested_by: str,
    run_id: str,
    task: str,
    action: str,
    extra: Optional[Mapping[str, Any]] = None,
) -> tuple[int, int]:
    """Write ``new_value`` as the next version of the keyset, in the caller's
    transaction: the audit row is built first (hashed with the audit key) and
    handed to ``settings.task_write_keyset``, which checks the run and writes the
    row itself. Returns (version, revision).
    Raises ``Refusal('stale_version')`` when the store moved since ``current``
    was read."""
    from sqlalchemy.exc import DBAPIError

    from backend.admin.services import audit
    from backend.admin.services.settings_store import store_registry, value_digest

    spec = store_registry().get(KEY)
    readers = tuple(sorted(spec.readers))
    version, revision = current.version + 1, current.revision + 1
    now = (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()
    blob = keys.seal(SECTION, KEY, version, new_value)
    signed = keys.sign_row(
        SettingRow(KEY, SECTION, readers, True, spec.reload_class.value, version, now, None, blob, "")
    )
    entries = {k: (v[0], v[1], tuple(v[2])) for k, v in current.manifest_entries.items()}
    entries[KEY] = (version, signed.sig, readers)
    manifest = sign_manifest(revision, entries, keys.signing_key())
    digest = hashlib.sha256(canonical_manifest(revision, entries)).hexdigest()

    detail = {
        "revision": revision,
        "tier": spec.tier.value,
        "run_id": run_id,
        "task": task,
        "requested_by": requested_by,
        **(dict(extra) if extra else {}),
    }
    # the audit row for this write is built and hashed here (with the audit key, which
    # the database never has) and appended by the function itself, after it has
    # checked the run: the runner's role cannot insert into the log
    row = await audit.prepare_runner_row(
        conn,
        AUDIT_ACTION,
        "setting",
        KEY,
        {**audit.setting_payload(KEY, "x", secret=True), "version": current.version},
        {
            **audit.setting_payload(KEY, "x", secret=True),
            "version": version,
            "digest": value_digest(keys, spec, KEY, version, new_value),
        },
        "success",
        detail=detail,
        request_id=run_id,
    )
    try:
        await conn.execute(
            text(
                "SELECT settings.task_write_keyset(:key, :ev, :er, :section, "
                "CAST(:readers AS text[]), :blob, :by, :at, :sig, :actor, :digest, "
                "CAST(CAST(:entries AS text) AS jsonb), :msig, :action, :run, CAST(CAST(:extra AS text) AS jsonb), "
                ":aid, :aat, :aprev, :ahash, :akv, CAST(CAST(:abefore AS text) AS jsonb), "
                "CAST(CAST(:aafter AS text) AS jsonb), CAST(CAST(:adetail AS text) AS jsonb))"
            ),
            {
                "key": KEY,
                "ev": current.version,
                "er": current.revision,
                "section": SECTION,
                "readers": list(readers),
                "blob": blob,
                "by": f"task:{task}"[:320],
                "at": now,
                "sig": signed.sig,
                "actor": requested_by[:320] or "task",
                "digest": digest,
                "entries": json.dumps(manifest.to_json()["entries"], allow_nan=False),
                "msig": manifest.sig,
                "action": action,
                "run": run_id,
                "extra": json.dumps(
                    {k: v for k, v in (extra or {}).items() if isinstance(v, int)},
                    allow_nan=False,
                ),
                "aid": row["id"],
                "aat": row["at"],
                "aprev": row["prev_hash"],
                "ahash": row["row_hash"],
                "akv": row["key_version"],
                "abefore": json.dumps(row["before"], allow_nan=False),
                "aafter": json.dumps(row["after"], allow_nan=False),
                "adetail": json.dumps(row["detail"], allow_nan=False),
            },
        )
    except DBAPIError as error:
        orig = getattr(error, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        if sqlstate == "40001":  # serialization_failure: stale version or revision
            raise Refusal("stale_version") from None
        raise
    return version, revision


# -------------------------------------------------------------- consumers
@dataclass(frozen=True)
class Consumer:
    service: str
    instance: str
    age_seconds: float
    revision_applied: int
    restart_pending: bool
    keyset_fp: str
    env_overrides: tuple
    write_stores: str = ""  # "" when the service did not say (before admin 0018)


async def consumers(conn, services: Sequence[str]) -> List[Consumer]:
    rows = await conn.execute(
        text(
            "SELECT service, instance, extract(epoch FROM (now() - reported_at)) AS age, "
            "revision_applied, restart_pending, keyset_fp, env_overrides, write_stores "
            "FROM settings.service_state WHERE service = ANY(CAST(:s AS text[])) "
            "ORDER BY service, instance"
        ),
        {"s": list(services)},
    )
    return [
        Consumer(
            r.service,
            r.instance,
            float(r.age),
            int(r.revision_applied),
            bool(r.restart_pending),
            r.keyset_fp,
            tuple(r.env_overrides or ()),
            r.write_stores or "",
        )
        for r in rows
    ]


async def check_consumers_off_mongo(conn) -> None:
    """For ``drop_old`` with ``mongo_retired``: every live keyset consumer (the
    backend and the Google integration, any instance seen within the retirement
    window) reports that it writes Postgres alone. Refuses
    ``consumer_writes_mongo`` when one still writes Mongo and
    ``consumer_write_stores_unknown`` when one does not say (a build from
    before the report existed): the runner's own write mode is not enough."""
    live = [
        c for c in await consumers(conn, ["backend", "google"])
        if c.age_seconds <= RETIRED_AFTER_SECONDS
    ]
    if any("mongo" in c.write_stores.split(",") for c in live):
        raise Refusal("consumer_writes_mongo")
    if any(c.write_stores != "postgres" for c in live):
        raise Refusal("consumer_write_stores_unknown")


def required_services(google_in_use: bool) -> List[str]:
    return ["backend", "google"] if google_in_use else ["backend"]


async def check_consumers(
    conn, *, ids: Sequence[int], min_revision: int, google_in_use: bool
) -> int:
    """Every keyset consumer reports (a heartbeat newer than 2 minutes, on every
    instance seen in the last 15 minutes), holds a keyset with exactly ``ids``
    (the heartbeat's ``keyset_fp``), has restarted onto the current settings
    revision and is not overriding the keyset from its environment. Raises a
    ``Refusal`` naming the first failure; returns the number of instances.

    The fingerprint is the hash of the key ids (not of which one is primary), so
    after a promote it is the settings revision and ``restart_pending`` that
    show a service runs the promoted keyset."""
    # the value a service's heartbeat carries: the loader's own function
    # a google instance that reports is checked whatever `google_in_use` says
    expected = keyset_fingerprint(ids)
    found = await consumers(conn, ["backend", "google"])
    live = [c for c in found if c.age_seconds <= RETIRED_AFTER_SECONDS]
    for service in required_services(google_in_use):
        mine = [c for c in live if c.service == service]
        if not mine:
            raise Refusal("consumer_not_reporting")
        if not any(c.age_seconds <= FRESH_SECONDS for c in mine):
            raise Refusal("consumer_stale")
    if any(c.age_seconds > FRESH_SECONDS for c in live):
        raise Refusal("consumer_stale")
    if any(KEY in c.env_overrides for c in live):
        raise Refusal("consumer_env_override")
    if any(c.restart_pending for c in live):
        raise Refusal("consumer_restart_pending")
    if any(c.keyset_fp != expected for c in live):
        raise Refusal("consumer_missing_key")
    if any(c.revision_applied < min_revision for c in live):
        raise Refusal("consumer_behind")
    return len(live)


# ------------------------------------------------------------ data stores
def _clean(env: Mapping[str, str]) -> dict:
    return {k: v for k, v in env.items() if v and v.strip()}


@dataclass(frozen=True)
class DataConfig:
    """The Postgres URLs of the targets (one role per owning schema). Postgres
    is the only store since 4.1; a runner that still has a Mongo URI never
    connects to it (:attr:`mongo_configured` only lets a task refuse)."""

    # connection strings carry passwords: never in a repr or a log
    database_url: Optional[str] = field(repr=False)
    google_database_url: Optional[str] = field(repr=False)
    mongo_configured: bool = False

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "DataConfig":
        env = _clean(os.environ if env is None else env)
        return cls(
            database_url=env.get("DATABASE_URL"),
            google_database_url=env.get("GOOGLE_DATABASE_URL"),
            mongo_configured=bool(env.get("MONGO_URI")),
        )

    def url_for(self, target: core.Target) -> Optional[str]:
        """The Postgres URL of a target: one role per owning schema."""
        return self.google_database_url if target is core.GOOGLE_CREDENTIALS else self.database_url

    def configured(self, target: core.Target) -> List[str]:
        return ["postgres"] if self.url_for(target) else []

    def stores_for(self, target: core.Target, choice: StoreChoice) -> List[str]:
        """Store names (``plan_task_stores``): Postgres, which must be configured
        for the target (``store_not_configured``); ``mongo`` and ``both`` refuse
        ``store_retired``."""
        return plan_task_stores(choice, self.configured(target))

    def drop_old_stores(self, target: core.Target) -> List[str]:
        """The stores ``drop_old`` scans: Postgres, which must be configured
        (``store_not_configured``). Mongo is never scanned: the operator signs
        ``mongo_retired`` instead (``store_retired`` without it)."""
        return self.stores_for(target, StoreChoice.postgres)


def selected_targets(chosen: Sequence[Targets]) -> List[core.Target]:
    wanted = set(chosen) or set(Targets)
    return [
        core.TARGETS[name]
        for name in ("responses", "google-credentials")
        if Targets(name.replace("-", "_")) in wanted
    ]


def field_name(target: core.Target) -> str:
    return target.name.replace("-", "_")


@asynccontextmanager
async def open_target_stores(
    config: DataConfig, target: core.Target, names: Sequence[str], *, read_only: bool
):
    closers: list = []
    stores: list = []
    try:
        for name in names:
            if name != "postgres":  # a plan never names another; never connect
                raise Refusal("store_retired")
            from sqlalchemy.ext.asyncio import create_async_engine

            settings = {"statement_timeout": "60000"}
            if read_only:
                settings["default_transaction_read_only"] = "on"
            engine = create_async_engine(
                config.url_for(target),
                pool_size=2,
                max_overflow=0,
                connect_args={"server_settings": settings},
            )
            closers.append(engine.dispose)
            stores.append(core.PostgresStore(engine, target))
        yield stores
    finally:
        for close in reversed(closers):
            try:
                await close()
            except Exception:  # noqa: BLE001
                pass


async def check_import_finished(store, mongo_configured: bool) -> None:
    """Refuses ``import_incomplete`` unless the 4.0 import into this store is
    over, so that no later backfill or reconcile can bring in a value on a key
    that was dropped (or a row that was purged):

    * the runner has a Mongo connection configured (``MONGO_URI``): the import
      tooling may still run against it;
    * ``<schema>.migration_progress`` records a collection of the target not
      ``done``, or finished with documents skipped;
    * the role may not read ``migration_progress`` (``import_state_unreadable``:
      re-run the roles script, which grants it): it fails closed.
    A collection with no row at all (a stack that never had Mongo, or whose
    import never started) cannot be told apart from "never imported": the
    operator confirms the 4.0 import ran, or that the stack never had Mongo,
    before the purge or the key drop. A clean verify marker is not used: it states that a verify was clean once,
    not that nothing will be copied later, and the runner's role cannot read it."""
    if mongo_configured:
        raise Refusal("import_incomplete")
    for _collection, progress_state, skipped in await store.import_progress():
        if progress_state != "done" or skipped:
            raise Refusal("import_incomplete")


async def ping(store) -> None:
    async with store.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


def parsed(value: str):
    try:
        return parse_keyset(value)
    except KeysetError:
        raise Refusal("keyset_unreadable") from None


def event_counts(counts: Mapping[str, int], keep: int = 10) -> dict:
    """Counters for an event (at most 16 of them). A per-key counter
    ``values_key_<id>`` is recorded as ``kid_<id>``: the event sanitiser blanks
    any name containing "key". Counters beyond ``keep`` keys are summed into
    ``kid_other``."""
    out: dict = {}
    other = 0
    keyed = 0
    for name, number in sorted(counts.items()):
        if name.startswith("values_key_"):
            keyed += 1
            if keyed > keep:
                other += number
                continue
            out["kid_" + name[len("values_key_"):]] = int(number)
            continue
        out[name] = int(number)
    if other:
        out["kid_other"] = other
    return out


def event_target(name: str) -> str:
    """The id a target goes by in an event ("credential" would be blanked)."""
    return {"google_credentials": "google_oauth"}.get(name, name)
