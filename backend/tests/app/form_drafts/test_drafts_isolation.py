"""A draft is not a response: it is counted nowhere and starts nothing until
the form is submitted, which is the normal submit with every gate, and the
draft goes with it. Erasure covers drafts."""

import datetime as dt
import json
from unittest.mock import AsyncMock, patch

import pytest
from common.clock import utcnow

from backend.app.container import container
from backend.app.services.actions_service import ActionService
from backend.app.services.registration.service import RegistrationService
from backend.app.services.webhooks.service import WebhookService
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.form_drafts.helpers import (
    ANSWERS,
    body,
    cookies,
    draft_rows,
    drafting_form,
    settings_of,
    submit_over_http,
    token_of,
    url,
)
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio

ADDRESS = "ada.respondent@example.org"


def workspace_url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


@pytest.fixture()
def starts():
    """What a submission starts: actions, the registration, webhooks."""
    with patch.object(
        ActionService, "start_actions_for_submission", AsyncMock()
    ) as actions, patch.object(
        RegistrationService, "queue_for_submission", AsyncMock()
    ) as registration, patch.object(
        WebhookService, "queue_for_submission", AsyncMock()
    ) as webhooks:
        yield [actions, registration, webhooks]


async def stored_responses(workspace, form) -> int:
    return await container.form_response_service().count_for_form(
        workspace.id, str(form.form_id)
    )


async def test_a_draft_is_in_no_list_export_or_count(
    client, workspace, test_user_cookies
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    assert len(await draft_rows()) == 2
    assert await stored_responses(workspace, form) == 0
    assert await container.form_response_repo().many() == []
    base = f"{workspace_url(workspace)}/forms/{form.form_id}"
    listed = await client.get(f"{base}/submissions", cookies=test_user_cookies)
    assert listed.status_code == 200 and listed.json()["items"] == []
    everything = await client.get(
        f"{workspace_url(workspace)}/all-submissions", cookies=test_user_cookies
    )
    assert everything.status_code == 200 and everything.json()["items"] == []
    exported = await client.get(
        f"{base}/all-submissions/export", cookies=test_user_cookies
    )
    assert "Ada Example" not in exported.text
    responders = await client.get(
        f"{workspace_url(workspace)}/responders", cookies=test_user_cookies
    )
    assert testUser1.sub not in responders.text
    mine = await client.get(
        f"{workspace_url(workspace)}/submissions", cookies=cookies()
    )
    assert mine.status_code in (200, 404) and "Ada Example" not in mine.text
    assert not await container.form_response_service().get_responses_count_in_workspace(
        workspace.id, [str(form.form_id)]
    )


async def test_a_draft_does_not_use_up_the_response_limit(client, workspace):
    form = await drafting_form(workspace, response_limit=1)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    # two drafts, a limit of one: a submission still has its place
    submitted = await submit_over_http(
        client, workspace, form, user_cookies=cookies(testUser2)
    )
    assert submitted.status_code == 200, submitted.text
    assert await stored_responses(workspace, form) == 1
    # now the form is full and takes no more, drafts or not
    full = await submit_over_http(
        client, workspace, form, user_cookies=cookies(testUser1)
    )
    assert full.status_code == 409 and full.json()["code"] == "form_full"


async def test_saving_opening_and_discarding_start_no_action_webhook_or_registration(
    client, workspace, mails, starts
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.post(url(workspace, form, "/mine"), cookies=cookies())
    sent = (
        await client.post(url(workspace, form, "/link"), json=body(email=ADDRESS))
    ).json()
    await client.post(url(workspace, form, "/open"), json={"token": token_of(mails[0])})
    await client.put(url(workspace, form), json=body(editKey=sent["editKey"]))
    await client.post(
        url(workspace, form, "/discard"), json={"editKey": sent["editKey"]}
    )
    await client.post(url(workspace, form, "/discard"), json={}, cookies=cookies())
    assert [spy.await_count for spy in starts] == [0, 0, 0]
    # the submission is what starts them
    submitted = await submit_over_http(client, workspace, form, user_cookies=cookies())
    assert submitted.status_code == 200
    assert [spy.await_count for spy in starts] == [1, 1, 1]


async def test_submitting_deletes_the_signed_in_respondents_draft(client, workspace):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    submitted = await submit_over_http(
        client, workspace, form, ANSWERS, user_cookies=cookies()
    )
    assert submitted.status_code == 200, submitted.text
    rows = await draft_rows()
    assert [r.owner_id for r in rows] == [testUser2.id]


async def test_submitting_with_the_edit_key_or_the_link_deletes_the_anonymous_draft(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    sent = (
        await client.post(url(workspace, form, "/link"), json=body(email=ADDRESS))
    ).json()
    assert (
        await submit_over_http(client, workspace, form, draft_key=sent["editKey"])
    ).status_code == 200
    assert await draft_rows() == []
    again = (
        await client.post(
            url(workspace, form, "/link"), json=body(email="b@example.org")
        )
    ).json()
    del again
    token = token_of(mails[1])
    assert (
        await submit_over_http(client, workspace, form, draft_key=token)
    ).status_code == 200
    assert await draft_rows() == []
    # a key that is not theirs deletes nothing
    await client.post(url(workspace, form, "/link"), json=body(email="c@example.org"))
    assert (
        await submit_over_http(
            client, workspace, form, draft_key="0" * 24 + "." + "A" * 43
        )
    ).status_code == 200
    assert len(await draft_rows()) == 1


async def test_a_refused_submission_keeps_the_draft(client, workspace):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await settings_of(
        workspace,
        form,
        form_close_date=(utcnow() - dt.timedelta(minutes=1)).isoformat(),
    )
    refused = await submit_over_http(client, workspace, form, user_cookies=cookies())
    assert refused.status_code == 409 and refused.json()["code"] == "form_closed"
    assert len(await draft_rows()) == 1
    # the same gates as any submission: open date, rules
    await settings_of(
        workspace,
        form,
        form_close_date=None,
        form_open_date=(utcnow() + dt.timedelta(days=1)).isoformat(),
    )
    assert (
        await submit_over_http(client, workspace, form, user_cookies=cookies())
    ).json()["code"] == "form_not_open"
    assert len(await draft_rows()) == 1


async def test_a_draft_never_lets_an_answer_past_the_submit_checks(client, workspace):
    """What a draft holds is the respondent's own text, saved unchecked; the
    submission checks it all again (here: an unknown question is refused)."""
    form = await drafting_form(workspace)
    odd = {"not-a-question": {"type": "text", "text": "x"}}
    assert (
        await client.put(url(workspace, form), json=body(odd), cookies=cookies())
    ).status_code == 200
    refused = await submit_over_http(
        client, workspace, form, odd, user_cookies=cookies()
    )
    assert refused.status_code == 422
    assert len(await draft_rows()) == 1


async def test_discarding_deletes_only_the_callers_own_draft(client, workspace, mails):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    gone = await client.post(
        url(workspace, form, "/discard"), json={}, cookies=cookies()
    )
    assert gone.status_code == 200 and gone.json() == {"deleted": True}
    assert [r.owner_id for r in await draft_rows()] == [testUser2.id]
    again = await client.post(
        url(workspace, form, "/discard"), json={}, cookies=cookies()
    )
    assert again.status_code == 404
    # nobody signed in and no key: nothing to delete
    assert (
        await client.post(url(workspace, form, "/discard"), json={})
    ).status_code == 404
    assert len(await draft_rows()) == 1
    # by edit key and by link, also after the form stopped keeping drafts
    sent = (
        await client.post(url(workspace, form, "/link"), json=body(email=ADDRESS))
    ).json()
    await settings_of(workspace, form, allow_save_draft=False)
    assert (
        await client.post(
            url(workspace, form, "/discard"), json={"editKey": sent["editKey"]}
        )
    ).status_code == 200
    assert [r.owner_id for r in await draft_rows()] == [testUser2.id]


async def test_deleting_the_form_deletes_its_drafts(client, workspace):
    form = await drafting_form(workspace)
    keep = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await client.put(url(workspace, keep), json=body(), cookies=cookies())
    await container.workspace_form_service().delete_form_from_workspace(
        workspace.id, form.form_id, testUser
    )
    assert [r.form_id for r in await draft_rows()] == [str(keep.form_id)]


async def test_deleting_the_workspace_deletes_its_drafts(
    client, workspace, workspace_1
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    kept = await publish(workspace_1, user=testUser1)
    await settings_of(workspace_1, kept, allow_save_draft=True)
    await client.put(url(workspace_1, kept), json=body(), cookies=cookies(testUser2))
    await container.workspace_service().delete_workspaces_of_user_with_forms(testUser)
    assert [str(r.workspace_id) for r in await draft_rows()] == [str(workspace_1.id)]


async def test_deleting_an_account_deletes_its_drafts_in_every_workspace(
    client, workspace, monkeypatch
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser1))
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    auth = container.auth_service()
    monkeypatch.setattr(auth, "delete_user_form_auth", AsyncMock())
    monkeypatch.setattr(auth, "delete_credentials_from_integrations", AsyncMock())
    monkeypatch.setattr(container.session_service(), "delete_all_for_user", AsyncMock())
    await auth.delete_user(testUser1)
    assert [r.owner_id for r in await draft_rows()] == [testUser2.id]


async def test_the_daily_purge_deletes_expired_drafts_and_those_of_forms_that_keep_none(
    client, workspace, mails
):
    from backend.jobs import tasks

    on = await drafting_form(workspace)
    off = await drafting_form(workspace)
    for form in (on, off):
        await client.put(url(workspace, form), json=body(), cookies=cookies(testUser1))
        await client.put(url(workspace, form), json=body(), cookies=cookies(testUser2))
    old = [
        r
        for r in await draft_rows()
        if r.form_id == str(on.form_id) and r.owner_id == testUser2.id
    ][0]
    old.expires_at = utcnow() - dt.timedelta(seconds=1)
    await container.form_draft_repo().upsert(old)
    await settings_of(workspace, off, allow_save_draft=False)
    assert await tasks.purge_form_drafts(0) == "1 expired, 2 of forms that keep none"
    assert [(r.form_id, r.owner_id) for r in await draft_rows()] == [
        (str(on.form_id), testUser1.id)
    ]
    # nothing to purge: counts only
    assert await tasks.purge_form_drafts(0) == "0 expired, 0 of forms that keep none"


async def test_a_form_that_turned_drafts_off_stops_serving_them_at_once(
    client, workspace, mails
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    sent = (
        await client.post(url(workspace, form, "/link"), json=body(email=ADDRESS))
    ).json()
    token = token_of(mails[0])
    await settings_of(workspace, form, allow_save_draft=False)
    for call in (
        client.post(url(workspace, form, "/mine"), cookies=cookies()),
        client.post(url(workspace, form, "/open"), json={"token": token}),
        client.put(url(workspace, form), json=body(editKey=sent["editKey"])),
    ):
        assert (await call).status_code == 404


def test_the_purge_is_scheduled_daily():
    from backend.jobs import tasks

    assert any(
        p.task.name == "purge_form_drafts" and p.cron == "29 3 * * *"
        for p in tasks.app.periodic_registry.periodic_tasks.values()
    )
