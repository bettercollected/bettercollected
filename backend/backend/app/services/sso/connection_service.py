"""Workspace single sign-on administration (docs/sso.md).

Viewing the settings and testing a connection need ``security.manage``
(Owner, Admin). Everything that changes the configuration (connections,
"SSO required", the default role) is **owners only** (every owner alike): an
enabled connection decides who every address on the workspace's verified
domains is, the owners' own accounts included, so an Admin must not be able
to point it at an identity provider they control.
Connections are created in Ory Polis through its admin API; we keep a
reference (``sso_connections``). The workspace's SSO settings (SSO required,
default role) live on the workspace document.
"""

import datetime as dt
import json
import re
from http import HTTPStatus
from typing import List, Optional

from beanie import PydanticObjectId
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import (
    canonical_role,
    is_owner_membership,
)
from backend.app.repositories.sso_connection_repository import (
    SsoConnectionExists,
    SsoConnectionRepository,
)
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
    SsoConnectionType,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.domains.names import display_domain, domain_of
from backend.app.services.session_service import RevokeReason, SessionService
from backend.app.services.sso.polis_client import (
    PolisAdminClient,
    PolisError,
    PolisUnavailable,
)
from backend.app.services.sso.policy import (
    SsoPolicyService,
    assignable_sso_roles,
    default_sso_role,
)
from backend.app.services.sso.url_guard import (
    Resolver,
    UnsafeUrl,
    check_public_https_url,
    fetch_public,
)
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.config import settings

MAX_METADATA_BYTES = 512 * 1024
OIDC_ENDPOINTS = (
    "issuer",
    "authorization_endpoint",
    "token_endpoint",
    "userinfo_endpoint",
    "jwks_uri",
)


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CreateSsoConnectionDto(_CamelModel):
    type: SsoConnectionType
    name: Optional[str] = Field(None, max_length=100)
    # SAML: the IdP's metadata, as XML or a URL Polis fetches it from
    metadata_xml: Optional[str] = Field(None, max_length=MAX_METADATA_BYTES)
    metadata_url: Optional[str] = Field(None, max_length=2048)
    # OIDC: the IdP's discovery URL and the client registered there
    discovery_url: Optional[str] = Field(None, max_length=2048)
    client_id: Optional[str] = Field(None, max_length=512)
    # SecretStr: never printed by a repr, a log line or a validation error
    client_secret: Optional[SecretStr] = None


class UpdateSsoSettingsDto(_CamelModel):
    sso_required: Optional[bool] = None
    default_role: Optional[str] = Field(None, max_length=64)
    # with sso_required switched on: sign out the members on the SSO domains
    # (their sessions from before the requirement); the owners and the
    # caller's own session are kept
    revoke_sessions: bool = False


class SsoConnectionDto(_CamelModel):
    id: str
    type: str
    name: str
    status: str
    idp_entity_id: Optional[str] = None
    metadata_url: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    created_at: Optional[dt.datetime] = None
    created_by: Optional[str] = None
    enabled_at: Optional[dt.datetime] = None
    tested: bool = False
    tested_at: Optional[dt.datetime] = None
    last_test_at: Optional[dt.datetime] = None
    last_test_error: Optional[str] = None
    last_test_domain: Optional[str] = None
    last_test_claims: Optional[List[str]] = None

    @classmethod
    def of(cls, c: SsoConnectionDocument) -> "SsoConnectionDto":
        return cls(
            id=str(c.id),
            type=c.type.value,
            name=c.name,
            status=c.status.value,
            idp_entity_id=c.idp_entity_id,
            metadata_url=c.metadata_url,
            oidc_discovery_url=c.oidc_discovery_url,
            oidc_client_id=c.oidc_client_id,
            created_at=c.created_at,
            created_by=c.created_by,
            enabled_at=c.enabled_at,
            tested=c.is_tested,
            tested_at=c.tested_at,
            last_test_at=c.last_test_at,
            last_test_error=c.last_test_error,
            last_test_domain=(
                display_domain(c.last_test_domain) if c.last_test_domain else None
            ),
            last_test_claims=c.last_test_claims,
        )


class ServiceProviderDto(_CamelModel):
    """What the customer enters at their identity provider."""

    acs_url: str
    entity_id: str
    sp_metadata_url: str
    oidc_redirect_uri: str


class SsoSettingsDto(_CamelModel):
    sso_required: bool = False
    sso_required_changed_at: Optional[dt.datetime] = None
    default_role: str
    assignable_roles: List[str]
    # owners can always sign in with an email code (docs/sso.md)
    owner_break_glass: bool = True
    revoked_sessions: Optional[int] = None


class SsoOverviewDto(_CamelModel):
    # SSO is switched on and configured on this instance
    available: bool
    service_provider: Optional[ServiceProviderDto] = None
    # the verified domains SSO applies to (Unicode form)
    domains: List[str] = []
    connections: List[SsoConnectionDto] = []
    settings: SsoSettingsDto
    max_connections: int
    # the caller may change the configuration (an owner of the workspace)
    can_manage: bool = False


# A failed test's claim names (auth sends them only for a test): SAML
# attribute names (often URIs) or OIDC claim names, never values.
_CLAIM_NAME = re.compile(r"^[A-Za-z0-9_.:/#-]{1,160}$")
MAX_TEST_CLAIMS = 50


def failed_test_domain(value: Optional[str]) -> Optional[str]:
    """The canonical domain to keep for a failed test, never an address."""
    if not isinstance(value, str) or "@" in value:
        return None
    return domain_of(value)


def failed_test_claims(names) -> Optional[List[str]]:
    """Plausible claim names only, de-duplicated, sorted, capped; None when
    there are none."""
    if not isinstance(names, list):
        return None
    kept = sorted({n for n in names if isinstance(n, str) and _CLAIM_NAME.match(n)})[
        :MAX_TEST_CLAIMS
    ]
    return kept or None


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, content={"code": code, "message": message})


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _polis_error(error: PolisError) -> HTTPException:
    if isinstance(error, PolisUnavailable):
        return _refused(
            HTTPStatus.SERVICE_UNAVAILABLE, "sso_unavailable", error.message
        )
    if error.code == "idp_already_connected":
        # one IdP entity ID belongs to one workspace in Polis: another
        # organisation may have registered it first (squatting)
        return _refused(
            HTTPStatus.CONFLICT,
            error.code,
            "This identity provider (its entity ID) is already connected to "
            "another workspace. If it is your organisation's, contact support "
            "to have it released.",
        )
    return _refused(HTTPStatus.UNPROCESSABLE_ENTITY, error.code, error.message)


class SsoConnectionService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        connection_repo: SsoConnectionRepository,
        domain_service: WorkspaceDomainService,
        workspace_repo: WorkspaceRepository,
        workspace_user_repo: WorkspaceUserRepository,
        session_service: SessionService,
        policy: SsoPolicyService,
        polis: PolisAdminClient,
        resolver: Optional[Resolver] = None,
        fetch_transport=None,
        on_default_role_changed=None,
    ):
        # SCIM: re-apply roles of directory members without a mapped group
        self._on_default_role_changed = on_default_role_changed
        self._authorization = authorization_service
        self._connections = connection_repo
        self._domains = domain_service
        self._workspace_repo = workspace_repo
        self._workspace_users = workspace_user_repo
        self._sessions = session_service
        self._policy = policy
        self._polis = polis
        self._resolver = resolver
        # a seam for tests: the HTTP transport of our own metadata fetches
        self._fetch_transport = fetch_transport

    # -- access ---------------------------------------------------------------
    async def _authorize(self, workspace_id: PydanticObjectId, user: User) -> None:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )

    async def _authorize_owner(self, workspace_id: PydanticObjectId, user: User):
        """Changing the configuration: owners only (see the module)."""
        await self._authorize(workspace_id, user)
        await self._authorization.require_owner(user, workspace_id)

    @staticmethod
    def _require_available() -> None:
        if not settings.sso.is_configured:
            raise _refused(
                HTTPStatus.NOT_FOUND,
                "sso_disabled",
                "Single sign-on is not enabled on this instance.",
            )

    async def _connection_in_workspace(
        self, workspace_id: PydanticObjectId, connection_id: str
    ) -> SsoConnectionDocument:
        connection = await self._connections.get(connection_id)
        if connection is None or connection.workspace_id != PydanticObjectId(
            workspace_id
        ):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        return connection

    async def connection_for_test(
        self, workspace_id: PydanticObjectId, connection_id: str, user: User
    ) -> SsoConnectionDocument:
        await self._authorize(workspace_id, user)
        self._require_available()
        connection = await self._connection_in_workspace(workspace_id, connection_id)
        if connection.oidc_endpoints:
            # the IdP's endpoints Polis will call: still public addresses?
            await self._check_oidc_endpoints(connection.oidc_endpoints)
        return connection

    # -- read -----------------------------------------------------------------
    async def overview(
        self, workspace_id: PydanticObjectId, user: User
    ) -> SsoOverviewDto:
        await self._authorize(workspace_id, user)
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        available = settings.sso.is_configured
        sso = settings.sso
        return SsoOverviewDto(
            available=available,
            service_provider=(
                ServiceProviderDto(
                    acs_url=sso.acs_url,
                    entity_id=sso.SAML_AUDIENCE,
                    sp_metadata_url=sso.sp_metadata_url,
                    oidc_redirect_uri=sso.oidc_redirect_uri,
                )
                if available
                else None
            ),
            domains=[
                display_domain(d) for d in await self._domains.sso_domains(workspace_id)
            ],
            connections=[
                SsoConnectionDto.of(c)
                for c in await self._connections.list_by_workspace(workspace_id)
            ],
            settings=self._settings_dto(workspace),
            max_connections=sso.MAX_CONNECTIONS_PER_WORKSPACE,
            can_manage=await self._authorization.is_owner(user, workspace_id),
        )

    @staticmethod
    def _settings_dto(workspace, revoked: Optional[int] = None) -> SsoSettingsDto:
        return SsoSettingsDto(
            sso_required=bool(getattr(workspace, "sso_required", False)),
            sso_required_changed_at=getattr(workspace, "sso_required_changed_at", None),
            default_role=default_sso_role(workspace).value,
            assignable_roles=assignable_sso_roles(),
            revoked_sessions=revoked,
        )

    # -- connections ----------------------------------------------------------
    async def create_connection(
        self,
        workspace_id: PydanticObjectId,
        request: CreateSsoConnectionDto,
        user: User,
    ) -> SsoConnectionDto:
        await self._authorize_owner(workspace_id, user)
        self._require_available()
        if not await self._domains.sso_domains(workspace_id):
            # a connection without a verified domain could only squat the
            # IdP's entity ID in Polis (one workspace per entity ID)
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_domain_required",
                "Verify your organisation's email domain under Domains before "
                "you add a single sign-on connection.",
            )
        if (
            await self._connections.count_by_workspace(workspace_id)
            >= settings.sso.MAX_CONNECTIONS_PER_WORKSPACE
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_connections",
                f"A workspace can have at most "
                f"{settings.sso.MAX_CONNECTIONS_PER_WORKSPACE} connections.",
            )
        tenant = str(workspace_id)
        name = (request.name or "").strip() or (
            "SAML identity provider"
            if request.type == SsoConnectionType.SAML
            else "OIDC identity provider"
        )
        document = SsoConnectionDocument(
            id=PydanticObjectId(),
            workspace_id=PydanticObjectId(workspace_id),
            type=request.type,
            name=name,
            polis_client_id="",
            polis_tenant=tenant,
            polis_product=settings.sso.POLIS_PRODUCT,
            created_by=str(user.id),
        )
        try:
            if request.type == SsoConnectionType.SAML:
                record = await self._create_saml(tenant, name, request, document)
            else:
                record = await self._create_oidc(tenant, name, request, document)
        except PolisError as error:
            raise _polis_error(error)
        client_id = (record or {}).get("clientID")
        if not client_id:
            raise _refused(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "sso_unavailable",
                "The single sign-on service did not create the connection.",
            )
        document.polis_client_id = client_id
        try:
            await self._connections.create(document)
        except SsoConnectionExists:
            # Polis updated the connection for the same tenant and IdP in
            # place: the recorded one no longer has the configuration its
            # test passed with
            existing = await self._connections.find_by_polis_client_id(client_id)
            if existing is not None:
                existing.tested_at = None
                existing.last_test_error = "config_changed"
                existing.last_test_domain = None
                existing.last_test_claims = None
                existing.updated_at = _now()
                await self._connections.save(existing)
            raise _refused(
                HTTPStatus.CONFLICT,
                "connection_exists",
                "This identity provider is already connected to this workspace. "
                "Its details were updated; test it again.",
            )
        logger.info(
            "SSO connection {} ({}) created in workspace {} by {}",
            document.id,
            document.type.value,
            workspace_id,
            user.id,
        )
        return SsoConnectionDto.of(document)

    async def _guarded_url(self, url: str) -> str:
        try:
            return await check_public_https_url(url.strip(), self._resolver)
        except UnsafeUrl as unsafe:
            raise _refused(HTTPStatus.UNPROCESSABLE_ENTITY, unsafe.code, unsafe.message)

    async def _fetch(self, url: str, max_bytes: int) -> bytes:
        """Fetch through the guard ourselves (every redirect hop checked)."""
        try:
            return await fetch_public(
                url.strip(),
                self._resolver,
                transport=self._fetch_transport,
                max_bytes=max_bytes,
                timeout=settings.sso.HTTP_TIMEOUT_SECONDS,
            )
        except UnsafeUrl as unsafe:
            raise _refused(HTTPStatus.UNPROCESSABLE_ENTITY, unsafe.code, unsafe.message)

    async def _check_oidc_endpoints(self, metadata: dict) -> None:
        for key in OIDC_ENDPOINTS:
            value = metadata.get(key)
            if not isinstance(value, str) or not value:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_discovery",
                    f"The discovery document has no {key}.",
                )
            try:
                await check_public_https_url(value, self._resolver)
            except UnsafeUrl as unsafe:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    unsafe.code,
                    f"The identity provider's {key} is not allowed: {unsafe.message}",
                )

    async def _create_saml(self, tenant, name, request, document) -> dict:
        xml = (request.metadata_xml or "").strip()
        url = (request.metadata_url or "").strip()
        if bool(xml) == bool(url):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "metadata_required",
                "Give the identity provider's metadata as XML or as a URL, not both.",
            )
        if url:
            # fetched here, through the guard; Polis gets the XML, never the URL
            body = await self._fetch(url, MAX_METADATA_BYTES)
            xml = body.decode("utf-8", errors="replace").strip()
            document.metadata_url = url.strip()
        if (
            len(xml.encode("utf-8")) > MAX_METADATA_BYTES
            or "EntityDescriptor" not in xml
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_metadata",
                "That is not SAML metadata (an EntityDescriptor document).",
            )
        record = await self._polis.create_saml(tenant, name, raw_metadata=xml)
        document.idp_entity_id = ((record or {}).get("idpMetadata") or {}).get(
            "entityID"
        )
        return record

    async def _create_oidc(self, tenant, name, request, document) -> dict:
        url = (request.discovery_url or "").strip()
        client_id = (request.client_id or "").strip()
        secret = (
            request.client_secret.get_secret_value() if request.client_secret else ""
        )
        if not url or not client_id or not secret:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "oidc_fields_required",
                "Give the discovery URL, the client ID and the client secret.",
            )
        if len(secret) > 1024:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_client_secret",
                "The client secret is too long.",
            )
        # fetched here, through the guard; Polis gets the checked endpoints
        # (it then never fetches the discovery URL itself)
        body = await self._fetch(url, 64 * 1024)
        try:
            discovery = json.loads(body)
        except ValueError:
            discovery = None
        if not isinstance(discovery, dict):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_discovery",
                "That is not an OpenID Connect discovery document.",
            )
        await self._check_oidc_endpoints(discovery)
        metadata = {key: discovery[key] for key in OIDC_ENDPOINTS}
        document.oidc_discovery_url = url.strip()
        document.oidc_client_id = client_id
        document.oidc_endpoints = metadata
        return await self._polis.create_oidc(tenant, name, metadata, client_id, secret)

    async def enable_connection(
        self, workspace_id: PydanticObjectId, connection_id: str, user: User
    ) -> SsoConnectionDto:
        """Enable one connection; the workspace's other ones are disabled
        (one identity provider signs members in at a time). Only a
        connection whose current configuration passed a test."""
        await self._authorize_owner(workspace_id, user)
        self._require_available()
        connection = await self._connection_in_workspace(workspace_id, connection_id)
        if not connection.is_tested:
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_connection_untested",
                "Test this connection successfully before you enable it.",
            )
        now = _now()
        if not connection.is_enabled:
            connection.status = SsoConnectionStatus.ENABLED
            connection.enabled_at = now
            connection.enabled_by = str(user.id)
            connection.updated_at = now
            await self._connections.save(connection)
        await self._connections.disable_others(
            PydanticObjectId(workspace_id), connection.id, str(user.id), now
        )
        return SsoConnectionDto.of(connection)

    async def disable_connection(
        self, workspace_id: PydanticObjectId, connection_id: str, user: User
    ) -> SsoConnectionDto:
        await self._authorize_owner(workspace_id, user)
        connection = await self._connection_in_workspace(workspace_id, connection_id)
        await self._refuse_while_required(workspace_id, connection)
        if connection.is_enabled:
            now = _now()
            connection.status = SsoConnectionStatus.DISABLED
            connection.disabled_at = now
            connection.disabled_by = str(user.id)
            connection.updated_at = now
            await self._connections.save(connection)
        return SsoConnectionDto.of(connection)

    async def delete_connection(
        self, workspace_id: PydanticObjectId, connection_id: str, user: User
    ) -> None:
        await self._authorize_owner(workspace_id, user)
        connection = await self._connection_in_workspace(workspace_id, connection_id)
        await self._refuse_while_required(workspace_id, connection)
        if settings.sso.is_configured:
            try:
                await self._polis.delete_connection(connection.polis_client_id)
            except PolisError as error:
                raise _polis_error(error)
        await self._connections.delete(connection.id)
        logger.info(
            "SSO connection {} deleted in workspace {} by {}",
            connection.id,
            workspace_id,
            user.id,
        )

    async def _refuse_while_required(self, workspace_id, connection) -> None:
        if not connection.is_enabled:
            return
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        if workspace is not None and workspace.sso_required:
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_required_on",
                "Members must sign in with this connection. Turn off “Require "
                "single sign-on” first.",
            )

    async def record_test(
        self,
        connection: SsoConnectionDocument,
        user_id: str,
        error: Optional[str],
        domain: Optional[str] = None,
        claims: Optional[List[str]] = None,
    ) -> None:
        """The outcome of a "Test connection" sign-in. A failure may carry
        what the test saw: the ``domain`` of the address the IdP sent and the
        names of the ``claims`` it sent (never an address or a value; both
        are sanitised again here and never logged)."""
        now = _now()
        connection.last_test_at = now
        connection.last_test_error = error
        connection.last_test_domain = failed_test_domain(domain) if error else None
        connection.last_test_claims = failed_test_claims(claims) if error else None
        if error is None:
            connection.tested_at = now
            connection.tested_by = str(user_id)
        connection.updated_at = now
        await self._connections.save(connection)

    # -- settings -------------------------------------------------------------
    async def update_settings(
        self,
        workspace_id: PydanticObjectId,
        request: UpdateSsoSettingsDto,
        user: User,
    ) -> SsoSettingsDto:
        await self._authorize_owner(workspace_id, user)
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        if workspace is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        fields = {}
        now = _now()
        if request.default_role is not None:
            if (
                canonical_role(request.default_role) is None
                or canonical_role(request.default_role).value
                not in assignable_sso_roles()
            ):
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_role",
                    "That role can't be given by single sign-on.",
                )
            fields["sso_default_role"] = canonical_role(request.default_role).value
        switching_on = request.sso_required is True and not workspace.sso_required
        if request.sso_required is not None and request.sso_required != bool(
            workspace.sso_required
        ):
            if request.sso_required:
                await self._check_can_require(workspace_id)
            fields.update(
                {
                    "sso_required": request.sso_required,
                    "sso_required_changed_by": str(user.id),
                    "sso_required_changed_at": now,
                }
            )
        if fields:
            fields["updated_at"] = now
            await self._workspace_repo.set_fields(workspace, fields)
            workspace = await self._workspace_repo.find_by_id(workspace_id)
            logger.info(
                "SSO settings of workspace {} changed by {}: {}",
                workspace_id,
                user.id,
                sorted(k for k in fields if k != "updated_at"),
            )
        if "sso_default_role" in fields and self._on_default_role_changed:
            await self._on_default_role_changed(workspace)
        revoked = None
        if request.revoke_sessions and (switching_on or workspace.sso_required):
            revoked = await self._revoke_member_sessions(workspace, user)
        return self._settings_dto(workspace, revoked)

    async def _check_can_require(self, workspace_id: PydanticObjectId) -> None:
        self._require_available()
        connection = await self._connections.find_enabled(workspace_id)
        if connection is None:
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_connection_required",
                "Enable a single sign-on connection first.",
            )
        if not connection.is_tested:
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_connection_untested",
                "Test the enabled connection successfully first.",
            )
        if not await self._domains.sso_domains(workspace_id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "sso_domain_required",
                "Verify an email domain first: single sign-on applies to verified domains.",
            )

    async def _revoke_member_sessions(self, workspace, user: User) -> int:
        """Sign out the members on the SSO domains (not the owners, whose
        email code still works, and not the caller's current session)."""
        members = await self._workspace_users.get_workspace_users(
            workspace_id=workspace.id
        )
        candidates = [
            str(m.user_id)
            for m in members
            if not m.disabled and not is_owner_membership(workspace, m)
        ]
        revoked = 0
        for user_id in await self._policy.sso_users_of(workspace.id, candidates):
            revoked += await self._sessions.revoke_all_for_user(
                user_id,
                RevokeReason.SSO_REQUIRED,
                except_sid=user.sid if user_id == str(user.id) else None,
            )
        logger.info(
            "SSO required in workspace {}: {} sessions revoked by {}",
            workspace.id,
            revoked,
            user.id,
        )
        return revoked

    # -- workspace deletion ---------------------------------------------------
    async def release_workspaces(self, workspace_ids: List[PydanticObjectId]) -> int:
        """Remove deleted workspaces' connections, in Polis (best effort) and
        here."""
        if not workspace_ids:
            return 0
        if settings.sso.is_configured:
            for workspace_id in workspace_ids:
                if not await self._connections.count_by_workspace(workspace_id):
                    continue
                try:
                    await self._polis.delete_tenant(str(workspace_id))
                except PolisError:
                    logger.warning(
                        "Could not delete the Polis connections of deleted workspace {}",
                        workspace_id,
                    )
        return await self._connections.delete_by_workspace_ids(workspace_ids)
