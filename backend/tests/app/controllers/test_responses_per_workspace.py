"""#768: a provider form linked to two workspaces (same provider form id in
both). Each workspace's import brings its own copy of the responses, and
every read path — staff, respondent and MCP — shows a workspace only the
responses collected or imported there."""

from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.response_scope import ResponseScope
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text
from tests.conftest import access_token

FORM_ID = "1FAIpQLSe-shared-provider-form"
RESPONDENT = testUser2  # answered through both workspaces' imports


def _cookies(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _converted(response_ids: List[str]) -> dict:
    """What a provider's conversion returns: the form and its responses."""
    return {
        "form": {
            "form_id": FORM_ID,
            "title": "Shared provider form",
            "settings": {"provider": "google"},
            "fields": [{"id": "q1", "type": "short_text", "title": "Name"}],
        },
        "responses": [
            {
                "response_id": response_id,
                "form_id": FORM_ID,
                "provider": "google",
                "dataOwnerIdentifier": RESPONDENT.sub,
                "submission_uuid": f"uuid-{response_id}",
                "answers": {"q1": {"field": {"id": "q1"}, "text": response_id}},
            }
            for response_id in response_ids
        ],
    }


async def _import(workspace, user, response_ids, slug):
    await container.form_import_service().save_converted_form_and_responses(
        _converted(response_ids), None, workspace_id=workspace.id
    )
    await container.workspace_form_repo().save_workspace_form(
        workspace_id=workspace.id,
        form_id=FORM_ID,
        user_id=user.id,
        workspace_form_settings=WorkspaceFormSettings(
            custom_url=slug, provider="google", private=False
        ),
    )


@pytest.fixture(autouse=True)
def _no_auth_service():
    """The forms listing asks the auth service who imported each form."""
    with patch.object(
        container.form_service(),
        "fetch_user_details",
        AsyncMock(return_value={"users_info": []}),
    ):
        yield


@pytest.fixture()
async def shared(workspace, workspace_1):
    """A = ``workspace`` (testUser) imported ra1, ra2; B = ``workspace_1``
    (testUser1) imported rb1."""
    await _import(workspace, testUser, ["ra1", "ra2"], "shared-a")
    await _import(workspace_1, testUser1, ["rb1"], "shared-b")
    return workspace, workspace_1


def _ids(items) -> set:
    return {item["responseId"] for item in items}


def _url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


async def _stored(response_id):
    return await container.form_response_repo().get_response(response_id)


class TestStaffReads:
    async def test_imports_are_stamped_with_their_workspace(self, shared):
        a, b = shared
        assert (await _stored("ra1")).workspace_id == a.id
        assert (await _stored("rb1")).workspace_id == b.id

    async def test_lists_and_exports_show_each_workspace_its_own(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        for workspace, cookies, expected in (
            (a, test_user_cookies, {"ra1", "ra2"}),
            (b, test_user_cookies_1, {"rb1"}),
        ):
            base = _url(workspace)
            dashboard = await client.get(
                f"{base}/forms/{FORM_ID}/submissions", cookies=cookies
            )
            assert dashboard.status_code == 200, dashboard.text
            assert _ids(dashboard.json()["items"]) == expected
            everything = await client.get(f"{base}/all-submissions", cookies=cookies)
            assert _ids(everything.json()["items"]) == expected
            for path in ("all-submissions", "all-submissions/export"):
                listed = await client.get(
                    f"{base}/forms/{FORM_ID}/{path}", cookies=cookies
                )
                assert listed.status_code == 200, listed.text
                assert _ids(listed.json()) == expected
            # answers decrypt under the workspace's own key context
            assert {
                item["answers"]["q1"]["text"] for item in dashboard.json()["items"]
            } == expected

    async def test_counts_and_data_subjects_are_per_workspace(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        for workspace, cookies, count in (
            (a, test_user_cookies, 2),
            (b, test_user_cookies_1, 1),
        ):
            base = _url(workspace)
            stats = await client.get(f"{base}/stats", cookies=cookies)
            assert stats.status_code == 200, stats.text
            assert stats.json()["responses"] == count
            forms = await client.get(f"{base}/forms", cookies=cookies)
            listed = next(f for f in forms.json()["items"] if f["formId"] == FORM_ID)
            assert listed["responses"] == count
            responders = await client.get(f"{base}/responders", cookies=cookies)
            assert responders.status_code == 200, responders.text
            (row,) = responders.json()["items"]
            assert row["responses"] == count

    async def test_a_response_of_the_other_workspace_is_not_found(
        self, client: AsyncClient, shared, test_user_cookies
    ):
        a, _ = shared
        base = _url(a)
        assert (
            await client.get(f"{base}/submissions/rb1", cookies=test_user_cookies)
        ).status_code == 404
        assert (
            await client.get(f"{base}/submissions/ra1", cookies=test_user_cookies)
        ).status_code == 200
        writes = [
            client.patch(
                f"{base}/forms/{FORM_ID}/submissions/rb1/internal-answers",
                cookies=test_user_cookies,
                json={"answers": {"x": None}},
            ),
            client.post(
                f"{base}/forms/{FORM_ID}/submissions/rb1/feedback",
                cookies=test_user_cookies,
                json={"message": "hello"},
            ),
            client.delete(f"{base}/submissions/rb1", cookies=test_user_cookies),
        ]
        for write in writes:
            answered = await write
            assert answered.status_code == 404, (answered.request.url, answered.text)
        # staff deletion (its route takes ObjectId form ids: native forms)
        with pytest.raises(HTTPException) as refused:
            await container.workspace_form_service().delete_form_response(
                a.id, FORM_ID, "rb1", testUser
            )
        assert refused.value.status_code == 404
        assert await _stored("rb1") is not None
        assert not await container.form_response_repo().find_deletion_request_by_response_id(
            "rb1"
        )

    async def test_deletion_requests_are_per_workspace(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        filed = await client.delete(
            f"{_url(b)}/submissions/rb1", cookies=test_user_cookies_1
        )
        assert filed.status_code == 200, filed.text
        assert (
            await container.form_response_repo().find_deletion_request_by_response_id(
                "rb1"
            )
        ).workspace_id == b.id
        for workspace, cookies, expected in (
            (a, test_user_cookies, set()),
            (b, test_user_cookies_1, {"rb1"}),
        ):
            base = _url(workspace)
            requests = await client.get(
                f"{base}/all-submissions",
                params={"request_for_deletion": True},
                cookies=cookies,
            )
            assert _ids(requests.json()["items"]) == expected
            for item in requests.json()["items"]:
                assert item["formImportedBy"] == testUser1.id  # B's importer
            per_form = await client.get(
                f"{base}/forms/{FORM_ID}/submissions",
                params={"request_for_deletion": True},
                cookies=cookies,
            )
            assert _ids(per_form.json()["items"]) == expected
            stats = await client.get(f"{base}/stats", cookies=cookies)
            assert (stats.json()["deletionRequests"].get("total") or 0) == len(expected)
            forms = await client.get(f"{base}/forms", cookies=cookies)
            listed = next(f for f in forms.json()["items"] if f["formId"] == FORM_ID)
            assert listed["deletionRequests"] == len(expected)


class TestRespondentReads:
    async def test_my_submissions_lists_this_workspaces_only(
        self, client: AsyncClient, shared
    ):
        a, b = shared
        for workspace, expected in ((a, {"ra1", "ra2"}), (b, {"rb1"})):
            mine = await client.get(
                f"{_url(workspace)}/submissions", cookies=_cookies(RESPONDENT)
            )
            assert mine.status_code == 200, mine.text
            assert _ids(mine.json()["items"]) == expected

    async def test_own_submission_and_receipt_only_in_their_workspace(
        self, client: AsyncClient, shared
    ):
        a, _ = shared
        base, cookies = _url(a), _cookies(RESPONDENT)
        own = await client.get(f"{base}/submissions/ra1", cookies=cookies)
        assert own.status_code == 200, own.text
        assert (
            await client.get(f"{base}/submissions/rb1", cookies=cookies)
        ).status_code == 404

        receipt = await client.get(f"{base}/submissions/by-uuid/uuid-ra1")
        assert receipt.status_code == 200, receipt.text
        # the form context is this workspace's, never the other's
        assert receipt.json()["form"]["settings"]["customUrl"] == "shared-a"
        assert (
            await client.get(f"{base}/submissions/by-uuid/uuid-rb1")
        ).status_code == 404
        assert (
            await client.delete(f"{base}/submissions/by-uuid/uuid-rb1")
        ).status_code == 404
        assert not await container.form_response_repo().find_deletion_request_by_response_id(
            "rb1"
        )


class TestMcp:
    async def test_mcp_reads_are_per_workspace(
        self, client: AsyncClient, shared, test_user_cookies_1
    ):
        a, b = shared
        token = await _make_key(a.id, ["responses:read", "deletion_requests:read"])
        filed = await client.delete(
            f"{_url(b)}/submissions/rb1", cookies=test_user_cookies_1
        )
        assert filed.status_code == 200

        listed = _tool_text(
            await _call_tool(client, token, "list_responses", {"form_id": FORM_ID})
        )
        assert {item["responseId"] for item in listed} == {"ra1", "ra2"}
        own = _tool_text(
            await _call_tool(client, token, "get_response", {"response_id": "ra1"})
        )
        assert own["answers"]["q1"]["text"] == "ra1"
        other = await _call_tool(client, token, "get_response", {"response_id": "rb1"})
        assert other.get("isError")
        requests = _tool_text(
            await _call_tool(client, token, "list_deletion_requests", {})
        )
        assert requests == []


class TestWrites:
    async def test_reimport_replaces_only_its_own_copy(self, shared):
        a, b = shared
        before = await _stored("ra1")
        await container.form_import_service().save_converted_form_and_responses(
            _converted(["ra1"]), None, workspace_id=a.id
        )
        repo = container.form_response_repo()
        a_scope = ResponseScope(a.id, (FORM_ID,))
        b_scope = ResponseScope(b.id, (FORM_ID,))
        assert [r.response_id for r in await repo.list_by_form_id(a_scope)] == ["ra1"]
        assert (await _stored("ra1")).id == before.id  # updated, not duplicated
        assert [r.response_id for r in await repo.list_by_form_id(b_scope)] == ["rb1"]

    async def test_unlinking_the_form_deletes_only_that_workspaces_responses(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        removed = await client.delete(
            f"{_url(a)}/forms/{FORM_ID}", cookies=test_user_cookies
        )
        assert removed.status_code == 200, removed.text
        assert await _stored("ra1") is None and await _stored("ra2") is None
        listed = await client.get(
            f"{_url(b)}/forms/{FORM_ID}/submissions", cookies=test_user_cookies_1
        )
        assert _ids(listed.json()["items"]) == {"rb1"}

    async def test_a_native_submission_is_stamped_with_its_workspace(
        self, workspace, workspace_form_response
    ):
        stored = await _stored(workspace_form_response["response_id"])
        assert stored.workspace_id == PydanticObjectId(workspace.id)
