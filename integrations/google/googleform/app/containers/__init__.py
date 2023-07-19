from concurrent.futures.thread import ThreadPoolExecutor

from dependency_injector import containers, providers

from common.services.http_client import HttpClient
from googleform.app.repositories.form import FormRepository
from googleform.app.repositories.form_response import FormResponseRepository
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.services.form import FormService
from googleform.app.services.form_response import FormResponseService
from googleform.app.services.google import GoogleService
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.app.services.oauth_google import OauthGoogleService
from googleform.config import settings


class Container(containers.DeclarativeContainer):
    """
    Container class for storing and accessing application-level dependencies.

    All the repositories and services used in the application are injected
    in this container.
    """

    http_client: HttpClient = providers.Singleton(HttpClient)

    # Google form repository and service
    form_repo = providers.Factory(FormRepository)
    form_service = providers.Factory(
        FormService, form_repo=form_repo
    )  # Injecting form repo onto form service

    # Google form response repository and service
    form_response_repo = providers.Factory(FormResponseRepository)
    form_response_service = providers.Factory(
        FormResponseService, form_response_repo=form_response_repo
    )  # Injecting form response repo onto form response service

    # Google service
    google_service = providers.Factory(GoogleService)

    # Oauth credential repository
    oauth_credential_repo = providers.Factory(OauthCredentialRepository)

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
    executor: ThreadPoolExecutor = providers.Singleton(ThreadPoolExecutor,
                                                       max_workers=settings.MAX_THREAD_POOL_EXECUTORS)
