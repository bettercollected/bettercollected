"""One entry of the revision log of a response (``services/response_revisions``).

An edit of a response, by staff or by the respondent: who, when, which
questions changed, and the values they had before, sealed with the response
keyset (``previous_values``, bound to the workspace and the form like the
answers). The entry is deleted with its response (``ON DELETE CASCADE``,
revision 0032). The time of the edit is ``created_at``.
"""

import enum
from dataclasses import dataclass
from typing import Any, List, Optional

from common.records import Record
from pydantic import BaseModel

# what actor_id becomes when the staff member's account is deleted: the entry stays
DELETED_ACTOR = "deleted-user"

# the most staff entries one response keeps: the next staff edit is refused
# (409 ``revision_limit``) rather than the history being trimmed; a respondent's
# own edits are recorded without this limit
MAX_REVISIONS = 200


class ActorKind(str, enum.Enum):
    STAFF = "staff"
    # a workspace API key editing a response it made (the submissions API);
    # ``actor_id`` is the key's id, never a user
    API_KEY = "api_key"
    # the person who submitted the response (nothing more is recorded of them)
    RESPONDENT = "respondent"


class ResponseRevisionDocument(Record):
    # the id of the response's row (``form_responses.id``): the foreign key
    response_pk: str
    response_id: Optional[str] = None
    form_id: str
    workspace_id: str
    # 1.. in the order of the edits of one response
    seq: int
    actor_kind: ActorKind
    # the user id (staff; ``DELETED_ACTOR`` once the account is deleted) or the
    # API key's id (api_key); none for a respondent
    actor_id: Optional[str] = None
    # the member's role when they edited (staff only), e.g. "EDITOR"
    actor_role: Optional[str] = None
    # the ids of the questions whose answer changed
    changed: List[str] = []
    # {question id: the answer it had before, or null}, as JSON, sealed
    previous_values: Optional[bytes] = None

    class Settings:
        name = "response_revisions"


def seal_context(response_pk, seq) -> bytes:
    """What ``previous_values`` is bound to besides the workspace and form
    (``crypto_service`` associated data): the response and the entry's number,
    so an entry copied onto another response, or to another number, does not
    open. Also how the keyset rotation derives it from the row
    (``admin/tasks/impl/keyset_core.py``)."""
    return f"{response_pk}|{seq}".encode()


@dataclass(frozen=True)
class RevisionEditor:
    """Who a staff edit is, as the revision log records them."""

    user_id: str
    role: Optional[str] = None


def plain_answer(value: Any) -> Any:
    """A stored answer as plain JSON data (None stays None)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_without_none(v) for v in value]
    return value


def same_answer(before: Any, after: Any) -> bool:
    """Whether two answers are the same value: a key that is null is a key
    that is missing (what one writer leaves out another writes as null)."""
    return _without_none(plain_answer(before)) == _without_none(plain_answer(after))
