"""Every Postgres twin exposes at least the public surface of its Mongo original.

The RoutingRepository dispatches by attribute name, so a method missing on
the twin would surface as a mirror failure (or an AttributeError when the
group is served from Postgres). No database needed.
"""

import inspect

import pytest

from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.template import FormTemplateRepository
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
)
from common.db import is_write_op

# The groups served from Postgres only (backend.db.groups.POSTGRES_ONLY_GROUPS)
# have no Mongo original left.
PAIRS = [
    (FormRepository, PostgresFormRepository),
    (WorkspaceFormRepository, PostgresWorkspaceFormRepository),
    (WorkspaceConsentRepo, PostgresWorkspaceConsentRepo),
    (FormTemplateRepository, PostgresFormTemplateRepository),
    (MediaLibraryRepository, PostgresMediaLibraryRepository),
    (FormResponseRepository, PostgresFormResponseRepository),
    (ResponderGroupsRepository, PostgresResponderGroupsRepository),
    (WorkspaceRespondersRepository, PostgresWorkspaceRespondersRepository),
]


def public_methods(cls):
    return {
        name
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_") and name in cls.__dict__
    }


@pytest.mark.parametrize("mongo, postgres", PAIRS, ids=lambda c: c.__name__)
def test_twin_covers_the_mongo_surface(mongo, postgres):
    missing = public_methods(mongo) - public_methods(postgres)
    assert not missing, f"{postgres.__name__} lacks {sorted(missing)}"


@pytest.mark.parametrize("mongo, postgres", PAIRS, ids=lambda c: c.__name__)
def test_twin_methods_are_not_marked_themselves(mongo, postgres):
    """Routing reads the markers off the Mongo surface; a marker on the twin is
    a sign the two classes have drifted apart."""
    marked = [n for n in public_methods(postgres) if is_write_op(getattr(postgres, n))]
    assert marked == []
