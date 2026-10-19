from concurrent.futures.thread import ThreadPoolExecutor

from dependency_injector import containers, providers

from common.services.http_client import HttpClient
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.repositories.postgres import PostgresOauthCredentialRepository
from googleform.app.services.google import GoogleService
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.app.services.oauth_google import OauthGoogleService
from googleform.config import settings
from googleform.db.models import MirrorWriteFailure
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


class Container(containers.DeclarativeContainer):
    """
    Container class for storing and accessing application-level dependencies.

    All the repositories and services used in the application are injected
    in this container.
    """

    http_client: HttpClient = providers.Singleton(HttpClient)

    # Postgres runtime (plans/postgres-consolidation.md): everything is None
    # without DATABASE_URL, and the routing layer treats the store as absent.
    flags = providers.Singleton(load_flags)
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(
        build_engine, db_settings, application_name="bettercollected-google"
    )
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)
    outbox_recorder = providers.Singleton(
        OutboxRecorder, pg_sessionmaker, MirrorWriteFailure
    )
    mirror_timeout_s = providers.Callable(
        lambda s: s.mirror_timeout_ms / 1000, db_settings
    )
    routing_metrics = providers.Singleton(RoutingMetrics)

    # Google service
    google_service = providers.Factory(GoogleService)

    # Oauth credential repository
    oauth_credential_repo = providers.Singleton(
        RoutingRepository,
        group="google",
        flags=flags,
        on_mirror_failure=outbox_recorder,
        mirror_timeout_s=mirror_timeout_s,
        metrics=routing_metrics,
        mongo=providers.Singleton(OauthCredentialRepository),
        postgres=providers.Singleton(
            postgres_repository, PostgresOauthCredentialRepository, pg_sessionmaker
        ),
    )

    # Oauth google service
    oauth_google_service = providers.Factory(
        OauthGoogleService, oauth_credential_repo=oauth_credential_repo
    )

    # Oauth credential service
    oauth_credential_service = providers.Factory(
        OauthCredentialService,
        oauth_credential_repo=oauth_credential_repo,
        oauth_google_service=oauth_google_service,
    )
    executor: ThreadPoolExecutor = providers.Singleton(
        ThreadPoolExecutor, max_workers=settings.MAX_THREAD_POOL_EXECUTORS
    )
