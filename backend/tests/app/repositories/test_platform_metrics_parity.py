"""The platform-metrics counts agree between each Mongo repository and its
Postgres twin, and count what the dashboard says they count.

Workspaces and forms are dated by ObjectId, responses by ``created_at``.
Skipped unless DATABASE_URL points at a *_test database.
"""

import datetime as dt
import os

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from tests.app.repositories.test_refdata_parity import parity

NOW = dt.datetime(2026, 3, 18, 12, 0, tzinfo=dt.timezone.utc)  # a Wednesday
WEEKS = [dt.datetime(2026, 3, d, tzinfo=dt.timezone.utc) for d in (2, 9, 16, 23)]


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def days_ago(days: float) -> dt.datetime:
    return NOW - dt.timedelta(days=days)


def minted_at(moment: dt.datetime) -> PydanticObjectId:
    """An ObjectId created at ``moment`` (random tail, so ids never collide)."""
    stamp = PydanticObjectId.from_datetime(moment).binary[:4]
    return PydanticObjectId(stamp + os.urandom(8))


async def seed(repositories, method, *documents):
    for repository in repositories:
        for document in documents:
            await getattr(repository, method)(document)


async def test_workspace_counts(sessions):
    mongo = WorkspaceRepository()
    postgres = PostgresWorkspaceRepository(sessions, ActionRepository(crypto=None))
    owner = str(PydanticObjectId())

    def workspace(name, created, **extra):
        return WorkspaceDocument(
            id=minted_at(created), workspace_name=name, owner_id=owner, **extra
        )

    await seed(
        (mongo, postgres),
        "save",
        workspace("old", days_ago(40)),
        workspace("week-one", WEEKS[0]),  # exactly on a boundary
        workspace("week-two", days_ago(5), disabled=True),
        workspace("today", days_ago(0.5), disabled=False),
    )
    await parity(
        mongo,
        postgres,
        [
            ("count_workspaces", lambda: ()),
            ("count_workspaces", lambda: (days_ago(30),)),
            ("count_disabled_workspaces", lambda: ()),
            ("count_workspaces_created_per_period", lambda: (WEEKS,)),
            ("count_workspaces_created_per_period", lambda: (WEEKS[:1],)),
        ],
    )
    for repository in (mongo, postgres):
        assert await repository.count_workspaces() == 4
        assert await repository.count_workspaces(days_ago(30)) == 3
        assert await repository.count_disabled_workspaces() == 1
        # 2–9 March holds the boundary one; 9–16 March the one 5 days back
        # (13 March); 16–23 March the one from this morning.
        assert await repository.count_workspaces_created_per_period(WEEKS) == [1, 1, 1]
        assert await repository.count_workspaces_created_per_period(WEEKS[:1]) == []


async def test_workspace_form_counts(sessions):
    mongo = WorkspaceFormRepository()
    postgres = PostgresWorkspaceFormRepository(sessions, None)
    workspace_id = PydanticObjectId()

    def workspace_form(form_id, user_id, created, provider):
        settings = (
            None if provider is None else WorkspaceFormSettings(provider=provider)
        )
        return WorkspaceFormDocument(
            id=minted_at(created),
            workspace_id=workspace_id,
            form_id=form_id,
            user_id=user_id,
            settings=settings,
        )

    await seed(
        (mongo, postgres),
        "save",
        workspace_form("f1", "alice", days_ago(60), "self"),
        workspace_form("f2", "alice", days_ago(2), "google"),
        workspace_form("f3", "bob", days_ago(10), "self"),
        workspace_form("f4", "carol", days_ago(45), None),
    )
    # f1 is published twice, f3 once; f2 and f4 never
    for repository in (FormRepository(), PostgresFormRepository(sessions, None, None)):
        for form_id, version in (("f1", 1), ("f1", 2), ("f3", 1)):
            await repository.save_form_version(
                FormVersionsDocument(form_id=form_id, version=version, title=form_id)
            )
    await parity(
        mongo,
        postgres,
        [
            ("count_workspace_forms", lambda: ()),
            ("count_workspace_forms", lambda: (days_ago(30),)),
            ("count_published_workspace_forms", lambda: ()),
            ("count_workspace_forms_by_provider", lambda: ()),
            ("count_form_creators", lambda: ()),
            ("count_form_creators", lambda: (days_ago(30),)),
            ("count_workspace_forms_created_per_period", lambda: (WEEKS,)),
        ],
    )
    for repository in (mongo, postgres):
        assert await repository.count_workspace_forms() == 4
        assert await repository.count_workspace_forms(days_ago(30)) == 2
        assert await repository.count_published_workspace_forms() == 2
        assert await repository.count_workspace_forms_by_provider() == {
            "self": 2,
            "google": 1,
            None: 1,
        }
        assert await repository.count_form_creators() == 3
        assert await repository.count_form_creators(days_ago(30)) == 2  # alice, bob
        assert await repository.count_workspace_forms_created_per_period(WEEKS) == [
            1,  # 8 March (f3)
            0,
            1,  # 16 March (f2)
        ]


async def test_response_counts(sessions):
    mongo = FormResponseRepository(crypto=container.crypto())
    postgres = PostgresFormResponseRepository(
        sessions, FormRepository(), WorkspaceFormRepository()
    )

    def response(response_id, submitted, **extra):
        return FormResponseDocument(
            id=PydanticObjectId(),  # minted now: imports keep the submission time
            form_id="f1",
            response_id=response_id,
            created_at=submitted,
            **extra,
        )

    await seed(
        (mongo, postgres),
        "save",
        response("r1", days_ago(1), answers={}, dataOwnerIdentifier="a@example.com"),
        response("r2", days_ago(3), answers={}, dataOwnerIdentifier="a@example.com"),
        response("r3", days_ago(12), answers={}, dataOwnerIdentifier="b@example.com"),
        response("r4", days_ago(20), answers={}),  # anonymous
        response("r5", days_ago(90), answers={}, dataOwnerIdentifier=""),  # anonymous
        response("r6", WEEKS[1], answers={}),  # on a boundary, anonymous
        response(
            "r8",
            NOW.replace(tzinfo=None) - dt.timedelta(hours=1),  # naive: UTC
            answers={},
            dataOwnerIdentifier="c@example.com",
        ),
    )
    await parity(
        mongo,
        postgres,
        [
            ("count_responses", lambda: ()),
            ("count_responses", lambda: (days_ago(7),)),
            ("count_responses", lambda: (days_ago(30),)),
            ("count_anonymous_responses", lambda: ()),
            ("count_identified_responders", lambda: ()),
            ("count_responses_per_period", lambda: (WEEKS,)),
        ],
    )
    for repository in (mongo, postgres):
        assert await repository.count_responses() == 7
        assert await repository.count_responses(days_ago(7)) == 3  # r1 r2 r8
        assert await repository.count_responses(days_ago(30)) == 6
        assert await repository.count_anonymous_responses() == 3
        assert await repository.count_identified_responders() == 3  # a, b, c
        assert await repository.count_responses_per_period(WEEKS) == [
            1,  # 6 March (r3)
            2,  # r6 on 9 March, r2 on 15 March
            2,  # r1 and r8
        ]
