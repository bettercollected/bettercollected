"""Host-side operations on the settings store (the operator CLI's engine room).

Everything here runs with the host's authority: the master key and the admin
database role. It prints nothing itself and returns names, counts and short
reason codes only; the one thing that ever holds a secret value is a variable
in memory, or a file the operator asked for (``export_env``, ``export_worker``),
created private (mode 600), never over an existing file.

* ``plan_import`` / ``import_config``: read compose config (or an env file),
  decide per setting what would be imported, and import what is clear.
* ``plan_drift``: compare the same sources with the store, by value, in memory.
* ``prune_env_files``: remove from env files the settings the store already
  holds with the same value (an env value wins over the store in 4.0, so a
  stale one is dangerous).
* ``bootstrap_keys``: generate the stack's own keys straight into the store.
* ``export_env`` / ``export_worker``: the break-glass and worker-key exports.
* ``apply_mail``: save the admin sign-in mail settings once a test mail was
  delivered and its code confirmed.
* ``set_value`` / ``restore_version``: the host's own settings-set/restore.

Every mutation is audited (actor kind ``cli``) in the transaction that makes it.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import stat
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from cryptography.fernet import Fernet
from dotenv.parser import parse_stream

from backend.admin.services import audit
from backend.admin.services.settings_store import (
    Actor,
    SettingsError,
    SettingsService,
    StoredSettings,
)
from common.settings.canonical import canonical_json
from common.settings.inventory import ALIASES
from common.settings.registry import (
    Tier,
    ValidationError,
    ValueType,
    coerce_value,
    is_env_only,
    normalize_value,
)

MAX_CONFIG_BYTES = 8 * 1024 * 1024

# Compose service name -> the registry reader whose settings it reads. The jobs
# worker and the task runner use the backend's settings; umami, polis and the
# databases are outside the store.
COMPOSE_READERS = {
    "backend": "backend",
    "jobs-worker": "backend",
    "auth": "auth",
    "integrations-googleform": "google",
    "admin": "admin",
    "worker": "temporal_worker",
    "actions-executor": "actions_executor",
    "webapp": "webapp",
}
# The workers keep their own copies of two stored keys under other names and
# never hold the master key (the drift check compares them with the store).
WORKER_SERVICES = frozenset({"worker", "actions-executor"})
WORKER_COPIES = {"API_KEY": "TEMPORAL_API_KEY", "AES_HEX_KEY": "AUTH_AES_HEX_KEY"}

GENERATED_KEYS = (
    "AUTH_JWT_SECRET",
    "AUTH_AES_HEX_KEY",
    "AUTH_INTERNAL_NOTIFY_KEY",
    "TEMPORAL_API_KEY",
    "MASTER_ENCRYPTION_KEYSET",
)
ENV_SOURCE = "env-file"  # the pseudo service of an env file: reads every key


class HostError(Exception):
    """A refusal of a host command: a stable code and a short fixed hint."""

    def __init__(self, code: str, hint: str = ""):
        self.code = code
        self.hint = hint
        super().__init__(f"{code}" + (f" ({hint})" if hint else ""))


# ----------------------------------------------------------------- sources


def parse_compose_config(raw: str) -> dict[str, dict[str, str]]:
    """``docker compose config --format json`` as ``{service: {NAME: value}}``
    for the services that read settings. Values that are null are left out."""
    if len(raw.encode("utf-8", "ignore")) > MAX_CONFIG_BYTES:
        raise HostError("config_too_large")
    try:
        document = json.loads(raw)
    except ValueError:
        raise HostError("config_not_json", "expected `docker compose config --format json`") from None
    services = document.get("services") if isinstance(document, dict) else None
    if not isinstance(services, dict):
        raise HostError("config_no_services")
    out: dict[str, dict[str, str]] = {}
    for name, body in services.items():
        if name not in COMPOSE_READERS or not isinstance(body, dict):
            continue
        env = body.get("environment") or {}
        if isinstance(env, list):  # NAME=value items (not what compose prints, but valid)
            env = dict(item.split("=", 1) for item in env if isinstance(item, str) and "=" in item)
        if not isinstance(env, dict):
            continue
        out[name] = {
            str(k): str(v) for k, v in env.items() if v is not None and not isinstance(v, (dict, list))
        }
    return out


def parse_env_text(raw: str) -> dict[str, str]:
    """``NAME=value`` pairs of env-file text, without interpolation."""
    import io

    pairs: dict[str, str] = {}
    for binding in parse_stream(io.StringIO(raw)):
        if binding.key is not None and binding.value is not None and not binding.error:
            pairs[binding.key] = binding.value
    return pairs


def _reader_of(source: str) -> Optional[str]:
    return COMPOSE_READERS.get(source)


@dataclass
class _Candidates:
    """The non-empty values one canonical key has across the sources."""

    values: list = field(default_factory=list)  # (source, normalised raw)


def _candidates(
    service: SettingsService, sources: Mapping[str, Mapping[str, str]], *, worker_copies: bool
) -> tuple[dict[str, _Candidates], set[str], set[str], set[str]]:
    """Group the sources' names by registry key.

    Returns ``(by_key, unknown, env_only, empty)``; ``empty`` holds keys whose
    every occurrence is empty (``${NAME:-}`` that nobody set)."""
    registry = service.registry
    by_key: dict[str, _Candidates] = {}
    unknown: set[str] = set()
    env_only: set[str] = set()
    seen_non_empty: set[str] = set()
    seen_any: set[str] = set()
    for source in sorted(sources):
        reader = ENV_SOURCE if source == ENV_SOURCE else _reader_of(source)
        for name in sorted(sources[source]):
            raw = normalize_value(sources[source][name])
            if worker_copies and source in WORKER_SERVICES and name in WORKER_COPIES:
                key = WORKER_COPIES[name]
                seen_any.add(key)
                if raw:
                    seen_non_empty.add(key)
                    by_key.setdefault(key, _Candidates()).values.append((source, raw))
                continue
            key = ALIASES.get(name, name)
            if key not in registry:
                (env_only if is_env_only(key) else unknown).add(name)
                continue
            spec = registry.get(key)
            if reader != ENV_SOURCE and reader not in spec.readers:
                unknown.add(name)
                continue
            seen_any.add(key)
            if raw:
                seen_non_empty.add(key)
                by_key.setdefault(key, _Candidates()).values.append((source, raw))
    return by_key, unknown, env_only, seen_any - seen_non_empty


def _key_ids(value: str) -> Optional[set]:
    try:
        from common.services import keyset as keyset_module

        return {k.key_id for k in keyset_module.parse_keyset(value).key}
    except Exception:  # noqa: BLE001
        return None


def _same(service: SettingsService, key: str, raw: str, stored: Any) -> bool:
    """Whether the env text ``raw`` means the stored value. For the response
    keyset the stored one must hold every key id of the environment's (a
    superset is fine: a rotation adds keys); ids are compared, never values."""
    if key == "MASTER_ENCRYPTION_KEYSET":
        env_ids, stored_ids = _key_ids(raw), _key_ids(stored) if isinstance(stored, str) else None
        return env_ids is not None and stored_ids is not None and env_ids <= stored_ids
    spec = service.registry.get(key)
    if spec.is_secret:
        return isinstance(stored, str) and secrets.compare_digest(
            normalize_value(raw).encode(), stored.encode()
        )
    try:
        return canonical_json(coerce_value(spec, raw)) == canonical_json(stored)
    except ValidationError:
        return False


def _distinct(service: SettingsService, key: str, values: Sequence[tuple[str, str]]) -> list[list]:
    """The values grouped by meaning: ``[[source, ...], ...]``."""
    spec = service.registry.get(key)
    groups: list[tuple[Any, list]] = []
    for source, raw in values:
        try:
            meaning: Any = raw if spec.is_secret else canonical_json(coerce_value(spec, raw))
        except ValidationError:
            meaning = raw
        for existing, members in groups:
            if existing == meaning:
                members.append(source)
                break
        else:
            groups.append((meaning, [source]))
    return [members for _, members in groups]


# ------------------------------------------------------------------ import


@dataclass
class ImportPlan:
    would_import: dict = field(default_factory=dict)  # key -> raw (in memory only)
    already_in_store: list = field(default_factory=list)
    empty: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    env_only: list = field(default_factory=list)
    conflict: dict = field(default_factory=dict)  # key -> [sources]
    refused: list = field(default_factory=list)  # (key, reason)

    def counts(self) -> dict:
        return {
            "would_import": len(self.would_import),
            "already_in_store": len(self.already_in_store),
            "empty": len(self.empty),
            "unknown": len(self.unknown),
            "env_only": len(self.env_only),
            "conflict": len(self.conflict),
            "refused": len(self.refused),
        }

    def __repr__(self) -> str:  # would_import holds values
        return f"ImportPlan({self.counts()})"


async def plan_import(
    service: SettingsService,
    sources: Mapping[str, Mapping[str, str]],
    *,
    prefer: Optional[str] = None,
) -> ImportPlan:
    """What an import would do. ``prefer`` names a compose service (or reader)
    whose value settles a conflict for the keys it sets."""
    stored = await service.stored()
    in_store = set(stored.values) | set(stored.tombstones) | set(stored.unverified)
    by_key, unknown, env_only, empty_keys = _candidates(service, sources, worker_copies=False)
    plan = ImportPlan(unknown=sorted(unknown), env_only=sorted(env_only))
    plan.empty = sorted(k for k in empty_keys if k not in by_key)
    for key in sorted(by_key):
        if key in in_store:
            plan.already_in_store.append(key)
            continue
        groups = _distinct(service, key, by_key[key].values)
        raw = by_key[key].values[0][1]
        if len(groups) > 1:
            chosen = None
            if prefer:
                for source, value in by_key[key].values:
                    if prefer in (source, _reader_of(source)):
                        chosen = value
                        break
            if chosen is None:
                plan.conflict[key] = sorted({s for g in groups for s in g})
                continue
            raw = chosen
        try:
            service.registry.validate(key, raw)
        except ValidationError as exc:
            plan.refused.append((key, exc.reason))
            continue
        spec = service.registry.get(key)
        if spec.tier is Tier.T5:
            plan.refused.append((key, "env_only"))
            continue
        if spec.section == MAIL_SECTION:  # only a delivered test mail may save these
            plan.refused.append((key, "mail_test_required"))
            continue
        plan.would_import[key] = raw
    return plan


@dataclass
class ImportResult:
    imported: list = field(default_factory=list)
    existing: list = field(default_factory=list)
    refused: list = field(default_factory=list)


async def import_config(service: SettingsService, plan: ImportPlan, actor: Actor) -> ImportResult:
    """Import what the plan would, each key through ``import_once`` (never an
    overwrite, one audited transaction per key)."""
    result = ImportResult()
    for key in sorted(plan.would_import):
        try:
            change = await service.import_once(key, plan.would_import[key], actor)
        except SettingsError as exc:
            result.refused.append((key, exc.detail or exc.code))
            continue
        (result.imported if change is not None and change.changed else result.existing).append(key)
    return result


# ------------------------------------------------------------------- drift


@dataclass
class DriftReport:
    equal: list = field(default_factory=list)
    differs: dict = field(default_factory=dict)  # key -> [sources]
    env_only: list = field(default_factory=list)
    store_only: list = field(default_factory=list)
    unverified: list = field(default_factory=list)

    def counts(self) -> dict:
        return {
            "equal": len(self.equal),
            "differs": len(self.differs),
            "env_only": len(self.env_only),
            "store_only": len(self.store_only),
            "unverified": len(self.unverified),
        }

    @property
    def clean(self) -> bool:
        return not self.differs and not self.unverified


def _drift(
    service: SettingsService,
    stored: StoredSettings,
    sources: Mapping[str, Mapping[str, str]],
) -> tuple[DriftReport, dict[str, list]]:
    by_key, _, _, _ = _candidates(service, sources, worker_copies=True)
    report = DriftReport(unverified=list(stored.unverified))
    for key in sorted(set(by_key) | set(stored.values)):
        if key not in stored.values:
            if key not in stored.tombstones and key not in stored.unverified:
                report.env_only.append(key)
            elif key in stored.tombstones and key in by_key:
                report.env_only.append(key)
            continue
        if key not in by_key:
            report.store_only.append(key)
            continue
        bad = sorted({s for s, raw in by_key[key].values if not _same(service, key, raw, stored.values[key])})
        if bad:
            report.differs[key] = bad
        else:
            report.equal.append(key)
    return report, {k: v.values for k, v in by_key.items()}


async def plan_drift(
    service: SettingsService, sources: Mapping[str, Mapping[str, str]]
) -> DriftReport:
    return _drift(service, await service.stored(), sources)[0]


# ------------------------------------------------------------------- prune


@dataclass
class PruneReport:
    file: str
    pruned: list = field(default_factory=list)
    kept: int = 0
    refused: dict = field(default_factory=dict)  # key -> "differs"
    interpolated: list = field(default_factory=list)
    text: str = field(default="", repr=False)  # the pruned file content (may hold secrets)


def plan_prune(
    service: SettingsService,
    stored: StoredSettings,
    path: str,
    *,
    keep: Iterable[str] = (),
) -> PruneReport:
    """Which assignments of the env file at ``path`` the store already holds.
    A key whose env value differs from the store is never removed: it would
    stop shadowing the store only after the operator decides which one is right
    (an env value wins over a store value)."""
    import io

    keep_set = {ALIASES.get(k, k) for k in keep} | set(keep)
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError:
        raise HostError("file_unreadable") from None
    report = PruneReport(file=os.path.basename(path))
    out: list[str] = []
    for binding in parse_stream(io.StringIO(raw)):
        original = binding.original.string
        name = binding.key
        key = ALIASES.get(name, name) if name else None
        if (
            name is None
            or binding.error
            or key not in service.registry
            or name in keep_set
            or key in keep_set
            or key not in stored.values
            or binding.value is None
        ):
            out.append(original)
            report.kept += 1
            continue
        if "$" in binding.value:
            report.interpolated.append(name)
            out.append(original)
            report.kept += 1
            continue
        value = normalize_value(binding.value)
        if not value:
            out.append(original)  # an empty assignment shadows nothing
            report.kept += 1
        elif _same(service, key, value, stored.values[key]):
            report.pruned.append(name)
        else:
            report.refused[name] = "differs"
            out.append(original)
            report.kept += 1
    report.text = "".join(out)
    return report


def _write_private(path: str, data: str) -> None:
    """Create ``path`` (mode 600), refusing to touch an existing file."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise HostError("file_exists", os.path.basename(path)) from None
    except OSError:
        raise HostError("cannot_create_file", os.path.basename(path)) from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


async def prune_env_files(
    service: SettingsService,
    paths: Sequence[str],
    *,
    apply: bool,
    swap: bool = False,
    keep: Iterable[str] = (),
    actor: Actor,
    clock: Callable[[], float] = time.time,
) -> list[PruneReport]:
    """Plan (and with ``apply`` write) the pruned copies of the env files.

    Apply writes ``<file>.pruned`` and a private backup ``<file>.pre-v4.<ts>``
    of each file with something to prune; ``swap`` then replaces the original by
    the pruned copy. Files are created 600 and never overwritten. The audit row
    commits with the files (one is rolled back with the other)."""
    stored = await service.stored()
    if stored.unverified:
        raise HostError("store_unverified", "run settings-verify first")
    reports = [plan_prune(service, stored, p, keep=keep) for p in paths]
    if not apply or not any(r.pruned for r in reports):
        return reports
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(clock()))
    created: list[str] = []
    try:
        async with service._engine.begin() as conn:
            await audit.write(
                conn, "cli.settings_prune", "settings_store", None, None, None, "success",
                actor_kind=actor.kind, actor_email=actor.email,
                detail={
                    "files": len(paths),
                    "pruned": sum(len(r.pruned) for r in reports),
                    "refused": sum(len(r.refused) for r in reports),
                    "swap": bool(swap),
                },
            )
            for path, report in zip(paths, reports):
                if not report.pruned:
                    continue
                backup, pruned = f"{path}.pre-v4.{stamp}", f"{path}.pruned"
                with open(path, encoding="utf-8") as handle:
                    _write_private(backup, handle.read())
                created.append(backup)
                _write_private(pruned, report.text)
                created.append(pruned)
            if swap:
                for path, report in zip(paths, reports):
                    if report.pruned:
                        os.replace(f"{path}.pruned", path)
                        os.chmod(path, 0o600)
                        created.remove(f"{path}.pruned")
    except BaseException:
        for leftover in created:
            try:
                os.unlink(leftover)
            except OSError:
                pass
        raise
    return reports


# ---------------------------------------------------------------- exports


_BARE = re.compile(r"^[A-Za-z0-9_./:@+=,-]*$")


def env_line(name: str, value: str) -> str:
    """``NAME=value`` the way compose env files read it."""
    if _BARE.match(value):
        return f"{name}={value}\n"
    if "'" in value or "\n" in value or "\r" in value:
        raise HostError("unrepresentable_value", name)
    return f"{name}='{value}'\n"


def _text_of(service: SettingsService, key: str, value: Any) -> str:
    spec = service.registry.get(key)
    if spec.type is ValueType.BOOL:
        return "true" if value else "false"
    if spec.type is ValueType.JSON:
        return canonical_json(value)
    return value if isinstance(value, str) else str(value)


async def export_env(
    service: SettingsService, names: Sequence[str], out: str, actor: Actor
) -> int:
    """Write the named settings, with values, to a new private env file (the
    break-glass copy). Audited by names; refuses an existing file."""
    names = list(dict.fromkeys(names))
    if not names:
        raise HostError("no_keys")
    for name in names:
        if name not in service.registry:
            raise HostError("unknown_key", name[:64])
    stored = await service.stored()
    missing = [n for n in names if n not in stored.values]
    if missing:
        raise HostError("not_in_store", ",".join(missing)[:200])
    body = "".join(env_line(n, _text_of(service, n, stored.values[n])) for n in names)
    await _audited_file(
        service, out, body, actor, "cli.settings_env_export", {"settings": names, "count": len(names)}
    )
    return len(names)


async def _audited_file(
    service: SettingsService,
    path: str,
    body: str,
    actor: Actor,
    action: str,
    detail: dict,
    *,
    append_to_existing: bool = False,
) -> None:
    """Audit row and file in one unit: the row rolls back if the file fails."""
    created = False
    try:
        async with service._engine.begin() as conn:
            await audit.write(
                conn, action, "settings_store", None, None, None, "success",
                actor_kind=actor.kind, actor_email=actor.email, detail=detail,
            )
            if append_to_existing and os.path.lexists(path):
                _append_private(path, body)
            else:
                _write_private(path, body)
                created = True
    except BaseException:
        if created:
            try:
                os.unlink(path)
            except OSError:
                pass
        raise


def _open_private_existing(path: str, flags: int) -> int:
    """Open an existing file without following a symlink and verify, on the
    OPENED descriptor, that it is a regular file owned by this user with no
    group or other access (no check-then-open gap)."""
    try:
        fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0))
    except OSError:  # a symlink (ELOOP), a missing file, no permission
        raise HostError("file_not_private", os.path.basename(path)) from None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mode & 0o077
            or info.st_uid != os.geteuid()
        ):
            raise HostError("file_not_private", os.path.basename(path))
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_private(path: str) -> str:
    fd = _open_private_existing(path, os.O_RDONLY)
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        return handle.read()


def _append_private(path: str, body: str) -> None:
    fd = _open_private_existing(path, os.O_RDWR | os.O_APPEND)
    with os.fdopen(fd, "a+", encoding="utf-8") as handle:
        handle.seek(0)
        existing = handle.read()
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(body)


async def export_worker(service: SettingsService, out: str, actor: Actor) -> None:
    """Write the two worker values (API_KEY, AES_HEX_KEY) to ``out``: a new
    private file, or appended to an existing private env file that has neither."""
    stored = await service.stored()
    missing = [k for k in WORKER_COPIES.values() if k not in stored.values]
    if missing:
        raise HostError("not_in_store", ",".join(missing))
    if os.path.lexists(out):
        present = parse_env_text(_read_private(out))
        if any(name in present for name in WORKER_COPIES):
            raise HostError("worker_keys_present", os.path.basename(out))
    body = "".join(
        env_line(name, stored.values[key]) for name, key in WORKER_COPIES.items()
    )
    await _audited_file(
        service, out, body, actor, "cli.bootstrap_export_worker",
        {"settings": sorted(WORKER_COPIES), "count": len(WORKER_COPIES)},
        append_to_existing=True,
    )


# ---------------------------------------------------------- bootstrap-keys


def generate_value(key: str) -> str:
    """A fresh value of the right shape for one generated key."""
    if key == "AUTH_AES_HEX_KEY":  # a Fernet key, despite the name
        return Fernet.generate_key().decode()
    if key == "MASTER_ENCRYPTION_KEYSET":
        from tink.proto import tink_pb2

        from common.services import keyset as keyset_module  # tink; only this command needs it

        return keyset_module.encode_keyset(
            keyset_module.add_primary_key(tink_pb2.Keyset())
        )
    return secrets.token_hex(32)


@dataclass
class BootstrapResult:
    generated: list = field(default_factory=list)
    keyset_fp: str = ""  # key-id fingerprint of the stored keyset (ids only), as services report it


async def _pg_counts(service: SettingsService) -> dict:
    from backend.admin.repositories import views

    async with service._engine.connect() as conn:
        return await views.platform_counts(conn)


async def _mongo_has_data(uri: str) -> bool:
    """Whether any non-system database on the Mongo server has a non-empty
    ``users`` or ``form_responses`` collection. Read-only; nothing is printed."""
    import asyncio

    import pymongo

    def work() -> bool:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        try:
            for name in client.list_database_names():
                if name in ("admin", "local", "config"):
                    continue
                database = client[name]
                present = set(database.list_collection_names())
                for collection in ("users", "form_responses"):
                    if collection in present and database[collection].find_one({}, {"_id": 1}) is not None:
                        return True
            return False
        finally:
            client.close()

    return await asyncio.to_thread(work)


async def refuse_if_stack_has_data(
    service: SettingsService,
    *,
    mongo_uri: Optional[str] = None,
    counts: Optional[Callable[[], Any]] = None,
    mongo_check: Optional[Callable[[str], Any]] = None,
) -> None:
    """Fail closed: a new response keyset cannot read data the old one wrote, so
    refuse when users or responses exist, and when that cannot be established."""
    hint = "run settings-import from the existing configuration instead"
    try:
        found = await (counts() if counts is not None else _pg_counts(service))
        users = int(found["users"]["total"])
        responses = int(found["responses"]["total"])
    except Exception:  # noqa: BLE001 - class only: never the cause
        raise HostError("stack_unknown", "the data counts could not be read; " + hint) from None
    if users > 0 or responses > 0:
        raise HostError("stack_has_data", hint)
    if (mongo_uri or "").strip():
        try:
            has = await (mongo_check or _mongo_has_data)(mongo_uri.strip())
        except Exception:  # noqa: BLE001
            raise HostError("stack_unknown", "the document store could not be read; " + hint) from None
        if has:
            raise HostError("stack_has_data", hint)


def keyset_fingerprint_of(value: str) -> str:
    """The fingerprint services report for a keyset (``service_state.keyset_fp``)."""
    from common.services import keyset as keyset_module
    from common.settings.loader.runtime import keyset_fingerprint

    return keyset_fingerprint(k.key_id for k in keyset_module.parse_keyset(value).key)


async def bootstrap_keys(
    service: SettingsService,
    actor: Actor,
    *,
    environ: Mapping[str, str],
    existing_stack: bool,
    fill_missing: bool = False,
    counts: Optional[Callable[[], Any]] = None,
    mongo_check: Optional[Callable[[str], Any]] = None,
) -> BootstrapResult:
    """Generate the stack's own keys into the store and print nothing of them.

    Refused whatever the flags when the stack holds data (users or responses in
    Postgres, or in the document store named by ``MONGO_URI``) or that cannot be
    established: a new keyset could not read what the old one encrypted, and
    import is the way for an existing stack. Also refused when the deploy says
    the stack already holds data (``existing_stack``), when the environment
    already carries any of the keys, or when the store holds any of them, unless
    ``fill_missing`` (finishing an interrupted run: it only adds the missing
    ones)."""
    if existing_stack:
        raise HostError("existing_stack", "import the current keys with settings-import instead")
    env_keys = sorted(k for k in GENERATED_KEYS if normalize_value(environ.get(k)))
    if env_keys:
        raise HostError("keys_in_environment", ",".join(env_keys))
    await refuse_if_stack_has_data(
        service, mongo_uri=environ.get("MONGO_URI"), counts=counts, mongo_check=mongo_check
    )
    stored = await service.stored()
    present = sorted(k for k in GENERATED_KEYS if k in stored.values or k in stored.tombstones or k in stored.unverified)
    if present and not fill_missing:
        raise HostError("keys_exist", ",".join(present))
    result = BootstrapResult()
    for key in GENERATED_KEYS:
        if key in present:
            continue
        change = await service.import_once(key, generate_value(key), actor)
        if change is not None and change.changed:
            result.generated.append(key)
    stored = await service.stored()
    if "MASTER_ENCRYPTION_KEYSET" in stored.values:
        result.keyset_fp = keyset_fingerprint_of(stored.values["MASTER_ENCRYPTION_KEYSET"])
    return result


# --------------------------------------------------------------- set/restore


def parse_set_value(raw: str) -> str:
    """The value as typed: one trailing newline (from a pipe) is not part of it."""
    return raw[:-1] if raw.endswith("\n") else raw


async def set_value(
    service: SettingsService, key: str, raw: str, actor: Actor, *, confirmation: Optional[str]
):
    return await service.set(key, raw, actor, confirmation=confirmation)


async def clear_value(
    service: SettingsService, key: str, actor: Actor, *, confirmation: Optional[str]
):
    return await service.clear(key, actor, confirmation=confirmation)


async def restore_version(
    service: SettingsService, key: str, version: int, actor: Actor, *, confirmation: Optional[str]
):
    return await service.restore(key, version, actor, confirmation=confirmation)


# ---------------------------------------------------------------- admin mail

MAIL_SECTION = "admin_mail"
CODE_DIGITS = 6


def mail_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(CODE_DIGITS))


async def apply_mail(
    service: SettingsService,
    pairs: Mapping[str, str],
    actor: Actor,
    *,
    test_to: str,
    send: Callable[[Any, str, str, str], Any],
    ask_code: Callable[[], str],
    config_factory: Callable[[Mapping[str, Any]], Any],
) -> list[str]:
    """Save admin sign-in mail settings only after a real test mail arrived.

    The candidate configuration is the stored mail settings overlaid with
    ``pairs``. A mail with a random code goes to ``test_to`` using exactly
    that configuration; the operator types the code from the received mail.
    Only a matching code lets the keys be saved (each one audited), so
    a typo in the server, port or password can never lock the admins out.
    Returns the keys saved. Nothing about the code or the password is printed."""
    registry = service.registry
    keys = {k: v for k, v in pairs.items() if k in registry and registry.get(k).section == MAIL_SECTION}
    foreign = sorted(set(pairs) - set(keys))
    if foreign:
        raise HostError("not_mail_settings", ",".join(foreign)[:200])
    if not keys:
        raise HostError("no_keys")
    typed: dict[str, Any] = {}
    for key, raw in keys.items():
        try:
            typed[key] = registry.validate(key, raw)
        except ValidationError as exc:
            raise HostError("invalid_value", f"{key} {exc.reason}") from None
    stored = await service.stored()
    candidate = {k: v for k, v in stored.values.items() if registry.get(k).section == MAIL_SECTION}
    candidate.update(typed)
    config = config_factory(candidate)
    code = mail_code()
    try:
        await send(config, test_to, "Test mail for the admin sign-in", f"Your confirmation code is {code}\n")
    except Exception:  # noqa: BLE001 - class only: the message can carry an address
        raise HostError("test_mail_failed") from None
    typed_code = (ask_code() or "").strip()
    if not secrets.compare_digest(typed_code.encode(), code.encode()):
        raise HostError("code_mismatch")
    saved = []
    for key in sorted(typed):
        await service.set(
            key, typed[key], actor,
            confirmation=key, mail_verified=True,
        )
        saved.append(key)
    return saved
