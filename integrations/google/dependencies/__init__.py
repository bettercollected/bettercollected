from dependency_injector import containers, providers

from repositories.form import FormRepository
from repositories.form_response import FormResponseRepository
from repositories.oauth_credential import OauthCredentialRepository
from services.form import FormService
from services.form_response import FormResponseService
from services.google import GoogleService
from services.oauth_credential import OauthCredentialService
from services.oauth_google import OauthGoogleService
from settings import Settings


class Container(containers.DeclarativeContainer):
    """
    Container class for storing and accessing application-level dependencies.

    All the repositories and services used in the application are injected
    in this container.

    Attributes:
        wiring_config: A WiringConfiguration instance that specifies which
            packages to search for dependencies.
        config: A Configuration instance for storing and accessing
            application-level configuration.
    """

    wiring_config = containers.WiringConfiguration(
        packages=["services", "repositories"]
    )
    config = providers.Configuration(pydantic_settings=[Settings()])

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
