"""Saving, reopening and discarding a draft over HTTP: signed-in respondents by
account, anonymous ones by the emailed link and the browser's edit key. A draft
is encrypted at rest and bound to its form, workspace and id."""

import base64
import datetime as dt

import pytest
from common.clock import utcnow

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.form_drafts import limits
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.form_drafts.helpers import (
    ANSWERS,
    POSITION,
    body,
    cookies,
    draft_ciphertexts,
    draft_rows,
    drafting_form,
    republish,
    settings_of,
    token_of,
    url,
)
from tests.app.registration.helpers import publish

pytestmark = pytest.mark.asyncio

ADDRESS = "ada.respondent@example.org"


async def test_the_setting_is_off_by_default_and_a_form_without_it_keeps_no_drafts(
    client, workspace
):
    form = await publish(workspace)
    for call in (
        client.put(url(workspace, form), json=body(), cookies=cookies()),
        client.post(url(workspace, form, "/mine"), cookies=cookies()),
        client.post(url(workspace, form, "/link"), json=body(email=ADDRESS)),
    ):
        refused = await call
        assert refused.status_code == 404, refused.text
        assert refused.json()["code"] == "drafts_off"
    assert await draft_rows() == []


async def test_a_signed_in_respondent_saves_one_draft_per_form_and_reopens_it(
    client, workspace
):
    form = await drafting_form(workspace)
    first = await client.put(url(workspace, form), json=body(), cookies=cookies())
    assert first.status_code == 200, first.text
    changed = {"name": {"type": "text", "text": "Ada, changed"}}
    second = await client.put(
        url(workspace, form), json=body(changed), cookies=cookies()
    )
    assert second.status_code == 200
    assert len(await draft_rows()) == 1
    mine = await client.post(url(workspace, form, "/mine"), cookies=cookies())
    assert mine.status_code == 200
    opened = mine.json()
    assert opened["answers"] == changed
    assert opened["hiddenFields"] == {"source": "newsletter"}
    assert opened["position"] == POSITION
    assert opened["formChanged"] is False and "editKey" not in opened
    # another account has none
    other = await client.post(url(workspace, form, "/mine"), cookies=cookies(testUser2))
    assert other.status_code == 404 and other.json()["code"] == "draft_not_found"


async def test_a_draft_is_encrypted_with_the_response_keyset_and_bound_to_itself(
    client, workspace
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    stored = draft_ciphertexts([row])
    for secret in ("Ada Example", "synthetic story", "newsletter", "A synthetic"):
        assert secret not in stored
    raw = base64.b64decode(row.payload)
    assert raw.startswith(b"v1:")
    from common.services.crypto_service import UnreadableCiphertext, crypto_service

    plain = crypto_service.decrypt(
        str(workspace.id), str(form.form_id), raw, f"draft|{row.id}".encode()
    )
    assert b"Ada Example" in plain
    # not under the response context, another draft's, another workspace's or form's
    for ws, fm, context in (
        (workspace.id, form.form_id, b""),
        (workspace.id, form.form_id, b"draft|0123456789abcdef01234567"),
        ("another-workspace", form.form_id, f"draft|{row.id}".encode()),
        (workspace.id, "another-form", f"draft|{row.id}".encode()),
    ):
        with pytest.raises(UnreadableCiphertext):
            crypto_service.decrypt(str(ws), str(fm), raw, context)


async def test_a_ciphertext_moved_to_another_draft_is_not_readable(client, workspace):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies(testUser1))
    await client.put(url(workspace, form), json=body({}), cookies=cookies(testUser2))
    one, two = sorted(await draft_rows(), key=lambda r: r.owner_id != testUser1.id)
    two.payload = one.payload
    await container.form_draft_repo().save(two)
    moved = await client.post(url(workspace, form, "/mine"), cookies=cookies(testUser2))
    assert moved.status_code == 404


async def test_a_body_that_is_too_large_or_malformed_is_refused_cleanly(
    client, workspace
):
    form = await drafting_form(workspace)
    huge = {"big": {"type": "text", "text": "x" * (limits.MAX_PAYLOAD_BYTES + 10)}}
    refused = await client.put(url(workspace, form), json=body(huge), cookies=cookies())
    assert refused.status_code == 413 and refused.json()["code"] == "draft_too_large"
    deep = {}
    node = deep
    for _ in range(40):
        node["a"] = {}
        node = node["a"]
    assert (
        await client.put(url(workspace, form), json=body(deep), cookies=cookies())
    ).status_code == 413
    bad = await client.put(
        url(workspace, form),
        content=b"{not json",
        cookies=cookies(),
        headers={"content-type": "application/json"},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_draft"
    nested = b"[" * 5000 + b"]" * 5000
    assert (
        await client.put(
            url(workspace, form),
            content=nested,
            cookies=cookies(),
            headers={"content-type": "application/json"},
        )
    ).status_code == 422
    unknown = await client.put(
        url(workspace, form), json={**body(), "extra": 1}, cookies=cookies()
    )
    assert unknown.status_code == 422
    assert await draft_rows() == []


async def test_every_draft_response_is_marked_uncacheable(client, workspace):
    form = await drafting_form(workspace)
    saved = await client.put(url(workspace, form), json=body(), cookies=cookies())
    mine = await client.post(url(workspace, form, "/mine"), cookies=cookies())
    for response in (saved, mine):
        assert response.headers["cache-control"] == "no-store"


async def test_the_retention_is_the_forms_with_an_absolute_cap(
    client, workspace, monkeypatch
):
    now = utcnow()
    form = await drafting_form(workspace, draft_retention_days=10)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    assert (
        dt.timedelta(days=9, hours=23)
        < row.expires_at - now
        < dt.timedelta(days=10, minutes=5)
    )
    # the default, without the setting
    await settings_of(workspace, form, draft_retention_days=None)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    assert (
        dt.timedelta(days=29, hours=23)
        < row.expires_at - now
        < dt.timedelta(days=30, minutes=5)
    )
    # saving again and again never goes past 90 days from the first save
    row.created_at = now - dt.timedelta(days=85)
    await container.form_draft_repo().upsert(row)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    assert row.expires_at - now < dt.timedelta(days=5, minutes=5)


async def test_a_fixed_retention_date_of_the_form_caps_its_drafts(client, workspace):
    form = await drafting_form(workspace)
    day = (utcnow() + dt.timedelta(days=3)).date()
    await settings_of(
        workspace,
        form,
        response_expiration_type="date",
        response_expiration=day.isoformat(),
    )
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    assert row.expires_at <= dt.datetime(
        day.year, day.month, day.day, tzinfo=dt.timezone.utc
    )
    # a date that is today or past could keep no draft at all
    gone = (utcnow() - dt.timedelta(days=1)).date()
    await settings_of(
        workspace,
        form,
        response_expiration_type="date",
        response_expiration=gone.isoformat(),
    )
    refused = await client.put(
        url(workspace, form), json=body(), cookies=cookies(testUser2)
    )
    assert refused.status_code == 409 and refused.json()["code"] == "drafts_off"


async def test_an_expired_draft_cannot_be_opened(client, workspace):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    (row,) = await draft_rows()
    row.expires_at = utcnow() - dt.timedelta(seconds=1)
    await container.form_draft_repo().upsert(row)
    gone = await client.post(url(workspace, form, "/mine"), cookies=cookies())
    assert gone.status_code == 404


async def test_a_changed_form_opens_with_a_notice(client, workspace):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await republish(workspace, form)
    opened = (
        await client.post(url(workspace, form, "/mine"), cookies=cookies())
    ).json()
    assert opened["formChanged"] is True
    assert opened["currentVersion"] == opened["formVersion"] + 1
    assert opened["answers"] == ANSWERS


async def test_a_form_that_stopped_taking_responses_hands_back_no_answers(
    client, workspace
):
    form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    await settings_of(
        workspace,
        form,
        form_close_date=(utcnow() - dt.timedelta(minutes=1)).isoformat(),
    )
    closed = (
        await client.post(url(workspace, form, "/mine"), cookies=cookies())
    ).json()
    assert closed["unavailable"] == "closed" and "answers" not in closed
    refused = await client.put(url(workspace, form), json=body(), cookies=cookies())
    assert refused.status_code == 409 and refused.json()["code"] == "form_closed"
    # not open yet, and full
    await settings_of(
        workspace,
        form,
        form_close_date=None,
        form_open_date=(utcnow() + dt.timedelta(days=1)).isoformat(),
    )
    assert (await client.post(url(workspace, form, "/mine"), cookies=cookies())).json()[
        "unavailable"
    ] == "not_yet_open"
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).json()["code"] == "form_not_open"
    await settings_of(workspace, form, form_open_date=None, response_limit=1)
    await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={}),
        testUser2,
    )
    assert (await client.post(url(workspace, form, "/mine"), cookies=cookies())).json()[
        "unavailable"
    ] == "full"
    assert (
        await client.put(url(workspace, form), json=body(), cookies=cookies())
    ).json()["code"] == "form_full"


async def test_a_private_form_is_not_reachable_to_a_respondent_it_does_not_admit(
    client, workspace
):
    form = await drafting_form(workspace, private=True)
    refused = await client.put(
        url(workspace, form), json=body(), cookies=cookies(testUser2)
    )
    assert refused.status_code == 404
    assert await draft_rows() == []


async def test_a_draft_is_found_only_through_its_own_workspace_and_form(
    client, workspace, workspace_1
):
    form = await drafting_form(workspace)
    other_form = await drafting_form(workspace)
    await client.put(url(workspace, form), json=body(), cookies=cookies())
    # the same account asking for another form of the workspace has no draft
    assert (
        await client.post(url(workspace, other_form, "/mine"), cookies=cookies())
    ).status_code == 404
    # and the form id under another workspace's path is not a form of it
    elsewhere = await client.post(
        f"/api/v1/workspaces/{workspace_1.id}/forms/{form.form_id}/drafts/mine",
        cookies=cookies(),
    )
    assert elsewhere.status_code == 404
    discarded = await client.post(
        f"/api/v1/workspaces/{workspace_1.id}/forms/{form.form_id}/drafts/discard",
        json={},
        cookies=cookies(),
    )
    assert discarded.status_code == 404
    assert len(await draft_rows()) == 1
