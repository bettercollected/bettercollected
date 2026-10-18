"""Operator CLI: ``python -m backend.admin <command>``.

Prints counts, sequence numbers, setting names and short reason codes only,
never row contents or setting values.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional, Sequence

from backend.admin.config import AdminConfigError, AdminSettings, parse_master_key
from common.settings.crypto.keys import MASTER_KEY_KEY, MasterKeyError
from backend.admin.db import make_engine
from backend.admin.services import audit

MASTER_KEY_PREVIOUS_KEY = "SETTINGS_MASTER_KEY_PREVIOUS"
CLI_ACTOR_EMAIL = None  # the CLI is the host operator; audit rows say actor_kind=cli


def _parse_checkpoint(raw: str) -> tuple[int, bytes]:
    seq, _, digest = raw.partition(":")
    try:
        return int(seq), bytes.fromhex(digest)
    except ValueError:
        raise argparse.ArgumentTypeError("expected SEQ:ROW_HASH_HEX") from None


async def _audit_verify(checkpoint: Optional[tuple[int, bytes]]) -> int:
    settings = AdminSettings.from_env()
    engine = make_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await audit.verify_chain(conn, None, checkpoint)
    finally:
        await engine.dispose()
    print(result.summary())
    return 0 if result.ok else 1


def _service(settings: AdminSettings, *, with_previous: bool = False):
    """A ``SettingsService`` on the admin runtime role (never prints a key)."""
    from backend.admin.services.settings_store import SettingsService, store_registry
    from common.settings.keys import SectionKeys

    registry = store_registry()
    previous = None
    if with_previous and (os.environ.get(MASTER_KEY_PREVIOUS_KEY) or "").strip():
        previous = parse_master_key(os.environ[MASTER_KEY_PREVIOUS_KEY])
    keys = SectionKeys(
        settings.master_key,
        sections={s.section for s in registry},
        master_previous=previous,
    )
    return SettingsService(make_engine(settings), registry, keys)


def _cli_actor():
    from backend.admin.services.settings_store import Actor

    return Actor(kind="cli", email=CLI_ACTOR_EMAIL)


def read_env_file(path: str) -> dict[str, str]:
    """``KEY=value`` pairs of an env file, without interpolation."""
    from dotenv import dotenv_values

    if not os.path.isfile(path):
        raise AdminConfigError("the env file does not exist")
    return {k: v for k, v in dotenv_values(path, interpolate=False).items() if v is not None}


async def _settings_import(path: str) -> int:
    from backend.admin.services.settings_store import SettingsError
    from common.settings.registry import normalize_value

    settings = AdminSettings.from_env()  # no master key: stop before anything is read
    pairs = read_env_file(path)
    service = _service(settings)
    counts = {"imported": 0, "existing": 0, "empty": 0, "unknown": 0, "refused": 0}
    refused: list[tuple[str, str]] = []
    try:
        for name in sorted(pairs):
            if name not in service.registry:
                counts["unknown"] += 1
                continue
            value = normalize_value(pairs[name])
            if not value:
                counts["empty"] += 1
                continue
            try:
                change = await service.import_once(name, value, _cli_actor())
            except SettingsError as exc:
                counts["refused"] += 1
                refused.append((name, exc.detail or exc.code))
                continue
            counts["imported" if change is not None and change.changed else "existing"] += 1
    finally:
        await service._engine.dispose()
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    for name, reason in refused:
        print(f"refused {name} {reason}")
    return 0 if not refused else 1


async def _settings_verify() -> int:
    settings = AdminSettings.from_env()
    service = _service(settings, with_previous=True)
    try:
        problems = await service.verify()
    finally:
        await service._engine.dispose()
    for problem in problems:
        print(f"{problem.key} {problem.reason}")
    print(f"settings-verify: {'ok' if not problems else str(len(problems)) + ' problem(s)'}")
    return 0 if not problems else 1


async def _rewrap() -> int:
    settings = AdminSettings.from_env()
    service = _service(settings, with_previous=True)
    try:
        result = await service.rewrap(_cli_actor())
    finally:
        await service._engine.dispose()
    print(
        f"rewrap: rewrapped={result.rewrapped} resigned={result.resigned} "
        f"batches={result.batches} skipped={len(result.skipped)}"
    )
    for key in result.skipped:
        print(f"skipped {key} unknown_key")
    return 0 if not result.skipped else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser(
        "audit-verify", help="recompute the audit hash chain and report the first break"
    )
    verify.add_argument(
        "--checkpoint",
        type=_parse_checkpoint,
        metavar="SEQ:ROW_HASH_HEX",
        help="an audit.checkpoint line's seq and row_hash; also proves that row exists",
    )
    importer = sub.add_parser(
        "settings-import",
        help="one-time import of known settings from an env file (never overwrites)",
    )
    importer.add_argument("--env-file", required=True, metavar="PATH")
    sub.add_parser(
        "settings-verify",
        help="check every settings signature, the manifest and the audit trail",
    )
    sub.add_parser(
        "rewrap",
        help=f"re-wrap and re-sign settings under the current {MASTER_KEY_KEY} "
        f"(rotation: set {MASTER_KEY_PREVIOUS_KEY} to the old key first)",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "audit-verify":
            return asyncio.run(_audit_verify(args.checkpoint))
        if args.command == "settings-import":
            return asyncio.run(_settings_import(args.env_file))
        if args.command == "settings-verify":
            return asyncio.run(_settings_verify())
        return asyncio.run(_rewrap())
    except (AdminConfigError, MasterKeyError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - class name only: messages may carry the DSN
        detail = getattr(exc, "code", "")
        print(
            f"{args.command} failed: {type(exc).__name__}" + (f" {detail}" if detail else ""),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
