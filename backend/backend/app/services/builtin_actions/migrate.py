"""Moving the built-in actions onto the backend's own features (4.4).

The form actions ``send_webhook``, ``send_to_slack``, ``send_to_discord``,
``creator_copy_mail`` and ``responder_copy_mail`` become a webhook (format
``legacy_list``, ``slack``, ``discord``) or an email action of the form; the
Google Sheets action stays an action and is marked, so the backend's own runner
runs it (``sheets.py``). Used by ``python -m backend.migrate_builtins``.

Rules this module keeps (docs and the operator steps say the same):

- **Nothing is sent and no switch is turned on.** A webhook or email action is
  only created (disabled if the old action was disabled), and the old entry is
  disabled and marked ``migrated_to`` in the same transaction as the new row, so
  a submission never delivers twice. The old entry is kept for ``rollback``.
- **One transaction per form**, with the form's row locked, re-reading the form
  after the checks (the checks resolve host names: no lock is held while they
  run) and refusing a form that changed meanwhile.
- **Idempotent**: ids are derived from the form and the action, an entry that
  carries the mark is left alone, a re-run changes nothing.
- **The destination rules are the webhooks'**: https, 443, public addresses
  (resolved now), Slack and Discord only to their own hosts. An address that
  fails is not moved and is reported, never relaxed. A copy recipient who is not
  a current member of the workspace is not moved. A mail server of a workspace or
  a form is not moved (the instance's ``MAIL_*`` is used) and is reported.
- **Secrets never leave this process.** The address is read, checked and sealed
  here; no address, recipient, secret or answer is printed, logged or queued:
  reports hold counts and codes only.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.clock import utcnow
from common.ids import RecordId
from common.records.codec import row_values
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError

from backend.app.schemas.email_action import EmailTemplate, FormEmailActionDocument
from backend.app.schemas.webhook import FormWebhookDocument, WebhookAuditDocument
from backend.app.services.builtin_actions import sheets
from backend.app.services.builtin_actions.links import responses_link
from backend.app.services.email_actions import defaults as email_defaults
from backend.app.services.email_actions.mode import email_actions_enabled, mail_configured
from backend.app.services.registration.secrets import SecretUnreadable, seal, unseal
from backend.app.services.webhooks import formats, guard
from backend.app.services.webhooks.mode import webhooks_enabled
from backend.app.services.webhooks.sealing import seal_url, unseal_url
from backend.app.services.webhooks.service import MAX_WEBHOOKS_PER_FORM, new_secret
from backend.config import settings
from backend.db.models import FormRow, WorkspaceFormRow

MIGRATED_VIA = "migrated_builtin"
TEMPORAL_TIMEOUT_SECONDS = 30
# recorded on a moved entry (``migrated_to``) and in the webhook's audit row when
# the open-workflow check was skipped by ``--temporal-drained``
CHECK_SKIPPED_KEY = "temporal_check"
CHECK_SKIPPED_VALUE = "skipped_by_operator"
MAX_EMAIL_ACTIONS_PER_FORM = 5
SMTP_NAMES = {"server", "port", "username", "password", "sender"}

# the built-in action's name -> what it becomes and where its address is
WEBHOOK_OF = {
    "send_webhook": (formats.LEGACY_LIST, "Webhook URL"),
    "send_to_slack": (formats.SLACK, "Slack Webhook URL"),
    "send_to_discord": (formats.DISCORD, "Discord Webhook URL"),
}
EMAIL_OF = {"creator_copy_mail": "Receiving Mail Address", "responder_copy_mail": None}
SHEETS = sheets.SHEETS_ACTION
BUILTINS = (*WEBHOOK_OF, *EMAIL_OF, SHEETS)


def target_id(kind: str, form_id: str, action_id: str) -> RecordId:
    """The id of what an action becomes: derived, so a re-run finds it."""
    digest = hashlib.sha256(f"builtin:{kind}:{form_id}:{action_id}".encode()).hexdigest()
    return RecordId(digest[:24])


def _norm(name: Any) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


class TemporalUnreachable(Exception):
    """The Temporal server could not be asked for the open workflows."""

    def __init__(self, reason: str = "unreachable"):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Item:
    form_id: str
    workspace_id: str
    entry: Any  # the form's action entry
    name: str  # the built-in action's name
    kind: str  # webhook | email | sheets
    enabled: bool
    format: Optional[str] = None
    address: Optional[str] = None  # normalised, never reported
    host: Optional[str] = None
    recipient: Optional[str] = None  # never reported
    dropped: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    skipped: Optional[str] = None  # a code: left as it is, not a blocker

    @property
    def action_id(self) -> str:
        return str(self.entry.id)

    @property
    def movable(self) -> bool:
        return not self.blockers and not self.skipped


@dataclass
class Report:
    counts: Dict[str, int] = field(default_factory=dict)

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def blocked(self) -> int:
        # "blocked.<code>" counts; "blocked.<code>.<action>" is the same one by action
        return sum(
            v for k, v in self.counts.items() if k.startswith("blocked.") and k.count(".") == 1
        )

    def as_json(self) -> str:
        return json.dumps(dict(sorted(self.counts.items())), indent=1)


class BuiltinMigration:
    def __init__(
        self,
        *,
        form_repo,
        action_repo,
        workspace_repo,
        workspace_form_repo,
        webhook_repo,
        email_repo,
        audit_repo,
        copy_recipient_service,
        crypto,
        clock=utcnow,
        temporal_open_runs=None,
        temporal_override: bool = False,
    ):
        self._forms = form_repo
        self._actions = action_repo
        self._workspaces = workspace_repo
        self._workspace_forms = workspace_form_repo
        self._webhooks = webhook_repo
        self._emails = email_repo
        self._audit = audit_repo
        self._copy = copy_recipient_service
        self._crypto = crypto
        self._clock = clock
        # ``async (form_id | None) -> [workflow ids]``: the open ``run_action_code``
        # workflows, when the executor's ``run_action`` is on Temporal (None: it is
        # on the Postgres queue, which is looked at directly). The override (the
        # operator's ``--temporal-drained``) is only for a Temporal that cannot be
        # reached: the check is then skipped, loudly
        self._temporal_open_runs = temporal_open_runs
        self._temporal_override = temporal_override
        self._actions_by_id: Optional[Dict[str, Any]] = None
        self.check_skipped = False

    # ------------------------------------------------------------ reading

    async def _builtin_actions(self) -> Dict[str, Any]:
        if self._actions_by_id is None:
            self._actions_by_id = {
                str(a.id): a
                for a in await self._actions.get_all_actions()
                if getattr(a, "predefined", None) and a.name in BUILTINS
            }
        return self._actions_by_id

    async def form_ids(self, workspace: Optional[str] = None) -> List[str]:
        """The ids of the forms that have an action on submit, by id."""
        query = select(FormRow.form_id).where(
            func.coalesce(
                func.jsonb_array_length(FormRow.doc["actions"]["on_submit"]), 0
            )
            > 0
        )
        if workspace:
            query = query.where(
                FormRow.form_id.in_(
                    select(WorkspaceFormRow.form_id).where(
                        WorkspaceFormRow.workspace_id == str(workspace)
                    )
                )
            )
        async with self._forms._session() as session:
            return sorted((await session.execute(query)).scalars().all())

    async def _workspace_of(self, form_id: str) -> Optional[str]:
        link = await self._workspace_forms.one(WorkspaceFormRow.form_id == str(form_id))
        return str(link.workspace_id) if link else None

    async def _layers(self, form, action, workspace_id: str):
        """The action's parameters and secrets, layered action < workspace <
        form, plus the names the workspace and the form set."""
        from backend.app.exceptions import HTTPException as AppHTTPException
        from backend.app.models.workspace import WorkspaceRequestWithActionDto

        try:
            raw = await self._workspaces.get_workspace_with_action_by_id(
                workspace_id=RecordId(workspace_id), action_id=action.id
            )
            workspace = WorkspaceRequestWithActionDto(**raw) if raw is not None else None
        except AppHTTPException:
            workspace = None
        if workspace is None:
            return None
        key = str(action.id)
        w_params = (workspace.parameters or {}).get(key)
        f_params = (form.parameters or {}).get(key)
        parameters = sheets._layer(action.parameters, w_params, f_params)
        overrides = {_norm(i.name) for i in [*(w_params or []), *(f_params or [])]}
        w_secrets = (workspace.secrets or {}).get(key)
        f_secrets = (form.secrets or {}).get(key)
        overrides |= {_norm(i.name) for i in [*(w_secrets or []), *(f_secrets or [])]}
        return parameters, overrides, workspace

    async def plan_form(self, form_id: str) -> List[Item]:
        """What each built-in action entry of the form would become, with its
        blockers. Reads (and resolves host names); writes nothing."""
        form = await self._forms.get_form_document_by_id(str(form_id))
        if form is None:
            return []
        builtins = await self._builtin_actions()
        workspace_id = await self._workspace_of(form_id)
        items: List[Item] = []
        for entry in (form.actions or {}).get("on_submit") or []:
            action = builtins.get(str(entry.id))
            if action is None:
                continue  # an action of someone's own: not ours
            enabled = bool(entry.enabled)
            kind = (
                "webhook" if action.name in WEBHOOK_OF
                else "email" if action.name in EMAIL_OF else "sheets"
            )
            item = Item(str(form_id), workspace_id or "", entry, action.name, kind, enabled)
            items.append(item)
            if entry.migrated_to:
                item.skipped = "already_moved"
                continue
            if getattr(form, "builder_version", None) != "v2":
                item.skipped = "form_v1"  # these never ran: nothing to move
                continue
            if not workspace_id:
                item.blockers.append("workspace_unavailable")
                continue
            layers = await self._layers(form, action, workspace_id)
            if layers is None:
                item.blockers.append("workspace_unavailable")
                continue
            parameters, overrides, _workspace = layers
            if kind == "sheets":
                continue
            if overrides & SMTP_NAMES and kind == "email":
                item.dropped.append("mail_server")
            if kind == "webhook":
                await self._plan_webhook(item, parameters)
            else:
                await self._plan_email(item, parameters)
        # the caps, counting what the form has and what would be added
        await self._plan_caps(form_id, workspace_id, items)
        return items

    async def _plan_webhook(self, item: Item, parameters: Dict[str, str]) -> None:
        item.format, name = WEBHOOK_OF[item.name]
        url = parameters.get(name)
        if not url:
            item.blockers.append("address_missing")
            return
        try:
            checked, host = await guard.check_destination(url)
            guard.check_chat_destination(item.format, checked)
        except guard.DestinationRefused as refused:
            item.blockers.append(
                {
                    "invalid_url": "address_invalid",
                    "not_https": "address_invalid",
                    "host_not_allowed": "host_not_allowed",
                    "not_allowed": "address_not_allowed",
                    "unreachable": "address_unreachable",
                }.get(refused.code, "address_invalid")
            )
            return
        item.address, item.host = checked, host

    async def _plan_email(self, item: Item, parameters: Dict[str, str]) -> None:
        name = EMAIL_OF[item.name]
        if name is None:
            return  # the respondent's copy: no address
        address = parameters.get(name)
        if not address:
            item.blockers.append("recipient_missing")
            return
        allowed = await self._copy.allowed_among([address], item.workspace_id, item.form_id)
        if not allowed:
            item.blockers.append("recipient_not_member")
            return
        item.recipient = allowed[0]

    async def _plan_caps(self, form_id, workspace_id, items: List[Item]) -> None:
        if not workspace_id:
            return
        webhooks = await self._webhooks.count_for_form(workspace_id, form_id)
        emails = await self._emails.count_for_form(workspace_id, form_id)
        for item in items:
            if not item.movable or item.kind == "sheets":
                continue
            existing = await self._exists(item, workspace_id)
            if existing:
                continue
            if item.kind == "webhook":
                webhooks += 1
                over = webhooks > MAX_WEBHOOKS_PER_FORM
            else:
                emails += 1
                over = emails > MAX_EMAIL_ACTIONS_PER_FORM
            if over:
                item.blockers.append("cap_exceeded")

    async def _exists(self, item: Item, workspace_id: str) -> bool:
        tid = target_id(item.kind, item.form_id, item.action_id)
        repo = self._webhooks if item.kind == "webhook" else self._emails
        return await repo.get(workspace_id, item.form_id, str(tid)) is not None

    # ----------------------------------------------------------- preflight

    def _classify(self, report: Report, items: List[Item]) -> None:
        for item in items:
            report.add(f"found.{item.name}")
            if not item.enabled:
                report.add(f"found.{item.name}.disabled")
            for dropped in item.dropped:
                report.add(f"dropped.{dropped}")
            if item.skipped:
                report.add(f"skipped.{item.skipped}")
                continue
            blockers = list(item.blockers)
            if item.kind == "webhook" and item.enabled and not webhooks_enabled():
                blockers.append("switch_off")
            if item.kind == "email" and item.enabled:
                if not email_actions_enabled():
                    blockers.append("switch_off")
                elif not mail_configured():
                    blockers.append("mail_not_configured")
            if blockers and not item.enabled:
                # an action nobody had on: left as it is, nothing is lost
                report.add(f"not_moved.disabled.{item.name}")
                item.skipped = "disabled_not_moved"
                continue
            for code in blockers:
                report.add(f"blocked.{code}")
                report.add(f"blocked.{code}.{item.name}")
            if blockers:
                item.blockers = blockers
                continue
            report.add(f"movable.{item.name}")

    async def preflight(self, workspace: Optional[str] = None) -> Report:
        report = Report()
        if self._temporal_open_runs is not None:
            try:
                report.add("open_run_action_workflows", len(await self._ask_temporal(None)))
            except TemporalUnreachable as unreachable:
                if self._temporal_override:
                    report.add("temporal_check_skipped_by_operator")
                    self._warn_override(unreachable.reason)
                else:
                    report.add("blocked.temporal_unreachable")
        for form_id in await self.form_ids(workspace):
            items = await self.plan_form(form_id)
            if items:
                report.add("forms_with_builtins")
            self._classify(report, items)
        return report

    # --------------------------------------------------------------- apply

    async def _open_runs(self, form_id: str) -> int:
        """Runs of the form's built-in actions still waiting for, or being run
        by, the executor: on the Postgres queue and, when ``run_action`` is on
        Temporal, the form's open workflows (asked of Temporal itself)."""
        count = await self._queued_runs(form_id)
        self.check_skipped = False
        if self._temporal_open_runs is not None:
            try:
                count += len(await self._ask_temporal(form_id))
            except TemporalUnreachable as unreachable:
                # fail closed: a Temporal that cannot be asked is never "no open
                # workflows"; only the operator's explicit word skips the check
                if not self._temporal_override:
                    raise
                self.check_skipped = True
                self._warn_override(unreachable.reason)
        return count

    async def _ask_temporal(self, form_id):
        """The open workflows (of ``form_id``, or all), or ``TemporalUnreachable``
        for any failure to ask: a connection error, a refused login, a timeout."""
        try:
            return await asyncio.wait_for(
                self._temporal_open_runs(form_id), TEMPORAL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as error:
            raise TemporalUnreachable("timeout") from error
        except Exception as error:  # noqa: BLE001
            raise TemporalUnreachable(type(error).__name__) from error

    @staticmethod
    def _warn_override(reason: str) -> None:
        logger.warning(
            "--temporal-drained: TEMPORAL COULD NOT BE ASKED ({}); the open "
            "run_action_code workflows are NOT checked, on the operator's word "
            "that none are open. The skipped check is recorded with each moved action.",
            reason,
        )

    async def _queued_runs(self, form_id: str) -> int:
        try:
            async with self._forms._session() as session:
                return int(
                    (
                        await session.execute(
                            text(
                                "select count(*) from jobs.procrastinate_jobs "
                                "where queue_name='actions' and status in ('todo','doing') "
                                "and args->>'form_id' = :f"
                            ),
                            {"f": str(form_id)},
                        )
                    ).scalar()
                    or 0
                )
        except ProgrammingError:
            # no queue table: this database never queued a run on Postgres
            return 0

    async def apply(
        self,
        workspace: Optional[str] = None,
        *,
        wait_queue_seconds: int = 0,
        poll=asyncio.sleep,
    ) -> Report:
        report = Report()
        for form_id in await self.form_ids(workspace):
            items = await self.plan_form(form_id)
            probe = Report()
            self._classify(probe, items)
            movable = [i for i in items if i.movable]
            for key, value in probe.counts.items():
                if key.startswith(("blocked.", "skipped.", "not_moved.", "dropped.")):
                    report.add(key, value)
            if not movable:
                continue
            waited = 0
            try:
                while await self._open_runs(form_id):
                    if waited >= wait_queue_seconds:
                        break
                    await poll(2)
                    waited += 2
                open_runs = await self._open_runs(form_id)
            except TemporalUnreachable:
                report.add("blocked.temporal_unreachable")
                break  # no form can be checked: nothing more is moved
            if open_runs:
                report.add("blocked.queued_runs")
                continue
            skipped = self.check_skipped
            if skipped:
                report.add("temporal_check_skipped_by_operator")
            moved = await self._apply_form(form_id, movable, skipped)
            if moved is None:
                report.add("blocked.form_changed")
                continue
            for item in movable:
                report.add(f"moved.{item.name}")
        return report

    async def _apply_form(
        self, form_id: str, items: List[Item], check_skipped: bool = False
    ) -> Optional[int]:
        """One transaction: the rows and the marks of the form's movable
        entries. None (nothing written) when the form changed since it was
        planned."""
        now = self._clock()
        async with self._forms._session() as session, session.begin():
            stored = await self._forms._locked_draft(session, form_id)
            if stored is None:
                return None
            entries = {str(e.id): e for e in (stored.actions or {}).get("on_submit") or []}
            for item in items:
                current = entries.get(item.action_id)
                if (
                    current is None
                    or bool(current.enabled) != item.enabled
                    or current.migrated_to
                ):
                    return None
            for item in items:
                entry = entries[item.action_id]
                if item.kind == "sheets":
                    entry.migrated_to = {
                        "kind": "sheets",
                        "id": item.action_id,
                        "was_enabled": "true" if item.enabled else "false",
                        **({CHECK_SKIPPED_KEY: CHECK_SKIPPED_VALUE} if check_skipped else {}),
                    }
                    entry.migrated_at = now
                    continue
                tid = target_id(item.kind, form_id, item.action_id)
                document = (
                    self._webhook_document(item, tid, now)
                    if item.kind == "webhook"
                    else await self._email_document(item, tid)
                )
                repo = self._webhooks if item.kind == "webhook" else self._emails
                await session.execute(repo._upsert_statement(row_values(document)))
                if item.kind == "webhook":
                    await session.execute(
                        self._audit._upsert_statement(
                            row_values(
                                WebhookAuditDocument(
                                    workspace_id=RecordId(item.workspace_id),
                                    form_id=form_id,
                                    webhook_id=str(tid),
                                    event="migrated",
                                    actor_id=None,
                                    changed=(
                                        ["temporal_check_skipped_by_operator"]
                                        if check_skipped
                                        else []
                                    ),
                                    host=document.host,
                                ).ensure_id()
                            )
                        )
                    )
                entry.enabled = False
                entry.migrated_to = {
                    "kind": item.kind,
                    "id": str(tid),
                    "was_enabled": "true" if item.enabled else "false",
                    **({CHECK_SKIPPED_KEY: CHECK_SKIPPED_VALUE} if check_skipped else {}),
                }
                entry.migrated_at = now
            stored.updated_at = now
            await session.execute(
                self._forms._upsert_statement(row_values(stored))
            )
        logger.info("builtin actions moved: form={} count={}", form_id, len(items))
        return len(items)

    def _webhook_document(self, item: Item, tid: RecordId, now) -> FormWebhookDocument:
        document = FormWebhookDocument(
            workspace_id=RecordId(item.workspace_id),
            form_id=item.form_id,
            url_sealed="",
            host=item.host or "",
            enabled=item.enabled,
            fields=[],
            format=item.format,
            all_questions=False,
            created_via=MIGRATED_VIA,
            source_action_id=item.action_id,
        )
        document.id = tid
        document.url_sealed = seal_url(
            self._crypto, item.workspace_id, tid, item.address
        )
        if item.format in formats.SIGNED:
            document.secret_sealed = seal(
                self._crypto, item.workspace_id, tid, new_secret()
            )
            document.secret_set_at = now
        return document

    async def _email_document(self, item: Item, tid: RecordId) -> FormEmailActionDocument:
        workspace = await self._workspaces.find_by_id(RecordId(item.workspace_id))
        link = responses_link(
            settings.api_settings.CLIENT_URL,
            workspace.workspace_name if workspace else "",
            item.form_id,
        )
        en, nl = email_defaults.default_templates(link)
        respondent = item.name == "responder_copy_mail"
        document = FormEmailActionDocument(
            workspace_id=RecordId(item.workspace_id),
            form_id=item.form_id,
            name="Copy for the respondent" if respondent else "Copy of each response",
            enabled=item.enabled,
            en=en,
            nl=nl,
            fields=[],
            team_recipients=[] if respondent else [item.recipient],
            respondent_copy=respondent,
            all_questions=True,
            created_via=MIGRATED_VIA,
            source_action_id=item.action_id,
        )
        document.id = tid
        return document

    # -------------------------------------------------------------- verify

    async def _moved_entries(self, workspace: Optional[str]):
        for form_id in await self.form_ids(workspace):
            form = await self._forms.get_form_document_by_id(form_id)
            workspace_id = await self._workspace_of(form_id)
            for entry in (form.actions or {}).get("on_submit") or []:
                if entry.migrated_to:
                    yield form_id, workspace_id, form, entry

    async def verify(self, workspace: Optional[str] = None) -> Report:
        """Every moved entry has its target, which opens and is on exactly when
        the old action was; the old entry is off (never both on)."""
        report = Report()
        builtins = await self._builtin_actions()
        async for form_id, workspace_id, form, entry in self._moved_entries(workspace):
            marker = entry.migrated_to
            kind = marker.get("kind")
            report.add(f"checked.{kind}")
            was_enabled = marker.get("was_enabled") == "true"
            if kind == "sheets":
                if bool(entry.enabled) != was_enabled:
                    report.add("problem.sheets_enabled_changed")
                continue
            repo = self._webhooks if kind == "webhook" else self._emails
            target = await repo.get(workspace_id, form_id, marker.get("id"))
            if target is None:
                report.add(f"problem.{kind}_missing")
                continue
            if bool(target.enabled) != was_enabled:
                report.add(f"problem.{kind}_enabled_differs")
            if entry.enabled:
                report.add("problem.both_on")
            if kind == "webhook":
                try:
                    unseal_url(self._crypto, workspace_id, target.id, target.url_sealed)
                    if target.format in formats.SIGNED:
                        unseal(self._crypto, workspace_id, target.id, target.secret_sealed)
                except SecretUnreadable:
                    report.add("problem.webhook_unreadable")
            if str(entry.id) not in builtins:
                report.add("problem.action_unknown")
        return report

    # ------------------------------------------------------------ rollback

    async def rollback(self, workspace: Optional[str] = None) -> Report:
        """Give the old entries back (on as they were) and switch the moved
        webhooks and email actions off. Their rows and logs stay."""
        report = Report()
        now = self._clock()
        for form_id in await self.form_ids(workspace):
            async with self._forms._session() as session, session.begin():
                stored = await self._forms._locked_draft(session, form_id)
                if stored is None:
                    continue
                workspace_id = await self._workspace_of(form_id)
                changed = False
                for entry in (stored.actions or {}).get("on_submit") or []:
                    marker = entry.migrated_to
                    if not marker:
                        continue
                    kind = marker.get("kind")
                    if kind in ("webhook", "email"):
                        repo = self._webhooks if kind == "webhook" else self._emails
                        target = await repo.get(workspace_id, form_id, marker.get("id"))
                        if target is not None:
                            target.enabled = False
                            target.touch()
                            await session.execute(repo._upsert_statement(row_values(target)))
                        entry.enabled = marker.get("was_enabled") == "true"
                    entry.migrated_to = None
                    entry.migrated_at = None
                    changed = True
                    report.add(f"rolled_back.{kind}")
                if changed:
                    stored.updated_at = now
                    await session.execute(self._forms._upsert_statement(row_values(stored)))
        return report
