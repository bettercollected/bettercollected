"""With ``CAPTCHA_ENABLED`` off, existing features behave as before: a form
whose stored settings carry the spam check value (set while the switch was on)
is copied to another workspace, and promoted into an existing form there,
unchanged. The public spec API still refuses a document that sets it
(test_switch.py)."""

import pytest

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies
from tests.app.form_promotion.helpers import (
    body,
    headers,
    make_member,
    on,
    spec_document,
    stored_spec,
    url,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def world(workspace, workspace_1, monkeypatch):
    """A source form in A whose spam check setting was stored as False while the
    switch was on; then the switch is off. The caller is an Admin of B."""
    on(monkeypatch)
    await make_member(workspace_1, testUser, WorkspaceRoles.ADMIN.value)
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", True)
    document = spec_document()
    document["trust"]["captchaEnabled"] = False
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, document, testUser
    )
    monkeypatch.setattr(settings, "CAPTCHA_ENABLED", False)
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert link.settings.captcha_enabled is False
    return type(
        "World",
        (),
        {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag},
    )


async def _stored_value(workspace, form_id):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    return link.settings.captcha_enabled


async def test_copying_to_another_workspace_keeps_the_value(client, world):
    response = await client.post(
        url(world.a, world.form_id, "/promotion/apply"),
        json=body(world.b, sourceEtag=world.etag),
        cookies=cookies(testUser),
        headers=headers(),
    )
    assert response.status_code == 201, response.text
    new_id = response.json()["formId"]
    assert await _stored_value(world.b, new_id) is False
    spec_a, _ = await stored_spec(world.a, world.form_id)
    spec_b, _ = await stored_spec(world.b, new_id)
    assert spec_b == spec_a


async def test_promoting_into_an_existing_form_previews_and_applies(client, world):
    target, _, target_etag = await container.form_spec_writer().create(
        world.b.id, spec_document(title="Bestaand"), testUser
    )
    assert await _stored_value(world.b, target) is None
    more = dict(targetFormId=target, targetEtag=target_etag)
    preview = await client.post(
        url(world.a, world.form_id, "/promotion/preview"),
        json=body(world.b, **more),
        cookies=cookies(testUser),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid"] is True and preview.json()["errors"] == []
    applied = await client.post(
        url(world.a, world.form_id, "/promotion/apply"),
        json=body(world.b, sourceEtag=world.etag, **more),
        cookies=cookies(testUser),
        headers=headers(),
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["formId"] == target
    assert await _stored_value(world.b, target) is False
