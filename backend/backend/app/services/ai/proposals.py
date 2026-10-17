"""AI edit proposals: the AI proposes, the person accepts.

A chat turn in ``propose`` mode dry-runs the model's ops against the stored
form and returns a proposal (the ops, the form they would make, a diff with
what each op changes, and the per-op results); nothing about the form is
written. Accepting applies the chosen ops, atomically, to the form as it is
*then* stored, through the AI write path (``persist_ops_to_form``) with the
builder's conditional write, so a save landing at the same moment is never
overwritten. Rejecting only marks the proposal.

Where proposals live: on the assistant turn of the chat session that
produced them (``FormAISessionDocument.messages``, already stored in both
databases through the routed session repository), as
``{"proposal": {id, status, expires_at, ...}}`` next to the turn's ``ops``
and ``results``. That is shared by every worker and needs no new
collection, table or migration; an in-process cache would not survive a
request reaching another replica. A proposal can be accepted until
``AI_PROPOSAL_TTL_SECONDS`` after it was made.

Two accepts of one proposal arriving at once (a double click, two tabs)
must not apply it twice. The session is saved as a whole document, so its
status cannot decide that race; a one-time claim in the shared, atomic
rate-limit counters (``FixedWindowRateLimiter.claim``) does: only the first
accept that gets past every check takes it.
"""

from __future__ import annotations

import datetime as dt
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
from pydantic.alias_generators import to_camel

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
from backend.app.services.form_concurrency import FORM_CHANGED_CODE
from backend.app.services.form_spec.diff import spec_diff
from backend.app.services.form_spec.service import settings_after_ops
from backend.config import settings as app_settings

STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
# accepted, but the ops no longer applied to the stored form
STATUS_FAILED = "failed"

ACCEPT_CLAIM_SCOPE = "ai:proposal:accept"
# a conditional write that lost to a save landing at the same moment is
# tried again on the newer form this many times in all
_WRITE_ATTEMPTS = 3
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
_PROPOSAL_ID = re.compile(r"^([0-9a-f]{24})-([0-9a-f]{16})$")
MAX_PROPOSAL_OPS = MAX_OPS_PER_BATCH


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


def _stale(errors: List[Dict[str, Any]]) -> HTTPException:
    return _error(
        HTTPStatus.CONFLICT,
        "proposal_stale",
        "The form changed since this was proposed, so some of the changes no "
        "longer apply. Nothing was changed.",
        errors,
    )


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
        previous[0] = current

    new_form, results = apply_form_ops(form, ops, on_step=on_step)
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
        return document

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

        # A trial on the stored form first: a stale proposal is refused
        # before it is claimed, and stays open.
        form_document = await self._load_form(workspace_id, form_id)
        _, trial = apply_form_ops(
            StandardForm(**form_document.model_dump()), chosen_ops, atomic=True
        )
        if not all(r.ok for r in trial):
            raise _stale(failures(trial))

        if not await self._rate_limiter.claim(
            ACCEPT_CLAIM_SCOPE, proposal_id, expires_at or _EPOCH
        ):
            raise _closed(STATUS_ACCEPTED)

        try:
            for attempt in range(_WRITE_ATTEMPTS):
                form = StandardForm(**form_document.model_dump())
                try:
                    new_form, results, settings = await persist_ops_to_form(
                        form_document,
                        form,
                        chosen_ops,
                        atomic=True,
                        expected_updated_at=form_document.updated_at or _EPOCH,
                    )
                except HTTPException as error:
                    lost_race = (
                        error.status_code == HTTPStatus.CONFLICT
                        and isinstance(error.content, dict)
                        and error.content.get("code") == FORM_CHANGED_CODE
                    )
                    if not lost_race or attempt == _WRITE_ATTEMPTS - 1:
                        raise
                    # another save landed between the read and the write:
                    # this accept holds the claim, so apply it to that form
                    form_document = await self._load_form(workspace_id, form_id)
                    continue
                if not all(r.ok for r in results):
                    raise _stale(failures(results))
                break
        except HTTPException:
            # the claim is spent: the proposal cannot be accepted again
            record.update(
                status=STATUS_FAILED,
                decided_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )
            await self._session_repo.save(session)
            raise

        record.update(
            status=STATUS_ACCEPTED,
            accepted_op_indexes=chosen,
            decided_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        await self._session_repo.save(session)
        return AcceptProposalResponse(
            proposal_id=proposal_id,
            status=STATUS_ACCEPTED,
            accepted_op_indexes=chosen,
            results=original(results),
            form=camel_form_reply(new_form, form_document),
            settings=settings,
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
            record.update(
                status=STATUS_REJECTED,
                decided_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )
            await self._session_repo.save(session)
        elif status != STATUS_REJECTED:
            raise _closed(status)
        return ProposalStatusResponse(proposal_id=proposal_id, status=STATUS_REJECTED)
