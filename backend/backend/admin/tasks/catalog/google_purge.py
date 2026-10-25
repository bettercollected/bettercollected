"""``google.purge_unencrypted_credentials``: delete the Google Forms integration's
stored credentials that have no user id, or whose tokens are stored readable.

The one-time cleanup of docs/postgres-cutover-runbook.md ("Google credentials
without a user id") as a task, with exactly the runbook's filters:

* Postgres ``google.oauth_credentials``: ``user_id`` empty or null, or
  ``doc.credentials`` a JSON object without ``$binary``.

A dry run (required first) counts; the apply deletes and records the counts in
the audit log. Mongo is not touched since 4.1: ``mongo`` and ``both`` refuse
``store_retired``, and an apply refuses ``import_incomplete`` until the import
from 4.0 is over (the runner has no Mongo connection and nothing unfinished is
recorded in ``migration_progress``): running the import again would copy the
rows still held in Mongo back. No manual step is needed once it is over. Counts only: never an id, an email or a token. Running
it again deletes nothing.
"""

import enum
from typing import Optional

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Params, Result, TaskMeta


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    store_retired = "store_retired"
    store_unreachable = "store_unreachable"
    # the Postgres function (postgres/ensure-admin-roles.sh) is missing, or the
    # runner's role may not execute it
    purge_function_missing = "purge_function_missing"
    # kept for runs made before this refusal was replaced by import_incomplete
    stores_incomplete = "stores_incomplete"
    # an apply while the import from 4.0 is not over (a Mongo connection on the
    # runner, or an unfinished backfill in migration_progress): a later backfill
    # would copy the rows back
    import_incomplete = "import_incomplete"


class Events(str, enum.Enum):
    counted = "counted"
    purged = "purged"


class PurgeParams(Params):
    stores: StoreChoice = StoreChoice.postgres


class StorePurge(Result):
    # rows matching the filter when the store was visited
    matched: int = 0
    # rows deleted (always 0 for a dry run)
    deleted: int = 0


class PurgeResult(Result):
    mongo: Optional[StorePurge] = None  # runs made before 4.1 only
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
