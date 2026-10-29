"""Which forms the theme contrast rule stops, and the outlined button.

The rule (``services/publish_checks.py`` ``theme_contrast``) stops a publish
for a new form (created under check version 3 or later), for a form that was
never published, and for any form whose colours differ from its live
version's; an older form republished with the colours it went live with is
only advised (``theme_contrast_blocks``). Every way of publishing goes through
``WorkspaceFormService.publish_form``, so the builder, the public API, the
MCP server and the AI assistant's edits are held to the same gate.

An outlined button is measured by its real text and edge colours
(``services/theme_contrast.py``), not as white text on its colour; the shared
cases in ``docs/spec/theme-contrast.cases.json`` (which the webapp runs too)
hold the numbers.
"""

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
    Theme,
)

from backend.app.constants.themes import themes
from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.publish_checks import (
    FORM_NOT_PUBLISHABLE,
    PUBLISH_CHECKS_VERSION,
    THEME_CONTRAST,
    THEME_CONTRAST_FROM_VERSION,
    WORKSPACE_TITLE_FROM_VERSION,
    WHY_WE_ASK_FROM_VERSION,
    ensure_publishable,
    publish_problems,
    requires_theme_contrast,
    requires_why_we_ask,
    requires_workspace_title,
    theme_contrast_blocks,
    theme_contrast_problems,
)
from backend.app.services.theme_contrast import (
    contrast,
    contrast_key,
    outlined_button_ink,
    theme_contrast_guard,
)
from tests.app.controllers.data import testUser

# Hard to read: grey questions and pale borders on white.
PASTEL = {
    "title": "Pastel",
    "primary": "#9CA3AF",
    "secondary": "#1649E2",
    "tertiary": "#E5E7EB",
    "accent": "#FFFFFF",
}
# Another failing palette (so a change of colours is a change of failing ones).
PALE = {**PASTEL, "title": "Pale", "primary": "#B0B7C3"}
READABLE = {
    "title": "Readable",
    "primary": "#101828",
    "secondary": "#1649E2",
    "tertiary": "#6B7280",
    "accent": "#FFFFFF",
}
# A mid-tone button colour: white text on it is 3.3:1 (a filled button fails),
# it reads as chosen-answer colour on white (3.3:1), but as text on white it
# does not (so an outlined button takes the dark questions' colour instead).
MID_TONE = {**READABLE, "title": "Mid-tone", "secondary": "#D9730D"}


def _form(theme=None) -> StandardForm:
    return StandardForm(
        title="Form",
        theme=Theme(**theme) if isinstance(theme, dict) else theme,
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[
                        StandardFormField(
                            id="q",
                            type=T.SHORT_TEXT,
                            title="Your name",
                            properties=StandardFieldProperty(fields=[]),
                        )
                    ]
                ),
            )
        ],
    )


# --- the versions ----------------------------------------------------------------


def test_the_contrast_gate_starts_at_version_3_and_new_forms_are_created_under_it():
    assert THEME_CONTRAST_FROM_VERSION == 3
    assert PUBLISH_CHECKS_VERSION == 3
    assert [requires_theme_contrast(v) for v in (None, 0, 1, 2, 3, 4)] == [
        False,
        False,
        False,
        False,
        True,
        True,
    ]


def test_the_bump_leaves_the_reason_and_title_rules_for_their_versions():
    assert WHY_WE_ASK_FROM_VERSION == 1
    assert WORKSPACE_TITLE_FROM_VERSION == 2
    assert [requires_why_we_ask(v) for v in (None, 0, 1, 2, 3)] == [
        False,
        False,
        True,
        True,
        True,
    ]
    assert [requires_workspace_title(v) for v in (None, 0, 1, 2, 3)] == [
        False,
        False,
        False,
        True,
        True,
    ]


# --- who is stopped ----------------------------------------------------------------


@pytest.mark.parametrize("version", [3, 4])
def test_a_new_form_is_stopped_even_with_the_colours_it_went_live_with(version):
    assert theme_contrast_blocks(version, PASTEL, PASTEL, was_published=True) is True


@pytest.mark.parametrize("version", [None, 0, 1, 2])
def test_an_older_form_is_stopped_only_when_its_colours_changed(version):
    # live with these colours: advice only
    assert theme_contrast_blocks(version, PASTEL, PASTEL, was_published=True) is False
    # other colours than the live version's
    assert theme_contrast_blocks(version, PALE, PASTEL, was_published=True) is True
    # never published: nothing live relies on its colours, nothing to compare
    assert theme_contrast_blocks(version, PASTEL, None, was_published=False) is True
    # live without colours of its own (an old form on the defaults), now with some
    assert theme_contrast_blocks(version, PASTEL, None, was_published=True) is True


def test_only_what_the_check_reads_counts_as_a_change():
    version = 2
    live = {**PASTEL, "background": {"type": "gradient", "gradientFrom": "#ffffff"}}
    # letter case of a hex colour, fonts, titles and shape change nothing
    same = {
        **live,
        "title": "Renamed",
        "primary": "#9ca3af",
        "titleFont": "besley",
        "radius": "round",
        "background": {"type": "gradient", "gradientFrom": "#FFFFFF"},
    }
    assert theme_contrast_blocks(version, same, live, was_published=True) is False
    for change in (
        {"primary": "#9CA3AE"},
        {"secondary": "#1649E3"},
        {"tertiary": "#E5E7EC"},
        {"accent": "#FFFFFE"},
        {"buttonStyle": "outlined"},
        {"background": {"type": "gradient", "gradientFrom": "#FFFFFE"}},
        {"background": {"type": "pattern", "pattern": "margin"}},
        {"background": {"type": "image", "imageUrl": "/api/v1/media/a.png"}},
    ):
        theme = {**live, **change}
        assert theme_contrast_blocks(version, theme, live, was_published=True), change


def test_an_older_form_that_is_live_publishes_with_the_colours_it_has():
    form = _form(PASTEL)
    # advice only: nothing is raised, and the problem is still listed for the builder
    ensure_publishable(
        form, checks_version=2, published_theme=Theme(**PASTEL), was_published=True
    )
    assert [p["code"] for p in publish_problems(form)] == [THEME_CONTRAST]


def test_an_older_form_whose_colours_changed_is_refused_with_the_usual_problem():
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(
            _form(PALE),
            checks_version=None,
            published_theme=Theme(**PASTEL),
            was_published=True,
        )
    assert raised.value.status_code == 422
    assert raised.value.content["code"] == FORM_NOT_PUBLISHABLE
    assert [p["code"] for p in raised.value.content["problems"]] == [THEME_CONTRAST]


def test_a_new_form_is_refused_with_the_live_colours_too():
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(
            _form(PASTEL),
            checks_version=PUBLISH_CHECKS_VERSION,
            published_theme=Theme(**PASTEL),
            was_published=True,
        )
    assert [p["code"] for p in raised.value.content["problems"]] == [THEME_CONTRAST]


def test_a_readable_theme_is_never_in_the_way():
    for version in (None, 2, PUBLISH_CHECKS_VERSION):
        ensure_publishable(_form(READABLE), checks_version=version)
        ensure_publishable(
            _form(READABLE),
            checks_version=version,
            published_theme=Theme(**PASTEL),
            was_published=True,
        )


@pytest.mark.parametrize("version", [None, 2, PUBLISH_CHECKS_VERSION])
def test_text_over_an_image_is_advice_for_every_form(version):
    """It can't be measured, so it never blocks (the spec check and the
    builder show a note instead); the boxes and buttons are still measured."""
    image = {"type": "image", "imageUrl": "/api/v1/media/a.png"}
    theme = {**PASTEL, "primary": "#101828", "tertiary": "#101828", "accent": "#000000"}
    ensure_publishable(_form(Theme(**theme, background=image)), checks_version=version)


# --- outlined buttons --------------------------------------------------------------


def test_an_outlined_button_is_not_white_text_on_its_colour():
    filled = theme_contrast_guard(MID_TONE)
    assert [i.key for i in filled.issues] == ["button"]
    outlined = theme_contrast_guard({**MID_TONE, "buttonStyle": "outlined"})
    assert outlined.issues == []
    # a pill button is filled
    assert [
        i.key for i in theme_contrast_guard({**MID_TONE, "buttonStyle": "pill"}).issues
    ] == ["button"]


def test_the_ink_of_an_outlined_button():
    # the button colour where it reads as text on the page (4.5:1), else the questions'
    assert outlined_button_ink({**READABLE, "buttonStyle": "outlined"}) == "#1649E2"
    assert outlined_button_ink({**MID_TONE, "buttonStyle": "outlined"}) == "#101828"
    # the page the button sits on is the page colour
    dark = {**READABLE, "accent": "#0B1220", "primary": "#F5F7FB", "secondary": "#FFD166"}
    assert outlined_button_ink(dark) == "#FFD166"


def test_its_real_text_and_edge_are_measured_not_skipped():
    pale = {**PASTEL, "secondary": "#F5C242", "buttonStyle": "outlined"}
    issues = {i.key: i for i in theme_contrast_guard(pale).issues}
    assert "button" not in issues
    ink = outlined_button_ink(pale)
    assert ink == pale["primary"]
    assert issues["outlined"].ratio == pytest.approx(contrast(ink, pale["accent"]))
    assert issues["outlined"].minimum == 4.5


def test_the_edge_is_held_to_the_page_it_sits_on():
    theme = {
        **READABLE,
        "secondary": "#1E4D8C",
        "buttonStyle": "outlined",
        "background": {
            "type": "gradient",
            "gradientFrom": "#FFFFFF",
            "gradientTo": "#7A8CB8",
        },
    }
    [issue, *_] = theme_contrast_guard(theme).issues
    assert issue.key == "outlined"
    assert issue.ratio == pytest.approx(contrast("#1E4D8C", "#7A8CB8"))
    assert issue.minimum == 3.0


def test_the_fix_for_an_outlined_theme_moves_the_button_colour_only_as_far_as_needed():
    yellow = {**READABLE, "secondary": "#F5C242"}
    filled = theme_contrast_guard(yellow).fix
    outlined = theme_contrast_guard({**yellow, "buttonStyle": "outlined"}).fix
    # filled needs white text on it (darker); outlined only 3:1 on the page
    assert outlined["secondary"] != filled["secondary"]
    assert contrast(outlined["secondary"], "#FFFFFF") >= 3.0
    assert contrast(outlined["secondary"], "#FFFFFF") < 4.5
    assert not theme_contrast_guard({**yellow, **outlined, "buttonStyle": "outlined"}).issues


def test_the_message_names_the_outlined_button_in_its_own_words():
    [problem] = theme_contrast_problems(
        Theme(**{**PASTEL, "secondary": "#F5C242", "buttonStyle": "outlined"})
    )
    assert "text and edges of outlined buttons (2.5:1, needs 4.5:1)" in problem["message"]
    assert "white text on buttons" not in problem["message"]


def test_the_contrast_key_reads_the_button_style():
    assert contrast_key({**READABLE}) != contrast_key({**READABLE, "buttonStyle": "outlined"})
    assert contrast_key({**READABLE, "buttonStyle": "pill"}) == contrast_key(READABLE)


@pytest.mark.parametrize("name", list(themes))
def test_every_preset_still_passes_filled_or_outlined(name):
    assert theme_contrast_problems(themes[name]) == []
    guard = theme_contrast_guard(themes[name].model_dump(exclude_none=True))
    assert guard.issues == []
    # and as the other kind of button, for the colours it has
    other = "filled" if themes[name].buttonStyle == "outlined" else "outlined"
    outlined = theme_contrast_guard(
        {**themes[name].model_dump(exclude_none=True), "buttonStyle": other}
    )
    assert [i.key for i in outlined.issues if i.key == "outlined"] == []


# --- publishing, over a database -----------------------------------------------------


async def _draft(workspace, theme=PASTEL) -> str:
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(theme), testUser
    )
    return form.form_id


async def _set_checks_version(workspace, form_id, version):
    repo = container.workspace_form_repo()
    workspace_form = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form_id)
    )
    workspace_form.settings.publish_checks_version = version
    await repo.save(workspace_form)


async def _go_live(form_id):
    """A live version made before the rule (the product's own publish, with
    no checks), as an older form has."""
    return await container.form_service().publish_form(form_id=form_id)


async def _set_theme(form_id, theme):
    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.theme = Theme(**theme)
    await container.form_service().update_form(form_id=form_id, form=draft)


async def _retitle(form_id, title):
    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.title = title
    await container.form_service().update_form(form_id=form_id, form=draft)


async def _publish(workspace, form_id):
    return await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )


def _problem_codes(raised) -> list:
    assert raised.value.content["code"] == FORM_NOT_PUBLISHABLE
    return [p["code"] for p in raised.value.content["problems"]]


@pytest.mark.parametrize("version", [None, 1, 2])
async def test_an_older_live_form_keeps_publishing_with_its_colours(workspace, version):
    form_id = await _draft(workspace)
    await _set_checks_version(workspace, form_id, version)
    await _go_live(form_id)
    await _retitle(form_id, "Edited, same colours")
    assert (await _publish(workspace, form_id)).version == 2
    await _retitle(form_id, "Edited again")
    assert (await _publish(workspace, form_id)).version == 3


async def test_a_change_of_colours_on_an_older_live_form_is_refused_until_it_reads(
    workspace,
):
    form_id = await _draft(workspace)
    await _set_checks_version(workspace, form_id, 2)
    await _go_live(form_id)
    await _set_theme(form_id, PALE)
    with pytest.raises(HTTPException) as raised:
        await _publish(workspace, form_id)
    assert _problem_codes(raised) == [THEME_CONTRAST]
    # back to the colours it went live with: advice only again
    await _set_theme(form_id, PASTEL)
    await _retitle(form_id, "Edited")
    assert (await _publish(workspace, form_id)).version == 2
    # readable colours publish; so would any later change of them
    await _set_theme(form_id, READABLE)
    assert (await _publish(workspace, form_id)).version == 3
    await _set_theme(form_id, PASTEL)
    with pytest.raises(HTTPException) as raised:
        await _publish(workspace, form_id)
    assert _problem_codes(raised) == [THEME_CONTRAST]


async def test_an_older_form_that_was_never_published_is_refused(workspace):
    form_id = await _draft(workspace)
    await _set_checks_version(workspace, form_id, None)
    with pytest.raises(HTTPException) as raised:
        await _publish(workspace, form_id)
    assert _problem_codes(raised) == [THEME_CONTRAST]
    assert await container.form_repo().get_latest_version_of_form(form_id) is None


async def test_a_new_form_is_refused_even_when_it_is_live_with_those_colours(workspace):
    form_id = await _draft(workspace)
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form_id)
        )
    )
    assert workspace_form.settings.publish_checks_version == PUBLISH_CHECKS_VERSION
    await _go_live(form_id)
    await _retitle(form_id, "Edited")
    with pytest.raises(HTTPException) as raised:
        await _publish(workspace, form_id)
    assert _problem_codes(raised) == [THEME_CONTRAST]


async def test_the_gate_does_not_change_the_other_checks_of_an_older_form(workspace):
    """An older form exempt from the contrast rule is held to every other
    rule as before."""
    form_id = await _draft(workspace)
    await _set_checks_version(workspace, form_id, 2)
    await _go_live(form_id)
    draft = await container.form_service().get_form_document_by_id(form_id)
    page = draft.fields[0]
    page.properties.fields[0].type = T.EMAIL  # asks for personal details
    await container.form_service().update_form(form_id=form_id, form=draft)
    with pytest.raises(HTTPException) as raised:
        await _publish(workspace, form_id)
    assert _problem_codes(raised) == ["missing_why_we_ask"]


# --- every way of publishing ------------------------------------------------------------


async def test_the_builder_endpoint_follows_the_gate(
    client: AsyncClient, workspace, test_user_cookies
):
    url = None
    old = await _draft(workspace)
    await _set_checks_version(workspace, old, 2)
    await _go_live(old)
    url = f"/api/v1/workspaces/{workspace.id}/forms/{old}/publish"
    assert (await client.post(url, cookies=test_user_cookies)).status_code == 200

    await _set_theme(old, PALE)
    refused = await client.post(url, cookies=test_user_cookies)
    assert refused.status_code == 422
    assert [p["code"] for p in refused.json()["problems"]] == [THEME_CONTRAST]

    new = await _draft(workspace)
    await _go_live(new)
    refused = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{new}/publish",
        cookies=test_user_cookies,
    )
    assert refused.status_code == 422


async def test_the_public_api_follows_the_gate(client: AsyncClient, workspace):
    from tests.app.controllers.test_public_api import BASE, _auth, _create, _token
    from tests.app.services.test_theme_contrast import _spec

    token = await _token(workspace.id)
    old = (await _create(client, token, spec=_spec(PASTEL))).json()["formId"]
    await _set_checks_version(workspace, old, 2)
    await _go_live(old)
    ok = await client.post(f"{BASE}/forms/{old}/publish", headers=_auth(token))
    assert ok.status_code == 200, ok.text

    await _set_theme(old, PALE)
    refused = await client.post(f"{BASE}/forms/{old}/publish", headers=_auth(token))
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == FORM_NOT_PUBLISHABLE

    new = (await _create(client, token, spec=_spec(PASTEL))).json()["formId"]
    refused = await client.post(f"{BASE}/forms/{new}/publish", headers=_auth(token))
    assert refused.status_code == 422, refused.text


async def test_the_mcp_server_follows_the_gate(client: AsyncClient, workspace):
    from tests.app.controllers.test_mcp_server import _call_tool, _make_key

    token = await _make_key(workspace.id, ["forms:write"])
    old = await _draft(workspace)
    await _set_checks_version(workspace, old, 2)
    await _go_live(old)
    ok = await _call_tool(client, token, "publish_form", {"form_id": str(old)})
    assert ok.get("isError") is not True, ok

    await _set_theme(old, PALE)
    refused = await _call_tool(client, token, "publish_form", {"form_id": str(old)})
    assert refused.get("isError") is True, refused

    new = await _draft(workspace)
    refused = await _call_tool(client, token, "publish_form", {"form_id": str(new)})
    assert refused.get("isError") is True, refused


async def test_the_spec_publish_follows_the_gate(workspace):
    """The form-spec service (the REST API, SDK and CLI documents) publishes
    through the same service call."""
    from backend.app.services.form_spec import writes

    assert "publish_form" in open(writes.__file__).read()
    old = await _draft(workspace)
    await _set_checks_version(workspace, old, 2)
    await _go_live(old)
    spec_writes = container.form_spec_writer()
    result = await spec_writes.publish(workspace.id, str(old), testUser)
    assert result["published"] is True
    await _set_theme(old, PALE)
    with pytest.raises(HTTPException) as raised:
        await spec_writes.publish(workspace.id, str(old), testUser)
    assert _problem_codes(raised) == [THEME_CONTRAST]
