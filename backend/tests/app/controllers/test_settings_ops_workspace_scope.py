"""Settings operations write the caller's workspace only.

One form id linked to two workspaces (A and B), each with its own trust
settings on its association. A caller of A applies update_form_settings on
every path that takes operations (AI chat, review fix, proposal accept, MCP
update_form, the public API's ops and replace, the builder's op save) and on
every dry run: A's settings change (or are previewed), B's stay exactly as
they were.

B's association is stored first, so a lookup by form id alone would find
B's settings before A's.
"""

import copy
import json
from typing import Any, Dict

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.services.ai import chat as chat_module
from backend.app.services.ai.ops import OpResult, parse_ops
from backend.config import settings as app_settings
from common.models.standard_form import StandardForm
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.data import formData, testUser, testUser1
from tests.app.controllers.test_form_spec_api import _make_v2
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text
from tests.app.controllers.test_public_api import BASE, _auth, _token

B_TRUST = {
    "purpose": "Workspace B purpose",
    "retention_text": "Workspace B keeps answers for two years",
    "privacy_policy_url": "https://b.example.org/privacy",
    "require_verified_identity": True,
    "allow_editing_response": True,
    "show_submission_number": True,
}
A_TRUST = {
    "purpose": "Workspace A purpose",
    "retention_text": "Workspace A keeps answers for a year",
    "privacy_policy_url": "https://a.example.org/privacy",
}
NEW_TRUST = {
    "purpose": "Changed in A",
    "retention_text": "Changed in A: kept for 30 days",
    "privacy_policy_url": "https://a.example.org/new-privacy",
    "require_verified_identity": False,
    "allow_editing_response": False,
    "show_submission_number": False,
}
SETTINGS_OP = {
    "op": "update_form_settings",
    "patch": {
        "purpose": NEW_TRUST["purpose"],
        "retentionText": NEW_TRUST["retention_text"],
        "privacyPolicyUrl": NEW_TRUST["privacy_policy_url"],
        "requireVerifiedIdentity": False,
        "allowEditingResponse": False,
        "showSubmissionNumber": False,
    },
}
# the same values as the spec document's trust block shows them
NEW_TRUST_SPEC = {
    "purpose": NEW_TRUST["purpose"],
    "retentionText": NEW_TRUST["retention_text"],
    "privacyPolicyUrl": NEW_TRUST["privacy_policy_url"],
}


async def _settings(workspace_id, form_id) -> Dict[str, Any]:
    association = await container.workspace_form_repo().find_workspace_form(
        workspace_id, form_id
    )
    assert association is not None
    return association.settings.model_dump()


def _change(diff: Any, path: str) -> Any:
    """The entry of a spec diff for ``path``, wherever the diff lists it."""
    if isinstance(diff, dict):
        if diff.get("path") == path:
            return diff
        values = diff.values()
    elif isinstance(diff, list):
        values = diff
    else:
        return None
    for value in values:
        found = _change(value, path)
        if found is not None:
            return found
    return None


def _trust_of(settings: Dict[str, Any]) -> Dict[str, Any]:
    return {key: settings.get(key) for key in NEW_TRUST}


class Shared:
    def __init__(self, a, b, form_id, a_before, b_before):
        self.a, self.b, self.form_id = a, b, form_id
        self.a_before, self.b_before = a_before, b_before

    async def assert_a_changed_b_kept(self):
        a_after = await _settings(self.a.id, self.form_id)
        assert _trust_of(a_after) == NEW_TRUST
        # nothing else on A's association moved
        assert {k: v for k, v in a_after.items() if k not in NEW_TRUST} == {
            k: v for k, v in self.a_before.items() if k not in NEW_TRUST
        }
        assert await _settings(self.b.id, self.form_id) == self.b_before

    async def assert_nothing_stored(self):
        assert await _settings(self.a.id, self.form_id) == self.a_before
        assert await _settings(self.b.id, self.form_id) == self.b_before


@pytest.fixture()
async def shared(workspace, workspace_1) -> Shared:
    """A = ``workspace`` (testUser), B = ``workspace_1`` (testUser1). The form
    is created in B, then linked to A as well."""
    created = await container.workspace_form_service().create_form(
        workspace_1.id, StandardForm(**formData), testUser1
    )
    form_id = created.form_id
    await _make_v2(await container.form_repo().get_form_document_by_id(form_id))

    b_link = await container.workspace_form_repo().find_workspace_form(
        workspace_1.id, form_id
    )
    for key, value in B_TRUST.items():
        setattr(b_link.settings, key, value)
    await container.workspace_form_repo().save(b_link)

    await container.workspace_form_repo().save_workspace_form(
        workspace_id=workspace.id,
        form_id=form_id,
        user_id=testUser.id,
        workspace_form_settings=WorkspaceFormSettings(
            **A_TRUST,
            publish_checks_version=b_link.settings.publish_checks_version,
        ),
    )
    return Shared(
        workspace,
        workspace_1,
        form_id,
        await _settings(workspace.id, form_id),
        await _settings(workspace_1.id, form_id),
    )


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


def _ai(shared: Shared) -> str:
    return f"/api/v1/workspaces/{shared.a.id}/forms/{shared.form_id}/ai"


class TestSettingsOpsStayInTheCallersWorkspace:
    async def test_the_two_links_start_apart(self, shared: Shared):
        assert _trust_of(shared.b_before) == B_TRUST
        assert shared.a_before["purpose"] == A_TRUST["purpose"]

    async def test_ai_chat(
        self, client: AsyncClient, shared: Shared, test_user_cookies, fake_provider
    ):
        fake_provider.replies = [
            json.dumps({"reply": "Updated.", "ops": [SETTINGS_OP]}),
            json.dumps({"memories": []}),
        ]
        response = await client.post(
            _ai(shared) + "/chat",
            cookies=test_user_cookies,
            json={"message": "update the trust settings"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["results"][0]["ok"] is True
        # the answer carries A's settings, never B's
        assert body["settings"]["purpose"] == NEW_TRUST["purpose"]
        assert body["settings"]["retentionText"] == NEW_TRUST["retention_text"]
        await shared.assert_a_changed_b_kept()

    async def test_review_fix(
        self, client: AsyncClient, shared: Shared, test_user_cookies
    ):
        response = await client.post(
            _ai(shared) + "/review/apply",
            cookies=test_user_cookies,
            json={"ops": [SETTINGS_OP]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["settings"]["purpose"] == NEW_TRUST["purpose"]
        await shared.assert_a_changed_b_kept()

    async def test_proposal_preview_and_accept(
        self, client: AsyncClient, shared: Shared, test_user_cookies, fake_provider
    ):
        fake_provider.replies = [
            json.dumps({"reply": "Here you go.", "ops": [SETTINGS_OP]})
        ]
        response = await client.post(
            _ai(shared) + "/chat",
            cookies=test_user_cookies,
            json={"message": "update the trust settings", "mode": "propose"},
        )
        assert response.status_code == 200, response.text
        proposal = response.json()["proposal"]
        # the preview starts from A's settings, never B's
        assert _change(proposal["diff"], "/trust/purpose") == {
            "path": "/trust/purpose",
            "before": A_TRUST["purpose"],
            "after": NEW_TRUST["purpose"],
        }
        await shared.assert_nothing_stored()

        accepted = await client.post(
            _ai(shared) + f"/proposals/{proposal['id']}/accept",
            cookies=test_user_cookies,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["settings"]["purpose"] == NEW_TRUST["purpose"]
        await shared.assert_a_changed_b_kept()

    async def test_mcp_update_form(self, client: AsyncClient, shared: Shared):
        token = await _make_key(shared.a.id, ["forms:write"])
        result = _tool_text(
            await _call_tool(
                client,
                token,
                "update_form",
                {"form_id": shared.form_id, "ops": [SETTINGS_OP]},
            )
        )
        assert result["results"][0]["ok"] is True
        assert result["settings"]["purpose"] == NEW_TRUST["purpose"]
        await shared.assert_a_changed_b_kept()

    async def test_mcp_dry_run(self, client: AsyncClient, shared: Shared):
        token = await _make_key(shared.a.id, ["forms:write"])
        result = _tool_text(
            await _call_tool(
                client,
                token,
                "dry_run_ops",
                {"form_id": shared.form_id, "ops": [SETTINGS_OP]},
            )
        )
        trust = result["form"]["trust"]
        assert {k: trust.get(k) for k in NEW_TRUST_SPEC} == NEW_TRUST_SPEC
        await shared.assert_nothing_stored()

    async def test_public_api_ops(self, client: AsyncClient, shared: Shared):
        token = await _token(shared.a.id)
        response = await client.post(
            f"{BASE}/forms/{shared.form_id}/ops",
            json={"ops": [SETTINGS_OP]},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        trust = response.json()["form"]["trust"]
        assert {k: trust.get(k) for k in NEW_TRUST_SPEC} == NEW_TRUST_SPEC
        await shared.assert_a_changed_b_kept()

    async def test_public_api_ops_dry_run(self, client: AsyncClient, shared: Shared):
        token = await _token(shared.a.id)
        response = await client.post(
            f"{BASE}/forms/{shared.form_id}/ops/dry-run",
            json={"ops": [SETTINGS_OP]},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        trust = response.json()["form"]["trust"]
        assert {k: trust.get(k) for k in NEW_TRUST_SPEC} == NEW_TRUST_SPEC
        await shared.assert_nothing_stored()

    async def test_public_api_replace(self, client: AsyncClient, shared: Shared):
        token = await _token(shared.a.id)
        current = await client.get(
            f"{BASE}/forms/{shared.form_id}", headers=_auth(token)
        )
        assert current.status_code == 200, current.text
        assert current.json()["trust"]["purpose"] == A_TRUST["purpose"]
        spec = copy.deepcopy(current.json())
        spec["trust"] = {
            **(spec.get("trust") or {}),
            **NEW_TRUST_SPEC,
            "requireVerifiedIdentity": False,
            "allowEditingResponse": False,
            "showSubmissionNumber": False,
        }
        response = await client.put(
            f"{BASE}/forms/{shared.form_id}",
            json=spec,
            headers=_auth(token, **{"If-Match": current.headers["ETag"]}),
        )
        assert response.status_code == 200, response.text
        await shared.assert_a_changed_b_kept()

    async def test_session_dry_run(
        self, client: AsyncClient, shared: Shared, test_user_cookies
    ):
        response = await client.post(
            f"/api/v1/workspaces/{shared.a.id}/forms/{shared.form_id}/ops/dry-run",
            json={"ops": [SETTINGS_OP]},
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text
        trust = response.json()["form"]["trust"]
        assert {k: trust.get(k) for k in NEW_TRUST_SPEC} == NEW_TRUST_SPEC
        await shared.assert_nothing_stored()

    async def test_builder_ops_save(
        self, client: AsyncClient, shared: Shared, test_user_cookies, monkeypatch
    ):
        monkeypatch.setattr(app_settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", True)
        _, etag = await container.form_spec_writer().read(shared.a.id, shared.form_id)
        response = await client.post(
            f"/api/v1/workspaces/{shared.a.id}/forms/{shared.form_id}/ops",
            json={"ops": [SETTINGS_OP]},
            headers={"If-Match": etag, "Idempotency-Key": "settings-scope-1"},
            cookies=test_user_cookies,
        )
        assert response.status_code == 200, response.text
        await shared.assert_a_changed_b_kept()


class TestTheWorkspaceIsRequired:
    async def test_persist_ops_to_form_needs_the_workspace(self, shared: Shared):
        document = await container.form_repo().get_form_document_by_id(
            shared.form_id
        )
        with pytest.raises(TypeError):
            await chat_module.persist_ops_to_form(
                document,
                StandardForm(**document.model_dump()),
                parse_ops([SETTINGS_OP]),
            )
        await shared.assert_nothing_stored()

    async def test_the_settings_write_needs_the_workspace(self, shared: Shared):
        ops = parse_ops([SETTINGS_OP])
        results = [OpResult(index=0, op=ops[0].op, ok=True, message="")]
        with pytest.raises(TypeError):
            await chat_module._persist_settings_ops(shared.form_id, ops, results)
        with pytest.raises(ValueError):
            await chat_module._persist_settings_ops(
                shared.form_id, ops, results, workspace_id=None
            )
        await shared.assert_nothing_stored()

    async def test_a_workspace_without_the_form_writes_nothing(
        self, shared: Shared, workspace_pro
    ):
        ops = parse_ops([SETTINGS_OP])
        results = [OpResult(index=0, op=ops[0].op, ok=True, message="")]
        written = await chat_module._persist_settings_ops(
            shared.form_id, ops, results, workspace_id=workspace_pro.id
        )
        assert written is None
        await shared.assert_nothing_stored()
