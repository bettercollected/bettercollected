"""The access mode of a form (``settings.access_mode``) can be written by its
own endpoint only. A create, an import, a replace, a settings patch or an AI
settings op cannot set it, clear it or smuggle it in, whatever the body says.
Those paths are whitelisted writers; the workspace-form repository is the
backstop for every write of the settings."""

import copy

from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.ai.ops import FormSettingsPatch, apply_settings_ops
from backend.app.services.form_access.model import MODE_RESTRICTED, MODE_WORKSPACE
from tests.app.controllers.test_public_api import BASE, SPEC, _auth, _token
from tests.app.form_access.helpers import restrict

SMUGGLED = {"accessMode": "restricted", "access_mode": "restricted", "hidden": True}


async def link_of(workspace, form_id):
    return await container.workspace_form_repo().find_workspace_form(
        workspace.id, str(form_id)
    )


# -- the repository backstop -----------------------------------------------------------
async def test_a_new_link_starts_without_a_mode_whatever_it_was_built_from(workspace):
    repo = container.workspace_form_repo()
    form_id = "f" * 24
    created = await repo.save_workspace_form(
        workspace.id,
        form_id,
        "u1",
        WorkspaceFormSettings(access_mode=MODE_RESTRICTED, custom_url="x"),
    )
    assert created.settings.access_mode is None
    assert created.settings.custom_url == "x"
    assert (await link_of(workspace, form_id)).settings.access_mode is None


async def test_a_new_link_saved_as_a_document_starts_without_a_mode(workspace):
    repo = container.workspace_form_repo()
    saved = await repo.save(
        WorkspaceFormDocument(
            workspace_id=workspace.id,
            form_id="e" * 24,
            user_id="u1",
            settings=WorkspaceFormSettings(access_mode=MODE_RESTRICTED),
        )
    )
    assert saved.settings.access_mode is None
    assert (await link_of(workspace, "e" * 24)).settings.access_mode is None


async def test_writing_the_settings_back_keeps_the_stored_mode(workspace, workspace_form):
    """An import or create for a form the user already has, and every
    read-modify-write through ``update``: the mode is the stored one."""
    repo = container.workspace_form_repo()
    await restrict(workspace, workspace_form.form_id)
    stored = await link_of(workspace, workspace_form.form_id)

    rewritten = await repo.save_workspace_form(
        workspace.id,
        workspace_form.form_id,
        stored.user_id,
        WorkspaceFormSettings(custom_url="other", access_mode=MODE_WORKSPACE),
    )
    assert rewritten.settings.access_mode == MODE_RESTRICTED
    assert rewritten.settings.custom_url == "other"

    stored = await link_of(workspace, workspace_form.form_id)
    stored.settings = WorkspaceFormSettings(access_mode=MODE_WORKSPACE, pinned=True)
    await repo.update(str(stored.id), stored)
    after = await link_of(workspace, workspace_form.form_id)
    assert after.settings.access_mode == MODE_RESTRICTED
    assert after.settings.pinned is True


async def test_settings_written_back_cannot_clear_the_mode_either(workspace, workspace_form):
    repo = container.workspace_form_repo()
    await restrict(workspace, workspace_form.form_id)
    stored = await link_of(workspace, workspace_form.form_id)
    stored.settings = None
    await repo.update(str(stored.id), stored)
    assert (await link_of(workspace, workspace_form.form_id)).settings.access_mode == MODE_RESTRICTED


async def test_a_link_without_a_mode_stays_without_one(workspace, workspace_form):
    repo = container.workspace_form_repo()
    stored = await link_of(workspace, workspace_form.form_id)
    stored.settings.access_mode = MODE_RESTRICTED
    await repo.update(str(stored.id), stored)
    assert (await link_of(workspace, workspace_form.form_id)).settings.access_mode is None


# -- the whitelisted writers --------------------------------------------------------------
async def test_the_settings_patch_ignores_the_mode(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings",
        cookies=test_user_cookies,
        json={"pinned": True, "accessMode": "restricted", "access_mode": "restricted"},
    )
    assert response.status_code == 200, response.text
    assert "accessMode" not in response.json()["settings"]
    link = await link_of(workspace, workspace_form.form_id)
    assert link.settings.pinned is True
    assert link.settings.access_mode is None

    # nor can it be taken back through the same patch
    await restrict(workspace, workspace_form.form_id)
    await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings",
        cookies=test_user_cookies,
        json={"accessMode": "workspace", "private": False},
    )
    assert (await link_of(workspace, workspace_form.form_id)).settings.access_mode == (
        MODE_RESTRICTED
    )


async def test_the_form_responses_do_not_carry_the_mode(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    await restrict(workspace, workspace_form.form_id)
    response = await client.patch(
        f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/settings",
        cookies=test_user_cookies,
        json={"pinned": False},
    )
    assert response.status_code == 200
    assert "accessMode" not in response.json()["settings"]
    assert "access_mode" not in response.json()["settings"]


async def test_the_public_api_create_cannot_set_the_mode(client: AsyncClient, workspace):
    token = await _token(workspace.id)
    for extra in (SMUGGLED, {"settings": SMUGGLED}, {"trust": {**SPEC["trust"], **SMUGGLED}}):
        response = await client.post(
            f"{BASE}/forms", json={**SPEC, **extra}, headers=_auth(token)
        )
        # created without it, or refused: never created restricted
        assert response.status_code in (201, 400, 422), response.text
    links = await container.workspace_form_repo().list_in_workspace(workspace.id)
    assert all(link.settings.access_mode is None for link in links)
    # the hidden flag is no more settable here than before
    assert not any(link.settings.hidden for link in links)


async def test_the_public_api_replace_cannot_set_or_clear_the_mode(
    client: AsyncClient, workspace
):
    token = await _token(workspace.id)
    created = await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(token))
    assert created.status_code == 201
    form_id, etag = created.json()["formId"], created.headers["ETag"]

    spec = copy.deepcopy(SPEC)
    spec.update(SMUGGLED)
    spec["settings"] = dict(SMUGGLED)
    await client.put(
        f"{BASE}/forms/{form_id}", json=spec, headers=_auth(token, **{"If-Match": etag})
    )
    assert (await link_of(workspace, form_id)).settings.access_mode is None

    await restrict(workspace, form_id)
    current = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
    spec = copy.deepcopy(SPEC)
    spec.update({"accessMode": "workspace", "access_mode": "workspace"})
    spec["settings"] = {"accessMode": "workspace"}
    await client.put(
        f"{BASE}/forms/{form_id}",
        json=spec,
        headers=_auth(token, **{"If-Match": current.headers["ETag"]}),
    )
    assert (await link_of(workspace, form_id)).settings.access_mode == MODE_RESTRICTED


def test_an_ai_settings_op_cannot_carry_it():
    patch = FormSettingsPatch.model_validate(
        {"purpose": "To plan seats.", "accessMode": "restricted", "access_mode": "restricted"}
    )
    assert not hasattr(patch, "access_mode") and not hasattr(patch, "accessMode")

    settings = WorkspaceFormSettings()

    class Op:
        pass

    from backend.app.services.ai.ops import UpdateFormSettingsOp

    op, result = UpdateFormSettingsOp(patch=patch), Op()
    result.ok = True
    assert apply_settings_ops(settings, [op], [result])
    assert settings.purpose == "To plan seats."
    assert settings.access_mode is None


# -- the copied-from mark is written by the promotion only ------------------------------
def _forged_mark():
    import datetime as dt

    from backend.app.models.workspace import PromotedFrom

    return PromotedFrom(
        workspace_id="a1" * 12,
        form_id="b2" * 12,
        at=dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc),
        by="c3" * 12,
        source_hash="d4" * 8,
    )


async def test_a_new_link_never_starts_with_a_copied_from_mark(workspace):
    """Settings that arrive from an import (a file, another instance) cannot
    forge where a form was copied from: that decides the picker's order and the
    "changed since the last copy" prompt."""
    repo = container.workspace_form_repo()
    created = await repo.save_workspace_form(
        workspace.id,
        "d" * 24,
        "u1",
        WorkspaceFormSettings(promoted_from=_forged_mark()),
    )
    assert created.settings.promoted_from is None
    assert (await link_of(workspace, "d" * 24)).settings.promoted_from is None
    saved = await repo.save(
        WorkspaceFormDocument(
            workspace_id=workspace.id,
            form_id="c" * 24,
            user_id="u1",
            settings=WorkspaceFormSettings(promoted_from=_forged_mark()),
        )
    )
    assert saved.settings.promoted_from is None
    assert (await link_of(workspace, "c" * 24)).settings.promoted_from is None


async def test_writing_settings_back_keeps_the_stored_mark_and_forges_none(
    workspace, workspace_form
):
    repo = container.workspace_form_repo()
    stored = await link_of(workspace, workspace_form.form_id)
    # nothing stored: a forged one is not taken
    await repo.save_workspace_form(
        workspace.id,
        workspace_form.form_id,
        stored.user_id,
        WorkspaceFormSettings(promoted_from=_forged_mark()),
    )
    assert (await link_of(workspace, workspace_form.form_id)).settings.promoted_from is None
    # the promotion's own writer sets it; a read-modify-write neither clears nor changes it
    await repo.set_promoted_from(workspace.id, workspace_form.form_id, _forged_mark())
    stored = await link_of(workspace, workspace_form.form_id)
    stored.settings = WorkspaceFormSettings(pinned=True)
    await repo.update(str(stored.id), stored)
    after = (await link_of(workspace, workspace_form.form_id)).settings
    assert after.pinned is True
    assert after.promoted_from is not None
    assert after.promoted_from.source_hash == "d4" * 8

