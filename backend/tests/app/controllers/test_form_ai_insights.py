"""Response summaries & insights — opt-in, anonymised by construction."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardChoice,
    StandardFieldProperty,
    StandardFormField,
    StandardFormFieldType,
    StandardFormResponse,
)

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from tests.app.controllers.data import testUser


class FakeProvider:
    def __init__(self):
        self.replies = []
        self.calls = []

    async def chat(self, system: str, messages: list) -> str:
        self.calls.append({"system": system, "messages": messages})
        return self.replies.pop(0)


@pytest.fixture()
def fake_insights_provider(monkeypatch):
    fake = FakeProvider()
    service = container.form_ai_insights_service()
    monkeypatch.setattr(service, "_provider_resolver", lambda name: fake)
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


async def _seed_form_and_responses(workspace_id, form_id: str) -> None:
    """Give the fixture form real questions and three answered responses."""
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

        document = await FormAIInsightDocument.find_one(
            FormAIInsightDocument.form_id == workspace_form.form_id
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
    ):
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
            await FormAIInsightDocument.find_one(
                FormAIInsightDocument.form_id == workspace_form.form_id
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
                roles=[WorkspaceRoles.COLLABORATOR],
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
