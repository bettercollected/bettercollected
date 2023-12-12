import elasticapm

from settings.application import settings

apm_client = None
if settings.apm_settings.enabled:
    apm_client = elasticapm.Client(service_name=settings.apm_settings.service_name,
                                   server_url=settings.apm_settings.server_url, api_key=settings.apm_settings.api_key)
elasticapm.instrument()  # Only call this once, as early as possible.
