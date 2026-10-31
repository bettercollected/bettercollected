"""Email actions per form: configuration, the hook on submit, the delivery
job's logic, the log and the deletion hooks. See ``docs/email-actions.md``.

Rules this module keeps:

- Nothing external is called on a respondent's request path: submitting writes
  one log row per mail (and per channel) and queues one job each, by log id.
- A mail is built and sent in the backend's jobs worker, on the ``emails``
  queue, as the backend's role. No creator code is involved, and the actions
  executor's database role can neither see nor queue these jobs.
- Answers are decrypted only inside :meth:`EmailActionService.run_delivery`,
  reduced to the mapped questions and rendered into the message in memory:
  never stored, queued or logged.
- **Two channels.** ``team``: the template the form's admins wrote, to
  addresses of current members of the workspace (checked at save and again at
  send). ``respondent``: fixed wording to the address the respondent typed into
  an email question of this very submission: never a template, rate limited per
  address and per form, nothing to an address a caller supplies. No endpoint
  mails an address it is given: the only free address is the current user's own,
  for a test.
- A log row holds ids, a status, counters, timings and one of our error codes:
  no address, hash of one, domain, subject or body.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from common.clock import utcnow
from common.constants import MESSAGE_NOT_FOUND
from common.models.user import User
from common.records import RecordId
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.email_action import EmailTemplate, FormEmailActionDocument
from backend.app.schemas.webhook import (
    ActionCondition,
    ActionLogDocument,
    ActionType,
    LogStatus,
    WebhookField,
)
from backend.app.services import action_conditions
from backend.app.services.calculated_fields import hidden_calculation_ids
from backend.app.services.copy_recipient import normalize_address, rate_limit_key
from backend.app.services.email_actions import templates
from backend.app.services.email_actions.mode import (
    email_actions_enabled,
    mail_configured,
    refuse_when_not_configured,
    refuse_when_off,
)
from backend.app.services.email_actions.retry import (  # noqa: F401
    MAX_ATTEMPTS,
    EmailRetry,
    backoff_seconds,
)
from backend.app.services.email_actions.transport import (
    MailFailed,
    SmtpTransport,
    failure_of,
)
from backend.app.services.registration import body as body_builder
from backend.app.services.webhooks import payload
from backend.app.services.webhooks.service import FieldDto, VariableDto

LOG_RETENTION = dt.timedelta(days=30)
# a pending run without a queued job is queued again after this long
REDEFER_AFTER = dt.timedelta(minutes=2)
# an in-progress run that did not move for this long lost its worker
STUCK_AFTER = dt.timedelta(minutes=30)
SWEEP_BATCH = 200
MAX_ACTIONS_PER_FORM = 5
MAX_FIELDS = 50
MAX_TEAM = 5
NAME_MAX = 80
COPY_SUFFIX = ".copy"
CHANNEL_TEAM = "team"
CHANNEL_RESPONDENT = "respondent"
EVENT_SUBMISSION = "submission"
EVENT_TEST = "test"

# test mails (to the current user only)
TEST_SCOPE = "email_test"
TEST_PER_ACTION = 5  # per action and minute
TEST_PER_WORKSPACE = 20  # per workspace and minute
TEST_PER_USER = 20  # per user and hour
# the respondent's copy: counters are keyed hashes (services/rate_limiter.py)
COPY_FORM_SCOPE = "email_copy_form"
COPY_FORM_PER_HOUR = 600
COPY_ADDRESS_FORM_SCOPE = "email_copy_address_form"
COPY_ADDRESS_FORM_PER_HOUR = 3
COPY_ADDRESS_SCOPE = "email_copy_address"
COPY_ADDRESS_PER_HOUR = 10
# all the copies of one workspace together
COPY_WORKSPACE_SCOPE = "email_copy_workspace"
COPY_WORKSPACE_PER_HOUR = 1000
# the team's mails of one form: a submission flood cannot drain the instance's mail quota
TEAM_FORM_SCOPE = "email_team_form"
TEAM_FORM_PER_HOUR = 600
# a delivery counts against the limits once, however many attempts it takes
COUNTED_SCOPE = "email_counted"
COUNTED_TTL = dt.timedelta(hours=3)
HOUR = 3600
_OPEN_STATES = (LogStatus.PENDING, LogStatus.RETRYING)


@dataclass(frozen=True)
class Outcome:
    status: str
    retry: bool = False
    retry_after: Optional[int] = None


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class TemplateDto(_CamelModel):
    subject: str = Field(..., max_length=templates.SUBJECT_MAX)
    body: str = Field(..., max_length=templates.BODY_MAX)


class EmailActionDto(_CamelModel):
    id: str
    name: str
    enabled: bool
    en: TemplateDto
    nl: TemplateDto
    fields: List[FieldDto] = Field(default_factory=list)
    team_recipients: List[str] = Field(default_factory=list)
    respondent_field: Optional[str] = None
    condition: Optional[ActionCondition] = None
    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None


class EmailActionCreateDto(_CamelModel):
    name: str = Field(..., min_length=1, max_length=NAME_MAX)
    enabled: bool = True
    en: TemplateDto
    nl: TemplateDto
    fields: List[FieldDto] = Field(default_factory=list)
    team_recipients: List[str] = Field(default_factory=list, max_length=20)
    respondent_field: Optional[str] = Field(None, max_length=200)
    condition: Optional[ActionCondition] = None


class EmailActionUpdateDto(_CamelModel):
    name: Optional[str] = Field(None, min_length=1, max_length=NAME_MAX)
    enabled: Optional[bool] = None
    en: Optional[TemplateDto] = None
    nl: Optional[TemplateDto] = None
    fields: Optional[List[FieldDto]] = None
    team_recipients: Optional[List[str]] = Field(None, max_length=20)
    respondent_field: Optional[str] = Field(None, max_length=200)
    # an explicit null removes the condition (``model_fields_set`` tells)
    condition: Optional[ActionCondition] = None


class PreviewRequestDto(_CamelModel):
    language: str = "en"
    subject: str = Field("", max_length=templates.SUBJECT_MAX)
    body: str = Field("", max_length=templates.BODY_MAX)
    fields: List[FieldDto] = Field(default_factory=list)


class PreviewDto(_CamelModel):
    subject: str
    body: str


class TestRequestDto(_CamelModel):
    channel: str = CHANNEL_TEAM


class StatusDto(_CamelModel):
    enabled: bool
    configured: bool


class DeliveryDto(_CamelModel):
    id: str
    action_id: str
    channel: Optional[str] = None
    event: str
    response_id: Optional[str] = None
    status: str
    attempts: int
    last_error_code: Optional[str] = None
    first_attempt_at: Optional[dt.datetime] = None
    last_attempt_at: Optional[dt.datetime] = None
    next_attempt_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None


class DeliveryPageDto(_CamelModel):
    items: List[DeliveryDto]
    total: int


def _refused(status: HTTPStatus, code: str, message: str) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message})


def _invalid(code: str, message: str) -> HTTPException:
    return _refused(HTTPStatus.UNPROCESSABLE_ENTITY, code, message)


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, MESSAGE_NOT_FOUND)


def base_action_id(action_id: str) -> str:
    """The action a log row belongs to (the respondent's copy is logged under
    ``<action id>.copy``, so one response has one row per channel)."""
    return action_id[: -len(COPY_SUFFIX)] if action_id.endswith(COPY_SUFFIX) else action_id


def _action_dto(document: FormEmailActionDocument) -> EmailActionDto:
    return EmailActionDto(
        id=str(document.id),
        name=document.name,
        enabled=document.enabled,
        en=TemplateDto(**document.en.model_dump()),
        nl=TemplateDto(**document.nl.model_dump()),
        fields=[FieldDto(source=f.source, key=f.key) for f in document.fields],
        team_recipients=list(document.team_recipients),
        respondent_field=document.respondent_field,
        condition=document.condition,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _delivery_dto(document: ActionLogDocument) -> DeliveryDto:
    return DeliveryDto(
        id=str(document.id),
        action_id=base_action_id(document.action_id),
        channel=document.channel,
        event=document.event,
        response_id=document.response_id,
        status=document.status.value,
        attempts=document.attempts,
        last_error_code=document.last_error_code,
        first_attempt_at=document.first_attempt_at,
        last_attempt_at=document.last_attempt_at,
        next_attempt_at=document.next_attempt_at,
        finished_at=document.finished_at,
        created_at=document.created_at,
    )


async def _defer_job(log_id: str) -> None:
    """Queue ``deliver_email`` for a log row: the id is the only argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.deliver_email.configure(
            queueing_lock=f"deliver_email:{log_id}",
        ).defer_async(log_id=log_id)
    except AlreadyEnqueued:
        pass


def _plain(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def respondent_address(form: Any, source: Optional[str], answers: Any) -> Optional[str]:
    """The address in the answer to the email question ``source`` of this
    submission **as typed** (surrounding space removed), or None (no such
    question, not an email question, unanswered, or not one plain address).
    Only counting and comparing use the case-folded form."""
    if not source:
        return None
    variable = body_builder.variables_of(form).get(source)
    if variable is None or variable.type != "email" or variable.kind != "question":
        return None
    answer = _plain((answers or {}).get(source) if isinstance(answers, dict) else None)
    value = answer.get("email") or answer.get("text")
    return value.strip() if normalize_address(value) is not None else None


def _form_title(form: Any) -> str:
    title = getattr(form, "title", None)
    if not (isinstance(title, str) and title.strip()):
        welcome = getattr(form, "welcome_page", None)
        title = getattr(welcome, "title", None)
    return title if isinstance(title, str) else ""


def _when(created: Optional[dt.datetime]) -> str:
    if not created:
        return ""
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.timezone.utc)
    return created.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class EmailActionService:
    def __init__(
        self,
        *,
        authorization_service,
        action_repo,
        log_repo,
        workspace_form_repo,
        form_repo,
        form_response_service,
        copy_recipient_service,
        rate_limiter=None,
        transport=None,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ):
        self._authorization = authorization_service
        self._actions = action_repo
        self._logs = log_repo
        self._workspace_forms = workspace_form_repo
        self._forms = form_repo
        self._responses = form_response_service
        self._copy = copy_recipient_service
        self._limiter = rate_limiter
        self._transport = transport or SmtpTransport()
        self._defer = defer or _defer_job
        self._clock = clock

    # ------------------------------------------------------------ status

    @staticmethod
    def status() -> StatusDto:
        return StatusDto(enabled=email_actions_enabled(), configured=mail_configured())

    # ----------------------------------------------------- authorization

    async def _manage(self, user: User, workspace_id: RecordId, form_id: str) -> None:
        """Email actions send answers to people: owners and admins
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
                return await self._authorization.authorize(
                    user, permission, workspace_id, form_id=str(form_id)
                )
        await self._authorization.authorize(
            user, Permission.FORM_EDIT, workspace_id, form_id=str(form_id)
        )

    async def _rate_limit(self, scope, client, limit, window, message) -> None:
        if self._limiter is None:
            return
        verdict = await self._limiter.hit(scope, client, limit, window)
        if not verdict.allowed:
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS,
                content={"code": "rate_limited", "message": message},
                headers={"Retry-After": str(verdict.retry_after)},
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
                reason=("file_not_sent" if v.type == "file_upload" else v.reason),
            )
            for v in body_builder.variables_of(form).values()
            if v.kind != "group_child"
        ]

    async def list_actions(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> List[EmailActionDto]:
        await self._manage(user, workspace_id, form_id)
        return [
            _action_dto(d)
            for d in await self._actions.list_for_form(workspace_id, form_id)
        ]

    async def _action_of(self, workspace_id, form_id, action_id) -> FormEmailActionDocument:
        document = await self._actions.get(workspace_id, form_id, action_id)
        if document is None:
            raise _not_found()
        return document

    async def _checked_fields(self, form, items: List[FieldDto]) -> List[WebhookField]:
        if len(items) > MAX_FIELDS:
            raise _invalid("too_many_fields", f"At most {MAX_FIELDS} questions.")
        index = body_builder.variables_of(form)
        mapping: List[WebhookField] = []
        keys, sources = set(), set()
        for item in items:
            variable = index.get(item.source)
            if variable is None or variable.kind == "group_child":
                raise _invalid("unknown_variable", "This form has no such question.")
            if variable.type == "file_upload":
                raise _invalid("file_not_sent", "Files are not sent by email.")
            if not variable.supported:
                raise _invalid(
                    "variable_not_supported", "This kind of question cannot be sent yet."
                )
            key = item.key or re.sub(r"[^A-Za-z0-9_]", "_", item.source)
            if (
                not payload.KEY_PATTERN.match(key)
                or key in keys
                or item.source in sources
                or key in templates.BUILT_INS_BODY
            ):
                raise _invalid(
                    "invalid_key", "Names are unique and use letters, digits and _ only."
                )
            keys.add(key)
            sources.add(item.source)
            mapping.append(WebhookField(source=item.source, key=key))
        return mapping

    @staticmethod
    def _checked_templates(
        en: TemplateDto, nl: TemplateDto, fields: List[WebhookField]
    ) -> Tuple[EmailTemplate, EmailTemplate]:
        keys = {f.key for f in fields}
        checked = []
        for template in (en, nl):
            subject = templates.one_line(template.subject, templates.SUBJECT_MAX)
            body = templates.multi_line(template.body, templates.BODY_MAX)
            if not subject or not body:
                raise _invalid(
                    "template_missing", "Write a subject and a body in both languages."
                )
            for text, allowed in (
                (subject, keys | set(templates.BUILT_INS_SUBJECT)),
                (body, keys | set(templates.BUILT_INS_BODY)),
            ):
                problem = templates.placeholder_problem(text, allowed)
                if problem:
                    code, name = problem
                    raise _invalid(
                        code,
                        (
                            f"{{{{{name}}}}} is not a question of this action, nor one "
                            "of form_title, submitted_at and (in the body) answers."
                            if name
                            else "Use {{name}} for a placeholder; other braces are not allowed."
                        ),
                    )
            checked.append(EmailTemplate(subject=subject, body=body))
        return checked[0], checked[1]

    async def _checked_team(
        self, addresses: List[str], workspace_id: RecordId, form_id: str
    ) -> List[str]:
        typed: dict = {}  # case-folded -> as typed (trimmed): each mailbox once
        for value in addresses:
            folded = normalize_address(value)
            if folded is None:
                raise _invalid("invalid_recipient", "Use one plain email address per line.")
            typed.setdefault(folded, value.strip())
        if len(typed) > MAX_TEAM:
            raise _invalid("too_many_recipients", f"At most {MAX_TEAM} addresses.")
        allowed = await self._copy.allowed_among(list(typed.values()), workspace_id, form_id)
        if len(allowed) != len(typed):
            raise _invalid(
                "recipient_not_allowed",
                "A team address must be the address of a member of this workspace.",
            )
        return list(typed.values())

    @staticmethod
    def _checked_respondent_field(form, source: Optional[str]) -> Optional[str]:
        source = (source or "").strip() or None
        if source is None:
            return None
        variable = body_builder.variables_of(form).get(source)
        if variable is None or variable.type != "email" or variable.kind != "question":
            raise _invalid(
                "invalid_respondent_field", "Choose an email question of this form."
            )
        return source

    async def _validated(
        self,
        workspace_id,
        form_id,
        *,
        name,
        en,
        nl,
        fields,
        team,
        respondent_field,
        condition,
    ):
        form = await self._form_for_variables(form_id)
        mapping = await self._checked_fields(form, fields)
        en_t, nl_t = self._checked_templates(en, nl, mapping)
        team = await self._checked_team(team, workspace_id, form_id)
        respondent_field = self._checked_respondent_field(form, respondent_field)
        if not team and respondent_field is None:
            raise _invalid(
                "no_recipient", "Add a team address or an email question for a copy."
            )
        clean_name = templates.one_line(name, NAME_MAX)
        if not clean_name:
            raise _invalid("invalid_name", "Give the action a name.")
        return (
            clean_name,
            en_t,
            nl_t,
            mapping,
            team,
            respondent_field,
            action_conditions.checked_condition(form, condition),
        )

    def _record(self, event: str, document: FormEmailActionDocument, user: User, changed=None) -> None:
        logger.info(
            "email action {}: workspace={} form={} action={} by={} changed={}",
            event,
            document.workspace_id,
            document.form_id,
            document.id,
            user.id,
            changed or [],
        )

    async def create_action(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: EmailActionCreateDto,
        user: User,
    ) -> EmailActionDto:
        await self._manage(user, workspace_id, form_id)
        refuse_when_off()
        if request.enabled:
            refuse_when_not_configured()
        if (
            await self._actions.count_for_form(workspace_id, form_id)
            >= MAX_ACTIONS_PER_FORM
        ):
            raise _invalid(
                "too_many_actions", f"At most {MAX_ACTIONS_PER_FORM} email actions per form."
            )
        name, en, nl, fields, team, respondent_field, condition = await self._validated(
            workspace_id,
            form_id,
            name=request.name,
            en=request.en,
            nl=request.nl,
            fields=request.fields,
            team=request.team_recipients,
            respondent_field=request.respondent_field,
            condition=request.condition,
        )
        document = await self._actions.save(
            FormEmailActionDocument(
                workspace_id=workspace_id,
                form_id=str(form_id),
                name=name,
                enabled=request.enabled,
                en=en,
                nl=nl,
                fields=fields,
                team_recipients=team,
                respondent_field=respondent_field,
                condition=condition,
                created_by=str(user.id),
                updated_by=str(user.id),
            )
        )
        self._record("created", document, user)
        return _action_dto(document)

    async def update_action(
        self,
        workspace_id: RecordId,
        form_id: str,
        action_id: str,
        request: EmailActionUpdateDto,
        user: User,
    ) -> EmailActionDto:
        await self._manage(user, workspace_id, form_id)
        document = await self._action_of(workspace_id, form_id, action_id)
        enabling = request.enabled is True and not document.enabled
        if request.enabled is True:
            refuse_when_off()
            refuse_when_not_configured()
        sent = request.model_fields_set
        content_changed = bool(
            sent
            & {
                "name",
                "en",
                "nl",
                "fields",
                "team_recipients",
                "respondent_field",
                "condition",
            }
        )
        changed: List[str] = []
        if content_changed or enabling:
            # the whole stored action is checked again: an edit never leaves a
            # template naming a question that was unmapped, nor a team address
            # that is no longer a member's
            name, en, nl, fields, team, respondent_field, condition = (
                await self._validated(
                    workspace_id,
                    form_id,
                    name=request.name if "name" in sent else document.name,
                    en=request.en if "en" in sent else TemplateDto(**document.en.model_dump()),
                    nl=request.nl if "nl" in sent else TemplateDto(**document.nl.model_dump()),
                    fields=(
                        request.fields
                        if "fields" in sent and request.fields is not None
                        else [FieldDto(source=f.source, key=f.key) for f in document.fields]
                    ),
                    team=(
                        request.team_recipients
                        if "team_recipients" in sent and request.team_recipients is not None
                        else document.team_recipients
                    ),
                    respondent_field=(
                        request.respondent_field
                        if "respondent_field" in sent
                        else document.respondent_field
                    ),
                    condition=(
                        request.condition if "condition" in sent else document.condition
                    ),
                )
            )
            for label, old, new in (
                ("name", document.name, name),
                ("en", document.en, en),
                ("nl", document.nl, nl),
                ("fields", document.fields, fields),
                ("team_recipients", document.team_recipients, team),
                ("respondent_field", document.respondent_field, respondent_field),
                ("condition", document.condition, condition),
            ):
                if old != new:
                    changed.append(label)
            document.name, document.en, document.nl = name, en, nl
            document.fields, document.team_recipients = fields, team
            document.respondent_field, document.condition = respondent_field, condition
        if request.enabled is not None and request.enabled != document.enabled:
            document.enabled = request.enabled
            changed.append("enabled")
        if not changed:
            return _action_dto(document)
        document.updated_by = str(user.id)
        document.touch()
        document = await self._actions.save(document)
        self._record("updated", document, user, changed)
        return _action_dto(document)

    async def delete_action(
        self, workspace_id: RecordId, form_id: str, action_id: str, user: User
    ) -> None:
        await self._manage(user, workspace_id, form_id)
        document = await self._action_of(workspace_id, form_id, action_id)
        await self._actions.delete(workspace_id, form_id, action_id)
        # its waiting runs are cancelled by the job (the action is gone); the
        # log rows stay until their 30 days are over
        self._record("deleted", document, user)

    # --------------------------------------------------------------- preview

    async def preview(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: PreviewRequestDto,
        user: User,
    ) -> PreviewDto:
        """A template with made-up answers, rendered by the code that renders
        the real mail: what the editor shows is what is sent."""
        await self._manage(user, workspace_id, form_id)
        form = await self._form_for_variables(form_id)
        fields = await self._checked_fields(form, request.fields)
        language = request.language if request.language in templates.LANGUAGES else "en"
        template = TemplateDto(subject=request.subject or " ", body=request.body or " ")
        self._checked_templates(template, template, fields)
        entries = self._sample_entries(form, fields)
        title = _form_title(form) or "Example form"
        when = _when(self._clock())
        return PreviewDto(
            subject=templates.render(
                request.subject,
                entries,
                form_title=title,
                submitted_at=when,
                language=language,
                subject=True,
            ),
            body=templates.render(
                request.body,
                entries,
                form_title=title,
                submitted_at=when,
                language=language,
                subject=False,
            ),
        )

    @staticmethod
    def _entries(form, mapping, data: Dict[str, Any]) -> List[templates.Entry]:
        index = body_builder.variables_of(form)
        return [
            (key, index[source].label if source in index else key, data[key])
            for source, key in mapping
            if key in data
        ]

    def _sample_entries(self, form, fields: List[WebhookField]) -> List[templates.Entry]:
        mapping = [(f.source, f.key) for f in fields]
        return self._entries(form, mapping, payload.sample_data(form, mapping))

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
            workspace_id,
            form_id,
            statuses=wanted,
            limit=limit,
            offset=max(0, offset),
            action_type=ActionType.EMAIL,
        )
        total = await self._logs.count_for_form(
            workspace_id, form_id, wanted, ActionType.EMAIL
        )
        return DeliveryPageDto(items=[_delivery_dto(d) for d in items], total=total)

    async def purge_expired(self) -> int:
        """The daily purge (also done by the webhooks queue's, which covers
        every action type): runs older than the retention are deleted."""
        return await self._logs.purge_before(self._clock() - LOG_RETENTION)

    # ------------------------------------------------------- privacy panel

    async def destination_for(
        self, workspace_id: RecordId, form_id: str
    ) -> Optional[Dict[str, bool]]:
        """What the respondent's privacy panel says: ``{"team": bool, "copy":
        bool}`` (answers are also emailed to the form's team; a copy goes to the
        respondent), or None (switch off, nothing enabled). Derived from stored
        configuration, never from a request, and a conditional action counts
        (it may run). ``form_id`` may be the form's custom address."""
        if not email_actions_enabled():
            return None
        association = (
            await self._workspace_forms.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
        )
        if association is None:
            return None
        team = copy = False
        for action in await self._actions.list_for_form(
            workspace_id, association.form_id
        ):
            if not action.enabled:
                continue
            team = team or bool(action.team_recipients)
            copy = copy or bool(action.respondent_field)
        return {"team": team, "copy": copy} if (team or copy) else None

    # ------------------------------------------------------------ test mail

    async def send_test(
        self,
        workspace_id: RecordId,
        form_id: str,
        action_id: str,
        request: TestRequestDto,
        user: User,
    ) -> DeliveryDto:
        """Send the action's mail, with made-up answers, to the **current
        user's own address and nobody else**; the outcome is logged (ids and a
        code). Rate limited per action, workspace and user."""
        await self._manage(user, workspace_id, form_id)
        refuse_when_off()
        refuse_when_not_configured()
        document = await self._action_of(workspace_id, form_id, action_id)
        channel = request.channel if request.channel in (CHANNEL_TEAM, CHANNEL_RESPONDENT) else CHANNEL_TEAM
        if channel == CHANNEL_RESPONDENT and not document.respondent_field:
            raise _invalid("no_copy", "This action sends no copy to the respondent.")
        sub = getattr(user, "sub", None)
        if normalize_address(sub) is None:
            raise _invalid("no_address", "Your account has no email address.")
        address = sub.strip()
        message = "Too many test mails; try again later."
        await self._rate_limit(TEST_SCOPE, f"{workspace_id}:{document.id}", TEST_PER_ACTION, 60, message)
        await self._rate_limit(TEST_SCOPE, str(workspace_id), TEST_PER_WORKSPACE, 60, message)
        await self._rate_limit(TEST_SCOPE, f"user:{user.id}", TEST_PER_USER, HOUR, message)
        form = await self._form_for_variables(form_id)
        language = templates.language_of(form)
        entries = self._sample_entries(form, document.fields)
        title = _form_title(form) or "Example form"
        when = _when(self._clock())
        if channel == CHANNEL_TEAM:
            template = document.nl if language == "nl" else document.en
            subject = templates.render(
                template.subject, entries, form_title=title, submitted_at=when,
                language=language, subject=True,
            )
            body = templates.render(
                template.body, entries, form_title=title, submitted_at=when,
                language=language, subject=False,
            )
        else:
            subject, body = templates.render_respondent(
                entries, submitted_at=when, language=language
            )
        now = self._clock()
        log = await self._logs.create(
            ActionLogDocument(
                workspace_id=workspace_id,
                form_id=str(form_id),
                action_type=ActionType.EMAIL,
                action_id=str(document.id) + (COPY_SUFFIX if channel == CHANNEL_RESPONDENT else ""),
                event=EVENT_TEST,
                channel=channel,
                status=LogStatus.IN_PROGRESS,
                attempts=1,
                first_attempt_at=now,
                last_attempt_at=now,
            )
        )
        try:
            await self._transport.send(
                recipients=[address],
                subject=templates.subject_line("[Test] " + subject),
                body=body,
            )
            log.status = LogStatus.DELIVERED
        except Exception as error:  # noqa: BLE001
            failed = failure_of(error)
            log.status = LogStatus.FAILED
            log.last_error_code = failed.code
        log.finished_at = self._clock()
        await self._logs.save_existing(log)
        logger.info(
            "email test: workspace={} form={} action={} by={} status={} code={}",
            workspace_id, form_id, document.id, user.id, log.status.value, log.last_error_code,
        )
        return _delivery_dto(log)

    # -------------------------------------------------------- on submission

    async def _queue(self, log: ActionLogDocument) -> bool:
        try:
            await self._defer(str(log.id))
            return True
        except Exception as error:  # noqa: BLE001 - never fail a request over the queue
            logger.error(
                "could not queue email delivery {} ({})", log.id, type(error).__name__
            )
            return False

    def _new_log(
        self, workspace_id, form_id, action_id: str, response_id: str, channel: str, **extra
    ) -> ActionLogDocument:
        return ActionLogDocument(
            workspace_id=workspace_id,
            form_id=str(form_id),
            action_type=ActionType.EMAIL,
            action_id=action_id,
            event=EVENT_SUBMISSION,
            response_id=str(response_id),
            channel=channel,
            **extra,
        )

    async def queue_for_submission(
        self,
        workspace_id: RecordId,
        form_id: str,
        response_id: str,
        *,
        form: Any = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Called after a response is stored. For each enabled action whose
        condition holds on ``answers`` (the submitted, normalised ones, in
        memory only): one log row per mail and one job each, by log id. Calls
        nothing external and never raises (the submission does not depend on
        it). A condition that does not hold writes a ``cancelled`` row with its
        code and no job. Returns the ids of the rows queued."""
        queued: List[str] = []
        try:
            if not email_actions_enabled():
                return queued
            for action in await self._actions.list_for_form(workspace_id, form_id):
                if not action.enabled:
                    continue
                runs, code = action_conditions.conditions_hold(
                    action.condition, form, answers or {}
                )
                if not runs:
                    await self._logs.create_if_absent(
                        self._new_log(
                            workspace_id, form_id, str(action.id), response_id, CHANNEL_TEAM,
                            status=LogStatus.CANCELLED,
                            last_error_code=code,
                            finished_at=self._clock(),
                        )
                    )
                    continue
                rows = []
                if action.team_recipients:
                    rows.append((str(action.id), CHANNEL_TEAM))
                if action.respondent_field and respondent_address(
                    form, action.respondent_field, answers
                ):
                    rows.append((str(action.id) + COPY_SUFFIX, CHANNEL_RESPONDENT))
                for action_id, channel in rows:
                    log = await self._logs.create_if_absent(
                        self._new_log(workspace_id, form_id, action_id, response_id, channel)
                    )
                    if log is None:
                        continue
                    await self._queue(log)
                    queued.append(str(log.id))
        except Exception as error:  # noqa: BLE001
            logger.error(
                "email actions not queued: workspace={} form={} response={} ({})",
                workspace_id, form_id, response_id, type(error).__name__,
            )
        return queued

    # ------------------------------------------------------------- the job

    async def run_delivery(self, log_id: str, *, job_attempt: int = 0) -> Outcome:
        """One attempt at one delivery (the ``deliver_email`` job). The attempt
        number is the log row's own count; the ``MAX_ATTEMPTS``-th fails the
        delivery instead of retrying."""
        if not email_actions_enabled():
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
        if log is None or log.action_type is not ActionType.EMAIL:
            return Outcome("skipped")
        job_attempt = log.attempts - 1
        final = log.attempts >= MAX_ATTEMPTS
        try:
            return await self._attempt(log)
        except MailFailed as failed:
            return await self._settle(log, failed.code, job_attempt, final, failed.permanent)
        except Exception as error:  # noqa: BLE001 - record, then retry or give up
            logger.error(
                "email attempt crashed: delivery={} ({})", log.id, type(error).__name__
            )
            return await self._settle(log, "internal_error", job_attempt, final, False)

    async def _settle(
        self, log: ActionLogDocument, code: str, job_attempt: int, final: bool, permanent: bool
    ) -> Outcome:
        log.last_error_code = code
        if permanent or final:
            log.status = LogStatus.FAILED
            log.next_attempt_at = None
            log.finished_at = self._clock()
            await self._logs.save_existing(log)
            logger.warning(
                "email failed: delivery={} code={} attempts={}", log.id, code, log.attempts
            )
            return Outcome("failed")
        wait = backoff_seconds(job_attempt)
        log.status = LogStatus.RETRYING
        log.next_attempt_at = self._clock() + dt.timedelta(seconds=wait)
        await self._logs.save_existing(log)
        logger.info(
            "email will retry: delivery={} code={} attempt={} in={}s",
            log.id, code, log.attempts, wait,
        )
        return Outcome("retrying", retry=True)

    async def _cancel(self, log: ActionLogDocument, code: str) -> Outcome:
        log.status = LogStatus.CANCELLED
        log.last_error_code = code
        log.next_attempt_at = None
        log.finished_at = self._clock()
        await self._logs.save_existing(log)
        logger.info("email cancelled: delivery={} code={}", log.id, code)
        return Outcome("cancelled")

    async def _action_for(self, log: ActionLogDocument) -> Optional[FormEmailActionDocument]:
        action = await self._actions.get(
            log.workspace_id, log.form_id, base_action_id(log.action_id)
        )
        return action if action is not None and action.enabled else None

    async def _attempt(self, log: ActionLogDocument) -> Outcome:
        action = await self._action_for(log)
        if action is None or log.event != EVENT_SUBMISSION or not log.response_id:
            return await self._cancel(log, "disabled")
        if not mail_configured():
            raise MailFailed("mail_not_configured", permanent=True)
        response = await self._responses.workspace_response(
            log.workspace_id, str(log.response_id)
        )
        if response is None or str(response.form_id) != str(log.form_id):
            # erasure wins over a late send: the submission is gone, so is the row
            await self._logs.delete_by_response_id(
                log.workspace_id, log.form_id, str(log.response_id)
            )
            logger.info("email dropped, response gone: delivery={}", log.id)
            return Outcome("gone")
        form = await self._form_of_response(response)
        # the only place answers are decrypted: in memory, for this attempt
        answers, hidden_fields = self._open_answers(log.workspace_id, response)
        language = templates.language_of(form)
        respondent = log.channel == CHANNEL_RESPONDENT
        mapping = [(f.source, f.key) for f in action.fields]
        if respondent:
            # a copy to the respondent leaves out calculations kept from them
            hidden = hidden_calculation_ids(form)
            mapping = [(s, k) for s, k in mapping if s not in hidden]
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None, lambda: payload.build_data(form, mapping, answers, hidden_fields)
        )
        entries = self._entries(form, mapping, data)
        title = _form_title(form)
        when = _when(getattr(response, "created_at", None))
        if respondent:
            address = respondent_address(form, action.respondent_field, answers)
            if address is None:
                return await self._cancel(log, "no_address")
            if await self._first_attempt(log) and not await self._copy_within_limits(
                log.workspace_id, log.form_id, address
            ):
                return await self._cancel(log, "rate_limited")
            recipients = [address]
            subject, body = templates.render_respondent(
                entries, submitted_at=when, language=language
            )
        else:
            recipients = await self._copy.allowed_among(
                action.team_recipients, log.workspace_id, log.form_id
            )
            if not recipients:
                return await self._cancel(log, "recipient_not_allowed")
            if await self._first_attempt(log) and not await self._team_within_limit(
                log.form_id
            ):
                return await self._cancel(log, "rate_limited")
            template = action.nl if language == "nl" else action.en
            subject = templates.render(
                template.subject, entries, form_title=title, submitted_at=when,
                language=language, subject=True,
            )
            body = templates.render(
                template.body, entries, form_title=title, submitted_at=when,
                language=language, subject=False,
            )
        del answers, hidden_fields, data, entries
        stopped = await self._still_wanted(log)
        if stopped is not None:
            return stopped
        await self._transport.send(recipients=recipients, subject=subject, body=body)
        log.status = LogStatus.DELIVERED
        log.finished_at = self._clock()
        log.last_error_code = None
        log.next_attempt_at = None
        await self._logs.save_existing(log)
        logger.info("email delivered: delivery={} attempts={}", log.id, log.attempts)
        return Outcome("delivered")

    async def _first_attempt(self, log: ActionLogDocument) -> bool:
        """True the first time a delivery asks, False on every later attempt
        (a one-time claim on its id, whichever replica): a mail counts against
        the limits once, so a retried mail is not cancelled as ``rate_limited``
        by its own earlier attempt."""
        if self._limiter is None:
            return True
        return await self._limiter.claim(
            COUNTED_SCOPE, str(log.id), self._clock() + COUNTED_TTL
        )

    async def _within(self, checks) -> bool:
        """``checks``: ``(scope, client, limit)`` triples, narrowest first.
        True, and every counter goes up by one, only when **all** have room;
        each is checked and counted in one locked step (``admit``), so parallel
        mails cannot overshoot a budget, and a mail that one budget refuses
        gives back what the narrower ones admitted: a denied attempt counts
        against none of the budgets (someone over one limit cannot use up a
        victim's mailbox or the workspace's budget)."""
        if self._limiter is None:
            return True
        admitted = []
        for scope, client, limit in checks:
            verdict = await self._limiter.admit(scope, client, limit, HOUR)
            if not verdict.allowed:
                for done_scope, done_client in admitted:
                    await self._limiter.release(done_scope, done_client, HOUR)
                return False
            admitted.append((scope, client))
        return True

    async def _team_within_limit(self, form_id: str) -> bool:
        return await self._within(((TEAM_FORM_SCOPE, str(form_id), TEAM_FORM_PER_HOUR),))

    async def _copy_within_limits(self, workspace_id, form_id: str, address: str) -> bool:
        """The respondent's copy: per workspace, per form, per mailbox and
        form, per mailbox. A mailbox is :func:`rate_limit_key` (case, ``+tag``,
        Gmail dots and the spelling of the domain do not make a new one); the
        address itself is mailed as typed. The counters are keyed hashes: none
        names an address."""
        key = rate_limit_key(address) or address.casefold()
        return await self._within(
            (
                (COPY_ADDRESS_SCOPE, key, COPY_ADDRESS_PER_HOUR),
                (COPY_ADDRESS_FORM_SCOPE, f"{form_id}:{key}", COPY_ADDRESS_FORM_PER_HOUR),
                (COPY_FORM_SCOPE, str(form_id), COPY_FORM_PER_HOUR),
                (COPY_WORKSPACE_SCOPE, str(workspace_id), COPY_WORKSPACE_PER_HOUR),
            )
        )

    async def _still_wanted(self, log: ActionLogDocument) -> Optional[Outcome]:
        """Right before a send: ``None`` when it may go on, else the outcome
        that stops it: the row, the submission (a deletion during the attempt
        stops the send) and the action (still there, still on) all exist."""
        if await self._logs.get(log.id) is None:
            return Outcome("gone")
        response = await self._responses.workspace_response(
            log.workspace_id, str(log.response_id)
        )
        if response is None or str(response.form_id) != str(log.form_id):
            await self._logs.delete_by_response_id(
                log.workspace_id, log.form_id, str(log.response_id)
            )
            return Outcome("gone")
        if await self._action_for(log) is None:
            return await self._cancel(log, "disabled")
        return None

    @staticmethod
    def _open_answers(workspace_id, response):
        """``(answers, hidden fields)`` decrypted with the key the answers were
        stored under. A value that does not decrypt is a permanent failure
        (``answers_unreadable``), never an empty mail sent on."""
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
                    raise MailFailed("answers_unreadable", permanent=True)
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
        """Queue again the runs whose job never got queued and rescue ones whose
        worker died mid-attempt. Does nothing while the switch is off."""
        if not email_actions_enabled():
            return {"queued": 0, "rescued": 0}
        now = self._clock()
        queued = 0
        for log in await self._logs.list_pending_before(
            now - REDEFER_AFTER, SWEEP_BATCH, ActionType.EMAIL
        ):
            queued += 1 if await self._queue(log) else 0
        rescued = 0
        stuck = (
            (LogStatus.IN_PROGRESS, now - STUCK_AFTER),
            (
                LogStatus.RETRYING,
                now - STUCK_AFTER - dt.timedelta(seconds=backoff_seconds(MAX_ATTEMPTS)),
            ),
        )
        for status, before in stuck:
            for log in await self._logs.list_stuck(
                status, before, SWEEP_BATCH, ActionType.EMAIL
            ):
                log.status = LogStatus.PENDING
                if await self._logs.save_existing(log):
                    rescued += 1 if await self._queue(log) else 0
        return {"queued": queued, "rescued": rescued}

    # --------------------------------------------------------- deletion hooks

    async def forget_address(self, address: Any, workspace_id: Any = None) -> int:
        """Erasure of a person's address from the team lists: removed from
        every email action's team (of ``workspace_id`` when given, else of every
        workspace) when they leave a workspace or their account is deleted. An
        action left with no recipient at all (no team, no copy question) is
        switched off. Returns how many actions changed. Compared case-folded."""
        folded = normalize_address(address)
        if folded is None:
            return 0
        changed = 0
        for action in await self._actions.list_with_team_address(folded, workspace_id):
            kept = [a for a in action.team_recipients if normalize_address(a) != folded]
            if len(kept) == len(action.team_recipients):
                continue
            action.team_recipients = kept
            if not kept and not action.respondent_field:
                action.enabled = False
            action.touch()
            await self._actions.save(action)
            changed += 1
            logger.info(
                "email action: a team address was erased: workspace={} form={} action={}",
                action.workspace_id, action.form_id, action.id,
            )
        return changed

    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        await self._actions.delete_for_form(workspace_id, form_id)
        await self._logs.delete_for_form(workspace_id, form_id)

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        await self._actions.delete_by_form_ids(form_ids)
        await self._logs.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[RecordId]) -> None:
        await self._actions.delete_by_workspace_ids(workspace_ids)
        await self._logs.delete_by_workspace_ids(workspace_ids)
