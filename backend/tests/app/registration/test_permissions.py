"""Who may do what with registration, for every workspace role (the permission
matrix of docs/enterprise-access-model.md, restricted to these endpoints):

- services, the choice of destination and variables: workspace.manage
  (owners and admins);
- reading a form's registration: form.read; delivery list: response.read;
- retrying a failed delivery: form.edit (editors too);
- the status read: any member.
Switch off: everything but the status answers 410 whatever the role."""

from dataclasses import dataclass
from typing import Callable, Optional

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.registration import DeliveryStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.config import settings
from tests.app.controllers.data import testUser1
from tests.app.controllers.test_permission_matrix import (
    ROLES,
    ROLES_WITH,
    SEEDED_MEMBERSHIPS,
    USERS,
    _body,
    _cookies,
)
from tests.app.registration.helpers import configure, make_service, publish, submit

pytestmark = pytest.mark.asyncio
P = Permission


@dataclass(frozen=True)
class Case:
    name: str
    method: str
    path: str
    permission: Optional[Permission]  # None: any member
    request: Callable[[dict], dict] = lambda c: {}
    ok: Optional[int] = None


W = "/api/v1/workspaces/{ws}"
F = W + "/forms/{form}"
SERVICE_BODY = {
    "name": "Created",
    "baseUrl": "https://case.example.org/",
    "auth": "none",
}

CASES = [
    Case("status", "GET", W + "/registration/status", None, ok=200),
    Case(
        "services.list", "GET", W + "/registration/services", P.WORKSPACE_MANAGE, ok=200
    ),
    Case(
        "services.create",
        "POST",
        W + "/registration/services",
        P.WORKSPACE_MANAGE,
        lambda c: {"json": SERVICE_BODY},
        ok=201,
    ),
    Case(
        "services.update",
        "PATCH",
        W + "/registration/services/{service}",
        P.WORKSPACE_MANAGE,
        lambda c: {"json": {"name": "Renamed"}},
        ok=200,
    ),
    Case(
        "services.test",
        "POST",
        W + "/registration/services/{service}/test",
        P.WORKSPACE_MANAGE,
        ok=200,
    ),
    Case(
        "services.delete",
        "DELETE",
        W + "/registration/services/{spare}",
        P.WORKSPACE_MANAGE,
        ok=204,
    ),
    Case("form.get", "GET", F + "/registration", P.FORM_READ, ok=200),
    Case(
        "form.put",
        "PUT",
        F + "/registration",
        P.WORKSPACE_MANAGE,
        lambda c: {
            "json": {
                "enabled": True,
                "serviceId": c["service"],
                "path": "x",
                "variables": [{"source": "name"}],
            }
        },
        ok=200,
    ),
    # a save that switches it off needs the same permission as one that switches it on
    Case(
        "form.put.off",
        "PUT",
        F + "/registration",
        P.WORKSPACE_MANAGE,
        lambda c: {
            "json": {
                "enabled": False,
                "serviceId": c["service"],
                "path": "x",
                "variables": [{"source": "name"}],
            }
        },
        ok=200,
    ),
    Case(
        "form.variables",
        "GET",
        F + "/registration/variables",
        P.WORKSPACE_MANAGE,
        ok=200,
    ),
    Case("form.check", "POST", F + "/registration/test", P.WORKSPACE_MANAGE, ok=200),
    Case(
        "deliveries.list",
        "GET",
        F + "/registration/deliveries",
        P.RESPONSE_READ,
        ok=200,
    ),
    Case(
        "deliveries.retry",
        "POST",
        F + "/registration/deliveries/{delivery}/retry",
        P.FORM_EDIT,
        ok=200,
    ),
    # a delivery or service of another workspace is simply not there
    Case(
        "deliveries.retry.other",
        "POST",
        F + "/registration/deliveries/{other_delivery}/retry",
        P.FORM_EDIT,
        ok=404,
    ),
    Case(
        "services.update.other",
        "PATCH",
        W + "/registration/services/{other_service}",
        P.WORKSPACE_MANAGE,
        lambda c: {"json": {"name": "Hijack"}},
        ok=404,
    ),
    Case(
        "services.delete.other",
        "DELETE",
        W + "/registration/services/{other_service}",
        P.WORKSPACE_MANAGE,
        ok=404,
    ),
    Case(
        "services.test.other",
        "POST",
        W + "/registration/services/{other_service}/test",
        P.WORKSPACE_MANAGE,
        ok=404,
    ),
]


@pytest.fixture()
async def reg(workspace, workspace_1, registration_on, memory_jobs, tls):
    members = container.workspace_user_repo()
    for user, roles, disabled in SEEDED_MEMBERSHIPS:
        await members.save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=user.id,
                roles=roles,
                disabled=disabled,
            )
        )
    form = await publish(workspace)
    service = await make_service(workspace)
    spare = await make_service(workspace, name="Spare", auth="none")
    other_service = await make_service(
        workspace_1,
        user=testUser1,
        name="Foreign",
    )
    await configure(workspace, form, service, ["name"])
    response = await submit(workspace, form)
    rows = await container.registration_delivery_repo().many()
    delivery = rows[0]
    delivery.status = DeliveryStatus.FAILED
    await container.registration_delivery_repo().save(delivery)
    other = delivery.model_copy(deep=True)
    other.id = None
    other.ensure_id()
    other.workspace_id = workspace_1.id
    other.response_id = "someone-elses"
    await container.registration_delivery_repo().upsert(other)
    return {
        "ws": str(workspace.id),
        "form": form.form_id,
        "service": str(service.id),
        "spare": str(spare.id),
        "other_service": str(other_service.id),
        "delivery": str(delivery.id),
        "other_delivery": str(other.id),
    }


def allowed(case: Case, role: str) -> bool:
    if case.permission is None:
        return role in ROLES_WITH[P.FORM_READ]
    return role in ROLES_WITH[case.permission]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_registration_permissions(
    client: AsyncClient, reg, case: Case, role: str
):
    response = await client.request(
        case.method,
        case.path.format(**reg),
        cookies=_cookies(USERS[role]),
        **case.request(reg),
    )
    seen = f"{case.name} as {role}: {response.status_code} {response.text}"
    if allowed(case, role):
        assert response.status_code == case.ok, seen
    else:
        assert response.status_code in (403, 404), seen
        assert response.status_code == 403, seen


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_switch_off_answers_410_for_everyone_but_the_status(
    client: AsyncClient, reg, monkeypatch, case: Case, role: str
):
    monkeypatch.setattr(settings.registration, "REGISTRATION", "off")
    response = await client.request(
        case.method,
        case.path.format(**reg),
        cookies=_cookies(USERS[role]),
        **case.request(reg),
    )
    seen = f"{case.name} as {role}: {response.status_code} {response.text}"
    if case.name == "status":
        if allowed(case, role):
            assert response.status_code == 200 and response.json() == {
                "enabled": False
            }, seen
        return
    if allowed(case, role):
        assert (
            response.status_code == 410
            and _body(response)["code"] == "registration_off"
        ), seen
    else:
        # refused roles are refused or told the feature is off, never let through
        assert response.status_code in (403, 410), seen
