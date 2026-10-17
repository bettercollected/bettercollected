"""Font sizes and colours of rich-text titles (services/rich_text.py): only
the formats the title editor writes; refused by the edit operations,
dropped on a whole-form save."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.rich_text import (
    sanitise_rich_text,
    style_value_problem,
    valid_color,
    valid_font_size,
)


@pytest.mark.parametrize(
    "value", ["12", "15", "16", "24", "32", "16px", "8px", "96", "13.5px"]
)
def test_font_sizes_the_editor_writes(value):
    assert valid_font_size(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "7px",
        "97px",
        "1em",
        "16 px",
        "16px;color:red",
        "calc(1px)",
        "-12px",
        16,
        None,
    ],
)
def test_other_font_sizes(value):
    assert not valid_font_size(value)


@pytest.mark.parametrize(
    "value",
    [
        "#fff",
        "#A0b1C2",
        "rgb(255, 0, 0)",
        "rgb(0,0,0)",
        "rgba(0, 0, 0, 0.5)",
        "rgba(1,2,3,1)",
        "rgba(1,2,3,.25)",
    ],
)
def test_colours_the_editor_writes(value):
    assert valid_color(value)


@pytest.mark.parametrize(
    "value",
    [
        "red",
        "#ff00",
        "#gggggg",
        "rgb(256, 0, 0)",
        "rgba(0,0,0,2)",
        "rgb(1,2)",
        "#fff;x:y",
        "url(x)",
        "var(--c)",
        "#fff\n",
        "rgb(1,\t2,3)",
        "rgb(1,\u00a02,3)",
        "rgb(\u0661,2,3)",
        0,
    ],
)
def test_other_colours(value):
    assert not valid_color(value)


def test_null_values_are_fine():
    assert style_value_problem("fontSize", None) is None
    assert style_value_problem("color", None) is None


def _title(**attrs):
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "x",
                        "marks": [
                            {"type": "bold"},
                            {"type": "textStyle", "attrs": attrs},
                        ],
                    }
                ],
            }
        ],
    }


def test_sanitising_drops_only_the_unusable_values():
    title = _title(fontSize="12px; background: url(x)", color="#ff0000")
    assert sanitise_rich_text(title) == 1
    assert title == _title(color="#ff0000")
    assert sanitise_rich_text(title) == 0


async def test_a_whole_form_save_drops_unusable_style_values(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    """Dropped, not refused: a form stored before the check still saves."""
    body = {
        "title": "Styled",
        "builder_version": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "q-1",
                            "index": 0,
                            "type": "short_text",
                            "title": _title(
                                fontSize="24px", color="red; position: fixed"
                            ),
                        }
                    ]
                },
            }
        ],
    }
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(body)},
    )
    assert response.status_code == 200, response.text
    stored = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    title = stored.fields[0].properties.fields[0].title
    assert title == _title(fontSize="24px")


@pytest.mark.parametrize("value", ["12px\n", "12\n", "\u0661\u0662px"])
def test_font_sizes_match_the_webapp_rule_exactly(value):
    assert not valid_font_size(value)
