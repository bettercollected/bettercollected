"""Response summaries & insights — opt-in, anonymised by construction."""

import datetime as dt
import json
import uuid
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.services.crypto_service import crypto_service
from common.models.standard_form import (
    StandardChoice,
    StandardFieldProperty,
    StandardFormField,
    StandardFormFieldType,
    StandardFormResponse,
)

from backend.app.container import container
from tests.app.ai_helpers import (
    FakeProvider,
    allow_insights,
    enable_ai,
    use_fake_provider,
)
from backend.app.models.dtos.request_dtos import AIProvider
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import testUser


@pytest.fixture()
async def fake_insights_provider(monkeypatch, workspace):
    # AI on for the fixture workspace (#715); the provider is a fake
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


INSIGHTS_REPLY = {
    "summary": "Respondents are broadly happy with onboarding but struggle with billing.",
    "themes": [
        {
            "title": "Billing confusion",
            "description": "Several responses mention unclear invoices.",
            "approxCount": 2,
        },
        {
            "title": "Smooth onboarding",
            "description": "Setup is repeatedly called easy.",
            "approxCount": 2,
        },
    ],
    "actionable": ["Clarify the invoice layout."],
    "sentiment": "Mostly positive with one recurring frustration.",
}


async def _seed_form_and_responses(
    workspace_id, form_id: str, allow: bool = True
) -> None:
    """Give the fixture form real questions and three answered responses,
    submitted after AI insights were allowed for it (unless ``allow`` is
    False)."""
    if allow:
        await allow_insights(workspace_id, form_id)
    form_doc = await container.form_repo().get_form_document_by_id(form_id)
    form_doc.fields = [
        StandardFormField(
            id="page-1",
            index=0,
            type=StandardFormFieldType.SLIDE,
            properties=StandardFieldProperty(
                fields=[
                    StandardFormField(
                        id="q-feedback",
                        index=0,
                        type=StandardFormFieldType.LONG_TEXT,
                        title="Any feedback?",
                        properties=StandardFieldProperty(fields=[]),
                    ),
                    StandardFormField(
                        id="q-email",
                        index=1,
                        type=StandardFormFieldType.EMAIL,
                        title="Your email?",
                        properties=StandardFieldProperty(fields=[]),
                    ),
                    StandardFormField(
                        id="q-score",
                        index=2,
                        type=StandardFormFieldType.NUMBER,
                        title="Score 1-10?",
                        properties=StandardFieldProperty(fields=[]),
                    ),
                    StandardFormField(
                        id="q-plan",
                        index=3,
                        type=StandardFormFieldType.DROPDOWN,
                        title="Which plan are you on?",
                        properties=StandardFieldProperty(
                            fields=[],
                            choices=[
                                StandardChoice(id="choice-free", value="Free"),
                                StandardChoice(id="choice-pro", value="Pro"),
                            ],
                        ),
                    ),
                ]
            ),
        )
    ]
    await container.form_repo().save_form(form_doc)

    answer_sets = [
        {
            "q-feedback": {
                "type": "text",
                "text": "Onboarding was easy but the invoice is confusing.",
            },
            "q-email": {"type": "email", "email": "alice@example.com"},
            "q-score": {"type": "number", "number": 8},
            # Responses store choice IDs — the projection must resolve labels.
            "q-plan": {"type": "choice", "choice": {"value": "choice-pro"}},
        },
        {
            "q-feedback": {
                "type": "text",
                "text": "Billing page needs work, rest is great.",
            },
            "q-email": {"type": "email", "email": "bob@example.com"},
            "q-score": {"type": "number", "number": 7},
        },
        {
            "q-feedback": {
                "type": "text",
                "text": "Setup took five minutes. Loved it.",
            },
            "q-email": {"type": "email", "email": "carol@example.com"},
            "q-score": {"type": "number", "number": 10},
        },
    ]
    for answers in answer_sets:
        await container.form_response_service().submit_form_response(
            form_id, StandardFormResponse(answers=answers), workspace_id
        )


class TestFormAIInsights:
    async def test_generate_is_grounded_anonymised_and_cached(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        fake_insights_provider.replies = [json.dumps(INSIGHTS_REPLY)]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/insights",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["summary"].startswith("Respondents are broadly happy")
        assert body["themes"][0]["title"] == "Billing confusion"
        assert body["responseCount"] == 3
        assert body["totalResponses"] == 3

        # The prompt saw questions and answer text…
        prompt = fake_insights_provider.calls[0]["messages"][0]["content"]
        assert "Any feedback?" in prompt
        assert "invoice is confusing" in prompt
        # …but NEVER the email addresses — redacted at projection time, the
        # model cannot leak what it never received.
        assert "alice@example.com" not in prompt
        assert "bob@example.com" not in prompt
        assert "[email provided]" in prompt
        assert "alice@example.com" not in fake_insights_provider.calls[0]["system"]
        # Choice answers arrive as IDs; the model must see the human label.
        assert "Pro" in prompt
        assert "choice-pro" not in prompt

        # Cached: GET returns it without another model call.
        cached = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/insights",
            cookies=test_user_cookies,
        )
        assert cached.status_code == 200
        assert cached.json()["summary"] == body["summary"]
        assert len(fake_insights_provider.calls) == 1

        document = await container.form_ai_insight_repo().find(
            workspace.id, workspace_form.form_id
        )
        assert document is not None and document.response_count == 3

    async def test_get_without_generation_returns_empty(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/insights",
            cookies=test_user_cookies,
        )
        assert response.status_code == 200
        assert response.json() is None

    async def test_no_responses_is_a_clear_400(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await allow_insights(workspace.id, workspace_form.form_id)
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/insights",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 400
        assert "no responses" in response.text.lower()

    async def test_unusable_model_reply_is_a_502_and_nothing_cached(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        fake_insights_provider.replies = ["The responses look nice overall!"]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/insights",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 502
        assert (
            await container.form_ai_insight_repo().find(
                workspace.id, workspace_form.form_id
            )
            is None
        )


class TestAIFormAccessIsWorkspaceScoped:
    """REGRESSION: access to workspace B must not unlock workspace A's forms
    by id — every AI surface 404s on a foreign form."""

    async def test_all_ai_endpoints_404_on_foreign_form(
        self,
        client: AsyncClient,
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        # Make the caller a member of workspace_1 so plain workspace access
        # passes — the form-belongs-to-workspace check must be what stops it.
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(
                workspace_id=workspace_1.id,
                user_id=testUser.id,
                roles=[WorkspaceRoles.ADMIN],
            )
        )
        foreign = workspace_form.form_id
        calls = [
            (
                "post",
                f"/api/v1/workspaces/{workspace_1.id}/forms/{foreign}/ai/chat",
                {"message": "hi"},
            ),
            (
                "post",
                f"/api/v1/workspaces/{workspace_1.id}/forms/{foreign}/ai/review",
                {},
            ),
            (
                "post",
                f"/api/v1/workspaces/{workspace_1.id}/forms/{foreign}/ai/review/apply",
                {"ops": [{"op": "remove_field", "fieldId": "x"}]},
            ),
            (
                "post",
                f"/api/v1/workspaces/{workspace_1.id}/forms/{foreign}/ai/insights",
                {},
            ),
            (
                "get",
                f"/api/v1/workspaces/{workspace_1.id}/forms/{foreign}/ai/insights",
                None,
            ),
        ]
        for method, url, body in calls:
            if method == "get":
                response = await client.get(url, cookies=test_user_cookies)
            else:
                response = await client.post(url, cookies=test_user_cookies, json=body)
            assert (
                response.status_code == 404
            ), f"{method.upper()} {url} -> {response.status_code}: {response.text}"


def _insights_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/ai/insights"


async def _submit(workspace_id, form_id, answers):
    await container.form_response_service().submit_form_response(
        form_id, StandardFormResponse(answers=answers), workspace_id
    )


class TestInsightsConsent:
    """#716: the workspace opt-in, the form's own setting, admins only, and
    only responses submitted after respondents saw the notice."""

    async def test_refused_without_the_form_setting(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(
            workspace.id, workspace_form.form_id, allow=False
        )
        response = await client.post(
            _insights_url(workspace, workspace_form.form_id),
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ai_insights_not_enabled"
        assert fake_insights_provider.calls == []

    async def test_refused_without_the_workspace_opt_in(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        from tests.app.ai_helpers import disable_ai

        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        await disable_ai(workspace)
        response = await client.post(
            _insights_url(workspace, workspace_form.form_id),
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ai_not_enabled"
        assert fake_insights_provider.calls == []

    async def test_admins_only(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_invited_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        url = _insights_url(workspace, workspace_form.form_id)
        collaborator = test_invited_user_cookies
        assert (
            await client.post(url, cookies=collaborator, json={})
        ).status_code == 403
        assert (await client.get(url, cookies=collaborator)).status_code == 403
        settings = await client.put(
            f"{url}/settings", cookies=collaborator, json={"enabled": False}
        )
        assert settings.status_code == 403
        assert fake_insights_provider.calls == []

    async def test_the_setting_is_admin_only_recorded_and_needs_the_opt_in(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        url = f"{_insights_url(workspace, workspace_form.form_id)}/settings"
        # workspace AI is off: the form setting cannot be turned on
        refused = await client.put(
            url, cookies=test_user_cookies, json={"enabled": True}
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == "ai_not_enabled"

        await enable_ai(workspace)
        enabled = await client.put(
            url, cookies=test_user_cookies, json={"enabled": True}
        )
        assert enabled.status_code == 200, enabled.text
        body = enabled.json()
        assert body["enabled"] is True and body["providerName"] == "OpenAI"
        assert body["enabledBy"] == testUser.id and body["enabledAt"]
        stored = await container.workspace_form_repo().find_workspace_form(
            workspace.id, workspace_form.form_id
        )
        assert stored.settings.ai_insights_enabled is True
        assert stored.settings.ai_insights_provider == "openai"
        assert stored.settings.ai_insights_enabled_by == testUser.id
        assert stored.settings.ai_insights_enabled_at

        disabled = await client.put(
            url, cookies=test_user_cookies, json={"enabled": False}
        )
        assert disabled.json()["enabled"] is False
        stored = await container.workspace_form_repo().find_workspace_form(
            workspace.id, workspace_form.form_id
        )
        assert not stored.settings.ai_insights_enabled
        assert stored.settings.ai_insights_provider_name is None

    async def test_respondents_see_the_notice_naming_the_provider(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form,
        test_user_cookies: dict[str, str],
    ):
        form_id = published_form.form_id
        public_url = f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"
        before = await client.get(public_url, params={"published": "true"})
        assert not (before.json().get("settings") or {}).get("aiInsightsEnabled")

        await enable_ai(workspace)
        await client.put(
            f"{_insights_url(workspace, form_id)}/settings",
            cookies=test_user_cookies,
            json={"enabled": True},
        )
        public = await client.get(public_url, params={"published": "true"})
        assert public.status_code == 200
        settings = public.json()["settings"]
        assert settings["aiInsightsEnabled"] is True
        assert settings["aiInsightsProviderName"] == "OpenAI"
        # who allowed it is staff information, never sent to respondents
        assert settings.get("aiInsightsEnabledBy") is None

    async def test_only_responses_after_the_notice_and_nothing_sensitive(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        form_id = workspace_form.form_id
        # three responses before the setting was turned on
        await _seed_form_and_responses(workspace.id, form_id, allow=False)
        form_doc = await container.form_repo().get_form_document_by_id(form_id)
        page = form_doc.fields[0]
        page.properties.fields += [
            StandardFormField(
                id="q-phone",
                index=4,
                type=StandardFormFieldType.PHONE_NUMBER,
                title="Your phone?",
                properties=StandardFieldProperty(fields=[]),
            ),
            StandardFormField(
                id="q-staff",
                index=5,
                type=StandardFormFieldType.SHORT_TEXT,
                title="Case worker notes",
                properties=StandardFieldProperty(fields=[]),
            ),
        ]
        await container.form_repo().save_form(form_doc)

        await allow_insights(workspace.id, form_id)
        await _submit(
            workspace.id,
            form_id,
            {
                "q-feedback": {"type": "text", "text": "After the notice: all good."},
                "q-email": {"type": "email", "email": "dave@example.com"},
                "q-phone": {"type": "phone_number", "phone_number": "+15550100"},
                "q-staff": {"type": "text", "text": "STAFF-ONLY-VALUE"},
            },
        )
        # the field becomes staff-only after answers were collected for it
        form_doc = await container.form_repo().get_form_document_by_id(form_id)
        form_doc.fields[0].properties.fields[5].internal = True
        await container.form_repo().save_form(form_doc)

        fake_insights_provider.replies = [json.dumps(INSIGHTS_REPLY)]
        response = await client.post(
            _insights_url(workspace, form_id), cookies=test_user_cookies, json={}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["responseCount"] == 1 and body["totalResponses"] == 4
        assert body["analysedSince"]

        sent = json.dumps(fake_insights_provider.calls)
        # only the post-notice response
        assert "After the notice" in sent
        assert "invoice is confusing" not in sent and "Loved it" not in sent
        # no email or phone values, no internal field or its answer
        assert "dave@example.com" not in sent and "+15550100" not in sent
        assert "[email provided]" in sent and "[phone provided]" in sent
        assert "STAFF-ONLY-VALUE" not in sent and "Case worker notes" not in sent

    async def test_no_post_notice_responses_is_a_clear_400(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(
            workspace.id, workspace_form.form_id, allow=False
        )
        await allow_insights(workspace.id, workspace_form.form_id)
        response = await client.post(
            _insights_url(workspace, workspace_form.form_id),
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 400
        assert "since AI insights were allowed" in response.text
        assert fake_insights_provider.calls == []

    async def test_a_changed_workspace_provider_needs_a_fresh_notice(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        await enable_ai(workspace, provider="google")
        response = await client.post(
            _insights_url(workspace, workspace_form.form_id),
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "ai_insights_not_enabled"
        assert fake_insights_provider.calls == []


async def _set_form_provider(workspace_id, form_id, provider: str) -> None:
    association = await container.workspace_form_repo().find_workspace_form(
        workspace_id, form_id
    )
    association.settings.provider = provider
    await container.workspace_form_repo().save(association)


async def _save_imported_response(workspace_id, form_id, answers) -> None:
    """A response the way a provider sync stores it: the provider's own
    timestamp, saved directly (form_import_service), never through submit."""
    now = dt.datetime.now(dt.timezone.utc)
    await container.form_response_repo().save(
        FormResponseDocument(
            response_id=f"google-{uuid.uuid4().hex}",
            form_id=form_id,
            provider="google",
            answers=crypto_service.encrypt(
                workspace_id=workspace_id, form_id=form_id, data=json.dumps(answers)
            ),
            created_at=now,
            updated_at=now,
        )
    )


class TestInsightsOnlyForFormsCollectedHere:
    """An imported form's respondents answered on Google Forms / Typeform and
    never saw the AI notice."""

    async def test_imported_form_refuses_the_setting_and_generate(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        form_id = workspace_form.form_id
        await _seed_form_and_responses(workspace.id, form_id)
        await _save_imported_response(
            workspace.id,
            form_id,
            {"q-feedback": {"type": "text", "text": "Answered on Google."}},
        )
        await _set_form_provider(workspace.id, form_id, "google")
        url = _insights_url(workspace, form_id)

        refused = await client.put(
            f"{url}/settings", cookies=test_user_cookies, json={"enabled": True}
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == "ai_insights_not_enabled"

        fake_insights_provider.replies = [json.dumps(INSIGHTS_REPLY)]
        generated = await client.post(url, cookies=test_user_cookies, json={})
        assert generated.status_code == 403
        assert generated.json()["code"] == "ai_insights_not_enabled"
        assert fake_insights_provider.calls == []
        assert (
            await container.form_ai_insight_repo().find(workspace.id, form_id) is None
        )

        # turning it off stays possible
        off = await client.put(
            f"{url}/settings", cookies=test_user_cookies, json={"enabled": False}
        )
        assert off.status_code == 200 and off.json()["enabled"] is False

    async def test_imported_responses_are_never_analysed(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        form_id = workspace_form.form_id
        await _seed_form_and_responses(workspace.id, form_id)
        # newer than the notice, but imported: the respondent never saw it
        await _save_imported_response(
            workspace.id,
            form_id,
            {"q-feedback": {"type": "text", "text": "IMPORTED-ANSWER"}},
        )

        fake_insights_provider.replies = [json.dumps(INSIGHTS_REPLY)]
        response = await client.post(
            _insights_url(workspace, form_id), cookies=test_user_cookies, json={}
        )
        assert response.status_code == 200, response.text
        assert response.json()["responseCount"] == 3
        sent = json.dumps(fake_insights_provider.calls)
        assert "IMPORTED-ANSWER" not in sent
        assert "invoice is confusing" in sent


class TestInsightsInternalFieldsInEveryVersion:
    async def test_a_field_internal_only_in_an_older_version_is_left_out(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_insights_provider: FakeProvider,
    ):
        form_id = workspace_form.form_id
        await _seed_form_and_responses(workspace.id, form_id)
        form_doc = await container.form_repo().get_form_document_by_id(form_id)
        form_doc.fields[0].properties.fields.append(
            StandardFormField(
                id="q-office",
                index=4,
                type=StandardFormFieldType.SHORT_TEXT,
                title="Office reference",
                internal=True,
                properties=StandardFieldProperty(fields=[]),
            )
        )
        await container.form_repo().save_form(form_doc)
        # v1: internal
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
        form_doc = await container.form_repo().get_form_document_by_id(form_id)
        form_doc.fields[0].properties.fields[4].internal = False
        await container.form_repo().save_form(form_doc)
        # v2 and the draft: public
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
        draft_and_latest = (
            await container.form_response_service().all_internal_field_ids(form_id)
        )
        assert "q-office" not in draft_and_latest

        await _submit(
            workspace.id,
            form_id,
            {
                "q-feedback": {"type": "text", "text": "Fine."},
                "q-office": {"type": "text", "text": "OLD-INTERNAL-VALUE"},
            },
        )
        fake_insights_provider.replies = [json.dumps(INSIGHTS_REPLY)]
        response = await client.post(
            _insights_url(workspace, form_id), cookies=test_user_cookies, json={}
        )
        assert response.status_code == 200, response.text
        sent = json.dumps(fake_insights_provider.calls)
        assert "OLD-INTERNAL-VALUE" not in sent
        assert "Fine." in sent


class TestInsightsCompatibleProviderHost:
    async def test_a_changed_compat_endpoint_needs_a_fresh_notice(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        monkeypatch.setattr(
            settings.ai, "COMPAT_BASE_URL", "http://llm-a.internal:11434/v1"
        )
        monkeypatch.setattr(settings.ai, "COMPAT_MODEL", "local-model")
        fake = FakeProvider()
        monkeypatch.setitem(
            container.openai_service()._providers, AIProvider.COMPATIBLE, fake
        )
        await enable_ai(workspace, provider="compatible")
        form_id = workspace_form.form_id
        url = _insights_url(workspace, form_id)

        enabled = await client.put(
            f"{url}/settings", cookies=test_user_cookies, json={"enabled": True}
        )
        assert enabled.status_code == 200, enabled.text
        assert (
            enabled.json()["providerName"]
            == "this instance's own AI model (llm-a.internal)"
        )
        stored = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        assert stored.settings.ai_insights_provider == "compatible"
        assert (
            stored.settings.ai_insights_provider_name
            == "this instance's own AI model (llm-a.internal)"
        )

        await _seed_form_and_responses(workspace.id, form_id, allow=False)
        fake.replies = [json.dumps(INSIGHTS_REPLY)]
        same_host = await client.post(url, cookies=test_user_cookies, json={})
        assert same_host.status_code == 200, same_host.text
        assert len(fake.calls) == 1

        # same provider id, another endpoint: respondents were told llm-a
        monkeypatch.setattr(
            settings.ai, "COMPAT_BASE_URL", "http://llm-b.example.com/v1"
        )
        moved = await client.post(url, cookies=test_user_cookies, json={})
        assert moved.status_code == 403
        assert moved.json()["code"] == "ai_insights_not_enabled"
        assert len(fake.calls) == 1

        # renewing the setting names the new host to respondents
        renewed = await client.put(
            f"{url}/settings", cookies=test_user_cookies, json={"enabled": True}
        )
        assert (
            renewed.json()["providerName"]
            == "this instance's own AI model (llm-b.example.com)"
        )
