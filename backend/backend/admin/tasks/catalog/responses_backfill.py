"""``responses.backfill_workspaces``: stamp stored responses and deletion requests
with the workspace they belong to. Never guesses: ambiguous records stay
unstamped."""

import enum
from typing import Annotated, Optional

from pydantic import Field

from backend.admin.tasks.catalog.responses_common import Refusals, StoreChoice
from backend.admin.tasks.spec import Id, Params, Result, TaskMeta


class Events(str, enum.Enum):
    backfilled_mongo = "backfilled_mongo"
    backfilled_postgres = "backfilled_postgres"


class BackfillParams(Params):
    stores: StoreChoice = StoreChoice.auto
    batch_size: Annotated[int, Field(ge=100, le=1000)] = 500
    # only records of forms linked to this workspace
    workspace_id: Optional[Id] = None
    # only records of these forms (together with workspace_id: both must hold)
    form_ids: Optional[Annotated[list[Id], Field(min_length=1, max_length=100)]] = None


class Buckets(Result):
    unstamped: int = 0
    single_workspace: int = 0
    attributed_by_encryption: int = 0
    from_response: int = 0
    ambiguous: int = 0
    orphaned: int = 0
    stamped: int = 0
    # a copy of the record is already stamped with that workspace: skipped
    conflict: int = 0


class StoreBackfill(Result):
    forms_linked_to_several_workspaces: int = 0
    responses: Buckets = Buckets()
    deletion_requests: Buckets = Buckets()


class BackfillResult(Result):
    complete: bool
    mongo: Optional[StoreBackfill] = None
    postgres: Optional[StoreBackfill] = None


META = TaskMeta(
    name="responses.backfill_workspaces",
    version=1,
    params=BackfillParams,
    result=BackfillResult,
    events=Events,
    mutating=True,
    resources=("responses.stamping",),
    resumable=True,
    requires_prior_dry_run=True,
    title="Stamp responses with their workspace",
    refusals=Refusals,
    idempotent=True,
)
