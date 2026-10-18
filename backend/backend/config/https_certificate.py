from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class HttpsCertificateApiSettings(StoreBackedSettings):
    host: str = ""
    key: str = ""
    upstream: str = ""

    model_config = SettingsConfigDict(env_prefix='HTTPS_CERT_API_')
