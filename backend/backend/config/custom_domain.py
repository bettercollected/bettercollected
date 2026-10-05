from typing import Dict, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CustomDomainSettings(BaseSettings):
    """The custom-domain service: hosted (customdomainapi.com) or self-hosted
    (github.com/sireto/custom-domain); both expose the same v1 API.

    ``api_url`` + ``api_credential`` switch the backend from the legacy
    certificate server (``HTTPS_CERT_API_*``) to the v1 domain API; with them
    unset nothing changes. ``assertion_keys`` (``<id>:<secret>,...``) are the
    edge's signing keys, shared with the webapp, which verifies the assertion
    on every custom-domain request. ``webhook_secrets`` is the subscription
    secret (current first, previous second during a rotation).
    """

    api_url: str = ""
    api_credential: str = ""
    application_id: str = ""
    assertion_keys: str = ""
    webhook_secrets: str = ""

    model_config = SettingsConfigDict(env_prefix="CUSTOM_DOMAIN_")

    @field_validator("api_url")
    @classmethod
    def _without_version(cls, value: str) -> str:
        # The SDK adds /v1 itself; the hosted docs print the base URL with it.
        value = value.strip().rstrip("/")
        return value[: -len("/v1")] if value.endswith("/v1") else value

    @property
    def enabled(self) -> bool:
        return bool(self.api_url and self.api_credential)

    def assertion_key_map(self) -> Dict[str, str]:
        keys: Dict[str, str] = {}
        for item in self.assertion_keys.split(","):
            key_id, sep, secret = item.strip().partition(":")
            if sep and key_id and secret:
                keys[key_id] = secret
        return keys

    def webhook_secret_list(self) -> List[str]:
        return [s.strip() for s in self.webhook_secrets.split(",") if s.strip()]
