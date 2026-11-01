"""A webhook delivery of a response an API key made says so (``"source":
"api"``), through the real wiring (the stored response's source read by the
webhook service); a respondent's has no ``source``."""

import json

import pytest

from backend.app.container import container
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services.submissions_api.service import (
    CreateSubmission,
    create_submission,
)
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.registration.helpers import publish, submit
from tests.app.webhooks.helpers import logs_of, make_webhook

pytestmark = pytest.mark.asyncio


async def _sent_for(form, response_id, tls):
    (row,) = [r for r in await logs_of(form) if r.response_id == response_id]
    outcome = await container.webhook_service().run_delivery(str(row.id))
    assert outcome.status == "delivered"
    return json.loads(tls.requests[-1].body)


async def test_source_is_api_only_for_a_key_made_response(
    workspace, webhooks_on, memory_jobs, tls, monkeypatch
):
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    form = await publish(workspace)
    await make_webhook(workspace, form, ["name", "age"])
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(name="crm", scopes=["submissions:write"]),
        testUser,
    )
    [key] = [
        k
        for k in await container.workspace_api_key_repo().list_by_workspace(workspace.id)
        if str(k.id) == created.id
    ]
    made = await create_submission(
        key,
        form.form_id,
        CreateSubmission(answers={"name": "Ada", "age": 36}, consent=True),
    )
    sent = await _sent_for(form, made["responseId"], tls)
    assert sent["source"] == "api"
    assert sent["data"] == {"name": "Ada", "age": 36}
    # nothing of the key leaves
    assert "crm" not in json.dumps(sent) and created.id not in json.dumps(sent)

    respondent = await submit(workspace, form)
    sent = await _sent_for(form, respondent.response_id, tls)
    assert "source" not in sent
