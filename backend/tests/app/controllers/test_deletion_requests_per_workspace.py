"""Deletion requests are keyed per workspace: the same provider response
imported into two workspaces (one copy in each, #768) gets its own request in
each. A request filed in workspace A neither blocks nor shows in workspace B;
filing twice in one workspace is refused as before; a legacy request stored
without a workspace is still found."""

import pytest
from beanie import PydanticObjectId
from common.clock import utcnow
from common.db import to_bson_dict
from common.db.beanie_bridge import store_exactly
from httpx import AsyncClient
from loguru import logger
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.handlers.database import ensure_deletion_request_indexes, init_db
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.repositories.response_scope import response_scope
from backend.app.schemas.standard_form_response import (
    DELETION_REQUEST_INDEX,
    LEGACY_DELETION_REQUEST_INDEX,
    FormResponseDeletionRequest,
)
from backend.config import settings
from backend.db.models import ResponseDeletionRequestRow
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_responses_per_workspace import (  # noqa: F401
    FORM_ID,
    _converted,
    _import,
    _no_auth_service,
    _url,
)
from tests.app.response_helpers import deletion_requests_of


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


async def _stored(*workspaces):
    """workspace id -> status of r1's deletion requests stored in each of
    ``workspaces``, read from the read store."""
    found = {}
    for workspace in workspaces:
        for request in await deletion_requests_of(workspace.id, FORM_ID, "r1"):
            found[str(request.workspace_id)] = request.status
    return found


async def _import_with_receipt(workspace, user, slug, receipt):
    """``_import`` of r1 with its own receipt number in this workspace."""
    converted = _converted(["r1"])
    converted["responses"][0]["submission_uuid"] = receipt
    await container.form_import_service().save_converted_form_and_responses(
        converted, None, workspace_id=workspace.id
    )
    await container.workspace_form_repo().save_workspace_form(
        workspace_id=workspace.id,
        form_id=FORM_ID,
        user_id=user.id,
        workspace_form_settings=WorkspaceFormSettings(
            custom_url=slug, provider="google", private=False
        ),
    )


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
        assert await _stored(a, b) == {str(a.id): "pending", str(b.id): "pending"}

    async def test_executing_one_workspaces_request_leaves_the_others_pending(
        self, client: AsyncClient, same_response, test_user_cookies, test_user_cookies_1
    ):
        """Deleting A's copy (staff deletion) completes A's request only."""
        a, b = same_response
        assert (await _file(client, a, test_user_cookies)).status_code == 200
        assert (await _file(client, b, test_user_cookies_1)).status_code == 200

        await container.workspace_form_service().delete_form_response(
            a.id, FORM_ID, "r1", testUser
        )

        assert await _stored(a, b) == {str(a.id): "success", str(b.id): "pending"}
        assert await _status_shown(client, b, test_user_cookies_1) == "pending"

    async def test_a_refresh_completes_only_its_own_workspaces_requests(
        self, client: AsyncClient, same_response, test_user_cookies, test_user_cookies_1
    ):
        """An imported-form refresh in A that no longer finds r1 at the source
        marks A's request done (mark_deletion_requests_success_except), not B's."""
        a, b = same_response
        assert (await _file(client, a, test_user_cookies)).status_code == 200
        assert (await _file(client, b, test_user_cookies_1)).status_code == 200

        scope = await response_scope(container.workspace_form_repo(), a.id, [FORM_ID])
        marked = (
            await container.form_response_repo().mark_deletion_requests_success_except(
                scope, "google", [], utcnow()
            )
        )

        assert marked == 1
        assert await _stored(a, b) == {str(a.id): "success", str(b.id): "pending"}

    async def test_the_listing_shows_the_receipt_of_the_requests_own_copy(
        self, client: AsyncClient, workspace, workspace_1, test_user_cookies_1
    ):
        """Each workspace's copy of r1 has its own receipt number; B's request
        lists B's, though A's copy was stored first."""
        a, b = workspace, workspace_1
        await _import_with_receipt(a, testUser, "receipt-a", "uuid-in-a")
        await _import_with_receipt(b, testUser1, "receipt-b", "uuid-in-b")
        assert (await _file(client, b, test_user_cookies_1)).status_code == 200

        listed = await client.get(
            f"{_url(b)}/all-submissions",
            params={"request_for_deletion": True},
            cookies=test_user_cookies_1,
        )
        assert listed.status_code == 200, listed.text
        (item,) = listed.json()["items"]
        assert item["submissionUuid"] == "uuid-in-b"

    async def test_filing_by_receipt_number_is_per_workspace(
        self, client: AsyncClient, same_response, test_user_cookies, test_user_cookies_1
    ):
        """The receipt path (``by-uuid``): a request filed with r1's receipt in
        A neither blocks the same receipt in B nor shows there; a second one in
        A is refused."""
        a, b = same_response
        by_receipt = "submissions/by-uuid/uuid-r1"
        filed = await client.delete(f"{_url(a)}/{by_receipt}")
        assert filed.status_code == 200, filed.text
        assert await _listed(client, b, test_user_cookies_1) == []

        filed = await client.delete(f"{_url(b)}/{by_receipt}")
        assert filed.status_code == 200, filed.text
        assert await _listed(client, a, test_user_cookies) == ["r1"]
        assert await _listed(client, b, test_user_cookies_1) == ["r1"]
        assert await _stored(a, b) == {str(a.id): "pending", str(b.id): "pending"}

        again = await client.delete(f"{_url(a)}/{by_receipt}")
        assert again.status_code == 400, again.text

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

    async def test_startup_drops_the_superseded_key_and_builds_the_new_one(self):
        """A Mongo database from before still has the unique (form_id,
        response_id, provider) index, which Beanie never drops. The startup
        set-up (Beanie and the indexes after it) drops it and builds the
        per-workspace key; after that, both a direct write and a mirrored one
        (stored exactly, as the reverse mirror does) of another workspace's
        request go through."""
        client = container.database_client()
        app_db = settings.mongo_settings.DB
        name = app_db + "_drstart"
        collection = client[name]["responses_deletion_requests"]
        a, b = PydanticObjectId(), PydanticObjectId()
        await collection.create_index(
            [("form_id", 1), ("response_id", 1), ("provider", 1)],
            unique=True,
            name=LEGACY_DELETION_REQUEST_INDEX,
        )
        await collection.insert_one(to_bson_dict(_request(a)))
        with pytest.raises(DuplicateKeyError, match=LEGACY_DELETION_REQUEST_INDEX):
            await collection.insert_one(to_bson_dict(_request(b)))
        logged = []
        sink = logger.add(lambda m: logged.append(str(m)), level="INFO")
        try:
            await init_db(name, client, required=True)
            assert any("Database connected successfully" in m for m in logged)
            indexes = await collection.index_information()
            assert LEGACY_DELETION_REQUEST_INDEX not in indexes
            assert indexes[DELETION_REQUEST_INDEX]["unique"] is True
            # Beanie is on the scratch database now: the reverse mirror's write
            await store_exactly(_request(b))
            with pytest.raises(DuplicateKeyError, match=DELETION_REQUEST_INDEX):
                await collection.insert_one(to_bson_dict(_request(b)))
            assert await collection.count_documents({}) == 2
            # a second start finds nothing left to drop
            assert await ensure_deletion_request_indexes(client[name]) is True
        finally:
            logger.remove(sink)
            # Beanie back on the test database
            await init_db(app_db, client, required=True)
            await client.drop_database(name)

    async def test_index_failures_are_logged_and_the_start_goes_on(self):
        """Duplicates under the new key (possible only on a database that
        never had the old one) leave it unbuilt: an error with their count,
        no exception."""
        client = container.database_client()
        name = settings.mongo_settings.DB + "_drdups"
        db = client[name]
        a = PydanticObjectId()
        await db["responses_deletion_requests"].insert_many(
            [to_bson_dict(_request(a)), to_bson_dict(_request(a))]
        )
        logged = []
        sink = logger.add(lambda m: logged.append(str(m)), level="ERROR")
        try:
            assert await ensure_deletion_request_indexes(db) is False
            (message,) = [m for m in logged if DELETION_REQUEST_INDEX in m]
            assert "provider and workspace: 1." in message
            assert str(a) not in message  # counts only
        finally:
            logger.remove(sink)
            await client.drop_database(name)
