"""Registration of submissions in a workspace's case system.

Configuration (services, a form's registration), the hook on submit, the
delivery job's logic, the nightly sweeps and the deletion hooks. See
``docs/open-formulieren-registration.md``.

Rules this module keeps:

- Nothing external is called on a respondent's request path: submitting writes
  a delivery row and queues a job (by delivery id) and returns.
- Answers are decrypted only inside :meth:`RegistrationService.run_delivery`,
  built into the body in memory and never stored, logged or queued.
- A delivery row holds ids, a status, counters and one of our error codes.
- Every object is loaded with its workspace in the query; a form can only use
  a service of its own workspace.
- Logs name ids, counts and our codes; never answers, bodies, addresses,
  secrets or the destination's text.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import Awaitable, Callable, Dict, List, Optional

from common.constants import MESSAGE_NOT_FOUND
from common.clock import utcnow
from common.models.user import User
from common.records import RecordId
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.registration import ServiceNameTaken
from backend.app.schemas.registration import (
    DeliveryStatus,
    FormRegistrationDocument,
    RegistrationDeliveryDocument,
    RegistrationServiceDocument,
    ServiceAuth,
    ServiceKind,
    VariableMapping,
)
from backend.app.services import safe_http
from backend.app.services.registration import body as body_builder
from backend.app.services.registration import client, objects_api
from backend.app.services.registration.retry import (  # noqa: F401
    MAX_ATTEMPTS,
    RETRY_WAITS,
    RegistrationRetry,
)
from backend.app.services.registration.mode import refuse_when_off, registration_enabled
from backend.app.services.registration.secrets import (
    SecretUnreadable,
    seal,
    unseal,
)

# a pending delivery without a queued job is queued again after this long
REDEFER_AFTER = dt.timedelta(minutes=2)
# an in-progress delivery that did not move for this long lost its worker
STUCK_AFTER = dt.timedelta(minutes=30)
SWEEP_BATCH = 200
MAX_VARIABLES = 200
MAX_SECRET_LENGTH = 4000
_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,100}$")
_OPEN_STATES = (DeliveryStatus.PENDING, DeliveryStatus.RETRYING)


@dataclass(frozen=True)
class Outcome:
    status: str
    retry_after: Optional[int] = None
    retry: bool = False


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class ServiceDto(_CamelModel):
    id: str
    name: str
    kind: str
    base_url: str
    auth: str
    auth_name: Optional[str] = None
    # the secret itself is never returned
    has_secret: bool
    secret_set_at: Optional[dt.datetime] = None
    organisation_name: str
    # Objects API services only
    objecttypes_base_url: Optional[str] = None
    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None


class ServiceCreateDto(_CamelModel):
    name: str = Field(..., min_length=1, max_length=80)
    kind: ServiceKind = ServiceKind.GENERIC_JSON
    base_url: str = Field(..., min_length=1, max_length=2048)
    # left out: ``none`` for Generic JSON, ``token`` for an Objects API
    auth: Optional[ServiceAuth] = None
    auth_name: Optional[str] = Field(None, max_length=200)
    secret: Optional[str] = Field(None, max_length=MAX_SECRET_LENGTH, repr=False)
    organisation_name: Optional[str] = Field(None, max_length=80)
    objecttypes_base_url: Optional[str] = Field(None, min_length=1, max_length=2048)


class ServiceUpdateDto(_CamelModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    base_url: Optional[str] = Field(None, min_length=1, max_length=2048)
    auth: Optional[ServiceAuth] = None
    auth_name: Optional[str] = Field(None, max_length=200)
    secret: Optional[str] = Field(None, max_length=MAX_SECRET_LENGTH, repr=False)
    organisation_name: Optional[str] = Field(None, max_length=80)
    objecttypes_base_url: Optional[str] = Field(None, min_length=1, max_length=2048)


class ServiceTestDto(_CamelModel):
    ok: bool
    code: Optional[str] = None
    http_status: Optional[int] = None


class VariableMappingDto(_CamelModel):
    source: str = Field(..., min_length=1, max_length=200)
    # Generic JSON: the name in the body
    key: Optional[str] = Field(None, max_length=64)
    # Objects API: the path in ``record.data`` (1-8 segments)
    target_path: Optional[List[str]] = Field(None, max_length=16)


class FormRegistrationUpdateDto(_CamelModel):
    enabled: bool = False
    service_id: Optional[str] = Field(None, max_length=64)
    path: str = Field("", max_length=client.MAX_PATH_LENGTH)
    variables: List[VariableMappingDto] = Field(default_factory=list)
    transform_to_list: List[str] = Field(default_factory=list)
    # Objects API only
    object_type_url: Optional[str] = Field(None, max_length=2048)
    object_type_version: Optional[int] = None
    reference_path: Optional[List[str]] = Field(None, max_length=16)


class FormRegistrationDto(_CamelModel):
    enabled: bool
    kind: Optional[str] = None
    service_id: Optional[str] = None
    service_name: Optional[str] = None
    organisation_name: Optional[str] = None
    path: str = ""
    variables: List[VariableMappingDto] = Field(default_factory=list)
    transform_to_list: List[str] = Field(default_factory=list)
    object_type_url: Optional[str] = None
    object_type_version: Optional[int] = None
    reference_path: Optional[List[str]] = None
    updated_at: Optional[dt.datetime] = None


class VariableDto(_CamelModel):
    source: str
    label: str
    type: str
    supported: bool
    reason: Optional[str] = None


class DeliveryDto(_CamelModel):
    id: str
    response_id: str
    status: str
    service_name: Optional[str] = None
    attempts: int
    manual_attempts: int
    last_error_code: Optional[str] = None
    last_http_status: Optional[int] = None
    remote_id: Optional[str] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    delivered_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None


class DeliveryPageDto(_CamelModel):
    items: List[DeliveryDto]
    total: int


class StatusDto(_CamelModel):
    enabled: bool


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message})


def _not_found(message: str = MESSAGE_NOT_FOUND) -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, message)


def _service_dto(document: RegistrationServiceDocument) -> ServiceDto:
    return ServiceDto(
        id=str(document.id),
        name=document.name,
        kind=document.kind.value,
        base_url=document.base_url,
        auth=document.auth.value,
        auth_name=document.auth_name,
        has_secret=bool(document.secret_sealed),
        secret_set_at=document.secret_set_at,
        organisation_name=document.organisation_name,
        objecttypes_base_url=document.objecttypes_base_url,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _delivery_dto(document: RegistrationDeliveryDocument) -> DeliveryDto:
    return DeliveryDto(
        id=str(document.id),
        response_id=document.response_id,
        status=document.status.value,
        service_name=document.service_name,
        attempts=document.attempts,
        manual_attempts=document.manual_attempts,
        last_error_code=document.last_error_code,
        last_http_status=document.last_http_status,
        remote_id=document.remote_id,
        last_attempt_at=document.last_attempt_at,
        next_attempt_at=document.next_attempt_at,
        delivered_at=document.delivered_at,
        created_at=document.created_at,
    )


async def _defer_job(delivery_id: str) -> None:
    """Queue ``register_submission`` for a delivery: the id is the only
    argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.register_submission.configure(
            # no ``lock``: procrastinate keeps a unique index on a lock while a
            # job is ``doing``, which a hard-killed worker would leave behind
            # and block the re-queued job. One send at a time is the atomic
            # claim in ``run_delivery``; ``queueing_lock`` stops duplicates.
            queueing_lock=f"register_submission:{delivery_id}",
        ).defer_async(delivery_id=delivery_id)
    except AlreadyEnqueued:
        pass


class RegistrationService:
    def __init__(
        self,
        *,
        authorization_service,
        service_repo,
        registration_repo,
        delivery_repo,
        workspace_form_repo,
        form_repo,
        form_response_service,
        workspace_repo,
        crypto,
        aws_service,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ):
        self._authorization = authorization_service
        self._services = service_repo
        self._registrations = registration_repo
        self._deliveries = delivery_repo
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._responses = form_response_service
        self._workspaces = workspace_repo
        self._crypto = crypto
        self._aws = aws_service
        self._defer = defer or _defer_job
        self._clock = clock

    # ------------------------------------------------------------ status

    @staticmethod
    def status() -> StatusDto:
        return StatusDto(enabled=registration_enabled())

    # ---------------------------------------------------------- services

    async def _manage(self, user: User, workspace_id: RecordId) -> None:
        refuse_when_off()
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id
        )

    async def list_services(
        self, workspace_id: RecordId, user: User
    ) -> List[ServiceDto]:
        await self._manage(user, workspace_id)
        return [
            _service_dto(d)
            for d in await self._services.list_by_workspace(workspace_id)
        ]

    @staticmethod
    def _check_auth(auth: ServiceAuth, auth_name: Optional[str], secret) -> None:
        if auth is ServiceAuth.NONE:
            return
        if secret is not None and (
            not secret
            or re.search(r"[\r\n\x00]", secret)
            or len(secret) > MAX_SECRET_LENGTH
            # a token goes after "Token " in one header: plain, no spaces
            or (
                auth is ServiceAuth.TOKEN
                and (not secret.isascii() or re.search(r"[\s\x00-\x1f\x7f]", secret))
            )
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_secret",
                "The secret is empty or contains characters that are not allowed.",
            )
        if auth is ServiceAuth.TOKEN:
            return
        if auth is ServiceAuth.HEADER and not (
            auth_name
            and _HEADER_NAME.match(auth_name)
            and not client.reserved_header(auth_name)
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_auth_name",
                "Give the name of the header that carries the secret.",
            )
        if auth is ServiceAuth.BASIC and not auth_name:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_auth_name",
                "Give the user name.",
            )

    async def _checked_base_url(self, base_url: str) -> str:
        """https only, the default port, and a host that resolves to public
        addresses only (checked again at every connection)."""
        try:
            url, host = safe_http.checked_https_url(base_url, allow_query=False)
        except safe_http.UrlRefused:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_url",
                "Use a https:// address without a port, user name, query or fragment.",
            )
        try:
            await asyncio.wait_for(
                safe_http.public_address(host, lambda h, p: client.resolve(h, p)),
                10,
            )
        except asyncio.TimeoutError:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "unreachable",
                "That address does not resolve.",
            )
        except safe_http.AddressRefused as refused:
            if refused.code == "not_allowed":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "not_allowed",
                    "That address is not a public one.",
                )
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "unreachable",
                "That address does not resolve.",
            )
        return url

    @staticmethod
    def _auth_for_kind(kind: ServiceKind, auth: Optional[ServiceAuth]) -> ServiceAuth:
        """An Objects API service authenticates with a token and nothing else
        (``none`` and ``basic`` are refused); Generic JSON never uses one."""
        if kind is ServiceKind.OBJECTS_API:
            if auth not in (None, ServiceAuth.TOKEN):
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_auth",
                    "An Objects API is reached with a token.",
                )
            return ServiceAuth.TOKEN
        if auth is ServiceAuth.TOKEN:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_auth",
                "A token is only used for an Objects API.",
            )
        return auth or ServiceAuth.NONE

    @staticmethod
    def _objecttypes_base_not_applicable() -> HTTPException:
        return _refused(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "objecttypes_base_not_applicable",
            "An object types address belongs to an Objects API service.",
        )

    async def create_service(
        self, workspace_id: RecordId, request: ServiceCreateDto, user: User
    ) -> ServiceDto:
        await self._manage(user, workspace_id)
        auth = self._auth_for_kind(request.kind, request.auth)
        auth_name = request.auth_name if auth is not ServiceAuth.TOKEN else None
        self._check_auth(auth, auth_name, request.secret)
        if auth is not ServiceAuth.NONE and not request.secret:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "secret_required",
                "Give the secret this service needs.",
            )
        base_url = await self._checked_base_url(request.base_url)
        objecttypes_base_url = None
        if request.kind is ServiceKind.OBJECTS_API:
            if not request.objecttypes_base_url:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "objecttypes_base_required",
                    "Give the address of the object types API.",
                )
            objecttypes_base_url = await self._checked_base_url(
                request.objecttypes_base_url
            )
        elif request.objecttypes_base_url is not None:
            raise self._objecttypes_base_not_applicable()
        workspace = await self._workspaces.find_by_id(workspace_id)
        document = RegistrationServiceDocument(
            workspace_id=workspace_id,
            name=request.name.strip(),
            kind=request.kind,
            base_url=base_url,
            auth=auth,
            auth_name=auth_name if auth is not ServiceAuth.NONE else None,
            organisation_name=(request.organisation_name or "").strip()
            or (getattr(workspace, "title", None) or "").strip()
            or "the organisation",
            objecttypes_base_url=objecttypes_base_url,
            created_by=str(user.id),
            updated_by=str(user.id),
        )
        document.ensure_id()
        if auth is not ServiceAuth.NONE:
            document.secret_sealed = seal(
                self._crypto, workspace_id, document.id, request.secret
            )
            document.secret_set_at = self._clock()
        try:
            document = await self._services.create(document)
        except ServiceNameTaken:
            raise _refused(
                HTTPStatus.CONFLICT, "name_taken", "A service with this name exists."
            )
        logger.info(
            "registration service created: workspace={} service={} by={}",
            workspace_id,
            document.id,
            user.id,
        )
        return _service_dto(document)

    async def _service_of(
        self, workspace_id, service_id
    ) -> RegistrationServiceDocument:
        document = await self._services.get(workspace_id, service_id)
        if document is None:
            raise _not_found()
        return document

    async def update_service(
        self,
        workspace_id: RecordId,
        service_id: str,
        request: ServiceUpdateDto,
        user: User,
    ) -> ServiceDto:
        await self._manage(user, workspace_id)
        document = await self._service_of(workspace_id, service_id)
        objects = document.kind is ServiceKind.OBJECTS_API
        auth = self._auth_for_kind(
            document.kind, request.auth if request.auth is not None else document.auth
        )
        auth_name = (
            request.auth_name if request.auth_name is not None else document.auth_name
        )
        if auth is ServiceAuth.TOKEN:
            auth_name = None
        self._check_auth(auth, auth_name, request.secret)
        new_url = document.base_url
        if request.base_url is not None:
            new_url = await self._checked_base_url(request.base_url)
        if request.objecttypes_base_url is not None:
            if not objects:
                raise self._objecttypes_base_not_applicable()
            # never fetched by us, so no new secret is needed; forms whose
            # object type now sits outside it fail at their next send
            document.objecttypes_base_url = await self._checked_base_url(
                request.objecttypes_base_url
            )
        moved = (
            new_url != document.base_url
            or auth is not document.auth
            or (auth is not ServiceAuth.NONE and auth_name != document.auth_name)
        )
        # a stored secret is never pointed at a new host or method by someone
        # who cannot read it: a change of address or auth needs a new secret
        if auth is not ServiceAuth.NONE and moved and not request.secret:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "secret_required",
                "Changing the address or the authentication needs the secret again.",
            )
        if (
            auth is not ServiceAuth.NONE
            and not request.secret
            and not document.secret_sealed
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "secret_required",
                "Give the secret this service needs.",
            )
        if request.name is not None:
            document.name = request.name.strip()
        if request.organisation_name is not None and request.organisation_name.strip():
            document.organisation_name = request.organisation_name.strip()
        document.base_url = new_url
        document.auth = auth
        document.auth_name = auth_name if auth is not ServiceAuth.NONE else None
        if auth is ServiceAuth.NONE:
            document.secret_sealed = None
            document.secret_set_at = None
        elif request.secret:
            document.secret_sealed = seal(
                self._crypto, workspace_id, document.id, request.secret
            )
            document.secret_set_at = self._clock()
        document.updated_by = str(user.id)
        try:
            document = await self._services.save(document)
        except ServiceNameTaken:
            raise _refused(
                HTTPStatus.CONFLICT, "name_taken", "A service with this name exists."
            )
        logger.info(
            "registration service updated: workspace={} service={} by={}",
            workspace_id,
            document.id,
            user.id,
        )
        return _service_dto(document)

    async def delete_service(
        self, workspace_id: RecordId, service_id: str, user: User
    ) -> None:
        await self._manage(user, workspace_id)
        document = await self._service_of(workspace_id, service_id)
        if await self._registrations.count_for_service(document.id):
            raise _refused(
                HTTPStatus.CONFLICT,
                "service_in_use",
                "A form still sends its submissions to this service.",
            )
        await self._services.delete(workspace_id, document.id)
        logger.info(
            "registration service deleted: workspace={} service={} by={}",
            workspace_id,
            service_id,
            user.id,
        )

    def _target(self, service: RegistrationServiceDocument, path: str) -> client.Target:
        return client.Target(
            base_url=service.base_url,
            path=path,
            auth=service.auth.value,
            auth_name=service.auth_name,
            secret=unseal(
                self._crypto, service.workspace_id, service.id, service.secret_sealed
            ),
        )

    async def test_service(
        self, workspace_id: RecordId, service_id: str, user: User
    ) -> ServiceTestDto:
        """Send a body marked as a test; reports our outcome code only."""
        await self._manage(user, workspace_id)
        service = await self._service_of(workspace_id, service_id)
        if service.kind is ServiceKind.OBJECTS_API:
            # a test record would create an object (or fail its schema): an
            # Objects API is checked on a form, with a lookup that reads nothing
            return ServiceTestDto(ok=False, code="use_form_check")
        try:
            target = self._target(service, "")
            empty_values, empty_schema = body_builder.build_values(
                {}, [], {}, None, [], lambda _id: b""
            )
            payload = body_builder.serialize(
                empty_values, empty_schema, {"test": True}, {"type": "object"}
            )
            status = await client.post_json(
                target, payload, idempotency_key=f"test-{service.id}"
            )
        except SecretUnreadable:
            return ServiceTestDto(ok=False, code="secret_unreadable")
        except client.SendFailed as failed:
            return ServiceTestDto(
                ok=False, code=failed.code, http_status=failed.http_status
            )
        return ServiceTestDto(ok=True, http_status=status)

    # ------------------------------------------------- a form's registration

    async def _form_scope(self, user, permission, workspace_id, form_id) -> None:
        refuse_when_off()
        await self._authorization.authorize(
            user, permission, workspace_id, form_id=str(form_id)
        )

    async def _form_for_variables(self, form_id):
        latest = await self._forms.get_latest_version_of_form(form_id)
        return latest or await self._forms.get_form_document_by_id(str(form_id))

    async def get_form_registration(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> FormRegistrationDto:
        await self._form_scope(user, Permission.FORM_READ, workspace_id, form_id)
        document = await self._registrations.get_for_form(workspace_id, form_id)
        if document is None:
            return FormRegistrationDto(enabled=False)
        service = (
            await self._services.get(workspace_id, document.service_id)
            if document.service_id
            else None
        )
        objects = service is not None and service.kind is ServiceKind.OBJECTS_API
        return FormRegistrationDto(
            enabled=document.enabled,
            kind=service.kind.value if service else None,
            service_id=document.service_id,
            service_name=service.name if service else None,
            organisation_name=service.organisation_name if service else None,
            path=document.path,
            variables=[
                VariableMappingDto(
                    source=v.source,
                    key=None if objects else v.key,
                    target_path=v.target_path if objects else None,
                )
                for v in document.variables
            ],
            transform_to_list=document.transform_to_list,
            object_type_url=document.object_type_url,
            object_type_version=document.object_type_version,
            reference_path=(
                list(document.reference_path or objects_api.DEFAULT_REFERENCE_PATH)
                if objects
                else None
            ),
            updated_at=document.updated_at,
        )

    async def list_variables(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> List[VariableDto]:
        await self._form_scope(user, Permission.WORKSPACE_MANAGE, workspace_id, form_id)
        form = await self._form_for_variables(form_id)
        return [
            VariableDto(
                source=v.source,
                label=v.label,
                type=v.type,
                supported=v.supported,
                reason=v.reason,
            )
            for v in body_builder.variables_of(form).values()
            if v.kind != "group_child"
        ]

    async def put_form_registration(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: FormRegistrationUpdateDto,
        user: User,
    ) -> FormRegistrationDto:
        await self._form_scope(user, Permission.WORKSPACE_MANAGE, workspace_id, form_id)
        workspace_form = await self._workspace_forms.find_workspace_form(
            workspace_id, str(form_id)
        )
        provider = getattr(getattr(workspace_form, "settings", None), "provider", None)
        if provider not in (None, "self"):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "form_not_collected_here",
                "Only forms collected here can send their submissions on.",
            )
        objects_fields = (
            request.object_type_url is not None
            or request.object_type_version is not None
            or request.reference_path is not None
            or any(v.target_path is not None for v in request.variables)
        )
        service = None
        if request.service_id:
            # only a service of this workspace, whatever id the body names
            service = await self._services.get(workspace_id, request.service_id)
            if service is None:
                raise _refused(
                    HTTPStatus.NOT_FOUND, "service_not_found", MESSAGE_NOT_FOUND
                )
        if request.enabled and service is None:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "service_required",
                "Choose the service to send to.",
            )
        objects = service is not None and service.kind is ServiceKind.OBJECTS_API
        if objects_fields and not objects:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "service_required" if service is None else "not_an_objects_api",
                "These settings belong to a form that sends to an Objects API.",
            )
        if objects and request.path:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_path",
                "An Objects API has no path to choose.",
            )
        if not objects and client.path_problem(request.path):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_path",
                "The path must be relative, without '..', a query or a fragment.",
            )
        form_for_mapping = await self._form_for_variables(form_id)
        object_type_url = object_type_version = reference_path = None
        if objects:
            mapping = self._checked_objects_mapping(form_for_mapping, request)
            object_type_url, object_type_version, reference_path = (
                self._checked_object_type(service, request, mapping)
            )
        else:
            mapping = self._checked_mapping(form_for_mapping, request)
        if request.enabled and not mapping:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "variables_required",
                "Choose at least one variable to send.",
            )
        document = await self._registrations.get_for_form(workspace_id, form_id)
        if document is None:
            document = FormRegistrationDocument(
                workspace_id=workspace_id, form_id=str(form_id)
            )
            document.ensure_id()
        document.enabled = request.enabled
        document.service_id = str(service.id) if service else None
        document.path = request.path
        document.variables = mapping
        document.transform_to_list = list(dict.fromkeys(request.transform_to_list))
        document.object_type_url = object_type_url
        document.object_type_version = object_type_version
        document.reference_path = reference_path
        document.updated_by = str(user.id)
        await self._registrations.save(document)
        logger.info(
            "form registration saved: workspace={} form={} enabled={} variables={} by={}",
            workspace_id,
            form_id,
            document.enabled,
            len(mapping),
            user.id,
        )
        return await self.get_form_registration(workspace_id, str(form_id), user)

    @staticmethod
    def _checked_objects_mapping(
        form, request: FormRegistrationUpdateDto
    ) -> List[VariableMapping]:
        """The answers of an Objects API form: each source goes to a target
        path in ``record.data``. Files cannot be sent (there is no Documents
        API here); paths are unique and none sits inside another."""
        if len(request.variables) > MAX_VARIABLES:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_variables",
                f"At most {MAX_VARIABLES} variables.",
            )
        if request.transform_to_list:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_transform",
                "Multiple choice answers are always sent as a list here.",
            )
        index = body_builder.variables_of(form)
        mapping: List[VariableMapping] = []
        for item in request.variables:
            variable = index.get(item.source)
            if variable is None or variable.kind == "group_child":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "unknown_variable",
                    "This form has no such variable.",
                )
            if not variable.supported or variable.type == "file_upload":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "variable_not_supported",
                    "This kind of question cannot be sent to an Objects API.",
                )
            path = item.target_path
            if objects_api.path_problem(path):
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_target_path",
                    "A target path has 1 to 8 names of letters, digits and _, "
                    "each starting with a letter, without '__' or a trailing '_'.",
                )
            for earlier in mapping:
                if objects_api.paths_conflict(earlier.target_path, path):
                    raise _refused(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        "target_path_conflict",
                        "Target paths are unique and none sits inside another.",
                    )
            mapping.append(
                VariableMapping(
                    source=item.source, key=".".join(path), target_path=list(path)
                )
            )
        return mapping

    @staticmethod
    def _checked_object_type(
        service: RegistrationServiceDocument,
        request: FormRegistrationUpdateDto,
        mapping: List[VariableMapping],
    ):
        """``(object type URL, version, reference path)`` to store. The URL
        must sit under the service's object types address (set by the
        workspace's admins); we never fetch it, their Objects API does."""
        url = None
        if request.object_type_url is not None and request.object_type_url.strip():
            try:
                url = objects_api.checked_object_type(
                    request.object_type_url, service.objecttypes_base_url
                )
            except objects_api.ObjectTypeRefused as refused:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    refused.code,
                    "The object type URL must be an https address of the form "
                    ".../objecttypes/<uuid> under the service's object types address.",
                )
        version = request.object_type_version
        if version is not None and not (
            objects_api.MIN_VERSION <= version <= objects_api.MAX_VERSION
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_object_type_version",
                "The version is a whole number from 1 to 10000.",
            )
        if request.enabled and (url is None or version is None):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "object_type_required",
                "Give the object type URL and its version.",
            )
        reference = request.reference_path
        if reference is None:
            reference = list(objects_api.DEFAULT_REFERENCE_PATH)
        if objects_api.path_problem(reference):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_reference_path",
                "The reference path has 1 to 8 names of letters, digits and _.",
            )
        if any(objects_api.paths_conflict(m.target_path, reference) for m in mapping):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "reference_path_conflict",
                "The reference path is also used by a mapped answer.",
            )
        return url, version, list(reference)

    @staticmethod
    def _checked_mapping(
        form, request: FormRegistrationUpdateDto
    ) -> List[VariableMapping]:
        if len(request.variables) > MAX_VARIABLES:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_variables",
                f"At most {MAX_VARIABLES} variables.",
            )
        index = body_builder.variables_of(form)
        mapping: List[VariableMapping] = []
        keys = set()
        for item in request.variables:
            variable = index.get(item.source)
            if variable is None or variable.kind == "group_child":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "unknown_variable",
                    "This form has no such variable.",
                )
            if not variable.supported:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "variable_not_supported",
                    "This kind of question cannot be sent yet.",
                )
            key = item.key or re.sub(r"[^A-Za-z0-9_]", "_", item.source)
            if not body_builder.KEY_PATTERN.match(key) or key in keys:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_key",
                    "Names in the body are unique and use letters, digits and _ only.",
                )
            keys.add(key)
            mapping.append(VariableMapping(source=item.source, key=key))
        sources = {m.source for m in mapping}
        for source in request.transform_to_list:
            variable = index.get(source)
            if (
                source not in sources
                or variable is None
                or variable.type != "multiple_choice"
            ):
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_transform",
                    "Only a multiple choice question that is sent can be sent as a list.",
                )
        return mapping

    async def destination_for(
        self, workspace_id: RecordId, form_id: str
    ) -> Optional[Dict[str, str]]:
        """What the respondent's privacy panel names: the organisation of the
        service a submission is sent to, or None (switch off, no registration,
        nothing enabled). Derived from stored configuration, never from a
        request."""
        if not registration_enabled():
            return None
        # the page is addressed by form id or by its custom address
        association = (
            await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
        )
        if association is None:
            return None
        document = await self._registrations.get_for_form(
            workspace_id, association.form_id
        )
        if document is None or not document.enabled or not document.service_id:
            return None
        service = await self._services.get(workspace_id, document.service_id)
        if service is None:
            return None
        return {"organisation": service.organisation_name}

    # ----------------------------------------------------------- deliveries

    async def list_deliveries(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User,
        *,
        statuses: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DeliveryPageDto:
        await self._form_scope(user, Permission.RESPONSE_READ, workspace_id, form_id)
        limit = max(1, min(limit, 200))
        items = await self._deliveries.list_for_form(
            workspace_id, form_id, statuses=statuses, limit=limit, offset=max(0, offset)
        )
        total = await self._deliveries.count_for_form(workspace_id, form_id, statuses)
        return DeliveryPageDto(items=[_delivery_dto(d) for d in items], total=total)

    async def retry_delivery(
        self, workspace_id: RecordId, form_id: str, delivery_id: str, user: User
    ) -> DeliveryDto:
        await self._form_scope(user, Permission.FORM_EDIT, workspace_id, form_id)
        delivery = await self._deliveries.get_in_form(
            workspace_id, form_id, delivery_id
        )
        if delivery is None:
            raise _not_found()
        if delivery.status not in (DeliveryStatus.FAILED, DeliveryStatus.CANCELLED):
            raise _refused(
                HTTPStatus.CONFLICT,
                "not_retryable",
                "Only a delivery that failed can be tried again.",
            )
        delivery.status = DeliveryStatus.PENDING
        delivery.manual_attempts += 1
        delivery.next_attempt_at = None
        await self._deliveries.save(delivery)
        await self._queue(delivery)
        logger.info(
            "registration retry requested: workspace={} form={} delivery={} by={}",
            workspace_id,
            form_id,
            delivery.id,
            user.id,
        )
        return _delivery_dto(delivery)

    async def _queue(self, delivery: RegistrationDeliveryDocument) -> bool:
        try:
            await self._defer(str(delivery.id))
            return True
        except Exception as error:  # noqa: BLE001 - never fail a request over the queue
            logger.error(
                "could not queue registration delivery {} ({})",
                delivery.id,
                type(error).__name__,
            )
            return False

    # -------------------------------------------------------- on submission

    async def queue_for_submission(
        self,
        workspace_id: RecordId,
        form_id: str,
        response_id: str,
    ) -> Optional[str]:
        """Called after a response is stored. Writes the delivery row and
        queues the job; calls nothing external and never raises (the
        respondent's submission does not depend on it). Returns the delivery
        id, or None when nothing is to be sent."""
        try:
            if not registration_enabled():
                return None
            registration = await self._registrations.get_for_form(workspace_id, form_id)
            if (
                registration is None
                or not registration.enabled
                or not registration.service_id
            ):
                return None
            service = await self._services.get(workspace_id, registration.service_id)
            if service is None:
                return None
            delivery = await self._deliveries.create_if_absent(
                RegistrationDeliveryDocument(
                    workspace_id=workspace_id,
                    form_id=str(form_id),
                    response_id=str(response_id),
                    registration_id=str(registration.id),
                    service_id=str(service.id),
                    kind=service.kind,
                    service_name=service.name,
                )
            )
            if delivery is None:
                return None
            await self._queue(delivery)
            return str(delivery.id)
        except Exception as error:  # noqa: BLE001
            logger.error(
                "registration not queued: workspace={} form={} response={} ({})",
                workspace_id,
                form_id,
                response_id,
                type(error).__name__,
            )
            return None

    # ------------------------------------------------------------- the job

    async def run_delivery(self, delivery_id: str, *, job_attempt: int = 0) -> Outcome:
        """One attempt at one delivery (the ``register_submission`` job).
        ``job_attempt``: how many attempts this job had before (0 the first);
        the last one (``MAX_ATTEMPTS - 1``) fails the delivery instead of
        retrying."""
        final = job_attempt + 1 >= MAX_ATTEMPTS
        if not registration_enabled():
            # nothing leaves while the switch is off; a delivery that was
            # waiting for a retry goes back to pending (attempts kept), so the
            # sweep queues it once the switch is on again
            parked = await self._deliveries.get(delivery_id)
            if parked is not None and parked.status is DeliveryStatus.RETRYING:
                parked.status = DeliveryStatus.PENDING
                parked.next_attempt_at = None
                await self._deliveries.save(parked)
            return Outcome("skipped")
        delivery = await self._deliveries.claim(
            delivery_id, _OPEN_STATES, now=self._clock()
        )
        if delivery is None:
            return Outcome("skipped")
        try:
            return await self._attempt(delivery, job_attempt)
        except client.SendFailed as failed:
            return await self._failed(delivery, failed, job_attempt, final)
        except Exception as error:  # noqa: BLE001 - record, then retry or give up
            logger.error(
                "registration attempt crashed: delivery={} ({})",
                delivery.id,
                type(error).__name__,
            )
            return await self._settle(
                delivery, "internal_error", None, job_attempt, final, None
            )

    async def _failed(
        self, delivery, failed: client.SendFailed, job_attempt: int, final: bool
    ) -> Outcome:
        return await self._settle(
            delivery,
            failed.code,
            failed.http_status,
            job_attempt,
            final,
            failed.retry_after,
            permanent=failed.permanent,
        )

    async def _settle(
        self,
        delivery: RegistrationDeliveryDocument,
        code: str,
        http_status: Optional[int],
        job_attempt: int,
        final: bool,
        retry_after: Optional[int],
        permanent: bool = False,
    ) -> Outcome:
        delivery.last_error_code = code
        delivery.last_http_status = http_status
        if permanent or final:
            delivery.status = DeliveryStatus.FAILED
            delivery.next_attempt_at = None
            await self._deliveries.save(delivery)
            logger.warning(
                "registration failed: delivery={} response={} code={} http={} attempts={}",
                delivery.id,
                delivery.response_id,
                code,
                http_status,
                delivery.attempts,
            )
            return Outcome("failed")
        wait = max(
            RETRY_WAITS[min(job_attempt, len(RETRY_WAITS) - 1)], retry_after or 0
        )
        delivery.status = DeliveryStatus.RETRYING
        delivery.next_attempt_at = self._clock() + dt.timedelta(seconds=wait)
        await self._deliveries.save(delivery)
        logger.info(
            "registration will retry: delivery={} code={} http={} attempt={} in={}s",
            delivery.id,
            code,
            http_status,
            delivery.attempts,
            wait,
        )
        return Outcome("retrying", retry_after=retry_after, retry=True)

    async def _cancel(self, delivery, code: str) -> Outcome:
        delivery.status = DeliveryStatus.CANCELLED
        delivery.last_error_code = code
        delivery.next_attempt_at = None
        await self._deliveries.save(delivery)
        logger.info("registration cancelled: delivery={} code={}", delivery.id, code)
        return Outcome("cancelled")

    async def _attempt(
        self, delivery: RegistrationDeliveryDocument, job_attempt: int
    ) -> Outcome:
        workspace_id = delivery.workspace_id
        registration = await self._registrations.get(delivery.registration_id)
        if (
            registration is None
            or not registration.enabled
            or str(registration.workspace_id) != str(workspace_id)
            or str(registration.form_id) != str(delivery.form_id)
        ):
            return await self._cancel(delivery, "disabled")
        service = (
            await self._services.get(workspace_id, registration.service_id)
            if registration.service_id
            else None
        )
        if service is None:
            return await self._cancel(delivery, "disabled")
        response = await self._responses.workspace_response(
            workspace_id, delivery.response_id
        )
        if response is None or str(response.form_id) != str(delivery.form_id):
            # the submission is gone: so is its delivery record
            await self._deliveries.delete_by_ids([delivery.id])
            logger.info("registration dropped, response gone: delivery={}", delivery.id)
            return Outcome("gone")
        if service.kind is ServiceKind.OBJECTS_API:
            return await self._attempt_objects(
                delivery, registration, service, response
            )
        try:
            target = self._target(service, registration.path)
        except SecretUnreadable:
            raise client.SendFailed("secret_unreadable", permanent=True)
        form = await self._form_of_response(response)
        # the only place answers are decrypted: in memory, for this attempt
        answers, hidden_fields = self._open_answers(workspace_id, response)
        read = self._file_reader(workspace_id, delivery.form_id, delivery.response_id)
        loop = asyncio.get_running_loop()
        try:
            values, values_schema = await loop.run_in_executor(
                None,
                lambda: body_builder.build_values(
                    body_builder.variables_of(form),
                    [(v.source, v.key) for v in registration.variables],
                    answers,
                    hidden_fields,
                    registration.transform_to_list,
                    read,
                ),
            )
        except body_builder.FileTooLarge:
            raise client.SendFailed("too_large", permanent=True)
        except body_builder.FileMissing:
            raise client.SendFailed("file_missing", permanent=True)
        metadata, metadata_schema = body_builder.build_metadata(
            body_builder.FIXED_METADATA,
            public_reference=str(response.submission_uuid or response.response_id),
            form_version=str(response.form_version or ""),
            now=self._clock(),
        )
        payload = body_builder.serialize(
            values, values_schema, metadata, metadata_schema
        )
        del answers, hidden_fields, values
        status = await client.post_json(
            target, payload, idempotency_key=str(delivery.id)
        )
        return await self._delivered(delivery, status)

    async def _delivered(
        self,
        delivery: RegistrationDeliveryDocument,
        status: Optional[int],
        remote_id: Optional[str] = None,
        *,
        found: bool = False,
    ) -> Outcome:
        delivery.status = DeliveryStatus.DELIVERED
        delivery.delivered_at = self._clock()
        delivery.last_error_code = None
        delivery.last_http_status = status
        delivery.remote_id = remote_id
        delivery.next_attempt_at = None
        await self._deliveries.save(delivery)
        logger.info(
            "registration delivered: delivery={} response={} http={} attempts={}{}",
            delivery.id,
            delivery.response_id,
            status,
            delivery.attempts,
            " (found by lookup, nothing sent)" if found else "",
        )
        return Outcome("delivered")

    # ------------------------------------------------------------ objects api

    def _objects_target(self, service: RegistrationServiceDocument) -> client.Target:
        return client.Target(
            base_url=service.base_url,
            path=objects_api.RECORDS_PATH,
            auth=ServiceAuth.TOKEN.value,
            secret=unseal(
                self._crypto, service.workspace_id, service.id, service.secret_sealed
            ),
        )

    @staticmethod
    def _objects_settings(registration, service):
        """The stored settings of an Objects API form, checked again: stored
        configuration is not trusted for an address, a path or a version.
        Returns ``(object type URL, version, reference path, mapping)`` or
        raises a permanent ``config_invalid``."""
        invalid = client.SendFailed("config_invalid", permanent=True)
        try:
            url = objects_api.checked_object_type(
                registration.object_type_url, service.objecttypes_base_url
            )
        except objects_api.ObjectTypeRefused:
            raise invalid
        version = registration.object_type_version
        if not isinstance(version, int) or not (
            objects_api.MIN_VERSION <= version <= objects_api.MAX_VERSION
        ):
            raise invalid
        reference = list(
            registration.reference_path or objects_api.DEFAULT_REFERENCE_PATH
        )
        if objects_api.path_problem(reference):
            raise invalid
        mapping = []
        for item in registration.variables:
            if objects_api.path_problem(item.target_path) or any(
                objects_api.paths_conflict(m[1], item.target_path) for m in mapping
            ):
                raise invalid
            mapping.append((item.source, list(item.target_path)))
        if any(objects_api.paths_conflict(path, reference) for _s, path in mapping):
            raise invalid
        return url, version, reference, mapping

    async def _lookup(
        self,
        target: client.Target,
        object_type_url: str,
        reference_path,
        reference: str,
        start_at: str,
    ) -> Optional[str]:
        """Does the Objects API already hold the object of this delivery?
        ``None``: no. A string: yes, its UUID (``""`` if it has none we can
        read). An answer that is not clearly one of these is never a "no":
        a 4xx or an unreadable or mismatching answer raises ``lookup_failed``
        (permanent), a connection problem or 5xx raises its usual transient
        failure. The delivery is never sent blind after a failed lookup."""
        try:
            reply = await client.request(
                target,
                "GET",
                query=objects_api.lookup_query(
                    object_type_url, reference_path, reference, start_at
                ),
                extra_headers=objects_api.record_headers(),
                keep_reply=True,
            )
        except client.SendFailed as failed:
            if failed.code == "http_4xx" and failed.permanent:
                raise client.SendFailed(
                    "lookup_failed", permanent=True, http_status=failed.http_status
                )
            raise
        try:
            if reply.truncated:
                raise objects_api.LookupUnreadable()
            return objects_api.read_lookup(reply.body, reference_path, reference)
        except objects_api.LookupUnreadable:
            raise client.SendFailed(
                "lookup_failed", permanent=True, http_status=reply.status
            )

    async def _attempt_objects(
        self, delivery, registration, service, response
    ) -> Outcome:
        workspace_id = delivery.workspace_id
        try:
            target = self._objects_target(service)
        except SecretUnreadable:
            raise client.SendFailed("secret_unreadable", permanent=True)
        url, version, reference_path, mapping = self._objects_settings(
            registration, service
        )
        reference = objects_api.reference_for(delivery.id)
        submitted = response.created_at or self._clock()
        start_at = objects_api.amsterdam_date(submitted)
        # An earlier attempt (automatic, or a retry the creator asked for) may
        # have created the object and lost the reply: look before sending
        # again. Found: delivered, nothing is sent.
        if delivery.attempts > 1 or delivery.manual_attempts > 0:
            existing = await self._lookup(
                target, url, reference_path, reference, start_at
            )
            if existing is not None:
                return await self._delivered(
                    delivery, 200, existing or None, found=True
                )
        form = await self._form_of_response(response)
        index = body_builder.variables_of(form)
        for source, _path in mapping:
            variable = index.get(source)
            if variable is not None and (
                not variable.supported or variable.type == "file_upload"
            ):
                # a question mapped earlier became a file question: files are
                # never sent here
                raise client.SendFailed("config_invalid", permanent=True)
        # the only place answers are decrypted: in memory, for this attempt
        answers, hidden_fields = self._open_answers(workspace_id, response)

        def never_read(_file_id, _limit=0):
            raise body_builder.FileMissing()

        as_list = [
            source
            for source, _path in mapping
            if index.get(source) is not None and index[source].type == "multiple_choice"
        ]
        loop = asyncio.get_running_loop()
        try:
            values, _schema = await loop.run_in_executor(
                None,
                lambda: body_builder.build_values(
                    index,
                    [(source, ".".join(path)) for source, path in mapping],
                    answers,
                    hidden_fields,
                    as_list,
                    never_read,
                ),
            )
        except (body_builder.FileTooLarge, body_builder.FileMissing):
            raise client.SendFailed("config_invalid", permanent=True)
        by_path = {
            tuple(path): values[".".join(path)]
            for _source, path in mapping
            if ".".join(path) in values
        }
        try:
            payload = objects_api.build_record(
                object_type_url=url,
                version=version,
                values=by_path,
                reference_path=reference_path,
                reference=reference,
                start_at=start_at,
            )
        except ValueError:
            raise client.SendFailed("config_invalid", permanent=True)
        del answers, hidden_fields, values, by_path
        reply = await client.request(
            target,
            "POST",
            body=payload,
            extra_headers=objects_api.record_headers(),
            idempotency_key=str(delivery.id),
            keep_reply=True,
        )
        # the object exists now; its UUID is all we keep of the reply (none if
        # the reply was oversized or not what we expect: still delivered)
        remote_id = None if reply.truncated else objects_api.read_created(reply.body)
        return await self._delivered(delivery, reply.status, remote_id)

    async def check_connection(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> ServiceTestDto:
        """ "Check connection" of an Objects API form: the same lookup the job
        runs, for a reference that cannot exist. It must answer 200 with no
        results, which proves the address, the token, read permission and
        that the filter is applied; a second lookup with a deliberately
        malformed filter must be refused (400), which proves the server
        checks the filter at all (an empty object type would otherwise
        hide an ignored filter). Reads no records. Reports our codes only."""
        await self._form_scope(user, Permission.WORKSPACE_MANAGE, workspace_id, form_id)
        registration = await self._registrations.get_for_form(workspace_id, form_id)
        service = (
            await self._services.get(workspace_id, registration.service_id)
            if registration is not None and registration.service_id
            else None
        )
        if (
            registration is None
            or service is None
            or service.kind is not ServiceKind.OBJECTS_API
            or not registration.object_type_url
            or registration.object_type_version is None
        ):
            return ServiceTestDto(ok=False, code="not_configured")
        try:
            url, _version, reference_path, _mapping = self._objects_settings(
                registration, service
            )
            target = self._objects_target(service)
        except SecretUnreadable:
            return ServiceTestDto(ok=False, code="secret_unreadable")
        except client.SendFailed as failed:
            return ServiceTestDto(ok=False, code=failed.code)
        today = objects_api.amsterdam_date(self._clock())
        random_reference = str(uuid.uuid4())
        try:
            reply = await client.request(
                target,
                "GET",
                query=objects_api.lookup_query(
                    url, reference_path, random_reference, today
                ),
                extra_headers=objects_api.record_headers(),
                keep_reply=True,
            )
            if reply.truncated or not objects_api.check_reply_empty(reply.body):
                return ServiceTestDto(
                    ok=False,
                    code=(
                        "filter_not_supported"
                        if not reply.truncated
                        else "lookup_failed"
                    ),
                    http_status=reply.status,
                )
        except client.SendFailed as failed:
            return ServiceTestDto(
                ok=False,
                code="lookup_failed" if failed.code == "http_4xx" else failed.code,
                http_status=failed.http_status,
            )
        try:
            probe = await client.request(
                target,
                "GET",
                query=objects_api.malformed_filter_query(url),
                extra_headers=objects_api.record_headers(),
                keep_reply=False,
            )
            # a 2xx: the filter was not looked at
            return ServiceTestDto(
                ok=False, code="filter_not_supported", http_status=probe.status
            )
        except client.SendFailed as failed:
            if failed.code == "http_4xx" and failed.http_status == 400:
                return ServiceTestDto(ok=True, http_status=reply.status)
            return ServiceTestDto(
                ok=False,
                code="lookup_failed" if failed.code == "http_4xx" else failed.code,
                http_status=failed.http_status,
            )

    @staticmethod
    def _open_answers(workspace_id, response):
        """``(answers, hidden fields)`` decrypted with the key the answers
        were stored under. A value that does not decrypt is a permanent
        failure (``answers_unreadable``), never an empty body sent on."""
        import json

        from common.services.crypto_service import UnreadableCiphertext, crypto_service

        def open_value(value):
            if value is None:
                return None
            if isinstance(value, (bytes, str)):
                try:
                    return json.loads(
                        crypto_service.decrypt(
                            workspace_id=workspace_id,
                            form_id=response.form_id,
                            data=value,
                        )
                    )
                except (UnreadableCiphertext, ValueError):
                    raise client.SendFailed("answers_unreadable", permanent=True)
            return value

        answers = open_value(response.answers)
        hidden = open_value(response.hidden_fields)
        return (
            answers if isinstance(answers, dict) else {},
            hidden if isinstance(hidden, dict) else None,
        )

    async def _form_of_response(self, response):
        version = getattr(response, "form_version", None)
        form = None
        if version:
            form = await self._forms.get_form_by_by_version(response.form_id, version)
        return (
            form
            or await self._forms.get_latest_version_of_form(response.form_id)
            or await self._forms.get_form_document_by_id(str(response.form_id))
        )

    def _file_reader(self, workspace_id, form_id, response_id):
        from backend.app.services.form_response_service import is_plain_file_id

        def read(file_id: str, limit: int = body_builder.MAX_FILE_BYTES) -> bytes:
            if not is_plain_file_id(file_id):
                raise body_builder.FileMissing()
            # only this response's own folder: registration covers new
            # submissions, and an id the respondent chose never reaches
            # another object (no fallback to shared or bare keys)
            key = f"private/{workspace_id}/{form_id}/{response_id}/{file_id}"
            try:
                data = self._aws.read_object(
                    key, min(limit, body_builder.MAX_FILE_BYTES)
                )
            except ValueError:
                raise body_builder.FileTooLarge()
            if data is None:
                raise body_builder.FileMissing()
            return data

        return read

    # ---------------------------------------------------------------- sweeps

    async def redefer_pending(self) -> Dict[str, int]:
        """Queue again the deliveries whose job never got queued (a crash or
        queue trouble between the row and the job) and rescue ones whose
        worker died mid-attempt. Does nothing while the switch is off."""
        if not registration_enabled():
            return {"queued": 0, "rescued": 0}
        now = self._clock()
        queued = 0
        for delivery in await self._deliveries.list_pending_before(
            now - REDEFER_AFTER, SWEEP_BATCH
        ):
            queued += 1 if await self._queue(delivery) else 0
        rescued = 0
        # a retry whose job vanished: well past its time and never picked up
        for delivery in await self._deliveries.list_retrying_before(
            now - STUCK_AFTER - dt.timedelta(seconds=max(RETRY_WAITS)), SWEEP_BATCH
        ):
            delivery.status = DeliveryStatus.PENDING
            await self._deliveries.save(delivery)
            rescued += 1 if await self._queue(delivery) else 0
        for delivery in await self._deliveries.list_stuck_in_progress(
            now - STUCK_AFTER, SWEEP_BATCH
        ):
            delivery.status = DeliveryStatus.PENDING
            await self._deliveries.save(delivery)
            rescued += 1 if await self._queue(delivery) else 0
        return {"queued": queued, "rescued": rescued}

    async def sweep_orphans(self) -> Dict[str, int]:
        """Delete delivery rows of responses that no longer exist, form
        registrations of forms that were removed from their workspace and
        services of deleted workspaces. Does nothing while the switch is off."""
        if not registration_enabled():
            return {"deliveries": 0, "registrations": 0}
        deliveries = 0
        after = ""
        while True:
            batch = await self._deliveries.list_after(after, SWEEP_BATCH)
            if not batch:
                break
            after = str(batch[-1].id)
            gone = []
            for delivery in batch:
                if delivery.status is DeliveryStatus.IN_PROGRESS:
                    continue
                response = await self._responses.workspace_response(
                    delivery.workspace_id, delivery.response_id
                )
                if response is None:
                    gone.append(delivery.id)
            deliveries += await self._deliveries.delete_by_ids(gone)
        registrations = 0
        after = ""
        while True:
            batch = await self._registrations.list_all(SWEEP_BATCH, after)
            if not batch:
                break
            after = str(batch[-1].id)
            for registration in batch:
                if (
                    await self._workspace_forms.find_workspace_form(
                        registration.workspace_id, registration.form_id
                    )
                    is None
                ):
                    await self._deliveries.delete_by_registration(registration.id)
                    registrations += await self._registrations.delete(registration.id)
        return {"deliveries": deliveries, "registrations": registrations}

    # ------------------------------------------------------- deletion hooks

    async def delete_for_response(self, response_id: str) -> int:
        """A response was deleted: its delivery records go with it. Runs
        whatever the switch says (deleting data is always allowed)."""
        return await self._deliveries.delete_by_response_id(response_id)

    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        """A form was removed from a workspace: its registration and delivery
        records go (whatever the switch says)."""
        await self._deliveries.delete_for_form(workspace_id, form_id)
        await self._registrations.delete_for_form(workspace_id, form_id)

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        """Forms were deleted entirely (account deletion)."""
        await self._deliveries.delete_by_form_ids(form_ids)
        await self._registrations.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[RecordId]) -> None:
        """Workspaces were deleted: their services (and sealed secrets), form
        registrations and delivery records go with them."""
        await self._deliveries.delete_by_workspace_ids(workspace_ids)
        await self._registrations.delete_by_workspace_ids(workspace_ids)
        await self._services.delete_by_workspace_ids(workspace_ids)
