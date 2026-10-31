"""Who may do what with email actions, for every workspace role (the permission
matrix of docs/enterprise-access-model.md, restricted to these endpoints):

- the actions themselves, their questions, the preview and the test mail:
  workspace.manage (owners and admins) - they send answers to people;
- the delivery log: form.edit or audit.read (editors, admins, owners and the
  privacy officer, who never reads answers);
- the status read: any member.
An action, form or workspace that is not the caller's is not there (404)."""

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
from tests.app.email_actions.helpers import EN, NL, make_action
from tests.app.registration.helpers import publish

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
TEMPLATE = {"subject": "Hi {{name}}", "body": "{{answers}}"}
NEW = {"json": {"name": "New", "en": TEMPLATE, "nl": TEMPLATE, "fields": [{"source": "name"}], "teamRecipients": ["owner@acme.example"]}}
PREVIEW = {"json": {"language": "en", "subject": "Hi", "body": "b", "fields": []}}

CASES = [
    Case("status", "GET", W + "/email-actions/status", None),
    Case("list", "GET", F + "/email-actions", MANAGE),
    Case("variables", "GET", F + "/email-actions/variables", MANAGE),
    Case("create", "POST", F + "/email-actions", MANAGE, lambda c: NEW, ok=201),
    Case("update", "PATCH", F + "/email-actions/{action}", MANAGE, lambda c: {"json": {"enabled": False}}),
    Case("preview", "POST", F + "/email-actions/preview", MANAGE, lambda c: PREVIEW),
    Case("test", "POST", F + "/email-actions/{action}/test", MANAGE),
    Case("delete", "DELETE", F + "/email-actions/{spare}", MANAGE, ok=204),
    Case("deliveries", "GET", F + "/email-actions/deliveries", STAFF),
    Case("update.other", "PATCH", F + "/email-actions/{other_action}", MANAGE, lambda c: {"json": {"enabled": False}}, ok=404),
    Case("delete.other", "DELETE", F + "/email-actions/{other_action}", MANAGE, ok=404),
    Case("test.other", "POST", F + "/email-actions/{other_action}/test", MANAGE, ok=404),
    Case("list.other_form", "GET", W + "/forms/{other_form}/email-actions", MANAGE, ok=404),
    Case("deliveries.other_form", "GET", W + "/forms/{other_form}/email-actions/deliveries", STAFF, ok=404),
]


@pytest.fixture()
async def actions(workspace, workspace_1, emails_on, transport, memory_jobs):
    members = container.workspace_user_repo()
    for user, roles, disabled in SEEDED_MEMBERSHIPS:
        await members.save(
            WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=roles, disabled=disabled)
        )
    form = await publish(workspace)
    other_form = await publish(workspace_1, user=testUser1)
    action = await make_action(workspace, form)
    spare = await make_action(workspace, form, fields=["name"])
    other = await make_action(workspace_1, other_form, team=["outsider@elsewhere.example"], user=testUser1)
    return {
        "ws": str(workspace.id),
        "form": form.form_id,
        "other_form": other_form.form_id,
        "action": action.id,
        "spare": spare.id,
        "other_action": other.id,
    }


def allowed(case: Case, role: str) -> bool:
    if case.roles is None:
        return role in ROLES_WITH[P.FORM_READ]
    return role in case.roles


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_email_action_permissions(client: AsyncClient, actions, case: Case, role: str):
    response = await client.request(
        case.method, case.path.format(**actions), cookies=_cookies(USERS[role]), **case.request(actions)
    )
    seen = f"{case.name} as {role}: {response.status_code} {response.text[:200]}"
    if allowed(case, role):
        assert response.status_code == case.ok, seen
    else:
        assert response.status_code == 403, seen


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", [c for c in CASES if c.name in ("create", "test")], ids=lambda c: c.name)
async def test_switch_off_answers_422_to_create_and_test(client: AsyncClient, actions, monkeypatch, case: Case, role: str):
    monkeypatch.setattr(settings.email_actions, "ENABLED", False)
    response = await client.request(
        case.method, case.path.format(**actions), cookies=_cookies(USERS[role]), **case.request(actions)
    )
    if role in MANAGE:
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "email_actions_off"
    else:
        assert response.status_code == 403


async def test_status_over_http_says_whether_a_mail_server_is_set_up(client: AsyncClient, actions, monkeypatch):
    cookies = _cookies(testUser)
    path = (W + "/email-actions/status").format(**actions)
    assert (await client.get(path, cookies=cookies)).json() == {"enabled": True, "configured": True}
    monkeypatch.setattr(settings.mail_settings, "sender", "")
    assert (await client.get(path, cookies=cookies)).json() == {"enabled": True, "configured": False}


async def test_a_test_mail_over_http_goes_to_the_caller_only(client: AsyncClient, actions, transport):
    response = await client.post(
        (F + "/email-actions/{action}/test").format(**actions), cookies=_cookies(testUser)
    )
    assert response.status_code == 200 and response.json()["status"] == "delivered"
    assert [m["recipients"] for m in transport.sent] == [["test@email.com"]]
    assert "@" not in response.text.replace("test@email.com", "")
