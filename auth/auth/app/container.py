from common.services.http_client import HttpClient
from common.services.jwt_service import JwtService
from dependency_injector import containers, providers
from pymongo import AsyncMongoClient

from auth.app.repositories.postgres import (
    PostgresProviderRepository,
    PostgresUserRepository,
)
from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.auth_service import AuthService
from auth.app.services.stripe_service import StripeService
from auth.app.services.user_service import UserService
from auth.config import settings
from auth.db.models import MirrorWriteFailure
from common.db import (
    DatabaseSettings,
    OutboxRecorder,
    RoutingMetrics,
    RoutingRepository,
    build_engine,
    build_sessionmaker,
    load_flags,
    postgres_repository,
)


class AppContainer(containers.DeclarativeContainer):
    # Beanie 2.x uses pymongo's native async client, not motor. Instantiated
    # inside on_startup (a running event loop) via container.database_client().
    database_client: AsyncMongoClient = providers.Singleton(
        AsyncMongoClient, settings.mongo_settings.URI
    )

    # Define non-decorated objects here
    http_client: HttpClient = providers.Singleton(HttpClient)

    # Postgres runtime (plans/postgres-consolidation.md): everything is None
    # without DATABASE_URL, and the routing layer treats the store as absent.
    flags = providers.Singleton(load_flags)
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(
        build_engine, db_settings, application_name="bettercollected-auth"
    )
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)
    outbox_recorder = providers.Singleton(
        OutboxRecorder, pg_sessionmaker, MirrorWriteFailure
    )
    mirror_timeout_s = providers.Callable(
        lambda s: s.mirror_timeout_ms / 1000, db_settings
    )
    routing_metrics = providers.Singleton(RoutingMetrics)

    provider_repository: ProviderRepository = providers.Singleton(
        RoutingRepository,
        group="auth",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        metrics=routing_metrics,
        mongo=providers.Singleton(ProviderRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresProviderRepository, pg_sessionmaker
        ),
    )
    user_repository: UserRepository = providers.Singleton(
        RoutingRepository,
        group="auth",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        metrics=routing_metrics,
        mongo=providers.Singleton(UserRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresUserRepository, pg_sessionmaker
        ),
    )

    auth_provider_factory: AuthProviderFactory = providers.Singleton(
        AuthProviderFactory
    )

    jwt_service = providers.Singleton(JwtService, settings.AUTH_JWT_SECRET)

    auth_service: AuthService = providers.Singleton(
        AuthService,
        auth_provider_factory=auth_provider_factory,
        user_repository=user_repository,
        http_client=http_client,
    )

    stripe_service: StripeService = providers.Singleton(
        StripeService, user_repository=user_repository
    )

    user_service: UserService = providers.Singleton(
        UserService, user_repo=user_repository, stripe_service=stripe_service
    )


container = AppContainer()
