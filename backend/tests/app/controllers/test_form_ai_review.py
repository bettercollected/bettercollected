"""Compliance copilot — review + apply-fix endpoints with a FAKE provider."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument


class FakeProvider:
    def __init__(self):
        self.replies = []
        self.calls = []

    async def chat(self, system: str, messages: list) -> str:
        self.calls.append({"system": system, "messages": messages})
        return self.replies.pop(0)


@pytest.fixture()
def fake_review_provider(monkeypatch):
    fake = FakeProvider()
    service = container.form_ai_review_service()
    monkeypatch.setattr(service, "_provider_resolver", lambda name: fake)
    return fake


async def _make_v2(form_doc: FormDocument) -> str:
    form_doc.fields = [
        StandardFormField(
            id="page-1",
            index=0,
            type=StandardFormFieldType.SLIDE,
            properties=StandardFieldProperty(
                fields=[
                    StandardFormField(
                        id="field-age",
                        index=0,
                        type=StandardFormFieldType.NUMBER,
                        title="What is your exact age?",
                        properties=StandardFieldProperty(fields=[]),
                    )
                ]
            ),
        )
    ]
    await container.form_repo().save_form(form_doc)
    return "page-1"


REVIEW_REPLY = {
    "summary": "One high-severity issue: the form asks for exact age.",
    "findings": [
        {
            "severity": "info",
            "message": "Consider stating a retention period.",
            "fieldId": None,
            "fix": None,
        },
        {
            "severity": "high",
            "message": "Exact age is collected — the compliance profile requires age ranges.",
            "fieldId": "field-age",
            "fix": {
                "description": "Replace with an age-range dropdown",
                # A type change is remove + add — FieldPatch deliberately has
                # no `type`, so this mirrors what the model actually proposes.
                "ops": [
                    {"op": "remove_field", "fieldId": "field-age"},
                    {
                        "op": "add_field",
                        "pageId": "page-1",
                        "field": {
                            "title": "Which age range are you in?",
                            "type": "dropdown",
                            "choices": ["18-24", "25-34", "35+"],
                        },
                    },
                ],
            },
        },
    ],
}


class TestFormAIReview:
    async def test_review_returns_findings_sorted_by_severity(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_review_provider: FakeProvider,
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        fake_review_provider.replies = [json.dumps(REVIEW_REPLY)]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "exact age" in body["summary"]
        # Sorted most severe first regardless of model order.
        assert [f["severity"] for f in body["findings"]] == ["high", "info"]
        assert body["findings"][0]["fieldId"] == "field-age"
        assert [o["op"] for o in body["findings"][0]["fix"]["ops"]] == [
            "remove_field",
            "add_field",
        ]
        assert body["findings"][1]["fix"] is None

        # The review prompt is grounded in the form snapshot + baseline checks.
        system = fake_review_provider.calls[0]["system"]
        assert "What is your exact age?" in system
        assert "Baseline privacy checks" in system

        # Review is read-only: the draft must be untouched.
        refreshed = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert (
            refreshed.fields[0].properties.fields[0].title == "What is your exact age?"
        )

    async def test_apply_fix_persists_through_the_one_write_path(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review/apply",
            cookies=test_user_cookies,
            json=REVIEW_REPLY["findings"][1]["fix"]
            | {"ops": REVIEW_REPLY["findings"][1]["fix"]["ops"]},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert all(r["ok"] for r in body["results"])
        # Response form is camelised for the webapp stores.
        assert "welcomePage" in body["form"] or "fields" in body["form"]

        refreshed = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        fields = refreshed.fields[0].properties.fields
        titles = [f.title for f in fields]
        assert "What is your exact age?" not in titles
        replacement = next(
            f for f in fields if f.title == "Which age range are you in?"
        )
        assert str(getattr(replacement.type, "value", replacement.type)) == "dropdown"
        assert [c.value for c in replacement.properties.choices] == [
            "18-24",
            "25-34",
            "35+",
        ]

    async def test_apply_fix_fails_gracefully_on_stale_field(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)

        # The finding's target no longer exists (form edited since review).
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review/apply",
            cookies=test_user_cookies,
            json={"ops": [{"op": "remove_field", "fieldId": "gone-field"}]},
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert results[0]["ok"] is False
        assert "not found" in results[0]["message"]

    async def test_apply_rejects_invalid_ops(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review/apply",
            cookies=test_user_cookies,
            json={"ops": [{"op": "definitely_not_an_op"}]},
        )
        assert response.status_code == 400

    async def test_unusable_model_reply_is_a_502_not_a_fake_review(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_review_provider: FakeProvider,
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        fake_review_provider.replies = ["I looked at the form and it seems fine to me!"]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 502

    async def test_broken_fix_ops_drop_the_fix_but_keep_the_finding(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_review_provider: FakeProvider,
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        fake_review_provider.replies = [
            json.dumps(
                {
                    "summary": "One issue found.",
                    "findings": [
                        {
                            "severity": "medium",
                            "message": "This matters even though the fix is broken.",
                            "fix": {
                                "description": "bad",
                                "ops": [{"op": "not_a_real_op"}],
                            },
                        }
                    ],
                }
            )
        ]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/review",
            cookies=test_user_cookies,
            json={},
        )
        assert response.status_code == 200
        finding = response.json()["findings"][0]
        assert finding["message"] == "This matters even though the fix is broken."
        assert finding["fix"] is None
