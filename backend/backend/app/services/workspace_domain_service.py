"""Verified email domains for workspaces (docs/verified-domains.md).

A workspace's Owner or Admins claim an email domain, publish a DNS TXT record
with the claim's token and verify it. A domain is verified by at most one
workspace at a time; the first to verify wins and other workspaces' claims
of it cannot verify (``conflict``) until it is released. Single sign-on may
only map a domain its workspace has verified (``domain_owner``,
``is_domain_verified_for``): a verified domain hands every address in it to
that workspace's identity provider.

A verified domain is re-checked periodically (``recheck_verified_domains``,
for a job). After LOSS_AFTER_FAILED_CHECKS checks in a row that find the
record missing or wrong, ``verification_lost_at`` is set; the domain stays
verified and is never transferred automatically. Resolver timeouts and
errors do not count towards that.
"""

import datetime as dt
import secrets
from http import HTTPStatus
from typing import Callable, Dict, List, Optional

from beanie import PydanticObjectId
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.repositories.workspace_domain_repository import (
    DomainAlreadyClaimed,
    DomainVerifiedElsewhere,
    WorkspaceDomainRepository,
)
from backend.app.schemas.workspace_domain import DomainStatus, WorkspaceDomainDocument
from backend.app.services.domains import dns_txt
from backend.app.services.domains.names import (
    DomainRefused,
    claimable_domain,
    display_domain,
    domain_of,
)
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings

# check outcome stored when another workspace holds the domain verified
VERIFIED_ELSEWHERE = "verified_by_another_workspace"
# status shown for a claim another workspace's verification blocks
CONFLICT = "conflict"


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class ClaimDomainDto(_CamelModel):
    domain: str = Field(..., min_length=1, max_length=300)


class WorkspaceDomainDto(_CamelModel):
    id: str
    domain: str  # ASCII (punycode) form, what DNS uses
    display_domain: str  # Unicode form
    # pending | verified | failed | conflict
    status: str
    txt_record_name: str
    txt_record_value: str
    created_at: Optional[dt.datetime] = None
    created_by: Optional[str] = None
    verified_at: Optional[dt.datetime] = None
    last_checked_at: Optional[dt.datetime] = None
    last_check_error: Optional[str] = None
    failed_checks: int = 0
    verification_lost_at: Optional[dt.datetime] = None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, content={"code": code, "message": message})


class WorkspaceDomainService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        domain_repo: WorkspaceDomainRepository,
        resolver_factory: Optional[Callable] = None,
    ):
        self._workspace_user_service = workspace_user_service
        self._domain_repo = domain_repo
        self._resolver_factory = resolver_factory or self._default_resolver

    @staticmethod
    def _default_resolver():
        config = settings.verified_domains
        return dns_txt.make_resolver(config.DNS_TIMEOUT_S, config.nameservers)

    async def _authorize(self, workspace_id: PydanticObjectId, user: User) -> None:
        """The one access check for managing domains: Owner or Admin (403
        otherwise, members and outsiders alike). Becomes
        ``authorize(user, "security.manage", workspace_id)`` with the
        permission service (docs/enterprise-access-model.md)."""
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )

    # -- management (Owner/Admin) ---------------------------------------------
    async def list_domains(
        self, workspace_id: PydanticObjectId, user: User
    ) -> List[WorkspaceDomainDto]:
        await self._authorize(workspace_id, user)
        documents = await self._domain_repo.list_by_workspace(workspace_id)
        return [await self._to_dto(document) for document in documents]

    async def claim_domain(
        self, workspace_id: PydanticObjectId, request: ClaimDomainDto, user: User
    ) -> WorkspaceDomainDto:
        await self._authorize(workspace_id, user)
        config = settings.verified_domains
        try:
            domain = claimable_domain(request.domain, config.reserved_domains)
        except DomainRefused as refused:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY, refused.code, refused.message
            )
        if (
            await self._domain_repo.count_by_workspace(workspace_id)
            >= config.MAX_PER_WORKSPACE
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_domains",
                f"A workspace can claim at most {config.MAX_PER_WORKSPACE} domains.",
            )
        owner = await self._domain_repo.find_verified(domain)
        if owner is not None:
            if owner.workspace_id == PydanticObjectId(workspace_id):
                raise self._already_claimed()
            raise self._verified_elsewhere()
        document = WorkspaceDomainDocument(
            id=PydanticObjectId(),
            workspace_id=PydanticObjectId(workspace_id),
            domain=domain,
            verification_token=secrets.token_hex(16),
            created_by=str(user.id),
        )
        try:
            await self._domain_repo.create(document)
        except DomainAlreadyClaimed:
            raise self._already_claimed()
        return await self._to_dto(document)

    async def verify_domain(
        self, workspace_id: PydanticObjectId, domain_id: str, user: User
    ) -> WorkspaceDomainDto:
        """Check the TXT record now. The outcome is in the returned status
        and ``lastCheckError``; only a missing claim is an error (404)."""
        await self._authorize(workspace_id, user)
        document = await self._claim_in_workspace(workspace_id, domain_id)
        document = await self._check(document, verified_by=str(user.id))
        return await self._to_dto(document)

    async def delete_domain(
        self, workspace_id: PydanticObjectId, domain_id: str, user: User
    ) -> None:
        """Remove the claim; a verified domain is released for others."""
        await self._authorize(workspace_id, user)
        document = await self._claim_in_workspace(workspace_id, domain_id)
        await self._domain_repo.delete(document.id)

    # -- for single sign-on ---------------------------------------------------
    async def domain_owner(self, domain: str) -> Optional[PydanticObjectId]:
        """The workspace that verified ``domain`` (an email address works
        too), or None. A verified domain whose re-checks have since failed
        (``verification_lost_at``) still has its owner."""
        name = domain_of(domain)
        if name is None:
            return None
        owner = await self._domain_repo.find_verified(name)
        return owner.workspace_id if owner else None

    async def is_domain_verified_for(
        self, workspace_id: PydanticObjectId, email_or_domain: str
    ) -> bool:
        """Whether the workspace has verified exactly this domain (the
        address's domain for an email). Sub-domains are separate domains."""
        owner = await self.domain_owner(email_or_domain)
        return owner is not None and owner == PydanticObjectId(workspace_id)

    # -- for a periodic job ---------------------------------------------------
    async def recheck_verified_domains(self, limit: int = 100) -> Dict[str, int]:
        """Re-check verified domains not checked within
        RECHECK_INTERVAL_HOURS, oldest first. Returns counts by outcome."""
        config = settings.verified_domains
        due = await self._domain_repo.list_due_for_recheck(
            _now() - dt.timedelta(hours=config.RECHECK_INTERVAL_HOURS), limit
        )
        counts = {"checked": 0, "passed": 0, "failed": 0, "lost": 0}
        for document in due:
            was_lost = document.verification_lost_at is not None
            document = await self._check(document)
            counts["checked"] += 1
            if document.last_check_error is None:
                counts["passed"] += 1
            else:
                counts["failed"] += 1
            if document.verification_lost_at is not None and not was_lost:
                counts["lost"] += 1
                logger.warning(
                    "verified domain lost its TXT record: workspace={} domain_id={}",
                    document.workspace_id,
                    document.id,
                )
        return counts

    async def release_workspace_domains(
        self, workspace_ids: List[PydanticObjectId]
    ) -> int:
        """Remove the claims of deleted workspaces."""
        if not workspace_ids:
            return 0
        return await self._domain_repo.delete_by_workspace_ids(workspace_ids)

    # -- internals ------------------------------------------------------------
    async def _claim_in_workspace(
        self, workspace_id: PydanticObjectId, domain_id: str
    ) -> WorkspaceDomainDocument:
        document = await self._domain_repo.get(domain_id)
        if document is None or document.workspace_id != PydanticObjectId(workspace_id):
            raise HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)
        return document

    async def _check(
        self, document: WorkspaceDomainDocument, verified_by: Optional[str] = None
    ) -> WorkspaceDomainDocument:
        now = _now()
        owner = await self._domain_repo.find_verified(document.domain)
        if owner is not None and owner.id != document.id:
            return await self._store_failure(document, VERIFIED_ELSEWHERE, now)
        result = await dns_txt.check_token(
            self._resolver_factory(), document.domain, document.verification_token
        )
        if not result.verified:
            return await self._store_failure(document, result.error, now)

        document.last_checked_at = now
        document.last_check_error = None
        document.failed_checks = 0
        document.verification_lost_at = None
        if document.status == DomainStatus.VERIFIED:
            return await self._domain_repo.save(document)
        document.status = DomainStatus.VERIFIED
        document.verified_domain = document.domain
        document.verified_at = now
        document.verified_by = verified_by
        try:
            return await self._domain_repo.save(document)
        except DomainVerifiedElsewhere:
            # another workspace verified it between our look and our write
            document.status = DomainStatus.PENDING
            document.verified_domain = None
            document.verified_at = None
            document.verified_by = None
            return await self._store_failure(document, VERIFIED_ELSEWHERE, now)

    async def _store_failure(
        self, document: WorkspaceDomainDocument, error: str, now: dt.datetime
    ) -> WorkspaceDomainDocument:
        document.last_checked_at = now
        document.last_check_error = error
        if document.status == DomainStatus.VERIFIED:
            # a verified domain only loses its verification by its records
            if error not in dns_txt.TRANSIENT_ERRORS:
                document.failed_checks += 1
                if (
                    document.failed_checks
                    >= settings.verified_domains.LOSS_AFTER_FAILED_CHECKS
                    and document.verification_lost_at is None
                ):
                    document.verification_lost_at = now
        else:
            document.status = DomainStatus.FAILED
            document.failed_checks += 1
        return await self._domain_repo.save(document)

    async def _to_dto(self, document: WorkspaceDomainDocument) -> WorkspaceDomainDto:
        status = DomainStatus(document.status).value
        if document.status != DomainStatus.VERIFIED:
            owner = await self._domain_repo.find_verified(document.domain)
            if owner is not None and owner.id != document.id:
                status = CONFLICT
        return WorkspaceDomainDto(
            id=str(document.id),
            domain=document.domain,
            display_domain=display_domain(document.domain),
            status=status,
            txt_record_name=dns_txt.record_name(document.domain),
            txt_record_value=dns_txt.record_value(document.verification_token),
            created_at=document.created_at,
            created_by=document.created_by,
            verified_at=document.verified_at,
            last_checked_at=document.last_checked_at,
            last_check_error=document.last_check_error,
            failed_checks=document.failed_checks,
            verification_lost_at=document.verification_lost_at,
        )

    @staticmethod
    def _already_claimed() -> HTTPException:
        return _refused(
            HTTPStatus.CONFLICT,
            "already_claimed",
            "This workspace has already claimed that domain.",
        )

    @staticmethod
    def _verified_elsewhere() -> HTTPException:
        return _refused(
            HTTPStatus.CONFLICT,
            "domain_verified_elsewhere",
            "Another workspace has verified that domain. Contact support if your "
            "organisation owns it.",
        )
