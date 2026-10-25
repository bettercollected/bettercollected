"""The ``theme_contrast`` publish check (services/theme_contrast.py, the port
of the builder's contrast guard): the shared cases in
docs/spec/theme-contrast.cases.json (the webapp's
src/utils/theme-contrast-cases.test.ts runs the same ones), every preset, the
message, and publishing refused through the service, the public API, the MCP
server and after an AI edit, with the AI review and spec validation naming it."""

import json
import math
from pathlib import Path

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
)

from backend.app.constants.themes import theme_dict, themes
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import FormOps, apply_form_ops
from backend.app.services.ai.quality import ERROR, check_form_quality
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.publish_checks import (
    FORM_NOT_PUBLISHABLE,
    THEME_CONTRAST,
    THEME_PROBLEM_ID,
    ensure_publishable,
    publish_problems,
    theme_contrast_problems,
)
from backend.app.services.theme_contrast import (
    AA_NON_TEXT,
    AA_TEXT,
    contrast,
    display_ratio,
    theme_contrast_guard,
)
from tests.app.controllers.data import testUser

CASES = json.loads(
    (
        Path(__file__).resolve().parents[4] / "docs/spec/theme-contrast.cases.json"
    ).read_text()
)

# Hard to read: grey questions and pale borders on white.
PASTEL = {
    "title": "Pastel",
    "primary": "#9CA3AF",
    "secondary": "#1649E2",
    "tertiary": "#E5E7EB",
    "accent": "#FFFFFF",
}


# --- the shared cases ----------------------------------------------------------


@pytest.mark.parametrize("pair", CASES["pairs"], ids=lambda pair: pair["name"])
def test_contrast_of_the_shared_pairs(pair):
    ratio = contrast(pair["foreground"], pair["background"])
    if pair["ratio"] is None:
        assert math.isnan(ratio)
    else:
        assert ratio == pytest.approx(pair["ratio"], abs=1e-5)
        assert display_ratio(ratio) == pair["display"]
    assert (ratio >= AA_TEXT) is pair["passesText"]
    assert (ratio >= AA_NON_TEXT) is pair["passesNonText"]


@pytest.mark.parametrize("case", CASES["themes"], ids=lambda case: case["name"])
def test_guard_of_the_shared_themes(case):
    guard = theme_contrast_guard(case["theme"])
    assert [issue.key for issue in guard.issues] == [
        issue["key"] for issue in case["issues"]
    ]
    for issue, shared in zip(guard.issues, case["issues"]):
        assert issue.ratio == pytest.approx(shared["ratio"], abs=1e-5)
        assert display_ratio(issue.ratio) == shared["display"]
        assert issue.minimum == shared["minimum"]
    assert guard.fix == case["fix"]
    assert guard.image_ground is case["imageGround"]
    if guard.fix:  # the suggestion passes
        assert not theme_contrast_guard({**case["theme"], **guard.fix}).issues


def test_the_ratio_is_shown_rounded_down():
    assert display_ratio(4.4999) == "4.4"
    assert display_ratio(contrast("#777777", "#FFFFFF")) == "4.4"
    assert display_ratio(3.0) == "3.0"


# --- presets -------------------------------------------------------------------


def test_the_shared_cases_list_every_preset_as_it_is():
    guarded = ("primary", "secondary", "tertiary", "accent", "background")
    for name, preset in theme_dict.items():
        shared = next(c for c in CASES["themes"] if c["name"] == f"preset {name}")
        assert shared["theme"] == {k: preset[k] for k in guarded if k in preset}


@pytest.mark.parametrize("name", list(themes))
def test_every_preset_publishes(name):
    assert theme_contrast_problems(themes[name]) == []
    form = _form(theme=themes[name])
    assert THEME_CONTRAST not in [p["code"] for p in publish_problems(form)]


# --- the problem ---------------------------------------------------------------


def _form(theme=None, *fields):
    return StandardForm(
        title="Form",
        theme=Theme(**theme) if isinstance(theme, dict) else theme,
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(fields=list(fields)),
            )
        ],
    )


def test_a_hard_to_read_theme_names_each_failing_pair_and_the_fix():
    assert theme_contrast_problems(Theme(**PASTEL)) == [
        {
            "code": THEME_CONTRAST,
            "fieldId": THEME_PROBLEM_ID,
            "message": "The theme's colours are hard to read: questions and "
            "text on the page (2.5:1, needs 4.5:1), answers in the input boxes "
            "(2.5:1, needs 4.5:1) and input borders (1.2:1, needs 3.0:1). The "
            "nearest colours that pass: primary #6C7586 and tertiary #8791A3. "
            "Use them (the builder's Design tab offers them in one click), or "
            "pick others.",
        }
    ]


def test_a_gradient_fix_names_both_stops():
    theme = {
        **PASTEL,
        "primary": "#101828",
        "tertiary": "#818CA0",
        "background": {
            "type": "gradient",
            "gradientFrom": "#FFFFFF",
            "gradientTo": "#101828",
        },
    }
    [problem] = theme_contrast_problems(Theme(**theme))
    assert "questions and text on the page (1.0:1, needs 4.5:1)" in problem["message"]
    assert "background gradient #FFFFFF to #DBDCDF" in problem["message"]


def test_text_over_an_image_never_blocks():
    image = {"type": "image", "imageUrl": "/api/v1/media/a.png"}
    # dark text on a dark page colour: unmeasurable under the image
    theme = {**PASTEL, "primary": "#101828", "tertiary": "#101828", "accent": "#000000"}
    assert theme_contrast_problems(Theme(**theme, background=image)) == []
    # the white input boxes and the buttons are still measured
    [problem] = theme_contrast_problems(
        Theme(**{**theme, "primary": "#FFFFFF"}, background=image)
    )
    assert problem["message"].startswith(
        "The theme's colours are hard to read: answers in the input boxes"
    )


@pytest.mark.parametrize(
    "theme",
    [
        None,
        {"title": "Default"},
        # not every colour a 6-digit hex: an older form on the defaults
        {**PASTEL, "accent": "#FFF"},
        {**PASTEL, "primary": "black"},
    ],
)
def test_a_theme_without_its_four_colours_is_not_checked(theme):
    assert theme_contrast_problems(theme) == []


def test_it_blocks_every_form_old_or_new():
    for checks_version in (None, 1):
        with pytest.raises(HTTPException) as raised:
            ensure_publishable(_form(PASTEL), checks_version=checks_version)
        assert raised.value.status_code == 422
        assert raised.value.content["code"] == FORM_NOT_PUBLISHABLE
        assert [p["code"] for p in raised.value.content["problems"]] == [THEME_CONTRAST]


# --- the AI review and spec validation name it -----------------------------------


def test_the_ai_review_reports_it_as_an_error():
    report = check_form_quality(_form(PASTEL))
    [finding] = [f for f in report.findings if f.code == THEME_CONTRAST]
    assert finding.severity == ERROR
    assert finding.where == (THEME_PROBLEM_ID,)


def _spec(theme):
    return {
        "specVersion": "1",
        "title": "Form",
        "theme": theme,
        "pages": [
            {
                "id": "page-1",
                "fields": [{"id": "name", "type": "short_text", "title": "Name"}],
            }
        ],
    }


def test_spec_validation_warns_before_publishing():
    result = check_spec_document(_spec(PASTEL))
    assert result["valid"] is True
    [warning] = [w for w in result["warnings"] if w["path"] == "/theme"]
    assert warning["message"].startswith(
        "Before publishing: The theme's colours are hard to read"
    )


def test_spec_validation_notes_an_image_page_cannot_be_measured():
    theme = {
        **dict(theme_dict["Default"]),
        "background": {"type": "image", "imageUrl": "/api/v1/media/a.png"},
    }
    result = check_spec_document(_spec(theme))
    paths = [w["path"] for w in result["warnings"]]
    assert "/theme/background/imageUrl" in paths
    assert "/theme" not in paths


# --- publishing ----------------------------------------------------------------


async def _draft(workspace, theme=PASTEL):
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(theme), testUser
    )
    return form.form_id


async def test_the_service_refuses_then_publishes_once_fixed(workspace):
    form_id = await _draft(workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    assert raised.value.content["problems"][0]["code"] == THEME_CONTRAST

    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.theme = themes["Default"].model_copy(deep=True)
    await container.form_service().update_form(form_id=form_id, form=draft)
    published = await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    assert published.theme.primary == "#101828"


async def test_the_builder_endpoint_answers_422(
    client: AsyncClient, workspace, test_user_cookies
):
    form_id = await _draft(workspace)
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/publish",
        cookies=test_user_cookies,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == FORM_NOT_PUBLISHABLE
    assert [(p["code"], p["fieldId"]) for p in body["problems"]] == [
        (THEME_CONTRAST, THEME_PROBLEM_ID)
    ]


async def test_the_public_api_refuses_it(client: AsyncClient, workspace):
    from tests.app.controllers.test_public_api import BASE, _auth, _create, _token

    token = await _token(workspace.id)
    created = await _create(client, token, spec=_spec(PASTEL))
    form_id = created.json()["formId"]
    response = await client.post(
        f"{BASE}/forms/{form_id}/publish", headers=_auth(token)
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == FORM_NOT_PUBLISHABLE
    # the API's error carries the problems in its message: the failing pairs
    # with their ratios and the colours that pass
    assert "The theme's colours are hard to read" in body["message"]
    assert "input borders (1.2:1, needs 3.0:1)" in body["message"]
    assert "tertiary #8791A3" in body["message"]


async def test_the_mcp_server_refuses_it(client: AsyncClient, workspace):
    from tests.app.controllers.test_mcp_server import _call_tool, _make_key

    form_id = await _draft(workspace)
    token = await _make_key(workspace.id, ["forms:write"])
    result = await _call_tool(client, token, "publish_form", {"form_id": str(form_id)})
    assert result.get("isError") is True, result
    latest = await container.form_repo().get_latest_version_of_form(form_id)
    assert latest is None


async def test_a_theme_the_ai_assistant_set_is_refused(workspace):
    form_id = await _draft(workspace, theme=themes["Default"])
    draft = await container.form_service().get_form_document_by_id(form_id)
    update = {"op": "update_theme", "theme": PASTEL}
    edited, results = apply_form_ops(
        StandardForm(**draft.model_dump()),
        FormOps.model_validate({"ops": [update]}).ops,
    )
    assert all(r.ok for r in results)
    draft.theme = edited.theme
    await container.form_service().update_form(form_id=form_id, form=draft)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    assert [p["code"] for p in raised.value.content["problems"]] == [THEME_CONTRAST]


def test_the_seeded_flow_templates_use_a_theme_that_publishes():
    from scripts.seed_flow_templates import THEME

    assert theme_contrast_problems(THEME) == []
