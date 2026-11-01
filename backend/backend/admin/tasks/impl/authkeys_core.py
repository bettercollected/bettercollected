"""The walk of the ``authkeys.*`` tasks over the values sealed with
``AUTH_AES_HEX_KEY`` (a Fernet key ring) at rest, in the backend's Postgres.

What is sealed with it, and where (docs/auth-key-rotation.md, the inventory):

=======================  =========================================  ==========================
target                   table                                      path in ``doc``
=======================  =========================================  ==========================
``forms``                ``app.forms``                              ``secrets.<action>[].value``
``form_versions``        ``app.form_versions``                      ``secrets.<action>[].value``
``actions``              ``app.actions``                            ``secrets[].value``
``workspace_actions``    ``app.workspace_actions``                  ``secrets[].value``
``scim_directories``     ``app.scim_directories``                   ``webhook_secret``
``registration_services````app.registration_services``              ``secret_sealed``
``form_webhooks``        ``app.form_webhooks``                      ``url_sealed``,
                                                                    ``secret_sealed``
=======================  =========================================  ==========================

A Fernet token carries no key id, so which key sealed a value is found by
trying: the ring's first member (current), then the second (previous). A value
only the previous key opens is *stale* and is re-encrypted; one neither opens is
*unopenable* and left alone; text that is not a Fernet token at all (an empty
value, a legacy plain one) is *plain* and never touched. Re-encryption keeps the
plaintext string exactly as it was sealed (the envelopes that bind a value to a
workspace and a row are inside it).

Never prints or returns a value or a key: counts and ids only.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from common.configs.crypto import Crypto

logger = logging.getLogger("authkeys")

Path = Tuple[Any, ...]  # into a document: ("secrets", "<action id>", 0, "value")

# a Fernet token is url-safe base64 of: version (0x80), 8 bytes of time, 16 of
# IV, at least one 16-byte block, 32 of HMAC
FERNET_VERSION = 0x80
FERNET_MIN_BYTES = 1 + 8 + 16 + 16 + 32


def is_fernet_token(value: Any) -> bool:
    """Whether ``value`` has the shape of a Fernet token (not that any key opens it)."""
    if not isinstance(value, str) or len(value) < 100:
        return False
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return False
    return len(raw) >= FERNET_MIN_BYTES and raw[0] == FERNET_VERSION


# ------------------------------------------------------------------- targets
@dataclass(frozen=True)
class Target:
    name: str
    schema: str
    table: str
    # SQL condition (no parameters) that keeps rows that may hold a sealed value
    where: str
    values: Callable[[Dict[str, Any]], List[Tuple[Path, str]]]


def _bag_values(doc: Dict[str, Any]) -> List[Tuple[Path, str]]:
    """``secrets``: {action id: [{name, value, ...}]} (forms and their versions)."""
    found: List[Tuple[Path, str]] = []
    bag = doc.get("secrets")
    if isinstance(bag, dict):
        for action_id, items in bag.items():
            for index, item in enumerate(items if isinstance(items, list) else []):
                value = item.get("value") if isinstance(item, dict) else None
                if isinstance(value, str) and value:
                    found.append((("secrets", action_id, index, "value"), value))
    return found


def _list_values(doc: Dict[str, Any]) -> List[Tuple[Path, str]]:
    """``secrets``: [{name, value, ...}] (actions and the workspace's copy)."""
    found: List[Tuple[Path, str]] = []
    items = doc.get("secrets")
    for index, item in enumerate(items if isinstance(items, list) else []):
        value = item.get("value") if isinstance(item, dict) else None
        if isinstance(value, str) and value:
            found.append((("secrets", index, "value"), value))
    return found


def _fields(*names: str) -> Callable[[Dict[str, Any]], List[Tuple[Path, str]]]:
    def values(doc: Dict[str, Any]) -> List[Tuple[Path, str]]:
        return [
            ((name,), doc[name])
            for name in names
            if isinstance(doc.get(name), str) and doc[name]
        ]

    return values


_HAS_SECRETS = "jsonb_typeof(doc -> 'secrets') IN ('object', 'array')"
TARGETS: Dict[str, Target] = {
    t.name: t
    for t in (
        Target("forms", "app", "forms", _HAS_SECRETS, _bag_values),
        Target("form_versions", "app", "form_versions", _HAS_SECRETS, _bag_values),
        Target("actions", "app", "actions", _HAS_SECRETS, _list_values),
        Target("workspace_actions", "app", "workspace_actions", _HAS_SECRETS, _list_values),
        Target(
            "scim_directories", "app", "scim_directories",
            "doc ->> 'webhook_secret' IS NOT NULL", _fields("webhook_secret"),
        ),
        Target(
            "registration_services", "app", "registration_services",
            "doc ->> 'secret_sealed' IS NOT NULL", _fields("secret_sealed"),
        ),
        Target(
            "form_webhooks", "app", "form_webhooks",
            "(doc ->> 'url_sealed' IS NOT NULL OR doc ->> 'secret_sealed' IS NOT NULL)",
            _fields("url_sealed", "secret_sealed"),
        ),
    )
}


def _doc(value: Any) -> Dict[str, Any]:
    """A ``doc`` as a dict (a driver may hand a JSONB value back as text)."""
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def _get(document: Any, path: Path) -> Any:
    for part in path:
        document = document[part]
    return document


def _set(document: Any, path: Path, value: Any) -> None:
    for part in path[:-1]:
        document = document[part]
    document[path[-1]] = value


Update = Tuple[Path, str, str]  # path, the value read, its replacement


# -------------------------------------------------------------------- store
class PostgresStore:
    name = "postgres"

    def __init__(self, engine, target: Target):
        self.engine = engine  # SQLAlchemy AsyncEngine
        self.target = target
        # identifiers are constants of this module, never from a request
        self._table = f'"{target.schema}"."{target.table}"'

    async def batch(self, after: Optional[str], limit: int) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        sql = f"SELECT id, doc FROM {self._table} WHERE ({self.target.where})"
        params: Dict[str, Any] = {"n": limit}
        if after is not None:
            sql += " AND id > :after"
            params["after"] = after
        sql += " ORDER BY id LIMIT :n"
        async with self.engine.connect() as conn:
            rows = (await conn.execute(text(sql), params)).all()
        return [{"id": row[0], "doc": _doc(row[1])} for row in rows]

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(f"SELECT doc FROM {self._table} WHERE id = :id"), {"id": record_id}
                )
            ).first()
        return None if row is None else _doc(row[0])

    async def write(self, record_id: str, updates: Sequence[Update]) -> bool:
        """Compare-and-set under a row lock. Only the sealed values change, each by
        its own path (``jsonb_set``): the rest of the stored document is not
        re-serialised, so no number, date or key order in it can move. The
        checksum follows the document (computed from the document as read, with
        the new values in place). False when the row is gone or a value is not
        the one that was read."""
        import copy

        from sqlalchemy import text

        from common.db.canonical import checksum

        async with self.engine.begin() as conn:
            row = (
                await conn.execute(
                    text(f"SELECT doc FROM {self._table} WHERE id = :id FOR UPDATE"),
                    {"id": record_id},
                )
            ).first()
            if row is None:
                return False
            document = _doc(row[0])
            changed = copy.deepcopy(document)
            for path, old, new in updates:
                try:
                    if _get(document, path) != old:
                        return False
                except (KeyError, IndexError, TypeError):
                    return False
                _set(changed, path, new)
            expression = "doc"
            params: Dict[str, Any] = {"id": record_id, "sum": checksum(changed)}
            for index, (path, _old, new) in enumerate(updates):
                expression = (
                    f"jsonb_set({expression}, CAST(:p{index} AS text[]), "
                    f"to_jsonb(CAST(:v{index} AS text)), false)"
                )
                params[f"p{index}"] = [str(part) for part in path]
                params[f"v{index}"] = new
            await conn.execute(
                text(
                    f"UPDATE {self._table} SET doc = {expression}, "
                    "_bc_checksum = :sum WHERE id = :id"
                ),
                params,
            )
        return True


# ---------------------------------------------------------------- the work
class Rotation:
    """Opens values with the ring and re-encrypts them with its first member."""

    def __init__(self, ring_text: str):
        self.ring = Crypto(ring_text)
        self.primary = Crypto(ring_text.split(",")[0].strip())

    def position(self, value: str) -> Optional[int]:
        """0: the current key opens it, 1: only the previous one, None: neither."""
        return self.ring.opening_position(value)

    def classify(self, doc: Dict[str, Any], target: Target):
        """(values, current, stale paths, unopenable paths, plain count)."""
        current = stale = unopenable = 0
        stale_values: List[Tuple[Path, str]] = []
        plain = 0
        for path, value in target.values(doc):
            if not is_fernet_token(value):
                plain += 1
                continue
            where = self.position(value)
            if where == 0:
                current += 1
            elif where is None:
                unopenable += 1
            else:
                stale += 1
                stale_values.append((path, value))
        return current, stale, unopenable, plain, stale_values

    def reencrypt(self, doc: Dict[str, Any], target: Target):
        """The updates that move a document's stale values to the first member,
        and how many values nothing opens. Each new value is read back with the
        first member ALONE before it is returned."""
        updates: List[Update] = []
        unopenable = 0
        for path, value in target.values(doc):
            if not is_fernet_token(value):
                continue
            where = self.position(value)
            if where is None:
                unopenable += 1
                continue
            if where == 0:
                continue
            plain = self.ring.decrypt(value)
            new = self.primary.encrypt(plain)
            if self.primary.decrypt(new) != plain or self.ring.opening_position(new) != 0:
                raise RuntimeError("a re-encrypted value did not read back")
            updates.append((path, value, new))
        return updates, unopenable


def _count(counts: Counter, rotation: Rotation, doc, target: Target) -> None:
    current, stale, unopenable, plain, _ = rotation.classify(doc, target)
    counts["records"] += 1
    counts["values"] += current + stale + unopenable
    counts["values_current"] += current
    counts["values_stale"] += stale
    counts["values_unopenable"] += unopenable
    counts["values_plain"] += plain


async def scan(
    store,
    target: Target,
    rotation: Rotation,
    batch_size: int,
    on_batch: Optional[Callable[[int], Any]] = None,
) -> Dict:
    """Read-only counts (a dry run, ``verify`` and the scan before a drop): records,
    sealed values on the first key, only on the second, on neither, plain. A true
    result of ``on_batch(records so far)`` stops the scan (counts carry ``stopped``)."""
    counts: Counter = Counter(records=0)
    after = None
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        after = batch[-1]["id"]
        for record in batch:
            _count(counts, rotation, record["doc"], target)
        if on_batch is not None and await on_batch(counts["records"]):
            counts["stopped"] = 1
            break
    return dict(counts)


async def reencrypt_store(
    store,
    target: Target,
    rotation: Rotation,
    batch_size: int = 200,
    start_after: Optional[str] = None,
    on_batch: Optional[Callable[[str, Dict], Any]] = None,
) -> Tuple[Dict, Optional[str]]:
    """Re-encrypt one table; returns the counts and the last id walked. Each
    record is read again after its write and counted re-encrypted only if the
    stored values are the ones written. ``on_batch(last id, counts so far)`` is
    awaited after each batch; a true result stops the walk."""
    counts: Counter = Counter()
    after = start_after
    while True:
        batch = await store.batch(after, batch_size)
        if not batch:
            break
        for record in batch:
            after = record["id"]
            counts["records"] += 1
            updates, unopenable = rotation.reencrypt(record["doc"], target)
            sealed = [v for _, v in target.values(record["doc"]) if is_fernet_token(v)]
            counts["values"] += len(sealed)
            counts["values_unopenable"] += unopenable
            counts["values_plain"] += len(target.values(record["doc"])) - len(sealed)
            counts["values_current"] += len(sealed) - unopenable - len(updates)
            if not updates:
                continue
            if not await store.write(record["id"], updates):
                counts["records_changed_concurrently"] += 1
                logger.info("%s %s changed while it was read; left for the next run", target.name, record["id"])
                continue
            if not await _read_back(store, record["id"], updates):
                counts["records_readback_failed"] += 1
                logger.warning("%s %s did not read back as written; not counted", target.name, record["id"])
                continue
            counts["records_reencrypted"] += 1
            counts["values_reencrypted"] += len(updates)
        logger.info("%s: walked to %s; %s", target.name, after, json.dumps(dict(counts), sort_keys=True))
        if on_batch is not None and await on_batch(after, dict(counts)):
            counts["stopped"] = 1
            break
    return dict(counts), after


async def _read_back(store, record_id: str, updates: Sequence[Update]) -> bool:
    fresh = await store.read(record_id)
    if fresh is None:
        return False
    for path, _old, new in updates:
        try:
            if _get(fresh, path) != new:
                return False
        except (KeyError, IndexError, TypeError):
            return False
    return True
