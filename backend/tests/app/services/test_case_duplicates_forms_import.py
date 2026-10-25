"""The case-duplicate accounts routes count forms in Postgres only (4.1):
while Mongo still holds workspace links of forms that Postgres does not (an
incomplete forms import), every account would count none and the newest of
each group would be kept, so both the plan and a drop refuse with 409
``forms_import_incomplete``. Mongo-driven (tests/conftest.py)."""

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.case_duplicate_accounts import CaseDuplicateAccounts
from common.records import to_bson
from tests.conftest import TEST_MONGO_DB


def _link(workspace_id, form_id):
    return WorkspaceFormDocument(
        id=PydanticObjectId(), workspace_id=workspace_id, form_id=form_id, user_id="u1"
    )


@pytest.fixture
def mongo(clean_postgres):
    return container.database_client()[TEST_MONGO_DB]


def _service(mongo_database):
    service = CaseDuplicateAccounts(
        http_client=None,
        workspace_repo=container.workspace_repo(),
        workspace_form_repo=container.workspace_form_repo(),
        auth_service=None,
        mongo_database=mongo_database,
    )

    async def no_groups():  # the auth service is never asked first
        return []

    service._group_ids = no_groups
    return service


async def test_the_plan_and_drops_wait_for_a_complete_forms_import(mongo):
    ws_a, ws_b = PydanticObjectId(), PydanticObjectId()
    imported, not_yet = _link(ws_a, "f1"), _link(ws_b, "f1")
    await container.workspace_form_repo().save(imported)
    await mongo["workspace_forms"].insert_many([to_bson(imported), to_bson(not_yet)])
    service = _service(lambda: mongo)

    for call in (service.plan, lambda: service.drop(str(PydanticObjectId()))):
        with pytest.raises(HTTPException) as refused:
            await call()
        assert refused.value.status_code == 409
        assert refused.value.content["code"] == "forms_import_incomplete"
        assert str(ws_b) not in refused.value.content["message"]  # counts only

    await container.workspace_form_repo().save(not_yet)
    assert await service.plan() == []
    assert await service.drop(str(PydanticObjectId())) == "not_found"


async def test_without_mongo_nothing_is_checked(clean_postgres):
    service = _service(lambda: None)
    assert await service.plan() == []
