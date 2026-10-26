"""The responses listings read a form's title and importer through the forms
repositories (``response_scope.form_titles`` / ``form_importers``), not by a
Mongo ``$lookup`` into ``forms`` / ``workspace_forms``: the forms group may
leave Mongo while responses are still served from it.

Through the container's repositories, so each storage mode (mongo, dual,
postgres) runs its own composition.
"""

import pytest
from common.ids import RecordId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.repositories.response_scope import (
    ResponseScope,
    mongo_lookup_stages,
)
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.models.user import User


async def _seed():
    """Workspace ``ws`` with two linked forms (one titled like a Mongo field
    path), a form linked to another workspace only, and a response plus a
    deletion request on each; ``gone`` has responses but no form any more."""
    ws, other = RecordId(), RecordId()
    forms, links = container.form_repo(), container.workspace_form_repo()
    responses = container.form_response_repo()
    for form_id, title in (("f1", "Alpha"), ("f2", "$answers"), ("f3", "Other")):
        await forms.save_form(
            FormDocument(id=RecordId(), form_id=form_id, title=title)
        )
    for workspace_id, form_id, user_id in (
        (ws, "f1", "importer-1"),
        (ws, "f2", "importer-2"),
        (other, "f3", "importer-3"),
        (other, "f1", "importer-other"),  # f1 is linked to both workspaces
    ):
        await links.save(
            WorkspaceFormDocument(
                id=RecordId(),
                workspace_id=workspace_id,
                form_id=form_id,
                user_id=user_id,
            )
        )
    for form_id, workspace_id in (
        ("f1", ws),
        ("f2", ws),
        ("gone", ws),
        ("f3", other),
    ):
        saved = await responses.save(
            FormResponseDocument(
                id=RecordId(),
                form_id=form_id,
                response_id=f"r-{form_id}",
                workspace_id=workspace_id,
                dataOwnerIdentifier="owner@example.com",
                provider="self",
                answers={},
            )
        )
        await responses.add_deletion_request(saved, saved.response_id)
    return ws, ResponseScope(ws, ("f1", "f2", "gone"))


def _page():
    return set_page(Page), set_params(Params(page=1, size=10))


async def test_responses_carry_their_form_title():
    ws, scope = await _seed()
    page_ctx, params_ctx = _page()
    with page_ctx, params_ctx:
        page = await container.form_response_repo().list(
            scope, request_for_deletion=False
        )
    titles = {item["form_id"]: item["form_title"] for item in page.items}
    # a deleted form's responses are left out (the $unwind did that); a
    # title that looks like a field path is the title, not that field
    assert titles == {"f1": "Alpha", "f2": "$answers"}
    assert page.total == 2
    assert {item["status"] for item in page.items} == {"pending"}


async def test_deletion_requests_carry_title_and_this_workspaces_importer():
    ws, scope = await _seed()
    page_ctx, params_ctx = _page()
    with page_ctx, params_ctx:
        page = await container.form_response_repo().list(
            scope, request_for_deletion=True
        )
    got = {
        item["form_id"]: (item["form_title"], item["form_imported_by"])
        for item in page.items
    }
    # f1 is linked to the other workspace too: this workspace's importer only
    assert got == {"f1": ("Alpha", "importer-1"), "f2": ("$answers", "importer-2")}


async def test_a_responders_own_listings_are_composed_too():
    ws, scope = await _seed()
    user = User(id=str(RecordId()), sub="owner@example.com")
    responses = container.form_response_repo()
    page_ctx, params_ctx = _page()
    with page_ctx, params_ctx:
        submissions = await responses.get_user_submissions(scope, user)
        requests = await responses.get_user_submissions(
            scope, user, request_for_deletion=True
        )
    assert {i["form_title"] for i in submissions.items} == {"Alpha", "$answers"}
    assert {i["form_imported_by"] for i in requests.items} == {
        "importer-1",
        "importer-2",
    }


async def test_a_form_deleted_after_its_responses_drops_out_of_the_listing():
    ws, scope = await _seed()
    await container.form_repo().delete_form("f2")
    page_ctx, params_ctx = _page()
    with page_ctx, params_ctx:
        page = await container.form_response_repo().list(
            scope, request_for_deletion=False
        )
    assert {item["form_id"] for item in page.items} == {"f1"}


@pytest.mark.parametrize("by_form", [{}, {"a": "$x", "b": {"$gt": 1}}])
def test_the_composed_values_are_literals(by_form):
    match, set_stage = mongo_lookup_stages("t", by_form)
    assert match == {"$match": {"form_id": {"$in": list(by_form)}}}
    elem = set_stage["$set"]["t"]["$arrayElemAt"]
    assert elem[0] == {"$literal": list(by_form.values())}
    assert elem[1] == {"$indexOfArray": [{"$literal": list(by_form)}, "$form_id"]}
