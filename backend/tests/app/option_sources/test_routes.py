"""What a respondent can fetch (labels only, published forms only, rate limited),
what the form payload says about its sources, and the builder's preview."""

import pytest
from common.ids import RecordId
from common.models.standard_form import StandardForm
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.option_sources import service as module
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.option_sources.helpers import make_list, publish, question, submit
from tests.app.option_sources.helpers import text as text_answer

pytestmark = pytest.mark.asyncio

COUNTRIES = [{"id": "nl", "value": "Netherlands"}, {"id": "de", "value": "Germany"}]


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


def options_url(workspace, form, field_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/options/{field_id}"


@pytest.fixture()
async def city_form(workspace):
    created = await make_list(workspace)
    form = await publish(
        workspace,
        [
            question("country", "dropdown", "Country", choices=COUNTRIES),
            question(
                "city",
                "dropdown",
                "City",
                source={
                    "kind": "list",
                    "list_id": created.id,
                    "parent_field_id": "country",
                },
            ),
            question("plain", "dropdown", "Plain", choices=COUNTRIES),
        ],
        title="Cities",
    )
    return created, form


async def test_a_respondent_gets_labels_and_ids_and_nothing_else(
    client: AsyncClient, workspace, city_form
):
    created, form = city_form
    response = await client.get(
        options_url(workspace, form, "city")
    )  # nobody is signed in
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert set(body) == {"items", "total", "truncated", "available"}
    assert (
        body["total"] == 5 and body["available"] is True and body["truncated"] is False
    )
    assert [i["label"] for i in body["items"]] == [
        "Amsterdam",
        "Utrecht",
        "Berlin",
        "Hamburg",
        "Anywhere",
    ]
    assert all(set(i) == {"id", "label"} for i in body["items"])
    # the group key of an item is never sent
    assert "Netherlands" not in response.text and "group" not in response.text.lower()


async def test_search_pages_and_the_parent_filter(
    client: AsyncClient, workspace, city_form
):
    created, form = city_form
    url = options_url(workspace, form, "city")
    found = (await client.get(url, params={"q": "BER"})).json()
    assert [i["label"] for i in found["items"]] == ["Berlin", "Hamburg"][:1] or found[
        "total"
    ] >= 1
    assert [i["label"] for i in found["items"]] == ["Berlin"]
    page = (await client.get(url, params={"limit": 2, "offset": 3})).json()
    assert [i["label"] for i in page["items"]] == ["Hamburg", "Anywhere"] and page[
        "total"
    ] == 5
    # the respondent chose Netherlands in the parent question
    dutch = (await client.get(url, params={"parent": ["nl"]})).json()
    assert [i["label"] for i in dutch["items"]] == ["Amsterdam", "Utrecht", "Anywhere"]
    both = (await client.get(url, params=[("parent", "nl"), ("parent", "de")])).json()
    assert both["total"] == 5
    # an id that is not an option of the parent only offers the items without a group
    assert [
        i["label"]
        for i in (await client.get(url, params={"parent": ["zzz"]})).json()["items"]
    ] == ["Anywhere"]
    assert (await client.get(url, params={"limit": 101})).status_code == 422
    assert (await client.get(url, params={"q": "x" * 101})).status_code == 422


async def test_anything_that_is_not_a_published_sourced_question_is_one_404(
    client: AsyncClient, workspace, workspace_1, city_form
):
    created, form = city_form
    draft = await container.workspace_form_service().create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Draft",
            fields=[
                {
                    "id": "s",
                    "type": "slide",
                    "properties": {
                        "fields": [
                            question(
                                "city",
                                "dropdown",
                                "City",
                                source={"kind": "list", "list_id": created.id},
                            )
                        ]
                    },
                }
            ],
        ),
        testUser,
    )
    other = await publish(
        workspace_1, [question("c", "dropdown", "C")], user=testUser1, title="Other"
    )
    unknown = f"/api/v1/workspaces/{workspace.id}/forms/{RecordId()}/options/city"
    seen = {
        "unpublished": await client.get(options_url(workspace, draft, "city")),
        "unknown form": await client.get(unknown),
        "another workspace's form": await client.get(
            f"/api/v1/workspaces/{workspace.id}/forms/{other.form_id}/options/c"
        ),
        "form of another workspace through this one": await client.get(
            options_url(workspace_1, form, "city")
        ),
        "question without a source": await client.get(
            options_url(workspace, form, "plain")
        ),
        "unknown question": await client.get(options_url(workspace, form, "nope")),
        "long id": await client.get(options_url(workspace, form, "x" * 300)),
    }
    for why, response in seen.items():
        assert response.status_code == 404, (why, response.status_code)
    assert len({r.text for r in seen.values()}) == 1  # the same answer for each


async def test_the_published_version_decides_not_the_draft(
    client: AsyncClient, workspace, city_form
):
    created, form = city_form
    other = await make_list(workspace, name="Other", items=[("Only", None)])
    stored = await container.form_service().get_form_document_by_id(form.form_id)
    for slide in stored.fields:
        for field in slide.properties.fields:
            if field.id == "city":
                field.properties.option_source.list_id = other.id
    await container.form_repo().save_form(stored)  # a draft change, not published
    container.option_source_service()._servable_cache.clear()
    body = (await client.get(options_url(workspace, form, "city"))).json()
    assert body["total"] == 5


async def test_stored_sources_are_still_served_while_the_switch_is_off(
    client: AsyncClient, workspace, city_form, monkeypatch
):
    created, form = city_form
    from backend.config import settings

    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    assert (await client.get(options_url(workspace, form, "city"))).json()["total"] == 5


async def test_the_options_of_another_forms_answers_hold_labels_only(
    client: AsyncClient, workspace
):
    people = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    for name in ("Alice", "Bob", "alice"):
        await submit(workspace, people, {"name": text_answer(name)}, user=testUser1)
    form = await publish(
        workspace,
        [
            question(
                "who",
                "dropdown",
                "Who",
                source={
                    "kind": "form_answers",
                    "form_id": people.form_id,
                    "question_id": "name",
                },
            )
        ],
        title="Who comes",
    )
    response = await client.get(options_url(workspace, form, "who"))
    body = response.json()
    assert [i["label"] for i in body["items"]] == ["Alice", "Bob"]
    assert set(body) == {"items", "total", "truncated", "available"}
    # nothing identifies a response, a person or a count of them
    stored = await container.form_response_repo().list_by_form_id(
        await container.form_response_service().scope(workspace.id, [people.form_id])
    )
    for row in stored:
        for secret in (
            str(row.id),
            str(row.response_id),
            row.dataOwnerIdentifier or "-",
            row.submission_uuid or "-",
        ):
            assert secret not in response.text
    assert (
        "testuser" not in response.text.lower()
        and "bettercollected@email.com" not in response.text
    )
    # the form a respondent loads names neither the other form nor its question
    form_payload = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        params={"published": "true"},
    )
    assert form_payload.status_code == 200
    assert people.form_id not in form_payload.text
    source = form_payload.json()["fields"][0]["properties"]["fields"][0]["properties"][
        "optionSource"
    ]
    assert (
        source["kind"] == "form_answers"
        and not source.get("formId")
        and not source.get("questionId")
    )
    # what is stored (and what a creator reads) has it
    stored = await container.form_service().get_form_document_by_id(form.form_id)
    assert (
        stored.fields[0].properties.fields[0].properties.option_source.form_id
        == people.form_id
    )


async def test_a_respondent_view_of_a_list_source_hides_the_list_id(
    client: AsyncClient, workspace, city_form
):
    created, form = city_form
    payload = await client.get(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}",
        params={"published": "true"},
    )
    assert created.id not in payload.text
    source = payload.json()["fields"][0]["properties"]["fields"][1]["properties"][
        "optionSource"
    ]
    assert (
        source == {"kind": "list", "parentFieldId": "country"}
        or source.get("kind") == "list"
    )


async def test_the_endpoint_is_rate_limited_per_client_and_per_form(
    client: AsyncClient, workspace, city_form, monkeypatch
):
    created, form = city_form
    monkeypatch.setattr(module, "RATE_PER_CLIENT", 3)
    url = options_url(workspace, form, "city")
    assert [(await client.get(url)).status_code for _ in range(3)] == [200, 200, 200]
    limited = await client.get(url)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    # the whole form has a limit too, whoever asks (counters are keyed per form: another form is not slowed)
    monkeypatch.setattr(module, "RATE_PER_CLIENT", 1000)
    monkeypatch.setattr(module, "RATE_PER_FORM", 4)
    status = [(await client.get(url)).status_code for _ in range(3)]
    assert status == [200, 429, 429]  # 3 are already counted for this form
    second = await publish(
        workspace,
        [
            question(
                "c", "dropdown", "C", source={"kind": "list", "list_id": created.id}
            )
        ],
        title="Second",
    )
    assert (await client.get(options_url(workspace, second, "c"))).status_code == 200


# ---------------------------------------------------------------- the preview


@pytest.fixture()
async def privacy_officer(workspace):
    user = User(id=str(RecordId()), sub="privacy@routes.example")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=[WorkspaceRoles.PRIVACY_OFFICER],
        )
    )
    return user


@pytest.fixture()
async def viewer(workspace):
    user = User(id=str(RecordId()), sub="viewer@routes.example")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[WorkspaceRoles.VIEWER]
        )
    )
    return user


def preview_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/option-sources/preview"


async def test_the_preview_shows_a_list_with_its_counts(
    client: AsyncClient, workspace, city_form
):
    created, form = city_form
    response = await client.post(
        preview_url(workspace),
        json={"source": {"kind": "list", "listId": created.id}, "q": "a", "limit": 2},
        cookies=_cookies(testUser),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert body["options"] == 5 and body["total"] == 3 and len(body["items"]) == 2
    dependent = await client.post(
        preview_url(workspace),
        json={
            "source": {"kind": "list", "listId": created.id},
            "parentLabels": ["Germany"],
        },
        cookies=_cookies(testUser),
    )
    assert [i["label"] for i in dependent.json()["items"]] == [
        "Berlin",
        "Hamburg",
        "Anywhere",
    ]


async def test_the_preview_of_another_forms_answers_needs_response_read(
    client: AsyncClient, workspace, privacy_officer, viewer
):
    people = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    await submit(workspace, people, {"name": text_answer("Alice")})
    body = {
        "source": {
            "kind": "form_answers",
            "formId": people.form_id,
            "questionId": "name",
        }
    }
    ok = await client.post(
        preview_url(workspace), json=body, cookies=_cookies(testUser)
    )
    assert ok.status_code == 200 and ok.json()["responses"] == 1
    assert [i["label"] for i in ok.json()["items"]] == ["Alice"]
    # a privacy officer holds neither response.read nor form.edit; a viewer reads answers but edits no form
    for user in (privacy_officer, viewer, testUser1):
        refused = await client.post(
            preview_url(workspace), json=body, cookies=_cookies(user)
        )
        assert refused.status_code == 403, user.sub
        assert "Alice" not in refused.text
    anon = await client.post(preview_url(workspace), json=body)
    assert anon.status_code in (401, 403)
    # naming a form of another workspace is the same refusal as a missing one
    bad = await client.post(
        preview_url(workspace),
        json={
            "source": {
                "kind": "form_answers",
                "formId": str(RecordId()),
                "questionId": "name",
            }
        },
        cookies=_cookies(testUser),
    )
    assert bad.status_code == 422 and bad.json()["code"] == "option_source_invalid"
