"""Operator CLI: ``python -m backend.admin <command>``.

Prints counts and sequence numbers only, never row contents.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional, Sequence

from backend.admin.config import AdminConfigError, AdminSettings
from backend.admin.db import make_engine
from backend.admin.services import audit


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
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_audit_verify(args.checkpoint))
    except AdminConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - class name only: messages may carry the DSN
        print(f"audit-verify failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
