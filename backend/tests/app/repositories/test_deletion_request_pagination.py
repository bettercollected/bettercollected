"""Paging over the deletion-request listing goes through fastapi-pagination's
``apaginate``. These pin the page totals and slicing the repository relies on,
so a pagination library upgrade cannot change them silently.
"""

from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.repositories.response_scope import ResponseScope
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.db.models import ResponseDeletionRequestRow
from common.records import RecordId


def _repository() -> PostgresFormResponseRepository:
    return PostgresFormResponseRepository(
        container.pg_sessionmaker(),
        container.form_repo(),
        container.workspace_form_repo(),
    )


async def _seed_deletion_requests(count: int) -> ResponseScope:
    workspace_id = RecordId()
    repository = _repository()
    await container.form_repo().save_form(FormDocument(form_id="f1", title="Alpha"))
    await container.workspace_form_repo().save(
        WorkspaceFormDocument(workspace_id=workspace_id, form_id="f1", user_id="u1")
    )
    for index in range(count):
        await repository.save_document(
            FormResponseDeletionRequest(
                form_id="f1",
                response_id=f"r{index}",
                dataOwnerIdentifier="owner@example.com" if index % 2 else None,
            ),
            row=ResponseDeletionRequestRow,
        )
    # A request on a form outside the listed ids is never counted.
    await repository.save_document(
        FormResponseDeletionRequest(form_id="other", response_id="x"),
        row=ResponseDeletionRequestRow,
    )
    # stored without a workspace_id (before #768): the only workspace's
    return ResponseScope(workspace_id, ("f1",), ("f1",))


async def test_deletion_requests_page_totals_and_slices(clean_postgres):
    form_ids = await _seed_deletion_requests(5)

    with set_page(Page), set_params(Params(page=1, size=2)):
        first = await _repository().get_deletion_requests(form_ids)
    with set_page(Page), set_params(Params(page=3, size=2)):
        last = await _repository().get_deletion_requests(form_ids)

    assert (first.total, first.page, first.size, first.pages) == (5, 1, 2, 3)
    assert len(first.items) == 2
    assert (last.total, last.page, last.pages) == (5, 3, 3)
    assert len(last.items) == 1
    # Items are the listing's rows, joined with the form's title.
    assert all(item["form_title"] == "Alpha" for item in first.items + last.items)
    assert all(item["form_imported_by"] == "u1" for item in first.items)
    seen = {item["response_id"] for item in first.items + last.items}
    assert seen <= {f"r{index}" for index in range(5)}


async def test_deletion_requests_filtered_total_follows_the_match(clean_postgres):
    form_ids = await _seed_deletion_requests(5)

    with set_page(Page), set_params(Params(page=1, size=10)):
        page = await _repository().get_deletion_requests(
            form_ids, data_owner_identifier="owner@example.com"
        )

    assert page.total == 2
    assert {item["response_id"] for item in page.items} == {"r1", "r3"}


async def test_deletion_requests_empty_page(clean_postgres):
    with set_page(Page), set_params(Params(page=1, size=10)):
        page = await _repository().get_deletion_requests(
            ResponseScope(RecordId(), ("missing",))
        )

    assert (page.total, page.items) == (0, [])
