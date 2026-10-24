"""uv run python -m smoke [--target URL] [--api-url URL] [--report-dir DIR]

Configured from the environment (smoke/config.py, docs/smoke-test.md). Exit
status: 0 every check passed (or was skipped), 1 a check failed, 2 the
configuration is incomplete.

Local dry run (never against production): point --target at a local stack and
read the codes from its Mailpit inbox with --mailpit http://localhost:8025.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from smoke import config as config_module
from smoke.redact import Redactor
from smoke.report import Report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m smoke", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument(
        "--target", help="the web app's base URL (default: SMOKE_APP_URL)"
    )
    parser.add_argument(
        "--api-url",
        help="the API base (default: <target>/api/v1, or as the app calls it)",
    )
    parser.add_argument("--report-dir", default="smoke-report", type=Path)
    parser.add_argument(
        "--mailpit", help="local dry run: read codes from this Mailpit inbox"
    )
    parser.add_argument(
        "--debug-dir",
        type=Path,
        help="local dry run: write page snapshots (redacted) here when a flow fails",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    redactor = Redactor()
    try:
        config = config_module.load(
            target=args.target, api_url=args.api_url, mailpit_url=args.mailpit
        )
    except config_module.ConfigError as error:
        report = Report(redactor, args.target or "(unset)", "-")
        with report.check("-", "Configuration") as c:
            c.fail(str(error))
        report.write(args.report_dir)
        print(redactor.scrub(f"configuration: {error}"), file=sys.stderr)
        return 2
    for value in config.secrets():
        redactor.add(value)
    redactor.add(config.run_address)
    if args.debug_dir and not args.mailpit:
        print(
            "--debug-dir is for local dry runs (with --mailpit) only", file=sys.stderr
        )
        return 2

    # imported here: the configuration errors above need no browser
    from playwright.sync_api import sync_playwright

    from smoke.checks import Suite
    from smoke.mailbox import open_mailbox

    report = Report(redactor, config.app_url, config.run_tag)
    mailbox = open_mailbox(config.mailbox, redactor)
    try:
        with sync_playwright() as playwright:
            Suite(config, report, mailbox, playwright, args.debug_dir).run()
    finally:
        mailbox.close()
        report.write(args.report_dir)
    print(report.markdown())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
