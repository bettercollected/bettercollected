import logging
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

from settings.apm_settings import APMSettings
from settings.shipped_secrets import require_secrets

load_dotenv()

DEFAULT_ORGANIZATION_NAME = "Better Collected"

# Published defaults of earlier versions: treated as not configured.
PLACEHOLDER_API_KEYS = frozenset({"random_api_key"})


class ApplicationSettings(BaseSettings):
    temporal_server_url: str = "localhost:7233"
    namespace: str = "default"
    # the backend's internal listener (API_INTERNAL_PORT): never published
    server_url: str = "http://backend:8001/api/v1"
    # Sent as the ``api-key`` header to the backend's internal job routes; the
    # same value as TEMPORAL_API_KEY on the backend. No default: unset (or a
    # published placeholder) is "", which the backend refuses.
    api_key: str = ""
    aes_hex_key: str = ""
    worker_queue: str = "actions"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000/api/v1"
    workers: int = 10
    cookie_domain: str = "localhost"
    # this instance's name: the sender of a respondent's copy is
    # "<workspace> via <organization_name>" (the auth service's ORGANIZATION_NAME)
    organization_name: str = DEFAULT_ORGANIZATION_NAME
    max_thread_pool_executors: int = 20
    # Isolation of the executor (docs/executor-isolation.md). ``enforce`` (the
    # default): custom action code runs in a confined child process that holds
    # no key, secret or network (sandbox/), every outgoing call of an action
    # goes through the egress rules (utilities/egress.py), and the run's
    # secrets are read from the backend already opened, so this process needs no
    # AES key. ``legacy``: the pre-4.3 in-process ``exec`` with the whole
    # process reachable, kept only as a way back; it logs an error at start.
    action_isolation: str = "enforce"
    # hosts (``host`` or ``host:port``, comma separated) the operator allows
    # actions to call although they are internal or not https
    action_egress_allow: str = ""
    action_sandbox_memory_mb: int = 256
    action_sandbox_cpu_seconds: int = 10
    action_sandbox_timeout_seconds: int = 30
    action_sandbox_max_calls: int = 20
    apm_settings: APMSettings = APMSettings()

    @field_validator("organization_name", mode="before")
    @classmethod
    def _organization_name_unset_is_the_default(cls, value):
        # an empty variable (``ORGANIZATION_NAME=`` in an env file) is unset,
        # not a blank sender name
        if value is None or not str(value).strip():
            return DEFAULT_ORGANIZATION_NAME
        return str(value).strip()

    @field_validator("action_isolation", mode="before")
    @classmethod
    def _known_isolation(cls, value):
        text = str(value or "enforce").strip().lower() or "enforce"
        if text not in ("enforce", "legacy"):
            raise ValueError("ACTION_ISOLATION must be enforce or legacy")
        return text

    @field_validator("api_key")
    @classmethod
    def _no_placeholder_key(cls, value: str) -> str:
        value = (value or "").strip()
        return "" if value in PLACEHOLDER_API_KEYS else value


settings = ApplicationSettings()


def isolation_enforced(current: Optional[ApplicationSettings] = None) -> bool:
    """Whether custom action code and outgoing calls run under the isolation
    (``ACTION_ISOLATION=enforce``, the default)."""
    return (current or settings).action_isolation == "enforce"


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


def require_aes_hex_key(current: Optional[ApplicationSettings] = None) -> None:
    """Raise InsecureSecretError unless AES_HEX_KEY (the stack's
    AUTH_AES_HEX_KEY, a Fernet key) is set, well-formed and not a value
    published in the repository."""
    require_secrets(
        "the actions-executor",
        fernet_keys={"AES_HEX_KEY": (current or settings).aes_hex_key},
    )
