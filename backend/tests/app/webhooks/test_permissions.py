"""Who may do what with webhooks, for every workspace role (the permission
matrix of docs/enterprise-access-model.md, restricted to these endpoints):

- the webhooks themselves, their questions, the secret, the test event:
  workspace.manage (owners and admins) - they send answers to a third party;
- the delivery log and the change history: form.edit or audit.read (editors,
  admins, owners and the privacy officer, who never reads answers);
- the status read: any member.
A webhook, form or workspace that is not the caller's is not there (404)."""

from dataclasses import dataclass
from typing import Callable, Optional

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import (
    ROLES,
    ROLES_WITH,
    SEEDED_MEMBERSHIPS,
    USERS,
    _cookies,
)
from tests.app.registration.helpers import publish
from tests.app.webhooks.helpers import make_webhook

pytestmark = pytest.mark.asyncio
P = Permission


@dataclass(frozen=True)
class Case:
    name: str
    method: str
    path: str
    roles: Optional[frozenset]  # None: any member
    request: Callable[[dict], dict] = lambda c: {}
    ok: int = 200


W = "/api/v1/workspaces/{ws}"
F = W + "/forms/{form}"
MANAGE = ROLES_WITH[P.WORKSPACE_MANAGE]
STAFF = ROLES_WITH[P.FORM_EDIT] | ROLES_WITH[P.AUDIT_READ]
NEW = {"json": {"url": "https://case.example.org/new", "fields": [{"source": "name"}]}}

CASES = [
    Case("status", "GET", W + "/webhooks/status", None),
    Case("list", "GET", F + "/webhooks", MANAGE),
    Case("variables", "GET", F + "/webhooks/variables", MANAGE),
    Case("create", "POST", F + "/webhooks", MANAGE, lambda c: NEW, ok=201),
    Case("update", "PATCH", F + "/webhooks/{hook}", MANAGE, lambda c: {"json": {"enabled": False}}),
    Case("rotate", "POST", F + "/webhooks/{hook}/rotate-secret", MANAGE),
    Case("test", "POST", F + "/webhooks/{hook}/test", MANAGE),
    Case("delete", "DELETE", F + "/webhooks/{spare}", MANAGE, ok=204),
    Case("deliveries", "GET", F + "/webhooks/deliveries", STAFF),
    Case("audit", "GET", F + "/webhooks/audit", STAFF),
    # another workspace's webhook, or a form that is not this workspace's
    Case("update.other", "PATCH", F + "/webhooks/{other_hook}", MANAGE, lambda c: {"json": {"enabled": False}}, ok=404),
    Case("delete.other", "DELETE", F + "/webhooks/{other_hook}", MANAGE, ok=404),
    Case("rotate.other", "POST", F + "/webhooks/{other_hook}/rotate-secret", MANAGE, ok=404),
    Case("test.other", "POST", F + "/webhooks/{other_hook}/test", MANAGE, ok=404),
    Case("list.other_form", "GET", W + "/forms/{other_form}/webhooks", MANAGE, ok=404),
    Case("deliveries.other_form", "GET", W + "/forms/{other_form}/webhooks/deliveries", STAFF, ok=404),
]


@pytest.fixture()
async def hooks(workspace, workspace_1, webhooks_on, public_dns, memory_jobs, tls):
    members = container.workspace_user_repo()
    for user, roles, disabled in SEEDED_MEMBERSHIPS:
        await members.save(
            WorkspaceUserDocument(
                workspace_id=workspace.id, user_id=user.id, roles=roles, disabled=disabled
            )
        )
    form = await publish(workspace)
    other_form = await publish(workspace_1, user=testUser1)
    hook = await make_webhook(workspace, form)
    spare = await make_webhook(workspace, form, ["name"])
    other_hook = await make_webhook(workspace_1, other_form, user=testUser1)
    return {
        "ws": str(workspace.id),
        "form": form.form_id,
        "other_form": other_form.form_id,
        "hook": hook.id,
        "spare": spare.id,
        "other_hook": other_hook.id,
    }


def allowed(case: Case, role: str) -> bool:
    if case.roles is None:
        return role in ROLES_WITH[P.FORM_READ]
    return role in case.roles


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_webhook_permissions(client: AsyncClient, hooks, case: Case, role: str):
    response = await client.request(
        case.method,
        case.path.format(**hooks),
        cookies=_cookies(USERS[role]),
        **case.request(hooks),
    )
    seen = f"{case.name} as {role}: {response.status_code} {response.text[:200]}"
    if allowed(case, role):
        assert response.status_code == case.ok, seen
    else:
        # a refusal is 403 for everyone who is not allowed in, whatever the object
        assert response.status_code == 403, seen


@pytest.mark.parametrize("role", sorted(MANAGE))
async def test_no_response_but_the_create_and_rotate_carries_a_secret(client: AsyncClient, hooks, role):
    cookies = _cookies(USERS[role])
    for method, path in [
        ("GET", F + "/webhooks"),
        ("GET", F + "/webhooks/deliveries"),
        ("GET", F + "/webhooks/audit"),
        ("GET", F + "/webhooks/variables"),
        ("PATCH", F + "/webhooks/{hook}"),
    ]:
        kwargs = {"json": {"enabled": True}} if method == "PATCH" else {}
        response = await client.request(method, path.format(**hooks), cookies=cookies, **kwargs)
        assert response.status_code == 200
        assert "whsec_" not in response.text and "secret\"" not in response.text.lower().replace("hassecret", "")
    created = await client.post(
        (F + "/webhooks").format(**hooks), cookies=cookies, **NEW
    )
    assert created.status_code == 201 and created.json()["secret"].startswith("whsec_")
    rotated = await client.post(
        (F + "/webhooks/{hook}/rotate-secret").format(**hooks), cookies=cookies
    )
    assert rotated.json()["secret"].startswith("whsec_")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    "case",
    [c for c in CASES if c.name in ("create", "test")],
    ids=lambda c: c.name,
)
async def test_switch_off_answers_422_to_create_and_test(
    client: AsyncClient, hooks, monkeypatch, case: Case, role: str
):
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    response = await client.request(
        case.method, case.path.format(**hooks), cookies=_cookies(USERS[role]), **case.request(hooks)
    )
    if role in MANAGE:
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "webhooks_off"
    else:
        assert response.status_code == 403
    assert (await container.action_log_repo().count()) == 0


async def test_enabling_over_http_answers_422_while_off_and_disabling_works(
    client: AsyncClient, hooks, monkeypatch
):
    cookies = _cookies(testUser)
    path = (F + "/webhooks/{hook}").format(**hooks)
    off = await client.patch(path, cookies=cookies, json={"enabled": False})
    assert off.status_code == 200 and off.json()["enabled"] is False
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    on = await client.patch(path, cookies=cookies, json={"enabled": True})
    assert on.status_code == 422 and on.json()["code"] == "webhooks_off"
    again = await client.patch(path, cookies=cookies, json={"enabled": False})
    assert again.status_code == 200
    status = await client.get((W + "/webhooks/status").format(**hooks), cookies=cookies)
    assert status.json() == {"enabled": False}
