"""``auth.resolve_case_duplicate_accounts``: resolve the accounts whose emails
are equal ignoring case, which 4.1's auth (unique ``lower(email)``) refuses to
run with.

For each group of such accounts (the API decides, on every call; see
``backend/app/services/case_duplicate_accounts.py``):

1. an account without forms is dropped;
2. if exactly one account has forms, it is kept;
3. if none has forms, the one created last is kept (the ObjectId timestamp);
4. if two or more have forms, those are left for manual handling, and the
   formless ones in the group are still dropped.

A dry run (required first) lists every group (``Group 1, 2, ...``) as events:
each account's id, created time, forms count and decision. The apply drops
each "drop" account through the product's account deletion (the same
workflow as a user's own request), re-evaluated by the API right before, waits
for the deletions to finish, then reports the groups that remain. Ids and
counts only: never an email.
"""

import enum

from backend.admin.tasks.spec import Params, Result, TaskMeta


class Refusals(str, enum.Enum):
    # ADMIN_TASKS_API_KEY or ADMIN_TASKS_BACKEND_URL missing on the runner
    backend_not_configured = "backend_not_configured"
    # no connection to the API, or it timed out (ADMIN_TASKS_BACKEND_URL,
    # the backend service down)
    backend_unreachable = "backend_unreachable"
    # the API has no ADMIN_TASKS_API_KEY (503) or refused the runner's (401/403)
    backend_key_missing = "backend_key_missing"
    backend_key_refused = "backend_key_refused"
    # the API has no such route (404): usually a backend older than this task
    backend_route_missing = "backend_route_missing"
    # the API answered with a redirect (3xx, never followed): the URL or the
    # path the runner requests is not the route's exact one
    backend_redirect = "backend_redirect"
    # the API answered 5xx or another unexpected status
    backend_error = "backend_error"
    # the API answered 200 with a body that is not the expected JSON
    backend_bad_reply = "backend_bad_reply"
    # the API's call to the auth service failed (the API answered 502 with
    # its code): no connection to auth; auth refused the API's
    # AUTH_INTERNAL_NOTIFY_KEY (401/403, the two services' keys differ); or
    # auth answered another error
    auth_unreachable = "auth_unreachable"
    auth_key_refused = "auth_key_refused"
    auth_error = "auth_error"


class Events(str, enum.Enum):
    # dry run and apply: one per account; counts group / forms, ids
    # [account id, created time]
    keep = "keep"
    drop = "drop"
    manual = "manual"
    # apply: the outcome of one drop, ids [account id, outcome]
    drop_started = "drop_started"
    drop_skipped = "drop_skipped"
    # apply: what remains afterwards, one per remaining group (ids: its accounts)
    remaining = "remaining"
    # the totals (both)
    counted = "counted"


class ResolveParams(Params):
    pass


class ResolveResult(Result):
    groups: int = 0
    accounts: int = 0
    keep: int = 0
    drop: int = 0
    manual: int = 0
    # groups with two or more accounts with forms (the owner's to handle)
    manual_groups: int = 0
    # apply only
    drops_started: int = 0
    already_running: int = 0
    # the rules no longer dropped the account when it came to it
    changed: int = 0
    # the account deletion refused (e.g. billing owner of a shared workspace)
    refused: int = 0
    # deletions still running when the task stopped waiting
    pending: int = 0
    remaining_groups: int = 0
    remaining_manual_groups: int = 0


META = TaskMeta(
    name="auth.resolve_case_duplicate_accounts",
    version=1,
    params=ResolveParams,
    result=ResolveResult,
    events=Events,
    mutating=True,
    requires_prior_dry_run=True,
    title="Resolve accounts whose emails differ only in case",
    refusals=Refusals,
    idempotent=True,
)
