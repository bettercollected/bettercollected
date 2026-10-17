"""The builder's op-batch save: POST /workspaces/{ws}/forms/{form_id}/ops
(session auth, form.edit, If-Match, Idempotency-Key, atomic, behind
API_EDITOR_OPS_SAVE_ENABLED), and the ETag on the editor's form GET."""

import json

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import idempotency
from backend.app.services.ai import chat as chat_module
from backend.app.services.form_spec import editor_ops
from backend.app.services.ai.ops import parse_ops
from backend.app.services.form_spec.editor_ops import (
    EDITOR_OP_NAMES,
    idempotency_scope,
)
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.controllers.test_form_spec_api import _make_v2


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def _ops_url(workspace, form_id) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/ops"


def _form_url(workspace, form_id) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"


def _headers(etag=None, key=None) -> dict:
    headers = {}
    if etag is not None:
        headers["If-Match"] = etag
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


RENAME = {"ops": [{"op": "update_form_info", "title": "Renamed"}]}


@pytest.fixture(autouse=True)
def _auth_service_users(mock_aiohttp_get_request):
    # the editor's GET asks the auth service for the importer's details
    with mock_aiohttp_get_request:
        yield


@pytest.fixture()
def enabled(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", True)


@pytest.fixture()
async def v2_form(workspace_form, enabled):
    doc = await container.form_repo().get_form_document_by_id(workspace_form.form_id)
    await _make_v2(doc)
    return await container.form_repo().get_form_document_by_id(workspace_form.form_id)


async def _etag(client, workspace, form_id, cookies) -> str:
    response = await client.get(_form_url(workspace, form_id), cookies=cookies)
    assert response.status_code == 200, response.text
    etag = response.headers["ETag"]
    assert response.json()["etag"] == etag
    return etag


async def _member(workspace, role) -> User:
    user = User(id=str(PydanticObjectId()), sub=f"{role.value.lower()}@example.org")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[role]
        )
    )
    return user


class TestEditorGet:
    async def test_the_editor_get_carries_the_etag(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        response = await client.get(
            _form_url(workspace, v2_form.form_id), cookies=test_user_cookies
        )
        assert response.status_code == 200, response.text
        etag = response.headers["ETag"]
        assert etag.startswith('"') and response.json()["etag"] == etag
        # the public API's version of the same form
        spec, public_etag = await container.form_spec_writer().read(
            workspace.id, v2_form.form_id
        )
        assert etag == public_etag

    async def test_a_form_without_pages_still_gets_one(
        self, client: AsyncClient, workspace, workspace_form, enabled,
        test_user_cookies,
    ):
        response = await client.get(
            _form_url(workspace, workspace_form.form_id), cookies=test_user_cookies
        )
        assert response.status_code == 200, response.text
        assert response.headers["ETag"] == response.json()["etag"]

    async def test_no_etag_while_off_for_viewers_or_respondents(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies,
        monkeypatch,
    ):
        viewer = await _member(workspace, WorkspaceRoles.VIEWER)
        response = await client.get(
            _form_url(workspace, v2_form.form_id), cookies=_cookies(viewer)
        )
        assert response.status_code == 200, response.text
        assert "ETag" not in response.headers and response.json()["etag"] is None

        await container.workspace_form_service().publish_form(
            workspace.id, v2_form.form_id, testUser
        )
        published = await client.get(
            _form_url(workspace, v2_form.form_id) + "?published=true"
        )
        assert published.status_code == 200, published.text
        assert "ETag" not in published.headers

        monkeypatch.setattr(settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", False)
        response = await client.get(
            _form_url(workspace, v2_form.form_id), cookies=test_user_cookies
        )
        assert "ETag" not in response.headers and response.json()["etag"] is None


class TestFlagAndAuth:
    async def test_off_is_404(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        response = await client.post(
            _ops_url(workspace, workspace_form.form_id),
            json=RENAME,
            headers=_headers('"x"', "k1"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 404

    async def test_outsiders_and_viewers_are_refused(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies_1
    ):
        url = _ops_url(workspace, v2_form.form_id)
        viewer = await _member(workspace, WorkspaceRoles.VIEWER)
        for cookies in (test_user_cookies_1, _cookies(viewer)):
            response = await client.post(
                url, json=RENAME, headers=_headers('"x"', "k1"), cookies=cookies
            )
            assert response.status_code == 403, response.text
        stored = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert stored.title == v2_form.title

    async def test_signed_out_is_401(self, client: AsyncClient, workspace, v2_form):
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json=RENAME,
            headers=_headers('"x"', "k1"),
        )
        assert response.status_code == 401

    async def test_another_workspaces_form_is_404(
        self, client: AsyncClient, workspace, workspace_1, workspace_form_1,
        enabled, test_user_cookies,
    ):
        response = await client.post(
            _ops_url(workspace, workspace_form_1.form_id),
            json=RENAME,
            headers=_headers('"x"', "k1"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 404

    async def test_an_editor_saves(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        editor = await _member(workspace, WorkspaceRoles.EDITOR)
        etag = await _etag(client, workspace, v2_form.form_id, _cookies(editor))
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json=RENAME,
            headers=_headers(etag, "k1"),
            cookies=_cookies(editor),
        )
        assert response.status_code == 200, response.text


class TestPreconditions:
    async def test_if_match_is_required_and_enforced(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        url = _ops_url(workspace, v2_form.form_id)
        response = await client.post(
            url, json=RENAME, headers=_headers(key="k1"), cookies=test_user_cookies
        )
        assert response.status_code == 428, response.text
        assert response.json()["code"] == "precondition_required"

        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        response = await client.post(
            url,
            json=RENAME,
            headers=_headers('"0-stale"', "k2"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 412, response.text
        assert response.json()["code"] == "precondition_failed"

        first = await client.post(
            url, json=RENAME, headers=_headers(etag, "k3"), cookies=test_user_cookies
        )
        assert first.status_code == 200, first.text
        # the ETag the first save was based on is stale now
        again = await client.post(
            url,
            json={"ops": [{"op": "update_form_info", "title": "Again"}]},
            headers=_headers(etag, "k4"),
            cookies=test_user_cookies,
        )
        assert again.status_code == 412, again.text
        stored = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert stored.title == "Renamed"

    async def test_idempotency_key_is_required(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        url = _ops_url(workspace, v2_form.form_id)
        response = await client.post(
            url, json=RENAME, headers=_headers(etag), cookies=test_user_cookies
        )
        assert response.status_code == 400, response.text
        assert response.json()["code"] == "idempotency_key_required"
        response = await client.post(
            url,
            json=RENAME,
            headers=_headers(etag, "x" * 300),
            cookies=test_user_cookies,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_idempotency_key"


class TestSave:
    async def test_saves_and_answers_the_editor_form(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json={
                "atomic": True,
                "ops": [
                    {"op": "update_form_info", "title": "Renamed"},
                    {
                        "op": "add_field",
                        "pageId": "page-2",
                        "field": {"title": "Your email", "type": "email"},
                    },
                ],
            },
            headers=_headers(etag, "save-1"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["applied"] is True
        assert [r["ok"] for r in body["results"]] == [True, True]
        new_etag = response.headers["ETag"]
        assert new_etag != etag and body["etag"] == new_etag
        # the shape of the editor's GET, which answers the same version
        got = await client.get(
            _form_url(workspace, v2_form.form_id), cookies=test_user_cookies
        )
        assert got.headers["ETag"] == new_etag
        expected = got.json()
        expected.pop("importerDetails", None)
        assert body["form"] == expected
        assert body["form"]["title"] == "Renamed"
        assert body["form"]["fields"][1]["properties"]["fields"][0]["title"] == (
            "Your email"
        )

    async def test_atomic_failure_writes_nothing(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        before = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json={
                "ops": [
                    {"op": "update_form_info", "title": "Should not stick"},
                    {"op": "remove_field", "fieldId": "ghost"},
                ]
            },
            headers=_headers(etag, "fail-1"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "ops_failed"
        assert [e["path"] for e in body["errors"]] == ["/ops/1"]
        after = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert after.title == before.title
        assert after.updated_at == before.updated_at
        assert await _etag(client, workspace, v2_form.form_id, test_user_cookies) == (
            etag
        )

    @pytest.mark.parametrize(
        "payload, code",
        [
            ({"ops": [{"op": "launch_rocket"}]}, "invalid_ops"),
            ({"ops": [{"op": "move_page", "pageId": "page-1"}]}, "invalid_ops"),
            ({"ops": [], "atomic": False}, "invalid_request"),
            ({"ops": [], "extra": 1}, "invalid_request"),
            (
                {"ops": [{"op": "update_form_info", "title": "x"}] * 201},
                "too_many_ops",
            ),
        ],
    )
    async def test_invalid_batches_are_422(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies, payload,
        code,
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json=payload,
            headers=_headers(etag, "bad"),
            cookies=test_user_cookies,
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == code

    async def test_a_save_landing_after_the_check_wins_the_race(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies,
        monkeypatch,
    ):
        """If-Match passed, then another save lands before the write: the
        conditional write refuses this batch with 412 and the other save is
        kept."""
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        original = chat_module.persist_ops_to_form
        raced = {"done": False}

        async def another_save_first(document, form, ops, **kwargs):
            if not raced["done"]:
                raced["done"] = True
                stored = await container.form_repo().get_form_document_by_id(
                    v2_form.form_id
                )
                await original(
                    stored,
                    StandardForm(**stored.model_dump()),
                    parse_ops([{"op": "update_form_info", "title": "Other save"}]),
                    atomic=True,
                )
            return await original(document, form, ops, **kwargs)

        monkeypatch.setattr(editor_ops, "persist_ops_to_form", another_save_first)
        response = await client.post(
            _ops_url(workspace, v2_form.form_id),
            json=RENAME,
            headers=_headers(etag, "race-1"),
            cookies=test_user_cookies,
        )
        assert raced["done"]
        assert response.status_code == 412, response.text
        assert response.json()["code"] == "precondition_failed"
        stored = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert stored.title == "Other save"

    def test_editor_only_ops_are_allowed_here(self):
        from backend.app.services.ai import ops

        assert getattr(ops, "EDITOR_ONLY_OPS", frozenset()) <= EDITOR_OP_NAMES
        assert ops.OP_NAMES <= EDITOR_OP_NAMES


class TestIdempotency:
    async def test_a_retry_replays_and_runs_nothing_twice(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        url = _ops_url(workspace, v2_form.form_id)
        add = {
            "ops": [
                {
                    "op": "add_field",
                    "pageId": "page-2",
                    "field": {"title": "Q", "type": "short_text"},
                }
            ]
        }
        first = await client.post(
            url, json=add, headers=_headers(etag, "add-1"), cookies=test_user_cookies
        )
        assert first.status_code == 200, first.text
        replay = await client.post(
            url,
            content=json.dumps(add, indent=2),
            headers={**_headers(etag, "add-1"), "Content-Type": "application/json"},
            cookies=test_user_cookies,
        )
        assert replay.status_code == 200, replay.text
        assert replay.headers["Idempotent-Replayed"] == "true"
        assert replay.json() == first.json()
        assert replay.headers["ETag"] == first.headers["ETag"]
        stored = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert len(stored.fields[1].properties.fields) == 1

        # only a summary is kept, scoped to the user and the form
        record = await container.idempotency_repo().find(
            idempotency._record_id(
                idempotency_scope(testUser, v2_form.form_id), "add-1"
            )
        )
        summary = json.loads(record.body)
        assert summary["kind"] == "ops" and "form" not in summary

    async def test_the_same_key_with_another_body_is_422(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        etag = await _etag(client, workspace, v2_form.form_id, test_user_cookies)
        url = _ops_url(workspace, v2_form.form_id)
        first = await client.post(
            url, json=RENAME, headers=_headers(etag, "k"), cookies=test_user_cookies
        )
        assert first.status_code == 200, first.text
        reused = await client.post(
            url,
            json={"ops": [{"op": "update_form_info", "title": "Other"}]},
            headers=_headers(first.headers["ETag"], "k"),
            cookies=test_user_cookies,
        )
        assert reused.status_code == 422, reused.text
        assert reused.json()["code"] == "idempotency_key_reused"
        stored = await container.form_repo().get_form_document_by_id(v2_form.form_id)
        assert stored.title == "Renamed"

    async def test_errors_replay_and_keys_are_per_user(
        self, client: AsyncClient, workspace, v2_form, test_user_cookies
    ):
        url = _ops_url(workspace, v2_form.form_id)
        stale = await client.post(
            url,
            json=RENAME,
            headers=_headers('"0-stale"', "e1"),
            cookies=test_user_cookies,
        )
        assert stale.status_code == 412
        again = await client.post(
            url,
            json=RENAME,
            headers=_headers('"0-stale"', "e1"),
            cookies=test_user_cookies,
        )
        assert again.status_code == 412
        assert again.headers["Idempotent-Replayed"] == "true"
        assert again.json() == stale.json()

        # another editor's same key is their own
        editor = await _member(workspace, WorkspaceRoles.EDITOR)
        etag = await _etag(client, workspace, v2_form.form_id, _cookies(editor))
        mine = await client.post(
            url, json=RENAME, headers=_headers(etag, "e1"), cookies=_cookies(editor)
        )
        assert mine.status_code == 200, mine.text
        assert "Idempotent-Replayed" not in mine.headers
