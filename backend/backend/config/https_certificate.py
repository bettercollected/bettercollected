from pydantic import BaseSettings


class HttpsCertificateApiSettings(BaseSettings):
    host: ""
    key: ""

    class Config:
        env_prefix = "HTTPS_CERT_API_"
