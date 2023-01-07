from dependency_injector import containers, providers

from settings import Settings


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["services", "repositories"]
    )
    config = providers.Configuration(pydantic_settings=[Settings()])

    # form_repo = providers.Factory(FormRepository)
    # form_response_repo = providers.Factory(FormResponseRepository)
    # form_scheduler_config_repo = providers.Factory(FormSchedulerConfigRepository)
    # oauth_credential_repo = providers.Factory(OauthCredentialRepository)
    #
    # form_service = providers.Factory(FormService)
    # form_response_service = providers.Factory(FormResponseService)
    # form_scheduler_config_service = providers.Factory(FormSchedulerConfigService)
    # google_service = providers.Factory(GoogleService)
    # oauth_google_service = providers.Factory(OauthGoogleService)
    # oauth_credential_service = providers.Factory(OauthCredentialService)
    # scheduler_service = providers.Factory(SchedulerService)
