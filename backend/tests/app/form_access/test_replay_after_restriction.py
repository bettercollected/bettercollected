"""What was begun before a form was restricted must not finish after.

Two things outlive a decision: an Idempotency-Key replay on the public API (the
stored answer of an earlier write) and an export built earlier (a file with a
signed link). Each is decided again on the form when it is asked for again: a
member the form has since been closed to (or whose grant was removed) gets the
404 of an unknown form, not the stored answer or the file; a member who may still
open the form gets the replay or the file.
"""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_EDITOR
from backend.app.services.response_export import limits, links
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import SPEC
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.form_access.helpers import add_member, grant, restrict
from tests.app.form_access.test_key_enforcement import ANSWERS, _auth, _call
from tests.app.form_access.test_key_route_matrix import kworld  # noqa: F401
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.response_export.helpers import publish, start, submit_many, url


# -- an Idempotency-Key replay on the public API ---------------------------------------


def _key(label: str) -> dict:
    return {"Idempotency-Key": f"replay-{label}-0001"}


async def test_a_replayed_create_is_decided_on_the_form_it_made(
    client: AsyncClient, kworld, monkeypatch  # noqa: F811
):
    """``POST /forms`` made a form (201); the form is then restricted and its
    creator changed. The Editor's key replays the create: a 404 as for an unknown
    form, never the stored 201 with the form's text. The Admin's key replays it:
    the stored answer, marked as a replay."""
    spec = {**SPEC, "title": "Replayed create"}
    made = {}
    for who in ("editor", "admin"):
        headers = _key(who)
        first = await client.post(
            "/api/v1/public/v1/forms", json=spec, headers=_auth(kworld.tokens[who], **headers)
        )
        assert first.status_code == 201, (who, first.text[:150])
        made[who] = first.json()["formId"]
        # the form is the owner's from now on, and restricted
        repo = container.workspace_form_repo()
        link = await repo.find_workspace_form(kworld.workspace.id, made[who])
        link.user_id = str(testUser.id)
        await repo.save(link)
        await restrict(kworld.workspace, made[who])
    monkeypatch.setattr(settings.form_access, "ENABLED", True)

    replay = await client.post(
        "/api/v1/public/v1/forms", json=spec, headers=_auth(kworld.tokens["editor"], **_key("editor"))
    )
    unknown = await _call(client, kworld.tokens["editor"], "GET", f"/forms/{RecordId()}")
    assert replay.status_code == 404, (replay.status_code, replay.text[:150])
    assert (replay.status_code, replay.json()) == (unknown.status_code, unknown.json())
    assert made["editor"] not in replay.text

    again = await client.post(
        "/api/v1/public/v1/forms", json=spec, headers=_auth(kworld.tokens["admin"], **_key("admin"))
    )
    assert again.status_code == 201, again.text[:150]
    assert again.headers.get("Idempotent-Replayed") == "true"
    assert again.json()["formId"] == made["admin"]


async def test_a_replayed_submission_is_decided_on_the_form_it_was_made_to(
    client: AsyncClient, kworld, monkeypatch  # noqa: F811
):
    path = f"/api/v1/public/v1/forms/{kworld.form_id}/submissions"
    firsts = {}
    for who in ("editor", "admin"):
        got = await client.post(
            path, json=ANSWERS, headers=_auth(kworld.tokens[who], **_key("sub-" + who))
        )
        assert got.status_code == 201, (who, got.text[:150])
        firsts[who] = got.json()["responseId"]
    await restrict(kworld.workspace, kworld.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)

    closed = await client.post(
        path, json=ANSWERS, headers=_auth(kworld.tokens["editor"], **_key("sub-editor"))
    )
    gone = await client.post(
        f"/api/v1/public/v1/forms/{RecordId()}/submissions",
        json=ANSWERS,
        headers=_auth(kworld.tokens["editor"], **_key("sub-editor-other")),
    )
    assert closed.status_code == 404, (closed.status_code, closed.text[:150])
    assert (closed.status_code, closed.json()) == (gone.status_code, gone.json())
    assert firsts["editor"] not in closed.text

    kept = await client.post(
        path, json=ANSWERS, headers=_auth(kworld.tokens["admin"], **_key("sub-admin"))
    )
    assert kept.status_code in (200, 201), kept.text[:150]
    assert kept.headers.get("Idempotent-Replayed") == "true"
    assert kept.json()["responseId"] == firsts["admin"]


async def test_a_replayed_operation_batch_is_decided_on_the_form(
    client: AsyncClient, kworld, monkeypatch  # noqa: F811
):
    path = f"/api/v1/public/v1/forms/{kworld.form_id}/ops"
    ops = {"ops": [{"op": "update_form_info", "title": "Retitled"}], "atomic": True}
    first = await client.post(
        path, json=ops, headers=_auth(kworld.tokens["editor"], **_key("ops-editor"))
    )
    assert first.status_code == 200, first.text[:150]
    await restrict(kworld.workspace, kworld.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    closed = await client.post(
        path, json=ops, headers=_auth(kworld.tokens["editor"], **_key("ops-editor"))
    )
    gone = await client.post(
        f"/api/v1/public/v1/forms/{RecordId()}/ops",
        json=ops,
        headers=_auth(kworld.tokens["editor"], **_key("ops-other")),
    )
    assert closed.status_code == 404
    assert (closed.status_code, closed.json()) == (gone.status_code, gone.json())


# -- an export built before the restriction ---------------------------------------------


@pytest.fixture()
def small_exports(monkeypatch, memory_jobs):  # noqa: F811
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 2)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 120)
    return memory_jobs


async def _ready_export(client, workspace, form, user):
    queued = await start(client, workspace, form, user=user)
    assert queued.status_code == 202, queued.text[:150]
    export_id = queued.json()["id"]
    assert await container.response_export_service().run_job(export_id) == "ready"
    ready = await client.get(url(workspace, form, f"/{export_id}"), cookies=_cookies(user))
    assert ready.status_code == 200 and "downloadUrl" in ready.json(), ready.text[:150]
    return export_id, "/api/v1" + ready.json()["downloadUrl"]


async def test_an_export_built_before_the_restriction_is_not_served_after(
    client: AsyncClient, workspace, small_exports, monkeypatch
):
    """The editor built a large export while the form was open; the form is then
    restricted and the editor has no grant: the status and the file (through the
    link handed out earlier, and through a freshly signed one) are the 404 of an
    unknown form. With an Editor grant the editor keeps the file."""
    form = await publish(workspace)
    await submit_many(workspace, form, 5)
    closed = await add_member(workspace, "COLLABORATOR")
    kept = await add_member(workspace, "COLLABORATOR")
    closed_export, closed_link = await _ready_export(client, workspace, form, closed)
    kept_export, kept_link = await _ready_export(client, workspace, form, kept)
    await grant(workspace, form.form_id, kept.id, ROLE_EDITOR)
    await restrict(workspace, form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)

    unknown_form = type("F", (), {"form_id": str(RecordId())})
    ghost_status = await client.get(
        url(workspace, unknown_form, f"/{closed_export}"), cookies=_cookies(closed)
    )
    status = await client.get(
        url(workspace, form, f"/{closed_export}"), cookies=_cookies(closed)
    )
    assert status.status_code == 404
    assert (status.status_code, status.text) == (ghost_status.status_code, ghost_status.text)
    served = await client.get(closed_link, cookies=_cookies(closed))
    assert served.status_code == 404 and not served.content.startswith(b"PK"), served.status_code
    fresh = links.issue(closed_export, workspace.id, form.form_id, closed.id)
    again = await client.get(
        url(workspace, form, f"/{closed_export}/download") + f"?token={fresh}",
        cookies=_cookies(closed),
    )
    assert again.status_code == 404
    # a member who may still export it keeps the file
    still = await client.get(kept_link, cookies=_cookies(kept))
    assert still.status_code == 200 and len(still.content) > 0, still.status_code
    assert (
        await client.get(url(workspace, form, f"/{kept_export}"), cookies=_cookies(kept))
    ).status_code == 200


async def test_an_export_is_not_served_after_the_grant_that_allowed_it_is_removed(
    client: AsyncClient, workspace, small_exports, monkeypatch
):
    form = await publish(workspace)
    await submit_many(workspace, form, 5)
    await restrict(workspace, form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")
    row = await grant(workspace, form.form_id, editor.id, ROLE_EDITOR)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    export_id, link = await _ready_export(client, workspace, form, editor)
    assert (await client.get(link, cookies=_cookies(editor))).status_code == 200
    await container.form_access_grant_repo().delete(
        workspace.id, str(form.form_id), str(row.id)
    )
    container.form_access_service().invalidate()
    after = await client.get(link, cookies=_cookies(editor))
    assert after.status_code == 404, after.status_code
