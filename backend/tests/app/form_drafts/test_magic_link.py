"""The magic link for respondents who are not signed in: opt-in by entering an
address, sent through the auth service's mail sender, the token random,
expiring, single purpose and stored only as a keyed hash, the address never
stored, every refusal alike, every route rate limited."""

import datetime as dt
import json

import pytest
from common.clock import utcnow
from loguru import logger

from backend.app.container import container
from backend.app.services.form_drafts import limits, tokens
from tests.app.controllers.data import testUser1
from tests.app.form_drafts.helpers import (
    ANSWERS,
    body,
    cookies,
    draft_ciphertexts,
    draft_rows,
    drafting_form,
    token_of,
    url,
)

pytestmark = pytest.mark.asyncio

ADDRESS = "ada.respondent@example.org"


async def ask_for_link(client, workspace, form, address=ADDRESS, **extra):
    return await client.post(
        url(workspace, form, "/link"), json=body(email=address, **extra)
    )


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


async def test_the_mail_names_the_form_and_the_link_and_holds_no_answer(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    sent = await ask_for_link(client, workspace, form, locale="nl")
    assert sent.status_code == 200, sent.text
    (mail,) = mails
    assert mail["url"].endswith("/notifications/draft-link")
    assert mail["headers"] is not None
    payload = mail["json"]
    assert payload["recipient"] == ADDRESS and payload["locale"] == "nl"
    assert payload["days"] == 7 and payload["form_title"]
    assert set(payload) == {
        "recipient",
        "form_title",
        "workspace_title",
        "link",
        "days",
        "locale",
    }
    # the link: the client host, the form's page, the token in the fragment
    link = payload["link"]
    assert f"/{workspace.workspace_name}/forms/{form.form_id}#resume=" in link
    assert "?" not in link
    dumped = json.dumps(mail)
    for secret in ("Ada Example", "synthetic story", "newsletter"):
        assert secret not in dumped


async def test_the_token_is_stored_only_as_a_keyed_hash_and_the_address_not_at_all(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    sent = (await ask_for_link(client, workspace, form)).json()
    token = token_of(mails[0])
    secret = token.split(".")[1]
    edit_secret = sent["editKey"].split(".")[1]
    (row,) = await draft_rows()
    stored = draft_ciphertexts([row])
    assert secret not in stored and edit_secret not in stored and token not in stored
    assert ADDRESS not in stored and "example.org" not in stored
    assert row.token_hash and row.edit_key_hash and row.token_hash != row.edit_key_hash
    assert row.email_key and ADDRESS not in row.email_key
    # the token is the draft's id and 256 random bits, never the edit key
    assert token.split(".")[0] == str(row.id) == sent["editKey"].split(".")[0]
    assert secret != edit_secret and len(secret) == 43
    # unlike the response, the browser is never handed the link's token
    assert token not in json.dumps(sent)
    # the token lasts 7 days at most, and no longer than the draft
    assert (
        dt.timedelta(days=6, hours=23)
        < row.token_expires_at - utcnow()
        <= limits.LINK_LIFETIME
    )


async def test_opening_the_link_restores_the_draft_and_hands_out_a_fresh_edit_key(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    first = (await ask_for_link(client, workspace, form)).json()
    token = token_of(mails[0])
    opened = await client.post(url(workspace, form, "/open"), json={"token": token})
    assert opened.status_code == 200, opened.text
    draft = opened.json()
    assert draft["answers"] == ANSWERS and draft["hiddenFields"] == {
        "source": "newsletter"
    }
    assert draft["editKey"] and draft["editKey"] != first["editKey"]
    assert opened.headers["cache-control"] == "no-store"
    # the key of the browser that made the draft no longer saves; the new one does
    old = await client.put(url(workspace, form), json=body(editKey=first["editKey"]))
    assert old.status_code == 404
    changed = {"name": {"type": "text", "text": "Ada, later"}}
    saved = await client.put(
        url(workspace, form), json=body(changed, editKey=draft["editKey"])
    )
    assert saved.status_code == 200, saved.text
    again = (
        await client.post(url(workspace, form, "/open"), json={"token": token})
    ).json()
    assert again["answers"] == changed
    # the link keeps working until it expires (a second device), no mail was needed
    assert len(mails) == 1


async def test_the_browser_that_made_the_draft_saves_with_its_edit_key_and_without_a_mail(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    first = (await ask_for_link(client, workspace, form)).json()
    changed = {"name": {"type": "text", "text": "Ada, again"}}
    saved = await client.put(
        url(workspace, form), json=body(changed, editKey=first["editKey"])
    )
    assert saved.status_code == 200
    assert len(await draft_rows()) == 1 and len(mails) == 1
    # a save without the key, or with another draft's, finds nothing to update
    assert (await client.put(url(workspace, form), json=body())).status_code == 404
    other = (
        await ask_for_link(client, workspace, form, address="b@example.org")
    ).json()
    mixed = other["editKey"].split(".")[0] + "." + first["editKey"].split(".")[1]
    assert (
        await client.put(url(workspace, form), json=body(editKey=mixed))
    ).status_code == 404


async def test_a_new_link_for_the_same_draft_replaces_the_old_one(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    first = (await ask_for_link(client, workspace, form)).json()
    old = token_of(mails[0])
    second = await ask_for_link(client, workspace, form, editKey=first["editKey"])
    assert second.status_code == 200
    assert len(await draft_rows()) == 1 and len(mails) == 2
    new = token_of(mails[1])
    assert new != old
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": old})
    ).status_code == 404
    assert (
        await client.post(url(workspace, form, "/open"), json={"token": new})
    ).status_code == 200


async def test_every_bad_token_gets_the_same_answer(
    client, workspace, workspace_1, mails, monkeypatch
):
    monkeypatch.setattr(
        limits, "OPEN_MISSES_PER_CLIENT", ("draft-open-miss", 1000, 3600)
    )
    form = await drafting_form(workspace)
    other_form = await drafting_form(workspace)
    await ask_for_link(client, workspace, form)
    token = token_of(mails[0])
    draft_id, secret = token.split(".")
    edit_key = (
        await client.put(url(workspace, form), json=body())
    ).status_code  # no key: 404 as well
    assert edit_key == 404
    expired_row = (await draft_rows())[0]
    answers = []
    for value in (
        "",
        "garbage",
        draft_id + "." + "A" * 43,
        "0" * 24 + "." + secret,
        secret,
        token + "x",
        token.upper(),
        "a" * 5000,
    ):
        answers.append(
            await client.post(url(workspace, form, "/open"), json={"token": value})
        )
    # the right token on another form, or another workspace's path
    answers.append(
        await client.post(url(workspace, other_form, "/open"), json={"token": token})
    )
    answers.append(
        await client.post(
            f"/api/v1/workspaces/{workspace_1.id}/forms/{form.form_id}/drafts/open",
            json={"token": token},
        )
    )
    # expired link, and an expired draft
    expired_row.token_expires_at = utcnow() - dt.timedelta(seconds=1)
    await container.form_draft_repo().upsert(expired_row)
    answers.append(
        await client.post(url(workspace, form, "/open"), json={"token": token})
    )
    expired_row.token_expires_at = utcnow() + dt.timedelta(days=1)
    expired_row.expires_at = utcnow() - dt.timedelta(seconds=1)
    await container.form_draft_repo().upsert(expired_row)
    answers.append(
        await client.post(url(workspace, form, "/open"), json={"token": token})
    )
    assert {(a.status_code, json.dumps(a.json(), sort_keys=True)) for a in answers} == {
        (
            404,
            json.dumps(
                {"code": "draft_not_found", "message": "There is no such draft."},
                sort_keys=True,
            ),
        )
    }


async def test_a_token_is_not_an_edit_key_and_an_edit_key_is_not_a_token(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    sent = (await ask_for_link(client, workspace, form)).json()
    token = token_of(mails[0])
    assert (
        await client.post(
            url(workspace, form, "/open"), json={"token": sent["editKey"]}
        )
    ).status_code == 404
    assert (
        await client.put(url(workspace, form), json=body(editKey=token))
    ).status_code == 404
    discarded = await client.post(
        url(workspace, form, "/discard"), json={"editKey": token}
    )
    assert discarded.status_code == 404
    assert len(await draft_rows()) == 1


async def test_secrets_are_compared_in_constant_time(
    client, workspace, mails, monkeypatch
):
    form = await drafting_form(workspace)
    await ask_for_link(client, workspace, form)
    token = token_of(mails[0])
    calls = []
    real = tokens.hmac.compare_digest
    monkeypatch.setattr(
        tokens.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b)
    )
    await client.post(url(workspace, form, "/open"), json={"token": token})
    await client.post(
        url(workspace, form, "/open"),
        json={"token": "0" * 24 + "." + token.split(".")[1]},
    )
    assert len(calls) == 2  # the right token, and one for no such draft


async def test_a_form_that_requires_sign_in_sends_no_links(client, workspace, mails):
    form = await drafting_form(workspace, require_verified_identity=True)
    refused = await ask_for_link(client, workspace, form)
    assert refused.status_code == 403 and refused.json()["code"] == "sign_in_required"
    assert mails == [] and await draft_rows() == []
    # signed in, it saves to the account as on any form
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 200


async def test_a_signed_in_respondent_is_sent_to_their_account_and_no_mail_goes(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    refused = await client.post(
        url(workspace, form, "/link"), json=body(email=ADDRESS), cookies=cookies()
    )
    assert refused.status_code == 409 and refused.json()["code"] == "use_account"
    assert mails == []


@pytest.mark.parametrize(
    "address", ["", "x", "not an address", "a@b", "a@@b.test", "a" * 300 + "@b.test"]
)
async def test_an_address_that_is_not_one_is_refused_before_anything_is_stored(
    client, workspace, mails, address
):
    form = await drafting_form(workspace)
    refused = await ask_for_link(client, workspace, form, address=address)
    assert refused.status_code == 422
    assert mails == [] and await draft_rows() == []


async def test_a_mail_that_cannot_be_sent_is_reported_and_the_respondent_can_try_again(
    client, workspace, monkeypatch, mails
):
    form = await drafting_form(workspace)

    async def down(*args, **kwargs):
        raise RuntimeError("auth is down")

    monkeypatch.setattr(type(container.http_client()), "post", down)
    refused = await ask_for_link(client, workspace, form)
    assert refused.status_code == 503 and refused.json()["code"] == "link_not_sent"


async def test_link_requests_are_limited_per_address_per_client_and_per_form(
    client, workspace, mails, monkeypatch
):
    form = await drafting_form(workspace)
    monkeypatch.setattr(limits, "LINK_PER_ADDRESS", ("draft-link-address", 2, 3600))
    assert (await ask_for_link(client, workspace, form)).status_code == 200
    assert (await ask_for_link(client, workspace, form)).status_code == 200
    refused = await ask_for_link(client, workspace, form)
    assert refused.status_code == 429 and refused.json()["code"] == "rate_limited"
    assert int(refused.headers["retry-after"]) > 0
    # the same address on another form has its own budget; another address is not held back
    other_form = await drafting_form(workspace)
    assert (await ask_for_link(client, workspace, other_form)).status_code == 200
    assert (
        await ask_for_link(client, workspace, form, address="b@example.org")
    ).status_code == 200
    # five requests counted so far for this client
    monkeypatch.setattr(limits, "LINK_PER_CLIENT", ("draft-link-client", 7, 3600))
    assert (
        await ask_for_link(client, workspace, form, address="c@example.org")
    ).status_code == 200
    assert (
        await ask_for_link(client, workspace, form, address="d@example.org")
    ).status_code == 200
    assert (
        await ask_for_link(client, workspace, form, address="e@example.org")
    ).status_code == 429
    monkeypatch.setattr(limits, "LINK_PER_CLIENT", ("draft-link-client", 500, 3600))
    monkeypatch.setattr(limits, "LINK_PER_FORM", ("draft-link-form", 6, 3600))
    assert (
        await ask_for_link(client, workspace, form, address="f@example.org")
    ).status_code == 200
    assert (
        await ask_for_link(client, workspace, form, address="g@example.org")
    ).status_code == 429
    # refused requests sent nothing
    assert len(mails) == 7


async def test_one_address_holds_at_most_a_few_drafts_on_a_form(
    client, workspace, mails, monkeypatch
):
    form = await drafting_form(workspace)
    monkeypatch.setattr(limits, "LINK_PER_ADDRESS", ("draft-link-address", 100, 3600))
    monkeypatch.setattr(limits, "LINK_PER_CLIENT", ("draft-link-client", 100, 3600))
    for _ in range(limits.MAX_DRAFTS_PER_ADDRESS):
        assert (await ask_for_link(client, workspace, form)).status_code == 200
    refused = await ask_for_link(client, workspace, form)
    assert refused.status_code == 429
    assert len(await draft_rows()) == limits.MAX_DRAFTS_PER_ADDRESS
    assert len(mails) == limits.MAX_DRAFTS_PER_ADDRESS
    # another address is unaffected, and upper case is the same address
    assert (
        await ask_for_link(client, workspace, form, address="other@example.org")
    ).status_code == 200
    assert (
        await ask_for_link(client, workspace, form, address=ADDRESS.upper())
    ).status_code == 429


async def test_failed_opens_are_counted_and_end_in_a_wait(
    client, workspace, monkeypatch
):
    form = await drafting_form(workspace)
    monkeypatch.setattr(limits, "OPEN_MISSES_PER_CLIENT", ("draft-open-miss", 3, 3600))
    for _ in range(3):
        assert (
            await client.post(url(workspace, form, "/open"), json={"token": "x"})
        ).status_code == 404
    waiting = await client.post(url(workspace, form, "/open"), json={"token": "x"})
    assert waiting.status_code == 429 and "retry-after" in waiting.headers


async def test_saves_are_limited_per_client(client, workspace, monkeypatch):
    form = await drafting_form(workspace)
    monkeypatch.setattr(limits, "SAVES_PER_CLIENT", ("draft-save", 2, 3600))
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 200
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 200
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).status_code == 429


async def test_no_log_line_holds_an_answer_a_token_or_an_address(
    client, workspace, mails, lines
):
    form = await drafting_form(workspace)
    sent = (await ask_for_link(client, workspace, form)).json()
    token = token_of(mails[0])
    await client.post(url(workspace, form, "/open"), json={"token": token})
    await client.post(
        url(workspace, form, "/open"),
        json={"token": "0" * 24 + "." + token.split(".")[1]},
    )
    await client.put(url(workspace, form), json=body(editKey=sent["editKey"]))
    text = "\n".join(lines)
    for secret in (
        token,
        token.split(".")[1],
        sent["editKey"],
        ADDRESS,
        "Ada Example",
        "synthetic story",
    ):
        assert secret not in text


async def test_a_failed_send_logs_no_address_and_no_link(
    client, workspace, monkeypatch, lines
):
    form = await drafting_form(workspace)

    async def down(*args, **kwargs):
        raise RuntimeError(
            f"cannot reach {kwargs['json']['recipient']} {kwargs['json']['link']}"
        )

    monkeypatch.setattr(type(container.http_client()), "post", down)
    await ask_for_link(client, workspace, form)
    text = "\n".join(lines)
    assert ADDRESS not in text and "#resume=" not in text
