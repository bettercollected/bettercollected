"""The per-address draft cap holds across a promotion of the signing secret
(docs/auth-key-rotation.md): a draft saved before it carries the address's hash
under the previous key, so the atomic count looks at every member of the ring."""

import datetime as dt
import secrets

import pytest
from common.clock import utcnow
from common.ids import RecordId

from backend.app.container import container
from backend.app.schemas.form_draft import FormDraftDocument
from backend.app.services.form_drafts import tokens

pytestmark = pytest.mark.asyncio

OLD = secrets.token_hex(32)
NEW = secrets.token_hex(32)
WORKSPACE = RecordId("65e5501d00000000000000a1")
FORM = "65e5501d00000000000000f1"
ADDRESS = "ada.respondent@example.org"


def draft(email_key: str) -> FormDraftDocument:
    return FormDraftDocument(
        workspace_id=WORKSPACE,
        form_id=FORM,
        payload="p",
        email_key=email_key,
        token_hash="a" * 64,
        expires_at=utcnow() + dt.timedelta(days=3),
    )


async def test_the_cap_counts_a_draft_saved_under_the_previous_key():
    repo = container.form_draft_repo()
    before = tokens.DraftKeys(OLD).address_key(FORM, ADDRESS)
    assert await repo.create_for_address(draft(before), 1, utcnow()) is not None

    promoted = tokens.DraftKeys(f"{NEW},{OLD}")
    now_key = promoted.address_key(FORM, ADDRESS)
    assert now_key != before
    # a count under the new key alone sees nothing: the cap would be bypassed
    assert await repo.count_live_for_address(FORM, now_key, utcnow()) == 0
    assert await repo.count_live_for_address(FORM, promoted.address_keys(FORM, ADDRESS), utcnow()) == 1
    # the atomic insert looks at every member, so the second draft is refused
    refused = await repo.create_for_address(
        draft(now_key), 1, utcnow(), email_keys=promoted.address_keys(FORM, ADDRESS)
    )
    assert refused is None
    # another address is not affected
    other = promoted.address_key(FORM, "someone.else@example.org")
    saved = await repo.create_for_address(
        draft(other), 1, utcnow(), email_keys=promoted.address_keys(FORM, "someone.else@example.org")
    )
    assert saved is not None


async def test_without_the_old_key_in_the_ring_the_old_draft_no_longer_counts():
    repo = container.form_draft_repo()
    before = tokens.DraftKeys(OLD).address_key(FORM, ADDRESS)
    await repo.create_for_address(draft(before), 1, utcnow())
    dropped = tokens.DraftKeys(NEW)
    saved = await repo.create_for_address(
        draft(dropped.address_key(FORM, ADDRESS)), 1, utcnow(),
        email_keys=dropped.address_keys(FORM, ADDRESS),
    )
    assert saved is not None  # the old draft's link ended with its key (documented)
