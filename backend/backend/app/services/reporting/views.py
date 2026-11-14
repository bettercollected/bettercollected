"""Saved views of a form's report (``REPORTING_ENABLED``, docs/reporting.md).

A view is a name, a scope and a validated report definition. Who may do what:

* **Open** a view: anyone who may open the form's report (``response.read`` and
  ``analytics.read`` on the form, ``ReportService.authorize``) sees the form's own
  views and their own private ones. Another person's private view is a 404, for
  everyone, owner and admin of the workspace included: it is a notebook.
* **Private views** (the default) are created, changed and deleted by their owner
  alone, to the number of ``VIEWS_PRIVATE_MAX`` per person and form.
* **Form views** need ``form.edit`` on the form to be created, changed (also by
  another editor, they are the form's) or deleted by the person who made them; one
  made by someone else is deleted by a holder of ``members.manage`` (an owner or an
  admin: moderation), and nobody but its creator takes it back to private. At most
  ``VIEWS_FORM_MAX`` per form.
* **What is stored** is the definition as ``definition.parse`` and ``validate``
  accept it for this caller, the same checks as a query: ids, enums, numbers and
  dates, never an answer, an identity or a respondent's text. The name is text the
  staff member typed: shown, never logged and never in an audit entry.
* **Changes** carry the ``revision`` they were made from: a stale one is refused
  (409 ``view_changed``), a name already used by another view of the same scope
  (and owner, for a private one) is refused (409 ``view_name_taken``).
* **Audit.** Changes that involve the form's shared views (a form view created,
  changed or deleted, a view shared or taken back) are written before they are
  made, ids and enum values only (``REPORT_EVENTS``); the notebook of a person is
  not (an entry would say that someone looked at something).

Running a view is a query: the page posts the stored definition to
``/report/query``, which validates it again (a form change can invalidate it).
"""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from typing import Any, Dict, List, Literal, Optional

from common.ids import RecordId
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.report_views import (
    PostgresReportViewRepository,
    ViewChanged,
)
from backend.app.schemas.form_report_view import (
    SCOPE_FORM,
    SCOPE_PRIVATE,
    FormReportViewDocument,
)
from backend.app.schemas.workspace_audit_event import (
    REPORT_VIEW_CREATED,
    REPORT_VIEW_DELETED,
    REPORT_VIEW_SHARED,
    REPORT_VIEW_UNSHARED,
    REPORT_VIEW_UPDATED,
)
from backend.app.services.form_access import audit
from backend.app.services.reporting import limits
from backend.app.services.reporting.definition import invalid as invalid_definition

NOT_FOUND_CODE = "view_not_found"
INVALID_CODE = "invalid_view"
CHANGED_CODE = "view_changed"
NAME_TAKEN_CODE = "view_name_taken"
LIMIT_CODE = "view_limit"
FORBIDDEN_CODE = "view_forbidden"

# letters, digits, punctuation and spaces: no control characters
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message})


def _not_found() -> HTTPException:
    return _error(HTTPStatus.NOT_FOUND, NOT_FOUND_CODE, "No such view.")


def _changed() -> HTTPException:
    return _error(
        HTTPStatus.CONFLICT,
        CHANGED_CODE,
        "This view was changed by someone else. Reload to see it.",
    )


def _forbidden(message: str) -> HTTPException:
    return _error(HTTPStatus.FORBIDDEN, FORBIDDEN_CODE, message)


class _Body(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=to_camel
    )


class ViewCreate(_Body):
    name: str
    scope: Literal["private", "form"] = SCOPE_PRIVATE
    definition: Dict[str, Any]


class ViewChange(_Body):
    revision: int = Field(ge=1, le=1_000_000)
    name: Optional[str] = None
    scope: Optional[Literal["private", "form"]] = None
    definition: Optional[Dict[str, Any]] = None


def parse_body(model, body: bytes):
    """The request body as ``model``, or 422 ``invalid_view``: a path and a
    rule, never a value."""
    if len(body) > limits.VIEW_BODY_MAX_BYTES:
        raise _error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID_CODE,
            f"A view request is at most {limits.VIEW_BODY_MAX_BYTES} bytes.",
        )
    try:
        return model.model_validate_json(body)
    except ValidationError as problem:
        first = problem.errors(
            include_url=False, include_context=False, include_input=False
        )[0]
        where = ".".join(str(part) for part in first["loc"]) or "body"
        raise _error(
            HTTPStatus.UNPROCESSABLE_ENTITY, INVALID_CODE, f"{where}: {first['msg']}"
        ) from None


def clean_name(name: str) -> str:
    """The name, trimmed; 422 when it is empty, too long or holds control
    characters."""
    name = (name or "").strip()
    if not name or len(name) > limits.VIEW_NAME_MAX or _CONTROL.search(name):
        raise _error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID_CODE,
            f"name: one to {limits.VIEW_NAME_MAX} characters, no control characters.",
        )
    return name


class ReportViewService:
    def __init__(
        self,
        authorization_service,
        report_service,
        view_repo: PostgresReportViewRepository,
        member_directory=None,
        audit_repo=None,
    ):
        self._authorization = authorization_service
        self._reports = report_service
        self._repo = view_repo
        self._directory = member_directory
        self._audit = audit_repo

    # ------------------------------------------------------------------ helpers
    async def _may(
        self, user: User, permission: Permission, workspace_id, form_id: Optional[str]
    ) -> bool:
        return await self._authorization.has_permission(
            user, permission, workspace_id, form_id=form_id
        )

    async def _need_form_edit(self, user, workspace_id, form_id, message: str) -> None:
        if not await self._may(user, Permission.FORM_EDIT, workspace_id, form_id):
            raise _forbidden(message)

    async def _owner_names(self, workspace_id, views, me: str) -> Dict[str, str]:
        owners = {v.owner_id for v in views if v.owner_id != me}
        if not owners or self._directory is None:
            return {}
        try:
            _, names = await self._directory.lookup(workspace_id, owners, timeout=3)
        except Exception:  # noqa: BLE001 - names are best effort
            return {}
        return names

    def _dto(
        self,
        view: FormReportViewDocument,
        user: User,
        names: Dict[str, str],
        may_edit_form: bool,
        may_moderate: bool,
    ) -> Dict[str, Any]:
        mine = view.owner_id == str(user.id)
        shared = view.scope == SCOPE_FORM
        return {
            "id": str(view.id),
            "name": view.name,
            "scope": view.scope,
            "mine": mine,
            # "a former member" when the owner is not a current member (no name)
            "ownerName": None if mine else names.get(view.owner_id),
            "revision": view.revision,
            "createdAt": view.created_at.isoformat() if view.created_at else None,
            "updatedAt": view.updated_at.isoformat() if view.updated_at else None,
            "definition": view.definition,
            "canEdit": may_edit_form if shared else mine,
            "canDelete": (may_edit_form and (mine or may_moderate)) if shared else mine,
        }

    async def _one_dto(self, view, user, workspace_id, form_id) -> Dict[str, Any]:
        may_edit = await self._may(user, Permission.FORM_EDIT, workspace_id, form_id)
        may_moderate = await self._may(user, Permission.MEMBERS_MANAGE, workspace_id, None)
        names = await self._owner_names(workspace_id, [view], str(user.id))
        return self._dto(view, user, names, may_edit, may_moderate)

    async def _visible(self, user, workspace_id, form_id, view_id) -> FormReportViewDocument:
        """The view, or 404: a missing one and another person's private one
        answer alike."""
        view = await self._repo.get_in_form(workspace_id, form_id, view_id)
        if view is None or (view.scope == SCOPE_PRIVATE and view.owner_id != str(user.id)):
            raise _not_found()
        return view

    async def _check_name(
        self, workspace_id, form_id, scope, owner_id, name: str, own_id: Optional[str] = None
    ) -> None:
        taken = await self._repo.names_of(workspace_id, form_id, scope, owner_id)
        wanted = name.casefold()
        if any(id_ != own_id and other.casefold() == wanted for id_, other in taken):
            raise _error(
                HTTPStatus.CONFLICT,
                NAME_TAKEN_CODE,
                "Another view already has this name.",
            )

    async def _check_room(self, workspace_id, form_id, scope, owner_id) -> None:
        if scope == SCOPE_FORM:
            full = await self._repo.count_form_views(workspace_id, form_id) >= limits.VIEWS_FORM_MAX
            cap = limits.VIEWS_FORM_MAX
        else:
            full = await self._repo.count_private(workspace_id, form_id, owner_id) >= limits.VIEWS_PRIVATE_MAX
            cap = limits.VIEWS_PRIVATE_MAX
        if full:
            raise _error(
                HTTPStatus.CONFLICT,
                LIMIT_CODE,
                f"A {'form' if scope == SCOPE_FORM else 'person'} has at most {cap} saved views here. Delete one first.",
            )

    async def _definition(self, user, workspace_id, form_id, raw: Dict[str, Any]) -> Dict[str, Any]:
        """The definition validated as a query would, in the shape it is stored.
        A card's ``title`` is a request-only caption: a stored view does not hold one
        (a name chosen by a person would have to be reviewed like the view's own)."""
        cards = raw.get("cards")
        if isinstance(cards, list):
            for index, card in enumerate(cards):
                if isinstance(card, dict) and card.get("title") is not None:
                    raise invalid_definition(
                        f"cards.{index}.title: a saved view does not hold a card title."
                    )
        checked = await self._reports.check_definition(
            user, workspace_id, form_id, json.dumps(raw).encode()
        )
        return checked.model_dump(mode="json", by_alias=True, exclude_none=True)

    # --------------------------------------------------------------------- reads
    async def list(self, user: User, workspace_id: RecordId, form_id: str) -> Dict[str, Any]:
        await self._reports.authorize(user, workspace_id, form_id=form_id)
        views = await self._repo.list_visible(workspace_id, form_id, str(user.id))
        may_edit = await self._may(user, Permission.FORM_EDIT, workspace_id, form_id)
        may_moderate = await self._may(user, Permission.MEMBERS_MANAGE, workspace_id, None)
        names = await self._owner_names(workspace_id, views, str(user.id))
        return {
            "views": [self._dto(v, user, names, may_edit, may_moderate) for v in views],
            "canShare": may_edit,
            "limits": {
                "nameMax": limits.VIEW_NAME_MAX,
                "formViews": limits.VIEWS_FORM_MAX,
                "privateViews": limits.VIEWS_PRIVATE_MAX,
            },
        }

    async def get(self, user: User, workspace_id: RecordId, form_id: str, view_id: str) -> Dict[str, Any]:
        await self._reports.authorize(user, workspace_id, form_id=form_id)
        view = await self._visible(user, workspace_id, form_id, view_id)
        return await self._one_dto(view, user, workspace_id, form_id)

    # -------------------------------------------------------------------- writes
    async def create(self, user: User, workspace_id: RecordId, form_id: str, body: bytes) -> Dict[str, Any]:
        await self._reports.authorize(user, workspace_id, form_id=form_id)
        request = parse_body(ViewCreate, body)
        if request.scope == SCOPE_FORM:
            await self._need_form_edit(
                user, workspace_id, form_id, "Only someone who may edit the form can save a view for everyone."
            )
        name = clean_name(request.name)
        owner = str(user.id)
        definition = await self._definition(user, workspace_id, form_id, request.definition)
        await self._check_name(workspace_id, form_id, request.scope, owner, name)
        await self._check_room(workspace_id, form_id, request.scope, owner)
        view = FormReportViewDocument(
            id=RecordId(),
            workspace_id=RecordId(str(workspace_id)),
            form_id=str(form_id),
            owner_id=owner,
            scope=request.scope,
            name=name,
            definition=definition,
        )
        if view.scope == SCOPE_FORM:
            await audit.record_or_refuse(
                self._audit, REPORT_VIEW_CREATED, workspace_id, user,
                form_id=str(form_id), view_id=str(view.id), view_scope=view.scope,
            )
        await self._repo.add(view)
        return await self._one_dto(view, user, workspace_id, form_id)

    async def update(
        self, user: User, workspace_id: RecordId, form_id: str, view_id: str, body: bytes
    ) -> Dict[str, Any]:
        await self._reports.authorize(user, workspace_id, form_id=form_id)
        request = parse_body(ViewChange, body)
        view = await self._visible(user, workspace_id, form_id, view_id)
        mine = view.owner_id == str(user.id)
        before_scope = view.scope
        after_scope = request.scope or before_scope
        if before_scope == SCOPE_FORM:
            await self._need_form_edit(
                user, workspace_id, form_id, "Only someone who may edit the form can change a view of the form."
            )
        if before_scope == SCOPE_FORM and after_scope == SCOPE_PRIVATE and not mine:
            raise _forbidden("Only the person who made a view of the form can make it private.")
        if before_scope == SCOPE_PRIVATE and after_scope == SCOPE_FORM:
            await self._need_form_edit(
                user, workspace_id, form_id, "Only someone who may edit the form can share a view."
            )
        changed: List[str] = []
        updated = view.model_copy(deep=True)
        if request.name is not None:
            name = clean_name(request.name)
            if name != view.name:
                changed.append("name")
            updated.name = name
        if request.definition is not None:
            definition = await self._definition(user, workspace_id, form_id, request.definition)
            if definition != view.definition:
                changed.append("definition")
            updated.definition = definition
        if after_scope != before_scope:
            changed.append("scope")
            updated.scope = after_scope
            # a view made private is its maker's; a view shared stays its owner's
            await self._check_room(workspace_id, form_id, after_scope, view.owner_id)
        if "name" in changed or "scope" in changed:
            await self._check_name(
                workspace_id, form_id, after_scope, view.owner_id, updated.name, own_id=str(view.id)
            )
        if not changed:
            return await self._one_dto(view, user, workspace_id, form_id)
        if request.revision != view.revision:
            # a stale request writes nothing, and leaves no audit entry for a change that did not happen
            raise _changed()
        involved = SCOPE_FORM in (before_scope, after_scope)
        if involved:
            if before_scope == SCOPE_PRIVATE:
                event = REPORT_VIEW_SHARED
            elif after_scope == SCOPE_PRIVATE:
                event = REPORT_VIEW_UNSHARED
            else:
                event = REPORT_VIEW_UPDATED
            await audit.record_or_refuse(
                self._audit, event, workspace_id, user,
                form_id=str(form_id), view_id=str(view.id), view_scope=after_scope,
                changed=changed,
            )
        try:
            stored = await self._repo.replace(updated, request.revision)
        except ViewChanged:
            raise _changed() from None
        return await self._one_dto(stored, user, workspace_id, form_id)

    async def delete(
        self,
        user: User,
        workspace_id: RecordId,
        form_id: str,
        view_id: str,
        revision: Optional[int] = None,
    ) -> None:
        await self._reports.authorize(user, workspace_id, form_id=form_id)
        view = await self._visible(user, workspace_id, form_id, view_id)
        mine = view.owner_id == str(user.id)
        if view.scope == SCOPE_FORM:
            await self._need_form_edit(
                user, workspace_id, form_id, "Only someone who may edit the form can delete a view of the form."
            )
            if not mine and not await self._may(user, Permission.MEMBERS_MANAGE, workspace_id, None):
                raise _forbidden("Only the person who made a view of the form, an owner or an admin can delete it.")
            if revision is not None and revision != view.revision:
                # the person saw an older view: nothing is deleted, nothing is audited
                raise _changed()
            await audit.record_or_refuse(
                self._audit, REPORT_VIEW_DELETED, workspace_id, user,
                form_id=str(form_id), view_id=str(view.id), view_scope=view.scope,
            )
        if revision is not None and revision != view.revision:
            raise _changed()
        try:
            await self._repo.delete_view(workspace_id, form_id, view.id, view.revision)
        except ViewChanged:
            raise _changed() from None
