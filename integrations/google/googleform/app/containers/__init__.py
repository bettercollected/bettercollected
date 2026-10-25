from concurrent.futures.thread import ThreadPoolExecutor

from dependency_injector import containers, providers

from common.services.http_client import HttpClient
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.services.google import GoogleService
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.app.services.oauth_google import OauthGoogleService
from googleform.config import settings
from googleform.db.flags import load_google_flags
from common.db import DatabaseSettings, build_engine, build_sessionmaker


class Container(containers.DeclarativeContainer):
    """
    Container class for storing and accessing application-level dependencies.

    All the repositories and services used in the application are injected
    in this container.
    """

    http_client: HttpClient = providers.Singleton(HttpClient)

    # Postgres only (googleform/db/flags.py): a stale DB_* flag naming another
    # store refuses the start. The engine is None without DATABASE_URL, and
    # the startup check then refuses to start.
    flags = providers.Singleton(load_google_flags)
    db_settings = providers.Singleton(DatabaseSettings.from_env)
    pg_engine = providers.Singleton(
        build_engine, db_settings, application_name="bettercollected-google"
    )
    pg_sessionmaker = providers.Singleton(build_sessionmaker, pg_engine)

    # Google service
    google_service = providers.Factory(GoogleService)

    # Oauth credential repository
    oauth_credential_repo = providers.Singleton(
        OauthCredentialRepository, pg_sessionmaker
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
