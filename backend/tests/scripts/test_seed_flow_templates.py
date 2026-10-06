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
    # Stored in both places the seed looks: Mongo (its existence check) and
    # the routed repository (its repair), whatever the persistence mode.
    saved = await container.form_template_repo().save(doc)
    await saved.save()
    return saved


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
        t.title
        for t in await FormTemplateDocument.find(
            FormTemplateDocument.title == "Lead qualification"
        ).to_list()
    ]
    assert titles == ["Lead qualification"]
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
