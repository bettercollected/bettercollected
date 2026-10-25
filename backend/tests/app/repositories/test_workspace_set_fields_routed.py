"""``set_fields`` of workspaces through the routed repository under ``dual``
(Mongo primary): a workspace whose Postgres copy is missing gets it back from
the primary, instead of the gap staying unnoticed until ``verify``. Drives a
Mongo server; skipped unless DATABASE_URL points at a *_test database."""

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.db.models import WorkspaceRow
from common.db import RoutingRepository, load_flags


@pytest.fixture
def repo(clean_postgres):
    return RoutingRepository(
        group="identity",
        flags=load_flags({"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"}),
        mongo=WorkspaceRepository(),
        postgres=PostgresWorkspaceRepository(
            container.pg_sessionmaker(), ActionRepository(crypto=None)
        ),
        on_mirror_failure=container.outbox_recorder(),
    )


async def postgres_copy(workspace_id):
    async with container.pg_sessionmaker()() as session:
        return (
            await session.execute(
                select(WorkspaceRow.doc).where(WorkspaceRow.id == str(workspace_id))
            )
        ).scalar_one_or_none()


async def test_a_missing_postgres_copy_is_converged_from_the_primary(repo):
    name = f"mu-{PydanticObjectId()}"
    workspace = WorkspaceDocument(
        id=PydanticObjectId(), title=name, workspace_name=name, owner_id="o"
    )
    await workspace.save()  # Mongo only: the Postgres copy is missing
    assert await postgres_copy(workspace.id) is None

    await repo.set_fields(workspace, {"sso_required": True})

    doc = await postgres_copy(workspace.id)
    assert doc is not None
    assert doc["sso_required"] is True and doc["workspace_name"] == name
