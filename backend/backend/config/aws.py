from pydantic_settings import BaseSettings, SettingsConfigDict


class AWSSettings(BaseSettings):
    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""
    PRE_SIGNED_URL_EXPIRY: int = 10
    # Any S3-compatible store works (Wasabi in production; RustFS/MinIO for
    # local dev and self-hosting). The defaults preserve the original
    # hardwired Wasabi setup so existing deployments need no new env.
    ENDPOINT_URL: str = "https://s3.eu-central-1.wasabisys.com"
    REGION: str = "eu-central-1"
    BUCKET: str = "bettercollected"
    # Domain used to build public object URLs. Defaults to ENDPOINT_URL;
    # set separately when serving objects through a CDN.
    PUBLIC_URL: str = ""

    model_config = SettingsConfigDict(env_prefix='AWS_')

    @property
    def public_base_url(self) -> str:
        return self.PUBLIC_URL or self.ENDPOINT_URL
