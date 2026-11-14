"""The workspace default of the automatic spam check (``captcha_default``): the
form's own value wins, else the workspace's, else on; changing it needs
``workspace.manage`` and is recorded in the audit log (the new value and who,
never a person's data)."""

import pytest

from backend.app.container import container
from backend.app.services.captcha import challenge as ch
from backend.app.services.captcha.mode import required_by
from tests.app.captcha.conftest import ALICE, a_form, solved, submit
from tests.app.controllers.data import testUser1
from tests.app.controllers.test_permission_matrix import _cookies

pytestmark = pytest.mark.usefixtures("on")


def base(workspace) -> str:
    return f"/api/v1/workspaces/{workspace.id}"


async def set_default(client, workspace, cookies, value=False):
    return await client.put(
        f"{base(workspace)}/captcha/settings",
        json={"captchaDefault": value},
        cookies=cookies,
    )


async def form_with(workspace, own):
    form = await a_form(workspace)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    link.settings.captcha_enabled = own
    await container.workspace_form_repo().update(link.id, link)
    return form


def served_required(client, workspace, form, cookies=None):
    return client.get(
        f"{base(workspace)}/forms/{form.form_id}?published=true", cookies=cookies
    )


def test_the_rule_is_the_forms_own_then_the_workspaces_then_on():
    class S:
        def __init__(self, own):
            self.captcha_enabled = own

    assert required_by(S(None)) is True
    assert required_by(S(None), None) is True
    assert required_by(S(None), False) is False
    assert required_by(S(None), True) is True
    assert required_by(S(True), False) is True
    assert required_by(S(False), True) is False
    assert required_by({"captchaEnabled": False}, True) is False
    assert required_by({"captcha_enabled": None}, False) is False


async def test_the_default_is_read_and_set_by_a_manager_and_recorded(
    client, workspace, test_user_cookies
):
    read = await client.get(f"{base(workspace)}/captcha/settings", cookies=test_user_cookies)
    assert read.status_code == 200 and read.json()["captchaDefault"] is True
    changed = await set_default(client, workspace, test_user_cookies, False)
    assert changed.status_code == 200, changed.text
    assert changed.json()["captchaDefault"] is False
    stored = await container.workspace_repo().find_by_id(workspace.id)
    assert stored.captcha_default is False
    events = [
        e
        for e in await container.workspace_audit_repo().many()
        if e.event == "captcha_setting_changed"
    ]
    assert len(events) == 1
    assert events[0].enabled is False and events[0].form_id is None
    assert str(events[0].workspace_id) == str(workspace.id) and events[0].user_id
    # the same value again is no change and no entry
    assert (await set_default(client, workspace, test_user_cookies, False)).status_code == 200
    assert len(
        [e for e in await container.workspace_audit_repo().many() if e.event == "captcha_setting_changed"]
    ) == 1
    back = await set_default(client, workspace, test_user_cookies, True)
    assert back.json()["captchaDefault"] is True


async def test_only_a_manager_of_the_workspace_may_change_or_read_it(client, workspace):
    stranger = _cookies(testUser1)
    for cookies in (None, stranger):
        assert (
            await client.get(f"{base(workspace)}/captcha/settings", cookies=cookies)
        ).status_code in (401, 403)
        assert (await set_default(client, workspace, cookies)).status_code in (401, 403)
        assert (
            await client.get(f"{base(workspace)}/captcha/stats", cookies=cookies)
        ).status_code in (401, 403)
    assert (await container.workspace_repo().find_by_id(workspace.id)).captcha_default is None


async def test_a_change_is_refused_when_the_audit_entry_cannot_be_stored(
    client, workspace, test_user_cookies, monkeypatch
):
    async def broken(*args, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(container.workspace_audit_repo(), "record", broken)
    refused = await set_default(client, workspace, test_user_cookies, False)
    assert refused.status_code == 503 and refused.json()["code"] == "audit_unavailable"
    assert (await container.workspace_repo().find_by_id(workspace.id)).captcha_default is None


async def test_a_form_without_a_value_follows_the_workspace(
    client, workspace, test_user_cookies
):
    inherit = await form_with(workspace, None)
    off = await form_with(workspace, False)
    on = await form_with(workspace, True)
    # no choice yet: on for everyone
    for form, expected in ((inherit, True), (off, False), (on, True)):
        got = (await served_required(client, workspace, form)).json()["settings"]
        assert got["captchaRequired"] is expected
    await set_default(client, workspace, test_user_cookies, False)
    for form, expected in ((inherit, False), (off, False), (on, True)):
        got = (await served_required(client, workspace, form)).json()["settings"]
        assert got["captchaRequired"] is expected, form.form_id
    # a member answering their own form is told the same
    staff = (
        await served_required(client, workspace, inherit, test_user_cookies)
    ).json()["settings"]
    assert staff["captchaRequired"] is False
    # the creator's own setting is not changed by the default
    assert staff.get("captchaEnabled") is None


async def test_the_submit_follows_the_same_rule(
    client, workspace, test_user_cookies, claims
):
    inherit = await form_with(workspace, None)
    on = await form_with(workspace, True)
    await set_default(client, workspace, test_user_cookies, False)
    # the workspace asks for none: the form without a value takes none ...
    sent = await submit(client, workspace, inherit)
    assert sent.status_code == 200, sent.text
    assert claims == []
    # ... a form that asks for it does
    refused = await submit(client, workspace, on)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_missing"
    proof = await solved(client, workspace, on)
    assert (await submit(client, workspace, on, proof)).status_code == 200
    # and back to on for everyone
    await set_default(client, workspace, test_user_cookies, True)
    refused = await submit(client, workspace, inherit)
    assert refused.status_code == 422 and refused.json()["code"] == "captcha_missing"


async def test_a_forms_own_change_is_recorded_with_the_form(
    client, workspace, test_user_cookies
):
    form = await a_form(workspace)
    answer = await client.patch(
        f"{base(workspace)}/forms/{form.form_id}/settings",
        json={"captchaEnabled": False},
        cookies=test_user_cookies,
    )
    assert answer.status_code == 200, answer.text
    events = [
        e
        for e in await container.workspace_audit_repo().many()
        if e.event == "captcha_setting_changed"
    ]
    assert len(events) == 1
    assert events[0].form_id == str(form.form_id) and events[0].enabled is False
    # a save that leaves it as it is records nothing more
    await client.patch(
        f"{base(workspace)}/forms/{form.form_id}/settings",
        json={"captchaEnabled": False},
        cookies=test_user_cookies,
    )
    assert len(
        [e for e in await container.workspace_audit_repo().many() if e.event == "captcha_setting_changed"]
    ) == 1


def test_challenge_module_still_exports_both_purposes():
    assert set(ch.PURPOSES) == {"submit", "mail"}
    assert ALICE
