"""The import holds a row to the same rules as a respondent: one fixture set
runs through the respondent submission and through the import's check, and the
two must agree on every case (and on the rules they name)."""

import pytest
from httpx import AsyncClient

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.container import container
from tests.app.controllers.data import testUser
from tests.app.response_import.helpers import (
    csv_bytes,
    get,
    post,
    publish_form,
    run_job,
    upload,
)

pytestmark = pytest.mark.asyncio

FIELDS = [
    {"id": "name", "type": "short_text", "title": "Name", "validations": {"required": True, "max_length": 6}},
    {"id": "age", "type": "number", "title": "Age", "validations": {"min_value": 18, "max_value": 65}},
    {"id": "mail", "type": "email", "title": "Mail", "properties": {"why_we_ask": "To write back"}},
    {
        "id": "colour",
        "type": "dropdown",
        "title": "Colour",
        "properties": {"choices": [{"id": "c1", "value": "Red"}, {"id": "c2", "value": "Blue"}]},
    },
    {"id": "start", "type": "date", "title": "Start"},
    {
        "id": "end",
        "type": "date",
        "title": "End",
        "properties": {"date_rules": [{"comparison": "after", "target": "field", "field_id": "start"}]},
    },
    {
        "id": "jobs",
        "type": "group",
        "title": "Jobs",
        "properties": {
            "repeat": {"min_items": 1, "max_items": 2, "item_label": "Job", "export_layout": "columns"},
            "fields": [{"id": "employer", "type": "short_text", "title": "Employer", "validations": {"required": True}}],
        },
    },
]
HEADER = [
    "Name", "Age", "Mail", "Colour", "Start", "End",
    "Job 1 – Employer", "Job 2 – Employer",
]

# (case, answers a respondent posts, cells the file holds)
CASES = [
    ("valid", {"name": "Ada", "age": 30, "colour": "c1", "jobs": ["X"]}, ["Ada", "30", "", "Red", "", "", "X", ""]),
    ("name missing", {"age": 30, "jobs": ["X"]}, ["", "30", "", "", "", "", "X", ""]),
    ("name too long", {"name": "Lovelace", "jobs": ["X"]}, ["Lovelace", "", "", "", "", "", "X", ""]),
    ("age too low", {"name": "Ada", "age": 3, "jobs": ["X"]}, ["Ada", "3", "", "", "", "", "X", ""]),
    ("age too high", {"name": "Ada", "age": 99, "jobs": ["X"]}, ["Ada", "99", "", "", "", "", "X", ""]),
    ("no job", {"name": "Ada", "jobs": []}, ["Ada", "", "", "", "", "", "", ""]),
    ("job without employer", {"name": "Ada", "jobs": [""]}, ["Ada", "", "", "", "", "", "", ""]),
    ("two jobs", {"name": "Ada", "jobs": ["X", "Y"]}, ["Ada", "", "", "", "", "", "X", "Y"]),
    ("dates in order", {"name": "Ada", "start": "2026-01-01", "end": "2026-02-01", "jobs": ["X"]}, ["Ada", "", "", "", "2026-01-01", "2026-02-01", "X", ""]),
    ("end before start", {"name": "Ada", "start": "2026-03-01", "end": "2026-02-01", "jobs": ["X"]}, ["Ada", "", "", "", "2026-03-01", "2026-02-01", "X", ""]),
]


def posted(case):
    given = case[1]
    answers = {}
    for key, value in given.items():
        if key == "name":
            answers[key] = {"type": "text", "text": value}
        elif key == "age":
            answers[key] = {"type": "number", "number": value}
        elif key == "colour":
            answers[key] = {"type": "choice", "choice": {"value": value}}
        elif key in ("start", "end"):
            answers[key] = {"type": "date", "date": value}
        elif key == "jobs":
            items = [{"employer": {"type": "text", "text": v}} if v else {} for v in value]
            answers[key] = {"type": "group", "items": items}
    return answers


async def test_the_import_and_the_respondent_agree_on_every_case(client: AsyncClient, workspace):
    form = await publish_form(workspace, FIELDS, title="Parity")
    service = container.workspace_form_service()
    respondent = {}
    for case in CASES:
        try:
            await service.submit_response(
                workspace.id, form.form_id, StandardFormResponseCamelModel(answers=posted(case)), testUser
            )
            respondent[case[0]] = set()
        except HTTPException as refused:
            content = refused.content
            if isinstance(content, dict) and content.get("errors"):
                respondent[case[0]] = {e["rule"] for e in content["errors"]}
            else:
                respondent[case[0]] = {"refused"}

    rows = [HEADER] + [case[2] for case in CASES]
    first = (await upload(client, workspace, form, csv_bytes(rows))).json()
    assert first["mapping"]["0"] == "q:name" and first["mapping"]["7"].startswith("q:jobs#1#")
    queued = await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    assert queued.status_code == 202, queued.text
    await run_job(first["id"])
    body = (await get(client, workspace, form, first["id"])).json()
    assert body["status"] == "checked"
    by_row = {}
    for problem in body["problems"]:
        by_row.setdefault(problem["row"], set()).add(problem["code"])
    for index, case in enumerate(CASES):
        imported = by_row.get(index + 2, set())
        assert bool(imported) == bool(respondent[case[0]]), (case[0], imported, respondent[case[0]])
        if respondent[case[0]] == {"refused"}:
            # a refusal that names no rule (a date rule, a group limit, an empty group the file leaves out): the import's own codes
            assert imported <= {"date_rule", "group_invalid", "required"}, (case[0], imported)
        else:
            assert imported == respondent[case[0]], (case[0], imported, respondent[case[0]])


# ---------------------------------------------------------------- a second set

FIELDS_2 = [
    {"id": "qty", "type": "number", "title": "Quantity"},
    {"id": "price", "type": "number", "title": "Price"},
    {
        "id": "total",
        "type": "calculated",
        "title": "Total",
        "properties": {"expression": {"*": [{"var": "qty"}, {"var": "price"}]}},
    },
    {
        "id": "note",
        "type": "short_text",
        "title": "Note",
        "validations": {"required": True},
        "properties": {
            "logic": {
                "action": "SHOW",
                "operator": "AND",
                "conditions": [{"field_id": "qty", "field_type": "number", "comparison": "is_not_empty"}],
            }
        },
    },
    {"id": "sku", "type": "short_text", "title": "Code", "validations": {"min_length": 3}},
]
HEADER_2 = ["Quantity", "Price", "Total", "Note", "Code", "Hidden: utm"]
CASES_2 = [
    # label, respondent answers, hidden, cells
    ("empty: the note is hidden by logic, so not required", {}, None, ["", "", "", "", "", ""]),
    ("quantity asked: the note is required", {"qty": 2}, None, ["2", "", "", "", "", ""]),
    ("quantity and note", {"qty": 2, "note": "ok"}, None, ["2", "", "", "ok", "", ""]),
    ("a note under a hidden question stays", {"note": "kept"}, None, ["", "", "", "kept", "", ""]),
    ("code too short", {"sku": "ab"}, None, ["", "", "", "", "ab", ""]),
    ("a declared hidden field", {}, {"utm": "mail"}, ["", "", "", "", "", "mail"]),
    ("a calculated cell is the server's: what the file says is dropped", {"qty": 2, "price": 3, "note": "x"}, None, ["2", "3", "999", "x", "", ""]),
]


def posted_2(given):
    out = {}
    for key, value in given.items():
        if key in ("qty", "price"):
            out[key] = {"type": "number", "number": value}
        else:
            out[key] = {"type": "text", "text": value}
    return out


async def test_the_import_and_the_respondent_agree_on_calculations_logic_and_hidden_fields(client: AsyncClient, workspace):
    form = await publish_form(workspace, FIELDS_2, hidden=["utm"], title="Parity two")
    service = container.workspace_form_service()
    respondent = {}
    for label, given, hidden, _ in CASES_2:
        try:
            await service.submit_response(
                workspace.id,
                form.form_id,
                StandardFormResponseCamelModel(answers=posted_2(given), hidden_fields=hidden),
                testUser,
            )
            respondent[label] = set()
        except HTTPException as refused:
            content = refused.content
            respondent[label] = {e["rule"] for e in content.get("errors", [])} or {"refused"}
    rows = [HEADER_2] + [case[3] for case in CASES_2]
    first = (await upload(client, workspace, form, csv_bytes(rows))).json()
    assert first["mapping"]["5"] == "hidden:utm"
    assert any(n["code"] == "calculated_ignored" for n in first["notes"])
    await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    await run_job(first["id"])
    body = (await get(client, workspace, form, first["id"])).json()
    by_row = {}
    for problem in body["problems"]:
        by_row.setdefault(problem["row"], set()).add(problem["code"])
    for index, case in enumerate(CASES_2):
        assert by_row.get(index + 2, set()) == respondent[case[0]], (case[0], by_row.get(index + 2), respondent[case[0]])


async def test_an_import_enforces_whatever_the_switch_for_respondents_says(client: AsyncClient, workspace, monkeypatch):
    from backend.config import settings

    form = await publish_form(workspace, FIELDS, title="Enforce")
    monkeypatch.setattr(settings, "RESPONSE_VALIDATION_ENFORCE", False)
    service = container.workspace_form_service()
    # a respondent with a missing required answer is let through (log only)...
    await service.submit_response(
        workspace.id, form.form_id, StandardFormResponseCamelModel(answers={"age": {"type": "number", "number": 3}}), testUser
    )
    # ...an import is not
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["", "30", "", "", "", "", "", ""]]))).json()
    await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    await run_job(first["id"])
    body = (await get(client, workspace, form, first["id"])).json()
    assert body["rowsInvalid"] == 1 and body["problems"][0]["code"] == "required"
