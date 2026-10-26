"""python -m backend.identity_rekey [--dry-run] [--batch-size N] [--expect-fingerprint HEX]

The one pass that moves every stored respondent identity to the keyed scheme
(``v2:`` + HMAC-SHA256(RESPONDENT_IDENTITY_KEY, md5_hex(email)); see
``backend.app.utils.respondent_identity``). It needs no address: the legacy
value is the MD5 step of the formula, so ``HMAC(key, stored)`` is the new value.

Where the identity is stored (both tables keep the JSON document in ``doc`` and
a generated, indexed ``anonymous_identity`` column over it, so the update goes
through ``doc``):

* ``app.form_responses``: the response's own identity;
* ``app.responses_deletion_requests``: the copy a deletion request keeps, which
  the respondent's "my deletion requests" list matches on.

Properties:

* **Idempotent**: a value that already starts with ``v2:`` is never touched, so
  the pass can run any number of times and on every start.
* **Resumable**: rows are visited in id order in batches of ``--batch-size``;
  each batch is its own transaction. The data is the checkpoint: a converted row
  no longer matches the ``NOT LIKE 'v2:%'`` predicate, so an interrupted run
  continues where it stopped without a checkpoint table (and without a schema
  migration, which cannot hold the key).
* **Safe beside live writers**: each row is updated only while it still holds
  the value that was read (``WHERE ... = :old``) and only the one key of ``doc``
  is rewritten (``jsonb_set``), never the whole document. Several processes can
  start together: one advisory lock (``pg_try_advisory_lock``, a dedicated
  connection) lets one of them run; the others skip.
* **Counts only**: nothing logged or printed names an id, a value or a hash,
  and an error is logged by its class (a database error message can carry the
  statement's parameters, which here are identity values).

Exit status: 0 nothing left to convert, 1 values remain or the run failed, 2
another process holds the lock, 3 the key is missing or unusable, 4 the key is
not the one that converted the stored identities (or not ``--expect-fingerprint``).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.utils.respondent_identity import (
    PREFIX,
    IdentityKeyError,
    IdentityKeyMismatch,
    configured_key,
    convert_legacy,
    fingerprint_of,
    key_check_value,
)
from backend.db.models import FormResponseRow, ResponseDeletionRequestRow

TABLES = {
    "form_responses": FormResponseRow,
    "responses_deletion_requests": ResponseDeletionRequestRow,
}
DEFAULT_BATCH = 500
#: the second pass of an API start, for a 4.0 replica still writing MD5 during the roll
RERUN_DELAY_SECONDS = 300.0
#: advisory lock key, a stable signed 64-bit number of this pass
LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"bettercollected:respondent-identity-rekey").digest()[:8],
    "big",
    signed=True,
)


@dataclass
class RekeyReport:
    """Counts per table; never a value, an id or a hash."""

    converted: Dict[str, int] = field(default_factory=dict)
    changed_meanwhile: Dict[str, int] = field(default_factory=dict)
    remaining: Dict[str, int] = field(default_factory=dict)
    locked: bool = False
    #: matched | written | adopted | None (locked)
    key_check: Optional[str] = None
    fingerprint: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "converted": self.converted,
            "changed_meanwhile": self.changed_meanwhile,
            "remaining": self.remaining,
            "locked": self.locked,
            "key_check": self.key_check,
            "key_fingerprint": self.fingerprint,
        }

    @property
    def done(self) -> bool:
        return not self.locked and not any(self.remaining.values())


def _table(row) -> str:
    return row.__table__.fullname  # a constant of the model, never user input


async def _count_remaining(conn, row) -> int:
    return int(
        await conn.scalar(
            text(
                f"SELECT count(*) FROM {_table(row)} "
                "WHERE anonymous_identity IS NOT NULL "
                f"AND anonymous_identity NOT LIKE '{PREFIX}%'"
            )
        )
    )


async def _rekey_table(
    engine: AsyncEngine, name: str, row, key: bytes, batch_size: int, report: RekeyReport
) -> None:
    table = _table(row)
    select_batch = text(
        f"SELECT id, anonymous_identity FROM {table} "
        "WHERE id > :last AND anonymous_identity IS NOT NULL "
        f"AND anonymous_identity NOT LIKE '{PREFIX}%' "  # the literal of the partial index (0022)
        "ORDER BY id LIMIT :n"
    )
    # only the one key of the document, and only while it still holds what was read
    update_one = text(
        f"UPDATE {table} SET doc = jsonb_set(doc, '{{anonymous_identity}}', "
        "to_jsonb(CAST(:new AS text))) "
        "WHERE id = :id AND anonymous_identity = :old"
    )
    report.converted[name] = 0
    report.changed_meanwhile[name] = 0
    last = ""
    while True:
        async with engine.begin() as conn:
            batch = (
                await conn.execute(
                    select_batch, {"last": last, "n": batch_size}
                )
            ).all()
            for row_id, old in batch:
                result = await conn.execute(
                    update_one,
                    {"id": row_id, "old": old, "new": convert_legacy(key, old)},
                )
                if result.rowcount == 1:
                    report.converted[name] += 1
                else:
                    report.changed_meanwhile[name] += 1
        if len(batch) < batch_size:
            return
        last = batch[-1][0]


KEY_CHECK_TABLE = "app.respondent_identity_key_check"


async def read_key_check(conn) -> Optional[str]:
    return await conn.scalar(text(f"SELECT check_value FROM {KEY_CHECK_TABLE} WHERE id = 1"))


def _mismatch(stored: str, expected: str) -> IdentityKeyMismatch:
    # fingerprints only (4 bytes of an HMAC): never a check value, never a key
    return IdentityKeyMismatch(
        "RESPONDENT_IDENTITY_KEY is not the key that converted the stored respondent "
        f"identities (configured key fingerprint {fingerprint_of(expected)}, stored "
        f"{fingerprint_of(stored)}). Nothing was converted and the API will not start with it: "
        "set the key the stack used at its first 4.1 start. See docs/respondent-identity.md."
    )


async def verify_key(engine: AsyncEngine, key: bytes) -> Optional[str]:
    """The key check of the stored identities, without the lock and without
    writing: ``None`` when no row exists yet, else the stored value when it is
    this key's; raises :class:`IdentityKeyMismatch` when it is another key's."""
    expected = key_check_value(key)
    async with engine.connect() as conn:
        stored = await read_key_check(conn)
    if stored is not None and not hmac.compare_digest(stored.encode(), expected.encode()):
        raise _mismatch(stored, expected)
    return stored


async def _ensure_key_check(engine: AsyncEngine, key: bytes, *, write: bool) -> str:
    """Under the lock, before any conversion: ``matched``, ``adopted`` (v2 values
    were already stored without a row: the configured key is taken as theirs) or
    ``written`` (nothing was converted yet). Raises on another key's row."""
    expected = key_check_value(key)
    async with engine.begin() as conn:
        stored = await read_key_check(conn)
        if stored is not None:
            if not hmac.compare_digest(stored.encode(), expected.encode()):
                raise _mismatch(stored, expected)
            return "matched"
        has_v2 = False
        for row in TABLES.values():
            has_v2 = has_v2 or bool(
                await conn.scalar(
                    text(
                        f"SELECT EXISTS (SELECT 1 FROM {_table(row)} "
                        f"WHERE anonymous_identity LIKE '{PREFIX}%')"
                    )
                )
            )
        if write:
            await conn.execute(
                text(
                    f"INSERT INTO {KEY_CHECK_TABLE} (id, check_value) VALUES (1, :v) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"v": expected},
            )
            # a concurrent writer (not under our lock) would have won: it must be this key
            winner = await read_key_check(conn)
            if winner != expected:
                raise _mismatch(winner, expected)
        return "adopted" if has_v2 else "written"


async def rekey_identities(
    engine: AsyncEngine,
    key: bytes,
    *,
    batch_size: int = DEFAULT_BATCH,
    dry_run: bool = False,
) -> RekeyReport:
    """Convert every stored legacy identity. ``dry_run`` only counts them (and
    checks the key, writing nothing). Raises :class:`IdentityKeyMismatch`, before
    converting anything, when another key converted the stored identities."""
    report = RekeyReport(fingerprint=fingerprint_of(key_check_value(key)))
    async with engine.connect() as lock_conn:
        if not await lock_conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}):
            report.locked = True
            return report
        unlocked = False
        try:
            await lock_conn.rollback()  # the lock is session level; leave no transaction open
            # the check row is written BEFORE the first conversion, so a crash
            # mid-pass is covered by it too
            report.key_check = await _ensure_key_check(engine, key, write=not dry_run)
            if report.key_check == "adopted":
                logger.warning(
                    "respondent identity pass: v2 identities were stored without a key check; "
                    "the configured key (fingerprint {}) is taken as the one that converted them",
                    report.fingerprint,
                )
            if not dry_run:
                for name, row in TABLES.items():
                    await _rekey_table(engine, name, row, key, batch_size, report)
            async with engine.connect() as conn:
                for name, row in TABLES.items():
                    report.remaining[name] = await _count_remaining(conn, row)
        finally:
            try:
                await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                await lock_conn.commit()
                unlocked = True
            except Exception:  # noqa: BLE001 - class only
                logger.warning("respondent identity pass: advisory unlock failed")
            if not unlocked:
                # a pooled connection would keep the session lock for as long as it lives
                try:
                    await lock_conn.invalidate()
                except Exception:  # noqa: BLE001
                    logger.warning("respondent identity pass: could not drop the lock connection")
    return report


def log_report(report: RekeyReport) -> None:
    if report.locked:
        logger.info("respondent identity pass: another process is running it; skipped")
    else:
        logger.info(
            "respondent identity pass: key fingerprint={} key_check={} converted={} "
            "changed_meanwhile={} remaining={}",
            report.fingerprint,
            report.key_check,
            report.converted,
            report.changed_meanwhile,
            report.remaining,
        )
    if not report.locked and any(report.remaining.values()):
        logger.error(
            "respondent identity pass: stored identities are still not v2 ({}); matching refuses them",
            report.remaining,
        )


async def check_key_at_startup(engine: Optional[AsyncEngine]) -> None:
    """The API's start refuses (raises) when the configured key is not the one
    that converted the stored identities. A cheap read, no lock, no write: the
    first conversion (and the row) comes from the background pass."""
    if engine is None:
        return
    key = configured_key()
    try:
        stored = await verify_key(engine, key)
    except IdentityKeyMismatch:
        raise
    except Exception as exc:  # noqa: BLE001 - class only: the message can carry values
        logger.error("respondent identity key check failed ({})", type(exc).__name__)
        return
    logger.info(
        "respondent identity key fingerprint={} ({})",
        fingerprint_of(key_check_value(key)),
        "matches the stored check" if stored is not None else "no stored check yet",
    )


async def run_at_startup(engine: Optional[AsyncEngine]) -> Optional[RekeyReport]:
    """One pass as the API runs it: whatever it finds (a 4.0 import, a 4.0
    replica still writing during a rolling update) is converted, and a failure
    never takes the API down (matching refuses a non-v2 value, so nothing is
    exposed). A key that is not the one that converted the stored identities
    converts nothing and is logged as an error."""
    if engine is None:
        return None
    try:
        report = await rekey_identities(engine, configured_key())
    except IdentityKeyMismatch as exc:
        logger.error("respondent identity pass refused: {}", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - class only: the message can carry values
        logger.error(
            "respondent identity pass failed ({}); run python -m backend.identity_rekey",
            type(exc).__name__,
        )
        return None
    log_report(report)
    return report


async def background_passes(
    engine: Optional[AsyncEngine], rerun_delay: Optional[float] = None
) -> None:
    """What the API runs after it has started: a pass now, and once more after
    ``rerun_delay`` seconds for a 4.0 replica that was still writing MD5 while
    the roll finished. Its ``remaining`` counts are in the log lines."""
    await run_at_startup(engine)
    await asyncio.sleep(RERUN_DELAY_SECONDS if rerun_delay is None else rerun_delay)
    await run_at_startup(engine)


def start_background_passes(engine: Optional[AsyncEngine]) -> Optional["asyncio.Task"]:
    """Start :func:`background_passes`; the caller keeps the task and cancels it
    at shutdown. ``None`` without a database."""
    if engine is None:
        return None
    return asyncio.ensure_future(background_passes(engine))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend.identity_rekey", description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="count what would be converted; change nothing")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument(
        "--expect-fingerprint",
        metavar="HEX",
        help="refuse (exit 4) unless the configured key's fingerprint (8 hex digits, logged by "
        "every pass) is this one",
    )
    return parser


async def run(args: argparse.Namespace) -> int:
    from backend.app.container import container
    from backend.db.startup import dispose_postgres

    try:
        key = configured_key()
    except IdentityKeyError as exc:
        logger.error("{}", exc)
        return 3
    fingerprint = fingerprint_of(key_check_value(key))
    expected = (args.expect_fingerprint or "").strip().lower()
    if expected and not hmac.compare_digest(expected.encode(), fingerprint.encode()):
        logger.error(
            "the configured RESPONDENT_IDENTITY_KEY has fingerprint {}, not the expected one",
            fingerprint,
        )
        return 4
    engine = container.pg_engine()
    if engine is None:
        logger.error("DATABASE_URL is not set")
        return 1
    try:
        report = await rekey_identities(
            engine, key, batch_size=max(1, args.batch_size), dry_run=args.dry_run
        )
    except IdentityKeyMismatch as exc:
        logger.error("{}", exc)
        return 4
    except Exception as exc:  # noqa: BLE001 - class only
        logger.error("respondent identity pass failed ({})", type(exc).__name__)
        return 1
    finally:
        await dispose_postgres(container)
    print(json.dumps(report.to_dict(), sort_keys=True))
    if report.locked:
        return 2
    return 0 if report.done else 1


def main(argv=None) -> int:
    return asyncio.run(run(build_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
