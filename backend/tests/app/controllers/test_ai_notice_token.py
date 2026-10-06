"""#752: a response is analysed by AI insights only when the respondent's page
showed the AI notice, proven by the signed token the public form fetch hands
out and the form page sends back on submit."""

import datetime as dt
import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai import notice_token
from backend.app.services.workspace_form_service import _question_ids
from backend.config import settings
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider

ENABLED_AT = dt.datetime(2026, 10, 1, 9, 0, 0, 123000, tzinfo=dt.timezone.utc)
CLAIMS = dict(
    workspace_id="6ac4fe01c5f99a0c65ac3275",
    form_id="6ac4fe01c5f99a0c65ac3278",
    provider="openai",
    provider_name="OpenAI",
    enabled_at=ENABLED_AT,
)
INSIGHTS_REPLY = json.dumps(
    {"summary": "Fine.", "themes": [], "actionable": [], "sentiment": None}
)


def _token(now=None, **overrides):
    return notice_token.issue_token(**{**CLAIMS, **overrides}, now=now)


def _shown(token, now=None, **overrides):
    return notice_token.shown_at(token, **{**CLAIMS, **overrides}, now=now)


class TestTheToken:
    def test_a_token_names_when_the_notice_was_shown(self):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        token = _token(now=issued)
        later = issued + dt.timedelta(hours=3)
        assert _shown(token, now=later) == issued

    @pytest.mark.parametrize(
        "other",
        [
            {"form_id": "6ac4fe01c5f99a0c65ac3279"},
            {"workspace_id": "6ac4fe01c5f99a0c65ac3276"},
            {"provider_name": "Google Gemini"},
            {"provider": "google"},
            # the setting was turned off and on again since
            {"enabled_at": ENABLED_AT + dt.timedelta(days=1)},
        ],
    )
    def test_a_token_for_anything_else_is_ignored(self, other):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        token = _token(now=issued)
        assert _shown(token, now=issued, **other) is None

    def test_an_expired_token_is_ignored(self):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        token = _token(now=issued)
        assert _shown(token, now=issued + dt.timedelta(hours=23, minutes=59))
        assert _shown(token, now=issued + dt.timedelta(hours=24, seconds=1)) is None

    def test_a_token_from_the_future_or_before_the_setting_is_ignored(self):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        assert _shown(_token(now=issued), now=issued - dt.timedelta(hours=1)) is None
        before = ENABLED_AT - dt.timedelta(seconds=1)
        assert _shown(_token(now=before), now=ENABLED_AT) is None

    @pytest.mark.parametrize(
        "mangle",
        [
            lambda t: t[:-2] + ("AA" if not t.endswith("AA") else "BB"),
            lambda t: t.replace("v1.", "v2.", 1),
            lambda t: t.split(".")[0] + "." + t.split(".")[1],
            lambda t: "not-a-token",
            lambda t: "v1.%%%.%%%",
            lambda t: "v1." + "A" * 5000 + ".x",
            lambda t: "",
            lambda t: None,
        ],
    )
    def test_a_forged_or_malformed_token_is_ignored(self, mangle):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        assert _shown(mangle(_token(now=issued)), now=issued) is None

    def test_a_changed_claim_breaks_the_signature(self):
        import base64

        issued = ENABLED_AT + dt.timedelta(hours=1)
        version, payload, signature = _token(now=issued).split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        claims["n"] = "Google Gemini"
        forged = base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        token = f"{version}.{forged}.{signature}"
        assert _shown(token, now=issued, provider_name="Google Gemini") is None

    def test_without_a_server_secret_nothing_is_issued_or_accepted(
        self, monkeypatch
    ):
        issued = ENABLED_AT + dt.timedelta(hours=1)
        token = _token(now=issued)
        monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", "")
        assert _token(now=issued) is None
        assert _shown(token, now=issued) is None


def _public_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"


def _insights_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/ai/insights"


async def _allow(client, workspace, form_id, cookies, enabled=True):
    response = await client.put(
        f"{_insights_url(workspace, form_id)}/settings",
        cookies=cookies,
        json={"enabled": enabled},
    )
    assert response.status_code == 200, response.text


async def _page_token(client, workspace, form_id):
    """What the respondent's form page receives with the published form."""
    page = await client.get(
        _public_url(workspace, form_id), params={"published": "true"}
    )
    assert page.status_code == 200, page.text
    return page.json().get("aiNoticeToken")


async def _submit(client, workspace, form_id, token=None, text="An answer", body=None):
    data = {
        "response": json.dumps(
            {"answers": {"q": {"type": "text", "text": text}}, **(body or {})}
        )
    }
    if token is not None:
        data["ai_notice_token"] = token
    submitted = await client.post(
        f"{_public_url(workspace, form_id)}/response", data=data
    )
    assert submitted.status_code == 200, submitted.text
    return await container.form_response_repo().get_by_submission_uuid(
        submitted.json()
    )


@pytest.fixture()
async def ai_on(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


class TestSubmissions:
    async def test_a_page_showing_the_notice_stamps_the_response(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        form_id = published_form.form_id
        # no notice on the page, no token
        assert await _page_token(client, workspace, form_id) is None

        await _allow(client, workspace, form_id, test_user_cookies)
        token = await _page_token(client, workspace, form_id)
        assert token
        before = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5)
        stored = await _submit(client, workspace, form_id, token)
        assert stored.ai_notice_provider_name == "OpenAI"
        shown = stored.ai_notice_shown_at
        shown = shown if shown.tzinfo else shown.replace(tzinfo=dt.timezone.utc)
        assert shown >= before

    async def test_a_page_loaded_before_the_setting_is_never_analysed(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        form_id = published_form.form_id
        stale_page_token = await _page_token(client, workspace, form_id)
        assert stale_page_token is None
        await _allow(client, workspace, form_id, test_user_cookies)

        # submitted after the setting was on, from the page loaded before it
        early = await _submit(client, workspace, form_id, stale_page_token, "EARLY")
        assert early.ai_notice_shown_at is None
        assert early.ai_notice_provider_name is None

        ai_on.replies = [INSIGHTS_REPLY]
        refused = await client.post(
            _insights_url(workspace, form_id), cookies=test_user_cookies, json={}
        )
        assert refused.status_code == 400
        assert ai_on.calls == []

        await _submit(
            client,
            workspace,
            form_id,
            await _page_token(client, workspace, form_id),
            "WITH-NOTICE",
        )
        analysed = await client.post(
            _insights_url(workspace, form_id), cookies=test_user_cookies, json={}
        )
        assert analysed.status_code == 200, analysed.text
        body = analysed.json()
        assert body["responseCount"] == 1 and body["totalResponses"] == 2
        assert body["noticeShownResponses"] == 1
        sent = json.dumps(ai_on.calls)
        assert "WITH-NOTICE" in sent and "EARLY" not in sent

    async def test_a_token_from_before_the_setting_was_renewed_is_ignored(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        form_id = published_form.form_id
        await _allow(client, workspace, form_id, test_user_cookies)
        token = await _page_token(client, workspace, form_id)
        await _allow(client, workspace, form_id, test_user_cookies, enabled=False)
        # while off, a token is neither issued nor accepted
        assert await _page_token(client, workspace, form_id) is None
        assert (await _submit(client, workspace, form_id, token)).ai_notice_shown_at is None
        await _allow(client, workspace, form_id, test_user_cookies)
        assert (await _submit(client, workspace, form_id, token)).ai_notice_shown_at is None

    async def test_tokens_for_another_form_or_expired_ones_are_ignored(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        form_id = published_form.form_id
        await _allow(client, workspace, form_id, test_user_cookies)
        association = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        current = association.settings
        claims = dict(
            workspace_id=workspace.id,
            provider=current.ai_insights_provider,
            provider_name=current.ai_insights_provider_name,
            enabled_at=current.ai_insights_enabled_at,
        )
        other_form = notice_token.issue_token(form_id="6ac4fe01c5f99a0c65ac3299", **claims)
        expired = notice_token.issue_token(
            form_id=form_id,
            **claims,
            now=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25),
        )
        other_name = notice_token.issue_token(
            form_id=form_id, **{**claims, "provider_name": "Google Gemini"}
        )
        for token in (other_form, expired, other_name, "garbage"):
            stored = await _submit(client, workspace, form_id, token)
            assert stored.ai_notice_shown_at is None, token

    async def test_the_body_cannot_claim_the_notice(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        form_id = published_form.form_id
        await _allow(client, workspace, form_id, test_user_cookies)
        claimed = {
            "aiNoticeShownAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "aiNoticeProviderName": "OpenAI",
            "ai_notice_shown_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "ai_notice_provider_name": "OpenAI",
        }
        stored = await _submit(client, workspace, form_id, body=claimed)
        assert stored.ai_notice_shown_at is None
        assert stored.ai_notice_provider_name is None

    async def test_an_edit_never_adds_the_stamp_and_keeps_an_existing_one(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
        workspace_form_response: Coroutine[Any, Any, dict],
        test_user_cookies: dict[str, str],
        ai_on: FakeProvider,
    ):
        """An edit merges answers: stamping it would make answers given before
        the notice existed analysable. It keeps whatever the submission got."""
        common_url = f"/api/v1/workspaces/{workspace.id}"
        form_id = published_form.form_id
        allowed = await client.patch(
            f"{common_url}/forms/{form_id}/settings",
            json={"require_verified_identity": True, "allow_editing_response": True},
            cookies=test_user_cookies,
        )
        assert allowed.status_code == 200, allowed.text
        question = sorted(_question_ids(published_form.fields))[0]
        claimed = {
            "aiNoticeShownAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "aiNoticeProviderName": "Google Gemini",
        }

        async def edit(response_id, token=None, extra=None):
            data = {
                "response": json.dumps(
                    {
                        "answers": {question: {"field": {"id": question}, "text": "x"}},
                        **(extra or {}),
                    }
                )
            }
            if token is not None:
                data["ai_notice_token"] = token
            edited = await client.patch(
                f"{common_url}/forms/{form_id}/response/{response_id}",
                data=data,
                cookies=test_user_cookies,
            )
            assert edited.status_code == 200, edited.text
            return await container.form_response_repo().get_response(response_id)

        # submitted before AI insights were allowed: an edit from a page that
        # shows the notice, with a valid token, still adds no stamp
        before = workspace_form_response["response_id"]
        await _allow(client, workspace, form_id, test_user_cookies)
        token = await _page_token(client, workspace, form_id)
        assert token
        stored = await edit(before, token)
        assert stored.ai_notice_shown_at is None
        assert stored.ai_notice_provider_name is None
        stored = await edit(before, token, extra=claimed)
        assert stored.ai_notice_shown_at is None
        assert stored.ai_notice_provider_name is None

        # submitted with the notice: an edit keeps the stamp as it was,
        # whatever the body claims and with or without a token
        submitted = await client.post(
            f"{_public_url(workspace, form_id)}/response",
            data={
                "response": json.dumps({"answers": {}}),
                "ai_notice_token": token,
            },
            cookies=test_user_cookies,
        )
        assert submitted.status_code == 200, submitted.text
        stamped = await container.form_response_repo().get_by_submission_uuid(
            submitted.json()
        )
        assert stamped.ai_notice_provider_name == "OpenAI"
        for kwargs in ({}, {"extra": claimed}, {"token": token}):
            stored = await edit(stamped.response_id, **kwargs)
            assert stored.ai_notice_provider_name == "OpenAI"
            assert stored.ai_notice_shown_at == stamped.ai_notice_shown_at
