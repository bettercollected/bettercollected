"""Operator CLI: ``python -m backend.admin <command>``.

Prints counts and sequence numbers only, never row contents.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional, Sequence

from backend.admin.config import AdminConfigError, AdminSettings
from common.settings.crypto.keys import MasterKeyError
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


async def _with_portal(action):
    """Run ``action(portal)`` with the services the web app uses."""
    from backend.admin.portal import Portal

    engine = make_engine(AdminSettings.from_env())
    try:
        return await action(Portal.build(engine))
    finally:
        await engine.dispose()


async def _unlock(email: str) -> int:
    async def run(portal):
        await portal.limiter.unlock(email)
        async with portal.engine.begin() as conn:
            await audit.write(
                conn, "cli.unlock", "account", None, None, None, "success",
                actor_kind="cli", detail={"account_len": len(email)},
            )

    await _with_portal(run)
    print("unlocked")
    return 0


async def _resume() -> int:
    async def run(portal):
        await portal.limiter.resume_sign_in()
        async with portal.engine.begin() as conn:
            await audit.write(
                conn, "cli.resume_sign_in", "service", None, None, None, "success",
                actor_kind="cli",
            )

    await _with_portal(run)
    print("sign-in resumed")
    return 0


async def _revoke_sessions(email: Optional[str]) -> int:
    async def run(portal):
        if email:
            return await portal.sessions.revoke_all(
                email, by="cli", reason="cli_revoke", actor_kind="cli"
            )
        return await portal.sessions.revoke_everyone()

    count = await _with_portal(run)
    print(f"revoked {count} session(s)")
    return 0


def _os_user() -> str:
    import getpass
    import os

    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - a container user without a passwd entry
        return f"uid{os.getuid()}"


async def _reset_factor(email: str) -> int:
    from backend.admin.portal_config import parse_admin_emails, ADMIN_EMAILS_KEY
    import os

    address = email.strip().lower()
    if address not in parse_admin_emails(os.environ.get(ADMIN_EMAILS_KEY)):
        print("refused: that address is not in PLATFORM_ADMIN_EMAILS", file=sys.stderr)
        return 2

    async def run(portal):
        result = await portal.factors.reset_factor(address, _os_user())
        for job in result.after:  # mail every admin; a mail failure is logged, not fatal
            await job()

    await _with_portal(run)
    print("second factor removed; sessions revoked; re-enrolment is required at the next sign-in")
    return 0


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
    unlock = sub.add_parser("unlock", help="clear failures and the lockout of one admin email")
    unlock.add_argument("email")
    sub.add_parser("resume-sign-in", help="lift the global sign-in pause now")
    revoke = sub.add_parser(
        "revoke-sessions", help="revoke the live sessions of one email, or of everyone"
    )
    revoke.add_argument("email", nargs="?")
    reset = sub.add_parser(
        "reset-factor",
        help="remove an admin's second factor and recovery codes (lost device and codes)",
    )
    reset.add_argument("--email", required=True)
    reset.add_argument("--yes", action="store_true", help="confirm; nothing happens without it")
    args = parser.parse_args(argv)
    try:
        if args.command == "reset-factor":
            if not args.yes:
                print("refused: pass --yes to confirm the reset", file=sys.stderr)
                return 2
            return asyncio.run(_reset_factor(args.email))
        if args.command == "unlock":
            return asyncio.run(_unlock(args.email))
        if args.command == "resume-sign-in":
            return asyncio.run(_resume())
        if args.command == "revoke-sessions":
            return asyncio.run(_revoke_sessions(args.email))
        return asyncio.run(_audit_verify(args.checkpoint))
    except (AdminConfigError, MasterKeyError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - class name only: messages may carry the DSN
        print(f"{args.command} failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
