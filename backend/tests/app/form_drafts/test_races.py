"""A save changes the draft's content and nothing else, and never brings a
deleted draft back: interleaved with a link request, an open, a discard, the
submit's delete and the purge. And the form's retention as it is now reaches
drafts that already exist."""

import datetime as dt

import pytest
from common.clock import utcnow

from backend.app.container import container
from backend.app.repositories.postgres.form_drafts import PostgresFormDraftRepository
from tests.app.controllers.data import testUser1
from tests.app.form_drafts.helpers import (
    body,
    cookies,
    draft_rows,
    drafting_form,
    settings_of,
    token_of,
    url,
)

pytestmark = pytest.mark.asyncio

ADDRESS = "ada.respondent@example.org"
CHANGED = {"name": {"type": "text", "text": "Ada, changed by the save"}}


@pytest.fixture()
def before_update(monkeypatch):
    """Run ``callback`` once, just before the next locked update of a draft: the
    other request that lands between a save's read and its write."""
    real = PostgresFormDraftRepository.update_fields
    pending = []

    async def update_fields(self, *args, **kwargs):
        if pending:
            callback = pending.pop()
            await callback()
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(PostgresFormDraftRepository, "update_fields", update_fields)
    return pending.append


async def link(client, workspace, form, **extra):
    return await client.post(
        url(workspace, form, "/link"), json=body(email=ADDRESS, **extra)
    )


async def test_a_save_racing_a_link_request_keeps_the_new_link_and_the_old_one_dead(
    client, workspace, mails, before_update
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()
    old_token = token_of(mails[0])
    holder = {}

    async def new_link():
        holder["second"] = (
            await link(client, workspace, form, editKey=first["editKey"])
        ).json()

    # the save has read the draft (old hashes) when the new link lands
    before_update(new_link)
    saved = await client.put(
        url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
    )
    assert saved.status_code == 200
    new_token = token_of(mails[1])
    # the link request's edit key was not undone by the save's stale copy
    assert (
        await client.put(
            url(workspace, form),
            json=body(CHANGED, editKey=holder["second"]["editKey"]),
        )
    ).status_code == 200
    # the replaced link stays dead; the new one works
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": old_token})
    ).status_code == 404
    opened = await client.post(url(workspace, form, "/open"), json={"token": new_token})
    assert opened.status_code == 200 and opened.json()["answers"] == CHANGED
    # opening the link replaced that edit key in turn
    assert (
        await client.put(
            url(workspace, form),
            json=body(CHANGED, editKey=holder["second"]["editKey"]),
        )
    ).status_code == 404
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=opened.json()["editKey"])
        )
    ).status_code == 200
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 404
    assert len(await draft_rows()) == 1


async def test_a_save_racing_an_open_keeps_the_new_edit_key(
    client, workspace, mails, before_update
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()
    token = token_of(mails[0])
    holder = {}

    async def open_link():
        holder["opened"] = (
            await client.post(url(workspace, form, "/open"), json={"token": token})
        ).json()

    before_update(open_link)
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 200
    # the open's edit key was not overwritten by the save's stale copy
    assert (
        await client.put(
            url(workspace, form),
            json=body(CHANGED, editKey=holder["opened"]["editKey"]),
        )
    ).status_code == 200
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 404


async def test_a_save_racing_a_discard_does_not_bring_the_draft_back(
    client, workspace, mails, before_update
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()

    async def discard():
        assert (
            await client.post(
                url(workspace, form, "/discard"), json={"editKey": first["editKey"]}
            )
        ).status_code == 200

    before_update(discard)
    saved = await client.put(
        url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
    )
    assert saved.status_code == 404 and saved.json()["code"] == "draft_not_found"
    assert await draft_rows() == []


async def test_a_save_racing_the_submits_delete_does_not_bring_the_draft_back(
    client, workspace, mails, before_update
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()

    async def submitted():
        await container.form_draft_service().delete_after_submit(
            workspace.id,
            str(form.form_id),
            None,
            edit_key=first["editKey"],
            token=first["editKey"],
        )

    before_update(submitted)
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 404
    assert await draft_rows() == []


async def test_a_save_racing_the_purge_does_not_bring_the_draft_back(
    client, workspace, mails, before_update
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()

    async def purged():
        (row,) = await draft_rows()
        row.expires_at = utcnow() - dt.timedelta(seconds=1)
        await container.form_draft_repo().upsert(row)
        assert (await container.form_draft_service().purge())["expired"] == 1

    before_update(purged)
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 404
    assert await draft_rows() == []


async def test_a_signed_in_save_racing_a_discard_or_the_purge_does_not_bring_the_draft_back(
    client, workspace, before_update
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())

    async def discard():
        assert (
            await client.post(
                url(workspace, form, "/discard"), json={}, cookies=cookies()
            )
        ).status_code == 200

    before_update(discard)
    saved = await client.put(
        url(workspace, form), json=body(CHANGED), cookies=cookies()
    )
    assert saved.status_code == 404
    assert await draft_rows() == []
    # without a draft, a save is a new draft (the insert, guarded by the account's unique index)
    assert (
        await client.put(url(workspace, form), json=body(CHANGED), cookies=cookies())
    ).status_code == 200
    assert len(await draft_rows()) == 1


async def test_a_save_changes_the_content_and_the_saved_date_only(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()
    (before,) = await draft_rows()
    assert (
        await client.put(
            url(workspace, form), json=body(CHANGED, editKey=first["editKey"])
        )
    ).status_code == 200
    (after,) = await draft_rows()
    assert after.payload != before.payload and after.updated_at > before.updated_at
    assert (
        after.token_hash,
        after.token_expires_at,
        after.edit_key_hash,
        after.email_key,
        after.created_at,
    ) == (
        before.token_hash,
        before.token_expires_at,
        before.edit_key_hash,
        before.email_key,
        before.created_at,
    )


# -------------------------------------------- the retention as it is now


async def age(days_ago: int, expires_in_days: int):
    """The draft as if it was last saved ``days_ago`` days ago under a form that kept it 30 days."""
    (row,) = await draft_rows()
    now = utcnow()
    row.updated_at = now - dt.timedelta(days=days_ago)
    row.created_at = row.updated_at
    row.expires_at = now + dt.timedelta(days=expires_in_days)
    row.token_expires_at = now + dt.timedelta(days=3)
    await container.form_draft_repo().upsert(row)


async def test_a_lowered_retention_reaches_drafts_that_already_exist(
    client, workspace, mails
):
    form = await drafting_form(workspace, draft_retention_days=30)
    sent = (await link(client, workspace, form)).json()
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    token = token_of(mails[0])
    rows = await draft_rows()
    now = utcnow()
    for row in rows:
        row.updated_at = row.created_at = now - dt.timedelta(days=20)
        row.expires_at = now + dt.timedelta(days=10)
        row.token_expires_at = now + dt.timedelta(days=3)
        await container.form_draft_repo().upsert(row)
    # inside the form's retention they open
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).status_code == 200
    assert (
        await client.post(url(workspace, form, "/mine"), json={}, cookies=cookies())
    ).status_code == 200
    # the form lowers it to 10 days: both are past it, whatever their own expiry says
    await settings_of(workspace, form, draft_retention_days=10)
    for call in (
        client.post(url(workspace, form, "/open"), json={"token": token}),
        client.post(url(workspace, form, "/mine"), json={}, cookies=cookies()),
        client.put(url(workspace, form), json=body(editKey=sent["editKey"])),
    ):
        refused = await call
        assert (
            refused.status_code == 404 and refused.json()["code"] == "draft_not_found"
        )
        assert "answers" not in refused.text
    # and the purge removes them
    assert (await container.form_draft_service().purge())["expired"] == 2
    assert await draft_rows() == []


async def test_the_purge_keeps_drafts_inside_the_lowered_retention(
    client, workspace, mails
):
    form = await drafting_form(workspace, draft_retention_days=30)
    await link(client, workspace, form)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    rows = await draft_rows()
    now = utcnow()
    old, recent = rows[0], rows[1]
    old.updated_at = old.created_at = now - dt.timedelta(days=20)
    recent.updated_at = recent.created_at = now - dt.timedelta(days=2)
    for row in (old, recent):
        row.expires_at = now + dt.timedelta(days=10)
        await container.form_draft_repo().upsert(row)
    await settings_of(workspace, form, draft_retention_days=10)
    assert (await container.form_draft_service().purge())["expired"] == 1
    assert [r.id for r in await draft_rows()] == [recent.id]


async def test_an_earlier_fixed_retention_date_reaches_drafts_that_already_exist(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    await link(client, workspace, form)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    token = token_of(mails[0])
    await settings_of(
        workspace,
        form,
        response_expiration_type="date",
        response_expiration=(utcnow() - dt.timedelta(days=1)).date().isoformat(),
    )
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).status_code == 404
    assert (
        await client.post(url(workspace, form, "/mine"), json={}, cookies=cookies())
    ).status_code == 404
    assert (await container.form_draft_service().purge())["expired"] == 2
    assert await draft_rows() == []


async def test_drafts_not_yet_past_the_retention_still_open(client, workspace, mails):
    form = await drafting_form(workspace, draft_retention_days=10)
    await link(client, workspace, form)
    token = token_of(mails[0])
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).status_code == 200
    assert (await container.form_draft_service().purge())["expired"] == 0


# ------------------------------------------------------------- the address key


def test_the_address_key_folds_case_unicode_and_internationalised_domains():
    keys = container.form_draft_service()._keys
    same = [
        "Ada@Example.org",
        " ada@example.ORG ",
        "Straße@example.org",
        "STRASSE@example.org",
        "ada@bücher.example",
        "ada@BÜCHER.example",
        "ada@xn--bcher-kva.example",
    ]
    assert keys.address_key("f", same[0]) == keys.address_key("f", same[1])
    assert keys.address_key("f", same[2]) == keys.address_key("f", same[3])
    assert (
        keys.address_key("f", same[4])
        == keys.address_key("f", same[5])
        == keys.address_key("f", same[6])
    )
    assert keys.address_key("f", same[0]) != keys.address_key("f", same[4])
    assert keys.address_key("f", "ada@example.org") != keys.address_key(
        "g", "ada@example.org"
    )
    # a composed and a decomposed letter are the same mailbox
    assert keys.address_key("f", "é@example.org") == keys.address_key(
        "f", "é@example.org"
    )
