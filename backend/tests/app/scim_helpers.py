"""Stand-ins for SCIM directory sync tests: Polis's dsync admin API, and a
signed webhook delivery as Polis makes it (npm/src/event/webhook.ts)."""

import json
import time
from typing import Dict, List, Optional

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.scim.signature import sign
from backend.app.services.sso.polis_client import PolisError
from backend.config import settings
from tests.app.controllers.data import invited_user, testUser
from tests.app.sso_helpers import DOMAIN, sso_on, verify_domain  # noqa: F401

WEBHOOK_BASE = "http://backend:8000/api/v1/scim/webhook"
PRODUCT = "bettercollected"


class FakePolisDirectory:
    def __init__(self):
        self.calls: List[tuple] = []
        self.directories: Dict[str, dict] = {}
        self.fail: Optional[PolisError] = None
        # only deleting a directory fails (a rotation's clean-up)
        self.fail_delete: Optional[PolisError] = None
        self._n = 0
        # what a resync lists: Polis users, groups and members per group
        self.users: List[dict] = []
        self.groups: List[dict] = []
        self.members: Dict[str, List[str]] = {}

    async def create_directory(self, tenant, name, directory_type, url, secret):
        if self.fail:
            raise self.fail
        self._n += 1
        directory_id = f"dir-{self._n}"
        self.calls.append(("create", tenant, name, directory_type, url))
        self.directories[directory_id] = {
            "id": directory_id,
            "tenant": tenant,
            "webhook_url": url,
            "webhook_secret": secret,
        }
        return {
            "id": directory_id,
            "tenant": tenant,
            "product": PRODUCT,
            "type": directory_type,
            "scim": {
                "path": f"/api/scim/v2.0/{directory_id}",
                "endpoint": f"https://polis.test/api/scim/v2.0/{directory_id}",
                "secret": f"bearer-token-{self._n}",
            },
            "webhook": {"endpoint": url, "secret": secret},
        }

    async def delete_directory(self, directory_id):
        if self.fail or self.fail_delete:
            raise self.fail or self.fail_delete
        self.calls.append(("delete", directory_id))
        self.directories.pop(directory_id, None)

    async def list_users(self, tenant, directory_id, page_size=100):
        if self.fail:
            raise self.fail
        return list(self.users)

    async def list_groups(self, tenant, directory_id, page_size=100):
        if self.fail:
            raise self.fail
        return list(self.groups)

    async def list_group_members(self, tenant, directory_id, group_id, page_size=100):
        return list(self.members.get(group_id, []))

    def secret(self, directory_id: str) -> str:
        return self.directories[directory_id]["webhook_secret"]


@pytest.fixture
def scim_on(sso_on, monkeypatch):
    polis_sso, auth = sso_on
    monkeypatch.setattr(settings.scim, "WEBHOOK_URL", WEBHOOK_BASE)
    polis = FakePolisDirectory()
    monkeypatch.setattr(container.scim_directory_service(), "_polis", polis)
    monkeypatch.setattr(container.scim_sync_service(), "_http", auth)
    for user in (testUser, invited_user):
        auth.add_account(user.sub, user_id=user.id)
    return polis, auth


@pytest.fixture
def members_list(scim_on, monkeypatch):
    """The members list asks the stand-in auth for names and emails."""
    _, auth = scim_on
    monkeypatch.setattr(container.workspace_members_service(), "http_client", auth)


def user_data(polis_id: str, email: str, active: bool = True, **extra) -> dict:
    return {
        "id": polis_id,
        "first_name": "Jane",
        "last_name": "Doe",
        "email": email,
        "active": active,
        "raw": {"userName": email},
        **extra,
    }


def group_data(polis_id: str, name: str) -> dict:
    return {"id": polis_id, "name": name, "raw": {"displayName": name}}


def event(directory, kind: str, data: dict, **overrides) -> dict:
    return {
        "event": kind,
        "tenant": directory.polis_tenant,
        "product": directory.polis_product,
        "directory_id": directory.polis_directory_id,
        "data": data,
        **overrides,
    }


def signed(body: bytes, secret: str, at_ms: Optional[int] = None) -> dict:
    at_ms = int(time.time() * 1000) if at_ms is None else at_ms
    return {
        "Content-Type": "application/json",
        "BoxyHQ-Signature": sign(secret, body, at_ms),
    }


async def deliver(client, directory, polis: FakePolisDirectory, payload, **kwargs):
    """POST ``payload`` to the directory's webhook, signed like Polis."""
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed(body, polis.secret(directory.polis_directory_id), **kwargs)
    return await client.post(
        f"/api/v1/scim/webhook/{directory.id}", content=body, headers=headers
    )


async def create_directory(client, workspace, cookies, polis=None):
    """Through the API, as the owner: (directory document, the reply)."""
    await verify_domain(workspace.id)
    reply = await client.post(
        f"/api/v1/workspaces/{workspace.id}/scim/directory",
        json={"type": "okta-scim-v2"},
        cookies=cookies,
    )
    assert reply.status_code == 201, reply.text
    directory = await container.scim_directory_repo().find_by_workspace(workspace.id)
    return directory, reply


async def member_of(workspace_id, user_id) -> Optional[WorkspaceUserDocument]:
    return await container.workspace_user_repo().find_workspace_user(
        PydanticObjectId(workspace_id), PydanticObjectId(user_id)
    )
