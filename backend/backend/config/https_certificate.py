from pydantic import BaseSettings


class HttpsCertificateApiSettings(BaseSettings):
    host: str = ""
    key: str = ""
    upstream: str = ""

    class Config:
        env_prefix = "HTTPS_CERT_API_"
