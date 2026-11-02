"""Copying a form's structure to another workspace (promotion between
environments, ``FORM_PROMOTION_ENABLED``).

An environment is a workspace. What moves is the form's spec document and
nothing else, and the result is always a **draft**: a new form, or the draft of
an existing one. Responses, webhooks, email actions, connected actions, case
system hand-overs, who may open the form, its link, its dates and its publish
state never move; the preview counts what is not copied.

The document goes through the product's own write path, so every check of the
spec API holds in the target, the target instance's switches included:
``FormSpecWriter.create`` / ``replace`` after a normalising step (``normalise``:
first-party images, answer patterns, option lists matched by name, no sources
from other forms' answers). Nothing here bypasses a check.

Both sides are authorised as the same person: ``form.read`` on the source form
(a restricted source also needs an Owner, an Admin or its creator, and gives a
restricted copy), ``form.create`` in the target workspace, or ``form.edit`` on
the target form. A target workspace the caller is not a member of answers as one
that does not exist.

Apply takes the source's and the target's ETags back (412 when either changed
since the preview) and an ``Idempotency-Key`` (a double click never makes two
forms). Both audit entries are stored before the change: no entry, no change.

Never read, copied or counted: an answer. Never logged or stored: a title, a name,
an address or any text of the form. Ids and counts only.
"""

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from common.form_spec import FormSpec
from common.ids import RecordId
from common.models.user import User
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.form_promotion_dto import (
    ApplyRequest,
    PromotionRequest,
    PromotionTargetDto,
    PromotionTargetsDto,
)
from backend.app.models.enum.permission import Permission
from backend.app.models.workspace import PromotedFrom
from backend.app.schemas.workspace_audit_event import FORM_COPIED_OUT, FORM_PROMOTED
from backend.app.services.form_access.audit import record_or_refuse
from backend.app.services.form_access.model import MODE_RESTRICTED
from backend.app.services.form_promotion.normalise import (
    Report,
    every_question,
    normalise,
    option_list_ids,
)
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_spec.writes import (
    INVALID_SPEC_CODE,
    _drafts_problem,
    form_etag,
    precondition_failed,
)
from backend.app.services.form_versions.compare import compare_specs
from backend.app.services.form_patterns import pattern_problem
from backend.app.services.idempotency import (
    IdempotencyService,
    StoredResponse,
    request_hash,
)
from backend.app.services.image_urls import first_party_image_url
from backend.app.services.workspace_form_service import WorkspaceFormService
from common.settings.loader import live

NOT_PROMOTABLE_CODE = "form_not_promotable"
SAME_FORM_CODE = "same_form"
TARGET_CHANGED_CODE = "target_changed"
TARGET_NOT_RESTRICTED_CODE = "target_not_restricted"
TARGET_NOT_RESTRICTED_MESSAGE = "Restrict the target form first"
SESSION_ONLY_CODE = "promotion_needs_session"
RETENTION_CONFIRMATION_CODE = "retention_confirmation_required"
IDEMPOTENCY_KEY_REQUIRED_CODE = "idempotency_key_required"
RATE_LIMIT_SCOPE = "form_promotion"
# preview and the picker run the normaliser, the checks and the diff on every call:
# the same per-person limit as apply, counted apart so a review never starves a copy
READ_RATE_LIMIT_SCOPE = "form_promotion_read"
RATE_LIMITED_CODE = "rate_limited"
# the audit entry of the form file download (``export_channel``)
FILE_CHANNEL = "file"
# the most forms the target picker lists
TARGETS_MAX = 50
# answers about the forms' versions, not the request: not kept for the key, so
# the same request resent after a new preview runs again
_NOT_KEPT = {HTTPStatus.PRECONDITION_FAILED}

# What never moves, besides the counted automations: shown with the counts.
ALSO_NOT_COPIED = (
    "responses",
    "access",
    "link",
    "availability",
    "publishState",
    "logoFile",
)


def _not_found(message: str = "Form not found") -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, content=message)


def _unprocessable(code: str, message: str, **more: Any) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": code, "message": message, **more},
    )


def spec_hash(document: Dict[str, Any]) -> str:
    """A short hash of a spec document (the copy's mark of what it stored)."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def retention_shortened(before: Any, after: Any) -> bool:
    """Whether replacing retention ``before`` with ``after`` can make the target
    delete answers earlier. Nothing kept before: nothing to shorten; unknown
    shapes count as shortened."""

    def rank(retention: Any):
        if not isinstance(retention, dict):
            return None
        kind = retention.get("type")
        if kind == "forever":
            return (2, 0)
        if kind == "days" and isinstance(retention.get("value"), int):
            return (1, retention["value"])
        if kind == "date" and isinstance(retention.get("value"), str):
            return (0, retention["value"])
        return None

    old, new = rank(before), rank(after)
    if before is None or old is None:
        return False
    if after is None or new is None:
        return True
    if new[0] == 2:
        return False
    if old[0] != new[0]:
        return True  # days and an end date do not compare
    return new[1] < old[1]


def counts_of(document: Dict[str, Any]) -> Dict[str, int]:
    pages = [p for p in document.get("pages") or [] if isinstance(p, dict)]
    return {
        "pages": len(pages),
        "questions": sum(
            sum(1 for _ in every_question(p.get("fields"), "")) for p in pages
        ),
    }


@dataclass
class _Side:
    """One form on one side: its document, its version, its link."""

    workspace_id: RecordId
    form_id: str
    spec: Dict[str, Any]
    etag: str
    link: Any
    # the stored draft (its actions are counted, never read)
    document: Any


@dataclass
class _Plan:
    source: _Side
    target: Optional[_Side]
    target_workspace_id: RecordId
    document: Dict[str, Any]
    report: Report
    # counts of what does not move, for those who may edit the source form (None
    # for a reader: how many automations a form has is for its editors)
    not_carried: Optional[Dict[str, int]]
    # the source form is restricted: its copy must not be open to more people
    restricted: bool
    # the target form (when there is one) is restricted
    target_restricted: bool
    changed_since_last: bool


class FormPromotionService:
    def __init__(
        self,
        authorization_service,
        workspace_form_repo,
        form_repo,
        form_spec_service,
        form_spec_writer,
        option_list_repo,
        webhook_repo,
        email_action_repo,
        registration_repo,
        audit_repo,
        idempotency_service: IdempotencyService,
        rate_limiter=None,
    ):
        self._authorization = authorization_service
        self._links = workspace_form_repo
        self._forms = form_repo
        self._spec = form_spec_service
        self._writer = form_spec_writer
        self._lists = option_list_repo
        self._webhooks = webhook_repo
        self._email_actions = email_action_repo
        self._registrations = registration_repo
        self._audit = audit_repo
        self._idempotency = idempotency_service
        self._limiter = rate_limiter

    # -- who may do what ----------------------------------------------------------

    @staticmethod
    def _session_only(user: User) -> None:
        """Promotion is a signed-in person's action: an API key's acting user has
        neither side's key semantics (a listed key cannot create, a key works in
        its own workspace only). Keys promote with the CLI, one key per side."""
        if getattr(user, "auth_method", None) == "api_key":
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content={
                    "code": SESSION_ONLY_CODE,
                    "message": "Copying a form to another workspace is done by a "
                    "signed-in person. With API keys use the command line, one "
                    "key for each workspace.",
                },
            )

    async def _source_link(self, user: User, workspace_id: RecordId, form_id: str):
        """The source form's link after the source-side checks: ``form.read`` on
        the form (404 for a form that is not there or closed to the caller), and
        for a restricted form an Owner, an Admin or its creator."""
        await self._authorization.authorize(
            user, Permission.FORM_READ, workspace_id, form_id=str(form_id)
        )
        link = await self._links.find_workspace_form(workspace_id, str(form_id))
        if link is None:
            raise _not_found()
        return link

    async def _target_permission(
        self, user: User, workspace_id: RecordId, form_id: Optional[str]
    ):
        """The target-side checks: nothing is said about a workspace the caller
        is not an active member of (404, as for one that does not exist);
        ``form.create`` there for a new form, ``form.edit`` on the form to update
        one (the form's own 404 for one that is not there or closed to them).
        Returns the target form's link, or None for a new form."""
        held = await self._authorization.effective_permissions(
            user, workspace_id, raise_sso_required=True
        )
        if not held:
            raise _not_found("Workspace not found")
        if form_id is None:
            await self._authorization.authorize(
                user, Permission.FORM_CREATE, workspace_id
            )
            return None
        await self._authorization.authorize(
            user, Permission.FORM_EDIT, workspace_id, form_id=str(form_id)
        )
        link = await self._links.find_workspace_form(workspace_id, str(form_id))
        if link is None:
            raise _not_found()
        return link

    @staticmethod
    def _check_promotable(link) -> None:
        """Only a form built from pages that this instance holds, and not an
        import still waiting for its review."""
        settings = getattr(link, "settings", None)
        provider = getattr(settings, "provider", None)
        if provider not in (None, "self"):
            raise _unprocessable(
                NOT_PROMOTABLE_CODE,
                "This form comes from another provider and cannot be copied.",
            )
        if getattr(settings, "needs_review", None):
            raise _unprocessable(
                NOT_PROMOTABLE_CODE,
                "This form is an import that has not been reviewed yet. Review it "
                "first.",
            )

    # -- reading a side -----------------------------------------------------------

    async def _side(self, workspace_id: RecordId, form_id: str, link) -> _Side:
        document = await self._forms.get_form_document_by_id(str(form_id))
        if document is None:
            raise _not_found()
        form, settings = await self._spec.load(workspace_id, form_id)
        try:
            spec = await run_in_threadpool(self._spec.spec_of, form, settings)
        except HTTPException as error:
            if error.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
                raise _unprocessable(
                    NOT_PROMOTABLE_CODE,
                    "This form is not built from pages, so it has no form document "
                    "to copy.",
                ) from error
            raise
        return _Side(
            workspace_id=workspace_id,
            form_id=str(form_id),
            spec=spec,
            etag=form_etag(document.updated_at, spec),
            link=link,
            document=document,
        )

    async def _not_carried(self, side: _Side) -> Dict[str, int]:
        """What the form has that does not move, as counts (never an address, a
        recipient or a secret)."""
        workspace_id, form_id = side.workspace_id, side.form_id
        connected = sum(len(v or []) for v in (side.document.actions or {}).values())
        return {
            "webhooks": await self._webhooks.count_for_form(workspace_id, form_id),
            "emailActions": await self._email_actions.count_for_form(
                workspace_id, form_id
            ),
            "sheets": connected,
            "registrations": await self._registrations.count_for_form(
                workspace_id, form_id
            ),
        }

    async def _list_map(
        self, source: RecordId, target: RecordId, document: Dict[str, Any]
    ) -> Dict[str, str]:
        """The source workspace's option list ids the document uses, each mapped
        to the target workspace's list of the same name (none when the target has
        no such list). List contents never move."""
        wanted = option_list_ids(document)
        if not wanted:
            return {}
        names = await self._lists.name_keys(source, wanted)
        if not names:
            return {}
        by_name = await self._lists.ids_by_name_key(target, set(names.values()))
        return {
            list_id: by_name[name] for list_id, name in names.items() if name in by_name
        }

    @staticmethod
    def _image_rule(url: str) -> Optional[str]:
        return first_party_image_url(url)

    @staticmethod
    def _pattern_ok(pattern: str) -> bool:
        return pattern_problem(pattern) is None

    # -- the plan both preview and apply share -----------------------------------

    async def _plan(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        body: PromotionRequest,
    ) -> _Plan:
        self._session_only(user)
        source_link = await self._source_link(user, source_workspace_id, source_form_id)
        target_workspace_id = RecordId(str(body.target_workspace_id))
        target_form_id = str(body.target_form_id) if body.target_form_id else None
        if target_form_id == str(source_form_id) and str(target_workspace_id) == str(
            source_workspace_id
        ):
            raise _unprocessable(
                SAME_FORM_CODE, "A form cannot be copied onto itself."
            )
        target_link = await self._target_permission(
            user, target_workspace_id, target_form_id
        )
        # after the target's permission, so that a member who may not create there
        # gets the plain refusal first
        await self._authorization.authorize_copy_out_of_workspace(
            user, source_workspace_id, source_form_id
        )
        self._check_promotable(source_link)
        source = await self._side(source_workspace_id, source_form_id, source_link)
        target = None
        if target_link is not None:
            self._check_promotable(target_link)
            target = await self._side(target_workspace_id, target_form_id, target_link)

        # the versions the person reviewed (preview: when they send them back)
        if body.source_etag is not None and body.source_etag != source.etag:
            raise precondition_failed()
        if target is not None and body.target_etag is not None:
            if body.target_etag != target.etag:
                raise precondition_failed()

        list_map = await self._list_map(
            source_workspace_id, target_workspace_id, source.spec
        )
        document, report = await run_in_threadpool(
            lambda: normalise(
                source.spec,
                image_rule=self._image_rule,
                pattern_ok=self._pattern_ok,
                list_map=list_map,
                keep_target_privacy=target is not None
                and not body.copy_data_protection,
            )
        )
        restricted = WorkspaceFormService._source_is_restricted(source_link)
        target_restricted = target is not None and (
            WorkspaceFormService._source_is_restricted(target.link)
        )
        can_edit_source = await self._authorization.has_permission(
            user, Permission.FORM_EDIT, source_workspace_id, form_id=str(source_form_id)
        )
        return _Plan(
            source=source,
            target=target,
            target_workspace_id=target_workspace_id,
            document=document,
            report=report,
            not_carried=await self._not_carried(source) if can_edit_source else None,
            restricted=restricted,
            target_restricted=target_restricted,
            changed_since_last=self._changed_since_last(target),
        )

    @staticmethod
    def _open_target_for_restricted(plan: _Plan) -> bool:
        """A restricted form's structure would land in an existing form that is
        open to more people. Never done silently: who may open an existing form
        is not changed as a side effect of copying into it."""
        return plan.restricted and plan.target is not None and not plan.target_restricted

    async def _still_restricted(self, plan: _Plan) -> None:
        """Awaited by the writer right before it writes the target: a restricted
        source's structure never lands in a form that was opened after the plan
        read its mode (no version tag covers the mode). Reads the link again, so
        what is left is the few statements between this read and the write."""
        if not plan.restricted or plan.target is None:
            return
        link = await self._links.find_workspace_form(
            plan.target_workspace_id, plan.target.form_id
        )
        if link is None:
            raise _not_found()
        if not WorkspaceFormService._source_is_restricted(link):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content={
                    "code": TARGET_NOT_RESTRICTED_CODE,
                    "message": TARGET_NOT_RESTRICTED_MESSAGE,
                },
            )

    @staticmethod
    def _changed_since_last(target: Optional[_Side]) -> bool:
        """The target form was copied into before and has been changed since
        (its document no longer is what that copy stored)."""
        if target is None:
            return False
        mark = getattr(getattr(target.link, "settings", None), "promoted_from", None)
        if mark is None or not mark.source_hash:
            return False
        return mark.source_hash != spec_hash(target.spec)

    # -- preview -------------------------------------------------------------------

    async def _validity(self, plan: _Plan) -> Dict[str, Any]:
        """``{valid, errors, warnings, compliance, diff, counts}`` of the plan's
        document as the target would store it. Stores nothing."""
        target = plan.target
        if target is not None:
            result = await self._writer.preview_replace(
                target.workspace_id, target.form_id, plan.document
            )
            diff = None
            if result["valid"] and result.get("form") is not None:
                diff = await run_in_threadpool(
                    compare_specs, target.spec, result["form"]
                )
            valid, errors = result["valid"], list(result["errors"])
            if self._open_target_for_restricted(plan):
                valid = False
                errors.append(
                    {
                        "path": "/targetFormId",
                        "code": TARGET_NOT_RESTRICTED_CODE,
                        "message": TARGET_NOT_RESTRICTED_MESSAGE,
                    }
                )
            return {
                "valid": valid,
                "errors": errors,
                "warnings": result["warnings"],
                "compliance": None,
                "diff": diff,
                "after": result.get("form"),
            }
        result = await run_in_threadpool(check_spec_document, plan.document)
        errors = list(result["errors"])
        valid = result["valid"]
        if valid:
            problem = _drafts_problem(FormSpec.model_validate(plan.document), None)
            if problem is not None:
                valid = False
                errors.append(problem)
        return {
            "valid": valid,
            "errors": errors,
            "warnings": result["warnings"],
            "compliance": result.get("compliance"),
            "diff": None,
            "after": None,
        }

    @staticmethod
    def _shortened(plan: _Plan, copy_data_protection: bool) -> bool:
        if plan.target is None or not copy_data_protection:
            return False
        before = (plan.target.spec.get("trust") or {}).get("retention")
        trust = plan.document.get("trust") or {}
        if "retention" not in trust:
            return False
        return retention_shortened(before, trust.get("retention"))

    async def preview(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        body: PromotionRequest,
    ) -> Dict[str, Any]:
        """What copying the form would do, stored nowhere: the diff for an
        existing target, the checks of the target (every error, every warning),
        what is adjusted and what is not copied, and the two ETags to send back
        to apply."""
        self._session_only(user)
        await self._rate_limit(user, READ_RATE_LIMIT_SCOPE)
        plan = await self._plan(user, source_workspace_id, source_form_id, body)
        checked = await self._validity(plan)
        counts = counts_of(plan.document)
        return {
            "valid": checked["valid"],
            "errors": checked["errors"],
            "warnings": checked["warnings"],
            "compliance": checked["compliance"],
            "created": plan.target is None,
            "diff": checked["diff"],
            "counts": counts,
            "notCarried": plan.not_carried,
            "alsoNotCopied": list(ALSO_NOT_COPIED),
            "adjusted": plan.report.to_dict(),
            # what the target will be: a new form takes its source's mode, an
            # existing one keeps its own
            "copyIsRestricted": plan.restricted
            if plan.target is None
            else plan.target_restricted,
            "sourceEtag": plan.source.etag,
            "targetEtag": plan.target.etag if plan.target else None,
            "targetChangedSinceLastPromotion": plan.changed_since_last,
            "retentionShortened": self._shortened(plan, body.copy_data_protection),
        }

    # -- the targets a person may pick ----------------------------------------------

    async def targets(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        target_workspace_id: RecordId,
        query: Optional[str],
    ) -> PromotionTargetsDto:
        """The forms of the target workspace the caller may update (``form.edit``
        on the form, a grant on it included, as they see them): the ones last
        copied from this form first, then by title; none for a member who may edit
        nothing there. ``query`` narrows by title. A workspace the caller is not a
        member of is a 404."""
        self._session_only(user)
        await self._rate_limit(user, READ_RATE_LIMIT_SCOPE)
        await self._source_link(user, source_workspace_id, source_form_id)
        held = await self._authorization.effective_permissions(
            user, target_workspace_id, raise_sso_required=True
        )
        if not held:
            raise _not_found("Workspace not found")
        links = [
            link
            for link in await self._links.list_in_workspace(target_workspace_id)
            if getattr(link.settings, "provider", None) in (None, "self")
            and not getattr(link.settings, "needs_review", None)
        ]
        every = [str(link.form_id) for link in links]
        # None: every form (the role holds form.edit and no form is closed)
        visible = await self._authorization.visible_form_ids(
            user, target_workspace_id, Permission.FORM_EDIT, every
        )
        allowed = set(every) if visible is None else set(visible)
        titles = await self._links.titles_in_workspace(target_workspace_id, allowed)
        needle = (query or "").strip().casefold()
        rows = []
        for link in links:
            form_id = str(link.form_id)
            if form_id not in allowed or form_id not in titles:
                continue
            title = titles[form_id]
            if needle and needle not in (title or "").casefold():
                continue
            mark = getattr(link.settings, "promoted_from", None)
            rows.append(
                PromotionTargetDto(
                    form_id=form_id,
                    title=title,
                    copied_from_source=bool(
                        mark is not None
                        and mark.form_id == str(source_form_id)
                        and mark.workspace_id == str(source_workspace_id)
                    ),
                )
            )
        rows.sort(key=lambda r: (not r.copied_from_source, (r.title or "").casefold()))
        return PromotionTargetsDto(
            items=rows[:TARGETS_MAX], more=len(rows) > TARGETS_MAX
        )

    # -- apply -----------------------------------------------------------------------

    @staticmethod
    def _idempotency_scope(user: User, source_form_id: str) -> str:
        return f"promotion:{user.id}:{source_form_id}"

    async def _rate_limit(self, user: User, scope: str = RATE_LIMIT_SCOPE) -> None:
        limit = live().api.EDITOR_OPS_PER_WINDOW
        if self._limiter is None or limit <= 0:
            return
        verdict = await self._limiter.hit(
            scope,
            str(user.id),
            limit,
            live().api.EDITOR_OPS_WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                content={
                    "code": RATE_LIMITED_CODE,
                    "message": "Too many copies; try again shortly.",
                },
                headers={"Retry-After": str(verdict.retry_after)},
            )

    async def apply(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        body: ApplyRequest,
        idempotency_key: Optional[str],
        path: str,
    ) -> JSONResponse:
        """Copy the form as a draft, only while both forms are still the versions
        the person reviewed. Answers 201 with the new form, 200 with the updated
        one."""
        self._session_only(user)
        if idempotency_key is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content={
                    "code": IDEMPOTENCY_KEY_REQUIRED_CODE,
                    "message": "Send an Idempotency-Key with each copy, the same "
                    "one again only when retrying it.",
                },
            )
        IdempotencyService.check_key(idempotency_key)
        # every permission is decided before a key is claimed or a form read
        # beyond what the decisions need
        await self._source_link(user, source_workspace_id, source_form_id)
        await self._target_permission(
            user,
            RecordId(str(body.target_workspace_id)),
            str(body.target_form_id) if body.target_form_id else None,
        )
        await self._rate_limit(user)
        scope = self._idempotency_scope(user, source_form_id)
        fingerprint = request_hash(
            "POST",
            path,
            json.dumps(body.model_dump(mode="json"), sort_keys=True).encode(),
        )
        stored = await self._idempotency.begin(scope, idempotency_key, fingerprint)
        if stored is not None:
            return await self._replay(user, stored)
        try:
            summary = await self._apply(
                user, source_workspace_id, source_form_id, body
            )
        except HTTPException as error:
            content = error.content if isinstance(error.content, dict) else {}
            if (
                error.status_code in _NOT_KEPT
                or content.get("code") == RETENTION_CONFIRMATION_CODE
            ):
                # a question for the person, not an outcome: the same key goes
                # again with their answer
                await self._idempotency.abandon(scope, idempotency_key)
            else:
                await self._idempotency.finish(
                    scope,
                    idempotency_key,
                    error.status_code,
                    {"kind": "body", "body": error.content},
                )
            logger.info(
                "form promotion: form {} refused with {}",
                source_form_id,
                error.status_code,
            )
            raise
        except BaseException:
            await self._idempotency.abandon(scope, idempotency_key)
            raise
        await self._idempotency.finish(
            scope,
            idempotency_key,
            201 if summary["created"] else 200,
            {"kind": "promotion", **summary},
            summary.get("etag"),
        )
        logger.info(
            "form promotion: form {} -> workspace {} form {} ({})",
            source_form_id,
            summary["workspaceId"],
            summary["formId"],
            "created" if summary["created"] else "updated",
        )
        return self._answer(summary, replayed=False)

    @staticmethod
    def _answer(summary: Dict[str, Any], replayed: bool) -> JSONResponse:
        status = 201 if summary["created"] else 200
        headers: Dict[str, str] = {}
        if summary.get("etag"):
            headers["ETag"] = summary["etag"]
        if replayed:
            headers["Idempotent-Replayed"] = "true"
        content = {k: v for k, v in summary.items() if k != "kind"}
        return JSONResponse(content, status, headers)

    async def _replay(self, user: User, stored: StoredResponse) -> JSONResponse:
        summary = json.loads(stored.body)
        if summary.get("kind") != "promotion":
            return JSONResponse(
                summary.get("body"),
                stored.status_code,
                {"Idempotent-Replayed": "true"},
            )
        # the form's version as it is now, for someone who may read that form
        # (permission to create there is not that)
        summary["etag"] = None
        workspace_id = RecordId(summary["workspaceId"])
        if await self._authorization.has_permission(
            user, Permission.FORM_READ, workspace_id, form_id=summary["formId"]
        ):
            try:
                _, summary["etag"] = await self._writer.read(
                    workspace_id, summary["formId"]
                )
            except HTTPException:
                pass
        return self._answer(summary, replayed=True)

    async def _apply(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        body: ApplyRequest,
    ) -> Dict[str, Any]:
        plan = await self._plan(user, source_workspace_id, source_form_id, body)
        if (plan.target is None) != (body.target_etag is None):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": "target_etag_mismatch",
                    "message": "Send targetEtag when updating a form, and none for "
                    "a new form.",
                },
            )
        if plan.target is not None and body.target_etag != plan.target.etag:
            raise precondition_failed()
        if self._open_target_for_restricted(plan):
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content={
                    "code": TARGET_NOT_RESTRICTED_CODE,
                    "message": TARGET_NOT_RESTRICTED_MESSAGE,
                },
            )
        checked = await self._validity(plan)
        if not checked["valid"]:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content={
                    "code": INVALID_SPEC_CODE,
                    "message": "The form cannot be copied as it is.",
                    "errors": checked["errors"],
                },
            )
        if plan.changed_since_last and not body.overwrite:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                content={
                    "code": TARGET_CHANGED_CODE,
                    "message": "The form was changed here since it was last copied "
                    "from there. Overwrite the changes, or leave it.",
                },
            )
        if self._shortened(plan, body.copy_data_protection) and not (
            body.confirm_shorter_retention
        ):
            raise _unprocessable(
                RETENTION_CONFIRMATION_CODE,
                "Copying the data protection settings shortens how long this form "
                "keeps answers. Confirm it to go on.",
            )

        # Both entries before the change: no entry, no copy. A copy that then
        # fails leaves entries for an attempt, the safe direction.
        new_form_id = str(RecordId()) if plan.target is None else None
        target_form_id = new_form_id or plan.target.form_id
        adjusted = plan.report.counts()
        await record_or_refuse(
            self._audit,
            FORM_COPIED_OUT,
            source_workspace_id,
            user,
            form_id=str(source_form_id),
            target_workspace_id=str(plan.target_workspace_id),
            target_form_id=plan.target.form_id if plan.target else None,
        )
        await record_or_refuse(
            self._audit,
            FORM_PROMOTED,
            plan.target_workspace_id,
            user,
            form_id=target_form_id,
            source_workspace_id=str(source_workspace_id),
            source_form_id=str(source_form_id),
            count=sum(adjusted.values()),
        )

        if plan.target is None:
            form_id, stored_spec, etag = await self._writer.create(
                plan.target_workspace_id,
                plan.document,
                user,
                form_id=new_form_id,
                access_mode=MODE_RESTRICTED if plan.restricted else None,
            )
        else:
            stored_spec, etag = await self._writer.replace(
                plan.target_workspace_id,
                plan.target.form_id,
                plan.document,
                [plan.target.etag],
                user,
                before_write=lambda: self._still_restricted(plan),
            )
            form_id = plan.target.form_id
        await self._mark(
            user, source_workspace_id, source_form_id, plan, form_id, stored_spec,
            adjusted,
        )
        return {
            "formId": str(form_id),
            "workspaceId": str(plan.target_workspace_id),
            "created": plan.target is None,
            "etag": etag,
            "notCarried": plan.not_carried,
            "adjusted": adjusted,
        }

    async def _mark(
        self,
        user: User,
        source_workspace_id: RecordId,
        source_form_id: str,
        plan: _Plan,
        form_id: str,
        stored_spec: Dict[str, Any],
        adjusted: Dict[str, int],
    ) -> None:
        """Where the form came from, on its link. Advisory: a failure is logged
        (ids only) and never fails a copy that is already stored (a retry would
        make a second form)."""
        mark = PromotedFrom(
            workspace_id=str(source_workspace_id),
            form_id=str(source_form_id),
            at=dt.datetime.now(dt.timezone.utc),
            by=str(user.id),
            source_hash=spec_hash(stored_spec),
            not_carried=plan.not_carried or {},
            adjusted=adjusted,
        )
        try:
            await self._links.set_promoted_from(
                plan.target_workspace_id, str(form_id), mark
            )
        except Exception as error:  # noqa: BLE001
            logger.error(
                "form promotion: the mark of form {} was not stored ({})",
                form_id,
                type(error).__name__,
            )

    # -- the form file ------------------------------------------------------------

    async def spec_file(
        self, user: User, workspace_id: RecordId, form_id: str
    ) -> JSONResponse:
        """The form's document as a download, for taking it to another instance
        (the file holds no answer). The structure leaves the workspace, so it is
        audited first, and the same people may do it as may copy it to another
        workspace. Never cached."""
        self._session_only(user)
        link = await self._source_link(user, workspace_id, form_id)
        await self._authorization.authorize_copy_out_of_workspace(
            user, workspace_id, form_id
        )
        self._check_promotable(link)
        side = await self._side(workspace_id, form_id, link)
        await record_or_refuse(
            self._audit,
            FORM_COPIED_OUT,
            workspace_id,
            user,
            form_id=str(form_id),
            # tells the download from a copy to a workspace in the Activity page
            # (it shows no other workspace's ids): the channel "file"
            export_channel=FILE_CHANNEL,
        )
        return JSONResponse(
            side.spec,
            headers={
                "Content-Disposition": f'attachment; filename="form-{form_id}.json"',
                "Cache-Control": "no-store",
                "ETag": side.etag,
            },
        )
