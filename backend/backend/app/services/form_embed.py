"""Embedding a published form in another site (docs/embed.md).

The switch ``FORM_EMBED_ENABLED`` (default off) turns the feature on. While
it is off nothing here is served: the settings routes answer 404, the policy
says "not enabled" (the webapp then sends no framing header and the pages are
served as before) and no origin is stored or used.

A workspace lists the sites that may frame its forms (``embed_allowed_origins``
on the workspace document). They become the ``frame-ancestors`` of the
respondent pages, which the webapp's proxy sets from ``embed_policy``. An
origin is ``https://host[:port]`` (``http`` only for localhost and
127.0.0.1, so a developer can try it), or ``https://*.host`` for the
subdomains of a registrable domain: never a bare suffix such as
``https://*.com``, ``https://*.co.uk`` or ``https://*.github.io``.
"""

import re
from http import HTTPStatus
from typing import List, Optional
from urllib.parse import urlsplit

from bson.errors import InvalidId
from common.constants import MESSAGE_FORBIDDEN
from common.ids import RecordId
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.domains.names import (
    DomainRefused,
    canonical_domain,
    registrable_domain,
)

MAX_ORIGINS = 20
MAX_ORIGIN_LENGTH = 255
LOCAL_HOSTS = ("localhost", "127.0.0.1")
DEFAULT_PORTS = {"https": 443, "http": 80}

DISABLED_CODE = "form_embed_disabled"
DISABLED_MESSAGE = (
    "Embedding forms is not switched on on this server (FORM_EMBED_ENABLED is off)."
)

# scheme://host[:port], nothing else: no userinfo, no brackets (IPv6), no path
_AUTHORITY = re.compile(r"^(?P<host>[^:/@\[\]?#\s]+)(?::(?P<port>[0-9]{1,5}))?$")


def form_embed_enabled() -> bool:
    """Is ``FORM_EMBED_ENABLED`` on?"""
    from backend.config import settings

    return bool(getattr(settings, "FORM_EMBED_ENABLED", False))


class OriginRefused(ValueError):
    """``code`` is stable for clients: invalid_origin, origin_scheme,
    origin_path, origin_wildcard, origin_host, origin_port."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_origin(raw: str) -> str:
    """The stored form of a site allowed to frame the forms (lower case,
    punycode host, default port dropped), or ``OriginRefused``."""
    if not isinstance(raw, str):
        raise OriginRefused(
            "invalid_origin", "Enter a site like https://www.example.org."
        )
    value = raw.strip()
    if (
        not value
        or len(value) > MAX_ORIGIN_LENGTH
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise OriginRefused(
            "invalid_origin", "Enter a site like https://www.example.org."
        )
    try:
        parts = urlsplit(value)
    except ValueError:
        raise OriginRefused(
            "invalid_origin", "Enter a site like https://www.example.org."
        )
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http"):
        raise OriginRefused("origin_scheme", "The site must start with https://.")
    if parts.query or parts.fragment or "?" in value or "#" in value:
        raise OriginRefused(
            "origin_path", "Enter the site only, without a path, query or fragment."
        )
    if parts.path not in ("", "/"):
        raise OriginRefused(
            "origin_path",
            "Enter the site only, without a path (https://www.example.org).",
        )
    authority = _AUTHORITY.match(parts.netloc)
    if not authority:
        raise OriginRefused(
            "invalid_origin",
            "Enter a site like https://www.example.org (no user name, no IP address).",
        )
    host = authority.group("host")
    port = int(authority.group("port")) if authority.group("port") else None
    if port is not None and not 1 <= port <= 65535:
        raise OriginRefused("origin_port", "The port must be between 1 and 65535.")

    wildcard = host.startswith("*.")
    if "*" in host and not wildcard:
        raise OriginRefused(
            "origin_wildcard", "A wildcard looks like https://*.example.org."
        )
    if wildcard:
        if scheme != "https":
            raise OriginRefused(
                "origin_scheme", "A wildcard site must start with https://."
            )
        try:
            name = canonical_domain(host[2:])
        except DomainRefused:
            raise OriginRefused(
                "origin_wildcard", "A wildcard looks like https://*.example.org."
            )
        # a registrable domain or something below one: never "*.com" or "*.co.uk"
        if registrable_domain(name) is None:
            raise OriginRefused(
                "origin_wildcard",
                "A wildcard must sit under a domain of your own (https://*.example.org), not under a shared suffix like .com or .co.uk.",
            )
        canonical_host = "*." + name
    elif host.lower() in LOCAL_HOSTS:
        canonical_host = host.lower()
    else:
        if scheme != "https":
            raise OriginRefused(
                "origin_scheme",
                "The site must start with https:// (http:// is accepted for localhost only).",
            )
        try:
            canonical_host = canonical_domain(host)
        except DomainRefused:
            raise OriginRefused("origin_host", "That is not a valid host name.")
    if port is not None and port == DEFAULT_PORTS[scheme]:
        port = None
    return f"{scheme}://{canonical_host}" + (f":{port}" if port is not None else "")


def normalize_origins(origins: List[str]) -> List[str]:
    """The canonical origins, without duplicates, in the order given; at most
    ``MAX_ORIGINS``. Raises ``OriginRefused`` for the first bad entry (its
    ``index`` says which)."""
    if len(origins) > MAX_ORIGINS:
        raise OriginRefused(
            "too_many_origins", f"At most {MAX_ORIGINS} sites are allowed."
        )
    cleaned: List[str] = []
    for index, raw in enumerate(origins):
        try:
            origin = canonical_origin(raw)
        except OriginRefused as error:
            error.index = index  # type: ignore[attr-defined]
            raise
        if origin not in cleaned:
            cleaned.append(origin)
    return cleaned


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class EmbedSettingsDto(_CamelModel):
    origins: List[str] = []
    can_manage: bool = False
    max_origins: int = MAX_ORIGINS


class UpdateEmbedSettingsDto(_CamelModel):
    # a bounded input: the list is checked (and capped) in normalize_origins
    origins: List[str] = Field(default_factory=list, max_length=MAX_ORIGINS * 2)


class EmbedPolicyDto(_CamelModel):
    """What the webapp needs to answer a respondent page: whether embedding is
    on and which sites the workspace allows. Everything in it is visible to
    anyone who loads one of the workspace's forms (the response's
    ``frame-ancestors``)."""

    enabled: bool = False
    origins: List[str] = []


def disabled_error() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.NOT_FOUND,
        content={"code": DISABLED_CODE, "message": DISABLED_MESSAGE},
    )


class FormEmbedService:
    def __init__(
        self,
        workspace_repo: PostgresWorkspaceRepository,
        authorization_service: AuthorizationService,
    ):
        self._workspace_repo = workspace_repo
        self._authorization = authorization_service

    async def get_settings(
        self, workspace_id: RecordId, user: User
    ) -> EmbedSettingsDto:
        """The allowed sites. Whoever may share forms sees them (the share
        dialog says which sites can show the form); only admins change them."""
        held = await self._authorization.effective_permissions(
            user, workspace_id, raise_sso_required=True
        )
        if (
            Permission.FORM_SHARE not in held
            and Permission.WORKSPACE_MANAGE not in held
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        self._ensure_enabled()
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        return EmbedSettingsDto(
            origins=list(workspace.embed_allowed_origins or []),
            can_manage=Permission.WORKSPACE_MANAGE in held,
        )

    async def update_settings(
        self, workspace_id: RecordId, dto: UpdateEmbedSettingsDto, user: User
    ) -> EmbedSettingsDto:
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        self._ensure_enabled()
        try:
            origins = normalize_origins(dto.origins)
        except OriginRefused as error:
            content = {"code": error.code, "message": error.message}
            if hasattr(error, "index"):
                content["index"] = error.index  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content=content
            )
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        await self._workspace_repo.set_fields(
            workspace, {"embed_allowed_origins": origins}
        )
        return EmbedSettingsDto(origins=origins, can_manage=True)

    async def policy(
        self,
        workspace_name: Optional[str] = None,
        custom_domain: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> EmbedPolicyDto:
        """The policy of the workspace named by exactly one of its handle, its
        custom domain or its id. Never an error for an unknown or disabled
        workspace: no origins, so only the first-party pages may frame it."""
        if not form_embed_enabled():
            return EmbedPolicyDto(enabled=False, origins=[])
        if (
            sum(1 for value in (workspace_name, custom_domain, workspace_id) if value)
            != 1
        ):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content="Provide exactly one of workspace_name, custom_domain or workspace_id.",
            )
        workspace = None
        if workspace_name:
            workspace = await self._workspace_repo.find_by_name(workspace_name)
        elif custom_domain:
            workspace = await self._workspace_repo.find_by_custom_domain(custom_domain)
        else:
            try:
                workspace = await self._workspace_repo.find_by_id(
                    RecordId(workspace_id)
                )
            except (ValueError, InvalidId):
                workspace = None
        if workspace is None or workspace.disabled:
            return EmbedPolicyDto(enabled=True, origins=[])
        return EmbedPolicyDto(
            enabled=True, origins=list(workspace.embed_allowed_origins or [])
        )

    @staticmethod
    def _ensure_enabled() -> None:
        if not form_embed_enabled():
            raise disabled_error()
