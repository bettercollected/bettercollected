from pydantic_settings import BaseSettings, SettingsConfigDict


class HttpsCertificateApiSettings(BaseSettings):
    host: str = ""
    key: str = ""
    upstream: str = ""

    model_config = SettingsConfigDict(env_prefix='HTTPS_CERT_API_')
