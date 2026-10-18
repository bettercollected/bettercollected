"""``responses.check_undecryptable``: count stored response values that carry the
ciphertext prefix but do not decrypt. Read-only; counts only."""

import enum
from typing import Annotated, Optional

from pydantic import Field

from backend.admin.tasks.catalog.responses_common import Refusals, StoreChoice
from backend.admin.tasks.spec import Params, Result, TaskMeta


class Events(str, enum.Enum):
    scanned_mongo = "scanned_mongo"
    scanned_postgres = "scanned_postgres"


class CheckParams(Params):
    stores: StoreChoice = StoreChoice.auto
    batch_size: Annotated[int, Field(ge=100, le=1000)] = 500


class FieldTally(Result):
    prefixed: int = 0
    decrypts: int = 0
    does_not_decrypt: int = 0
    of_which_text: int = 0
    of_which_binary: int = 0
    no_workspace_to_try: int = 0


class StoreScan(Result):
    responses: int = 0
    does_not_decrypt: int = 0
    answers: FieldTally = FieldTally()
    hidden_fields: FieldTally = FieldTally()
    internal_answers: FieldTally = FieldTally()
    feedback_message: FieldTally = FieldTally()


class CheckResult(Result):
    complete: bool
    mongo: Optional[StoreScan] = None
    postgres: Optional[StoreScan] = None


META = TaskMeta(
    name="responses.check_undecryptable",
    version=1,
    params=CheckParams,
    result=CheckResult,
    events=Events,
    mutating=False,
    resumable=False,
    title="Check for undecryptable response values",
    refusals=Refusals,
)
