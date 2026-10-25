"""The flow-template seed gives every yes/no question its Yes/No choices, and
repairs templates seeded before it did (forms created from them showed the
question with nothing to answer)."""

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.schemas.template import FormTemplateDocument
from scripts.seed_flow_templates import (
    TEMPLATE_BUILDERS,
    lead_qualification,
    support_triage,
    repair_yes_no_choices,
    seed_flow_templates,
)

pytestmark = pytest.mark.asyncio

WORKSPACE_ID = PydanticObjectId("65e5501d0000000000000001")


def _yes_no_fields(fields):
    for field in fields:
        if field.get("type") == "yes_no":
            yield field
        yield from _yes_no_fields((field.get("properties") or {}).get("fields") or [])


def test_every_seeded_yes_no_question_has_yes_and_no():
    found = 0
    for build in TEMPLATE_BUILDERS:
        for field in _yes_no_fields(build()["fields"]):
            found += 1
            assert [c["value"] for c in field["properties"]["choices"]] == ["Yes", "No"]
    assert found == 2


async def _seed_broken_lead_qualification():
    """A template as earlier versions of the seed stored it: no yes/no choices."""
    payload = lead_qualification()
    for field in _yes_no_fields(payload["fields"]):
        field.pop("properties", None)
    doc = FormTemplateDocument(
        builder_version="v2",
        type="form",
        workspace_id=WORKSPACE_ID,
        title=payload["title"],
        description=payload["description"],
        fields=payload["fields"],
        settings={"is_public": True},
    )
    # Through the routed repository, where the seed looks, whatever the
    # persistence mode.
    return await container.form_template_repo().save(doc)


def _stored_yes_no_choices(template):
    out = []
    for slide in template.fields:
        for field in slide.properties.fields or []:
            if getattr(field.type, "value", field.type) == "yes_no":
                out.append(
                    [
                        c.value
                        for c in (
                            field.properties.choices if field.properties else None
                        )
                        or []
                    ]
                )
    return out


async def test_repair_adds_yes_no_choices_once():
    repo = container.form_template_repo()
    broken = await _seed_broken_lead_qualification()
    assert _stored_yes_no_choices(await repo.get_template_by_id(broken.id)) == [[]]

    assert await repair_yes_no_choices(repo, broken.id) is True
    assert _stored_yes_no_choices(await repo.get_template_by_id(broken.id)) == [
        ["Yes", "No"]
    ]

    # Idempotent: a repaired template is left alone.
    assert await repair_yes_no_choices(repo, broken.id) is False


async def test_an_existing_template_in_another_workspace_is_not_duplicated():
    """DEFAULT_WORKSPACE_ID can differ from where an earlier run seeded."""
    repo = container.form_template_repo()
    broken = await _seed_broken_lead_qualification()
    other_workspace = PydanticObjectId("65e5501d0000000000000002")

    result = await seed_flow_templates(other_workspace, template_repo=repo)

    assert "Lead qualification" in result["skipped"]
    assert result["repaired"] == ["Lead qualification"]
    titles = [
        t["title"]
        for workspace_id in (WORKSPACE_ID, other_workspace)
        for t in await repo.get_templates_with_creator(
            v2=True, workspace_id=workspace_id
        )
    ]
    assert titles.count("Lead qualification") == 1
    assert _stored_yes_no_choices(await repo.get_template_by_id(broken.id)) == [
        ["Yes", "No"]
    ]


async def test_seed_repairs_an_existing_template_and_leaves_the_rest():
    repo = container.form_template_repo()
    broken = await _seed_broken_lead_qualification()

    result = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert result["repaired"] == ["Lead qualification"]
    assert "Lead qualification" in result["skipped"]
    assert sorted(result["seeded"]) == [
        "Job application with screening",
        "Support triage",
    ]
    assert _stored_yes_no_choices(await repo.get_template_by_id(broken.id)) == [
        ["Yes", "No"]
    ]

    again = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)
    assert again["seeded"] == [] and again["repaired"] == []


def test_every_seeded_contact_question_says_why_it_asks():
    from common.models.standard_form import StandardForm

    from backend.app.services.publish_checks import publish_problems

    for build in TEMPLATE_BUILDERS:
        payload = build()
        form = StandardForm(title=payload["title"], fields=payload["fields"])
        assert publish_problems(form) == [], payload["title"]


async def test_repair_adds_a_missing_why_we_ask_line():
    repo = container.form_template_repo()
    broken = await _seed_broken_lead_qualification()
    template = await repo.get_template_by_id(broken.id)
    for slide in template.fields:
        for field in slide.properties.fields or []:
            if field.properties is not None:
                field.properties.why_we_ask = None
    await repo.save(template)

    assert await repair_yes_no_choices(repo, broken.id) is True
    reasons = [
        field.properties.why_we_ask
        for slide in (await repo.get_template_by_id(broken.id)).fields
        for field in slide.properties.fields or []
        if getattr(field.type, "value", field.type) == "email"
    ]
    assert reasons == ["So we can follow up on your enquiry."]


# The predefined templates wear the Leaflet design (the shared preset and
# style); templates seeded before that move to it once, and nothing else does.

LEGACY_THEME = {
    "title": "Default",
    "primary": "#2E2E2E",
    "secondary": "#0764EB",
    "tertiary": "#A2C5F8",
    "accent": "#F2F7FF",
}
LAYOUT = "SINGLE_COLUMN_NO_BACKGROUND"


def _leaflet():
    from backend.app.constants.themes import theme_dict

    return theme_dict["Leaflet"]


def _theme_of(template):
    return template.theme.model_dump(exclude_none=True) if template.theme else None


def _layout(page):
    return getattr(page.layout, "value", page.layout)


def test_the_template_theme_is_the_shared_leaflet_preset():
    from scripts.seed_flow_templates import template_theme

    theme = template_theme()
    assert theme == _leaflet()
    assert theme["style"] == "leaflet"
    # A fresh copy each time: changing one never changes the preset.
    theme["primary"] = "#000000"
    assert template_theme() == _leaflet()


def test_every_welcome_page_says_in_one_line_what_the_form_is_for():
    for build in TEMPLATE_BUILDERS:
        welcome = build()["welcome"]
        assert welcome and "\n" not in welcome and len(welcome) <= 120, build.__name__


async def test_new_templates_wear_leaflet_with_a_welcome_description():
    repo = container.form_template_repo()

    result = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert len(result["seeded"]) == len(TEMPLATE_BUILDERS)
    for build in TEMPLATE_BUILDERS:
        payload = build()
        stored = await repo.get_v2_template_by_title(payload["title"])
        assert _theme_of(stored) == _leaflet()
        assert stored.welcome_page.description == payload["welcome"]
        assert _layout(stored.welcome_page) == LAYOUT
        assert [_layout(page) for page in stored.thankyou_page] == [LAYOUT]
        assert {_layout(slide.properties) for slide in stored.fields} == {LAYOUT}


def _without_section_titles(payload):
    for page in payload["fields"]:
        page["properties"].pop("section_title", None)
    return payload


def _section_titles(template):
    return [page.properties.section_title for page in template.fields]


def _seeded_section_titles(payload):
    return [page["properties"].get("section_title") for page in payload["fields"]]


async def _save_template(payload, *, theme=LEGACY_THEME, workspace_id=WORKSPACE_ID, **extra):
    """A template as earlier versions of the seed stored it (old theme, a
    welcome page with a title only, pages without section titles), unless
    told otherwise."""
    if not extra.pop("keep_section_titles", False):
        payload = _without_section_titles(payload)
    doc = FormTemplateDocument(
        builder_version=extra.pop("builder_version", "v2"),
        type="form",
        workspace_id=workspace_id,
        title=payload["title"],
        description=payload["description"],
        fields=payload["fields"],
        theme=theme,
        welcome_page={"title": payload["title"], "layout": LAYOUT, "buttonText": "Start"},
        thankyou_page=[{"layout": LAYOUT}],
        settings=extra.pop("settings", {"is_public": True}),
        **extra,
    )
    return await container.form_template_repo().save(doc)


async def test_seed_moves_an_old_template_to_leaflet_once():
    repo = container.form_template_repo()
    old = await _save_template(lead_qualification())

    first = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)
    stored = await repo.get_template_by_id(old.id)
    second = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert first["restyled"] == ["Lead qualification"]
    assert _theme_of(stored) == _leaflet()
    assert stored.welcome_page.description == lead_qualification()["welcome"]
    # The rest of the template is as it was.
    assert stored.title == old.title and stored.welcome_page.buttonText == "Start"
    assert [str(s.id) for s in stored.fields] == [str(s.id) for s in old.fields]
    # Idempotent: nothing to do the second time, and nothing created.
    assert second["seeded"] == second["repaired"] == second["restyled"] == []
    titles = [
        t["title"]
        for t in await repo.get_templates_with_creator(v2=True, workspace_id=WORKSPACE_ID)
    ]
    assert titles.count("Lead qualification") == 1
    assert len(titles) == len(TEMPLATE_BUILDERS)


async def test_the_repair_touches_only_the_seeds_own_templates():
    from backend.app.constants.themes import theme_dict
    from scripts.seed_flow_templates import repair_leaflet_design

    repo = container.form_template_repo()
    workspace = PydanticObjectId("65e5501d0000000000000003")
    payload = lead_qualification()
    own_questions = dict(payload, fields=[
        {"id": "p1", "index": 0, "type": "slide", "properties": {"layout": LAYOUT, "fields": [
            {"id": "q1", "index": 0, "type": "short_text", "title": "Something of my own"}
        ]}}
    ])
    others = [
        # A copy imported into a workspace.
        await _save_template(payload, workspace_id=workspace, imported_from=WORKSPACE_ID),
        # A workspace's own template with the same title.
        await _save_template(own_questions, workspace_id=workspace),
        # A private template with the same title and questions.
        await _save_template(payload, workspace_id=workspace, settings={"is_public": False}),
        # A classic (v1) template.
        await _save_template(payload, builder_version="v1"),
    ]
    before = [(await repo.get_template_by_id(t.id)).model_dump() for t in others]

    for template in others:
        assert await repair_leaflet_design(repo, template.id) is False
    assert [(await repo.get_template_by_id(t.id)).model_dump() for t in others] == before

    # The seed's own template whose theme was changed by hand keeps that theme.
    ocean = await _save_template(payload, theme=theme_dict["Ocean"])
    await repair_leaflet_design(repo, ocean.id)
    assert _theme_of(await repo.get_template_by_id(ocean.id)) == theme_dict["Ocean"]


async def test_the_gallery_template_is_repaired_when_a_namesake_is_found_first():
    repo = container.form_template_repo()
    workspace = PydanticObjectId("65e5501d0000000000000003")
    payload = lead_qualification()
    namesake = await _save_template(payload, workspace_id=workspace, settings={"is_public": False})
    seeded = await _save_template(payload)

    result = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert result["restyled"] == ["Lead qualification"]
    assert _theme_of(await repo.get_template_by_id(seeded.id)) == _leaflet()
    assert _theme_of(await repo.get_template_by_id(namesake.id)) == LEGACY_THEME


async def test_forms_made_from_an_old_template_keep_their_theme(
    client, workspace, test_user_cookies
):
    repo = container.form_template_repo()
    old = await _save_template(lead_qualification())
    created = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template/{old.id}", cookies=test_user_cookies
    )
    assert created.status_code == 200, created.text
    form_id = created.json()["formId"]

    result = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert result["restyled"] == ["Lead qualification"]
    form = await container.form_repo().get_form_document_by_id(form_id)
    assert form.theme.model_dump(exclude_none=True) == LEGACY_THEME
    assert form.welcome_page.description is None


def test_every_seeded_page_has_a_short_section_title():
    for build in TEMPLATE_BUILDERS:
        payload = build()
        titles = _seeded_section_titles(payload)
        assert all(titles) and all(len(t) <= 30 for t in titles), build.__name__
        # Never the page's first question, which the bar would repeat.
        for page, title in zip(payload["fields"], titles):
            assert title != page["properties"]["fields"][0]["title"]


async def test_new_templates_have_their_section_titles():
    repo = container.form_template_repo()
    await seed_flow_templates(WORKSPACE_ID, template_repo=repo)
    stored = await repo.get_v2_template_by_title("Lead qualification")
    assert _section_titles(stored) == ["Timing", "Your needs", "Contact"]


async def test_the_repair_adds_section_titles_once_and_keeps_a_title_set_by_hand():
    from scripts.seed_flow_templates import repair_leaflet_design

    repo = container.form_template_repo()
    old = await _save_template(lead_qualification())
    hand_set = await _save_template(support_triage())
    template = await repo.get_template_by_id(hand_set.id)
    template.fields[0].properties.section_title = "Wat speelt er?"
    template.fields[2].properties.section_title = ""
    await repo.save(template)
    assert _section_titles(await repo.get_template_by_id(old.id)) == [None, None, None]

    first = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)

    assert sorted(first["restyled"]) == ["Lead qualification", "Support triage"]
    assert _section_titles(await repo.get_template_by_id(old.id)) == [
        "Timing",
        "Your needs",
        "Contact",
    ]
    # The title set by hand stays; empty ones are filled.
    assert _section_titles(await repo.get_template_by_id(hand_set.id)) == [
        "Wat speelt er?",
        "Billing",
        "Technical issue",
        "Contact",
    ]

    # A second run changes nothing.
    before = [(await repo.get_template_by_id(t.id)).model_dump() for t in (old, hand_set)]
    second = await seed_flow_templates(WORKSPACE_ID, template_repo=repo)
    assert second["restyled"] == []
    assert await repair_leaflet_design(repo, old.id) is False
    assert [(await repo.get_template_by_id(t.id)).model_dump() for t in (old, hand_set)] == before


async def test_the_repair_adds_no_section_titles_to_templates_it_does_not_own():
    from scripts.seed_flow_templates import repair_leaflet_design

    repo = container.form_template_repo()
    workspace = PydanticObjectId("65e5501d0000000000000003")
    copy = await _save_template(lead_qualification(), workspace_id=workspace, imported_from=WORKSPACE_ID)
    namesake = await _save_template(lead_qualification(), workspace_id=workspace, settings={"is_public": False})

    for template in (copy, namesake):
        assert await repair_leaflet_design(repo, template.id) is False
        assert _section_titles(await repo.get_template_by_id(template.id)) == [None, None, None]
