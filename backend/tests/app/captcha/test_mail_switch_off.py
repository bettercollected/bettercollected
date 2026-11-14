"""``CAPTCHA_ENABLED`` off, for what the mail phase adds: the sign-in code sends
and the draft link never read the header (no verification, no claim, no count, no
refusal for a missing or garbage one), the new routes answer 404 (a change of the
workspace default 422), and nothing is counted. Behaviour as before."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.container import container
from backend.app.services.captcha import challenge as ch
from backend.app.services.captcha.mode import DISABLED_CODE
from backend.config import settings
from tests.app.captcha.conftest import ALICE, a_form
from tests.app.form_drafts.helpers import body, drafting_form, url

pytestmark = pytest.mark.usefixtures("off")

SENT = {"message": "Email set to be sent"}
GARBAGE = (None, "garbage", "a.b.c", "x" * 5000)


@pytest.fixture(autouse=True)
def drafts_on(monkeypatch):
    monkeypatch.setattr(settings, "SAVE_DRAFTS_ENABLED", True)


@pytest.fixture()
def never_read(monkeypatch):
    def boom(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("the proof was read")

    monkeypatch.setattr(ch, "check", boom)


def _mailing():
    return patch(
        "common.services.http_client.HttpClient.get", AsyncMock(return_value=SENT)
    )


async def test_the_workspace_code_ignores_the_header(
    client, workspace, claims, never_read
):
    with _mailing() as mailed:
        for index, proof in enumerate(GARBAGE):
            headers = dict(ALICE)
            if proof:
                headers[ch.HEADER] = proof
            sent = await client.post(
                f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
                params={"receiver_email": f"person{index}@example.org"},
                headers=headers,
            )
            assert sent.status_code == 200, sent.text
        assert mailed.await_count == len(GARBAGE)
    assert claims == []


async def test_the_creator_code_ignores_the_header(client, claims, never_read):
    with _mailing() as mailed:
        for index, proof in enumerate(GARBAGE):
            headers = dict(ALICE)
            if proof:
                headers[ch.HEADER] = proof
            sent = await client.post(
                "/api/v1/auth/creator/otp/send",
                params={"receiver_email": f"maker{index}@example.org"},
                headers=headers,
            )
            assert sent.status_code == 200, sent.text
        assert mailed.await_count == len(GARBAGE)
    assert claims == []


async def test_the_draft_link_ignores_the_header(
    client, workspace, claims, never_read, monkeypatch
):
    sent = []

    async def post(self, target, **kwargs):
        sent.append(target)
        return {"message": "Notice queued."}

    monkeypatch.setattr(type(container.http_client()), "post", post)
    form = await drafting_form(workspace)
    for index, proof in enumerate(GARBAGE):
        headers = dict(ALICE)
        if proof:
            headers[ch.HEADER] = proof
        answer = await client.post(
            url(workspace, form, "/link"),
            json=body(email=f"person{index}@example.org"),
            headers=headers,
        )
        assert answer.status_code == 200, answer.text
    assert len(sent) == len(GARBAGE) and claims == []


async def test_the_challenge_routes_answer_404_before_anything(client, workspace):
    form = await a_form(workspace)
    for target, payload in (
        (f"/api/v1/workspaces/{workspace.id}/captcha/challenge", {"purpose": "mail"}),
        (
            f"/api/v1/workspaces/{workspace.id}/captcha/challenge",
            {"purpose": "mail", "formId": str(form.form_id)},
        ),
        ("/api/v1/auth/captcha/challenge", {"purpose": "mail"}),
    ):
        answer = await client.post(target, json=payload, headers=ALICE)
        assert answer.status_code == 404 and answer.json()["code"] == "captcha_off"
    pressure = container.captcha_service().pressure
    assert not pressure._asked._keys and not pressure._issued._keys


async def test_the_default_and_the_counts_are_not_offered(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    base = f"/api/v1/workspaces/{workspace.id}"
    for target in (
        f"{base}/captcha/settings",
        f"{base}/captcha/stats",
        f"{base}/forms/{form.form_id}/captcha/stats",
    ):
        answer = await client.get(target, cookies=test_user_cookies)
        assert answer.status_code == 404 and answer.json()["code"] == "captcha_off"
    refused = await client.put(
        f"{base}/captcha/settings",
        json={"captchaDefault": False},
        cookies=test_user_cookies,
    )
    assert refused.status_code == 422 and refused.json()["code"] == DISABLED_CODE
    # nothing stored, nothing recorded
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.captcha_default is None
    assert not any(e.event == "captcha_setting_changed" for e in await container.workspace_audit_repo().many())


async def test_a_stored_default_is_kept_but_neither_served_nor_enforced(
    client, workspace, claims
):
    form = await a_form(workspace)
    stored = await container.workspace_repo().find_by_id(workspace.id)
    await container.workspace_repo().set_fields(stored, {"captcha_default": False})
    read = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true"
    served = (await client.get(read)).json()["settings"]
    assert served.get("captchaRequired") is None
    assert (await container.workspace_repo().find_by_id(workspace.id)).captcha_default is False
    assert container.captcha_stats()._waiting == {}


async def test_nothing_is_counted_while_off(client, workspace):
    stats = container.captcha_stats()
    before = dict(stats._waiting)
    with _mailing():
        await client.post(
            "/api/v1/auth/creator/otp/send",
            params={"receiver_email": "maker@example.org"},
            headers=ALICE,
        )
        await client.post(
            f"/api/v1/workspaces/{workspace.id}/auth/otp/send",
            params={"receiver_email": "person@example.org"},
            headers=ALICE,
        )
    assert stats._waiting == before
