from common.settings.registry import ip_list_problem
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from common.settings.loader.pydantic_source import StoreBackedSettings


class VerifiedDomainSettings(StoreBackedSettings):
    """Email domains a workspace proves it owns with a DNS TXT record
    (``docs/verified-domains.md``)."""

    # total time one TXT lookup may take, across retries and nameservers
    DNS_TIMEOUT_S: float = 5.0
    # comma-separated resolver IPs; empty = the system resolver (/etc/resolv.conf).
    # A verified domain is an SSO trust grant: on a hosted stack use resolvers
    # that validate DNSSEC (e.g. 1.1.1.1,9.9.9.9), not the container's default
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

    # an empty variable counts as unset: the compose file passes the root .env's
    # PLATFORM_ADMIN_EMAILS as VERIFIED_DOMAINS_PLATFORM_ADMIN_EMAILS, which must
    # not hide a PLATFORM_ADMIN_EMAILS from the service's own env file when the
    # root .env has none
    model_config = SettingsConfigDict(
        env_prefix="VERIFIED_DOMAINS_", env_ignore_empty=True
    )

    @field_validator("NAMESERVERS")
    @classmethod
    def _nameservers_are_ip_addresses(cls, value: str) -> str:
        # dnspython takes only addresses (or DoH URLs): a host name or another
        # separator would make every lookup, and so every re-check, fail
        problem = ip_list_problem(value or "")
        if problem:
            raise ValueError(f"VERIFIED_DOMAINS_NAMESERVERS: {problem}")
        return value

    @property
    def nameservers(self) -> list[str]:
        return [part.strip() for part in self.NAMESERVERS.split(",") if part.strip()]

    @property
    def platform_admin_domains(self) -> set[str]:
        domains = {
            email.rsplit("@", 1)[1].strip().lower().rstrip(".")
            for email in self.PLATFORM_ADMIN_EMAILS.split(",")
            if "@" in email
        }
        return {domain for domain in domains if domain}

    @property
    def reserved_domains(self) -> set[str]:
        domains = {
            part.strip().lower().rstrip(".")
            for part in self.RESERVED.split(",")
            if part.strip()
        }
        return {domain for domain in domains if domain} | self.platform_admin_domains

    def warnings(self, sso_enabled: bool) -> list[str]:
        """Configuration a hosted stack with single sign-on should not run
        without (logged at startup; docs/verified-domains.md)."""
        if not sso_enabled:
            return []
        found = []
        if not self.nameservers:
            found.append(
                "VERIFIED_DOMAINS_NAMESERVERS is not set: domain verification "
                "trusts the container's resolver; set DNSSEC-validating resolvers"
            )
        if not self.platform_admin_domains:
            found.append(
                "PLATFORM_ADMIN_EMAILS is not set on the backend: the platform "
                "admins' email domains are not reserved from verification"
            )
        return found
