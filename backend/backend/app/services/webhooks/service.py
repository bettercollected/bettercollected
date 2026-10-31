"""Self-service webhooks per form: configuration, the hook on submit, the
delivery job's logic, the action log and its purge, and the deletion hooks.
See ``docs/webhooks.md``.

Rules this module keeps:

- Nothing external is called on a respondent's request path: submitting writes
  one log row per enabled webhook and queues one job each (by log id) and
  returns.
- A webhook runs in the backend's jobs worker, on the ``webhooks`` queue, as the
  backend's role. No creator code is involved, and the actions executor's
  database role can neither see nor queue these jobs (``jobs/schema.py``).
- Answers are decrypted only inside :meth:`WebhookService.run_delivery`, reduced
  to the mapped questions, built into the body in memory and never stored,
  logged or queued.
- A log row holds ids, a status, counters, timings and one of our error codes:
  no answer, no body, no address, no secret and no text of the destination.
- Every object is loaded with its workspace and form in the query.
- Logs name ids, counts and our codes; never answers, bodies, addresses, secrets
  or the destination's text.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import secrets as token
from dataclasses import dataclass
from http import HTTPStatus
from typing import Awaitable, Callable, Dict, List, Optional

from common.clock import utcnow
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User
from common.records import RecordId
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.webhook import (
    ActionLogDocument,
    FormWebhookDocument,
    LogStatus,
    WebhookAuditDocument,
    WebhookField,
)
from backend.app.services.registration import body as body_builder
from backend.app.services.registration import client
from backend.app.services.registration.secrets import SecretUnreadable, seal, unseal
from backend.app.services.webhooks import guard, payload, sender
from backend.app.services.webhooks.mode import refuse_when_off, webhooks_enabled
from backend.app.services.webhooks.retry import (  # noqa: F401
    MAX_ATTEMPTS,
    WebhookRetry,
    backoff_seconds,
)

# how long the log keeps a run (the daily purge deletes older rows)
LOG_RETENTION = dt.timedelta(days=30)
# a pending run without a queued job is queued again after this long
REDEFER_AFTER = dt.timedelta(minutes=2)
# an in-progress run that did not move for this long lost its worker
STUCK_AFTER = dt.timedelta(minutes=30)
SWEEP_BATCH = 200
MAX_WEBHOOKS_PER_FORM = 5
MAX_FIELDS = 100
TEST_SCOPE = "webhook_test"
TEST_PER_WINDOW = 5
TEST_WINDOW_SECONDS = 60
_OPEN_STATES = (LogStatus.PENDING, LogStatus.RETRYING)
SECRET_PREFIX = "whsec_"


@dataclass(frozen=True)
class Outcome:
    status: str
    retry_after: Optional[int] = None
    retry: bool = False


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class FieldDto(_CamelModel):
    source: str = Field(..., min_length=1, max_length=200)
    key: Optional[str] = Field(None, max_length=64)


class WebhookDto(_CamelModel):
    id: str
    url: str
    host: str
    enabled: bool
    fields: List[FieldDto] = Field(default_factory=list)
    # the secret itself is returned once, by create and rotate, never here
    has_secret: bool
    secret_set_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None


class WebhookCreatedDto(WebhookDto):
    """Create and rotate: the only response that carries the secret."""

    secret: str = Field(..., repr=False)


class WebhookCreateDto(_CamelModel):
    url: str = Field(..., min_length=1, max_length=2048)
    fields: List[FieldDto] = Field(default_factory=list)
    enabled: bool = True


class WebhookUpdateDto(_CamelModel):
    url: Optional[str] = Field(None, min_length=1, max_length=2048)
    fields: Optional[List[FieldDto]] = None
    enabled: Optional[bool] = None


class VariableDto(_CamelModel):
    source: str
    label: str
    type: str
    supported: bool
    reason: Optional[str] = None


class DeliveryDto(_CamelModel):
    id: str
    action_type: str
    webhook_id: str
    host: Optional[str] = None
    event: str
    response_id: Optional[str] = None
    status: str
    attempts: int
    last_error_code: Optional[str] = None
    last_http_status: Optional[int] = None
    last_duration_ms: Optional[int] = None
    first_attempt_at: Optional[dt.datetime] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None


class DeliveryPageDto(_CamelModel):
    items: List[DeliveryDto]
    total: int


class AuditDto(_CamelModel):
    id: str
    webhook_id: str
    event: str
    actor_id: Optional[str] = None
    changed: List[str] = Field(default_factory=list)
    host: Optional[str] = None
    created_at: Optional[dt.datetime] = None


class StatusDto(_CamelModel):
    enabled: bool


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message})


def _not_found(message: str = MESSAGE_NOT_FOUND) -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, message)


def _webhook_dto(document: FormWebhookDocument) -> WebhookDto:
    return WebhookDto(
        id=str(document.id),
        url=document.url,
        host=document.host,
        enabled=document.enabled,
        fields=[FieldDto(source=f.source, key=f.key) for f in document.fields],
        has_secret=bool(document.secret_sealed),
        secret_set_at=document.secret_set_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _delivery_dto(
    document: ActionLogDocument, hosts: Dict[str, str]
) -> DeliveryDto:
    return DeliveryDto(
        id=str(document.id),
        action_type=document.action_type.value,
        webhook_id=document.action_id,
        host=hosts.get(document.action_id),
        event=document.event,
        response_id=document.response_id,
        status=document.status.value,
        attempts=document.attempts,
        last_error_code=document.last_error_code,
        last_http_status=document.last_http_status,
        last_duration_ms=document.last_duration_ms,
        first_attempt_at=document.first_attempt_at,
        last_attempt_at=document.last_attempt_at,
        next_attempt_at=document.next_attempt_at,
        finished_at=document.finished_at,
        created_at=document.created_at,
    )


async def _defer_job(log_id: str) -> None:
    """Queue ``deliver_webhook`` for a log row: the id is the only argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.deliver_webhook.configure(
            # no ``lock`` (a hard-killed worker would leave one behind); one
            # send at a time is the atomic claim in ``run_delivery``
            queueing_lock=f"deliver_webhook:{log_id}",
        ).defer_async(log_id=log_id)
    except AlreadyEnqueued:
        pass


def new_secret() -> str:
    return SECRET_PREFIX + token.token_urlsafe(32)


class WebhookService:
    def __init__(
        self,
        *,
        authorization_service,
        webhook_repo,
        log_repo,
        audit_repo,
        workspace_form_repo,
        form_repo,
        form_response_service,
        crypto,
        rate_limiter=None,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ):
        self._authorization = authorization_service
        self._webhooks = webhook_repo
        self._logs = log_repo
        self._audit = audit_repo
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._responses = form_response_service
        self._crypto = crypto
        self._limiter = rate_limiter
        self._defer = defer or _defer_job
        self._clock = clock

    # ------------------------------------------------------------ status

    @staticmethod
    def status() -> StatusDto:
        return StatusDto(enabled=webhooks_enabled())

    # ----------------------------------------------------- authorization

    async def _manage(self, user: User, workspace_id: RecordId, form_id: str) -> None:
        """Webhooks send answers to a third party: owners and admins
        (``workspace.manage``), for a form of this workspace."""
        await self._authorization.authorize(
            user, Permission.WORKSPACE_MANAGE, workspace_id, form_id=str(form_id)
        )

    async def _staff(self, user: User, workspace_id: RecordId, form_id: str) -> None:
        """The log holds ids and codes only: whoever edits the form or reads
        the audit log may look at it."""
        held = await self._authorization.effective_permissions(user, workspace_id)
        for permission in (Permission.FORM_EDIT, Permission.AUDIT_READ):
            if permission in held:
                # 404 when the form is not this workspace's, as every other read
                return await self._authorization.authorize(
                    user, permission, workspace_id, form_id=str(form_id)
                )
        # neither: 403
        await self._authorization.authorize(
            user, Permission.FORM_EDIT, workspace_id, form_id=str(form_id)
        )

    # ------------------------------------------------------- configuration

    async def _form_for_variables(self, form_id):
        latest = await self._forms.get_latest_version_of_form(form_id)
        return latest or await self._forms.get_form_document_by_id(str(form_id))

    async def list_variables(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> List[VariableDto]:
        await self._manage(user, workspace_id, form_id)
        form = await self._form_for_variables(form_id)
        return [
            VariableDto(
                source=v.source,
                label=v.label,
                type=v.type,
                supported=v.supported and v.type != "file_upload",
                reason=(
                    "file_not_sent"
                    if v.type == "file_upload"
                    else v.reason
                ),
            )
            for v in body_builder.variables_of(form).values()
            if v.kind != "group_child"
        ]

    async def list_webhooks(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> List[WebhookDto]:
        await self._manage(user, workspace_id, form_id)
        return [
            _webhook_dto(d)
            for d in await self._webhooks.list_for_form(workspace_id, form_id)
        ]

    async def _checked_url(self, url: str) -> tuple[str, str]:
        try:
            return await guard.check_destination(url)
        except guard.DestinationRefused as refused:
            messages = {
                "not_https": "Use a https:// address.",
                "not_allowed": "That address is not a public one.",
                "unreachable": "That address does not resolve.",
            }
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                refused.code,
                messages.get(
                    refused.code,
                    "Use a https:// address without a port, user name or fragment.",
                ),
            )

    async def _checked_fields(self, form, items: List[FieldDto]) -> List[WebhookField]:
        if len(items) > MAX_FIELDS:
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_fields",
                f"At most {MAX_FIELDS} questions.",
            )
        index = body_builder.variables_of(form)
        mapping: List[WebhookField] = []
        keys = set()
        sources = set()
        for item in items:
            variable = index.get(item.source)
            if variable is None or variable.kind == "group_child":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "unknown_variable",
                    "This form has no such question.",
                )
            if variable.type == "file_upload":
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "file_not_sent",
                    "Files are not sent by webhooks.",
                )
            if not variable.supported:
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "variable_not_supported",
                    "This kind of question cannot be sent yet.",
                )
            key = item.key or re.sub(r"[^A-Za-z0-9_]", "_", item.source)
            if (
                not payload.KEY_PATTERN.match(key)
                or key in keys
                or item.source in sources
            ):
                raise _refused(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_key",
                    "Names are unique and use letters, digits and _ only.",
                )
            keys.add(key)
            sources.add(item.source)
            mapping.append(WebhookField(source=item.source, key=key))
        return mapping

    async def _record(
        self,
        document: FormWebhookDocument,
        event: str,
        user: User,
        changed: Optional[List[str]] = None,
    ) -> None:
        """One audit entry (names of what changed, never values) and a log line
        with ids."""
        await self._audit.add(
            WebhookAuditDocument(
                workspace_id=document.workspace_id,
                form_id=document.form_id,
                webhook_id=str(document.id),
                event=event,
                actor_id=str(user.id),
                changed=changed or [],
                host=document.host,
            )
        )
        logger.info(
            "webhook {}: workspace={} form={} webhook={} by={} changed={}",
            event,
            document.workspace_id,
            document.form_id,
            document.id,
            user.id,
            changed or [],
        )

    async def create_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: WebhookCreateDto,
        user: User,
    ) -> WebhookCreatedDto:
        await self._manage(user, workspace_id, form_id)
        refuse_when_off()
        if (
            await self._webhooks.count_for_form(workspace_id, form_id)
            >= MAX_WEBHOOKS_PER_FORM
        ):
            raise _refused(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "too_many_webhooks",
                f"At most {MAX_WEBHOOKS_PER_FORM} webhooks per form.",
            )
        url, host = await self._checked_url(request.url)
        fields = await self._checked_fields(
            await self._form_for_variables(form_id), request.fields
        )
        secret = new_secret()
        document = FormWebhookDocument(
            workspace_id=workspace_id,
            form_id=str(form_id),
            url=url,
            host=host,
            enabled=request.enabled,
            fields=fields,
            created_by=str(user.id),
            updated_by=str(user.id),
        )
        document.ensure_id()
        document.secret_sealed = seal(self._crypto, workspace_id, document.id, secret)
        document.secret_set_at = self._clock()
        document = await self._webhooks.save(document)
        await self._record(document, "created", user)
        return WebhookCreatedDto(**_webhook_dto(document).model_dump(), secret=secret)

    async def _webhook_of(self, workspace_id, form_id, webhook_id) -> FormWebhookDocument:
        document = await self._webhooks.get(workspace_id, form_id, webhook_id)
        if document is None:
            raise _not_found()
        return document

    async def update_webhook(
        self,
        workspace_id: RecordId,
        form_id: str,
        webhook_id: str,
        request: WebhookUpdateDto,
        user: User,
    ) -> WebhookDto:
        await self._manage(user, workspace_id, form_id)
        document = await self._webhook_of(workspace_id, form_id, webhook_id)
        enabling = request.enabled is True
        if enabling:
            refuse_when_off()
        changed: List[str] = []
        if request.url is not None:
            url, host = await self._checked_url(request.url)
            if url != document.url:
                document.url, document.host = url, host
                changed.append("url")
        elif enabling and not document.enabled:
            # switched on: the address is checked again, not trusted from when
            # it was saved
            await self._checked_url(document.url)
        if request.fields is not None:
            fields = await self._checked_fields(
                await self._form_for_variables(form_id), request.fields
            )
            if fields != document.fields:
                document.fields = fields
                changed.append("fields")
        if request.enabled is not None and request.enabled != document.enabled:
            document.enabled = request.enabled
            changed.append("enabled")
        if not changed:
            return _webhook_dto(document)
        document.updated_by = str(user.id)
        document.touch()
        document = await self._webhooks.save(document)
        if changed == ["enabled"]:
            await self._record(
                document, "enabled" if document.enabled else "disabled", user
            )
        else:
            await self._record(document, "updated", user, changed)
        return _webhook_dto(document)

    async def rotate_secret(
        self, workspace_id: RecordId, form_id: str, webhook_id: str, user: User
    ) -> WebhookCreatedDto:
        await self._manage(user, workspace_id, form_id)
        document = await self._webhook_of(workspace_id, form_id, webhook_id)
        secret = new_secret()
        document.secret_sealed = seal(self._crypto, workspace_id, document.id, secret)
        document.secret_set_at = self._clock()
        document.updated_by = str(user.id)
        document.touch()
        document = await self._webhooks.save(document)
        await self._record(document, "secret_rotated", user)
        return WebhookCreatedDto(**_webhook_dto(document).model_dump(), secret=secret)

    async def delete_webhook(
        self, workspace_id: RecordId, form_id: str, webhook_id: str, user: User
    ) -> None:
        await self._manage(user, workspace_id, form_id)
        document = await self._webhook_of(workspace_id, form_id, webhook_id)
        await self._webhooks.delete(workspace_id, form_id, webhook_id)
        # its pending runs are cancelled by the job (the webhook is gone); the
        # log rows stay until their 30 days are over
        await self._record(document, "deleted", user)

    # -------------------------------------------------------------- the log

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
        await self._staff(user, workspace_id, form_id)
        limit = max(1, min(limit, 200))
        wanted = [s for s in (statuses or []) if s in {x.value for x in LogStatus}]
        if statuses and not wanted:
            return DeliveryPageDto(items=[], total=0)
        items = await self._logs.list_for_form(
            workspace_id, form_id, statuses=wanted, limit=limit, offset=max(0, offset)
        )
        total = await self._logs.count_for_form(workspace_id, form_id, wanted)
        hosts = {
            str(w.id): w.host
            for w in await self._webhooks.list_for_form(workspace_id, form_id)
        }
        return DeliveryPageDto(
            items=[_delivery_dto(d, hosts) for d in items], total=total
        )

    async def list_audit(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> List[AuditDto]:
        await self._staff(user, workspace_id, form_id)
        return [
            AuditDto(
                id=str(a.id),
                webhook_id=a.webhook_id,
                event=a.event,
                actor_id=a.actor_id,
                changed=a.changed,
                host=a.host,
                created_at=a.created_at,
            )
            for a in await self._audit.list_for_form(workspace_id, form_id)
        ]

    async def purge_expired(self) -> int:
        """The daily purge: runs older than the retention are deleted."""
        return await self._logs.purge_before(self._clock() - LOG_RETENTION)

    # ------------------------------------------------------- privacy panel

    async def destination_for(
        self, workspace_id: RecordId, form_id: str
    ) -> Optional[Dict[str, List[str]]]:
        """What the respondent's privacy panel names: the hosts answers are
        also sent to, or None (switch off, nothing enabled). Derived from stored
        configuration, never from a request. ``form_id`` may be the form's
        custom address."""
        if not webhooks_enabled():
            return None
        association = (
            await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
        )
        if association is None:
            return None
        hosts: List[str] = []
        for hook in await self._webhooks.list_for_form(
            workspace_id, association.form_id
        ):
            if hook.enabled and hook.host not in hosts:
                hosts.append(hook.host)
        return {"hosts": hosts} if hosts else None

    # ------------------------------------------------------------ test event

    async def send_test(
        self, workspace_id: RecordId, form_id: str, webhook_id: str, user: User
    ) -> DeliveryDto:
        """A real, signed delivery of made-up data for the mapped questions, so
        an admin can see the receiver work. Rate limited per workspace."""
        await self._manage(user, workspace_id, form_id)
        refuse_when_off()
        document = await self._webhook_of(workspace_id, form_id, webhook_id)
        if self._limiter is not None:
            verdict = await self._limiter.hit(
                TEST_SCOPE, str(workspace_id), TEST_PER_WINDOW, TEST_WINDOW_SECONDS
            )
            if not verdict.allowed:
                raise HTTPException(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    content={
                        "code": "rate_limited",
                        "message": "Too many test events; try again later.",
                    },
                    headers={"Retry-After": str(verdict.retry_after)},
                )
        log = await self._logs.create(
            ActionLogDocument(
                workspace_id=workspace_id,
                form_id=str(form_id),
                action_id=str(document.id),
                event=payload.EVENT_TEST,
            )
        )
        await self._queue(log)
        return _delivery_dto(log, {str(document.id): document.host})

    # -------------------------------------------------------- on submission

    async def _queue(self, log: ActionLogDocument) -> bool:
        try:
            await self._defer(str(log.id))
            return True
        except Exception as error:  # noqa: BLE001 - never fail a request over the queue
            logger.error(
                "could not queue webhook delivery {} ({})",
                log.id,
                type(error).__name__,
            )
            return False

    async def queue_for_submission(
        self, workspace_id: RecordId, form_id: str, response_id: str
    ) -> List[str]:
        """Called after a response is stored. Writes one log row per enabled
        webhook and queues a job for each; calls nothing external and never
        raises (the respondent's submission does not depend on it). Returns the
        log ids."""
        queued: List[str] = []
        try:
            if not webhooks_enabled():
                return queued
            for hook in await self._webhooks.list_for_form(workspace_id, form_id):
                if not hook.enabled:
                    continue
                log = await self._logs.create_if_absent(
                    ActionLogDocument(
                        workspace_id=workspace_id,
                        form_id=str(form_id),
                        action_id=str(hook.id),
                        event=payload.EVENT_SUBMISSION,
                        response_id=str(response_id),
                    )
                )
                if log is None:
                    continue
                await self._queue(log)
                queued.append(str(log.id))
        except Exception as error:  # noqa: BLE001
            logger.error(
                "webhooks not queued: workspace={} form={} response={} ({})",
                workspace_id,
                form_id,
                response_id,
                type(error).__name__,
            )
        return queued

    # ------------------------------------------------------------- the job

    async def run_delivery(self, log_id: str, *, job_attempt: int = 0) -> Outcome:
        """One attempt at one delivery (the ``deliver_webhook`` job).
        ``job_attempt``: how many attempts this job had before (0 the first);
        the last one (``MAX_ATTEMPTS - 1``) fails the delivery instead of
        retrying."""
        final = job_attempt + 1 >= MAX_ATTEMPTS
        if not webhooks_enabled():
            # nothing leaves while the switch is off; a delivery that was
            # waiting for a retry goes back to pending (attempts kept), so the
            # sweep queues it once the switch is on again
            parked = await self._logs.get(log_id)
            if parked is not None and parked.status is LogStatus.RETRYING:
                parked.status = LogStatus.PENDING
                parked.next_attempt_at = None
                await self._logs.save_existing(parked)
            return Outcome("skipped")
        log = await self._logs.claim(log_id, _OPEN_STATES, now=self._clock())
        if log is None:
            return Outcome("skipped")
        try:
            return await self._attempt(log, job_attempt)
        except client.SendFailed as failed:
            return await self._settle(
                log,
                failed.code,
                failed.http_status,
                sender.duration_of(failed),
                job_attempt,
                final,
                failed.retry_after,
                permanent=failed.permanent,
            )
        except Exception as error:  # noqa: BLE001 - record, then retry or give up
            logger.error(
                "webhook attempt crashed: delivery={} ({})",
                log.id,
                type(error).__name__,
            )
            return await self._settle(
                log, "internal_error", None, None, job_attempt, final, None
            )

    async def _settle(
        self,
        log: ActionLogDocument,
        code: str,
        http_status: Optional[int],
        duration_ms: Optional[int],
        job_attempt: int,
        final: bool,
        retry_after: Optional[int],
        permanent: bool = False,
    ) -> Outcome:
        log.last_error_code = code
        log.last_http_status = http_status
        log.last_duration_ms = duration_ms
        if permanent or final:
            log.status = LogStatus.FAILED
            log.next_attempt_at = None
            log.finished_at = self._clock()
            await self._logs.save_existing(log)
            logger.warning(
                "webhook failed: delivery={} code={} http={} attempts={}",
                log.id,
                code,
                http_status,
                log.attempts,
            )
            return Outcome("failed")
        wait = max(backoff_seconds(job_attempt), retry_after or 0)
        log.status = LogStatus.RETRYING
        log.next_attempt_at = self._clock() + dt.timedelta(seconds=wait)
        await self._logs.save_existing(log)
        logger.info(
            "webhook will retry: delivery={} code={} http={} attempt={} in={}s",
            log.id,
            code,
            http_status,
            log.attempts,
            wait,
        )
        return Outcome("retrying", retry_after=retry_after, retry=True)

    async def _cancel(self, log: ActionLogDocument, code: str) -> Outcome:
        log.status = LogStatus.CANCELLED
        log.last_error_code = code
        log.next_attempt_at = None
        log.finished_at = self._clock()
        await self._logs.save_existing(log)
        logger.info("webhook cancelled: delivery={} code={}", log.id, code)
        return Outcome("cancelled")

    async def _hook_for(self, log: ActionLogDocument) -> Optional[FormWebhookDocument]:
        hook = await self._webhooks.get(log.workspace_id, log.form_id, log.action_id)
        if hook is None:
            return None
        # a test goes to a webhook that is still switched off; a submission
        # does not
        if not hook.enabled and log.event != payload.EVENT_TEST:
            return None
        return hook

    async def _attempt(self, log: ActionLogDocument, job_attempt: int) -> Outcome:
        hook = await self._hook_for(log)
        if hook is None:
            return await self._cancel(log, "disabled")
        try:
            secret = unseal(self._crypto, hook.workspace_id, hook.id, hook.secret_sealed)
        except SecretUnreadable:
            secret = None
        if not secret:
            raise client.SendFailed("secret_unreadable", permanent=True)
        mapping = [(f.source, f.key) for f in hook.fields]
        response_id: Optional[str] = None
        submitted_at: Optional[str] = None
        if log.event == payload.EVENT_TEST:
            form = await self._forms.get_latest_version_of_form(
                RecordId(str(log.form_id))
            ) or await self._forms.get_form_document_by_id(str(log.form_id))
            data = payload.sample_data(form, mapping)
        else:
            response = await self._responses.workspace_response(
                log.workspace_id, str(log.response_id)
            )
            if response is None or str(response.form_id) != str(log.form_id):
                # erasure wins over a late send: the submission is gone, so is
                # the row
                await self._logs.delete_by_response_id(str(log.response_id))
                logger.info("webhook dropped, response gone: delivery={}", log.id)
                return Outcome("gone")
            form = await self._form_of_response(response)
            # the only place answers are decrypted: in memory, for this attempt
            answers, hidden_fields = self._open_answers(log.workspace_id, response)
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                lambda: payload.build_data(form, mapping, answers, hidden_fields),
            )
            response_id = str(response.response_id)
            created = getattr(response, "created_at", None)
            submitted_at = (
                created.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if created
                else None
            )
            del answers, hidden_fields
        body = payload.serialize(
            event=log.event,
            delivery_id=str(log.id),
            form_id=str(log.form_id),
            response_id=response_id,
            submitted_at=submitted_at,
            data=data,
        )
        del data
        stopped = await self._still_wanted(log)
        if stopped is not None:
            return stopped
        sent = await sender.post(
            hook.url,
            secret,
            body,
            delivery_id=str(log.id),
            event=log.event,
            timestamp=int(self._clock().timestamp()),
        )
        log.status = LogStatus.DELIVERED
        log.finished_at = self._clock()
        log.last_error_code = None
        log.last_http_status = sent.http_status
        log.last_duration_ms = sent.duration_ms
        log.next_attempt_at = None
        await self._logs.save_existing(log)
        logger.info(
            "webhook delivered: delivery={} http={} ms={} attempts={}",
            log.id,
            sent.http_status,
            sent.duration_ms,
            log.attempts,
        )
        return Outcome("delivered")

    async def _still_wanted(self, log: ActionLogDocument) -> Optional[Outcome]:
        """Right before a send: ``None`` when it may go on, else the outcome
        that stops it: the row, the submission (a deletion during the attempt
        stops the send) and the webhook (still there, still on for a
        submission) all exist."""
        if await self._logs.get(log.id) is None:
            return Outcome("gone")
        if log.event != payload.EVENT_TEST:
            response = await self._responses.workspace_response(
                log.workspace_id, str(log.response_id)
            )
            if response is None or str(response.form_id) != str(log.form_id):
                await self._logs.delete_by_response_id(str(log.response_id))
                return Outcome("gone")
        if await self._hook_for(log) is None:
            return await self._cancel(log, "disabled")
        return None

    @staticmethod
    def _open_answers(workspace_id, response):
        """``(answers, hidden fields)`` decrypted with the key the answers were
        stored under. A value that does not decrypt is a permanent failure
        (``answers_unreadable``), never an empty body sent on."""
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

    # ---------------------------------------------------------------- sweeps

    async def redefer_pending(self) -> Dict[str, int]:
        """Queue again the runs whose job never got queued (a crash or queue
        trouble between the row and the job) and rescue ones whose worker died
        mid-attempt. Does nothing while the switch is off."""
        if not webhooks_enabled():
            return {"queued": 0, "rescued": 0}
        now = self._clock()
        queued = 0
        for log in await self._logs.list_pending_before(now - REDEFER_AFTER, SWEEP_BATCH):
            queued += 1 if await self._queue(log) else 0
        rescued = 0
        stuck = (
            (LogStatus.IN_PROGRESS, now - STUCK_AFTER),
            # a retry whose job vanished: well past its time and never picked up
            (
                LogStatus.RETRYING,
                now - STUCK_AFTER - dt.timedelta(seconds=backoff_seconds(MAX_ATTEMPTS)),
            ),
        )
        for status, before in stuck:
            for log in await self._logs.list_stuck(status, before, SWEEP_BATCH):
                log.status = LogStatus.PENDING
                if await self._logs.save_existing(log):
                    rescued += 1 if await self._queue(log) else 0
        return {"queued": queued, "rescued": rescued}

    # --------------------------------------------------------- deletion hooks

    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        await self._webhooks.delete_for_form(workspace_id, form_id)
        await self._logs.delete_for_form(workspace_id, form_id)
        await self._audit.delete_for_form(workspace_id, form_id)

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        await self._webhooks.delete_by_form_ids(form_ids)
        await self._logs.delete_by_form_ids(form_ids)
        await self._audit.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[RecordId]) -> None:
        await self._webhooks.delete_by_workspace_ids(workspace_ids)
        await self._logs.delete_by_workspace_ids(workspace_ids)
        await self._audit.delete_by_workspace_ids(workspace_ids)
