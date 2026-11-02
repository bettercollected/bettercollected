"""The one place that combines a member's workspace role, their grants (direct
and through teams) and a form's access mode into the permissions they hold on
that form (docs/enterprise-access-model.md, "Form-level scope").

``AuthorizationService`` calls it whenever a request names a form; services
never read a grant themselves. While ``FORM_ACCESS_ENABLED`` is off, or for an
Owner or Admin, it answers from the base access alone, without a query.

No decision is ever cached across requests: a revoked grant is effective on
the next request. Within one request, a form's facts (its mode, its creator and
the member's grants) are read once and remembered on the request context, so a
handler that authorises several times does not repeat the queries; a write
through ``invalidate`` forgets them. Outside a request (a job, a script) nothing
is remembered.
"""

import dataclasses
from dataclasses import dataclass
from typing import Callable, FrozenSet, Iterable, List, Optional, Tuple

from backend.app.models.enum.permission import Permission
from backend.app.repositories.postgres.form_access import (
    PostgresFormAccessGrantRepository,
)
from backend.app.repositories.postgres.forms import (
    PostgresWorkspaceFormRepository,
)
from backend.app.schemas.form_access_grant import FormAccessGrantDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.form_access.mode import form_access_enabled
from backend.app.services.form_access.model import (
    BaseAccess,
    FormPermissions,
    SOURCE_ROLE,
    is_restricted,
    resolve,
)
from backend.app.services.request_context import current_request

_MEMO = "form_access"


@dataclass(frozen=True)
class _Facts:
    """What the decision needs to know about one form and one member."""

    link: Optional[WorkspaceFormDocument]
    grants: Tuple[FormAccessGrantDocument, ...]


def _decide(
    base: BaseAccess, link: WorkspaceFormDocument, grants: Iterable[FormAccessGrantDocument]
) -> FormPermissions:
    settings = link.settings
    restricted = is_restricted(
        getattr(settings, "access_mode", None), getattr(settings, "hidden", None)
    )
    decided = resolve(
        base,
        restricted=restricted,
        creator=str(link.user_id) == base.user_id,
        grants=grants,
    )
    return dataclasses.replace(decided, form_found=True)


class FormAccessService:
    def __init__(
        self,
        workspace_form_repo: PostgresWorkspaceFormRepository,
        grant_repo: PostgresFormAccessGrantRepository,
        enabled: Callable[[], bool] = form_access_enabled,
    ):
        self._workspace_form_repo = workspace_form_repo
        self._grant_repo = grant_repo
        self._enabled = enabled

    # -- memo (one request) ----------------------------------------------------
    @staticmethod
    def _memo() -> Optional[dict]:
        context = current_request()
        return None if context is None else context.memo.setdefault(_MEMO, {})

    def invalidate(self) -> None:
        """Forget what this request has read (a grant, a team or a mode was
        just changed)."""
        context = current_request()
        if context is not None:
            context.memo.pop(_MEMO, None)

    async def _facts(self, base: BaseAccess, form_id: str) -> _Facts:
        memo = self._memo()
        key = (base.workspace_id, base.user_id, str(form_id))
        if memo is not None and key in memo:
            return memo[key]
        link = await self._workspace_form_repo.find_workspace_form(
            base.workspace_id, str(form_id)
        )
        grants: Tuple[FormAccessGrantDocument, ...] = ()
        if link is not None:
            grants = tuple(
                await self._grant_repo.for_user_on_form(
                    base.workspace_id, str(form_id), base.user_id
                )
            )
        facts = _Facts(link, grants)
        if memo is not None:
            memo[key] = facts
        return facts

    # -- the decision ----------------------------------------------------------
    def _passes_through(self, base: BaseAccess) -> bool:
        """Whether the base access is the answer, without looking at the form:
        the switch is off, nothing is held, the workspace is disabled (grants
        do not elevate there) or the member is an Owner or Admin."""
        return (
            not self._enabled()
            or not base.permissions
            or base.workspace_disabled
            or base.privileged
        )

    async def permissions_on(
        self, base: BaseAccess, form_id: Optional[str]
    ) -> FormPermissions:
        """What ``base``'s member may do on the form. A form that is not one of
        the workspace's decides nothing here (``form_found`` stays false: the
        caller's own 404 follows)."""
        if form_id is None or self._passes_through(base):
            return FormPermissions(base.permissions, SOURCE_ROLE)
        facts = await self._facts(base, form_id)
        if facts.link is None:
            return FormPermissions(base.permissions, SOURCE_ROLE)
        return _decide(base, facts.link, facts.grants)

    # -- lists -----------------------------------------------------------------
    async def visible_ids(
        self,
        base: BaseAccess,
        permission: Permission,
        form_ids: Optional[Iterable[str]] = None,
    ) -> Optional[FrozenSet[str]]:
        """The ids of the workspace's forms (of ``form_ids`` when given) on
        which the member holds ``permission``; ``None`` means every form: the
        switch is off, or the member is an Owner or Admin (and holds it). Two
        queries however many forms there are."""
        if self._passes_through(base):
            return None if permission in base.permissions else frozenset()
        links = await self._workspace_form_repo.list_in_workspace(base.workspace_id)
        wanted = None if form_ids is None else {str(f) for f in form_ids}
        if wanted is not None:
            links = [link for link in links if str(link.form_id) in wanted]
        grants = await self._grant_repo.for_user(
            base.workspace_id, base.user_id, wanted
        )
        by_form: dict = {}
        for grant in grants:
            by_form.setdefault(str(grant.form_id), []).append(grant)
        return frozenset(
            str(link.form_id)
            for link in links
            if permission
            in _decide(base, link, by_form.get(str(link.form_id), ())).permissions
        )

    async def filter(
        self, base: BaseAccess, form_ids: Iterable[str], permission: Permission
    ) -> List[str]:
        """``form_ids`` (in their order) on which the member holds
        ``permission``."""
        ids = [str(f) for f in form_ids]
        visible = await self.visible_ids(base, permission, ids)
        return ids if visible is None else [f for f in ids if f in visible]

    async def get_visible_link(
        self, base: BaseAccess, form_id: str
    ) -> Optional[WorkspaceFormDocument]:
        """The form's link, or ``None`` both when it is not one of the
        workspace's and when the member may not open it: the same answer, so
        a refusal never tells the two apart."""
        if not base.permissions:
            return None
        if self._passes_through(base):
            facts_link = await self._workspace_form_repo.find_workspace_form(
                base.workspace_id, str(form_id)
            )
            return facts_link if Permission.FORM_READ in base.permissions else None
        facts = await self._facts(base, form_id)
        if facts.link is None:
            return None
        decided = _decide(base, facts.link, facts.grants)
        return facts.link if Permission.FORM_READ in decided.permissions else None
