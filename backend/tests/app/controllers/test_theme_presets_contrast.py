"""A workspace's saved themes are held to the publish check's contrast rules
(services/theme_contrast.py) when saved through the theme-presets endpoint:
the shared cases in docs/spec/theme-contrast.cases.json, a passing theme
saved, a failing one refused with a 422 naming the theme, its failing
pairings and the nearest colours that pass, colours the workspace already
stores kept as they are, and nothing from another workspace in the body."""

import copy
import json
from pathlib import Path
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.workspace import WorkspaceThemeDto
from backend.app.schemas.workspace import WorkspaceDocument

API = "/api/v1"
CASES = json.loads(
    (
        Path(__file__).resolve().parents[4] / "docs/spec/theme-contrast.cases.json"
    ).read_text()
)
# the cases' image path, as a first-party address the endpoint stores
IMAGE = "https://images.unsplash.com/photo-1?w=1080"

READABLE = {
    "title": "Readable",
    "primary": "#101828",
    "secondary": "#1649E2",
    "tertiary": "#818CA0",
    "accent": "#F5F7FB",
}
# Hard to read: grey questions and pale borders on white.
PASTEL = {
    "title": "Pastel",
    "primary": "#9CA3AF",
    "secondary": "#1649E2",
    "tertiary": "#E5E7EB",
    "accent": "#FFFFFF",
}


def case_theme(case: dict) -> dict:
    theme = copy.deepcopy(case["theme"])
    background = theme.get("background")
    if background and background.get("imageUrl"):
        background["imageUrl"] = IMAGE
    return {"title": case["name"][:40], **theme}


async def save_themes(client, workspace, cookies, themes):
    return await client.patch(
        f"{API}/workspaces/{workspace.id}/theme-presets", cookies=cookies, json=themes
    )


async def stored_titles(workspace) -> list:
    saved = await container.workspace_repo().get_or_404(workspace.id)
    return [
        theme["title"] if isinstance(theme, dict) else theme.title
        for theme in saved.custom_themes or []
    ]


async def store_directly(workspace, themes: list) -> None:
    """Themes saved before the check (or by a path that skips it)."""
    repo = container.workspace_repo()
    document = await repo.get_or_404(workspace.id)
    document.custom_themes = [WorkspaceThemeDto(**theme) for theme in themes]
    await repo.update(document.id, document)


@pytest.mark.parametrize(
    "case", CASES["themes"], ids=[case["name"] for case in CASES["themes"]]
)
async def test_shared_cases_through_the_endpoint(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    case: dict,
):
    response = await save_themes(
        client, workspace, test_user_cookies, [case_theme(case)]
    )
    if not case["issues"]:
        assert response.status_code == 200, response.text
        assert await stored_titles(workspace) == [case["name"][:40]]
        return
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "theme_contrast"
    [detail] = body["themes"]
    assert detail["index"] == 0 and detail["path"] == "customThemes.0"
    assert [issue["key"] for issue in detail["issues"]] == [
        issue["key"] for issue in case["issues"]
    ]
    for got, expected in zip(detail["issues"], case["issues"]):
        assert got["ratio"] == pytest.approx(expected["ratio"], abs=1e-5)
        assert got["minimum"] == expected["minimum"]
    assert detail["fix"] == case["fix"]
    assert body["errors"][0].startswith("customThemes.0: ")
    assert await stored_titles(workspace) == []


async def test_a_failing_theme_is_refused_with_the_fix(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    response = await save_themes(
        client, workspace, test_user_cookies, [READABLE, PASTEL]
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "theme_contrast"
    assert [detail["path"] for detail in body["themes"]] == ["customThemes.1"]
    assert body["message"] == body["errors"][0]
    assert body["message"].startswith(
        "customThemes.1: The theme's colours are hard to read: "
        "questions and text on the page (2.5:1, needs 4.5:1)"
    )
    assert "The nearest colours that pass: primary " in body["message"]
    # nothing is stored, not even the readable one
    assert await stored_titles(workspace) == []

    fixed = {**PASTEL, **body["themes"][0]["fix"]}
    response = await save_themes(
        client, workspace, test_user_cookies, [READABLE, fixed]
    )
    assert response.status_code == 200, response.text
    assert await stored_titles(workspace) == ["Readable", "Pastel"]


async def test_stored_colours_are_kept_as_they_are(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    await store_directly(workspace, [PASTEL])

    # adding another theme sends the stored one back unchanged
    response = await save_themes(
        client, workspace, test_user_cookies, [PASTEL, READABLE]
    )
    assert response.status_code == 200, response.text
    # renaming it keeps its colours, so it is kept too (hex case aside)
    renamed = {
        **PASTEL,
        "title": "Old pastel",
        "primary": PASTEL["primary"].lower(),
    }
    response = await save_themes(
        client, workspace, test_user_cookies, [renamed, READABLE]
    )
    assert response.status_code == 200, response.text
    assert await stored_titles(workspace) == ["Old pastel", "Readable"]

    # a changed colour that still fails is checked like a new theme
    response = await save_themes(
        client,
        workspace,
        test_user_cookies,
        [{**renamed, "tertiary": "#F0F0F0"}, READABLE],
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "theme_contrast"
    # so is the same colours on a background that puts a new ground behind them
    response = await save_themes(
        client,
        workspace,
        test_user_cookies,
        [
            {
                **renamed,
                "background": {
                    "type": "gradient",
                    "gradientFrom": "#FFFFFF",
                    "gradientTo": "#101828",
                },
            }
        ],
    )
    assert response.status_code == 422, response.text

    # deleting every theme still works
    response = await save_themes(client, workspace, test_user_cookies, [])
    assert response.status_code == 200, response.text
    assert await stored_titles(workspace) == []
    # and reading a stored failing theme is unchanged
    await store_directly(workspace, [PASTEL])
    response = await client.get(
        f"{API}/workspaces/{workspace.id}", cookies=test_user_cookies
    )
    assert response.status_code == 200, response.text
    assert [t["title"] for t in response.json()["customThemes"]] == ["Pastel"]


async def test_another_workspaces_themes_neither_pass_nor_leak(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_1: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    secret = {**PASTEL, "title": "Other workspace secret"}
    await store_directly(workspace_1, [secret])

    # the same failing colours stored elsewhere don't make them pass here
    response = await save_themes(client, workspace, test_user_cookies, [PASTEL])
    assert response.status_code == 422, response.text
    assert "Other workspace secret" not in response.text
    assert str(workspace_1.id) not in response.text
    assert await stored_titles(workspace) == []
    assert await stored_titles(workspace_1) == ["Other workspace secret"]
