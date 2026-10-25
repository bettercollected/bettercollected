"""A workspace's data-subjects (responders) listing shows that workspace's
own responder metadata and tags only, even when another workspace holds
responses from the same email, and a responder can only be tagged with the
workspace's own tags."""

from beanie import PydanticObjectId
from httpx import AsyncClient

from backend.app.container import container
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_responses_per_workspace import (  # noqa: F401
    RESPONDENT,
    _no_auth_service,
    _url,
    shared,
)

EMAIL = RESPONDENT.sub  # holds responses in both workspaces (see ``shared``)


async def _tag(workspace, user, title):
    return await container.workspace_responders_service().create_workspace_tag(
        workspace.id, title, user
    )


async def _patch(client, workspace, cookies, **body):
    return await client.patch(
        f"{_url(workspace)}/responders",
        params={"email": EMAIL},
        cookies=cookies,
        json=body,
    )


async def _listing(client, workspace, cookies):
    listed = await client.get(f"{_url(workspace)}/responders", cookies=cookies)
    assert listed.status_code == 200, listed.text
    return listed.json()


class TestRespondersListingIsWorkspaceScoped:
    async def test_each_workspace_sees_only_its_own_metadata_and_tags(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        tag_a, tag_b = await _tag(a, testUser, "alpha-only"), await _tag(
            b, testUser1, "beta-only"
        )
        for workspace, cookies, tag, team in (
            (a, test_user_cookies, tag_a, "alpha"),
            (b, test_user_cookies_1, tag_b, "beta"),
        ):
            patched = await _patch(
                client, workspace, cookies, metadata={"team": team}, tags=[str(tag.id)]
            )
            assert patched.status_code == 200, patched.text

        for workspace, cookies, tag, team in (
            (a, test_user_cookies, tag_a, "alpha"),
            (b, test_user_cookies_1, tag_b, "beta"),
        ):
            page = await _listing(client, workspace, cookies)
            # one row per responder, never one per workspace that knows the email
            assert page["total"] == 1
            [row] = page["items"]
            assert row["email"] == EMAIL
            assert row["metadata"] == {"team": team}
            assert [t["title"] for t in row["tags"]] == [tag.title]

    async def test_a_workspace_without_a_record_shows_none(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        tag_a = await _tag(a, testUser, "alpha-only")
        patched = await _patch(
            client,
            a,
            test_user_cookies,
            metadata={"team": "alpha"},
            tags=[str(tag_a.id)],
        )
        assert patched.status_code == 200, patched.text

        [row] = (await _listing(client, b, test_user_cookies_1))["items"]
        assert row["email"] == EMAIL
        assert not row.get("metadata")
        assert not row.get("tags")


class TestPatchResponderTags:
    async def test_a_tag_of_another_workspace_is_refused(
        self, client: AsyncClient, shared, test_user_cookies, test_user_cookies_1
    ):
        a, b = shared
        tag_a = await _tag(a, testUser, "alpha-only")
        tag_b = await _tag(b, testUser1, "beta-only")

        foreign = await _patch(client, a, test_user_cookies, tags=[str(tag_b.id)])
        assert foreign.status_code == 404
        mixed = await _patch(
            client, a, test_user_cookies, tags=[str(tag_a.id), str(tag_b.id)]
        )
        assert mixed.status_code == 404
        # not stored: the listing carries no tag
        [row] = (await _listing(client, a, test_user_cookies))["items"]
        assert not row.get("tags")

        # the same tag in its own workspace is fine
        ok = await _patch(client, b, test_user_cookies_1, tags=[str(tag_b.id)])
        assert ok.status_code == 200, ok.text

    async def test_a_foreign_tag_looks_like_one_that_does_not_exist(
        self, client: AsyncClient, shared, test_user_cookies
    ):
        a, b = shared
        tag_b = await _tag(b, testUser1, "beta-only")
        foreign = await _patch(client, a, test_user_cookies, tags=[str(tag_b.id)])
        unknown = await _patch(
            client, a, test_user_cookies, tags=[str(PydanticObjectId())]
        )
        assert (foreign.status_code, foreign.json()) == (
            unknown.status_code,
            unknown.json(),
        )
