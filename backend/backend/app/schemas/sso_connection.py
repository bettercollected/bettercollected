import datetime as dt
import enum
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel


class SsoConnectionType(str, enum.Enum):
    SAML = "saml"
    OIDC = "oidc"


class SsoConnectionStatus(str, enum.Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"


class SsoConnectionDocument(MongoDocument):
    """A workspace's single sign-on connection: our reference to a connection
    held by Ory Polis (docs/sso.md).

    The Polis tenant is the workspace id, so everything Polis keeps for the
    workspace (SSO connections now, a SCIM directory later) hangs off the same
    tenant. Polis holds the IdP metadata and, for OIDC, the client secret;
    this document only names the connection and records its lifecycle. It
    applies to the workspace's verified email domains, never to others.

    At most one connection of a workspace is ``enabled`` at a time.
    """

    workspace_id: PydanticObjectId
    type: SsoConnectionType
    name: str
    status: SsoConnectionStatus = SsoConnectionStatus.DISABLED
    # Polis's identifiers: its connection clientID, tenant and product
    polis_client_id: str
    polis_tenant: str
    polis_product: str
    # what the admin gave, for display (never the OIDC client secret)
    idp_entity_id: Optional[str] = None
    metadata_url: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    # the checked endpoints of the OIDC discovery document (handed to Polis
    # as its metadata; re-checked before a test)
    oidc_endpoints: Optional[Dict[str, str]] = None
    created_by: str
    enabled_at: Optional[dt.datetime] = None
    enabled_by: Optional[str] = None
    disabled_at: Optional[dt.datetime] = None
    disabled_by: Optional[str] = None
    # the last "Test connection": a sign-in through the IdP that came back
    # with an address on one of the workspace's verified domains
    tested_at: Optional[dt.datetime] = None
    tested_by: Optional[str] = None
    last_test_at: Optional[dt.datetime] = None
    # code of the last test's failure, None when it passed
    last_test_error: Optional[str] = None
    # what a failed test saw, for the admin to diagnose it (docs/sso.md,
    # "Troubleshooting"); cleared by a passed test and a config change:
    # the domain of the address the IdP sent (never the address itself),
    # for ``sso_email_domain_not_allowed``
    last_test_domain: Optional[str] = None
    # the names of the claims the IdP sent (never their values)
    last_test_claims: Optional[List[str]] = None

    @field_validator(
        "enabled_at", "disabled_at", "tested_at", "last_test_at", mode="after"
    )
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back without a zone; they are UTC
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    @property
    def is_enabled(self) -> bool:
        return self.status == SsoConnectionStatus.ENABLED

    @property
    def is_tested(self) -> bool:
        return self.tested_at is not None and self.last_test_error is None

    class Settings:
        name = "sso_connections"
        indexes = [
            IndexModel([("workspace_id", 1), ("status", 1)]),
            IndexModel([("polis_client_id", 1)], unique=True),
        ]
