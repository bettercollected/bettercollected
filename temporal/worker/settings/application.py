import logging
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

from settings.apm_settings import APMSettings

load_dotenv()

# Published defaults of earlier versions: treated as not configured.
PLACEHOLDER_API_KEYS = frozenset({"random_api_key"})


class ApplicationSettings(BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    server_url: str = "http://backend:8000/api/v1"
    # Sent as the ``api-key`` header to the backend's internal job routes; the
    # same value as TEMPORAL_API_KEY on the backend. No default: unset (or a
    # published placeholder) is "", which the backend refuses.
    api_key: str = ""
    aes_hex_key: str = ""
    worker_queue: str = "default"
    workers: int = 10
    cookie_domain: str = "localhost"
    max_thread_pool_executors: int = 20
    apm_settings: APMSettings = APMSettings()

    @field_validator("api_key")
    @classmethod
    def _no_placeholder_key(cls, value: str) -> str:
        value = (value or "").strip()
        return "" if value in PLACEHOLDER_API_KEYS else value


settings = ApplicationSettings()


def log_if_api_key_missing(current: Optional[ApplicationSettings] = None) -> bool:
    """Log an error at startup when API_KEY is not configured (True when it
    is). The worker still starts; its calls to the backend are refused."""
    if (current or settings).api_key:
        return True
    logging.getLogger(__name__).error(
        "API_KEY is not set (or is the old public default): the backend refuses "
        "this worker's calls. Set it to the backend's TEMPORAL_API_KEY."
    )
    return False
