"""CHOICE_LOGIC_ENABLED: off (the default, until the 4.2 release), every write
that brings new or changed option logic or a filter is refused (422
choice_logic_disabled) on every path (builder save, templates, edit
operations, the last gate every op writer goes through, the spec check warns),
a provider import never brings any, and what is stored is kept and still
enforced. On: they pass. The evaluation itself is in test_option_logic.py."""

import json
from pathlib import Path

import pytest
from common.form_spec import form_to_spec_dict
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.template import StandardFormTemplate
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_writes import persist_form
from backend.app.services.option_logic import (
    choice_logic_enabled,
    ensure_choice_logic_allowed,
    new_or_changed_option_logic,
    strip_option_logic,
)
from backend.config import settings
from backend.config.application import Application
from tests.app.controllers.data import testUser
from tests.app.services.test_option_logic import (
    CITIES,
    COUNTRIES,
    _city,
    _country,
    _field,
    _form,
    _is,
    _show,
)

LOGIC_CITY = _field(
    "city",
    choices=[
        {
            "id": "ams",
            "value": "Amsterdam",
            "logic": _show(_is("country", "Netherlands")),
        },
        *CITIES[1:],
    ],
)


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)


def _disabled(error):
    return error.value.status_code == 422 and error.value.content["code"] == (
        "choice_logic_disabled"
    )


def test_the_switch_is_off_by_default_and_registered():
    assert Application.model_fields["CHOICE_LOGIC_ENABLED"].default is False
    from common.settings.inventory import all_specs

    entry = next(s for s in all_specs() if s.key == "CHOICE_LOGIC_ENABLED")
    assert entry.default is False
    assert "CHOICE_LOGIC_ENABLED" in (
        Path(__file__).resolve().parents[3] / ".env.example"
    ).read_text("utf-8")


def test_what_counts_as_new_or_changed(off):
    stored = _form([_country(), LOGIC_CITY])
    # the same, a question moved to another page, a repair that took a condition away: nothing new
    assert new_or_changed_option_logic(stored, stored) == []
    moved = _form([_country()], [LOGIC_CITY])
    assert new_or_changed_option_logic(moved, stored) == []
    two = _field(
        "city",
        choices=[
            {
                "id": "ams",
                "value": "Amsterdam",
                "logic": _show(
                    _is("country", "Netherlands"), _is("country", "Germany")
                ),
            },
            *CITIES[1:],
        ],
    )
    wider = _form([_country(), two])
    assert new_or_changed_option_logic(wider, stored) == [("city", "option:ams")]
    # ... but with the second condition taken away it is the stored one again
    assert new_or_changed_option_logic(stored, wider) == []
    # clearing is never a change
    assert (
        new_or_changed_option_logic(
            _form([_country(), _field("city", choices=CITIES)]), stored
        )
        == []
    )
    # a filter: new, and one with entries taken away
    filtered = _form([_country(), _city()])
    assert new_or_changed_option_logic(filtered, None) == [("city", "filter")]
    less = _form(
        [
            _country(),
            _city(
                optionFilter={
                    "fieldId": "country",
                    "mapping": [{"when": "nl", "show": ["ams"]}],
                }
            ),
        ]
    )
    assert new_or_changed_option_logic(less, filtered) == []
    assert new_or_changed_option_logic(filtered, less) == [("city", "filter")]


def test_the_guard_refuses_while_off_and_passes_when_on(monkeypatch):
    form = _form([_country(), LOGIC_CITY])
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    assert not choice_logic_enabled()
    with pytest.raises(HTTPException) as error:
        ensure_choice_logic_allowed(form)
    assert _disabled(error)
    assert "CHOICE_LOGIC_ENABLED" in error.value.content["message"]
    assert error.value.content["errors"] == [{"fieldId": "city", "optionId": "ams"}]
    ensure_choice_logic_allowed(form, form)  # stored, unchanged
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    ensure_choice_logic_allowed(form)


# --- the builder save, templates, the last gate -------------------------------------


async def test_a_builder_save_follows_the_switch(workspace, monkeypatch):
    service = container.workspace_form_service()
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await service.create_form(
            workspace.id, _form([_country(), LOGIC_CITY]), testUser
        )
    assert _disabled(error)
    plain = await service.create_form(
        workspace.id, _form([_country(), _field("city", choices=CITIES)]), testUser
    )
    with pytest.raises(HTTPException) as error:
        await service.update_form(
            workspace.id, plain.form_id, _form([_country(), LOGIC_CITY]), testUser
        )
    assert _disabled(error)
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    await service.update_form(
        workspace.id, plain.form_id, _form([_country(), LOGIC_CITY]), testUser
    )
    # switched off again: what is stored is kept, re-sent unchanged and
    # repaired by the save passes, clearing it passes, a change does not
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    await service.update_form(
        workspace.id, plain.form_id, _form([_country(), LOGIC_CITY]), testUser
    )
    broken = _field(
        "city",
        choices=[
            {
                "id": "ams",
                "value": "Amsterdam",
                "logic": _show(_is("country", "Netherlands"), _is("gone", "x")),
            },
            *CITIES[1:],
        ],
    )
    repaired = []
    await service.update_form(
        workspace.id,
        plain.form_id,
        _form([_country(), broken]),
        testUser,
        dropped_option_logic=repaired,
    )
    assert [r["fieldId"] for r in repaired] == ["city"]
    assert "'gone'" in repaired[0]["message"]
    changed = _field(
        "city",
        choices=[
            {
                "id": "ams",
                "value": "Amsterdam",
                "logic": _show(_is("country", "Germany")),
            },
            *CITIES[1:],
        ],
    )
    with pytest.raises(HTTPException) as error:
        await service.update_form(
            workspace.id, plain.form_id, _form([_country(), changed]), testUser
        )
    assert _disabled(error)
    await service.update_form(
        workspace.id,
        plain.form_id,
        _form([_country(), _field("city", choices=CITIES)]),
        testUser,
    )


async def test_stored_choice_logic_is_still_enforced_while_off(workspace, monkeypatch):
    service = container.workspace_form_service()
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    form = await service.create_form(
        workspace.id, _form([_country(), _city()]), testUser
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(
                answers={
                    "country": {"type": "choice", "choice": {"value": "nl"}},
                    "city": {"type": "choice", "choice": {"value": "ber"}},
                }
            ),
            testUser,
        )
    assert error.value.content["errors"] == [
        {"fieldId": "city", "rule": "hidden_option"}
    ]


async def test_templates_follow_the_switch(workspace, monkeypatch):
    body = StandardFormTemplate(
        title="T", fields=_form([_country(), LOGIC_CITY]).fields
    )
    templates = container.form_template_service()
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        await templates.create_new_template(workspace.id, None, None, testUser, body)
    assert _disabled(error)
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    created = await templates.create_new_template(
        workspace.id, None, None, testUser, body
    )
    assert (
        created.fields[0].properties.fields[1].properties.choices[0].logic is not None
    )
    # a form made from a template is a copy: it keeps what the template has
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    filtered = _form(
        [
            _country(),
            _field(
                "city",
                choices=CITIES,
                optionFilter={
                    "fieldId": "country",
                    "mapping": [{"when": "nl", "show": ["ams"]}],
                },
            ),
        ]
    )
    with pytest.raises(HTTPException) as error:
        await templates.update_template(
            workspace.id,
            created.id,
            testUser,
            StandardFormTemplate(title="T2", fields=filtered.fields),
            None,
            None,
            None,
        )
    assert _disabled(error)


async def test_persist_form_is_the_last_gate_for_every_op_writer(
    workspace, monkeypatch
):
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    service = container.workspace_form_service()
    created = await service.create_form(
        workspace.id, _form([_country(), _field("city", choices=CITIES)]), testUser
    )
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))
    with pytest.raises(HTTPException) as error:
        await persist_form(
            repo, document, _form([_country(), LOGIC_CITY]), parts=["fields"]
        )
    assert _disabled(error)
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    assert await persist_form(
        repo, document, _form([_country(), LOGIC_CITY]), parts=["fields"]
    )


# --- the edit operations (both kinds), the spec check, the AI and MCP text ----------


def _ops(form, ops):
    return apply_form_ops(form, parse_ops(ops, allow_editor_ops=True))


SET_LOGIC = {
    "op": "set_option_logic",
    "fieldId": "city",
    "choice": "Amsterdam",
    "logic": {
        "action": "SHOW",
        "conditions": [
            {"fieldId": "country", "comparison": "IS_EQUAL", "value": "Netherlands"}
        ],
    },
}
SET_FILTER = {
    "op": "set_option_filter",
    "fieldId": "city",
    "filter": {
        "fieldId": "country",
        "mapping": [{"when": "Netherlands", "show": ["Amsterdam"]}],
    },
}


def test_edit_operations_follow_the_switch(monkeypatch):
    plain = _form([_country(), _field("city", choices=CITIES)])
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    for op in (SET_LOGIC, SET_FILTER):
        form, results = _ops(plain, [op])
        assert not results[0].ok
        assert "CHOICE_LOGIC_ENABLED" in results[0].message
        assert form.fields[0].properties.fields[1].properties.option_filter is None
    # an editor op bringing a whole question with logic
    bad = {
        "id": "town",
        "type": "dropdown",
        "title": "Town",
        "properties": {
            "choices": [
                {
                    "id": "a",
                    "value": "A",
                    "logic": {
                        "action": "SHOW",
                        "conditions": [
                            {
                                "fieldId": "country",
                                "fieldType": "dropdown",
                                "comparison": "IS_EQUAL",
                                "value": "Germany",
                            }
                        ],
                    },
                },
                {"id": "b", "value": "B"},
            ]
        },
    }
    _, results = _ops(
        plain, [{"op": "insert_field", "pageId": "p0", "index": 1, "field": bad}]
    )
    assert not results[0].ok and "CHOICE_LOGIC_ENABLED" in results[0].message
    # clearing is allowed, and so is setting what is already there
    stored = _form([_country(), LOGIC_CITY])
    form, results = _ops(
        stored,
        [
            {
                "op": "set_option_logic",
                "fieldId": "city",
                "choice": "Amsterdam",
                "logic": None,
            }
        ],
    )
    assert results[0].ok
    _, results = _ops(stored, [SET_LOGIC])
    assert results[0].ok
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    for op in (SET_LOGIC, SET_FILTER):
        _, results = _ops(plain, [op])
        assert results[0].ok, results[0].message


def test_a_copy_of_a_page_starts_without_option_logic_while_off_too(off):
    form, results = _ops(
        _form([_country(), LOGIC_CITY]), [{"op": "duplicate_page", "pageId": "p0"}]
    )
    assert results[0].ok
    assert new_or_changed_option_logic(form, _form([_country(), LOGIC_CITY])) == []


def test_the_spec_check_warns_while_off_and_not_when_on(monkeypatch):
    document = form_to_spec_dict(_form([_country(), LOGIC_CITY]))
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    result = check_spec_document(document)
    assert result["valid"]
    assert any(
        "Choice logic is switched off" in w["message"] for w in result["warnings"]
    )
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    result = check_spec_document(document)
    assert not any(
        "Choice logic is switched off" in w["message"] for w in result["warnings"]
    )


def test_the_ai_prompt_names_the_ops_only_while_on(monkeypatch):
    from backend.app.services.ai.prompt_builder import build_chat_system_prompt

    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", False)
    assert "set_option_logic" not in build_chat_system_prompt("{}", None)
    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)
    assert "set_option_logic" in build_chat_system_prompt("{}", None)


# --- imports ---------------------------------------------------------------------------


def test_a_provider_import_never_brings_choice_logic():
    form = _form([_country(), _city(), _field("other", choices=CITIES)])
    assert strip_option_logic(form) == 1
    assert new_or_changed_option_logic(form) == []
    with_logic = _form([_country(), LOGIC_CITY])
    assert strip_option_logic(with_logic) == 1
    assert with_logic.fields[0].properties.fields[1].properties.choices[0].logic is None


async def test_the_import_service_drops_choice_logic_a_payload_holds(
    workspace, monkeypatch
):
    from backend.app.services import form_import_service as module

    seen = {}

    async def save_form(form):
        seen["form"] = form
        raise RuntimeError("stop after the form is read")

    service = container.form_import_service()
    monkeypatch.setattr(service.form_service, "save_form", save_form)
    standard = _form([_country(), LOGIC_CITY])
    payload = {"form": json.loads(standard.model_dump_json()), "responses": []}
    with pytest.raises(RuntimeError):
        await service.save_converted_form_and_responses(payload, "owner", workspace.id)
    assert new_or_changed_option_logic(seen["form"]) == []
    assert module.strip_option_logic


def test_the_other_importers_do_not_write_choice_logic():
    """The PDF and Open Formulieren importers build edit operations of their own
    kinds (they have no source for option logic); what they save goes through
    create_form and persist_form, which the tests above hold to the switch."""
    root = Path(__file__).resolve().parents[3] / "backend/app/services"
    for relative in (
        "open_formulieren/importer.py",
        "open_formulieren/logic.py",
        "pdf_import/compile.py",
        "pdf_import/pipeline.py",
        "ai/outline_compile.py",
    ):
        text = (root / relative).read_text("utf-8")
        assert "set_option_logic" not in text and "set_option_filter" not in text
        assert "option_filter" not in text and "optionFilter" not in text


def test_a_save_made_while_off_cannot_change_how_stored_logic_evaluates(off):
    stored = _form([_country(), LOGIC_CITY])
    # the same conditions with another source type read the answer another way
    retyped = _field(
        "city",
        choices=[
            {
                "id": "ams",
                "value": "Amsterdam",
                "logic": _show(_is("country", "Netherlands", "short_text")),
            },
            *CITIES[1:],
        ],
    )
    assert new_or_changed_option_logic(_form([_country(), retyped]), stored) == [
        ("city", "option:ams")
    ]
