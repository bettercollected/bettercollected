"""``FORM_EMBED_ENABLED`` and the embedding routes: settings (who may read and
change the list), the public policy, and what the public workspace answer leaves out."""

import pytest
from common.ids import RecordId
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.auth_helpers import access_token

pytestmark = pytest.mark.asyncio

viewer = User(id=str(RecordId()), sub="embed-viewer@example.com")
SITE = "https://www.example.org"


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(settings, "FORM_EMBED_ENABLED", True)


@pytest.fixture()
def off(monkeypatch):
    monkeypatch.setattr(settings, "FORM_EMBED_ENABLED", False)


def cookies_of(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def settings_url(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}/embed/settings"


async def add_viewer(workspace):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=viewer.id, roles=[WorkspaceRoles.VIEWER]
        )
    )


def test_the_switch_is_off_by_default():
    from backend.config.application import Application

    assert Application.model_fields["FORM_EMBED_ENABLED"].default is False


async def test_the_permissions_answer_says_whether_it_is_on(
    client, workspace, test_user_cookies, monkeypatch
):
    for enabled in (True, False):
        monkeypatch.setattr(settings, "FORM_EMBED_ENABLED", enabled)
        answer = await client.get(
            f"/api/v1/workspaces/{workspace.id}/permissions", cookies=test_user_cookies
        )
        assert answer.status_code == 200
        assert answer.json()["formEmbedEnabled"] is enabled


async def test_off_the_settings_routes_do_not_exist_for_those_allowed_in(
    client, workspace, test_user_cookies, off
):
    for call in (
        client.get(settings_url(workspace), cookies=test_user_cookies),
        client.put(
            settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
        ),
    ):
        answer = await call
        assert answer.status_code == 404
        assert answer.json()["code"] == "form_embed_disabled"
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert not stored.embed_allowed_origins


async def test_off_refusals_still_come_first(
    client, workspace, test_user_cookies_1, off
):
    # someone with no place in the workspace learns nothing about the switch
    assert (
        await client.get(settings_url(workspace), cookies=test_user_cookies_1)
    ).status_code == 403


async def test_the_owner_saves_and_reads_the_list(
    client, workspace, test_user_cookies, on
):
    saved = await client.put(
        settings_url(workspace),
        json={
            "origins": [
                SITE,
                "HTTPS://Www.Example.org/",
                "https://*.acme.example.org:8443",
            ]
        },
        cookies=test_user_cookies,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["origins"] == [SITE, "https://*.acme.example.org:8443"]
    assert body["canManage"] is True and body["maxOrigins"] == 20
    read = await client.get(settings_url(workspace), cookies=test_user_cookies)
    assert read.json()["origins"] == body["origins"]
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.embed_allowed_origins == body["origins"]
    # the whole list is replaced; an empty one removes every site
    cleared = await client.put(
        settings_url(workspace), json={"origins": []}, cookies=test_user_cookies
    )
    assert cleared.json()["origins"] == []


async def test_a_change_is_logged_with_ids_and_counts_only(
    client, workspace, test_user_cookies, on
):
    from loguru import logger

    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="INFO")
    try:
        await client.put(
            settings_url(workspace),
            json={"origins": [SITE, "https://b.example.org"]},
            cookies=test_user_cookies,
        )
        await client.put(
            settings_url(workspace),
            json={"origins": ["https://b.example.org"]},
            cookies=test_user_cookies,
        )
    finally:
        logger.remove(sink)
    changes = [line for line in lines if "embed allowed sites changed" in line]
    assert len(changes) == 2
    assert "before=0 after=2 added=2 removed=0" in changes[0]
    assert "before=2 after=1 added=0 removed=1" in changes[1]
    assert str(workspace.id) in changes[0]
    assert "example.org" not in "".join(changes)


async def test_a_bad_origin_is_refused_with_its_place_and_nothing_is_kept(
    client, workspace, test_user_cookies, on
):
    await client.put(
        settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
    )
    refused = await client.put(
        settings_url(workspace),
        json={"origins": ["https://ok.example.org", "https://*.com"]},
        cookies=test_user_cookies,
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "origin_wildcard" and refused.json()["index"] == 1
    read = await client.get(settings_url(workspace), cookies=test_user_cookies)
    assert read.json()["origins"] == [SITE]
    too_many = await client.put(
        settings_url(workspace),
        json={"origins": [f"https://s{i}.example.org" for i in range(21)]},
        cookies=test_user_cookies,
    )
    assert too_many.status_code == 422 and too_many.json()["code"] == "too_many_origins"
    way_too_many = await client.put(
        settings_url(workspace),
        json={"origins": [f"https://s{i}.example.org" for i in range(500)]},
        cookies=test_user_cookies,
    )
    assert way_too_many.status_code == 422


async def test_editors_read_but_do_not_change_and_viewers_do_neither(
    client, workspace, test_user_cookies, test_invited_user_cookies, on
):
    await client.put(
        settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
    )
    # a collaborator may share forms: they see the sites, not change them
    read = await client.get(settings_url(workspace), cookies=test_invited_user_cookies)
    assert read.status_code == 200
    assert read.json() == {"origins": [SITE], "canManage": False, "maxOrigins": 20}
    changed = await client.put(
        settings_url(workspace), json={"origins": []}, cookies=test_invited_user_cookies
    )
    assert changed.status_code == 403
    await add_viewer(workspace)
    for call in (
        client.get(settings_url(workspace), cookies=cookies_of(viewer)),
        client.put(
            settings_url(workspace), json={"origins": []}, cookies=cookies_of(viewer)
        ),
    ):
        assert (await call).status_code == 403
    still = await client.get(settings_url(workspace), cookies=test_user_cookies)
    assert still.json()["origins"] == [SITE]


async def test_signed_out_callers_are_refused(client, workspace, on):
    assert (await client.get(settings_url(workspace))).status_code == 401
    assert (
        await client.put(settings_url(workspace), json={"origins": []})
    ).status_code == 401


async def test_another_workspaces_admin_cannot_read_or_change_it(
    client, workspace, workspace_1, test_user_cookies_1, on
):
    assert (
        await client.get(settings_url(workspace), cookies=test_user_cookies_1)
    ).status_code == 403
    assert (
        await client.put(
            settings_url(workspace),
            json={"origins": [SITE]},
            cookies=test_user_cookies_1,
        )
    ).status_code == 403
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert not stored.embed_allowed_origins


POLICY = "/api/v1/workspaces/embed/policy"


async def test_the_policy_says_not_enabled_while_the_switch_is_off(
    client, workspace, off
):
    answer = await client.get(
        POLICY, params={"workspace_name": workspace.workspace_name}
    )
    assert answer.status_code == 200
    assert answer.json() == {"enabled": False, "origins": []}


async def test_the_policy_is_public_and_found_three_ways(
    client, workspace, test_user_cookies, on
):
    await client.put(
        settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
    )
    workspace = await container.workspace_repo().find_by_id(workspace.id)
    await container.workspace_repo().set_fields(
        workspace, {"custom_domain": "forms.acme.example"}
    )
    for query in (
        {"workspace_name": workspace.workspace_name},
        {"custom_domain": "forms.acme.example"},
        {"workspace_id": str(workspace.id)},
    ):
        answer = await client.get(POLICY, params=query)  # no cookies
        assert answer.status_code == 200, answer.text
        assert answer.json() == {"enabled": True, "origins": [SITE]}
        assert answer.headers["cache-control"] == "no-store"


async def test_the_policy_does_not_tell_unknown_from_empty(client, workspace, on):
    for query in (
        {"workspace_name": "no-such-workspace"},
        {"custom_domain": "nowhere.example"},
        {"workspace_id": str(RecordId())},
        {"workspace_id": "not-an-id"},
    ):
        answer = await client.get(POLICY, params=query)
        assert answer.status_code == 200, (query, answer.text)
        assert answer.json() == {"enabled": True, "origins": []}


async def test_the_policy_wants_exactly_one_query(client, workspace, on):
    assert (await client.get(POLICY)).status_code == 422
    both = await client.get(POLICY, params={"workspace_name": "a", "workspace_id": "b"})
    assert both.status_code == 422


async def test_a_disabled_workspace_allows_no_site(
    client, workspace, test_user_cookies, on
):
    await client.put(
        settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
    )
    stored = await container.workspace_repo().find_by_id(workspace.id)
    await container.workspace_repo().set_fields(stored, {"disabled": True})
    answer = await client.get(
        POLICY, params={"workspace_name": workspace.workspace_name}
    )
    assert answer.json() == {"enabled": True, "origins": []}


async def test_the_public_workspace_answer_leaves_the_list_out(
    client, workspace, test_user_cookies, on
):
    await client.put(
        settings_url(workspace), json={"origins": [SITE]}, cookies=test_user_cookies
    )
    for cookies in (None, test_user_cookies):
        answer = await client.get(
            "/api/v1/workspaces",
            params={"workspace_name": workspace.workspace_name},
            cookies=cookies,
        )
        assert answer.status_code == 200
        assert (
            "embedAllowedOrigins" not in answer.text
            and "embed_allowed_origins" not in answer.text
        )
        assert SITE not in answer.text
        by_id = await client.get(f"/api/v1/workspaces/{workspace.id}", cookies=cookies)
        assert SITE not in by_id.text


# ------------------------------------------------------------------ rate limit


async def test_the_policy_is_limited_per_client_address(
    client, workspace, on, monkeypatch
):
    from backend.app.services import form_embed

    monkeypatch.setattr(form_embed, "POLICY_PER_IP_PER_MINUTE", 3)
    for _ in range(3):
        assert (
            await client.get(
                POLICY, params={"workspace_name": workspace.workspace_name}
            )
        ).status_code == 200
    # a different workspace name does not help: it is the address that is counted
    refused = await client.get(POLICY, params={"workspace_name": "another-one"})
    assert refused.status_code == 429
    assert refused.json()["code"] == "rate_limited"
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    assert refused.headers["cache-control"] == "no-store"


async def test_the_policy_is_limited_per_workspace(client, workspace, on, monkeypatch):
    from backend.app.services import form_embed

    monkeypatch.setattr(form_embed, "POLICY_PER_WORKSPACE_PER_MINUTE", 2)
    name = workspace.workspace_name
    assert (
        await client.get(POLICY, params={"workspace_name": name})
    ).status_code == 200
    assert (
        await client.get(POLICY, params={"workspace_name": name.upper()})
    ).status_code == 200
    third = await client.get(POLICY, params={"workspace_name": name})
    assert third.status_code == 429 and "retry-after" in third.headers
    # another workspace is not affected, and the three ways of naming one are counted separately
    assert (
        await client.get(POLICY, params={"workspace_name": "someone-else"})
    ).status_code == 200
    assert (
        await client.get(POLICY, params={"workspace_id": str(workspace.id)})
    ).status_code == 200


async def test_ordinary_use_is_far_below_the_ceilings(client, workspace, on):
    for _ in range(40):
        assert (
            await client.get(
                POLICY, params={"workspace_name": workspace.workspace_name}
            )
        ).status_code == 200


async def test_nothing_is_counted_or_refused_while_the_switch_is_off(
    client, workspace, off, monkeypatch
):
    from backend.app.services import form_embed

    monkeypatch.setattr(form_embed, "POLICY_PER_IP_PER_MINUTE", 1)
    monkeypatch.setattr(form_embed, "POLICY_PER_WORKSPACE_PER_MINUTE", 1)
    for _ in range(5):
        answer = await client.get(
            POLICY, params={"workspace_name": workspace.workspace_name}
        )
        assert answer.status_code == 200 and answer.json() == {
            "enabled": False,
            "origins": [],
        }


async def test_a_malformed_query_is_refused_before_it_counts(
    client, workspace, on, monkeypatch
):
    from backend.app.services import form_embed

    monkeypatch.setattr(form_embed, "POLICY_PER_IP_PER_MINUTE", 1)
    assert (await client.get(POLICY)).status_code == 422
    assert (
        await client.get(POLICY, params={"workspace_name": workspace.workspace_name})
    ).status_code == 200
