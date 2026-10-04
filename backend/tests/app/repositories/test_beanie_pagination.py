"""Paging over Beanie aggregation queries goes through fastapi-pagination's
``apaginate``. These pin the page totals and slicing the Mongo repositories
rely on, so a pagination library upgrade cannot change them silently.
"""

from beanie import PydanticObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.repositories.deletion_requests_repository import (
    DeletionRequestsRepository,
)
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.schemas.workspace_form import WorkspaceFormDocument


async def _seed_deletion_requests(count: int) -> list[str]:
    workspace_id = PydanticObjectId()
    await FormRepository().save_form(FormDocument(form_id="f1", title="Alpha"))
    await WorkspaceFormRepository().save(
        WorkspaceFormDocument(workspace_id=workspace_id, form_id="f1", user_id="u1")
    )
    for index in range(count):
        await FormResponseDeletionRequest(
            form_id="f1",
            response_id=f"r{index}",
            dataOwnerIdentifier="owner@example.com" if index % 2 else None,
        ).save()
    # A request on a form outside the listed ids is never counted.
    await FormResponseDeletionRequest(form_id="other", response_id="x").save()
    return ["f1"]


async def test_deletion_requests_page_totals_and_slices():
    form_ids = await _seed_deletion_requests(5)

    with set_page(Page), set_params(Params(page=1, size=2)):
        first = await DeletionRequestsRepository.get_deletion_requests(form_ids)
    with set_page(Page), set_params(Params(page=3, size=2)):
        last = await DeletionRequestsRepository.get_deletion_requests(form_ids)

    assert (first.total, first.page, first.size, first.pages) == (5, 1, 2, 3)
    assert len(first.items) == 2
    assert (last.total, last.page, last.pages) == (5, 3, 3)
    assert len(last.items) == 1
    # Items are the aggregation's output, joined with the form's title.
    assert all(item["form_title"] == "Alpha" for item in first.items + last.items)
    assert all(item["form_imported_by"] == "u1" for item in first.items)
    seen = {item["response_id"] for item in first.items + last.items}
    assert seen <= {f"r{index}" for index in range(5)}


async def test_deletion_requests_filtered_total_follows_the_match():
    form_ids = await _seed_deletion_requests(5)

    with set_page(Page), set_params(Params(page=1, size=10)):
        page = await DeletionRequestsRepository.get_deletion_requests(
            form_ids, data_owner_identifier="owner@example.com"
        )

    assert page.total == 2
    assert {item["response_id"] for item in page.items} == {"r1", "r3"}


async def test_deletion_requests_empty_page():
    with set_page(Page), set_params(Params(page=1, size=10)):
        page = await DeletionRequestsRepository.get_deletion_requests(["missing"])

    assert (page.total, page.items) == (0, [])
