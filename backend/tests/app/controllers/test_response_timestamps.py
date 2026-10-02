"""Submission times are the server's: a respondent cannot choose when their
response was submitted (or last edited). Imported responses keep the
provider's own timestamps."""

import datetime as dt
import json
from typing import Any, Coroutine

from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.workspace_form_service import _question_ids

FUTURE = "2099-01-01T00:00:00+00:00"
SLACK = dt.timedelta(seconds=5)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def test_a_client_supplied_created_at_is_ignored_on_submit(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    before = _now()
    submitted = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{published_form.form_id}/response",
        data={
            "response": json.dumps(
                {"answers": {}, "createdAt": FUTURE, "updatedAt": FUTURE}
            )
        },
        cookies=test_user_cookies,
    )
    assert submitted.status_code == 200, submitted.text
    after = _now()

    stored = await container.form_response_repo().get_by_submission_uuid(
        submitted.json()
    )
    assert before - SLACK <= _aware(stored.created_at) <= after + SLACK
    assert before - SLACK <= _aware(stored.updated_at) <= after + SLACK


async def test_an_edit_keeps_created_at_and_sets_updated_at(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[Any, Any, FormDocument],
    workspace_form_response: Coroutine[Any, Any, dict],
    test_user_cookies: dict[str, str],
):
    common_url = f"/api/v1/workspaces/{workspace.id}"
    form_id = published_form.form_id
    response_id = workspace_form_response["response_id"]
    original = await container.form_response_repo().get_response(response_id)

    allowed = await client.patch(
        f"{common_url}/forms/{form_id}/settings",
        json={"require_verified_identity": True, "allow_editing_response": True},
        cookies=test_user_cookies,
    )
    assert allowed.status_code == 200, allowed.text

    question = sorted(_question_ids(published_form.fields))[0]
    before = _now()
    edited = await client.patch(
        f"{common_url}/forms/{form_id}/response/{response_id}",
        data={
            "response": json.dumps(
                {
                    "answers": {question: {"field": {"id": question}, "text": "x"}},
                    "createdAt": FUTURE,
                    "updatedAt": FUTURE,
                }
            )
        },
        cookies=test_user_cookies,
    )
    assert edited.status_code == 200, edited.text
    after = _now()

    stored = await container.form_response_repo().get_response(response_id)
    assert _aware(stored.created_at) == _aware(original.created_at)
    assert _aware(stored.updated_at) > _aware(original.updated_at)
    assert before - SLACK <= _aware(stored.updated_at) <= after + SLACK


async def test_imported_responses_keep_the_provider_timestamps(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
):
    provider_time = "2024-01-02T03:04:05+00:00"
    await container.form_import_service().save_converted_form_and_responses(
        {
            "form": {
                "form_id": "imported-form-timestamps",
                "title": "Imported",
                "settings": {"provider": "google"},
            },
            "responses": [
                {
                    "response_id": "imported-response-timestamps",
                    "provider": "google",
                    "answers": {},
                    "created_at": provider_time,
                    "updated_at": provider_time,
                }
            ],
        },
        "",
        workspace.id,
    )
    stored = await container.form_response_repo().get_response(
        "imported-response-timestamps"
    )
    # the provider's submission time (updated_at is the sync's, as before)
    assert _aware(stored.created_at) == dt.datetime.fromisoformat(provider_time)
