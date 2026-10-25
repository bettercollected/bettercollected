"""``set_fields`` of the workspaces' Postgres twin changes only the named
fields, under a row lock, like Mongo's partial ``$set``. The twin is the
primary from ``postgres_primary_dual`` on: a whole-document save from a stale
copy would lose a concurrent change (AI consent coming back on, required
single sign-on switching off). Skipped unless DATABASE_URL points at a
*_test database."""

import asyncio

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.workspace import WorkspaceDocument


@pytest.fixture
def repo(clean_postgres):
    return PostgresWorkspaceRepository(
        container.pg_sessionmaker(), ActionRepository(crypto=None)
    )


def workspace(name, **extra):
    return WorkspaceDocument(
        id=PydanticObjectId(), title=name, workspace_name=name, owner_id="o", **extra
    )


async def test_set_fields_on_stale_copies_keeps_both_changes(repo):
    ws = workspace("iota", ai_enabled=False, sso_required=False)
    await repo.save(ws)
    consent = await repo.find_by_id(ws.id)
    sso = await repo.find_by_id(ws.id)
    await repo.set_fields(consent, {"ai_enabled": True, "ai_enabled_by": "admin"})
    await repo.set_fields(sso, {"sso_required": True})
    stored = await repo.find_by_id(ws.id)
    assert stored.ai_enabled is True and stored.ai_enabled_by == "admin"
    assert stored.sso_required is True
    # each copy gets the fields it set
    assert consent.ai_enabled is True and sso.sso_required is True


async def test_concurrent_set_fields_lose_no_write(repo):
    ws = workspace("kappa")
    await repo.save(ws)
    copies = [await repo.find_by_id(ws.id) for _ in range(5)]
    fields = [
        {"ai_enabled": True},
        {"sso_required": True},
        {"sso_default_role": "VIEWER"},
        {"custom_domain_verified": True},
        {"title": "Kappa"},
    ]
    await asyncio.gather(*(repo.set_fields(c, f) for c, f in zip(copies, fields)))
    stored = await repo.find_by_id(ws.id)
    for change in fields:
        for name, value in change.items():
            assert getattr(stored, name) == value, name


async def test_a_workspace_not_stored_stays_so(repo):
    ws = workspace("lambda")
    await repo.set_fields(ws, {"sso_required": True})
    assert ws.sso_required is True
    assert await repo.find_by_id(ws.id) is None
