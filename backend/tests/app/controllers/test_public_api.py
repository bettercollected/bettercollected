"""The public REST API (/api/v1/public/v1): Bearer API keys only, the same
scopes and creator re-check as MCP, ETags, idempotency, rate limit, one
error shape, and the committed OpenAPI document."""

import asyncio
import copy
import json
import re
from typing import Any, Coroutine

from beanie import PydanticObjectId
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.public_api import openapi as public_openapi
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services import idempotency
from backend.app.services.form_spec.writes import FormSpecWriter
from backend.config import settings
from tests.app.controllers.data import formResponse, testUser, testUser1, testUser2

BASE = "/api/v1/public/v1"

SPEC = {
    "specVersion": "1",
    "title": "Event sign-up",
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {
                    "id": "name",
                    "type": "short_text",
                    "title": "Your name",
                    "validations": {"required": True, "maxLength": 80},
                },
                {
                    "id": "dinner",
                    "type": "yes_no",
                    "title": "Will you join the dinner?",
                    "choices": [{"value": "Yes"}, {"value": "No"}],
                },
            ],
        }
    ],
    "endings": [{"title": "Thanks", "message": "See you there."}],
    "trust": {"purpose": "To plan seats and catering.", "showSubmissionNumber": True},
}

ALL_SCOPES = ["forms:read", "forms:write", "responses:read"]


async def _token(workspace_id, scopes=ALL_SCOPES, user=testUser) -> str:
    created = await container.api_key_service().create_key(
        workspace_id,
        CreateAPIKeyDto(
            name="api test key",
            scopes=scopes,
            acknowledge_unredacted_responses="responses:read" in scopes,
        ),
        user,
    )
    return created.token


def _auth(token: str, **headers) -> dict:
    return {"Authorization": f"Bearer {token}", **headers}


def _is_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["code"] == code, body
    assert isinstance(body["message"], str) and body["message"]
    assert set(body) <= {"code", "message", "errors"}
    return body


async def _create(client, token, spec=SPEC, **headers):
    response = await client.post(
        f"{BASE}/forms", json=spec, headers=_auth(token, **headers)
    )
    assert response.status_code == 201, response.text
    return response


async def _form_count(workspace_id) -> int:
    return len(await container.workspace_form_repo().list_in_workspace(workspace_id))


# -- authentication and scopes ---------------------------------------------------


class TestAuth:
    async def test_missing_bad_and_non_bearer_credentials_are_401(
        self, client: AsyncClient, workspace, test_user_cookies
    ):
        for headers, cookies in (
            ({}, None),
            ({"Authorization": "Bearer bc_not_a_real_key"}, None),
            ({"Authorization": "Basic dXNlcjpwYXNz"}, None),
            # a browser session is never accepted here
            ({}, test_user_cookies),
        ):
            client.cookies.clear()
            response = await client.get(
                f"{BASE}/forms", headers=headers, cookies=cookies
            )
            _is_error(response, 401, "unauthorized")
            assert response.headers["WWW-Authenticate"] == "Bearer"
        client.cookies.clear()

    async def test_a_revoked_key_is_401(self, client: AsyncClient, workspace):
        created = await container.api_key_service().create_key(
            workspace.id, CreateAPIKeyDto(name="k", scopes=["forms:read"]), testUser
        )
        assert (
            await client.get(f"{BASE}/forms", headers=_auth(created.token))
        ).status_code == 200
        await container.api_key_service().revoke_key(workspace.id, created.id, testUser)
        _is_error(
            await client.get(f"{BASE}/forms", headers=_auth(created.token)),
            401,
            "unauthorized",
        )

    async def test_a_missing_scope_is_403(self, client: AsyncClient, workspace):
        token = await _token(workspace.id, ["forms:read"])
        body = _is_error(
            await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(token)),
            403,
            "missing_scope",
        )
        assert "forms:write" in body["message"]
        assert await _form_count(workspace.id) == 0

    async def test_the_creators_current_permissions_apply(
        self, client: AsyncClient, workspace, workspace_form
    ):
        creator = User(id=str(PydanticObjectId()), sub="api-creator@example.com")
        repo = container.workspace_user_repo()
        await repo.save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=creator.id,
                roles=[WorkspaceRoles.ADMIN],
            )
        )
        token = await _token(workspace.id, ALL_SCOPES, user=creator)
        url = f"{BASE}/forms/{workspace_form.form_id}/responses"
        assert (await client.get(url, headers=_auth(token))).status_code == 200

        membership = await repo.find_workspace_user(
            workspace.id, PydanticObjectId(creator.id)
        )
        membership.roles = [WorkspaceRoles.VIEWER]
        await repo.save(membership)
        body = _is_error(
            await client.get(url, headers=_auth(token)),
            403,
            "key_creator_lacks_permission",
        )
        assert "response.export" in body["message"]

        await repo.delete(workspace.id, creator.id)
        _is_error(
            await client.get(f"{BASE}/forms", headers=_auth(token)),
            403,
            "key_creator_lacks_permission",
        )

    async def test_another_workspaces_form_is_not_found(
        self, client: AsyncClient, workspace_1, workspace_form
    ):
        token = await _token(workspace_1.id, user=testUser1)
        form_id = workspace_form.form_id
        for method, path, body in (
            ("GET", f"/forms/{form_id}", None),
            ("PUT", f"/forms/{form_id}", SPEC),
            ("POST", f"/forms/{form_id}/ops", {"ops": []}),
            ("POST", f"/forms/{form_id}/ops/dry-run", {"ops": []}),
            ("POST", f"/forms/{form_id}/publish", None),
            ("GET", f"/forms/{form_id}/responses", None),
        ):
            response = await client.request(
                method,
                BASE + path,
                json=body,
                headers=_auth(token, **{"If-Match": "*"}),
            )
            _is_error(response, 404, "not_found")
        listed = await client.get(f"{BASE}/forms", headers=_auth(token))
        assert form_id not in [f["formId"] for f in listed.json()["items"]]

    async def test_calls_are_audited(self, client: AsyncClient, workspace):
        token = await _token(workspace.id, ["forms:read"])
        await client.get(f"{BASE}/forms", headers=_auth(token))
        await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(token))
        logs = await container.mcp_audit_log_repo().list_by_workspace(workspace.id)
        by_tool = {log.tool: log for log in logs}
        assert by_tool["api:list_forms"].ok is True
        assert by_tool["api:create_form"].ok is False
        assert "403" in by_tool["api:create_form"].detail


# -- forms -------------------------------------------------------------------------


class TestForms:
    async def test_create_read_list_and_publish(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        created = await _create(client, token)
        body = created.json()
        form_id = body["formId"]
        assert created.headers["Location"] == f"{BASE}/forms/{form_id}"
        assert body["form"]["title"] == "Event sign-up"
        assert body["form"]["trust"]["purpose"] == "To plan seats and catering."
        assert body["form"]["trust"]["showSubmissionNumber"] is True
        assert [f["id"] for f in body["form"]["pages"][0]["fields"]] == [
            "name",
            "dinner",
        ]

        got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert got.status_code == 200
        assert got.headers["ETag"] == created.headers["ETag"]
        assert got.json() == body["form"]

        listed = await client.get(
            f"{BASE}/forms", params={"page": 1, "size": 1}, headers=_auth(token)
        )
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["formId"] == form_id
        assert listed.json()["items"][0]["published"] is False

        published = await client.post(
            f"{BASE}/forms/{form_id}/publish", headers=_auth(token)
        )
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True
        assert published.json()["slug"]

    async def test_list_is_paginated(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        ids = [(await _create(client, token)).json()["formId"] for _ in range(3)]
        seen = []
        for page in (1, 2):
            listed = await client.get(
                f"{BASE}/forms", params={"page": page, "size": 2}, headers=_auth(token)
            )
            assert listed.json()["total"] == 3
            seen += [f["formId"] for f in listed.json()["items"]]
        assert sorted(seen) == sorted(ids)

    async def test_pages_and_sizes_are_capped(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        for params in ({"page": 10_001}, {"size": 101}, {"page": 0}):
            _is_error(
                await client.get(f"{BASE}/forms", params=params, headers=_auth(token)),
                422,
                "invalid_request",
            )

    async def test_an_invalid_document_creates_nothing(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        bad = copy.deepcopy(SPEC)
        bad["pages"][0]["fields"][1]["logic"] = {
            "action": "SHOW",
            "conditions": [{"fieldId": "nope", "comparison": "IS_EQUAL", "value": 1}],
        }
        bad["pages"][0]["fields"][0]["colour"] = "red"
        response = await client.post(f"{BASE}/forms", json=bad, headers=_auth(token))
        body = _is_error(response, 422, "invalid_spec")
        assert {"path": "/pages/0/fields/0/colour", "message": "Unknown property."} in (
            body["errors"]
        )
        assert await _form_count(workspace.id) == 0

        not_json = await client.post(
            f"{BASE}/forms",
            content=b"{not json",
            headers=_auth(token, **{"Content-Type": "application/json"}),
        )
        _is_error(not_json, 422, "unprocessable")

    async def test_a_document_over_one_megabyte_is_413(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        huge = dict(SPEC, description="x" * (1024 * 1024 + 1))
        _is_error(
            await client.post(f"{BASE}/forms", json=huge, headers=_auth(token)),
            413,
            "payload_too_large",
        )

    async def test_a_logo_url_in_the_document_is_ignored(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        spec = dict(SPEC, logo={"url": "https://example.com/logo.png", "alt": "Org"})
        form = (await _create(client, token, spec)).json()["form"]
        assert form["logo"] == {"alt": "Org"}

    async def test_validate_reports_without_storing(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id, ["forms:read"])
        bad = dict(SPEC, specVersion="2")
        result = await client.post(
            f"{BASE}/forms/validate", json=bad, headers=_auth(token)
        )
        assert result.status_code == 200
        assert result.json()["valid"] is False
        assert result.json()["errors"][0]["path"] == "/specVersion"
        ok = await client.post(
            f"{BASE}/forms/validate", json=SPEC, headers=_auth(token)
        )
        assert ok.json()["valid"] is True
        assert await _form_count(workspace.id) == 0


# -- replace (PUT) and ETags -------------------------------------------------------


class TestReplace:
    async def test_if_match_is_required_and_enforced(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        url = f"{BASE}/forms/{form_id}"
        changed = dict(copy.deepcopy(SPEC), title="Renamed")

        _is_error(
            await client.put(url, json=changed, headers=_auth(token)),
            428,
            "precondition_required",
        )
        _is_error(
            await client.put(
                url, json=changed, headers=_auth(token, **{"If-Match": '"0-stale"'})
            ),
            412,
            "precondition_failed",
        )

        replaced = await client.put(
            url, json=changed, headers=_auth(token, **{"If-Match": etag})
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["title"] == "Renamed"
        new_etag = replaced.headers["ETag"]
        assert new_etag != etag
        got = await client.get(url, headers=_auth(token))
        assert got.json() == replaced.json()
        assert got.headers["ETag"] == new_etag

        # the old ETag is now stale
        _is_error(
            await client.put(
                url, json=SPEC, headers=_auth(token, **{"If-Match": etag})
            ),
            412,
            "precondition_failed",
        )

    async def test_replace_replaces_content_and_merges_trust(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        spec = copy.deepcopy(SPEC)
        spec["pages"][0]["fields"] = spec["pages"][0]["fields"][:1]
        spec["trust"] = {"retentionText": "Kept for a month."}
        replaced = await client.put(
            f"{BASE}/forms/{form_id}",
            json=spec,
            headers=_auth(token, **{"If-Match": etag}),
        )
        assert replaced.status_code == 200, replaced.text
        form = replaced.json()
        assert [f["id"] for f in form["pages"][0]["fields"]] == ["name"]
        # trust keys left out keep their stored values
        assert form["trust"]["purpose"] == "To plan seats and catering."
        assert form["trust"]["retentionText"] == "Kept for a month."

    async def test_an_invalid_replacement_changes_nothing(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        bad = dict(copy.deepcopy(SPEC), pages="nope")
        _is_error(
            await client.put(
                f"{BASE}/forms/{form_id}",
                json=bad,
                headers=_auth(token, **{"If-Match": etag}),
            ),
            422,
            "invalid_spec",
        )
        got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert got.headers["ETag"] == etag

    async def test_a_save_landing_after_the_check_wins_the_race(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        """If-Match passed, then another save lands before the write: the
        conditional write (update_form_if_unchanged) refuses the replace with
        412 and the other save is kept."""
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        original_load = FormSpecWriter._load
        raced = {"done": False}

        async def load_then_another_save(self, workspace_id, form_id_):
            loaded = await original_load(self, workspace_id, form_id_)
            if not raced["done"]:
                raced["done"] = True
                answer = await client.post(
                    f"{BASE}/forms/{form_id}/ops",
                    json={"ops": [{"op": "update_form_info", "title": "Other save"}]},
                    headers=_auth(token),
                )
                assert answer.status_code == 200, answer.text
            return loaded

        monkeypatch.setattr(FormSpecWriter, "_load", load_then_another_save)
        changed = dict(copy.deepcopy(SPEC), title="Mine")
        _is_error(
            await client.put(
                f"{BASE}/forms/{form_id}",
                json=changed,
                headers=_auth(token, **{"If-Match": etag}),
            ),
            412,
            "precondition_failed",
        )
        stored = await container.form_repo().get_form_document_by_id(form_id)
        assert stored.title == "Other save"

    async def test_simultaneous_replaces_one_wins(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        answers = await asyncio.gather(
            *(
                client.put(
                    f"{BASE}/forms/{form_id}",
                    json=dict(copy.deepcopy(SPEC), title=f"Writer {i}"),
                    headers=_auth(token, **{"If-Match": etag}),
                )
                for i in range(4)
            )
        )
        statuses = sorted(a.status_code for a in answers)
        assert statuses.count(200) == 1, [a.text for a in answers]
        assert statuses.count(412) == 3

    async def test_replace_dry_run_shows_the_diff(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        changed = dict(copy.deepcopy(SPEC), title="Preview")
        preview = await client.post(
            f"{BASE}/forms/{form_id}/replace/dry-run",
            json=changed,
            headers=_auth(token),
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["valid"] is True
        assert body["form"]["title"] == "Preview"
        assert {"path": "/title", "before": "Event sign-up", "after": "Preview"} in (
            body["diff"]["form"]
        )
        # what the preview shows is what PUT stores
        replaced = await client.put(
            f"{BASE}/forms/{form_id}",
            json=changed,
            headers=_auth(token, **{"If-Match": etag}),
        )
        assert replaced.json() == body["form"]


# -- operations --------------------------------------------------------------------


class TestOps:
    async def test_atomic_by_default_and_a_failure_writes_nothing(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        before = await container.form_repo().get_form_document_by_id(form_id)
        response = await client.post(
            f"{BASE}/forms/{form_id}/ops",
            json={
                "ops": [
                    {"op": "update_form_info", "title": "Should not stick"},
                    {"op": "remove_field", "fieldId": "missing"},
                ]
            },
            headers=_auth(token),
        )
        body = _is_error(response, 422, "ops_failed")
        assert body["errors"][0]["path"] == "/ops/1"
        after = await container.form_repo().get_form_document_by_id(form_id)
        assert after.title == before.title == "Event sign-up"
        assert after.updated_at == before.updated_at
        got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert got.headers["ETag"] == etag

    async def test_refs_apply_and_if_match_is_enforced(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        ops = {
            "ops": [
                {
                    "op": "add_page",
                    "ref": "contact",
                    "fields": [{"title": "Email", "type": "email", "ref": "email"}],
                },
                {
                    "op": "set_field_validation",
                    "fieldId": "$ref:email",
                    "validation": {"required": True},
                },
            ]
        }
        applied = await client.post(
            f"{BASE}/forms/{form_id}/ops",
            json=ops,
            headers=_auth(token, **{"If-Match": etag}),
        )
        assert applied.status_code == 200, applied.text
        body = applied.json()
        assert body["applied"] is True and body["atomic"] is True
        assert len(body["form"]["pages"]) == 2
        assert applied.headers["ETag"] != etag
        _is_error(
            await client.post(
                f"{BASE}/forms/{form_id}/ops",
                json=ops,
                headers=_auth(token, **{"If-Match": etag}),
            ),
            412,
            "precondition_failed",
        )

    async def test_non_atomic_applies_what_it_can(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        form_id = (await _create(client, token)).json()["formId"]
        response = await client.post(
            f"{BASE}/forms/{form_id}/ops",
            json={
                "atomic": False,
                "ops": [
                    {"op": "update_form_info", "title": "Kept"},
                    {"op": "remove_field", "fieldId": "missing"},
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        assert [r["ok"] for r in response.json()["results"]] == [True, False]
        assert response.json()["form"]["title"] == "Kept"

    async def test_malformed_and_oversized_batches_are_422(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        form_id = (await _create(client, token)).json()["formId"]
        url = f"{BASE}/forms/{form_id}/ops"
        body = _is_error(
            await client.post(
                url, json={"ops": [{"op": "no_such_op"}]}, headers=_auth(token)
            ),
            422,
            "invalid_ops",
        )
        assert body["errors"][0]["path"].startswith("/ops/0")
        _is_error(
            await client.post(
                url,
                json={"ops": [{"op": "update_form_info", "title": "x"}] * 201},
                headers=_auth(token),
            ),
            422,
            "too_many_ops",
        )
        _is_error(
            await client.post(url, json={"atomic": True}, headers=_auth(token)),
            422,
            "invalid_request",
        )

    async def test_editor_ops_are_refused_per_op(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        ops = [
            {"op": "update_form_info", "title": "Not stored"},
            {
                "op": "insert_field",
                "pageId": "page-1",
                "index": 0,
                "field": {"id": "x", "type": "short_text"},
            },
            {"op": "set_hidden_fields", "names": ["utm_source"]},
        ]
        for path, code in (("ops", "invalid_ops"), ("ops/dry-run", "unprocessable")):
            body = _is_error(
                await client.post(
                    f"{BASE}/forms/{form_id}/{path}",
                    json={"ops": ops, "atomic": False},
                    headers=_auth(token),
                ),
                422,
                code,
            )
            assert [e["path"] for e in body["errors"]] == ["/ops/1", "/ops/2"]
            assert all(
                "only available in the form editor" in e["message"]
                for e in body["errors"]
            )
        got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert got.headers["ETag"] == etag

    async def test_dry_run_stores_nothing(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        preview = await client.post(
            f"{BASE}/forms/{form_id}/ops/dry-run",
            json={"ops": [{"op": "update_form_info", "title": "Preview"}]},
            headers=_auth(token),
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["form"]["title"] == "Preview"
        assert preview.json()["diff"]["changed"] is True
        got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert got.headers["ETag"] == etag
        assert got.json()["title"] == "Event sign-up"


# -- idempotency -------------------------------------------------------------------


class TestIdempotency:
    async def test_a_retry_replays_the_first_response(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        first = await _create(client, token, **{"Idempotency-Key": "create-1"})
        # same request, key order and spacing differ: still the same request
        second = await client.post(
            f"{BASE}/forms",
            content=json.dumps(dict(reversed(list(SPEC.items()))), indent=2),
            headers=_auth(
                token,
                **{"Idempotency-Key": "create-1", "Content-Type": "application/json"},
            ),
        )
        assert second.status_code == 201, second.text
        assert second.headers["Idempotent-Replayed"] == "true"
        assert second.json() == first.json()
        assert second.headers["ETag"] == first.headers["ETag"]
        assert second.headers["Location"] == first.headers["Location"]
        assert await _form_count(workspace.id) == 1

        # only a summary is kept, never the form
        [api_key] = await container.workspace_api_key_repo().list_by_workspace(
            workspace.id
        )
        record = await container.idempotency_repo().find(
            idempotency._record_id(str(api_key.id), "create-1")
        )
        assert json.loads(record.body) == {
            "kind": "created",
            "formId": first.json()["formId"],
        }

        # another key is another request
        await _create(client, token, **{"Idempotency-Key": "create-2"})
        assert await _form_count(workspace.id) == 2

    async def test_a_replayed_edit_shows_the_form_as_it_is_now(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        form_id = (await _create(client, token)).json()["formId"]
        url = f"{BASE}/forms/{form_id}/ops"
        ops = {"ops": [{"op": "update_form_info", "title": "First"}]}
        headers = _auth(token, **{"Idempotency-Key": "edit-1"})
        first = await client.post(url, json=ops, headers=headers)
        assert first.status_code == 200, first.text
        later = await client.post(
            url,
            json={"ops": [{"op": "update_form_info", "title": "Later"}]},
            headers=_auth(token),
        )
        replay = await client.post(url, json=ops, headers=headers)
        assert replay.status_code == 200
        assert replay.headers["Idempotent-Replayed"] == "true"
        assert replay.json()["results"] == first.json()["results"]
        assert replay.json()["form"]["title"] == "Later"  # not run again
        assert replay.headers["ETag"] == later.headers["ETag"]

    async def test_the_same_key_with_another_body_is_422(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        await _create(client, token, **{"Idempotency-Key": "k"})
        _is_error(
            await client.post(
                f"{BASE}/forms",
                json=dict(SPEC, title="Other"),
                headers=_auth(token, **{"Idempotency-Key": "k"}),
            ),
            422,
            "idempotency_key_reused",
        )
        assert await _form_count(workspace.id) == 1

    async def test_keys_belong_to_one_api_key(self, client: AsyncClient, workspace):
        one, two = await _token(workspace.id), await _token(workspace.id)
        await _create(client, one, **{"Idempotency-Key": "shared"})
        again = await _create(client, two, **{"Idempotency-Key": "shared"})
        assert "Idempotent-Replayed" not in again.headers
        assert await _form_count(workspace.id) == 2

    async def test_ops_and_publish_and_errors_replay(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        form_id = (await _create(client, token)).json()["formId"]
        url = f"{BASE}/forms/{form_id}/ops"
        failing = {"ops": [{"op": "remove_field", "fieldId": "missing"}]}
        first = await client.post(
            url, json=failing, headers=_auth(token, **{"Idempotency-Key": "ops-1"})
        )
        again = await client.post(
            url, json=failing, headers=_auth(token, **{"Idempotency-Key": "ops-1"})
        )
        assert first.status_code == again.status_code == 422
        assert again.json() == first.json()
        assert again.headers["Idempotent-Replayed"] == "true"

        adding = {"ops": [{"op": "add_page", "fields": []}]}
        for _ in range(2):
            answer = await client.post(
                url, json=adding, headers=_auth(token, **{"Idempotency-Key": "ops-2"})
            )
            assert answer.status_code == 200, answer.text
        stored = await container.form_repo().get_form_document_by_id(form_id)
        assert len(stored.fields) == 2  # added once

        publish = f"{BASE}/forms/{form_id}/publish"
        for _ in range(2):
            answer = await client.post(
                publish, headers=_auth(token, **{"Idempotency-Key": "pub-1"})
            )
            assert answer.status_code == 200, answer.text
        assert answer.headers["Idempotent-Replayed"] == "true"

    async def test_an_invalid_key_is_400(self, client: AsyncClient, workspace):
        token = await _token(workspace.id)
        _is_error(
            await client.post(
                f"{BASE}/forms",
                json=SPEC,
                headers=_auth(token, **{"Idempotency-Key": "x" * 300}),
            ),
            400,
            "invalid_idempotency_key",
        )


# -- rate limit --------------------------------------------------------------------


class TestRateLimit:
    async def test_429_with_retry_after_per_key(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_REQUESTS_PER_WINDOW", 2)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_WINDOW_SECONDS", 3600)
        token, other = await _token(workspace.id), await _token(workspace.id)
        for _ in range(2):
            assert (
                await client.get(f"{BASE}/forms", headers=_auth(token))
            ).status_code == 200
        limited = await client.get(f"{BASE}/forms", headers=_auth(token))
        _is_error(limited, 429, "rate_limited")
        assert 0 < int(limited.headers["Retry-After"]) <= 3600
        # counted per API key
        assert (
            await client.get(f"{BASE}/forms", headers=_auth(other))
        ).status_code == 200

    async def test_a_ceiling_for_all_of_a_workspaces_keys(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        api = settings.api_settings
        monkeypatch.setattr(api, "PUBLIC_API_REQUESTS_PER_WINDOW", 100)
        monkeypatch.setattr(api, "PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", 3)
        monkeypatch.setattr(api, "PUBLIC_API_WINDOW_SECONDS", 3600)
        keys = [await _token(workspace.id) for _ in range(4)]
        for token in keys[:3]:
            assert (
                await client.get(f"{BASE}/forms", headers=_auth(token))
            ).status_code == 200
        limited = await client.get(f"{BASE}/forms", headers=_auth(keys[3]))
        body = _is_error(limited, 429, "rate_limited")
        assert "workspace" in body["message"]
        assert int(limited.headers["Retry-After"]) > 0

    async def test_zero_turns_it_off(self, client: AsyncClient, workspace, monkeypatch):
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_REQUESTS_PER_WINDOW", 0)
        token = await _token(workspace.id)
        for _ in range(3):
            assert (
                await client.get(f"{BASE}/forms", headers=_auth(token))
            ).status_code == 200


# -- responses ---------------------------------------------------------------------


class TestResponses:
    async def test_list_and_get_follow_the_privacy_rules(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form: Coroutine[Any, Any, FormDocument],
    ):
        token = await _token(workspace.id)
        response = await container.workspace_form_service().submit_response(
            workspace.id,
            published_form.form_id,
            StandardFormResponse(**formResponse),
            testUser2,
        )
        await container.form_response_service().request_for_response_deletion(
            workspace.id, response.response_id, testUser
        )
        url = f"{BASE}/forms/{published_form.form_id}/responses"
        listed = await client.get(url, headers=_auth(token))
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        item = listed.json()["items"][0]
        assert item["responseId"] == response.response_id
        assert item["deletionRequest"] == {"status": "pending"}

        detail = await client.get(f"{url}/{response.response_id}", headers=_auth(token))
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert set(body) == {
            "responseId",
            "formId",
            "submittedAt",
            "answers",
            "internalAnswers",
            "deletionRequest",
        }
        # never who answered
        assert "random@email.com" not in detail.text
        assert body["deletionRequest"] == {"status": "pending"}

        _is_error(
            await client.get(f"{url}/not-a-response", headers=_auth(token)),
            404,
            "not_found",
        )

    async def test_needs_responses_read(
        self, client: AsyncClient, workspace, workspace_form
    ):
        token = await _token(workspace.id, ["forms:read", "forms:write"])
        _is_error(
            await client.get(
                f"{BASE}/forms/{workspace_form.form_id}/responses",
                headers=_auth(token),
            ),
            403,
            "missing_scope",
        )

    async def test_another_workspaces_response_is_not_found(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        workspace_1,
        published_form_1,
    ):
        theirs = await container.workspace_form_service().submit_response(
            workspace_1.id,
            published_form_1.form_id,
            StandardFormResponse(**formResponse),
            testUser2,
        )
        token = await _token(workspace.id)
        _is_error(
            await client.get(
                f"{BASE}/forms/{workspace_form.form_id}/responses/"
                f"{theirs.response_id}",
                headers=_auth(token),
            ),
            404,
            "not_found",
        )


class TestDeleteForm:
    async def test_deletes_the_form_and_its_responses(
        self, client: AsyncClient, workspace, published_form
    ):
        token = await _token(workspace.id)
        form_id = published_form.form_id
        response = await container.workspace_form_service().submit_response(
            workspace.id, form_id, StandardFormResponse(**formResponse), testUser2
        )

        deleted = await client.delete(f"{BASE}/forms/{form_id}", headers=_auth(token))
        assert deleted.status_code == 204, deleted.text
        assert deleted.content == b""
        _is_error(
            await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token)),
            404,
            "not_found",
        )
        assert await _form_count(workspace.id) == 0
        assert (
            await container.form_response_service().workspace_response(
                workspace.id, response.response_id
            )
        ) is None
        _is_error(
            await client.delete(f"{BASE}/forms/{form_id}", headers=_auth(token)),
            404,
            "not_found",
        )

    async def test_needs_forms_write_and_the_creators_form_delete(
        self, client: AsyncClient, workspace, workspace_form
    ):
        url = f"{BASE}/forms/{workspace_form.form_id}"
        read_only = await _token(workspace.id, ["forms:read"])
        _is_error(
            await client.delete(url, headers=_auth(read_only)), 403, "missing_scope"
        )

        # a viewer may not change forms: a key they made is refused
        creator = await _member(workspace, WorkspaceRoles.ADMIN)
        token = await _token(workspace.id, ["forms:read", "forms:write"], user=creator)
        await _set_role(workspace, creator, WorkspaceRoles.VIEWER)
        _is_error(
            await client.delete(url, headers=_auth(token)),
            403,
            "key_creator_lacks_permission",
        )
        assert await _form_count(workspace.id) == 1

    async def test_another_workspaces_form_is_not_found(
        self, client: AsyncClient, workspace, workspace_1, workspace_form
    ):
        token = await _token(workspace_1.id, user=testUser1)
        _is_error(
            await client.delete(
                f"{BASE}/forms/{workspace_form.form_id}", headers=_auth(token)
            ),
            404,
            "not_found",
        )
        assert await _form_count(workspace.id) == 1


async def _member(workspace, role) -> User:
    user = User(id=str(PydanticObjectId()), sub="api-member@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
    )
    return user


async def _set_role(workspace, user: User, role) -> None:
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, PydanticObjectId(user.id))
    membership.roles = [role]
    await repo.save(membership)


CLOSE_SCOPES = ALL_SCOPES + ["deletion_requests:read", "deletion_requests:write"]


async def _pending_request(workspace, form) -> str:
    response = await container.workspace_form_service().submit_response(
        workspace.id, form.form_id, StandardFormResponse(**formResponse), testUser2
    )
    await container.form_response_service().request_for_response_deletion(
        workspace.id, response.response_id, testUser
    )
    return response.response_id


class TestCloseDeletionRequest:
    async def test_declined_keeps_the_response_and_records_the_reason(
        self, client: AsyncClient, workspace, published_form
    ):
        token = await _token(workspace.id, CLOSE_SCOPES)
        response_id = await _pending_request(workspace, published_form)
        url = f"{BASE}/forms/{published_form.form_id}/responses/{response_id}"

        closed = await client.post(
            f"{url}/deletion-request/close",
            json={"outcome": "declined", "reason": "legal_obligation"},
            headers=_auth(token),
        )
        assert closed.status_code == 200, closed.text
        assert closed.json() == {
            "formId": published_form.form_id,
            "responseId": response_id,
            "status": "declined",
            "declineReason": "legal_obligation",
        }
        detail = await client.get(url, headers=_auth(token))
        assert detail.status_code == 200
        assert detail.json()["deletionRequest"] == {"status": "declined"}

        _is_error(
            await client.post(
                f"{url}/deletion-request/close",
                json={"outcome": "completed"},
                headers=_auth(token),
            ),
            409,
            "deletion_request_closed",
        )

    async def test_completed_deletes_the_stored_copy(
        self, client: AsyncClient, workspace, published_form
    ):
        token = await _token(workspace.id, CLOSE_SCOPES)
        response_id = await _pending_request(workspace, published_form)
        url = f"{BASE}/forms/{published_form.form_id}/responses/{response_id}"
        closed = await client.post(
            f"{url}/deletion-request/close",
            json={"outcome": "completed"},
            headers=_auth(token),
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "success"
        assert closed.json()["declineReason"] is None
        _is_error(await client.get(url, headers=_auth(token)), 404, "not_found")

    async def test_invalid_bodies_are_422_and_change_nothing(
        self, client: AsyncClient, workspace, published_form
    ):
        token = await _token(workspace.id, CLOSE_SCOPES)
        response_id = await _pending_request(workspace, published_form)
        url = (
            f"{BASE}/forms/{published_form.form_id}/responses/{response_id}"
            "/deletion-request/close"
        )
        for body in (
            {"outcome": "declined"},
            {"outcome": "completed", "reason": "other"},
            {"outcome": "declined", "reason": "because I said so"},
            {"outcome": "archived"},
            [],
        ):
            _is_error(
                await client.post(url, json=body, headers=_auth(token)),
                422,
                "invalid_request",
            )
        listed = await client.get(
            f"{BASE}/forms/{published_form.form_id}/responses", headers=_auth(token)
        )
        assert listed.json()["items"][0]["deletionRequest"] == {"status": "pending"}

    async def test_needs_the_write_scope_and_privacy_manage(
        self, client: AsyncClient, workspace, published_form
    ):
        response_id = await _pending_request(workspace, published_form)
        url = (
            f"{BASE}/forms/{published_form.form_id}/responses/{response_id}"
            "/deletion-request/close"
        )
        body = {"outcome": "declined", "reason": "other"}
        token = await _token(workspace.id, ALL_SCOPES + ["deletion_requests:read"])
        message = _is_error(
            await client.post(url, json=body, headers=_auth(token)),
            403,
            "missing_scope",
        )["message"]
        assert "deletion_requests:write" in message

        # an editor (stored as COLLABORATOR) has no privacy.manage
        creator = await _member(workspace, WorkspaceRoles.ADMIN)
        editor_token = await _token(
            workspace.id, ["deletion_requests:write"], user=creator
        )
        await _set_role(workspace, creator, WorkspaceRoles.COLLABORATOR)
        _is_error(
            await client.post(url, json=body, headers=_auth(editor_token)),
            403,
            "key_creator_lacks_permission",
        )

    async def test_another_workspaces_request_is_not_found(
        self, client: AsyncClient, workspace, published_form, workspace_1
    ):
        response_id = await _pending_request(workspace, published_form)
        token = await _token(workspace_1.id, CLOSE_SCOPES, user=testUser1)
        _is_error(
            await client.post(
                f"{BASE}/forms/{published_form.form_id}/responses/{response_id}"
                "/deletion-request/close",
                json={"outcome": "completed"},
                headers=_auth(token),
            ),
            404,
            "not_found",
        )


# -- OpenAPI -----------------------------------------------------------------------


class TestOpenAPI:
    def test_the_committed_document_is_current(self):
        """docs/api/public-v1.openapi.json matches the code (regenerate with
        `uv run python -m backend.app.public_api.openapi`)."""
        assert public_openapi.main(["--check"]) == 0, (
            "docs/api/public-v1.openapi.json is stale: "
            "run python -m backend.app.public_api.openapi"
        )

    async def test_no_interactive_docs_page(self, client: AsyncClient):
        # it would load its scripts from a CDN
        for path in ("/docs", "/redoc"):
            _is_error(await client.get(BASE + path), 404, "not_found")

    async def test_it_is_served_and_self_contained(self, client: AsyncClient):
        served = await client.get(f"{BASE}/openapi.json")
        assert served.status_code == 200
        document = served.json()
        assert document["info"]["title"] == "BetterCollected public API"
        text = json.dumps(document)
        refs = set(re.findall(r"#/components/schemas/(\w+)", text))
        assert refs <= set(document["components"]["schemas"])
        assert "HTTPValidationError" not in text
        for path in document["paths"].values():
            for operation in path.values():
                assert operation["tags"] and operation["operationId"]
                assert operation["security"] == [{"apiKey": []}]


# -- idempotency summaries ---------------------------------------------------------


class TestCompactSummary:
    def test_a_small_summary_is_kept_as_is(self):
        summary = {"kind": "created", "formId": "abc"}
        assert idempotency.compact_summary(summary) == summary

    def test_long_lists_and_messages_are_cut_to_the_cap(self):
        results = [
            {"index": i, "op": "add_field", "ok": False, "message": "x" * 2000}
            for i in range(200)
        ]
        kept = idempotency.compact_summary(
            {"kind": "ops", "applied": False, "atomic": True, "results": results}
        )
        size = len(json.dumps(kept, separators=(",", ":")).encode())
        assert size <= idempotency.MAX_STORED_BYTES
        assert kept["truncated"] is True
        assert 0 < len(kept["results"]) < 200
        assert len(kept["results"][0]["message"]) == idempotency.MAX_STORED_MESSAGE

    def test_an_error_body_keeps_its_code_and_message(self):
        body = {
            "code": "invalid_spec",
            "message": "The document is not a valid form spec.",
            "errors": [
                {"path": f"/pages/{i}", "message": "y" * 500} for i in range(500)
            ],
        }
        kept = idempotency.compact_summary({"kind": "body", "body": body})
        assert kept["body"]["code"] == "invalid_spec"
        assert kept["body"]["truncated"] is True
        assert len(json.dumps(kept).encode()) <= idempotency.MAX_STORED_BYTES
