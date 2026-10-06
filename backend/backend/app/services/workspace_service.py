import os
import re
import uuid
from http import HTTPStatus
from typing import List, Optional

import bson
from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.user import User
from common.exceptions.http import HTTPException as CommonHTTPException
from common.services.http_client import HttpClient
from fastapi import UploadFile
from httpx import HTTPError
from loguru import logger
import loguru
from pydantic import EmailStr

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.brevo_event_dto import UserEventType
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import (
    WorkspaceRoles,
    has_owner_role,
    is_owner_membership,
)
from backend.app.models.workspace import (
    WorkspaceRequestDtoCamel,
    WorkspaceResponseDto,
    WorkspaceThemeDto,
)
from backend.app.repositories.allowed_origins_repository import AllowedOriginsRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.custom_domain_service import (
    CustomDomainService,
    cleared_fields,
    domain_fields,
    domain_payload,
    unregistered_payload,
)
from backend.app.services.custom_domain_origins import (
    remove_custom_domain_origin,
    sync_custom_domain_origin,
)
from backend.app.services.form_response_service import FormResponseService
from backend.app.services.brevo_service import event_logger_service
from backend.app.services.responder_groups_service import ResponderGroupsService
from backend.app.services.user_tags_service import UserTagsService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_domain_service import WorkspaceDomainService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

# Top-level paths the webapp serves itself; a workspace with one of these
# handles would be shadowed by (or shadow) that route — `/admin/metrics` is the
# platform admin dashboard.
RESERVED_WORKSPACE_NAMES = frozenset({"submissions", "forms", "templates", "admin"})


def is_reserved_workspace_name(workspace_name: str) -> bool:
    return workspace_name.strip().lower() in RESERVED_WORKSPACE_NAMES


def raise_if_reserved_workspace_name(workspace_name: str) -> None:
    if is_reserved_workspace_name(workspace_name):
        raise HTTPException(
            HTTPStatus.CONFLICT, content="This workspace handle is reserved."
        )


CODE_MAIL_FAILED = "We could not send the code. Please try again in a moment."


async def request_code_mail(http_client: HttpClient, params: dict) -> None:
    """Ask the auth service to mail a sign-in code. A refusal or failure there
    is never reported as sent; the caller gets a generic 502 (auth's answer
    can echo the request, the address included, so it is not passed on)."""
    try:
        await http_client.get(
            settings.auth_settings.BASE_URL + "/auth/otp/send",
            params=params,
            headers=auth_service_headers(),
            timeout=180,
        )
    except (CommonHTTPException, HTTPError) as exc:
        status = getattr(exc, "status_code", type(exc).__name__)
        logger.warning(f"Sign-in code mail not requested: auth answered {status}")
        raise HTTPException(HTTPStatus.BAD_GATEWAY, CODE_MAIL_FAILED)


class WorkspaceService:
    def __init__(
        self,
        http_client: HttpClient,
        workspace_repo: WorkspaceRepository,
        workspace_user_repo: WorkspaceUserRepository,
        allowed_origins_repo: AllowedOriginsRepository,
        aws_service: AWSS3Service,
        workspace_user_service: WorkspaceUserService,
        workspace_form_service: WorkspaceFormService,
        form_response_service: FormResponseService,
        responder_groups_service: ResponderGroupsService,
        user_tags_service: UserTagsService,
        authorization_service: AuthorizationService,
        custom_domain_service: Optional[CustomDomainService] = None,
        workspace_domain_service: Optional[WorkspaceDomainService] = None,
        sso_policy=None,
        sso_release=None,
    ):
        self._authorization = authorization_service
        # single sign-on: refuses email codes for SSO-required domains, and
        # removes a deleted workspace's connections (docs/sso.md)
        self._sso_policy = sso_policy
        self._sso_release = sso_release
        self.http_client = http_client
        self.workspace_domain_service = workspace_domain_service
        self.custom_domain_service = custom_domain_service
        self._workspace_repo = workspace_repo
        self._workspace_user_repo = workspace_user_repo
        self._allowed_origins_repo = allowed_origins_repo
        self._aws_service = aws_service
        self._workspace_user_service = workspace_user_service
        self.workspace_form_service = workspace_form_service
        self.form_response_service = form_response_service
        self.responder_groups_service = responder_groups_service
        self.user_tags_service = user_tags_service

    async def get_workspace_by_id(self, workspace_id: PydanticObjectId):
        workspace = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        return WorkspaceResponseDto(**workspace.model_dump(mode="json"))

    async def get_workspace_by_query(self, query: str, user: User):
        workspace = await self._workspace_repo.get_workspace_by_query(query)
        if user and await self._authorization.has_permission(
            user, Permission.FORM_READ, workspace.id
        ):
            return WorkspaceResponseDto(
                **workspace.model_dump(mode="json"), dashboard_access=True
            )
        return WorkspaceResponseDto(**workspace.model_dump(mode="json"))

    async def create_non_default_workspace(
        self,
        title: str,
        description: str,
        user: User,
        workspace_name: str = None,
        profile_image_file: UploadFile = None,
        banner_image_file: UploadFile = None,
    ):
        if user.plan != "PRO":
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="Upgrade to Pro to add more workspace.",
            )

        user_owner_workspaces = await self._workspace_repo.get_user_workspaces(user.id)
        if len(user_owner_workspaces) >= settings.api_settings.ALLOWED_WORKSPACES:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT, content="Cannot add more workspaces"
            )
        if workspace_name:
            raise_if_reserved_workspace_name(workspace_name)
            existing_workspace_with_name = await self._workspace_repo.find_by_name(
                workspace_name
            )
            if existing_workspace_with_name is not None:
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content="Workspace with given name already exists.",
                )
        workspace_document = WorkspaceDocument(
            title=title,
            description=description,
            owner_id=user.id,
            workspace_name=workspace_name if workspace_name else str(bson.ObjectId()),
            is_pro=True,
        )
        workspace_document = await self.upload_images_of_workspace(
            workspace_document=workspace_document,
            profile_image_file=profile_image_file,
            banner_image_file=banner_image_file,
        )
        workspace_document = await self._workspace_repo.save(workspace_document)
        existing_workspace_user = await self._workspace_user_repo.find_workspace_user(
            workspace_document.id, PydanticObjectId(user.id)
        )
        if not existing_workspace_user:
            workspace_user = WorkspaceUserDocument(
                workspace_id=workspace_document.id,
                user_id=user.id,
                roles=[WorkspaceRoles.ADMIN],
            )
            await self._workspace_user_repo.save(workspace_user)
        return WorkspaceResponseDto(**workspace_document.model_dump(mode="json"))

    async def patch_workspace(
        self,
        profile_image_file: UploadFile,
        banner_image_file: UploadFile,
        workspace_id,
        workspace_patch: WorkspaceRequestDtoCamel,
        user: User,
    ):
        # Name, handle, images, custom domain and policies: workspace.manage
        # (Owner and Admin, docs/enterprise-access-model.md §1). Owner-only
        # before the roles step.
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id
        )

        workspace_document = await self.upload_images_of_workspace(
            workspace_document=workspace_document,
            profile_image_file=profile_image_file,
            banner_image_file=banner_image_file,
        )

        if (
            workspace_patch.workspace_name
            and workspace_patch.workspace_name != workspace_document.workspace_name
        ):
            raise_if_reserved_workspace_name(workspace_patch.workspace_name)
            exists_by_handle = await self._workspace_repo.find_by_name(
                workspace_patch.workspace_name
            )
            await self.user_tags_service.add_user_tag(
                user_id=user.id, tag=UserTagType.WORKSPACE_HANDLE_CHANGE
            )
            if exists_by_handle:
                raise HTTPException(409, "Workspace with given handle already exists.")

        workspace_document.workspace_name = (
            workspace_patch.workspace_name
            if workspace_patch.workspace_name
            else workspace_document.workspace_name
        )
        workspace_document.title = (
            workspace_patch.title if workspace_patch.title else workspace_document.title
        )
        workspace_document.description = (
            workspace_patch.description
            if workspace_patch.description
            else workspace_document.description
        )

        if workspace_patch.custom_domain:
            if not workspace_document.is_pro:
                raise HTTPException(status_code=403, content=MESSAGE_FORBIDDEN)
            # the edge asserts the canonical (lowercase) hostname; store the same
            workspace_patch.custom_domain = (
                workspace_patch.custom_domain.strip().lower().rstrip(".")
            )

            try:
                workspace = await self._workspace_repo.find_by_custom_domain(
                    workspace_patch.custom_domain
                )
                if not workspace:
                    await self._provision_custom_domain(
                        workspace_document, workspace_patch.custom_domain
                    )
                    # CORS follows a successful registration: a refused hostname
                    # is never allowed and the working one keeps its origin; the
                    # new one is allowed only once it is verified
                    await self._swap_allowed_origin(
                        workspace_document.custom_domain,
                        workspace_patch.custom_domain,
                        bool(workspace_document.custom_domain_verified),
                    )
                    await self.user_tags_service.add_user_tag(
                        user_id=user.id, tag=UserTagType.CUSTOM_DOMAIN_UPDATED
                    )
                    await event_logger_service.send_event(
                        event_type=UserEventType.CUSTOM_DOMAIN_CHANGED,
                        user_id=user.id,
                        email=user.sub,
                    )
                else:
                    raise HTTPException(409)
            except HTTPException as e:
                if e.status_code == 409:
                    raise HTTPException(
                        409,
                        "Workspace with given custom domain already exists or Domain already exists.",
                    )
                # a refused or unavailable registration must not be saved as if it worked
                raise

        workspace_document.custom_domain = (
            workspace_patch.custom_domain
            if workspace_patch.custom_domain
            else workspace_document.custom_domain
        )

        workspace_document.privacy_policy = (
            workspace_patch.privacy_policy
            if workspace_patch.privacy_policy
            else workspace_document.privacy_policy
        )

        workspace_document.terms_of_service = (
            workspace_patch.terms_of_service
            if workspace_patch.terms_of_service
            else workspace_document.terms_of_service
        )

        saved_workspace = await self._workspace_repo.update(
            workspace_document.id, workspace_document
        )
        return WorkspaceResponseDto(**saved_workspace.model_dump(mode="json"))

    async def update_custom_themes(
        self,
        workspace_id: PydanticObjectId,
        custom_themes: list[WorkspaceThemeDto],
        user: User,
    ):
        """Replace the workspace's saved custom form themes (full-list PATCH).

        The list is small and owned by one settings surface, so replacing it
        wholesale keeps create/rename/delete a single round-trip each.
        """
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        if len(custom_themes) > 20:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                "A workspace can save at most 20 custom themes.",
            )
        titles = [theme.title.casefold() for theme in custom_themes]
        if len(set(titles)) != len(titles):
            raise HTTPException(HTTPStatus.BAD_REQUEST, "Theme names must be unique.")
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id
        )
        workspace_document.custom_themes = custom_themes
        saved_workspace = await self._workspace_repo.update(
            workspace_document.id, workspace_document
        )
        return WorkspaceResponseDto(**saved_workspace.model_dump(mode="json"))

    async def delete_custom_domain_of_workspace(
        self, workspace_id: PydanticObjectId, user: User
    ):
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        if not workspace_document.is_pro:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        workspace_document = await self._workspace_repo.get_workspace_by_id(
            workspace_id=workspace_id
        )
        await remove_custom_domain_origin(
            self._allowed_origins_repo, workspace_document.custom_domain
        )
        if self._custom_domain_enabled:
            domain_id = workspace_document.custom_domain_id
            if not domain_id and workspace_document.custom_domain:
                # set before the service was in use: the import may already
                # hold the hostname for this workspace, and the legacy server
                # may still serve it; release both so nothing stays claimed
                live = await self.custom_domain_service.find_live(
                    workspace_document.id, workspace_document.custom_domain
                )
                domain_id = live.id if live else None
                await self.update_https_server_for_certificate(
                    old_domain=workspace_document.custom_domain
                )
            if domain_id:
                await self.custom_domain_service.delete(domain_id)
            for field, value in cleared_fields().items():
                setattr(workspace_document, field, value)
        else:
            await self.update_https_server_for_certificate(
                old_domain=workspace_document.custom_domain
            )
        workspace_document.custom_domain = ""
        workspace_document.custom_domain_verified = False
        saved_workspace = await self._workspace_repo.save(workspace_document)
        return WorkspaceResponseDto(**saved_workspace.model_dump(mode="json"))

    async def generate_unique_names_from_the_workspace_handle(
        self, workspace_name: str, workspace_id: Optional[PydanticObjectId] = None
    ):
        suggestions = []
        clean_workspace_name = re.sub(r"\W+", "", workspace_name)
        is_valid_workspace_handle = await self.check_if_workspace_handle_is_unique(
            clean_workspace_name, workspace_id
        )
        if is_valid_workspace_handle:
            suggestions.append(clean_workspace_name)
        i = 1
        while 1:
            workspace_suggestion = clean_workspace_name + str(i)
            is_valid_workspace_handle = await self.check_if_workspace_handle_is_unique(
                workspace_suggestion, workspace_id
            )
            if is_valid_workspace_handle:
                suggestions.append(workspace_suggestion)
            if len(suggestions) == 6:
                break
            i += 1
        return suggestions

    async def check_if_workspace_handle_is_unique(
        self, workspace_name: str, workspace_id: Optional[PydanticObjectId] = None
    ):
        if is_reserved_workspace_name(workspace_name):
            return False
        existing_workspace = await self._workspace_repo.find_by_name(workspace_name)
        if workspace_id is not None:
            current_workspace = await self._workspace_repo.find_by_id(workspace_id)
            if existing_workspace and not existing_workspace == current_workspace:
                return False
            return True
        else:
            return existing_workspace is None

    async def get_mine_workspaces(self, user: User):
        memberships = {
            str(membership.workspace_id): membership
            for membership in await self._workspace_user_repo.get_mine_workspaces(
                user_id=user.id
            )
            if not membership.disabled
        }
        workspaces = await self._workspace_repo.get_workspace_by_ids(
            workspace_ids=[m.workspace_id for m in memberships.values()]
        )
        return [
            WorkspaceResponseDto(
                **workspace.model_dump(mode="json"),
                is_owner=is_owner_membership(
                    workspace, memberships.get(str(workspace.id))
                ),
            )
            for workspace in workspaces
        ]

    async def send_otp_for_workspace(
        self, workspace_id: PydanticObjectId, receiver_email: EmailStr
    ):
        workspace = await self._workspace_repo.get_workspace_by_id(workspace_id)
        if self._sso_policy is not None:
            # refused on the SSO workspace's own pages; elsewhere the code
            # only gives a respondent-scoped session (docs/sso.md)
            await self._sso_policy.code_sign_in_scope(
                receiver_email, workspace_id=str(workspace_id)
            )
        await request_code_mail(
            self.http_client,
            {
                "receiver_email": receiver_email,
                "workspace_title": workspace.title or "",
                "workspace_profile_image": workspace.profile_image or "",
                "creator": False,
            },
        )
        return {"message": "Otp sent successfully"}

    async def get_workspace_stats(self, workspace_id: PydanticObjectId, user: User):
        await self._authorization.authorize(
            user, Permission.ANALYTICS_READ, workspace_id
        )
        form_ids = await self.workspace_form_service.get_form_ids_in_workspace(
            workspace_id=workspace_id
        )
        responses_count = (
            await self.form_response_service.get_responses_count_in_workspace(
                workspace_form_ids=form_ids
            )
        )
        deletion_count = (
            await self.form_response_service.get_deletion_requests_count_in_workspace(
                form_ids=form_ids
            )
        )

        return {
            "forms": len(form_ids),
            "responses": responses_count,
            "deletion_requests": deletion_count,
        }

    async def downgrade_user_workspace(self, user_id: str):
        workspaces = await self._workspace_repo.get_user_workspaces(owner_id=user_id)
        for workspace in workspaces:
            if not workspace.default:
                workspace.disabled = True
            workspace.is_pro = False
            workspace.custom_domain_disabled = True
            await self._workspace_repo.save(workspace)
            await self._workspace_user_service.disable_other_users_in_workspace(
                workspace_id=workspace.id, user_id=PydanticObjectId(user_id)
            )

    async def upgrade_user_workspace(self, user_id: str):
        workspaces = await self._workspace_repo.get_user_workspaces(owner_id=user_id)
        for workspace in workspaces:
            workspace.disabled = False
            workspace.is_pro = True
            workspace.custom_domain_disabled = False
            await self._workspace_repo.save(workspace)
            await self._workspace_user_service.enable_all_users_in_workspace(
                workspace_id=workspace.id
            )

    async def update_https_server_for_certificate(
        self, old_domain: str = None, new_domain: str = None
    ):
        if not settings.https_cert_api_settings.host:
            return
        try:
            if old_domain:
                await self.http_client.delete(
                    f"{settings.https_cert_api_settings.host}/domains",
                    headers={"api_key": settings.https_cert_api_settings.key},
                    params={"domain": old_domain},
                )
            if new_domain:
                await self.http_client.post(
                    f"{settings.https_cert_api_settings.host}/domains",
                    headers={"api_key": settings.https_cert_api_settings.key},
                    params={
                        "domain": new_domain,
                        "upstream": (
                            settings.https_cert_api_settings.upstream
                            if settings.https_cert_api_settings.upstream
                            else None
                        ),
                    },
                )
        except Exception as e:
            logger.error("Error form https server: ", e)
            # raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, content="Could not update https certificate.")

    @property
    def _custom_domain_enabled(self) -> bool:
        return bool(self.custom_domain_service and self.custom_domain_service.enabled)

    async def _provision_custom_domain(
        self, workspace_document: WorkspaceDocument, hostname: str
    ) -> None:
        """Make ``hostname`` serve the workspace: through the custom-domain
        service when configured, otherwise through the legacy certificate
        server. With the service, the replacement is registered first and the
        previous domain deleted only after that succeeded, so a refused
        hostname never takes the working one offline."""
        if not self._custom_domain_enabled:
            await self.update_https_server_for_certificate(
                old_domain=workspace_document.custom_domain, new_domain=hostname
            )
            if workspace_document.custom_domain != hostname:
                # a new hostname starts unverified until the verify check passes
                workspace_document.custom_domain_verified = False
            return
        previous_id = workspace_document.custom_domain_id
        # One nonce per registration attempt, kept until the call succeeds: a
        # retry after a transport failure replays the same request, while a
        # later re-registration of the same hostname (delete → add, A → B → A)
        # gets a fresh domain instead of the service replaying a deleted one.
        attempt = workspace_document.custom_domain_attempt
        if not attempt:
            attempt = uuid.uuid4().hex
            await self._workspace_repo.set_fields(
                workspace_document, {"custom_domain_attempt": attempt}
            )
        domain = await self.custom_domain_service.register(
            hostname, workspace_document.id, attempt
        )
        for field, value in domain_fields(domain).items():
            setattr(workspace_document, field, value)
        workspace_document.custom_domain_attempt = None
        if previous_id and previous_id != domain.id:
            try:
                await self.custom_domain_service.delete(previous_id)
            except HTTPException as error:
                # the new hostname is registered; the old one is cleaned up by
                # `python -m backend.custom_domain sweep`
                logger.warning(
                    "custom domain {} replaced but not deleted: {}", previous_id, error
                )

    async def _swap_allowed_origin(
        self, previous: Optional[str], hostname: str, verified: bool
    ) -> None:
        if previous and previous != hostname:
            await remove_custom_domain_origin(self._allowed_origins_repo, previous)
        await sync_custom_domain_origin(self._allowed_origins_repo, hostname, verified)

    async def recheck_workspace_domain(
        self, workspace_id: PydanticObjectId, user: User
    ):
        """Bring the next lifecycle check forward (rate limited by the service)."""
        workspace = await self._require_custom_domain_admin(workspace_id, user)
        domain = await self.custom_domain_service.recheck(workspace.custom_domain_id)
        fields = domain_fields(domain)
        await self._workspace_repo.set_fields(workspace, fields)
        await sync_custom_domain_origin(
            self._allowed_origins_repo,
            workspace.custom_domain,
            fields["custom_domain_verified"],
        )
        return domain_payload(domain)

    async def _require_custom_domain_admin(
        self, workspace_id: PydanticObjectId, user: User
    ) -> WorkspaceDocument:
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        if (
            not workspace
            or not workspace.custom_domain
            or workspace.custom_domain_disabled
            or not workspace.is_pro
        ):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Cannot verify domain for workspace",
            )
        if not self._custom_domain_enabled or not workspace.custom_domain_id:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="This domain is not registered with the custom domain service.",
            )
        return workspace

    async def apply_custom_domain_event(self, event) -> str:
        """Apply a verified webhook event to the workspace that owns the domain.
        Deliveries are at least once and unordered: an event older than what the
        workspace already reflects is ignored. Returns what happened."""
        workspace = await self._workspace_repo.find_by_custom_domain_id(event.domain.id)
        if workspace is None:
            return "unknown_domain"
        seen = workspace.custom_domain_updated_at
        if seen is not None and event.created_at <= seen:
            return "stale"
        if event.type == "domain.deleted":
            # the hostname stays so the settings page can say the domain was
            # removed on the service side and offer to set it again
            fields = {
                **cleared_fields(),
                "custom_domain_status": "deleting",
                "custom_domain_updated_at": event.created_at,
            }
            await remove_custom_domain_origin(
                self._allowed_origins_repo, workspace.custom_domain
            )
        else:
            fields = domain_fields(event.domain)
            fields["custom_domain_updated_at"] = max(
                event.created_at, event.domain.updated_at or event.created_at
            )
        await self._workspace_repo.set_fields(workspace, fields)
        if event.type != "domain.deleted":
            await sync_custom_domain_origin(
                self._allowed_origins_repo,
                workspace.custom_domain,
                bool(fields.get("custom_domain_verified")),
            )
        return "applied"

    async def upload_images_of_workspace(
        self,
        workspace_document: WorkspaceDocument,
        profile_image_file: UploadFile,
        banner_image_file: UploadFile,
    ):
        if profile_image_file:
            profile_image = await self._aws_service.upload_file_to_s3(
                profile_image_file.file,
                str(workspace_document.id)
                + f"profile{os.path.splitext(profile_image_file.filename)[1]}",
                workspace_document.profile_image,
            )
            workspace_document.profile_image = (
                profile_image if profile_image else workspace_document.profile_image
            )
        if banner_image_file:
            banner_image = await self._aws_service.upload_file_to_s3(
                banner_image_file.file,
                str(workspace_document.id)
                + f"banner{os.path.splitext(banner_image_file.filename)[1]}",
                workspace_document.banner_image,
            )
            workspace_document.banner_image = (
                banner_image if banner_image else workspace_document.banner_image
            )
        return workspace_document

    async def shared_workspaces_of_billing_owner(
        self, user_id: str
    ) -> List[WorkspaceDocument]:
        """The workspaces ``user_id`` is the billing owner (``owner_id``) of
        that have another active owner: deleting the account would delete
        them under those owners."""
        shared = []
        for workspace in await self._workspace_repo.get_user_workspaces(
            owner_id=str(user_id)
        ):
            for membership in await self._workspace_user_repo.get_workspace_users(
                workspace_id=workspace.id
            ):
                if (
                    str(membership.user_id) != str(user_id)
                    and not membership.disabled
                    and has_owner_role(membership.roles)
                ):
                    shared.append(workspace)
                    break
        return shared

    async def refuse_deleting_billing_owner_of_shared_workspaces(self, user: User):
        """409 ``billing_owner_of_shared_workspaces`` while the account is the
        billing owner of a workspace with another active owner (every account
        deletion path calls this before deleting anything). The way out: make
        another owner the billing owner, or, on a paid or personal workspace,
        whose billing owner can't change, remove the other owners."""
        shared = await self.shared_workspaces_of_billing_owner(user.id)
        if not shared:
            return
        names = []
        for workspace in shared:
            name = workspace.title or workspace.workspace_name
            if workspace.is_pro or workspace.default:
                names.append(f"{name} (remove its other owners)")
            else:
                names.append(
                    f"{name} (make another owner the billing owner, or remove "
                    "its other owners)"
                )
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            content={
                "code": "billing_owner_of_shared_workspaces",
                "message": "You are the billing owner of workspaces that have other "
                "owners, so your account can't be deleted yet: "
                + "; ".join(names)
                + ".",
                "workspaces": [
                    {
                        "id": str(workspace.id),
                        "title": workspace.title,
                        "workspaceName": workspace.workspace_name,
                        # a paid or personal workspace's billing owner can't
                        # change: the only way out is removing the others
                        "billingOwnerCanChange": not (
                            workspace.is_pro or workspace.default
                        ),
                    }
                    for workspace in shared
                ],
            },
        )

    async def delete_workspaces_of_user_with_forms(self, user: User):
        # never a workspace another owner still relies on (checked again by
        # every caller before it deletes anything else)
        await self.refuse_deleting_billing_owner_of_shared_workspaces(user)
        workspaces = await self.get_mine_workspaces(user=user)
        workspaces = [
            workspace for workspace in workspaces if workspace.owner_id == user.id
        ]
        workspace_ids = [workspace.id for workspace in workspaces]
        form_ids = await self.workspace_form_service.get_form_ids_in_workspaces_and_imported_by_user(
            workspace_ids, user
        )
        await self.responder_groups_service.delete_groups_of_workspaces(
            workspace_ids=workspace_ids
        )
        await self.workspace_form_service.delete_forms_with_ids(form_ids=form_ids)
        await self._workspace_user_service.delete_user_form_all_workspaces(user)
        await self._workspace_user_service.delete_user_of_workspaces(
            workspace_ids=workspace_ids
        )
        for workspace_id in workspace_ids:
            self._aws_service.delete_folder_from_s3(f"private/{workspace_id}")
        if self.workspace_domain_service is not None:
            # a deleted workspace's verified domains are released
            await self.workspace_domain_service.release_workspace_domains(workspace_ids)
        if self._sso_release is not None:
            await self._sso_release(workspace_ids)

        for workspace in workspaces:
            await remove_custom_domain_origin(
                self._allowed_origins_repo, workspace.custom_domain
            )
        await self._workspace_repo.delete_workspaces_with_ids(workspace_ids)

    async def verify_workspace_domain(self, workspace_id, user):
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        if (
            not workspace.custom_domain
            or workspace.custom_domain_disabled
            or not workspace.is_pro
        ):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content="Cannot verify domain for workspace",
            )
        if self._custom_domain_enabled:
            if not workspace.custom_domain_id:
                # removed on the service side, or set before the service existed
                return unregistered_payload(workspace)
            domain = await self.custom_domain_service.fetch(workspace.custom_domain_id)
            if domain is None:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND, content="Custom domain not found."
                )
            fields = domain_fields(domain)
            await self._workspace_repo.set_fields(workspace, fields)
            await sync_custom_domain_origin(
                self._allowed_origins_repo,
                workspace.custom_domain,
                fields["custom_domain_verified"],
            )
            return domain_payload(domain)
        try:
            response = await self.http_client.get(
                f"{settings.https_cert_api_settings.host}/domains/verify/{workspace.custom_domain}",
                headers={"api_key": settings.https_cert_api_settings.key},
                timeout=60,
            )
            verified = False
            if response.get("domain_verified") and response.get("txt_verified"):
                verified = True
            await self._workspace_repo.set_fields(
                workspace, {"custom_domain_verified": verified}
            )
            await sync_custom_domain_origin(
                self._allowed_origins_repo, workspace.custom_domain, verified
            )
            return {**response, "provider": "legacy"}
        except Exception as e:
            loguru.logger.error(e)
            raise e


async def create_workspace(user: User):
    from backend.app.container import (
        container,
    )  # at call time: container imports this module

    workspace_repo = container.workspace_repo()
    workspace_user_repo = container.workspace_user_repo()
    workspace = await workspace_repo.get_default_workspace_by_owner_id(user.id)
    if not workspace:
        await event_logger_service.send_event(
            event_type=UserEventType.USER_CREATED, user_id=user.id, email=user.sub
        )
        workspace = WorkspaceDocument(
            title="",
            description="",
            owner_id=user.id,
            profile_image="",
            banner_image="",
            default=True,
            workspace_name=str(user.id),
            custom_domain=None,
        )
        await workspace_repo.save(workspace)
    # Save new workspace user if it is not associated yet
    existing_workspace_user = await workspace_user_repo.find_workspace_user(
        workspace.id, PydanticObjectId(user.id)
    )
    if not existing_workspace_user:
        workspace_user = WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[WorkspaceRoles.ADMIN]
        )
        await workspace_user_repo.save(workspace_user)
