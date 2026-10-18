"""AI edit proposals: the AI proposes, the person accepts.

A chat turn in ``propose`` mode dry-runs the model's ops against the stored
form and returns a proposal (the ops, the form they would make, a diff with
what each op changes, and the per-op results); nothing about the form is
written. Accepting applies the chosen ops, atomically, through the AI write
path (``persist_ops_to_form``), and only to the version of the form the
proposal was made from (``base_updated_at``, written conditionally): ops
address pages and fields by position too, so on a newer version they could
land somewhere other than what was shown. A changed form makes the proposal
stale ("Ask again"). A subset is accepted only when each chosen op still
changes exactly what its step showed (``changed_meaning``). Rejecting only
marks the proposal.

Where proposals live: on the assistant turn of the chat session that
produced them (``FormAISessionDocument.messages``, already stored in both
databases through the routed session repository), as
``{"proposal": {id, status, expires_at, ...}}`` next to the turn's ``ops``
and ``results``. That is shared by every worker and needs no new
collection, table or migration; an in-process cache would not survive a
request reaching another replica. A proposal can be accepted until
``AI_PROPOSAL_TTL_SECONDS`` after it was made.

Two accepts of one proposal arriving at once (a double click, two tabs)
must not apply it twice: a one-time claim in the shared, atomic rate-limit
counters (``FixedWindowRateLimiter.claim``) decides it; only the first
accept that gets past every check takes it. Statuses are then written to
the proposal's record alone (``update_proposal``), never by saving the
whole session, so a chat turn saved at the same time cannot undo them.

Once the form is written, the accept is a success: the ``accepted`` status
write is retried a couple of times, and when it still fails, the version
the accept wrote is marked next to the claim instead
(``_record_accepted``). A later accept or reject that finds the stored form
at exactly that version reports the proposal as accepted (and writes the
status then), rather than "busy" until the claim expires.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import secrets
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from common.exceptions import NotFoundError
from common.form_spec import SpecConversionError, form_to_spec_dict
from common.models.standard_form import StandardForm
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from pydantic.alias_generators import to_camel
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormCamelModel
from backend.app.models.enum.permission import Permission
from backend.app.services.ai.ops import (
    MAX_OPS_PER_BATCH,
    OpResult,
    apply_form_ops,
    finished_form,
    parse_ops,
    ref_dependencies,
)
from backend.app.services.form_concurrency import FORM_CHANGED_CODE, same_version
from backend.app.services.form_spec.diff import spec_diff
from backend.app.services.form_spec.service import settings_after_ops
from backend.config import settings as app_settings

STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
# accepted, but the ops no longer applied to the stored form
STATUS_FAILED = "failed"

# accept and reject take the same one-time claim: one of them decides
DECIDE_CLAIM_SCOPE = "ai:proposal:decide"
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
_PROPOSAL_ID = re.compile(r"^([0-9a-f]{24})-([0-9a-f]{16})$")
MAX_PROPOSAL_OPS = MAX_OPS_PER_BATCH
# a decision that must be recorded is retried after these pauses (seconds)
DECISION_WRITE_RETRY_DELAYS: Tuple[float, ...] = (0.05, 0.25)


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class ProposalStep(_CamelModel):
    """What one op changes, on top of the ops before it."""

    index: int
    diff: Dict[str, Any]
    # ops whose refs this op uses: accepting it needs them too
    requires: List[int] = []


class ProposalDto(_CamelModel):
    id: str
    ops: List[Dict[str, Any]]
    # the form as every op that worked would leave it (camelCase, as the
    # builder reads forms); never stored
    form: Dict[str, Any]
    # form spec v1 diff (services/form_spec/diff.py) of the whole proposal
    diff: Dict[str, Any]
    results: List[OpResult]
    summary: str
    steps: List[ProposalStep] = []
    expires_at: dt.datetime


class AcceptProposalRequest(_CamelModel):
    # the ops to apply (indexes into the proposal's ops); all that worked
    # when proposed when left out
    op_indexes: Optional[List[int]] = Field(None, max_length=MAX_PROPOSAL_OPS)


class AcceptProposalResponse(_CamelModel):
    proposal_id: str
    status: str
    accepted_op_indexes: List[int]
    results: List[OpResult]
    form: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = None


class ProposalStatusResponse(_CamelModel):
    proposal_id: str
    status: str


def _error(status: HTTPStatus, code: str, message: str, errors=None):
    content: Dict[str, Any] = {"code": code, "message": message}
    if errors is not None:
        content["errors"] = errors
    return HTTPException(status_code=status, content=content)


def _not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Proposal not found")


def _closed(status: str) -> HTTPException:
    what = {
        STATUS_ACCEPTED: "was already accepted",
        STATUS_REJECTED: "was discarded",
        STATUS_FAILED: "no longer applies",
    }.get(status, "is closed")
    return _error(
        HTTPStatus.CONFLICT,
        "proposal_closed",
        f"This proposal {what}. Ask again to get a new one.",
    )


FORM_CHANGED_SINCE = "This form changed since the suggestion. Ask again."


def _busy() -> HTTPException:
    return _error(
        HTTPStatus.CONFLICT,
        "proposal_busy",
        "This proposal is being accepted or discarded right now. Try again in "
        "a moment.",
    )


def _stale(
    errors: List[Dict[str, Any]],
    message: str = "Some of the changes can no longer be made. Nothing was changed.",
) -> HTTPException:
    return _error(HTTPStatus.CONFLICT, "proposal_stale", message, errors)


def dump_op(op) -> Dict[str, Any]:
    """An op as stored and returned: only what was given, so parse_ops
    reads back the same op."""
    return op.model_dump(mode="json", by_alias=True, exclude_unset=True)


def new_proposal_id(session_id: Any) -> str:
    """``<session id>-<16 hex>``: the session that holds it, and a part
    nobody can guess."""
    return f"{session_id}-{secrets.token_hex(8)}"


def _spec(form: StandardForm, settings: Any) -> Optional[Dict[str, Any]]:
    try:
        return form_to_spec_dict(form, settings)
    except SpecConversionError:
        return None


def _camel_form(form: StandardForm) -> Dict[str, Any]:
    reply = StandardFormCamelModel(**form.model_dump()).model_dump(
        mode="json", by_alias=True
    )
    # not a stored version: the builder must never adopt it
    reply.pop("updatedAt", None)
    return reply


def _step_diffs(
    form: StandardForm,
    settings: Any,
    ops: list,
    atomic: bool = False,
    afters: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Tuple[StandardForm, List[OpResult], Optional[Dict[str, Any]], List[ProposalStep]]:
    """Dry-run ``ops`` on ``form``: (the form they make, per-op results, the
    spec before, what each op that worked changed on top of the ops before
    it). ``afters`` collects the spec after each such op. Stores nothing."""
    before = _spec(form, settings)
    steps: List[ProposalStep] = []
    seen: List[OpResult] = []
    previous = [before]

    def on_step(index: int, working: StandardForm, result: OpResult) -> None:
        seen.append(result)
        if not result.ok or before is None:
            return
        try:
            snapshot = finished_form(working)
        except ValueError:
            # an intermediate state the schema refuses: nothing to show
            return
        current = _spec(
            snapshot, settings_after_ops(settings, ops[: index + 1], seen)
        )
        if current is None or previous[0] is None:
            previous[0] = current
            return
        steps.append(ProposalStep(index=index, diff=spec_diff(previous[0], current)))
        if afters is not None:
            afters[index] = current
        previous[0] = current

    new_form, results = apply_form_ops(form, ops, atomic=atomic, on_step=on_step)
    return new_form, results, before, steps


_GENERATED_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _ids_in(value: Any, found: set) -> set:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "id" and isinstance(item, str):
                found.add(item)
            _ids_in(item, found)
    elif isinstance(value, list):
        for item in value:
            _ids_in(item, found)
    return found


def _place(document: Dict[str, Any], path: str) -> List[Optional[str]]:
    """Where the page or field at ``path`` sits in ``document``: [the page
    or group it is in, the item before it] by id (None for the first)."""
    parts = path.strip("/").split("/")
    items, parent = document.get("pages") or [], None
    try:
        for i in range(1, len(parts), 2):
            index = int(parts[i])
            if i + 2 < len(parts):
                parent = items[index].get("id")
                items = items[index].get("fields") or []
            else:
                return [parent, items[index - 1].get("id") if index > 0 else None]
    except (ValueError, IndexError, AttributeError):
        pass
    return [parent, "?"]


def _canonical_step(
    diff: Dict[str, Any], known_ids: set, after: Dict[str, Any]
) -> str:
    """A step diff as a comparable value: an added or moved item by where
    it sits among its neighbours (not by index, which other ops shift),
    changes by their path inside their page or field, and the ids an op
    makes up (new on every run) written as "<new>"."""

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if (
            isinstance(value, str)
            and value not in known_ids
            and _GENERATED_ID.match(value)
        ):
            return "<new>"
        return value

    canonical: Dict[str, Any] = {
        "form": [
            [c["path"], scrub(c.get("before")), scrub(c.get("after"))]
            for c in diff.get("form") or []
        ]
    }
    for part in ("pages", "fields"):
        section = diff.get(part) or {}
        canonical[part] = {
            "added": sorted(
                [scrub(i["id"]), scrub(_place(after, i["path"]))]
                for i in section.get("added") or []
            ),
            "removed": sorted(scrub(i["id"]) for i in section.get("removed") or []),
            "moved": sorted(
                [scrub(i["id"]), scrub(_place(after, i["to"]))]
                for i in section.get("moved") or []
            ),
            "changed": sorted(
                [
                    scrub(item["id"]),
                    [
                        [
                            c["path"][len(item["path"]) :],
                            scrub(c.get("before")),
                            scrub(c.get("after")),
                        ]
                        for c in item.get("changes") or []
                    ],
                ]
                for item in section.get("changed") or []
            ),
        }
    return json.dumps(canonical, sort_keys=True, default=str)


def changed_meaning(
    form: StandardForm, settings: Any, ops: list, chosen: List[int]
) -> List[int]:
    """The chosen ops that, without the ops left out, would not change what
    the proposal showed for them (an op that inserts a page shifts what
    "page 2" means to the ops after it, for example). ``form`` is the form
    the proposal was made from."""
    shown_after: Dict[int, Dict[str, Any]] = {}
    alone_after: Dict[int, Dict[str, Any]] = {}
    _, _, base, shown = _step_diffs(form, settings, ops, afters=shown_after)
    _, _, _, alone = _step_diffs(
        form, settings, [ops[i] for i in chosen], afters=alone_after
    )
    known = _ids_in(base, set()) if base is not None else set()
    shown_by_op = {
        step.index: _canonical_step(step.diff, known, shown_after[step.index])
        for step in shown
    }
    alone_by_op = {
        chosen[step.index]: _canonical_step(
            step.diff, known, alone_after[step.index]
        )
        for step in alone
    }
    return [i for i in chosen if shown_by_op.get(i) != alone_by_op.get(i)]


def build_proposal(
    form: StandardForm,
    settings: Any,
    ops: list,
    summary: str,
    session_id: Any,
    now: Optional[dt.datetime] = None,
) -> Tuple[Optional[ProposalDto], List[OpResult]]:
    """Dry-run ``ops`` on ``form`` (the chat's partial mode: an op that
    fails is reported and skipped). Returns the proposal, or None when no
    op would change anything, and the per-op results. Stores nothing."""
    now = now or dt.datetime.now(dt.timezone.utc)
    new_form, results, before, steps = _step_diffs(form, settings, ops)
    if not any(r.ok for r in results):
        return None, results
    after = _spec(new_form, settings_after_ops(settings, ops, results))
    diff = (
        spec_diff(before, after)
        if before is not None and after is not None
        else {"changed": True}
    )
    requires = ref_dependencies(ops)
    for step in steps:
        step.requires = sorted(requires[step.index])
    ttl = max(60, int(app_settings.ai.PROPOSAL_TTL_SECONDS))
    proposal = ProposalDto(
        id=new_proposal_id(session_id),
        ops=[dump_op(op) for op in ops],
        form=_camel_form(new_form),
        diff=diff,
        results=results,
        summary=summary,
        steps=steps,
        expires_at=now + dt.timedelta(seconds=ttl),
    )
    return proposal, results


def proposal_record(proposal: ProposalDto, base_updated_at: Any) -> Dict[str, Any]:
    """What the session's assistant turn keeps about its proposal."""
    return {
        "id": proposal.id,
        "status": STATUS_PROPOSED,
        "expires_at": proposal.expires_at.isoformat(),
        "base_updated_at": (
            base_updated_at.isoformat() if base_updated_at is not None else None
        ),
    }


def _aware(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value


def _keep_until(record: Dict[str, Any]) -> dt.datetime:
    """How long a proposal's claims are kept: a day past the proposal, so a
    late retry still finds them."""
    return (_aware(record.get("expires_at")) or _EPOCH) + dt.timedelta(days=1)


def _accepted_key(proposal_id: str, version: dt.datetime) -> str:
    """The mark of an accept that wrote ``version`` of the form (to the
    millisecond, as every store keeps it) but not its status."""
    ms = (_aware(version) - _EPOCH) // dt.timedelta(milliseconds=1)
    return f"{proposal_id}#accepted@{ms}"


class FormAIProposalService:
    def __init__(
        self,
        authorization_service,
        workspace_form_repo,
        form_repo,
        session_repo,
        rate_limiter,
        ai_usage_guard=None,
    ):
        self._authorization = authorization_service
        self._workspace_form_repo = workspace_form_repo
        self._form_repo = form_repo
        self._session_repo = session_repo
        self._rate_limiter = rate_limiter
        self._ai_usage_guard = ai_usage_guard

    async def _load(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        proposal_id: str,
        user: User,
    ):
        """(session, the assistant turn holding the proposal); 404 for a
        proposal of another form, workspace or person, as for none."""
        match = _PROPOSAL_ID.match(proposal_id or "")
        if not match:
            raise _not_found()
        try:
            session = await self._session_repo.get_or_404(
                PydanticObjectId(match.group(1))
            )
        except NotFoundError:
            session = None
        if (
            session is None
            or session.form_id != str(form_id)
            or str(session.workspace_id) != str(workspace_id)
            or str(session.user_id) != str(user.id)
        ):
            raise _not_found()
        for message in session.messages or []:
            record = message.get("proposal")
            if isinstance(record, dict) and record.get("id") == proposal_id:
                return session, message
        raise _not_found()

    async def _load_form(self, workspace_id, form_id):
        association = await self._workspace_form_repo.find_workspace_form(
            workspace_id, str(form_id)
        )
        document = (
            await self._form_repo.get_form_document_by_id(str(form_id))
            if association
            else None
        )
        if document is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form not found"
            )
        return document, association.settings

    async def _set(self, session, proposal_id: str, only_if_status=None, **fields):
        """Change only this proposal's record, never the rest of the
        session (a chat turn may be saving it right now)."""
        if "status" in fields:
            fields.setdefault(
                "decided_at", dt.datetime.now(dt.timezone.utc).isoformat()
            )
        return await self._session_repo.update_proposal(
            session.id, proposal_id, fields, only_if_status=only_if_status
        )

    async def _claim(self, proposal_id: str, record: Dict[str, Any]) -> int:
        """The one-time right to decide this proposal (accept or reject),
        for its current attempt; 409 when another request holds it. An
        attempt that broke off without deciding (``_give_back``) moves the
        proposal to the next attempt, which can be claimed again."""
        attempt = int(record.get("attempt") or 0)
        if await self._rate_limiter.claim(
            DECIDE_CLAIM_SCOPE, f"{proposal_id}#{attempt}", _keep_until(record)
        ):
            return attempt
        raise _busy()

    async def _set_decision(self, session, proposal_id: str, **fields) -> None:
        """``_set`` for a decision that must be recorded: retried a couple
        of times before the error stands."""
        for delay in (*DECISION_WRITE_RETRY_DELAYS, None):
            try:
                await self._set(session, proposal_id, **fields)
                return
            except Exception:  # noqa: BLE001 — raised after the last try
                if delay is None:
                    raise
                await asyncio.sleep(delay)

    async def _record_accepted(
        self,
        session,
        proposal_id: str,
        record: Dict[str, Any],
        chosen: List[int],
        version: Optional[dt.datetime],
    ) -> None:
        """The form is written (as ``version``): record the proposal as
        accepted. When the status cannot be written, mark the version next
        to the claim, for ``_accepted_as``; never an error, since the
        accept itself succeeded."""
        try:
            await self._set_decision(
                session,
                proposal_id,
                status=STATUS_ACCEPTED,
                accepted_op_indexes=chosen,
            )
            return
        except Exception as error:  # noqa: BLE001 — the form is written
            failed = type(error).__name__
        try:
            if version is None:
                raise ValueError("no stored version")
            await self._rate_limiter.claim(
                DECIDE_CLAIM_SCOPE,
                _accepted_key(proposal_id, version),
                _keep_until(record),
            )
            logger.warning(
                "AI proposal accepted; status not written ({}), version marked",
                failed,
            )
        except Exception as again:  # noqa: BLE001 — logged by type only
            logger.warning(
                "AI proposal accepted; status not written ({}), version not "
                "marked ({})",
                failed,
                type(again).__name__,
            )

    async def _accepted_as(
        self, session, proposal_id: str, record: Dict[str, Any], version: Any
    ) -> bool:
        """Whether the stored form (at ``version``) is the one an accept of
        this proposal wrote without recording its status
        (``_record_accepted``). If so, the status is written now, when it
        can be."""
        if version is None or same_version(
            version, _aware(record.get("base_updated_at"))
        ):
            return False
        try:
            if not await self._rate_limiter.claimed(
                DECIDE_CLAIM_SCOPE,
                _accepted_key(proposal_id, version),
                _keep_until(record),
            ):
                return False
        except Exception:  # noqa: BLE001 — unknown: the caller's answer stands
            return False
        try:
            await self._set(
                session,
                proposal_id,
                only_if_status=STATUS_PROPOSED,
                status=STATUS_ACCEPTED,
            )
        except Exception:  # noqa: BLE001 — the mark keeps answering
            pass
        return True

    async def _accepted_since(
        self, workspace_id, form_id, session, proposal_id: str, record
    ) -> bool:
        """``_accepted_as`` for the form as stored now; False when the form
        cannot be read."""
        try:
            form_document, _ = await self._load_form(workspace_id, form_id)
        except Exception:  # noqa: BLE001 — unknown: the caller's answer stands
            return False
        return await self._accepted_as(
            session, proposal_id, record, form_document.updated_at
        )

    async def _give_back(self, session, proposal_id: str, attempt: int, error) -> None:
        """An unexpected failure after the claim, before a decision was
        recorded: open the next attempt so a retry can decide (a retry of an
        accept whose write did land meets a changed form: stale). If even
        this cannot be written, the error stands (logged by type only)."""
        try:
            await self._set(
                session,
                proposal_id,
                only_if_status=STATUS_PROPOSED,
                attempt=attempt + 1,
                last_error=type(error).__name__,
            )
        except Exception as again:  # noqa: BLE001 — the first error is raised
            logger.warning(
                "AI proposal attempt not reopened ({}, after {})",
                type(again).__name__,
                type(error).__name__,
            )

    async def _decided(self, workspace_id, form_id, proposal_id, user) -> str:
        _, message = await self._load(workspace_id, form_id, proposal_id, user)
        return message["proposal"].get("status")

    @staticmethod
    def _chosen(
        requested: Optional[List[int]], count: int, proposed: List[Dict[str, Any]]
    ) -> List[int]:
        worked = {
            int(r.get("index", i))
            for i, r in enumerate(proposed or [])
            if r.get("ok")
        }
        if requested is None:
            return sorted(worked)
        errors = []
        for index in requested:
            if index < 0 or index >= count:
                errors.append({"index": index, "message": "There is no such change."})
            elif index not in worked:
                errors.append(
                    {
                        "index": index,
                        "message": "This change could not be made when it was "
                        "proposed.",
                    }
                )
        if errors:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "proposal_invalid_selection",
                "Some of the chosen changes cannot be accepted.",
                errors,
            )
        chosen = sorted(set(requested))
        if not chosen:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "proposal_invalid_selection",
                "Choose at least one change to accept.",
                [],
            )
        return chosen

    @staticmethod
    def _check_dependencies(ops: list, chosen: List[int]) -> None:
        needs = ref_dependencies(ops)
        picked = set(chosen)
        errors = []
        for index in chosen:
            missing = sorted(needs[index] - picked)
            if missing:
                listed = ", ".join(f"#{m + 1}" for m in missing)
                errors.append(
                    {
                        "index": index,
                        "requires": missing,
                        "message": f"Change #{index + 1} builds on change "
                        f"{listed}, which is not accepted. Accept "
                        f"{'it' if len(missing) == 1 else 'them'} too, or leave "
                        f"#{index + 1} out.",
                    }
                )
        if errors:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "proposal_dependency",
                "Some chosen changes build on changes that are not accepted.",
                errors,
            )

    async def accept(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        proposal_id: str,
        request: AcceptProposalRequest,
        user: User,
    ) -> AcceptProposalResponse:
        # Resolved at call time: the container imports the chat module.
        from backend.app.services.ai.chat import camel_form_reply, persist_ops_to_form

        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        session, message = await self._load(workspace_id, form_id, proposal_id, user)
        record = message["proposal"]
        status = record.get("status")
        if status != STATUS_PROPOSED:
            raise _closed(status)
        expires_at = _aware(record.get("expires_at"))
        if expires_at is not None and expires_at <= dt.datetime.now(dt.timezone.utc):
            raise _error(
                HTTPStatus.GONE,
                "proposal_expired",
                "This proposal has expired. Ask again to get a new one.",
            )
        # no provider call: the review-fix allowance, no budget
        if self._ai_usage_guard is not None:
            await self._ai_usage_guard.admit_fix(workspace_id, user.id)

        ops = parse_ops(message.get("ops") or [])
        chosen = self._chosen(request.op_indexes, len(ops), message.get("results"))
        self._check_dependencies(ops, chosen)
        chosen_ops = [ops[i] for i in chosen]

        def original(results: List[OpResult]) -> List[OpResult]:
            return [
                r.model_copy(update={"index": chosen[r.index]}) for r in results
            ]

        def failures(results: List[OpResult]) -> List[Dict[str, Any]]:
            return [
                {"index": r.index, "message": r.message}
                for r in original(results)
                if not r.ok
            ]

        # Only on the form the proposal was made from: ops name pages and
        # fields by position too, so on any other version they could land
        # somewhere else than what was shown.
        form_document, settings = await self._load_form(workspace_id, form_id)
        base = _aware(record.get("base_updated_at"))
        if not same_version(form_document.updated_at, base):
            if await self._accepted_as(
                session, proposal_id, record, form_document.updated_at
            ):
                raise _closed(STATUS_ACCEPTED)
            raise _stale([], FORM_CHANGED_SINCE)
        form = StandardForm(**form_document.model_dump())
        _, trial = await run_in_threadpool(
            apply_form_ops, form, chosen_ops, atomic=True
        )
        if not all(r.ok for r in trial):
            raise _stale(failures(trial))
        # A subset: each chosen op must still do exactly what was shown.
        if chosen != self._chosen(None, len(ops), message.get("results")):
            differs = await run_in_threadpool(
                changed_meaning, form, settings, ops, chosen
            )
            if differs:
                raise _error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "proposal_selection_changes_meaning",
                    "Without the changes left out, some chosen changes would "
                    "not do what was shown. Accept those too, or ask again.",
                    [
                        {
                            "index": index,
                            "message": f"Without the changes left out, change "
                            f"#{index + 1} would not do what was shown.",
                        }
                        for index in differs
                    ],
                )

        try:
            attempt = await self._claim(proposal_id, record)
        except HTTPException:
            status = await self._decided(workspace_id, form_id, proposal_id, user)
            if status != STATUS_PROPOSED:
                raise _closed(status)
            raise

        try:
            new_form, results, updated_settings = await persist_ops_to_form(
                form_document,
                form,
                chosen_ops,
                workspace_id=workspace_id,
                atomic=True,
                # the proposal's base, still: a save landing in between
                # makes this a stale proposal, not a retry on that form
                expected_updated_at=form_document.updated_at or _EPOCH,
            )
            if not all(r.ok for r in results):
                raise _stale(failures(results))
        except HTTPException as error:
            # the claim is spent: the proposal cannot be accepted again
            await self._set_decision(session, proposal_id, status=STATUS_FAILED)
            if (
                error.status_code == HTTPStatus.CONFLICT
                and isinstance(error.content, dict)
                and error.content.get("code") == FORM_CHANGED_CODE
            ):
                raise _stale([], FORM_CHANGED_SINCE)
            raise
        except Exception as error:
            await self._give_back(session, proposal_id, attempt, error)
            raise

        await self._record_accepted(
            session, proposal_id, record, chosen, form_document.updated_at
        )
        return AcceptProposalResponse(
            proposal_id=proposal_id,
            status=STATUS_ACCEPTED,
            accepted_op_indexes=chosen,
            results=original(results),
            form=camel_form_reply(new_form, form_document),
            settings=updated_settings,
        )

    async def reject(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        proposal_id: str,
        user: User,
    ) -> ProposalStatusResponse:
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        session, message = await self._load(workspace_id, form_id, proposal_id, user)
        record = message["proposal"]
        status = record.get("status")
        if status == STATUS_PROPOSED:
            # the same claim as accept: exactly one of them decides
            try:
                attempt = await self._claim(proposal_id, record)
            except HTTPException:
                status = await self._decided(workspace_id, form_id, proposal_id, user)
                if status == STATUS_PROPOSED:
                    if not await self._accepted_since(
                        workspace_id, form_id, session, proposal_id, record
                    ):
                        raise
                    status = STATUS_ACCEPTED
            else:
                try:
                    if await self._set(
                        session,
                        proposal_id,
                        only_if_status=STATUS_PROPOSED,
                        status=STATUS_REJECTED,
                    ):
                        status = STATUS_REJECTED
                    else:
                        status = await self._decided(
                            workspace_id, form_id, proposal_id, user
                        )
                except Exception as error:
                    await self._give_back(session, proposal_id, attempt, error)
                    raise
        if status != STATUS_REJECTED:
            raise _closed(status)
        return ProposalStatusResponse(proposal_id=proposal_id, status=STATUS_REJECTED)
