"""Form spec endpoints: POST .../forms/validate and
POST .../forms/{form_id}/ops/dry-run (session auth, form.edit, nothing
stored)."""

import copy
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.form_spec import form_to_spec_dict
from common.models.standard_form import (
    StandardChoice,
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from scripts.seed_flow_templates import TEMPLATE_BUILDERS

T = StandardFormFieldType


def _url(workspace, form_id=None):
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    return f"{base}/{form_id}/ops/dry-run" if form_id else f"{base}/validate"


async def _make_v2(form_doc: FormDocument) -> None:
    form_doc.fields = [
        StandardFormField(
            id="page-1",
            index=0,
            type=T.SLIDE,
            properties=StandardFieldProperty(
                fields=[
                    StandardFormField(
                        id="name",
                        index=0,
                        type=T.SHORT_TEXT,
                        title="Your name",
                        properties=StandardFieldProperty(fields=[]),
                    ),
                    StandardFormField(
                        id="pets",
                        index=1,
                        type=T.YES_NO,
                        title="Pets?",
                        properties=StandardFieldProperty(
                            fields=[],
                            choices=[
                                StandardChoice(id="y", value="Yes"),
                                StandardChoice(id="n", value="No"),
                            ],
                        ),
                    ),
                ]
            ),
        ),
        StandardFormField(
            id="page-2",
            index=1,
            type=T.SLIDE,
            properties=StandardFieldProperty(fields=[]),
        ),
    ]
    await container.form_repo().save_form(form_doc)


@pytest.fixture()
async def v2_form(workspace_form) -> FormDocument:
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    return await container.form_repo().get_form_document_by_id(workspace_form.form_id)


VALID = {
    "specVersion": "1",
    "title": "Event sign-up",
    "pages": [
        {
            "id": "p1",
            "jumps": [
                {
                    "conditions": [
                        {"fieldId": "dinner", "comparison": "IS_EQUAL", "value": "No"}
                    ],
                    "target": "__SUBMIT__",
                }
            ],
            "fields": [
                {"id": "name", "type": "short_text", "title": "Your name"},
                {
                    "id": "dinner",
                    "type": "yes_no",
                    "title": "Dinner?",
                    "choices": [{"value": "Yes"}, {"value": "No"}],
                },
            ],
        },
        {
            "id": "p2",
            "fields": [
                {
                    "id": "diet",
                    "type": "short_text",
                    "title": "Diet",
                    "logic": {
                        "action": "SHOW",
                        "conditions": [
                            {
                                "fieldId": "dinner",
                                "comparison": "IS_EQUAL",
                                "value": "Yes",
                            }
                        ],
                    },
                },
                {
                    "id": "mail",
                    "type": "email",
                    "title": "Email",
                    "validations": {"required": True},
                },
            ],
        },
    ],
    "endings": [{"title": "Thanks", "buttonLink": "https://example.org"}],
    "trust": {"privacyPolicyUrl": "https://example.org/privacy"},
}


class TestValidate:
    async def test_a_valid_document(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies,
    ):
        response = await client.post(
            _url(workspace), json=VALID, cookies=test_user_cookies
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True and body["errors"] == []
        # publish checks are warnings, not errors: the email has no reason
        assert body["warnings"][0]["path"] == "/pages/1/fields/1"
        assert "Why we ask this" in body["warnings"][0]["message"]
        assert body["compliance"]["checked"] is False
        assert "AI review" in body["compliance"]["reason"]

    @pytest.mark.parametrize(
        "mutate, path, words",
        [
            (
                lambda d: d["pages"][0]["fields"][0].update(colour="red"),
                "/pages/0/fields/0/colour",
                "Unknown property",
            ),
            (lambda d: d.pop("specVersion"), "/specVersion", "required"),
            (
                lambda d: d["pages"][1]["fields"][0].update(colSpan=0),
                "/pages/1/fields/0/colSpan",
                "greater than or equal to 1",
            ),
            (
                lambda d: d["pages"][0]["jumps"][0].update(target="nowhere"),
                "/pages/0/jumps/0/target",
                "not a page of this form",
            ),
            (
                lambda d: d["pages"][0]["jumps"][0].update(target="p1"),
                "/pages/0/jumps/0/target",
                "cannot jump to itself",
            ),
            (
                lambda d: d["pages"][1]["fields"][0]["logic"]["conditions"][0].update(
                    fieldId="ghost"
                ),
                "/pages/1/fields/0/logic/conditions/0/fieldId",
                "no question",
            ),
            (
                lambda d: d["pages"][1]["fields"][0]["logic"]["conditions"][0].update(
                    fieldId="diet"
                ),
                "/pages/1/fields/0/logic/conditions/0/fieldId",
                "its own answer",
            ),
            (
                lambda d: d["pages"][0]["fields"][1].update(internal=True),
                "/pages/1/fields/0/logic/conditions/0/fieldId",
                "internal field",
            ),
            (
                lambda d: d["pages"][1]["fields"][1].update(id="name"),
                "/pages/1/fields/1/id",
                "used more than once",
            ),
            (
                lambda d: d["endings"][0].update(buttonLink="javascript:alert(1)"),
                "/endings/0/buttonLink",
                "http(s)",
            ),
            (
                lambda d: d["trust"].update(privacyPolicyUrl="ftp://x"),
                "/trust/privacyPolicyUrl",
                "http(s)",
            ),
            (
                lambda d: d["trust"].update(retention={"type": "days", "value": 0}),
                "/trust/retention",
                "days",
            ),
            (
                lambda d: d.update(hiddenFields=["utm", "utm"]),
                "/hiddenFields/1",
                "listed twice",
            ),
            (
                lambda d: d["pages"][1]["fields"].append(
                    {
                        "id": "when",
                        "type": "date",
                        "dateRules": [
                            {
                                "comparison": "after",
                                "target": "field",
                                "fieldId": "name",
                            }
                        ],
                    }
                ),
                "",
                "not a date question",
            ),
        ],
    )
    async def test_problems_come_back_with_paths(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies,
        mutate,
        path,
        words,
    ):
        document = copy.deepcopy(VALID)
        mutate(document)
        response = await client.post(
            _url(workspace), json=document, cookies=test_user_cookies
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is False
        assert any(
            e["path"] == path and words in e["message"] for e in body["errors"]
        ), body["errors"]

    async def test_a_legacy_type_is_accepted_with_a_warning(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        document = copy.deepcopy(VALID)
        document["pages"][1]["fields"].append(
            {"id": "old", "type": "input_short_text", "title": "Old"}
        )
        response = await client.post(
            _url(workspace), json=document, cookies=test_user_cookies
        )
        body = response.json()
        assert body["valid"] is True, body["errors"]
        assert {
            "path": "/pages/1/fields/2/type",
            "message": "'input_short_text' is a legacy type the builder no longer "
            "offers; use a current type for new questions.",
        } in body["warnings"]

    async def test_a_body_that_is_not_an_object(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        response = await client.post(
            _url(workspace), json=["not", "a", "form"], cookies=test_user_cookies
        )
        assert response.status_code == 200
        assert response.json()["errors"] == [
            {"path": "", "message": "The document must be a JSON object."}
        ]

    async def test_every_seeded_template_is_a_valid_document(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        for build in TEMPLATE_BUILDERS:
            template = build()
            form = StandardForm(
                title=template["title"],
                description=template["description"],
                fields=template["fields"],
                builder_version="v2",
            )
            response = await client.post(
                _url(workspace), json=form_to_spec_dict(form), cookies=test_user_cookies
            )
            assert response.json()["valid"] is True, (build.__name__, response.text)

    async def test_outsiders_are_refused(
        self, client: AsyncClient, workspace, test_user_cookies_1
    ):
        response = await client.post(
            _url(workspace), json=VALID, cookies=test_user_cookies_1
        )
        assert response.status_code == 403
        response = await client.post(_url(workspace), json=VALID)
        assert response.status_code == 401


class TestDryRun:
    async def test_previews_ops_with_refs_and_stores_nothing(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        v2_form: FormDocument,
        test_user_cookies,
    ):
        before = (
            await container.form_repo().get_form_document_by_id(v2_form.form_id)
        ).model_dump()
        ops = [
            {
                "op": "add_page",
                "ref": "pg",
                "fields": [{"title": "City", "type": "short_text", "ref": "city"}],
            },
            {
                "op": "set_field_logic",
                "fieldId": "$ref:city",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {"fieldId": "pets", "comparison": "IS_EQUAL", "value": "Yes"}
                    ],
                },
            },
            {"op": "update_field", "fieldId": "name", "patch": {"title": "Full name"}},
            {"op": "move_page", "pageId": "page-2", "index": 0},
            {
                "op": "set_field_validation",
                "fieldId": "name",
                "validation": {"maxLength": 60},
            },
            {"op": "update_form_settings", "patch": {"purpose": "To plan the trip."}},
        ]
        response = await client.post(
            _url(workspace, v2_form.form_id),
            json={"ops": ops},
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True and body["applied"] is True
        assert [r["ok"] for r in body["results"]] == [True] * 6
        new_page = body["results"][0]["createdId"]

        form = body["form"]
        assert form["specVersion"] == "1"
        assert [p["id"] for p in form["pages"]] == ["page-2", "page-1", new_page]
        assert form["pages"][1]["fields"][0]["title"] == "Full name"
        assert form["pages"][1]["fields"][0]["validations"] == {"maxLength": 60}
        city = form["pages"][2]["fields"][0]
        assert city["logic"]["conditions"][0]["fieldId"] == "pets"
        assert form["trust"]["purpose"] == "To plan the trip."

        diff = body["diff"]
        assert diff["changed"] is True
        assert diff["pages"]["added"] == [{"id": new_page, "path": "/pages/2"}]
        assert diff["pages"]["moved"] == [
            {"id": "page-2", "from": "/pages/1", "to": "/pages/0"}
        ]
        assert diff["fields"]["added"] == [
            {"id": city["id"], "path": "/pages/2/fields/0"}
        ]
        changed = {c["id"]: c for c in diff["fields"]["changed"]}
        assert {
            "path": "/pages/1/fields/0/title",
            "before": "Your name",
            "after": "Full name",
        } in changed["name"]["changes"]
        # moving a page is a move, not a change of every field on it
        assert diff["fields"]["moved"] == []
        assert {
            "path": "/trust/purpose",
            "before": None,
            "after": "To plan the trip.",
        } in diff["form"]

        # nothing stored: the form and its settings are as they were
        after = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert after.model_dump() == before
        association = await container.workspace_form_repo().find_workspace_form(
            workspace.id, v2_form.form_id
        )
        assert association.settings.purpose is None

    async def test_atomic_failure_changes_nothing_and_lists_every_error(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        response = await client.post(
            _url(workspace, v2_form.form_id),
            json={
                "atomic": True,
                "ops": [
                    {"op": "update_form_info", "title": "New"},
                    {"op": "remove_field", "fieldId": "ghost"},
                    {
                        "op": "add_field",
                        "pageId": "$ref:missing",
                        "field": {"title": "Q", "type": "short_text"},
                    },
                ],
            },
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["ok"], body["applied"], body["atomic"]) == (False, False, True)
        assert [(r["index"], r["ok"]) for r in body["results"]] == [
            (0, True),
            (1, False),
            (2, False),
        ]
        assert "Unknown reference" in body["results"][2]["message"]
        assert body["diff"]["changed"] is False
        assert body["form"]["title"] == v2_form.title

    async def test_partial_mode_previews_what_applies(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        response = await client.post(
            _url(workspace, v2_form.form_id),
            json={
                "ops": [
                    {"op": "update_form_info", "title": "New"},
                    {"op": "remove_field", "fieldId": "ghost"},
                ]
            },
            cookies=test_user_cookies,
        )
        body = response.json()
        assert (body["ok"], body["applied"]) == (False, True)
        assert body["form"]["title"] == "New"

    async def test_an_invalid_ops_payload_is_a_422_with_paths(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        response = await client.post(
            _url(workspace, v2_form.form_id),
            json={"ops": [{"op": "move_page", "pageId": "page-1"}]},
            cookies=test_user_cookies,
        )
        assert response.status_code == 422, response.text
        errors = response.json()["errors"]
        assert any(e["path"].startswith("/ops/0") for e in errors), errors

    async def test_a_form_without_pages_is_a_422(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        response = await client.post(
            _url(workspace, workspace_form.form_id),
            json={"ops": []},
            cookies=test_user_cookies,
        )
        assert response.status_code == 422
        assert "not built from pages" in response.text

    async def test_outsiders_and_other_workspaces(
        self,
        client: AsyncClient,
        workspace,
        v2_form,
        workspace_1,
        workspace_form_1,
        test_user_cookies,
        test_user_cookies_1,
    ):
        url = _url(workspace, v2_form.form_id)
        response = await client.post(url, json={"ops": []}, cookies=test_user_cookies_1)
        assert response.status_code == 403
        # a form id of another workspace is not found through this one
        response = await client.post(
            _url(workspace, workspace_form_1.form_id),
            json={"ops": []},
            cookies=test_user_cookies,
        )
        assert response.status_code == 404
