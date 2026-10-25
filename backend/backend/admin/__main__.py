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


def format_fingerprint(raw: str) -> str:
    """The master key's short id in groups of four (``abcd-ef01-2345``)."""
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


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
    print(f"master_key_fingerprint {format_fingerprint(service.keys.fingerprint)}")
    return 0 if not problems else 1


def _fingerprint() -> int:
    """Offline: needs only the master key, not the database."""
    from common.settings.keys import SectionKeys

    master = parse_master_key(os.environ.get(MASTER_KEY_KEY))
    print(f"master_key_fingerprint {format_fingerprint(SectionKeys(master, sections=()).fingerprint)}")
    return 0


# ------------------------------------------------------------- host commands


def _host():
    from backend.admin.services import host_settings

    return host_settings


def _refuse(error) -> int:
    print(f"refused: {error.code}" + (f" {error.hint}" if error.hint else ""), file=sys.stderr)
    return 1


def _read_stdin(limit: int = 8 * 1024 * 1024) -> str:
    data = sys.stdin.read(limit + 1)
    if len(data) > limit:
        host = _host()
        raise host.HostError("input_too_large")
    return data


def _sources(from_compose: bool, env_file: Optional[str]) -> dict[str, dict[str, str]]:
    host = _host()
    if from_compose:
        return host.parse_compose_config(_read_stdin())
    if env_file is None:
        raise host.HostError("no_source", "pass --from-compose-config or --env-file")
    return {host.ENV_SOURCE: read_env_file(env_file)}


def _print_counts(counts: dict) -> None:
    print(" ".join(f"{k}={v}" for k, v in counts.items()))


async def _import_plan(args) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    sources = _sources(args.from_compose_config, args.env_file)
    service = _service(settings)
    try:
        plan = await host.plan_import(service, sources, prefer=args.prefer)
        result = None
        if not args.dry_run:
            result = await host.import_config(service, plan, _cli_actor())
    finally:
        await service._engine.dispose()
    _print_counts(plan.counts())
    if result is None:
        for key in sorted(plan.would_import):
            print(f"would_import {key}")
    else:
        for key in result.imported:
            print(f"imported {key}")
    for key, sources_ in sorted(plan.conflict.items()):
        print(f"conflict {key} {','.join(sources_)}")
    refused = list(plan.refused) + (result.refused if result else [])
    for key, reason in sorted(refused):
        print(f"refused {key} {reason}")
    if plan.conflict:
        print("conflicts are imported neither way: pass --prefer SERVICE to choose")
    return 0 if not refused and not plan.conflict else 1


async def _settings_drift(args) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    sources = _sources(args.from_compose_config, args.env_file)
    service = _service(settings)
    try:
        report = await host.plan_drift(service, sources)
    finally:
        await service._engine.dispose()
    _print_counts(report.counts())
    for key, who in sorted(report.differs.items()):
        print(f"differs {key} {','.join(who)}")
    for label in ("env_only", "store_only", "unverified"):
        for key in sorted(getattr(report, label)):
            print(f"{label} {key}")
    if report.differs:
        print("an environment value wins over the store: fix or prune the differing keys")
    return 0 if report.clean else 1


async def _settings_prune(args) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        reports = await host.prune_env_files(
            service, args.env_file, apply=args.apply, swap=args.swap,
            keep=args.keep or (), actor=_cli_actor(),
        )
    finally:
        await service._engine.dispose()
    refused = 0
    for report in reports:
        print(
            f"{report.file}: prune={len(report.pruned)} keep={report.kept} "
            f"differs={len(report.refused)}"
        )
        for name in report.pruned:
            print(f"  {'pruned' if args.apply else 'would_prune'} {name}")
        for name in sorted(report.refused):
            print(f"  refused {name} differs")
        for name in report.interpolated:
            print(f"  kept {name} interpolated")
        refused += len(report.refused)
    if args.apply and any(r.pruned for r in reports):
        print(
            "backups (.pre-v4.*) hold the old secret values: keep them private and delete them "
            "once the stack runs well"
        )
        if not args.swap:
            print("the pruned copies are next to the originals (.pruned): move them into place")
    if not args.apply:
        print("dry run: nothing written (pass --apply)")
    return 1 if refused else 0


async def _settings_env_export(keys: Sequence[str], out: str) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        count = await host.export_env(service, keys, out, _cli_actor())
    finally:
        await service._engine.dispose()
    print(f"exported={count} file={os.path.basename(out)} mode=600")
    print("the file holds secret values in clear text: delete it when the break-glass is over")
    return 0


async def _settings_set(key: str, use_stdin: bool, value: Optional[str], confirm: Optional[str]) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        spec = service.registry.get(key) if key in service.registry else None
        if spec is not None and spec.is_secret and value is not None:
            print("refused: pass a secret on standard input (--stdin), never as an argument", file=sys.stderr)
            return 2
        raw = host.parse_set_value(_read_stdin(65536)) if use_stdin else value
        change = await host.set_value(service, key, raw, _cli_actor(), confirmation=confirm)
    finally:
        await service._engine.dispose()
    print(f"set {key} version={change.version} changed={'yes' if change.changed else 'no'}")
    return 0


async def _settings_clear(key: str, confirm: Optional[str]) -> int:
    """Clears KEY in the store: its versions are kept (``settings-restore``
    brings a value back), the services read it as unset."""
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        change = await host.clear_value(service, key, _cli_actor(), confirmation=confirm)
    finally:
        await service._engine.dispose()
    print(f"cleared {key} version={change.version}")
    return 0


async def _settings_restore(key: str, version: int, confirm: Optional[str]) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings, with_previous=True)
    try:
        change = await host.restore_version(service, key, version, _cli_actor(), confirmation=confirm)
    finally:
        await service._engine.dispose()
    print(f"restored {key} version={change.version}")
    return 0


async def _settings_history(key: str) -> int:
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        rows = await service.history(key)
    finally:
        await service._engine.dispose()
    for row in rows:
        print(f"{key} version={row.version} action={row.action}{' cleared' if row.cleared else ''}")
    print(f"versions={len(rows)}")
    return 0


async def _bootstrap_keys(args) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    service = _service(settings)
    try:
        result = None
        if not args.export_worker_only:
            result = await host.bootstrap_keys(
                service, _cli_actor(), environ=os.environ,
                existing_stack=args.existing_stack, fill_missing=args.fill_missing,
            )
        if args.export_worker:
            await host.export_worker(service, args.export_worker, _cli_actor())
    finally:
        await service._engine.dispose()
    if result is not None:
        print(f"generated={len(result.generated)} (values are not shown)")
        for key in result.generated:
            print(f"generated {key}")
    if args.export_worker:
        print(f"worker_keys_written file={os.path.basename(args.export_worker)} mode=600")
    if result is not None and result.keyset_fp:
        print(f"keyset_fingerprint {result.keyset_fp}")
    print(f"master_key_fingerprint {format_fingerprint(service.keys.fingerprint)}")
    print("back up SETTINGS_MASTER_KEY now: without it the stored secrets cannot be recovered")
    return 0


def _mail_config(candidate: dict):
    from backend.admin.security.mailer import MailConfig

    def get(name, default):
        return candidate.get(f"ADMIN_MAIL_{name}", default)

    return MailConfig(
        user=get("USER", ""),
        password=get("PASSWORD", ""),
        smtp_server=get("SMTP_SERVER", ""),
        smtp_port=int(get("SMTP_PORT", 587)),
        sender=get("SENDER", ""),
        starttls=bool(get("STARTTLS", True)),
        ssl_tls=bool(get("SSL_TLS", False)),
        use_credentials=bool(get("USE_CREDENTIALS", True)),
        validate_certs=bool(get("VALIDATE_CERTS", True)),
    )


async def _send_test_mail(config, to: str, subject: str, body: str) -> None:
    from backend.admin.security.mailer import FastMailTransport

    if not config.configured:
        raise RuntimeError("mail is not configured")
    await FastMailTransport(config).send(to, subject, body)


async def _settings_mail_apply(env_file: str, test_to: str) -> int:
    host = _host()
    settings = AdminSettings.from_env()
    pairs = read_env_file(env_file)
    service = _service(settings)

    def ask() -> str:
        print("A test mail was sent. Enter the 6-digit code from it: ", end="", file=sys.stderr, flush=True)
        return sys.stdin.readline()

    try:
        saved = await host.apply_mail(
            service, pairs, _cli_actor(), test_to=test_to,
            send=_send_test_mail, ask_code=ask, config_factory=_mail_config,
        )
    finally:
        await service._engine.dispose()
    print(f"saved={len(saved)}")
    for key in saved:
        print(f"saved {key}")
    return 0


async def _setup_token(new: bool, allow_non_tty: bool) -> int:
    from backend.admin.services import setup_token

    if not (sys.stdout.isatty() or allow_non_tty):
        print(
            "refused: the token is shown on a console only (run this in a terminal); "
            "--allow-non-tty overrides, mind who can read the output",
            file=sys.stderr,
        )
        return 2
    settings = AdminSettings.from_env()
    engine = make_engine(settings)
    try:
        async with engine.begin() as conn:
            token, replaced = await setup_token.issue(
                conn, settings.master_key, _os_user(), replace=new
            )
            await audit.write(
                conn, "cli.setup_token_issue", "setup_token", None, None, None, "success",
                actor_kind="cli",
                detail={"minutes": int(setup_token.TTL.total_seconds() // 60), "replaced": replaced},
            )
    except setup_token.SetupTokenError as exc:
        hints = {
            "setup_closed": "an admin already has a second factor; remove it with reset-factor first",
            "token_active": "a token is already active and cannot be shown again; use --new to replace it",
        }
        print(f"refused: {exc.code} {hints.get(exc.code, '')}".rstrip(), file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print("Setup token (shown once, valid 60 minutes, works once):")
    print(setup_token.display(token))
    return 0


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
    importer = sub.add_parser(
        "settings-import",
        help="one-time import of known settings from an env file (never overwrites)",
    )
    importer.add_argument("--env-file", metavar="PATH")
    importer.add_argument(
        "--from-compose-config",
        action="store_true",
        help="read `docker compose config --format json` on standard input (nothing is written to disk)",
    )
    importer.add_argument("--dry-run", action="store_true", help="show what would be imported; change nothing")
    importer.add_argument(
        "--prefer", metavar="SERVICE", help="compose service whose value settles a conflict"
    )
    bootstrap = sub.add_parser(
        "bootstrap-keys",
        help="generate the stack's own keys into the store (fresh installs; prints no secret)",
    )
    bootstrap.add_argument("--existing-stack", action="store_true", help="the stack already holds data: refuse")
    bootstrap.add_argument("--fill-missing", action="store_true", help="finish an interrupted run: add only missing keys")
    bootstrap.add_argument("--export-worker", metavar="FILE", help="write API_KEY and AES_HEX_KEY (the worker copies) to FILE, mode 600")
    bootstrap.add_argument("--export-worker-only", action="store_true", help="skip generation; only write the worker copies")
    drift = sub.add_parser(
        "settings-drift",
        help="compare compose or env values with the store (equal, differs, env_only, store_only; names only)",
    )
    drift.add_argument("--env-file", metavar="PATH")
    drift.add_argument("--from-compose-config", action="store_true")
    prune = sub.add_parser(
        "settings-prune",
        help="remove from env files the settings the store holds with the same value",
    )
    prune.add_argument("--env-file", action="append", required=True, metavar="PATH")
    prune.add_argument("--apply", action="store_true", help="write FILE.pruned and a backup FILE.pre-v4.<time>")
    prune.add_argument("--swap", action="store_true", help="with --apply: replace the original by the pruned copy")
    prune.add_argument("--keep", action="append", metavar="NAME", help="never prune this name (for example a service outside the store)")
    export = sub.add_parser(
        "settings-env-export",
        help="break-glass: write named settings, with values, to a new private env file",
    )
    export.add_argument("--keys", required=True, metavar="A,B")
    export.add_argument("--out", required=True, metavar="FILE")
    setter = sub.add_parser("settings-set", help="set a setting from the host (tiers T1-T3)")
    setter.add_argument("key")
    group = setter.add_mutually_exclusive_group(required=True)
    group.add_argument("--stdin", action="store_true", help="read the value from standard input")
    group.add_argument("--value", help="the value (not for secrets)")
    setter.add_argument("--confirm", metavar="KEY", help="type the key again to confirm a T3 setting")
    setter.add_argument("--yes", action="store_true")
    clearer = sub.add_parser(
        "settings-clear", help="clear a setting from the host (tiers T1-T3); its versions are kept"
    )
    clearer.add_argument("key")
    clearer.add_argument("--confirm", metavar="KEY", help="type the key again to confirm a T3 setting")
    clearer.add_argument("--yes", action="store_true")
    restorer = sub.add_parser("settings-restore", help="restore a previous version of a setting")
    restorer.add_argument("key")
    restorer.add_argument("--version", type=int, required=True)
    restorer.add_argument("--confirm", metavar="KEY")
    restorer.add_argument("--yes", action="store_true")
    history = sub.add_parser("settings-history", help="the kept versions of a setting (no values)")
    history.add_argument("key")
    mail = sub.add_parser(
        "settings-mail-apply",
        help="save admin sign-in mail settings from an env file after a delivered test mail",
    )
    mail.add_argument("--env-file", required=True, metavar="PATH")
    mail.add_argument("--test-to", required=True, metavar="ADDRESS")
    token = sub.add_parser(
        "setup-token", help="print a one-time first-run setup token on the console (60 minutes)"
    )
    token.add_argument("--new", action="store_true", help="replace the active token")
    token.add_argument("--allow-non-tty", action="store_true")
    sub.add_parser("master-key-fingerprint", help="short id of the master key (offline)")
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
        if args.command == "settings-import":
            if args.from_compose_config or args.dry_run or args.prefer:
                return asyncio.run(_import_plan(args))
            if not args.env_file:
                print("refused: pass --env-file or --from-compose-config", file=sys.stderr)
                return 2
            return asyncio.run(_settings_import(args.env_file))
        if args.command == "settings-verify":
            return asyncio.run(_settings_verify())
        if args.command == "bootstrap-keys":
            return asyncio.run(_bootstrap_keys(args))
        if args.command == "settings-drift":
            return asyncio.run(_settings_drift(args))
        if args.command == "settings-prune":
            return asyncio.run(_settings_prune(args))
        if args.command == "settings-env-export":
            return asyncio.run(
                _settings_env_export([k.strip() for k in args.keys.split(",") if k.strip()], args.out)
            )
        if args.command in ("settings-set", "settings-clear", "settings-restore"):
            if not args.yes:
                print("refused: pass --yes to confirm the change", file=sys.stderr)
                return 2
            if args.command == "settings-set":
                return asyncio.run(_settings_set(args.key, args.stdin, args.value, args.confirm))
            if args.command == "settings-clear":
                return asyncio.run(_settings_clear(args.key, args.confirm))
            return asyncio.run(_settings_restore(args.key, args.version, args.confirm))
        if args.command == "settings-history":
            return asyncio.run(_settings_history(args.key))
        if args.command == "settings-mail-apply":
            return asyncio.run(_settings_mail_apply(args.env_file, args.test_to))
        if args.command == "setup-token":
            return asyncio.run(_setup_token(args.new, args.allow_non_tty))
        if args.command == "master-key-fingerprint":
            return _fingerprint()
        return asyncio.run(_rewrap())
    except (AdminConfigError, MasterKeyError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - HostError and SettingsError carry codes, never values
        from backend.admin.services.host_settings import HostError
        from backend.admin.services.settings_store import SettingsError

        if isinstance(exc, HostError):
            return _refuse(exc)
        if isinstance(exc, SettingsError):
            print(f"refused: {exc.code} {exc.key}".rstrip(), file=sys.stderr)
            return 1
        # class name only: other messages may carry the DSN
        detail = getattr(exc, "code", "")
        print(
            f"{args.command} failed: {type(exc).__name__}" + (f" {detail}" if detail else ""),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
