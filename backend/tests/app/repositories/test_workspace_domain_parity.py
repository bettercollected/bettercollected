"""The Postgres twin of the workspace domain repository behaves like the Mongo
original, including the uniqueness rules both stores enforce. Skipped unless
DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.postgres.identity import (
    PostgresWorkspaceDomainRepository,
)
from backend.app.repositories.workspace_domain_repository import (
    DomainAlreadyClaimed,
    DomainVerifiedElsewhere,
    WorkspaceDomainRepository,
)
from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from tests.app.repositories.test_identity_parity import both_raise
from tests.app.repositories.test_refdata_parity import parity


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _at(hours_ago: float) -> dt.datetime:
    # millisecond precision: what Mongo stores
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return now - dt.timedelta(hours=hours_ago)


def claim(ws, domain, **extra):
    return WorkspaceDomainDocument(
        id=PydanticObjectId(),
        workspace_id=ws,
        domain=domain,
        verification_token=f"tok-{domain}",
        created_by="u1",
        **extra,
    )


def verified(ws, domain, checked_hours_ago):
    return claim(
        ws,
        domain,
        status=DomainStatus.VERIFIED,
        verified_domain=domain,
        verified_at=_at(100),
        last_checked_at=_at(checked_hours_ago),
    )


async def test_workspace_domains(sessions):
    ws, other = PydanticObjectId(), PydanticObjectId()
    acme = verified(ws, "acme.com", checked_hours_ago=30)
    beta = verified(ws, "beta.io", checked_hours_ago=48)
    fresh = verified(other, "fresh.org", checked_hours_ago=1)
    pending = claim(ws, "zeta.net")
    rival = claim(other, "acme.com")
    await parity(
        WorkspaceDomainRepository(),
        PostgresWorkspaceDomainRepository(sessions),
        [
            ("create", lambda: (pending,)),
            ("create", lambda: (acme,)),
            ("create", lambda: (beta,)),
            ("create", lambda: (fresh,)),
            ("create", lambda: (rival,)),
            ("get", lambda: (acme.id,)),
            ("get", lambda: (PydanticObjectId(),)),
            ("get", lambda: ("not-an-id",)),
            ("list_by_workspace", lambda: (ws,)),
            ("list_by_workspace", lambda: (PydanticObjectId(),)),
            ("count_by_workspace", lambda: (ws,)),
            ("find_verified", lambda: ("acme.com",)),
            ("find_verified", lambda: ("zeta.net",)),
            ("list_due_for_recheck", lambda: (_at(24), 10)),
            ("list_due_for_recheck", lambda: (_at(24), 1)),
            ("delete", lambda: (beta.id,)),
            ("list_by_workspace", lambda: (ws,)),
            ("delete_by_workspace_ids", lambda: ([other],)),
            ("find_verified", lambda: ("fresh.org",)),
            ("count_by_workspace", lambda: (other,)),
        ],
    )


async def test_uniqueness_is_enforced_by_both_stores(sessions):
    mongo, postgres = (
        WorkspaceDomainRepository(),
        PostgresWorkspaceDomainRepository(sessions),
    )
    ws, other = PydanticObjectId(), PydanticObjectId()
    holder = verified(ws, "acme.com", 1)
    for repo in (mongo, postgres):
        await repo.create(holder)

    # a second claim of the same domain in the same workspace
    await both_raise(
        DomainAlreadyClaimed,
        lambda: mongo.create(claim(ws, "acme.com")),
        lambda: postgres.create(claim(ws, "acme.com")),
    )

    # another workspace may hold a claim, but cannot store it as verified
    rival = claim(other, "acme.com")
    for repo in (mongo, postgres):
        await repo.create(rival)
    rival.status = DomainStatus.VERIFIED
    rival.verified_domain = "acme.com"
    await both_raise(
        DomainVerifiedElsewhere,
        lambda: mongo.save(rival),
        lambda: postgres.save(rival),
    )
    for repo in (mongo, postgres):
        stored = await repo.get(rival.id)
        assert stored.verified_domain is None
        assert (await repo.find_verified("acme.com")).workspace_id == ws

    # once the holder lets go, the other workspace's verification goes through
    for repo in (mongo, postgres):
        await repo.delete(holder.id)
        await repo.save(rival)
        assert (await repo.find_verified("acme.com")).workspace_id == other
