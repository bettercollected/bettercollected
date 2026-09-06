"""Every Postgres twin exposes at least the public surface of its Mongo original.

The RoutingRepository dispatches by attribute name, so a method missing on
the twin would surface as a mirror failure (or an AttributeError when the
group is served from Postgres). No database needed.
"""

import inspect

import pytest

from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.blacklisted_refresh_token_repository import (
    BlacklistedRefreshTokenRepository,
)
from backend.app.repositories.coupon_repository import CouponRepository
from backend.app.repositories.form_plugin_provider_repository import (
    FormPluginProviderRepository,
)
from backend.app.repositories.postgres.identity import (
    PostgresBlacklistedRefreshTokenRepository,
    PostgresUserTagsRepository,
    PostgresWorkspaceAPIKeyRepository,
    PostgresWorkspaceInvitationRepo,
    PostgresWorkspaceRepository,
    PostgresWorkspaceUserRepository,
)
from backend.app.repositories.postgres.refdata import (
    PostgresAllowedOriginsRepository,
    PostgresCouponRepository,
    PostgresFormPluginProviderRepository,
    PostgresUserFeedbackRepo,
)
from backend.app.repositories.user_feedback import UserFeedbackRepo
from backend.app.repositories.user_tags_repository import UserTagsRepository
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.repositories.workspace_invitation_repo import WorkspaceInvitationRepo
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from common.db import is_write_op

PAIRS = [
    (AllowedOriginsRepository, PostgresAllowedOriginsRepository),
    (FormPluginProviderRepository, PostgresFormPluginProviderRepository),
    (CouponRepository, PostgresCouponRepository),
    (UserFeedbackRepo, PostgresUserFeedbackRepo),
    (WorkspaceRepository, PostgresWorkspaceRepository),
    (WorkspaceUserRepository, PostgresWorkspaceUserRepository),
    (WorkspaceInvitationRepo, PostgresWorkspaceInvitationRepo),
    (WorkspaceAPIKeyRepository, PostgresWorkspaceAPIKeyRepository),
    (BlacklistedRefreshTokenRepository, PostgresBlacklistedRefreshTokenRepository),
    (UserTagsRepository, PostgresUserTagsRepository),
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
