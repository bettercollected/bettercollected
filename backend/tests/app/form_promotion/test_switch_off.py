"""``FORM_PROMOTION_ENABLED`` is off by default and environment-only. Off: the
promotion routes answer 422 ``form_promotion_disabled`` before anything is read,
no query is made for them, and nothing else changes."""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from backend.app.container import container
from backend.app.services.form_promotion.mode import (
    DISABLED_CODE,
    ensure_enabled,
    form_promotion_enabled,
)
from backend.config import settings
from backend.config.application import Application
from common.settings.inventory import ENV_ONLY_INVENTORY
from common.settings.registry import ENV_ONLY_KEYS
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import cookies
from tests.app.form_promotion.helpers import body, create_source, spec_document, url

pytestmark = pytest.mark.asyncio


@contextmanager
def statements():
    """Every SQL statement the database sees while the block runs."""
    seen = []
    engine = container.pg_engine().sync_engine

    def record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_the_switch_is_off_by_default_and_read_from_the_environment_only():
    assert Application.model_fields["form_promotion"].default.ENABLED is False
    assert settings.form_promotion.ENABLED is False
    assert form_promotion_enabled() is False
    spec = next(s for s in ENV_ONLY_INVENTORY if s.key == "FORM_PROMOTION_ENABLED")
    assert spec.default is False and spec.tier == "T5"
    assert "FORM_PROMOTION_ENABLED" in ENV_ONLY_KEYS


def test_turning_it_on_lets_the_check_pass(monkeypatch):
    monkeypatch.setattr(settings.form_promotion, "ENABLED", True)
    ensure_enabled()


async def _routes(workspace, form_id, target):
    base = url(workspace, form_id)
    return [
        ("GET", base + "/spec-file", {}),
        ("GET", base + "/promotion/targets", {"params": {"targetWorkspaceId": str(target.id)}}),
        ("POST", base + "/promotion/preview", {"json": body(target)}),
        ("POST", base + "/promotion/apply", {"json": body(target, sourceEtag='"x"')}),
    ]


async def test_every_route_answers_422_before_anything_is_read_or_queried(
    client, workspace, workspace_1
):
    form_id, _ = await create_source(workspace)
    for method, path, extra in await _routes(workspace, form_id, workspace_1):
        for signed_in in (True, False):
            with statements() as seen:
                response = await client.request(
                    method,
                    path,
                    cookies=cookies(testUser) if signed_in else None,
                    **extra,
                )
            assert response.status_code == 422, (method, path, response.text)
            assert response.json()["code"] == DISABLED_CODE
            # not even the session or the permissions were looked at (the CORS
            # middleware's own read of the allowed origins is not ours)
            ours = [s for s in seen if "allowed_origins" not in s]
            assert ours == [], (method, path, ours)


async def test_a_body_that_is_not_valid_does_not_hide_the_switch(
    client, workspace, workspace_1
):
    form_id, _ = await create_source(workspace)
    response = await client.post(
        url(workspace, form_id, "/promotion/preview"),
        json={"nonsense": True},
        cookies=cookies(testUser),
    )
    assert response.status_code == 422
    assert response.json()["code"] == DISABLED_CODE


async def test_nothing_else_changes_while_it_is_off(client, workspace, workspace_1):
    """The writer behind the public spec API and the permissions answer as ever;
    the new flag says off."""
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, spec_document(), testUser
    )
    spec, _ = await container.form_spec_writer().read(workspace.id, form_id)
    spec["title"] = "Gewijzigd"
    await container.form_spec_writer().replace(
        workspace.id, form_id, spec, [etag], testUser
    )
    assert (await container.form_spec_writer().read(workspace.id, form_id))[0][
        "title"
    ] == "Gewijzigd"
    permissions = await client.get(
        f"/api/v1/workspaces/{workspace.id}/permissions", cookies=cookies(testUser)
    )
    assert permissions.json()["formPromotionEnabled"] is False


async def test_the_permissions_tell_the_webapp_when_it_is_on(
    client, workspace, monkeypatch
):
    monkeypatch.setattr(settings.form_promotion, "ENABLED", True)
    permissions = await client.get(
        f"/api/v1/workspaces/{workspace.id}/permissions", cookies=cookies(testUser)
    )
    assert permissions.json()["formPromotionEnabled"] is True


async def test_a_mark_already_stored_is_kept_with_the_switch_off(
    client, workspace, workspace_1, monkeypatch
):
    """Stored ``promotedFrom`` stays (nothing reads it, nothing removes it)."""
    from backend.app.models.workspace import PromotedFrom
    import datetime as dt

    form_id, _ = await create_source(workspace)
    mark = PromotedFrom(
        workspace_id=str(workspace_1.id),
        form_id="f" * 24,
        at=dt.datetime.now(dt.timezone.utc),
        by="u",
        source_hash="h",
    )
    await container.workspace_form_repo().set_promoted_from(
        workspace.id, form_id, mark
    )
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert link.settings.promoted_from.form_id == "f" * 24
    # an ordinary settings save keeps it
    patched = await client.patch(
        url(workspace, form_id, "/settings"),
        json={"purpose": "Anders"},
        cookies=cookies(testUser),
    )
    assert patched.status_code == 200, patched.text
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert link.settings.promoted_from.form_id == "f" * 24
