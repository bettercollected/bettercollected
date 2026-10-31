"""A respondent's saved draft of a form (``services/form_drafts``).

A draft is not a response: its own table, never read by the responses
repositories, so it appears in no list, export, count, limit, action or
webhook until it is submitted (and then it is deleted). Answers, hidden-field
values and the page position are one encrypted payload (``payload``): the
response keyset, bound to the workspace and form and to this draft's id.
Nothing else here is respondent data: no address (``email_key`` is a keyed
hash), no token (only keyed hashes of them).
"""

import datetime as dt
from typing import Optional

from common.records import Record, RecordId
from pydantic import field_validator


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class FormDraftDocument(Record):
    workspace_id: RecordId
    form_id: str
    # the published version the answers were given against
    form_version: Optional[int] = None
    # the signed-in respondent's account id: the draft is theirs. None for an
    # anonymous draft, which is opened with a link or an edit key.
    owner_id: Optional[str] = None
    # keyed hash of the normalised address the link was sent to (anonymous
    # only), to cap drafts per address; the address itself is never stored
    email_key: Optional[str] = None
    # base64 of the encrypted payload (JSON: answers, hiddenFields, position)
    payload: str
    # keyed hash of the magic link's token, and when the link stops working
    token_hash: Optional[str] = None
    token_expires_at: Optional[dt.datetime] = None
    # keyed hash of the key the browser that created the draft holds, to save
    # again without another mail
    edit_key_hash: Optional[str] = None
    expires_at: dt.datetime

    _tz = field_validator("token_expires_at", "expires_at")(_utc)

    class Settings:
        name = "form_drafts"
