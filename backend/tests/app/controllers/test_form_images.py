"""Image addresses on a form and on saved themes, checked when they are saved
(services/form_images.py): first-party addresses are kept, Unsplash photos
are rewritten to our route, an address the stored form already holds is kept
as is, anything else is refused (or dropped from a copy)."""

import json
from typing import Any, Coroutine

import pytest
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings
from tests.app.controllers.data import testUser

API = "/api/v1"
STORAGE = "https://cdn.example.org"
BUCKET = "forms-bucket"
PUBLIC_API = "https://forms.example.org/api/v1"
OURS = f"{STORAGE}/{BUCKET}/public/media/ws/1.jpg"
TRACKER = "https://tracker.example.com/pixel.jpg"
UNSPLASH = "https://images.unsplash.com/photo-1?ixid=abc&w=1080"
# our route's address for that photo, as a client might send it back
ROUTED = f"{PUBLIC_API}/images/unsplash/photo-1?w=1080"
LOCAL_ROUTED = "http://localhost:8000/api/v1/images/unsplash/photo-1?w=1080"
CANONICAL = "https://images.unsplash.com/photo-1?w=1080"


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    monkeypatch.setattr(settings.aws_settings, "PUBLIC_URL", STORAGE)
    monkeypatch.setattr(settings.aws_settings, "BUCKET", BUCKET)


def form_url(workspace, form) -> str:
    return f"{API}/workspaces/{workspace.id}/forms/{form.form_id}"


async def patch(client, workspace, form, cookies, body: dict):
    return await client.patch(
        form_url(workspace, form),
        cookies=cookies,
        data={"form_body": json.dumps(body)},
    )


def with_images(welcome=None, page=None, field=None, ending=None, background=None):
    body = {
        "title": "Images",
        "builder_version": "v2",
        "welcome_page": {"title": "Hello", "imageUrl": welcome},
        "thankyou_page": [{"message": "Thanks", "imageUrl": ending}],
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "image_url": page,
                "properties": {
                    "fields": [
                        {
                            "id": "q-1",
                            "index": 0,
                            "type": "short_text",
                            "title": "Name",
                            "image_url": field,
                        }
                    ]
                },
            }
        ],
    }
    if background is not None:
        body["theme"] = {
            "title": "Pictured",
            "primary": "#101826",
            "secondary": "#2456CC",
            "tertiary": "#818CA0",
            "accent": "#F6F8FC",
            "background": {"type": "image", "imageUrl": background},
        }
    return body


async def stored(form) -> FormDocument:
    return await container.form_service().get_form_document_by_id(form.form_id)


@pytest.mark.parametrize("slot", ["welcome", "page", "field", "ending", "background"])
async def test_a_third_party_image_is_refused_on_save(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    slot,
):
    response = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_images(**{slot: TRACKER}),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "image_not_allowed"
    assert TRACKER not in json.dumps(
        (await stored(workspace_form)).model_dump(mode="json")
    )


async def test_our_images_and_unsplash_photos_are_stored_without_any_api_host(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_images(
            welcome=OURS,
            page=UNSPLASH,
            field=ROUTED,
            ending=LOCAL_ROUTED,
            background=UNSPLASH,
        ),
    )
    assert response.status_code == 200, response.text
    form = await stored(workspace_form)
    assert form.welcome_page.imageUrl == OURS
    # Unsplash's address kept as it came; route addresses (any host) turned
    # back into the canonical one
    assert form.fields[0].image_url == UNSPLASH
    assert form.fields[0].properties.fields[0].image_url == CANONICAL
    assert form.thankyou_page[0].imageUrl == CANONICAL
    assert form.theme.background.imageUrl == UNSPLASH
    saved = json.dumps(form.model_dump(mode="json"))
    assert "/images/unsplash/" not in saved and "localhost" not in saved


async def test_an_image_the_form_already_holds_is_kept(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # a form saved before these checks, with an image elsewhere
    legacy = StandardForm(**with_images(welcome=TRACKER))
    legacy.form_id = workspace_form.form_id
    await container.form_service().update_form(
        form_id=workspace_form.form_id, form=legacy
    )

    # saved unchanged, or with the image moved to another page: kept
    for body in (with_images(welcome=TRACKER), with_images(page=TRACKER)):
        response = await patch(
            client, workspace, workspace_form, test_user_cookies, body
        )
        assert response.status_code == 200, response.text
    assert (await stored(workspace_form)).fields[0].image_url == TRACKER

    # once gone from the form, it can't come back; a new one never gets in
    assert (
        await patch(client, workspace, workspace_form, test_user_cookies, with_images())
    ).status_code == 200
    for body in (with_images(welcome=TRACKER), with_images(page=TRACKER + "?2")):
        response = await patch(
            client, workspace, workspace_form, test_user_cookies, body
        )
        assert response.status_code == 422


async def test_a_new_form_with_a_third_party_image_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_images(background=TRACKER))},
    )
    assert response.status_code == 422
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_images(welcome=UNSPLASH))},
    )
    assert response.status_code == 200, response.text
    assert response.json()["welcomePage"]["imageUrl"] == UNSPLASH
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_images(welcome=LOCAL_ROUTED))},
    )
    assert response.status_code == 200, response.text
    assert response.json()["welcomePage"]["imageUrl"] == CANONICAL


async def test_a_copy_drops_third_party_images_instead(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
):
    form = await container.workspace_form_service().create_form(
        workspace.id,
        StandardForm(
            **with_images(welcome=TRACKER, page=OURS, field=UNSPLASH, ending=ROUTED)
        ),
        testUser,
        drop_unusable_settings=True,
    )
    assert form.welcome_page.imageUrl is None
    assert form.fields[0].image_url == OURS
    assert form.fields[0].properties.fields[0].image_url == UNSPLASH
    assert form.thankyou_page[0].imageUrl == CANONICAL


async def test_a_duplicate_carries_no_grandfathered_third_party_image(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    legacy = StandardForm(
        **with_images(welcome=TRACKER, page=UNSPLASH, field=OURS, background=TRACKER)
    )
    legacy.form_id = workspace_form.form_id
    await container.form_service().update_form(
        form_id=workspace_form.form_id, form=legacy
    )
    response = await client.post(
        f"{form_url(workspace, workspace_form)}/duplicate", cookies=test_user_cookies
    )
    assert response.status_code == 200, response.text
    copy = await container.form_service().get_form_document_by_id(
        response.json()["formId"]
    )
    assert copy.welcome_page.imageUrl is None
    assert copy.theme.background.imageUrl is None
    # the canonical Unsplash address is kept
    assert copy.fields[0].image_url == UNSPLASH
    assert copy.fields[0].properties.fields[0].image_url == OURS
    # the source keeps its own
    assert (await stored(workspace_form)).welcome_page.imageUrl == TRACKER


# --- saved workspace themes -----------------------------------------------------


def theme(image_url: str, title="Pictured") -> dict:
    return {
        "title": title,
        "primary": "#101826",
        "secondary": "#2456CC",
        "tertiary": "#818CA0",
        "accent": "#F6F8FC",
        "background": {"type": "image", "imageUrl": image_url},
    }


async def save_themes(client, workspace, cookies, themes):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/theme-presets", cookies=cookies, json=themes
    )


async def test_saved_themes_take_first_party_images_only(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    refused = await save_themes(client, workspace, test_user_cookies, [theme(TRACKER)])
    assert refused.status_code == 422
    assert refused.json()["code"] == "image_not_allowed"

    saved = await save_themes(
        client, workspace, test_user_cookies, [theme(UNSPLASH), theme(OURS, "Ours")]
    )
    assert saved.status_code == 200, saved.text
    urls = [t["background"]["imageUrl"] for t in saved.json()["customThemes"]]
    assert urls == [UNSPLASH, OURS]
    routed = await save_themes(
        client, workspace, test_user_cookies, [theme(LOCAL_ROUTED)]
    )
    assert routed.status_code == 200, routed.text
    assert routed.json()["customThemes"][0]["background"]["imageUrl"] == CANONICAL


async def test_a_saved_theme_already_holding_another_image_keeps_it(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    document = await container.workspace_repo().get_workspace_by_id(workspace.id)
    from backend.app.models.workspace import WorkspaceThemeDto

    document.custom_themes = [WorkspaceThemeDto(**theme(TRACKER))]
    await container.workspace_repo().update(document.id, document)

    renamed = await save_themes(
        client, workspace, test_user_cookies, [theme(TRACKER, "Renamed")]
    )
    assert renamed.status_code == 200, renamed.text
    other = await save_themes(
        client, workspace, test_user_cookies, [theme(TRACKER + "?other")]
    )
    assert other.status_code == 422
