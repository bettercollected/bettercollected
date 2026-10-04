"""SCIM directory sync through Ory Polis (docs/sso.md, "Directory sync").

Needs single sign-on to be on (``SSO_*``): a directory belongs to the same
Polis tenant (the workspace) as its SSO connections, and is created through
the same admin API key.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SCIMSettings(BaseSettings):
    # Where Polis delivers a directory's events: this backend's
    # /api/v1/scim/webhook, as Polis reaches it (in compose, over the internal
    # `sso` network: http://backend:8000/api/v1/scim/webhook). The directory's
    # own id is appended. Always from configuration, never from a request.
    WEBHOOK_URL: str = ""
    # how old (or how far in the future) a signed event may be
    SIGNATURE_TOLERANCE_SECONDS: int = 300
    # how long an accepted event is remembered against replays (> tolerance)
    EVENT_RETENTION_SECONDS: int = 24 * 3600
    # the largest webhook body accepted (Polis sends at most 1 MB)
    MAX_WEBHOOK_BYTES: int = 1_000_000
    # the nightly resync on the jobs worker (procrastinate cron syntax)
    RECONCILE_CRON: str = "17 3 * * *"
    # Polis's dsync API page size during a resync
    RECONCILE_PAGE_SIZE: int = 100

    model_config = SettingsConfigDict(env_prefix="SCIM_")

    @property
    def webhook_base(self) -> str:
        return (self.WEBHOOK_URL or "").rstrip("/")
