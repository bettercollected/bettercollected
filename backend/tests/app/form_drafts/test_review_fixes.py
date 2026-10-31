"""Hardening from the independent review: JSON-only routes (CSRF), a failed mail
that loses nothing, a full address that tells nothing, an open that moves only
the edit key, the address mailed as typed, a form that starts asking for a
sign-in, storage caps and a purge that pages."""

import datetime as dt
import json

import pytest
from common.clock import utcnow

from backend.app.container import container
from backend.app.services.form_drafts import limits, service, tokens
from backend.config import settings
from tests.app.controllers.data import testUser1, testUser2
from tests.app.form_drafts.helpers import (
    ANSWERS,
    body,
    cookies,
    draft_rows,
    drafting_form,
    settings_of,
    token_of,
    url,
)
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio

ADDRESS = "ada.respondent@example.org"


async def link(client, workspace, form, address=ADDRESS, **extra):
    return await client.post(
        url(workspace, form, "/link"), json=body(email=address, **extra)
    )


# ------------------------------------------------------------------ CSRF


@pytest.mark.parametrize(
    "content_type",
    [
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "",
    ],
)
async def test_a_draft_route_takes_json_only(client, workspace, mails, content_type):
    """A page on another site can post text or a form with the respondent's
    cookies and no preflight: none of that may reach a draft route."""
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    sent = (await link(client, workspace, form)).json()
    token = token_of(mails[0])
    headers = {"content-type": content_type} if content_type else {}
    payloads = {
        "/discard": json.dumps({}),
        "/link": json.dumps(body(email="b@example.org")),
        "/open": json.dumps({"token": token}),
        "/mine": "{}",
    }
    for tail, content in payloads.items():
        refused = await client.post(
            url(workspace, form, tail),
            content=content,
            headers=headers,
            cookies=cookies(),
        )
        assert refused.status_code == 415, (tail, refused.text)
        assert refused.json()["code"] == "json_required"
    saved = await client.put(
        url(workspace, form),
        content=json.dumps(body()),
        headers=headers,
        cookies=cookies(),
    )
    assert saved.status_code == 415
    # nothing was deleted, opened or mailed
    assert len(await draft_rows()) == 2 and len(mails) == 1
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).status_code == 200
    assert sent["editKey"]


async def test_json_with_a_charset_is_accepted(client, workspace):
    form = await drafting_form(workspace)
    saved = await client.put(
        url(workspace, form),
        content=json.dumps(body()),
        headers={"content-type": "Application/JSON; charset=utf-8"},
        cookies=cookies(),
    )
    assert saved.status_code == 200


# --------------------------------------------------- a failed mail loses nothing


async def test_a_failed_mail_leaves_the_old_link_and_edit_key_working(
    client, workspace, mails, monkeypatch
):
    form = await drafting_form(workspace)
    first = (await link(client, workspace, form)).json()
    old_token = token_of(mails[0])
    changed = {"name": {"type": "text", "text": "Ada, newer"}}

    async def down(*args, **kwargs):
        raise RuntimeError("auth is down")

    with monkeypatch.context() as patched:
        patched.setattr(type(container.http_client()), "post", down)
        refused = await link(
            client, workspace, form, editKey=first["editKey"], answers=changed
        )
    assert refused.status_code == 503 and refused.json()["code"] == "link_not_sent"
    assert len(await draft_rows()) == 1
    # the browser's key still saves, the old link still opens (with the old answers)
    assert (
        await client.put(
            url(workspace, form), json=body(changed, editKey=first["editKey"])
        )
    ).status_code == 200
    opened = await client.post(url(workspace, form, "/open"), json={"token": old_token})
    assert opened.status_code == 200 and opened.json()["answers"] == changed


async def test_a_failed_mail_for_a_new_draft_stores_nothing(
    client, workspace, monkeypatch
):
    form = await drafting_form(workspace)

    async def down(*args, **kwargs):
        raise RuntimeError("auth is down")

    monkeypatch.setattr(type(container.http_client()), "post", down)
    monkeypatch.setattr(limits, "LINK_PER_ADDRESS", ("draft-link-address", 100, 3600))
    monkeypatch.setattr(limits, "LINK_PER_CLIENT", ("draft-link-client", 100, 3600))
    for _ in range(limits.MAX_DRAFTS_PER_ADDRESS + 2):
        assert (await link(client, workspace, form)).status_code == 503
    # no retry added a draft that counts against the address
    assert await draft_rows() == []


# ----------------------------------------------- opening moves only the edit key


async def test_opening_a_link_moves_only_the_edit_key(client, workspace, mails):
    form = await drafting_form(workspace)
    sent = (await link(client, workspace, form)).json()
    (before,) = await draft_rows()
    token = token_of(mails[0])
    opened = (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).json()
    (after,) = await draft_rows()
    assert opened["savedAt"] == sent["savedAt"] or opened["savedAt"].startswith(
        sent["savedAt"][:19]
    )
    assert after.updated_at == before.updated_at
    assert after.payload == before.payload and after.token_hash == before.token_hash
    assert after.edit_key_hash != before.edit_key_hash
    # a save that lands after the open is not undone by a later open
    changed = {"name": {"type": "text", "text": "Ada, later"}}
    assert (
        await client.put(
            url(workspace, form), json=body(changed, editKey=opened["editKey"])
        )
    ).status_code == 200
    again = (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).json()
    assert again["answers"] == changed


# -------------------------------------------------- the address as typed


async def test_the_mail_goes_to_the_address_as_typed_and_the_caps_fold_it(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    typed = "Strasse.Weiß@example.org"
    assert (
        await link(client, workspace, form, address=f"  {typed} ")
    ).status_code == 200
    assert mails[0]["json"]["recipient"] == typed
    keys = container.form_draft_service()._keys
    assert keys.address_key(form.form_id, typed) == keys.address_key(
        form.form_id, "STRASSE.WEISS@EXAMPLE.ORG"
    )
    (row,) = await draft_rows()
    assert typed not in json.dumps(row.model_dump(mode="json"))


# ------------------------------------- a form that starts to ask for a sign-in


async def test_an_anonymous_draft_stops_opening_and_saving_when_the_form_asks_for_sign_in(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    sent = (await link(client, workspace, form)).json()
    token = token_of(mails[0])
    await client.put(url(workspace, form), json=body(editKey=sent["editKey"]))
    await settings_of(workspace, form, require_verified_identity=True)
    opened = await client.post(url(workspace, form, "/open"), json={"token": token})
    assert opened.status_code == 404 and opened.json()["code"] == "draft_not_found"
    assert "answers" not in opened.text
    saved = await client.put(url(workspace, form), json=body(editKey=sent["editKey"]))
    assert saved.status_code == 403 and saved.json()["code"] == "sign_in_required"
    # a signed-in respondent is unaffected, and the anonymous one can still delete
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 200
    assert (
        await client.post(
            url(workspace, form, "/discard"), json={"editKey": sent["editKey"]}
        )
    ).status_code == 200


# ----------------------------------------------------------- storage caps


async def test_a_form_holds_a_bounded_number_of_anonymous_drafts(
    client, workspace, mails, monkeypatch
):
    monkeypatch.setattr(limits, "MAX_ANONYMOUS_DRAFTS_PER_FORM", 2)
    form = await drafting_form(workspace)
    other = await drafting_form(workspace)
    first = (await link(client, workspace, form, address="a@example.org")).json()
    assert (
        await link(client, workspace, form, address="b@example.org")
    ).status_code == 200
    full = await link(client, workspace, form, address="c@example.org")
    assert full.status_code == 409 and full.json()["code"] == "draft_limit"
    assert len(mails) == 2 and len(await draft_rows()) == 2
    # a draft that exists can still be updated and re-sent, and another form has room
    assert (
        await link(
            client, workspace, form, address="a@example.org", editKey=first["editKey"]
        )
    ).status_code == 200
    assert (
        await link(client, workspace, other, address="c@example.org")
    ).status_code == 200
    # an expired draft no longer counts
    for row in await draft_rows():
        row.expires_at = utcnow() - dt.timedelta(seconds=1)
        await container.form_draft_repo().upsert(row)
    assert (
        await link(client, workspace, form, address="d@example.org")
    ).status_code == 200


async def test_an_account_holds_a_bounded_number_of_drafts(
    client, workspace, monkeypatch
):
    monkeypatch.setattr(limits, "MAX_DRAFTS_PER_ACCOUNT", 2)
    forms = [await drafting_form(workspace) for _ in range(3)]
    for form in forms[:2]:
        assert (
            await client.put(url(workspace, form), json=body(), cookies=cookies())
        ).status_code == 200
    full = await client.put(url(workspace, forms[2]), json=body(), cookies=cookies())
    assert full.status_code == 409 and full.json()["code"] == "draft_limit"
    # saving one it already has is not a new draft; another account has its own room
    assert (
        await client.put(url(workspace, forms[0]), json=body(), cookies=cookies())
    ).status_code == 200
    assert (
        await client.put(
            url(workspace, forms[2]), json=body(), cookies=cookies(testUser2)
        )
    ).status_code == 200
    assert len(await draft_rows()) == 3


# --------------------------------------------------------------- the purge pages


async def test_the_purge_looks_at_every_form_not_just_the_first_page(
    client, workspace, monkeypatch
):
    from backend.jobs import tasks

    monkeypatch.setattr(service, "PURGE_PAGE", 2)
    forms = [await drafting_form(workspace) for _ in range(5)]
    for form in forms:
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    for form in forms:
        await settings_of(workspace, form, allow_save_draft=False)
    assert await tasks.purge_form_drafts(0) == "0 expired, 5 of forms that keep none"
    assert await draft_rows() == []
