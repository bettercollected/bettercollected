"""The repository of saved report views (Postgres only, new in 5.0;
``REPORTING_ENABLED``).

Every query carries the workspace id and the form id, so a view can never be
read or changed across workspaces or forms. A private view is read only with its
owner's id in the query: no read here lists another person's private views.
"""

from typing import Iterable, List, Optional

from common.records import RecordId, decode, row_values
from common.records.repository import RecordRepository
from sqlalchemy import and_, or_, select

from backend.app.schemas.form_report_view import (
    SCOPE_FORM,
    SCOPE_PRIVATE,
    FormReportViewDocument,
)
from backend.db.models import FormReportViewRow


class ViewChanged(Exception):
    """The view was changed (or deleted) since the copy the caller holds."""

    def __init__(self, current: Optional[FormReportViewDocument]):
        super().__init__("view changed")
        self.current = current


def _ws(workspace_id) -> str:
    return str(workspace_id)


class PostgresReportViewRepository(RecordRepository):
    row = FormReportViewRow
    document = FormReportViewDocument

    @staticmethod
    def _of_form(workspace_id, form_id):
        return and_(
            FormReportViewRow.workspace_id == _ws(workspace_id),
            FormReportViewRow.form_id == str(form_id),
        )

    async def list_visible(
        self, workspace_id, form_id, user_id
    ) -> List[FormReportViewDocument]:
        """The views of a form the person may see: the form's own and their
        private ones, oldest first."""
        return await self.many(
            self._of_form(workspace_id, form_id),
            or_(
                FormReportViewRow.scope == SCOPE_FORM,
                and_(
                    FormReportViewRow.scope == SCOPE_PRIVATE,
                    FormReportViewRow.owner_id == str(user_id),
                ),
            ),
        )

    async def get_in_form(
        self, workspace_id, form_id, view_id
    ) -> Optional[FormReportViewDocument]:
        """One view of the form, whoever's (the service decides who may see it)."""
        if not _is_id(view_id):
            return None
        return await self.one(
            self._of_form(workspace_id, form_id), FormReportViewRow.id == str(view_id)
        )

    async def count_form_views(self, workspace_id, form_id) -> int:
        return await self.count(
            self._of_form(workspace_id, form_id), FormReportViewRow.scope == SCOPE_FORM
        )

    async def count_private(self, workspace_id, form_id, owner_id) -> int:
        return await self.count(
            self._of_form(workspace_id, form_id),
            FormReportViewRow.scope == SCOPE_PRIVATE,
            FormReportViewRow.owner_id == str(owner_id),
        )

    async def names_of(
        self, workspace_id, form_id, scope: str, owner_id: Optional[str]
    ) -> List[tuple]:
        """``(id, name)`` of the views a new name must not repeat: those of the
        same scope on the form, and for a private view the same owner's."""
        where = [self._of_form(workspace_id, form_id), FormReportViewRow.scope == scope]
        if scope == SCOPE_PRIVATE:
            where.append(FormReportViewRow.owner_id == str(owner_id))
        return [(str(view.id), view.name) for view in await self.many(*where)]

    async def add(self, view: FormReportViewDocument) -> FormReportViewDocument:
        return await self.upsert(view)

    async def replace(
        self, view: FormReportViewDocument, expected_revision: int
    ) -> FormReportViewDocument:
        """Store ``view`` (a copy of the stored one, changed) when the stored
        revision is still ``expected_revision``, in one transaction on the
        locked row; otherwise ``ViewChanged`` with what is stored now."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormReportViewRow.doc)
                    .where(FormReportViewRow.id == str(view.id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            stored = None if doc is None else decode(FormReportViewDocument, doc)
            if stored is None or stored.revision != expected_revision:
                raise ViewChanged(stored)
            view.revision = expected_revision + 1
            view.touch()
            await session.execute(self._upsert_statement(row_values(view)))
        return view

    async def delete_view(self, workspace_id, form_id, view_id, revision: int) -> bool:
        """Delete the view when it is still at ``revision``; False when it is
        gone already, ``ViewChanged`` when it changed."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(FormReportViewRow.doc)
                    .where(
                        self._of_form(workspace_id, form_id),
                        FormReportViewRow.id == str(view_id),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return False
            stored = decode(FormReportViewDocument, doc)
            if stored.revision != revision:
                raise ViewChanged(stored)
            await self._delete_recorded(
                session, FormReportViewRow, FormReportViewRow.id == str(view_id)
            )
        return True

    # -- clean-up: data hygiene, done whatever the switch says --------------
    async def delete_for_form(self, workspace_id, form_id) -> int:
        return await self.delete_where(self._of_form(workspace_id, form_id))

    async def delete_for_forms(self, form_ids: Iterable[str]) -> int:
        ids = [str(f) for f in form_ids]
        return await self.delete_where(FormReportViewRow.form_id.in_(ids)) if ids else 0

    async def delete_for_workspaces(self, workspace_ids: Iterable) -> int:
        """Every view of workspaces that are being deleted (the forms they shared
        with workspaces that stay keep their rows otherwise)."""
        ids = [_ws(w) for w in workspace_ids]
        return await self.delete_where(FormReportViewRow.workspace_id.in_(ids)) if ids else 0

    async def delete_private_of_account(self, user_id) -> int:
        """The private views of an account that is being deleted, in every
        workspace (the form views it made stay, as a former member's)."""
        return await self.delete_where(
            FormReportViewRow.owner_id == str(user_id),
            FormReportViewRow.scope == SCOPE_PRIVATE,
        )

    async def delete_private_of_member(self, workspace_id, user_id) -> int:
        """The private views of a member who leaves the workspace (a form's own
        views they made stay, named "a former member")."""
        return await self.delete_where(
            FormReportViewRow.workspace_id == _ws(workspace_id),
            FormReportViewRow.owner_id == str(user_id),
            FormReportViewRow.scope == SCOPE_PRIVATE,
        )


def _is_id(value) -> bool:
    try:
        return len(str(value)) == 24 and int(str(value), 16) >= 0
    except ValueError:
        return False
