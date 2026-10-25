"""``google.purge_unencrypted_credentials``: delete the Google Forms integration's
stored credentials that have no user id, or whose tokens are stored readable.

The one-time cleanup of docs/postgres-cutover-runbook.md ("Google credentials
without a user id") as a task, with exactly the runbook's filters:

* Mongo ``Oauth2CredentialDocument``: ``user_id`` missing, null or empty, or
  ``credentials.token`` / ``credentials.refresh_token`` present;
* Postgres ``google.oauth_credentials``: ``user_id`` empty or null, or
  ``doc.credentials`` a JSON object without ``$binary``.

A dry run (required first) counts per store; the apply deletes, Mongo first and
then Postgres, so neither store copies a row back to the other, and records the
counts in the audit log. Counts only: never an id, an email or a token. Running
it again deletes nothing.
"""

import enum
from typing import Optional

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Params, Result, TaskMeta


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    write_mode_unknown = "write_mode_unknown"
    store_unreachable = "store_unreachable"
    # the Postgres function (postgres/ensure-admin-roles.sh) is missing, or the
    # runner's role may not execute it
    purge_function_missing = "purge_function_missing"


class Events(str, enum.Enum):
    counted = "counted"
    purged = "purged"


class PurgeParams(Params):
    stores: StoreChoice = StoreChoice.auto


class StorePurge(Result):
    # rows matching the filter when the store was visited
    matched: int = 0
    # rows deleted (always 0 for a dry run)
    deleted: int = 0


class PurgeResult(Result):
    mongo: Optional[StorePurge] = None
    postgres: Optional[StorePurge] = None
    matched: int = 0
    deleted: int = 0


META = TaskMeta(
    name="google.purge_unencrypted_credentials",
    version=1,
    params=PurgeParams,
    result=PurgeResult,
    events=Events,
    mutating=True,
    requires_prior_dry_run=True,
    title="Delete Google credentials without a user id or stored readable",
    refusals=Refusals,
    idempotent=True,
)
