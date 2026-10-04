from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerifiedDomainSettings(BaseSettings):
    """Email domains a workspace proves it owns with a DNS TXT record
    (``docs/verified-domains.md``)."""

    # total time one TXT lookup may take, across retries and nameservers
    DNS_TIMEOUT_S: float = 5.0
    # comma-separated resolver IPs; empty = the system resolver (/etc/resolv.conf)
    NAMESERVERS: str = ""
    # a verified domain whose record is missing or wrong this many re-checks in
    # a row is marked as having lost its verification (it stays verified)
    LOSS_AFTER_FAILED_CHECKS: int = 3
    # how often the re-check job looks at a verified domain again
    RECHECK_INTERVAL_HOURS: int = 24
    MAX_PER_WORKSPACE: int = 20
    # comma-separated domains no workspace may claim (with their sub-domains),
    # e.g. the operator's own domains
    RESERVED: str = ""
    # the platform admins' email domains are reserved too (same value as auth's
    # PLATFORM_ADMIN_EMAILS): an SSO connection on such a domain would control
    # the platform-admin grant
    PLATFORM_ADMIN_EMAILS: str = Field(
        "",
        validation_alias=AliasChoices(
            "VERIFIED_DOMAINS_PLATFORM_ADMIN_EMAILS", "PLATFORM_ADMIN_EMAILS"
        ),
    )

    model_config = SettingsConfigDict(env_prefix="VERIFIED_DOMAINS_")

    @property
    def nameservers(self) -> list[str]:
        return [part.strip() for part in self.NAMESERVERS.split(",") if part.strip()]

    @property
    def reserved_domains(self) -> set[str]:
        domains = {
            part.strip().lower().rstrip(".")
            for part in self.RESERVED.split(",")
            if part.strip()
        }
        for email in self.PLATFORM_ADMIN_EMAILS.split(","):
            if "@" in email:
                domains.add(email.rsplit("@", 1)[1].strip().lower().rstrip("."))
        return {domain for domain in domains if domain}
