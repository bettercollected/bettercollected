"""Deletion requests are keyed per workspace: the same provider response
imported into two workspaces (one copy in each, #768) gets its own request in
each. A request filed in workspace A neither blocks nor shows in workspace B;
filing twice in one workspace is refused as before; a legacy request stored
without a workspace is still found."""

import pytest
from beanie import PydanticObjectId
from httpx import AsyncClient
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.standard_form_response import (
    DELETION_REQUEST_INDEX,
    LEGACY_DELETION_REQUEST_INDEX,
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.db.models import ResponseDeletionRequestRow
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_responses_per_workspace import (  # noqa: F401
    FORM_ID,
    _import,
    _no_auth_service,
    _url,
)


@pytest.fixture()
async def same_response(workspace, workspace_1):
    """The provider response ``r1`` imported into A (``workspace``, testUser)
    and into B (``workspace_1``, testUser1): one copy in each."""
    await _import(workspace, testUser, ["r1"], "shared-a")
    await _import(workspace_1, testUser1, ["r1"], "shared-b")
    return workspace, workspace_1


async def _file(client, workspace, cookies):
    return await client.delete(f"{_url(workspace)}/submissions/r1", cookies=cookies)


async def _listed(client, workspace, cookies):
    """The response ids of the workspace's deletion requests list."""
    listed = await client.get(
        f"{_url(workspace)}/all-submissions",
        params={"request_for_deletion": True},
        cookies=cookies,
    )
    assert listed.status_code == 200, listed.text
    return [item["responseId"] for item in listed.json()["items"]]


async def _status_shown(client, workspace, cookies):
    """The deletion status the submissions list shows on r1."""
    listed = await client.get(
        f"{_url(workspace)}/forms/{FORM_ID}/submissions", cookies=cookies
    )
    assert listed.status_code == 200, listed.text
    (item,) = [i for i in listed.json()["items"] if i["responseId"] == "r1"]
    return item.get("status")


async def _responder_requests(client, workspace, cookies):
    responders = await client.get(f"{_url(workspace)}/responders", cookies=cookies)
    assert responders.status_code == 200, responders.text
    (row,) = responders.json()["items"]
    return row["deletionRequests"]


async def _stored_workspaces():
    requests = await FormResponseDeletionRequest.find({"response_id": "r1"}).to_list()
    return sorted(str(r.workspace_id) for r in requests)


class TestPerWorkspace:
    async def test_a_request_in_one_workspace_neither_blocks_nor_shows_in_the_other(
        self, client: AsyncClient, same_response, test_user_cookies, test_user_cookies_1
    ):
        a, b = same_response
        filed = await _file(client, a, test_user_cookies)
        assert filed.status_code == 200, filed.text

        # B sees nothing of A's request
        assert await _listed(client, b, test_user_cookies_1) == []
        assert await _status_shown(client, b, test_user_cookies_1) is None
        assert await _responder_requests(client, b, test_user_cookies_1) == 0
        # A does
        assert await _listed(client, a, test_user_cookies) == ["r1"]
        assert await _status_shown(client, a, test_user_cookies) == "pending"
        assert await _responder_requests(client, a, test_user_cookies) == 1

        # and A's request does not block B's own
        filed = await _file(client, b, test_user_cookies_1)
        assert filed.status_code == 200, filed.text
        for workspace, cookies in ((a, test_user_cookies), (b, test_user_cookies_1)):
            assert await _listed(client, workspace, cookies) == ["r1"]
            assert await _status_shown(client, workspace, cookies) == "pending"
            assert await _responder_requests(client, workspace, cookies) == 1
        if not container.flags().requires_postgres() or container.flags().mirror_store(
            "responses"
        ):
            assert await _stored_workspaces() == sorted([str(a.id), str(b.id)])

    async def test_filing_twice_in_one_workspace_is_refused(
        self, client: AsyncClient, same_response, test_user_cookies
    ):
        a, _ = same_response
        assert (await _file(client, a, test_user_cookies)).status_code == 200
        again = await _file(client, a, test_user_cookies)
        assert again.status_code == 400, again.text
        assert "already exists" in again.text
        assert await _listed(client, a, test_user_cookies) == ["r1"]

    async def test_a_legacy_unstamped_request_is_still_found(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        """A request stored before requests carried a workspace (the backfill
        has stamped them all, but the reads keep accepting one) still counts
        for the response: listed, shown, and filing again is refused."""
        await _import(workspace, testUser, ["r1"], "only-a")
        repo = container.form_response_repo()
        (copy,) = await repo.list_by_response_id("r1")
        assert copy.workspace_id == workspace.id
        unstamped = copy.model_copy(update={"workspace_id": None})
        assert (await repo.add_deletion_request(unstamped, "r1")).workspace_id is None

        assert await _listed(client, workspace, test_user_cookies) == ["r1"]
        assert await _status_shown(client, workspace, test_user_cookies) == "pending"
        assert await _responder_requests(client, workspace, test_user_cookies) == 1
        again = await _file(client, workspace, test_user_cookies)
        assert again.status_code == 400, again.text


def _request(workspace_id, provider="google"):
    return FormResponseDeletionRequest(
        id=PydanticObjectId(),
        form_id="f1",
        response_id="r1",
        provider=provider,
        workspace_id=workspace_id,
    )


class TestTheKey:
    async def test_mongo_one_request_per_response_provider_and_workspace(self):
        a, b = PydanticObjectId(), PydanticObjectId()
        await _request(a).insert()
        await _request(b).insert()  # another workspace: its own request
        await _request(a, provider=None).insert()  # another provider
        with pytest.raises(DuplicateKeyError, match=DELETION_REQUEST_INDEX):
            await _request(a).insert()
        # no workspace (stored before #768) indexes as null, so two of them
        # collide, as NULLS NOT DISTINCT in Postgres; a missing field too
        await _request(None).insert()
        with pytest.raises(DuplicateKeyError, match=DELETION_REQUEST_INDEX):
            await _request(None).insert()
        with pytest.raises(DuplicateKeyError, match=DELETION_REQUEST_INDEX):
            await FormResponseDeletionRequest.get_pymongo_collection().insert_one(
                {"form_id": "f1", "response_id": "r1", "provider": "google"}
            )
        assert await FormResponseDeletionRequest.find({}).count() == 4

    async def test_postgres_one_request_per_response_provider_and_workspace(
        self, clean_postgres
    ):
        repo = PostgresFormResponseRepository(container.pg_sessionmaker(), None, None)

        async def save(document):
            return await repo.save_document(document, row=ResponseDeletionRequestRow)

        a, b = PydanticObjectId(), PydanticObjectId()
        await save(_request(a))
        await save(_request(b))
        await save(_request(a, provider=None))
        with pytest.raises(IntegrityError, match=DELETION_REQUEST_INDEX):
            await save(_request(a))
        await save(_request(None))
        with pytest.raises(IntegrityError, match=DELETION_REQUEST_INDEX):
            await save(_request(None))

    async def test_mongo_drops_the_superseded_per_response_key_when_it_refuses(self):
        """A Mongo database from before still has the unique (form_id,
        response_id, provider) index, which Beanie never drops. The first
        request it refuses for another workspace drops it, and the request
        is stored."""
        collection = FormResponseDeletionRequest.get_pymongo_collection()
        await collection.create_index(
            [("form_id", 1), ("response_id", 1), ("provider", 1)],
            unique=True,
            name=LEGACY_DELETION_REQUEST_INDEX,
        )
        try:
            repo = FormResponseRepository(crypto=container.crypto())
            a, b = PydanticObjectId(), PydanticObjectId()
            await repo.add_deletion_request(_copy(a), "r1")
            request = await repo.add_deletion_request(_copy(b), "r1")
            assert request.workspace_id == b
            indexes = await collection.index_information()
            assert LEGACY_DELETION_REQUEST_INDEX not in indexes
            assert DELETION_REQUEST_INDEX in indexes
            # the per-workspace key still refuses a second one in a workspace
            with pytest.raises(DuplicateKeyError, match=DELETION_REQUEST_INDEX):
                await repo.add_deletion_request(_copy(b), "r1")
        finally:
            if LEGACY_DELETION_REQUEST_INDEX in await collection.index_information():
                await collection.drop_index(LEGACY_DELETION_REQUEST_INDEX)


def _copy(workspace_id):
    """A stored copy of the provider response r1 in ``workspace_id``."""
    return FormResponseDocument(
        id=PydanticObjectId(),
        form_id="f1",
        response_id="r1",
        provider="google",
        workspace_id=workspace_id,
    )
