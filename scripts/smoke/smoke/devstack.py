"""Prepare a LOCAL stack for a dry run (never production):

    uv run python -m smoke.devstack --api http://localhost:8000/api/v1 \\
        --mailpit http://localhost:8025 --origin http://localhost:3000 \\
        --env-file .smoke-dry-run.env

Signs the workspace owner in with a code read from the stack's Mailpit (the
owner's workspace is created on that first sign-in), creates an API key with
the scopes the suite needs and writes SMOKE_API_KEY, SMOKE_WORKSPACE_ID (the
workspace's id) and SMOKE_WORKSPACE_NAME to ``--env-file`` (mode 600). Prints
nothing secret.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from smoke.checks import is_local
from smoke.config import MAILPIT, MailboxSettings
from smoke.mailbox import MailpitMailbox
from smoke.redact import Redactor

SCOPES = [
    "forms:read",
    "forms:write",
    "forms:delete",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m smoke.devstack")
    parser.add_argument("--api", required=True)
    parser.add_argument("--mailpit", required=True)
    parser.add_argument("--origin", required=True, help="the web app's origin")
    parser.add_argument("--owner", default="smoke-owner@example.com")
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args(argv)
    if not (is_local(args.api) and is_local(args.mailpit)):
        print("devstack prepares a local stack only", file=sys.stderr)
        return 2

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(method: str, path: str, body=None):
        request = urllib.request.Request(
            args.api.rstrip("/") + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Content-Type": "application/json", "Origin": args.origin},
        )
        with opener.open(request, timeout=60) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    mailbox = MailpitMailbox(
        MailboxSettings(kind=MAILPIT, address=args.owner, mailpit_url=args.mailpit),
        Redactor(),
    )
    mailbox.cleanup(args.owner)  # older codes would be read first
    asked_at = dt.datetime.now(dt.timezone.utc)
    query = urllib.parse.urlencode({"receiver_email": args.owner})
    call("POST", f"/auth/creator/otp/send?{query}")
    code = mailbox.wait_for_code(args.owner, asked_at, timeout=60)
    call("POST", "/auth/otp/validate", {"email": args.owner, "otp_code": code})
    if not any(c.name == "Authorization" and not c.secure for c in jar):
        # Secure cookies are never sent back over http
        print(
            "the sign-in set no usable session cookie: run the backend with "
            "API_HOST=localhost on a local stack",
            file=sys.stderr,
        )
        return 1
    workspace = call("GET", "/workspaces/mine")[0]
    key = call(
        "POST",
        f"/workspaces/{workspace['id']}/api-keys",
        {"name": "smoke dry run", "scopes": SCOPES, "acknowledgeUnredactedResponses": True},
    )
    args.env_file.write_text(
        f"SMOKE_API_KEY={key['token']}\n"
        f"SMOKE_WORKSPACE_ID={workspace['id']}\n"
        f"SMOKE_WORKSPACE_NAME={workspace['workspaceName']}\n"
    )
    os.chmod(args.env_file, 0o600)
    print(f"local workspace {workspace['id']} and an API key are ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
