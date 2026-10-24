"""``responses.purge_orphaned_forms``: delete the forms that belong to no
workspace, with their responses, deletion requests, versions and responder-group
links, in every store the task covers.

Older code removed a form's last workspace link without deleting the form, so
such forms and their responses stayed behind. Nobody can show or decrypt those
responses (their encryption context is the workspace, which is unknown), and
they keep an old response key in use. Current code deletes a form's responses
when it leaves its last workspace, so no new ones appear.

A form is in scope only if all hold, evaluated at run time:

* no workspace link in any configured store (Mongo and Postgres);
* it has responses, and none of them carries a workspace (in any configured
  store): a stamped response means a workspace holds it;
* with ``newest_response_before``: its newest response was stored before that
  date (the date in the response's id).

An apply run deletes only when the forms and responses it finds equal
``expected_forms`` and ``expected_responses``, copied from the dry run.
"""

import datetime as dt
import enum
from typing import Annotated, Optional

from pydantic import Field

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Id, Params, Result, TaskMeta


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    write_mode_unknown = "write_mode_unknown"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    # an apply run without expected_forms and expected_responses
    expected_counts_missing = "expected_counts_missing"
    # what the run finds is not what the operator confirmed
    expected_counts_mismatch = "expected_counts_mismatch"
    # the stores hold different numbers of the forms' responses
    stores_disagree = "stores_disagree"


class Events(str, enum.Enum):
    orphans_found = "orphans_found"
    purged_batch = "purged_batch"
    skipped_changed = "skipped_changed"
    purged_mongo = "purged_mongo"
    purged_postgres = "purged_postgres"


class PurgeParams(Params):
    stores: StoreChoice = StoreChoice.auto
    # only forms whose newest response was stored before this date (UTC)
    newest_response_before: Optional[dt.date] = None
    # required for an apply run: the dry run's ``forms`` and ``responses``
    expected_forms: Optional[Annotated[int, Field(ge=0, le=1_000_000)]] = None
    expected_responses: Optional[Annotated[int, Field(ge=0, le=100_000_000)]] = None
    forms_per_batch: Annotated[int, Field(ge=1, le=20)] = 10


class StorePurge(Result):
    """Records of the forms in scope in one store: counted by a dry run,
    deleted by an apply run."""

    # form documents (a form in scope may have lost its document already)
    form_documents: int = 0
    responses: int = 0
    deletion_requests: int = 0
    versions: int = 0
    group_links: int = 0


class PurgeResult(Result):
    complete: bool
    # the forms in scope and their responses (in the first store covered)
    forms: int = 0
    responses: int = 0
    # forms with no workspace link but a response that carries a workspace
    skipped_stamped: int = 0
    # forms left out by newest_response_before
    skipped_newer: int = 0
    # forms that gained a link or a stamped response before their batch ran
    skipped_changed: int = 0
    stores_agree: bool = True
    # a dry run given expected counts: whether they match what it found
    expected_counts_match: Optional[bool] = None
    # dates (YYYY-MM-DD, UTC) the responses in scope were stored
    oldest_response: Optional[Id] = None
    newest_response: Optional[Id] = None
    mongo: Optional[StorePurge] = None
    postgres: Optional[StorePurge] = None


META = TaskMeta(
    name="responses.purge_orphaned_forms",
    version=1,
    params=PurgeParams,
    result=PurgeResult,
    events=Events,
    mutating=True,
    resources=("responses.purge",),
    resumable=True,
    requires_prior_dry_run=True,
    title="Delete forms in no workspace, with their responses",
    refusals=Refusals,
    idempotent=True,
)
