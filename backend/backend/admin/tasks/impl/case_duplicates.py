"""``auth.resolve_case_duplicate_accounts`` (metadata and rules:
``catalog/case_duplicates.py``).

The runner holds no access to the accounts, workspaces or forms for this
task. It calls the API's internal admin-task routes
(``backend/app/controllers/admin_tasks_router.py``) at
``ADMIN_TASKS_BACKEND_URL`` with ``ADMIN_TASKS_API_KEY``:

* ``GET  .../case-duplicate-accounts``: the groups with each account's id,
  created time, forms count and decision, evaluated by the API now;
* ``POST .../case-duplicate-accounts/{id}/drop``: the API evaluates the
  account's group again and, only if the rules still drop it, starts the
  product's account deletion (the workflow a user's own deletion takes), which
  removes the account in every store the services write.

So the decision is never the runner's, and a change since the dry run is
honoured. After the drops, the task polls the groups until the started
deletions are done (or :data:`WAIT_SECONDS` pass) and reports what remains.

Ids and counts only, in the result, the events and the audit log: the API
never sends an email to the runner.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from backend.admin.tasks.catalog import case_duplicates as catalog
from backend.admin.tasks.catalog.case_duplicates import Events
from backend.admin.tasks.spec import Refusal

URL_ENV = "ADMIN_TASKS_BACKEND_URL"
KEY_ENV = "ADMIN_TASKS_API_KEY"
DEFAULT_URL = "http://backend:8001/api/v1"
KEY_HEADER = "X-Admin-Tasks-Key"
ROUTE = "/internal/admin-tasks/case-duplicate-accounts"
AUDIT_ACTION = "task.accounts.case_duplicates_resolved"
TARGET_TYPE = "accounts"
# how long the apply waits for the started deletions (jobs) to finish
WAIT_SECONDS = 600
POLL_SECONDS = 5
TIMEOUT_SECONDS = 120
OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")
DECISIONS = ("keep", "drop", "manual")
# what POST .../drop answers, and how the task counts it
STARTED = {"queued": "drops_started", "already_queued": "already_running"}
SKIPPED = {
    "kept": "changed",
    "manual": "changed",
    "not_found": "changed",
    "refused": "refused",
}

# tests replace it with an in-process transport
transport: Optional[httpx.AsyncBaseTransport] = None


class Backend:
    def __init__(self, url: str, key: str):
        self._client = httpx.AsyncClient(
            base_url=url.rstrip("/") + ROUTE,
            headers={KEY_HEADER: key},
            timeout=TIMEOUT_SECONDS,
            transport=transport,
            follow_redirects=False,
        )

    async def __aenter__(self) -> "Backend":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str) -> dict:
        try:
            reply = await self._client.request(method, path)
        except httpx.HTTPError:
            raise Refusal("backend_unreachable") from None
        if reply.status_code == 503:
            raise Refusal("backend_key_missing")
        if reply.status_code in (401, 403):
            raise Refusal("backend_key_refused")
        if reply.status_code != 200:
            raise Refusal("backend_unreachable")
        try:
            return reply.json()
        except ValueError:
            raise Refusal("backend_unreachable") from None

    async def groups(self) -> List[List[dict]]:
        groups = (await self._call("GET", "")).get("groups") or []
        return [_valid_group(group) for group in groups]

    async def drop(self, account_id: str) -> str:
        return str((await self._call("POST", f"/{account_id}/drop")).get("status"))


def _valid_group(group) -> List[dict]:
    """Only well-formed ids, integer counts and known decisions are used: the
    reply cannot carry anything else into an event."""
    out = []
    for account in group:
        account_id = str(account.get("id"))
        decision = account.get("decision")
        forms = account.get("forms")
        if (
            not OBJECT_ID.match(account_id)
            or decision not in DECISIONS
            or isinstance(forms, bool)
            or not isinstance(forms, int)
        ):
            raise Refusal("backend_unreachable")
        out.append({"id": account_id, "forms": forms, "decision": decision})
    return out


def _created(account_id: str) -> str:
    """The account's creation time: its ObjectId's timestamp, as an event id."""
    seconds = int(account_id[:8], 16)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config() -> tuple:
    url = (os.environ.get(URL_ENV) or DEFAULT_URL).strip()
    key = (os.environ.get(KEY_ENV) or "").strip()
    if not key or not url.startswith(("http://", "https://")):
        raise Refusal("backend_not_configured")
    return url, key


def _totals(groups: List[List[dict]]) -> Dict[str, int]:
    accounts = [a for group in groups for a in group]
    totals = {d: sum(a["decision"] == d for a in accounts) for d in DECISIONS}
    return {
        "groups": len(groups),
        "accounts": len(accounts),
        **totals,
        "manual_groups": sum(any(a["decision"] == "manual" for a in g) for g in groups),
    }


async def _list(ctx, groups: List[List[dict]]) -> None:
    """One event per account, numbered by group (Group 1, 2, ...)."""
    for number, group in enumerate(groups, start=1):
        for account in group:
            await ctx.emit(
                Events(account["decision"]),
                {"group": number, "forms": account["forms"]},
                [account["id"], _created(account["id"])],
            )


class ResolveCaseDuplicateAccounts:
    META = catalog.META

    async def precheck(self, ctx, params: catalog.ResolveParams) -> None:
        url, key = _config()
        async with Backend(url, key) as backend:
            await backend.groups()

    async def run(self, ctx, params: catalog.ResolveParams) -> catalog.ResolveResult:
        url, key = _config()
        async with Backend(url, key) as backend:
            groups = await backend.groups()
            await _list(ctx, groups)
            totals = _totals(groups)
            await ctx.emit(Events.counted, totals)
            if ctx.dry_run:
                return catalog.ResolveResult(**totals)

            outcome = {"drops_started": 0, "already_running": 0, "changed": 0, "refused": 0}
            started: List[str] = []
            drops = [a["id"] for g in groups for a in g if a["decision"] == "drop"]
            for done, account_id in enumerate(drops, start=1):
                status = await backend.drop(account_id)
                counter = STARTED.get(status) or SKIPPED.get(status, "changed")
                outcome[counter] += 1
                if status in STARTED:
                    started.append(account_id)
                    await ctx.emit(Events.drop_started, None, [account_id, status])
                else:
                    # the status is one of a fixed set; anything else is "changed"
                    shown = status if status in SKIPPED else "changed"
                    await ctx.emit(Events.drop_skipped, None, [account_id, shown])
                await ctx.progress(done, len(drops))

            # wait for the deletion jobs: an account is gone once no group names it
            remaining = await backend.groups()
            deadline = time.monotonic() + WAIT_SECONDS
            while started and time.monotonic() < deadline and not await ctx.cancelled():
                left = {a["id"] for g in remaining for a in g}
                if not left.intersection(started):
                    break
                await asyncio.sleep(POLL_SECONDS)
                remaining = await backend.groups()
            left = {a["id"] for g in remaining for a in g}
            pending = len(left.intersection(started))
            for group in remaining:
                await ctx.emit(
                    Events.remaining,
                    {"accounts": len(group)},
                    [a["id"] for a in group][:20],
                )
            after = {
                "pending": pending,
                "remaining_groups": len(remaining),
                "remaining_manual_groups": _totals(remaining)["manual_groups"],
            }
            await ctx.audit(
                AUDIT_ACTION,
                target_type=TARGET_TYPE,
                target_id="case_duplicates",
                detail={**totals, **outcome, **after},
            )
            return catalog.ResolveResult(**totals, **outcome, **after)
