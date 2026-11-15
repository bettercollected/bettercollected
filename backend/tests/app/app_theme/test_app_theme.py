"""The workspace's app theme (``app_theme``, ``APP_THEME_PIGMENT_ENABLED``):
``daybreak`` (the default) or ``pigment``, chosen by an owner or admin
(``workspace.manage``), recorded in the audit log (ids and the two theme names),
served to members in the workspace answer for the dashboard and to nobody else.
With the switch off a choice of pigment is refused (422) and every workspace is
served ``daybreak`` whatever it has stored."""

import pytest

from backend.app.container import container
from backend.config import settings
from tests.app.controllers.data import invited_user, testUser1
from tests.app.controllers.test_permission_matrix import _cookies

THEME_KEYS = ("appTheme", "app_theme")


def base(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


def theme_url(workspace) -> str:
    return f"{base(workspace)}/app-theme"


async def choose(client, workspace, cookies, value="pigment"):
    return await client.put(
        theme_url(workspace), json={"appTheme": value}, cookies=cookies
    )


async def lookup(client, workspace, cookies=None):
    return await client.get(
        "/api/v1/workspaces",
        params={"workspace_name": workspace.workspace_name},
        cookies=cookies,
    )


async def stored_theme(workspace):
    return (await container.workspace_repo().find_by_id(workspace.id)).app_theme


async def entries():
    return [
        e
        for e in await container.workspace_audit_repo().many()
        if e.event == "app_theme_changed"
    ]


def has_theme_key(payload) -> bool:
    """Any key of the answer, at any depth, that names the theme."""
    if isinstance(payload, dict):
        return any(k in THEME_KEYS or has_theme_key(v) for k, v in payload.items())
    if isinstance(payload, list):
        return any(has_theme_key(v) for v in payload)
    return False


@pytest.fixture()
def on(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)


@pytest.fixture()
def off(monkeypatch):
    monkeypatch.setattr(settings.app_theme, "ENABLED", False)


# ----------------------------------------------------------------- switch on


async def test_an_owner_chooses_a_theme_and_it_is_recorded(
    client, workspace, test_user_cookies, on
):
    assert await stored_theme(workspace) is None
    changed = await choose(client, workspace, test_user_cookies, "pigment")
    assert changed.status_code == 200, changed.text
    assert changed.json() == {"appTheme": "pigment"}
    assert await stored_theme(workspace) == "pigment"
    (event,) = await entries()
    assert event.app_theme == "pigment" and event.previous_app_theme == "daybreak"
    assert str(event.workspace_id) == str(workspace.id) and event.user_id
    # the entry holds ids and the two theme names, nothing else
    stored = {k: v for k, v in event.model_dump().items() if v is not None}
    assert set(stored) <= {
        "id",
        "created_at",
        "updated_at",
        "workspace_id",
        "user_id",
        "session_id",
        "event",
        "app_theme",
        "previous_app_theme",
    }, stored
    # and back
    back = await choose(client, workspace, test_user_cookies, "daybreak")
    assert back.status_code == 200 and back.json() == {"appTheme": "daybreak"}
    assert await stored_theme(workspace) == "daybreak"
    events = await entries()
    assert len(events) == 2
    assert {(e.previous_app_theme, e.app_theme) for e in events} == {
        ("daybreak", "pigment"),
        ("pigment", "daybreak"),
    }


async def test_the_same_theme_again_is_no_change_and_no_entry(
    client, workspace, test_user_cookies, on
):
    # not chosen counts as daybreak
    assert (await choose(client, workspace, test_user_cookies, "daybreak")).status_code == 200
    assert await stored_theme(workspace) is None
    assert await entries() == []
    assert (await choose(client, workspace, test_user_cookies, "pigment")).status_code == 200
    assert (await choose(client, workspace, test_user_cookies, "pigment")).status_code == 200
    assert len(await entries()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"appTheme": "blue"},
        {"appTheme": "Pigment"},
        {"appTheme": "PIGMENT"},
        {"appTheme": " pigment"},
        {"appTheme": ""},
        {"appTheme": None},
        {"appTheme": ["pigment"]},
        {"appTheme": {"name": "pigment"}},
        {"appTheme": 1},
        {},
        {"theme": "pigment"},
        {"appTheme": "pigment", "extra": True},
        {"appTheme": "pigment", "appThemeColor": "#ff0000"},
    ],
)
async def test_only_the_two_themes_are_accepted(
    client, workspace, test_user_cookies, on, body
):
    refused = await client.put(theme_url(workspace), json=body, cookies=test_user_cookies)
    assert refused.status_code == 422, refused.text
    assert await stored_theme(workspace) is None
    assert await entries() == []


async def test_a_body_that_is_not_an_object_is_refused(
    client, workspace, test_user_cookies, on
):
    for content in ('"pigment"', "[]", "null", "not json"):
        refused = await client.put(
            theme_url(workspace),
            content=content,
            headers={"Content-Type": "application/json"},
            cookies=test_user_cookies,
        )
        assert refused.status_code == 422, (content, refused.text)
    assert await stored_theme(workspace) is None


async def test_only_a_manager_of_the_workspace_may_choose(
    client, workspace, test_user_cookies, on
):
    for cookies in (None, _cookies(testUser1)):
        refused = await choose(client, workspace, cookies)
        assert refused.status_code in (401, 403), refused.text
    # a member without workspace.manage is refused too (the permission matrix
    # lists the route for every role)
    refused = await choose(client, workspace, _cookies(invited_user))
    assert refused.status_code == 403, refused.text
    assert await stored_theme(workspace) is None
    assert await entries() == []


async def test_a_change_is_refused_when_the_audit_entry_cannot_be_stored(
    client, workspace, test_user_cookies, on, monkeypatch
):
    async def broken(*args, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(container.workspace_audit_repo(), "record", broken)
    refused = await choose(client, workspace, test_user_cookies)
    assert refused.status_code == 503 and refused.json()["code"] == "audit_unavailable"
    assert await stored_theme(workspace) is None


async def test_another_workspace_is_not_touched(
    client, workspace, workspace_1, test_user_cookies, on
):
    assert (await choose(client, workspace, test_user_cookies)).status_code == 200
    assert await stored_theme(workspace_1) is None
    # a manager of one workspace cannot choose for another
    refused = await choose(client, workspace_1, test_user_cookies)
    assert refused.status_code in (403, 404), refused.text
    assert await stored_theme(workspace_1) is None


# ------------------------------------------------------ what is served, to whom


async def test_a_member_is_served_the_theme_and_nobody_else(
    client, workspace, test_user_cookies, on
):
    for cookies in (test_user_cookies, _cookies(invited_user)):
        member = await lookup(client, workspace, cookies)
        assert member.status_code == 200, member.text
        assert member.json()["dashboardAccess"] is True
        assert member.json()["appTheme"] == "daybreak"
    assert (await choose(client, workspace, test_user_cookies)).status_code == 200
    for cookies in (test_user_cookies, _cookies(invited_user)):
        member = await lookup(client, workspace, cookies)
        assert member.json()["appTheme"] == "pigment"
    # a visitor, a respondent session and a signed-in stranger learn nothing
    for cookies in (None, _cookies(testUser1)):
        public = await lookup(client, workspace, cookies)
        assert public.status_code == 200, public.text
        assert not has_theme_key(public.json()), public.json()


async def test_no_other_workspace_answer_carries_the_theme(
    client, workspace, test_user_cookies, on
):
    assert (await choose(client, workspace, test_user_cookies)).status_code == 200
    mine = await client.get("/api/v1/workspaces/mine", cookies=test_user_cookies)
    assert mine.status_code == 200, mine.text
    assert mine.json() and not has_theme_key(mine.json())
    patched = await client.patch(
        base(workspace), data={"title": "Renamed"}, cookies=test_user_cookies
    )
    assert patched.status_code == 200, patched.text
    assert not has_theme_key(patched.json())
    permissions = await client.get(f"{base(workspace)}/permissions", cookies=test_user_cookies)
    assert permissions.status_code == 200
    assert not has_theme_key(permissions.json())


def test_the_theme_is_only_taken_with_dashboard_access():
    from backend.app.models.workspace import Workspace, WorkspaceResponseDto

    document = Workspace(title="Acme", app_theme="pigment").model_dump(mode="json")
    public = WorkspaceResponseDto(**document)
    assert public.app_theme is None
    assert not has_theme_key(public.model_dump(mode="json", by_alias=True))
    assert not has_theme_key(public.model_dump(mode="json"))
    member = WorkspaceResponseDto(**document, dashboard_access=True)
    assert member.app_theme == "pigment"
    assert member.model_dump(mode="json", by_alias=True)["appTheme"] == "pigment"
    # a camelCase input is held to the same rule
    assert WorkspaceResponseDto(**{"appTheme": "pigment"}).app_theme is None


def test_a_stored_value_that_is_not_a_theme_is_not_a_workspace():
    from pydantic import ValidationError

    from backend.app.models.workspace import Workspace

    with pytest.raises(ValidationError):
        Workspace(title="Acme", app_theme="blue")


async def test_the_audit_log_lists_the_change_without_anything_else(
    client, workspace, test_user_cookies, on
):
    from backend.app.services.audit_log import catalog

    assert (await choose(client, workspace, test_user_cookies)).status_code == 200
    assert "app_theme_changed" in catalog.LISTED
    assert catalog.area_of("app_theme_changed") == catalog.AREA_SECURITY


# ---------------------------------------------------------------- switch off


async def test_off_a_choice_of_pigment_is_refused_and_nothing_is_stored(
    client, workspace, test_user_cookies, off
):
    refused = await choose(client, workspace, test_user_cookies, "pigment")
    assert refused.status_code == 422
    assert refused.json()["code"] == "app_theme_disabled"
    assert await stored_theme(workspace) is None
    assert await entries() == []


async def test_off_the_refusal_comes_after_the_permission(
    client, workspace, off
):
    # a person who may not choose is told so, not that the switch is off
    for cookies in (None, _cookies(testUser1), _cookies(invited_user)):
        refused = await choose(client, workspace, cookies)
        assert refused.status_code in (401, 403), refused.text


async def test_off_the_theme_it_already_has_passes(
    client, workspace, test_user_cookies, off
):
    same = await choose(client, workspace, test_user_cookies, "daybreak")
    assert same.status_code == 200 and same.json() == {"appTheme": "daybreak"}
    assert await stored_theme(workspace) is None
    assert await entries() == []


async def test_off_a_stored_pigment_is_kept_but_served_as_daybreak(
    client, workspace, test_user_cookies, monkeypatch
):
    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    assert (await choose(client, workspace, test_user_cookies)).status_code == 200
    assert (await lookup(client, workspace, test_user_cookies)).json()["appTheme"] == "pigment"

    monkeypatch.setattr(settings.app_theme, "ENABLED", False)
    member = await lookup(client, workspace, test_user_cookies)
    assert member.status_code == 200 and member.json()["appTheme"] == "daybreak"
    # kept, neither enforced nor shown
    assert await stored_theme(workspace) == "pigment"
    # asking for what it is served is no change, so the stored value stays too
    same = await choose(client, workspace, test_user_cookies, "daybreak")
    assert same.status_code == 200
    assert await stored_theme(workspace) == "pigment"
    assert len(await entries()) == 1
    # asking for pigment again is a change the switch refuses
    refused = await choose(client, workspace, test_user_cookies, "pigment")
    assert refused.status_code == 422 and refused.json()["code"] == "app_theme_disabled"
    # the public answer has no theme either way
    assert not has_theme_key((await lookup(client, workspace)).json())
    assert not has_theme_key((await lookup(client, workspace, _cookies(testUser1))).json())

    monkeypatch.setattr(settings.app_theme, "ENABLED", True)
    assert (await lookup(client, workspace, test_user_cookies)).json()["appTheme"] == "pigment"


async def test_off_the_member_answer_says_daybreak_for_every_workspace(
    client, workspace, test_user_cookies, off
):
    # nothing chosen
    member = await lookup(client, workspace, test_user_cookies)
    assert member.json()["appTheme"] == "daybreak"
    # a value stored behind the setter's back (an import, a restore)
    stored = await container.workspace_repo().find_by_id(workspace.id)
    await container.workspace_repo().set_fields(stored, {"app_theme": "pigment"})
    member = await lookup(client, workspace, test_user_cookies)
    assert member.json()["appTheme"] == "daybreak"


async def test_the_permissions_answer_says_whether_the_switch_is_on(
    client, workspace, test_user_cookies, monkeypatch
):
    for enabled in (True, False):
        monkeypatch.setattr(settings.app_theme, "ENABLED", enabled)
        permissions = await client.get(
            f"{base(workspace)}/permissions", cookies=test_user_cookies
        )
        assert permissions.status_code == 200, permissions.text
        assert permissions.json()["appThemeEnabled"] is enabled


def test_the_switch_is_off_by_default_and_read_from_the_environment_only(monkeypatch):
    from backend.config.app_theme_settings import AppThemeSettings

    monkeypatch.delenv("APP_THEME_PIGMENT_ENABLED", raising=False)
    assert AppThemeSettings().ENABLED is False
    monkeypatch.setenv("APP_THEME_PIGMENT_ENABLED", "true")
    assert AppThemeSettings().ENABLED is True

    from common.settings.inventory import T5, all_specs

    (spec,) = [s for s in all_specs() if s.key == "APP_THEME_PIGMENT_ENABLED"]
    assert spec.tier == T5 and spec.default is False
