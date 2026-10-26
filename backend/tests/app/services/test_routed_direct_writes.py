"""Writes that used to go straight to a Beanie document now go through the
repositories (every group is served from Postgres only since 4.1).

Before: a responder's tags and metadata, the prompts of AI-generated forms and
users' price suggestions were saved to Mongo only.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from beanie import PydanticObjectId
from dependency_injector import providers

from backend.app.container import container
from backend.app.models.dtos.price_suggestion import PriceSuggestionRequest
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.schemas.price_suggestion import PriceSuggestion
from backend.app.services.price_suggestion import PriceSuggestionService
from backend.db.models import WorkspaceResponderRow
from common.models.user import User
from common.records import RecordId
from tests.app.controllers.data import testUser


async def test_a_patched_responder_is_served_by_the_listing(
    client, workspace, workspace_form_response, test_user_cookies, published_form
):
    email = workspace_form_response["dataOwnerIdentifier"]
    url = f"api/v1/workspaces/{workspace.id}/responders"
    tag = await container.workspace_responders_service().create_workspace_tag(
        workspace.id, "VIP", testUser
    )

    patched = await client.patch(
        url,
        params={"email": email},
        cookies=test_user_cookies,
        json={"tags": [str(tag.id)], "metadata": {"team": "blue"}},
    )
    assert patched.status_code == 200, patched.text

    listed = await client.get(url, cookies=test_user_cookies)
    assert listed.status_code == 200, listed.text
    [item] = [i for i in listed.json()["items"] if i["email"] == email]
    assert item["metadata"] == {"team": "blue"}
    assert [t["title"] for t in item["tags"]] == ["VIP"]

    stored = await container.workspace_responders_repo().one(
        WorkspaceResponderRow.workspace_id == str(workspace.id),
        WorkspaceResponderRow.email == email,
    )
    assert stored.metadata == {"team": "blue"}
    assert stored.tags == [tag.id]


async def test_the_prompt_of_an_ai_form_is_stored(workspace):
    """ai is served from Postgres only (no routing): stored there."""
    form_id = RecordId()
    form = SimpleNamespace(
        form_id=str(form_id), model_dump=lambda **_: {"title": "Generated"}
    )
    outline = SimpleNamespace(dump=lambda: {"title": "Outline"})
    generator = SimpleNamespace(generate=AsyncMock(return_value=(form, outline, None)))

    with container.form_outline_service.override(providers.Object(generator)):
        created = await container.openai_service().create_form_with_ai(
            workspace.id, CreateFormWithAI(prompt="a short survey"), testUser
        )
    assert created is form

    repo = container.create_form_prompt_repo()
    [served] = await repo.list_by_form_id(form_id)
    assert (served.prompt, served.created_form) == (
        "a short survey",
        {"title": "Generated"},
    )
    assert isinstance(served, CreateFormPrompt) and served.form_id == form_id


async def test_a_price_suggestion_is_stored():
    """refdata is served from Postgres only (no routing): stored there."""
    user = User(id=str(PydanticObjectId()), sub="suggests@example.com")
    auth_service = SimpleNamespace(upgrade_user_to_pro=AsyncMock())
    workspace_service = SimpleNamespace(upgrade_user_workspace=AsyncMock())
    service = PriceSuggestionService(
        auth_service, workspace_service, container.price_suggestion_repo()
    )

    with patch(
        "backend.app.services.price_suggestion.event_logger_service.send_event",
        new=AsyncMock(),
    ):
        await service.save_price_suggestion_and_upgrade_user(
            PriceSuggestionRequest(price=7), user
        )
    auth_service.upgrade_user_to_pro.assert_awaited_once()

    repo = container.price_suggestion_repo()
    [served] = await repo.list_by_user_id(user.id)
    assert (served.price, served.email) == (7, "suggests@example.com")
    assert isinstance(served, PriceSuggestion) and str(served.user_id) == user.id
